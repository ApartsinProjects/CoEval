"""
Tests for runner.metric_judge — non-LLM metric judges.

All tests use in-memory data and mock heavy dependencies (bert_score, nltk).
No network calls, no model weights.
"""
from __future__ import annotations

from unittest.mock import patch, MagicMock

import pytest

from runner.metric_judge import (
    SUPPORTED_METRICS,
    METRIC_FACTOR_DEFS,
    compute_metric,
    is_metric_factor,
    split_rubric,
    score_metric_factors,
    make_metric_factor,
)


# ---------------------------------------------------------------------------
# exact_match — no mocks needed
# ---------------------------------------------------------------------------

def test_compute_metric_exact_match_identical():
    assert compute_metric("exact_match", "Paris", "Paris") == 1.0


def test_compute_metric_exact_match_different():
    assert compute_metric("exact_match", "London", "Paris") == 0.0


def test_compute_metric_exact_match_case_insensitive():
    assert compute_metric("exact_match", "PARIS", "paris") == 1.0


def test_compute_metric_exact_match_pipe_separated():
    """Pipe-separated reference: hypothesis matches one of the alternatives."""
    assert compute_metric("exact_match", "B", "A|B|C") == 1.0


def test_compute_metric_exact_match_pipe_separated_no_match():
    assert compute_metric("exact_match", "D", "A|B|C") == 0.0


def test_compute_metric_exact_match_whitespace():
    """Leading/trailing whitespace is stripped before comparison."""
    assert compute_metric("exact_match", "  hello  ", "hello") == 1.0


def test_compute_metric_exact_match_empty_strings():
    assert compute_metric("exact_match", "", "") == 1.0


def test_compute_metric_exact_match_empty_vs_nonempty():
    assert compute_metric("exact_match", "", "Paris") == 0.0


# ---------------------------------------------------------------------------
# bertscore — mocked
# ---------------------------------------------------------------------------

def test_compute_metric_bertscore_mocked():
    """BERTScore: mock the bert_score.score function, verify dispatch."""
    import torch

    fake_P = MagicMock()
    fake_R = MagicMock()
    fake_F1 = MagicMock()
    fake_F1.__getitem__ = lambda self, idx: torch.tensor(0.87)

    with patch("runner.metric_judge._require_bertscore") as mock_req:
        mock_bs = MagicMock(return_value=(fake_P, fake_R, fake_F1))
        mock_req.return_value = mock_bs

        result = compute_metric("bertscore", "hypothesis text", "reference text")

    assert isinstance(result, float)
    assert 0.0 <= result <= 1.0
    mock_bs.assert_called_once()
    call_args = mock_bs.call_args
    assert call_args[0][0] == ["hypothesis text"]
    assert call_args[0][1] == ["reference text"]


def test_compute_metric_bertscore_empty_hypothesis():
    """Empty hypothesis returns 0.0 without calling bert_score."""
    result = compute_metric("bertscore", "", "reference text")
    assert result == 0.0


def test_compute_metric_bertscore_empty_reference():
    """Empty reference returns 0.0 without calling bert_score."""
    result = compute_metric("bertscore", "hypothesis text", "")
    assert result == 0.0


# ---------------------------------------------------------------------------
# bleu — mocked
# ---------------------------------------------------------------------------

def test_compute_metric_bleu_mocked():
    """BLEU: mock nltk, verify dispatch."""
    mock_sentence_bleu = MagicMock(return_value=0.42)

    class MockSmoothingFunction:
        def method1(self, *args, **kwargs):
            pass

    with patch("runner.metric_judge._require_nltk_bleu") as mock_req:
        mock_req.return_value = (mock_sentence_bleu, MockSmoothingFunction)
        result = compute_metric("bleu", "the cat sat", "the cat sat on the mat")

    assert isinstance(result, float)
    assert result == 0.42
    mock_sentence_bleu.assert_called_once()


def test_compute_metric_bleu_empty_hypothesis():
    """Empty hypothesis returns 0.0 without calling nltk."""
    mock_sentence_bleu = MagicMock()

    class MockSmoothingFunction:
        def method1(self, *args, **kwargs):
            pass

    with patch("runner.metric_judge._require_nltk_bleu") as mock_req:
        mock_req.return_value = (mock_sentence_bleu, MockSmoothingFunction)
        result = compute_metric("bleu", "", "the cat sat on the mat")

    assert result == 0.0
    mock_sentence_bleu.assert_not_called()


# ---------------------------------------------------------------------------
# Unknown metric
# ---------------------------------------------------------------------------

def test_compute_metric_unknown_raises():
    with pytest.raises(ValueError, match="Unknown metric 'rouge'"):
        compute_metric("rouge", "a", "b")


# ---------------------------------------------------------------------------
# is_metric_factor
# ---------------------------------------------------------------------------

def test_is_metric_factor_true():
    assert is_metric_factor({"metric": "bertscore", "description": "F1"}) is True


def test_is_metric_factor_false_string():
    assert is_metric_factor("How accurate is the response") is False


def test_is_metric_factor_false_dict_no_metric():
    assert is_metric_factor({"description": "F1"}) is False


def test_is_metric_factor_false_none():
    assert is_metric_factor(None) is False


def test_is_metric_factor_false_int():
    assert is_metric_factor(42) is False


# ---------------------------------------------------------------------------
# split_rubric
# ---------------------------------------------------------------------------

def test_split_rubric_mixed():
    rubric = {
        "accuracy": "All key facts are preserved",
        "bertscore_f1": {"metric": "bertscore", "description": "BERTScore F1"},
        "conciseness": "Brief without unnecessary detail",
    }
    llm, metric = split_rubric(rubric)
    assert llm == {
        "accuracy": "All key facts are preserved",
        "conciseness": "Brief without unnecessary detail",
    }
    assert metric == {
        "bertscore_f1": {"metric": "bertscore", "description": "BERTScore F1"},
    }


def test_split_rubric_all_llm():
    rubric = {"accuracy": "good", "style": "nice"}
    llm, metric = split_rubric(rubric)
    assert llm == rubric
    assert metric == {}


def test_split_rubric_all_metric():
    rubric = {
        "bertscore_f1": {"metric": "bertscore", "description": "F1"},
        "exact_match": {"metric": "exact_match", "description": "EM"},
    }
    llm, metric = split_rubric(rubric)
    assert llm == {}
    assert metric == rubric


def test_split_rubric_empty():
    llm, metric = split_rubric({})
    assert llm == {}
    assert metric == {}


# ---------------------------------------------------------------------------
# score_metric_factors (integration with real exact_match)
# ---------------------------------------------------------------------------

def test_score_metric_factors_exact_match():
    metric_factors = {
        "exact_match": {"metric": "exact_match", "description": "EM"},
    }
    scores = score_metric_factors(metric_factors, "Paris", "Paris")
    assert scores == {"exact_match": "1.0"}


def test_score_metric_factors_exact_match_mismatch():
    metric_factors = {
        "exact_match": {"metric": "exact_match", "description": "EM"},
    }
    scores = score_metric_factors(metric_factors, "London", "Paris")
    assert scores == {"exact_match": "0.0"}


def test_score_metric_factors_returns_rounded_strings():
    """Metric factor scores are 4-decimal rounded float strings."""
    metric_factors = {
        "exact_match": {"metric": "exact_match", "description": "EM"},
    }
    scores = score_metric_factors(metric_factors, "Paris", "Paris")
    # 1.0 rounded to 4 decimals is "1.0"
    assert isinstance(scores["exact_match"], str)
    val = float(scores["exact_match"])
    assert 0.0 <= val <= 1.0


def test_score_metric_factors_multiple_factors():
    """Score two metric factors at once."""
    mock_sentence_bleu = MagicMock(return_value=0.55555)

    class MockSmoothingFunction:
        def method1(self, *args, **kwargs):
            pass

    metric_factors = {
        "exact_match": {"metric": "exact_match", "description": "EM"},
        "bleu4": {"metric": "bleu", "description": "BLEU-4"},
    }
    with patch("runner.metric_judge._require_nltk_bleu") as mock_req:
        mock_req.return_value = (mock_sentence_bleu, MockSmoothingFunction)
        scores = score_metric_factors(metric_factors, "hello world", "hello world")

    assert "exact_match" in scores
    assert "bleu4" in scores
    assert scores["exact_match"] == "1.0"
    assert scores["bleu4"] == "0.5555"  # rounded to 4 decimals (0.55555 rounds half-even)


# ---------------------------------------------------------------------------
# make_metric_factor
# ---------------------------------------------------------------------------

def test_make_metric_factor_bertscore():
    name, defn = make_metric_factor("bertscore")
    assert name == "bertscore_f1"
    assert defn["metric"] == "bertscore"
    assert "description" in defn


def test_make_metric_factor_bleu():
    name, defn = make_metric_factor("bleu")
    assert name == "bleu4"
    assert defn["metric"] == "bleu"


def test_make_metric_factor_exact_match():
    name, defn = make_metric_factor("exact_match")
    assert name == "exact_match"
    assert defn["metric"] == "exact_match"


def test_make_metric_factor_unknown_raises():
    with pytest.raises(ValueError, match="No default factor definition"):
        make_metric_factor("rouge")


# ---------------------------------------------------------------------------
# SUPPORTED_METRICS / METRIC_FACTOR_DEFS consistency
# ---------------------------------------------------------------------------

def test_supported_metrics_complete():
    """Every SUPPORTED_METRICS entry has a matching METRIC_FACTOR_DEFS entry."""
    for metric in SUPPORTED_METRICS:
        assert metric in METRIC_FACTOR_DEFS, (
            f"Metric '{metric}' in SUPPORTED_METRICS but not in METRIC_FACTOR_DEFS"
        )


def test_metric_factor_defs_reference_supported():
    """Every METRIC_FACTOR_DEFS entry references a supported metric."""
    for key, defn in METRIC_FACTOR_DEFS.items():
        assert defn["metric"] in SUPPORTED_METRICS, (
            f"METRIC_FACTOR_DEFS['{key}'] references '{defn['metric']}' "
            f"which is not in SUPPORTED_METRICS"
        )


def test_supported_metrics_is_frozenset():
    """SUPPORTED_METRICS should be immutable."""
    assert isinstance(SUPPORTED_METRICS, frozenset)


def test_metric_factor_defs_have_required_keys():
    """Each METRIC_FACTOR_DEFS entry has factor_name, metric, description."""
    for key, defn in METRIC_FACTOR_DEFS.items():
        assert "factor_name" in defn, f"Missing factor_name in METRIC_FACTOR_DEFS['{key}']"
        assert "metric" in defn, f"Missing metric in METRIC_FACTOR_DEFS['{key}']"
        assert "description" in defn, f"Missing description in METRIC_FACTOR_DEFS['{key}']"
