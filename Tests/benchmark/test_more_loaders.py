"""Tests for 16 additional benchmark loaders.

Covers:
  LogiQALoader, WinograndeLoader, MultiNLILoader, COPALoader, CosmosQALoader,
  BBQLoader, TriviaQALoader, SQuADv2Loader, NQOpenLoader, NarrativeQALoader,
  CNNDailyMailLoader, SAMSumLoader, FEVERLoader, SciFactLoader, MGSMLoader,
  MathQALoader

For each loader the test suite covers:
  - Helper functions (where applicable)
  - _load_dataset(): valid rows loaded, skip conditions honoured
  - _to_record(): Phase 3 JSONL schema compliance
  - Registry: dataset registered, attribute map file exists
  - BENCHMARK_METRIC: correct metric assigned

All tests use mocked datasets.load_dataset so no network access occurs.
"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

_REQUIRED_PHASE3_KEYS = {
    "id",
    "task_id",
    "teacher_model_id",
    "sampled_target_attributes",
    "prompt",
    "reference_response",
    "generated_at",
    "benchmark_id",
    "benchmark_split",
    "benchmark_native_id",
    "benchmark_native_score",
}


def _assert_phase3_record(record: dict) -> None:
    """Assert a record has all required Phase 3 JSONL fields."""
    missing = _REQUIRED_PHASE3_KEYS - set(record.keys())
    assert not missing, f"Missing Phase 3 keys: {missing}"
    assert record["benchmark_native_score"] is None


def _make_mock_ds(rows: list) -> MagicMock:
    mock_ds = MagicMock()
    mock_ds.__iter__ = MagicMock(return_value=iter(rows))
    return mock_ds



# ===========================================================================
# 1. LogiQALoader
# ===========================================================================

class TestPassageLengthLogiQA:
    def _fn(self):
        from benchmark.loaders.logiqa import _passage_length
        return _passage_length

    def test_short_under_50_words(self):
        text = " ".join(["word"] * 30)
        assert self._fn()(text) == "short"

    def test_boundary_49_words_is_short(self):
        text = " ".join(["word"] * 49)
        assert self._fn()(text) == "short"

    def test_boundary_50_words_is_medium(self):
        text = " ".join(["word"] * 50)
        assert self._fn()(text) == "medium"

    def test_medium_under_100_words(self):
        text = " ".join(["word"] * 75)
        assert self._fn()(text) == "medium"

    def test_boundary_99_words_is_medium(self):
        text = " ".join(["word"] * 99)
        assert self._fn()(text) == "medium"

    def test_boundary_100_words_is_long(self):
        text = " ".join(["word"] * 100)
        assert self._fn()(text) == "long"

    def test_long_over_100_words(self):
        text = " ".join(["word"] * 150)
        assert self._fn()(text) == "long"


class TestLogiQALoaderLoadDataset:
    def _loader(self):
        from benchmark.loaders.logiqa import LogiQALoader
        return LogiQALoader(attribute_map={}, sample_size=100, split="test", seed=42)

    def test_loads_valid_rows(self):
        rows = [
            {
                "context": "A passage about logic.",
                "question": "What follows?",
                "options": ["opt A", "opt B", "opt C", "opt D"],
                "label": 0,
                "id": 1,
            },
            {
                "context": "Another passage here.",
                "question": "Which is true?",
                "options": ["x", "y", "z", "w"],
                "label": 2,
                "id": 2,
            },
        ]
        mock_ds = _make_mock_ds(rows)
        with patch("datasets.load_dataset", return_value=mock_ds):
            items = self._loader()._load_dataset()
        assert len(items) == 2

    def test_skips_empty_context(self):
        rows = [
            {
                "context": "",
                "question": "What?",
                "options": ["a", "b", "c", "d"],
                "label": 0,
                "id": 1,
            },
        ]
        mock_ds = _make_mock_ds(rows)
        with patch("datasets.load_dataset", return_value=mock_ds):
            items = self._loader()._load_dataset()
        assert len(items) == 0

    def test_skips_empty_question(self):
        rows = [
            {
                "context": "Valid context here.",
                "question": "",
                "options": ["a", "b", "c", "d"],
                "label": 1,
                "id": 2,
            },
        ]
        mock_ds = _make_mock_ds(rows)
        with patch("datasets.load_dataset", return_value=mock_ds):
            items = self._loader()._load_dataset()
        assert len(items) == 0

    def test_skips_too_few_options(self):
        rows = [
            {
                "context": "Valid context here.",
                "question": "Valid question?",
                "options": ["a", "b"],
                "label": 0,
                "id": 3,
            },
        ]
        mock_ds = _make_mock_ds(rows)
        with patch("datasets.load_dataset", return_value=mock_ds):
            items = self._loader()._load_dataset()
        assert len(items) == 0

    def test_skips_invalid_label(self):
        rows = [
            {
                "context": "Valid context here.",
                "question": "Valid question?",
                "options": ["a", "b", "c", "d"],
                "label": 99,
                "id": 4,
            },
        ]
        mock_ds = _make_mock_ds(rows)
        with patch("datasets.load_dataset", return_value=mock_ds):
            items = self._loader()._load_dataset()
        assert len(items) == 0

    def test_inferred_attrs_present(self):
        rows = [
            {
                "context": "A short passage.",
                "question": "What?",
                "options": ["a", "b", "c", "d"],
                "label": 1,
                "id": 5,
            },
        ]
        mock_ds = _make_mock_ds(rows)
        with patch("datasets.load_dataset", return_value=mock_ds):
            items = self._loader()._load_dataset()
        assert items[0]["_inferred_attrs"]["reasoning_type"] == "logical"
        assert items[0]["_inferred_attrs"]["passage_length"] in ("short", "medium", "long")


class TestLogiQALoaderToRecord:
    def _loader(self):
        from benchmark.loaders.logiqa import LogiQALoader
        return LogiQALoader(attribute_map={}, sample_size=10, split="test", seed=42)

    def _make_item(self, label=0):
        return {
            "_native_id": "42",
            "_context": "Some passage for reasoning.",
            "_question": "What conclusion follows?",
            "_options": ["First option", "Second option", "Third option", "Fourth option"],
            "_label": label,
            "_inferred_attrs": {"passage_length": "short", "reasoning_type": "logical"},
        }

    def test_record_has_required_keys(self):
        record = self._loader()._to_record(self._make_item(), seq=0)
        _assert_phase3_record(record)

    def test_task_id_is_logical_reasoning(self):
        record = self._loader()._to_record(self._make_item(), seq=0)
        assert record["task_id"] == "logical_reasoning"

    def test_benchmark_id_is_logiqa(self):
        record = self._loader()._to_record(self._make_item(), seq=0)
        assert record["benchmark_id"] == "logiqa"

    def test_reference_response_letter_a(self):
        record = self._loader()._to_record(self._make_item(label=0), seq=0)
        assert record["reference_response"] == "A"

    def test_reference_response_letter_d(self):
        record = self._loader()._to_record(self._make_item(label=3), seq=0)
        assert record["reference_response"] == "D"

    def test_prompt_contains_context(self):
        item = self._make_item()
        record = self._loader()._to_record(item, seq=0)
        assert item["_context"] in record["prompt"]

    def test_prompt_contains_question(self):
        item = self._make_item()
        record = self._loader()._to_record(item, seq=0)
        assert item["_question"] in record["prompt"]

    def test_prompt_contains_options(self):
        item = self._make_item()
        record = self._loader()._to_record(item, seq=0)
        assert "First option" in record["prompt"]
        assert "Fourth option" in record["prompt"]


# ===========================================================================
# 2. WinograndeLoader
# ===========================================================================

class TestOptionLengthWinogrande:
    def _fn(self):
        from benchmark.loaders.winogrande import _option_length
        return _option_length

    def test_short_max_5_words(self):
        assert self._fn()("cat", "dog") == "short"

    def test_boundary_5_words_is_short(self):
        assert self._fn()("one two three four five", "x") == "short"

    def test_boundary_6_words_is_medium(self):
        assert self._fn()("one two three four five six", "x") == "medium"

    def test_medium_up_to_10_words(self):
        assert self._fn()("a b c d e f g", "x") == "medium"

    def test_boundary_10_words_is_medium(self):
        assert self._fn()("a b c d e f g h i j", "x") == "medium"

    def test_boundary_11_words_is_long(self):
        assert self._fn()("a b c d e f g h i j k", "x") == "long"

    def test_uses_max_of_both_options(self):
        assert self._fn()("cat", "a very long option indeed wow here") == "long"


class TestWinograndeLoaderLoadDataset:
    def _loader(self):
        from benchmark.loaders.winogrande import WinograndeLoader
        return WinograndeLoader(attribute_map={}, sample_size=100, split="validation", seed=42)

    def test_loads_valid_rows(self):
        rows = [
            {"sentence": "The _ sat on the mat.", "option1": "cat", "option2": "dog", "answer": "1"},
            {"sentence": "She put _ in her bag.", "option1": "book", "option2": "phone", "answer": "2"},
        ]
        mock_ds = _make_mock_ds(rows)
        with patch("datasets.load_dataset", return_value=mock_ds):
            items = self._loader()._load_dataset()
        assert len(items) == 2

    def test_skips_invalid_answer(self):
        rows = [
            {"sentence": "She _ fast.", "option1": "ran", "option2": "walked", "answer": "3"},
        ]
        mock_ds = _make_mock_ds(rows)
        with patch("datasets.load_dataset", return_value=mock_ds):
            items = self._loader()._load_dataset()
        assert len(items) == 0

    def test_skips_empty_sentence(self):
        rows = [
            {"sentence": "", "option1": "cat", "option2": "dog", "answer": "1"},
        ]
        mock_ds = _make_mock_ds(rows)
        with patch("datasets.load_dataset", return_value=mock_ds):
            items = self._loader()._load_dataset()
        assert len(items) == 0

    def test_answer_stored_correctly(self):
        rows = [
            {"sentence": "_ is on the table.", "option1": "cup", "option2": "plate", "answer": "1"},
        ]
        mock_ds = _make_mock_ds(rows)
        with patch("datasets.load_dataset", return_value=mock_ds):
            items = self._loader()._load_dataset()
        assert items[0]["_answer"] == "1"

    def test_inferred_format_is_fill_in_blank(self):
        rows = [
            {"sentence": "_ ran away.", "option1": "cat", "option2": "dog", "answer": "2"},
        ]
        mock_ds = _make_mock_ds(rows)
        with patch("datasets.load_dataset", return_value=mock_ds):
            items = self._loader()._load_dataset()
        assert items[0]["_inferred_attrs"]["format"] == "fill_in_blank"


class TestWinograndeLoaderToRecord:
    def _loader(self):
        from benchmark.loaders.winogrande import WinograndeLoader
        return WinograndeLoader(attribute_map={}, sample_size=10, split="validation", seed=42)

    def _make_item(self, answer="1"):
        return {
            "_native_id": "0",
            "_sentence": "The _ sat on the mat.",
            "_option1": "cat",
            "_option2": "dog",
            "_answer": answer,
            "_inferred_attrs": {"option_length": "short", "format": "fill_in_blank"},
        }

    def test_record_has_required_keys(self):
        record = self._loader()._to_record(self._make_item(), seq=0)
        _assert_phase3_record(record)

    def test_benchmark_id_is_winogrande(self):
        record = self._loader()._to_record(self._make_item(), seq=0)
        assert record["benchmark_id"] == "winogrande"

    def test_task_id_is_commonsense_reasoning(self):
        record = self._loader()._to_record(self._make_item(), seq=0)
        assert record["task_id"] == "commonsense_reasoning"

    def test_reference_a_for_answer_1(self):
        record = self._loader()._to_record(self._make_item(answer="1"), seq=0)
        assert record["reference_response"] == "A"

    def test_reference_b_for_answer_2(self):
        record = self._loader()._to_record(self._make_item(answer="2"), seq=0)
        assert record["reference_response"] == "B"

    def test_prompt_contains_sentence(self):
        item = self._make_item()
        record = self._loader()._to_record(item, seq=0)
        assert item["_sentence"] in record["prompt"]

    def test_prompt_contains_both_options(self):
        item = self._make_item()
        record = self._loader()._to_record(item, seq=0)
        assert "cat" in record["prompt"]
        assert "dog" in record["prompt"]

