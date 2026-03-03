"""metric_judge.py -- Non-LLM metric judges for rubric dimensions.

Metric judges compute well-defined, deterministic metrics (BERTScore, BLEU-4,
exact-match, etc.) against reference responses.  They return continuous [0, 1]
scores rather than the ordinal High/Medium/Low used by LLM judges.

Metric factors are declared in the rubric as dicts with a ``"metric"`` key:

    rubric:
      accuracy: "All key facts are preserved"          # LLM-evaluated
      bertscore_f1:                                     # metric-evaluated
        metric: bertscore
        description: "BERTScore F1 semantic similarity"

Usage
-----
    from runner.metric_judge import (
        SUPPORTED_METRICS, METRIC_FACTOR_DEFS,
        compute_metric, score_metric_factors,
        split_rubric,
    )

    llm_factors, metric_factors = split_rubric(rubric)
    scores = score_metric_factors(metric_factors, hypothesis, reference)
    # scores = {"bertscore_f1": "0.8423"}
"""
from __future__ import annotations

import sys
from typing import Any

# ---------------------------------------------------------------------------
# Supported metrics and their default rubric factor definitions
# ---------------------------------------------------------------------------

SUPPORTED_METRICS: frozenset[str] = frozenset({
    "bertscore",
    "bleu",
    "exact_match",
})

METRIC_FACTOR_DEFS: dict[str, dict[str, str]] = {
    "bertscore": {
        "factor_name": "bertscore_f1",
        "metric": "bertscore",
        "description": (
            "BERTScore F1 semantic similarity between student response "
            "and reference response"
        ),
    },
    "bleu": {
        "factor_name": "bleu4",
        "metric": "bleu",
        "description": (
            "BLEU-4 token overlap score between student response "
            "and reference response"
        ),
    },
    "exact_match": {
        "factor_name": "exact_match",
        "metric": "exact_match",
        "description": (
            "Exact string match (case-insensitive) between student response "
            "and reference answer"
        ),
    },
}


# ---------------------------------------------------------------------------
# Lazy imports for heavy dependencies
# ---------------------------------------------------------------------------

def _require_bertscore():
    """Import bert_score or exit with clear message."""
    try:
        from bert_score import score as _bs_score
        return _bs_score
    except ImportError:
        print(
            "ERROR: bert-score is not installed.\n"
            "  pip install bert-score\n"
            "  (also requires torch)",
            file=sys.stderr,
        )
        raise ImportError("bert-score is required for the bertscore metric judge")


def _require_nltk_bleu():
    """Import NLTK BLEU or exit with clear message."""
    try:
        from nltk.translate.bleu_score import sentence_bleu, SmoothingFunction
        return sentence_bleu, SmoothingFunction
    except ImportError:
        print(
            "ERROR: nltk is not installed.\n"
            "  pip install nltk",
            file=sys.stderr,
        )
        raise ImportError("nltk is required for the bleu metric judge")


# ---------------------------------------------------------------------------
# Core metric computation
# ---------------------------------------------------------------------------

def _compute_bertscore(hypothesis: str, reference: str, **kwargs) -> float:
    """BERTScore F1 between hypothesis and reference.  Range [0, 1]."""
    if not hypothesis or not reference:
        return 0.0
    bs_score = _require_bertscore()
    model_type = kwargs.get("model_type", "distilbert-base-uncased")
    _, _, F1 = bs_score(
        [hypothesis], [reference],
        model_type=model_type,
        batch_size=1,
        verbose=False,
        lang="en",
    )
    return float(F1[0])


def _compute_bleu(hypothesis: str, reference: str, **kwargs) -> float:
    """Sentence BLEU-4 with smoothing.  Range [0, 1]."""
    sentence_bleu, SmoothingFunction = _require_nltk_bleu()
    hyp_tokens = hypothesis.lower().split()
    ref_tokens = reference.lower().split()
    if not hyp_tokens or not ref_tokens:
        return 0.0
    smoother = SmoothingFunction().method1
    return float(sentence_bleu(
        [ref_tokens], hyp_tokens, smoothing_function=smoother,
    ))


def _compute_exact_match(hypothesis: str, reference: str, **kwargs) -> float:
    """Case-insensitive exact match.  Returns 1.0 or 0.0."""
    hyp = hypothesis.strip().lower()
    ref = reference.strip().lower()
    # Support pipe-separated multiple valid answers in reference
    answers = [a.strip().lower() for a in ref.split("|")] if "|" in ref else [ref]
    return 1.0 if any(hyp == a for a in answers) else 0.0


_METRIC_FNS = {
    "bertscore": _compute_bertscore,
    "bleu": _compute_bleu,
    "exact_match": _compute_exact_match,
}


def compute_metric(metric: str, hypothesis: str, reference: str, **kwargs) -> float:
    """Dispatch to the appropriate metric function.

    Parameters
    ----------
    metric      : One of SUPPORTED_METRICS (``"bertscore"``, ``"bleu"``,
                  ``"exact_match"``).
    hypothesis  : The student's response text.
    reference   : The reference (gold) response text.
    **kwargs    : Forwarded to the metric function (e.g. ``model_type``
                  for BERTScore).

    Returns
    -------
    float in [0, 1].

    Raises
    ------
    ValueError  : If *metric* is not in SUPPORTED_METRICS.
    """
    fn = _METRIC_FNS.get(metric)
    if fn is None:
        raise ValueError(
            f"Unknown metric '{metric}'. "
            f"Supported: {sorted(SUPPORTED_METRICS)}"
        )
    return fn(hypothesis, reference, **kwargs)


# ---------------------------------------------------------------------------
# Rubric helpers
# ---------------------------------------------------------------------------

def is_metric_factor(factor_value: Any) -> bool:
    """Return True if the rubric value represents a metric-evaluated factor.

    Metric factors are dicts with a ``"metric"`` key:

        {"metric": "bertscore", "description": "..."}

    LLM factors are plain strings:

        "How accurate is the response"
    """
    return isinstance(factor_value, dict) and "metric" in factor_value


def split_rubric(
    rubric: dict[str, Any],
) -> tuple[dict[str, str], dict[str, dict]]:
    """Split a rubric into LLM-evaluated and metric-evaluated factors.

    Returns
    -------
    (llm_factors, metric_factors)
        llm_factors    : ``{factor_name: description}`` — for LLM judges
        metric_factors : ``{factor_name: {"metric": ..., "description": ...}}``
    """
    llm: dict[str, str] = {}
    metric: dict[str, dict] = {}
    for name, value in rubric.items():
        if is_metric_factor(value):
            metric[name] = value
        else:
            llm[name] = str(value)
    return llm, metric


def score_metric_factors(
    metric_factors: dict[str, dict],
    hypothesis: str,
    reference: str,
    **kwargs,
) -> dict[str, str]:
    """Compute all metric factors for one (hypothesis, reference) pair.

    Parameters
    ----------
    metric_factors : ``{factor_name: {"metric": "bertscore", ...}}``
    hypothesis     : Student response text.
    reference      : Reference response text.
    **kwargs       : Forwarded to metric functions.

    Returns
    -------
    ``{factor_name: score_string}`` — scores as rounded float strings
    (e.g. ``{"bertscore_f1": "0.8423"}``).
    """
    scores: dict[str, str] = {}
    for factor_name, factor_def in metric_factors.items():
        metric_name = factor_def["metric"]
        # Forward any extra parameters from the factor definition
        extra = {k: v for k, v in factor_def.items()
                 if k not in ("metric", "description")}
        merged_kwargs = {**kwargs, **extra}
        value = compute_metric(metric_name, hypothesis, reference, **merged_kwargs)
        scores[factor_name] = str(round(value, 4))
    return scores


def make_metric_factor(metric: str) -> dict[str, Any]:
    """Create a metric factor definition from a metric name.

    Uses the default definition from METRIC_FACTOR_DEFS.

    Returns
    -------
    ``(factor_name, factor_def)`` tuple suitable for inserting into a rubric.

    Raises
    ------
    ValueError : If *metric* is not in METRIC_FACTOR_DEFS.
    """
    defn = METRIC_FACTOR_DEFS.get(metric)
    if defn is None:
        raise ValueError(
            f"No default factor definition for metric '{metric}'. "
            f"Available: {sorted(METRIC_FACTOR_DEFS)}"
        )
    factor_name = defn["factor_name"]
    factor_def = {
        "metric": defn["metric"],
        "description": defn["description"],
    }
    return factor_name, factor_def
