"""Label-based accuracy metrics for classification and information-extraction tasks.

When the teacher's ``sampled_target_attributes`` represent ground-truth labels
— e.g. ``{"sentiment": "positive"}`` for a sentiment classifier or
``{"entity_type": "PERSON"}`` for a named-entity recogniser — this module
computes label accuracy metrics **directly** from Phase 3 datapoints and Phase 4
student responses without requiring an LLM judge.

Supported task types
--------------------
Multiclass classification
    One target attribute acts as the class label.  The student's response is
    parsed for a matching label string.  Exact-match (case-insensitive) accuracy
    is reported plus per-class precision / recall / F1.

Multilabel classification
    Multiple target attributes each carry an independent categorical value.
    :meth:`LabelEvaluator.evaluate_multilabel` returns per-attribute metrics and
    macro-averaged Hamming accuracy.

Information extraction
    Target attribute values are the expected extracted spans or entity types.
    The same extraction + comparison pipeline applies; a custom ``match_fn`` can
    implement normalisation or fuzzy matching.

Extraction strategies
---------------------
The evaluator tries to extract a predicted label from the student's response in
this order:

1. **JSON with exact key** — parse the response as JSON and return the value at
   the attribute key (e.g. ``{"sentiment": "positive"}``).
2. **JSON with alias key** — if the exact key is absent, try common aliases such
   as ``"label"``, ``"prediction"``, ``"class"``, ``"category"``, etc.
3. **Short free-text** — if the entire response is a single-line string of at
   most 60 characters, return it directly.  Useful when the student is instructed
   to output only the label with no commentary.
4. Return ``None`` (extraction failed; response is counted as *skipped*).

Usage::

    from experiments.label_eval import LabelEvaluator

    # Multiclass
    ev = LabelEvaluator(label_attributes=["sentiment"])
    report = ev.evaluate(datapoints, responses)
    # report → {"sentiment": {"accuracy": 0.87, "n_total": 50, "n_matched": 44,
    #            "n_skipped": 3, "per_label": {"positive": {...}, ...}}}

    # Multilabel
    ev2 = LabelEvaluator(label_attributes=["topic", "urgency"])
    report2 = ev2.evaluate_multilabel(datapoints, responses)
    # report2 → {"hamming_accuracy": 0.75, "per_attribute": {...}}

    # Custom match (prefix match for hierarchical labels)
    ev3 = LabelEvaluator(
        label_attributes=["category"],
        match_fn=lambda pred, gt: pred.split("/")[0] == gt.split("/")[0],
    )
"""
from __future__ import annotations

import json
import re
from collections import defaultdict
from typing import Callable

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

#: Common JSON field aliases tried when the exact attribute key is absent.
_LABEL_ALIASES: tuple[str, ...] = (
    'label', 'prediction', 'class', 'category',
    'answer', 'output', 'result', 'type', 'value',
)

#: Maximum response length (chars) for the short free-text extraction strategy.
_SHORT_TEXT_MAX = 60


# ---------------------------------------------------------------------------
# JSON helper
# ---------------------------------------------------------------------------

def _try_parse_json(text: str):
    """Parse *text* as JSON, stripping markdown code fences.

    Returns the parsed Python object, or ``None`` on failure.
    """
    cleaned = re.sub(r'^```(?:json)?\s*', '', text.strip(), flags=re.MULTILINE)
    cleaned = re.sub(r'```\s*$', '', cleaned.strip(), flags=re.MULTILINE)
    cleaned = cleaned.strip()
    # Try the full string first
    for attempt in [cleaned]:
        # Find the outermost JSON object or array
        for start_ch, end_ch in (('{', '}'), ('[', ']')):
            idx = attempt.find(start_ch)
            ridx = attempt.rfind(end_ch)
            if 0 <= idx < ridx:
                try:
                    return json.loads(attempt[idx:ridx + 1])
                except json.JSONDecodeError:
                    pass
        try:
            return json.loads(attempt)
        except json.JSONDecodeError:
            pass
    return None


# ---------------------------------------------------------------------------
# Label extraction API (public)
# ---------------------------------------------------------------------------

def extract_label(response_text: str, attr_key: str) -> str | None:
    """Extract a predicted label from a student response.

    Parameters
    ----------
    response_text:
        The raw text returned by the student model.
    attr_key:
        The target attribute key whose predicted value is to be extracted
        (e.g. ``"sentiment"``, ``"entity_type"``).

    Returns
    -------
    str | None
        The extracted label as a stripped string, or ``None`` when extraction
        fails.

    Examples
    --------
    >>> extract_label('{"sentiment": "positive"}', "sentiment")
    'positive'
    >>> extract_label('positive', "sentiment")
    'positive'
    >>> extract_label('Based on my analysis, the text has a very nuanced...', "sentiment")
    # returns None (too long for free-text strategy)
    """
    text = response_text.strip() if response_text else ''
    if not text:
        return None

    # Strategy 1 & 2: JSON
    obj = _try_parse_json(text)
    if isinstance(obj, dict):
        # Exact attribute key
        if attr_key in obj:
            val = obj[attr_key]
            return str(val).strip() if val is not None else None
        # Common aliases
        for alias in _LABEL_ALIASES:
            if alias in obj:
                val = obj[alias]
                return str(val).strip() if val is not None else None

    # Strategy 3: short single-line free text
    if len(text) <= _SHORT_TEXT_MAX and '\n' not in text:
        return text

    return None


def extract_multilabel(
    response_text: str,
    attr_keys: list[str],
) -> dict[str, str | None]:
    """Extract predicted labels for multiple attributes from one response.

    Tries JSON first (all keys in one pass), then falls back to the short
    free-text strategy (same value replicated for every attribute).

    Parameters
    ----------
    response_text:
        Raw student response.
    attr_keys:
        List of attribute names to extract.

    Returns
    -------
    dict[str, str | None]
        Mapping ``attr_key → extracted_value``.  Values are ``None`` when
        extraction fails for that attribute.
    """
    text = (response_text or '').strip()
    result: dict[str, str | None] = {}

    obj = _try_parse_json(text)
    if isinstance(obj, dict):
        for key in attr_keys:
            if key in obj:
                val = obj[key]
                result[key] = str(val).strip() if val is not None else None
            else:
                result[key] = None
        return result

    # Short free-text fallback
    short = text if (len(text) <= _SHORT_TEXT_MAX and '\n' not in text) else None
    return {key: short for key in attr_keys}


# ---------------------------------------------------------------------------
# Internal metric helpers
# ---------------------------------------------------------------------------

def _prf1(tp: int, fp: int, fn: int) -> tuple[float, float, float]:
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall    = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1        = (2 * precision * recall / (precision + recall)
                 if (precision + recall) > 0 else 0.0)
    return precision, recall, f1


# ---------------------------------------------------------------------------
# LabelEvaluator
# ---------------------------------------------------------------------------

class LabelEvaluator:
    """Compute label accuracy metrics from Phase 3 datapoints + Phase 4 responses.

    Parameters
    ----------
    label_attributes:
        Names of target attributes that represent ground-truth labels.  Must be
        a non-empty list.  Each name must appear as a key in the
        ``sampled_target_attributes`` dict of the relevant datapoints.
    match_fn:
        Optional custom comparator ``(predicted, ground_truth) → bool``.
        Defaults to case-insensitive exact match after stripping whitespace.
        Use this to implement prefix matching, stemming, or fuzzy equality for
        information-extraction tasks.

    Raises
    ------
    ValueError
        If *label_attributes* is empty.
    """

    def __init__(
        self,
        label_attributes: list[str],
        match_fn: Callable[[str, str], bool] | None = None,
    ) -> None:
        if not label_attributes:
            raise ValueError('label_attributes must be a non-empty list')
        self.label_attributes = list(label_attributes)
        self._match: Callable[[str, str], bool] = match_fn or (
            lambda a, b: a.strip().lower() == b.strip().lower()
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def evaluate(
        self,
        datapoints: list[dict],
        responses: list[dict],
    ) -> dict[str, dict]:
        """Compute per-attribute label accuracy metrics.

        Parameters
        ----------
        datapoints:
            Phase 3 datapoint records.  Each must include the field
            ``sampled_target_attributes`` (a dict).
        responses:
            Phase 4 student response records.  Each must include
            ``datapoint_id`` and ``response`` fields.

        Returns
        -------
        dict[str, dict]
            Mapping ``attribute_name → metrics``.  Each metrics dict has:

            ``accuracy`` : float
                Fraction of correct predictions (``n_matched / n_total``).
                0.0 when *n_total* is 0.
            ``n_total`` : int
                Responses for which both ground-truth and predicted label could
                be determined.
            ``n_matched`` : int
                Count of correct predictions.
            ``n_skipped`` : int
                Responses skipped because the datapoint was missing, the
                attribute was absent from ground truth, or the label could not
                be extracted from the response.
            ``per_label`` : dict[str, dict]
                Per-class breakdown with ``precision``, ``recall``, ``f1``
                (4-decimal floats).
        """
        dp_index = {dp['id']: dp for dp in datapoints}
        return {
            attr: self._evaluate_attr(attr, dp_index, responses)
            for attr in self.label_attributes
        }

    def evaluate_multilabel(
        self,
        datapoints: list[dict],
        responses: list[dict],
    ) -> dict:
        """Compute Hamming accuracy for multi-label / multi-attribute tasks.

        Each attribute in :attr:`label_attributes` is treated as an independent
        classification sub-problem.  Hamming accuracy is the macro-average of
        per-attribute accuracies.

        Returns
        -------
        dict
            ``per_attribute`` : dict[str, dict]
                Same structure as :meth:`evaluate`.
            ``hamming_accuracy`` : float
                Macro-averaged accuracy across all attributes.
        """
        per_attr = self.evaluate(datapoints, responses)
        if not per_attr:
            return {'per_attribute': {}, 'hamming_accuracy': 0.0}
        hamming = sum(m['accuracy'] for m in per_attr.values()) / len(per_attr)
        return {
            'per_attribute': per_attr,
            'hamming_accuracy': round(hamming, 4),
        }

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _evaluate_attr(
        self,
        attr: str,
        dp_index: dict[str, dict],
        responses: list[dict],
    ) -> dict:
        n_total = n_matched = n_skipped = 0
        per_label: dict[str, dict[str, int]] = defaultdict(
            lambda: {'tp': 0, 'fp': 0, 'fn': 0}
        )

        for resp in responses:
            dp = dp_index.get(resp.get('datapoint_id', ''))
            if dp is None:
                n_skipped += 1
                continue

            gt_attrs = dp.get('sampled_target_attributes') or {}
            ground_truth = gt_attrs.get(attr)
            if ground_truth is None:
                n_skipped += 1
                continue
            ground_truth = str(ground_truth)

            predicted = extract_label(resp.get('response', ''), attr)
            if predicted is None:
                n_skipped += 1
                per_label[ground_truth]['fn'] += 1
                continue

            n_total += 1
            if self._match(predicted, ground_truth):
                n_matched += 1
                per_label[ground_truth]['tp'] += 1
            else:
                per_label[ground_truth]['fn'] += 1
                per_label[predicted]['fp'] += 1

        # Per-label precision / recall / F1
        per_label_metrics: dict[str, dict] = {}
        for label, counts in per_label.items():
            p, r, f1 = _prf1(counts['tp'], counts['fp'], counts['fn'])
            per_label_metrics[label] = {
                'precision': round(p, 4),
                'recall': round(r, 4),
                'f1': round(f1, 4),
            }

        return {
            'accuracy': round(n_matched / n_total, 4) if n_total > 0 else 0.0,
            'n_total': n_total,
            'n_matched': n_matched,
            'n_skipped': n_skipped,
            'per_label': per_label_metrics,
        }
