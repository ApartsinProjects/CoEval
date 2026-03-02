"""Tests for experiments/label_eval.py — label accuracy for classification/IE tasks.

Scenarios covered:
  - extract_label: JSON exact key, alias key, markdown fence, short free-text,
    long text (returns None), empty text
  - extract_multilabel: JSON, missing keys, short free-text fallback
  - LabelEvaluator.evaluate: perfect/partial/zero accuracy, case-insensitive
    default match, custom match_fn, extraction failure (skipped), per-label P/R/F1,
    missing datapoint (skipped), missing attribute in ground truth (skipped)
  - LabelEvaluator.evaluate_multilabel: Hamming accuracy
  - LabelEvaluator: empty label_attributes raises ValueError
  - Information-extraction scenario (entity_type attribute)
"""
from __future__ import annotations

import pytest

from experiments.label_eval import (
    LabelEvaluator,
    extract_label,
    extract_multilabel,
)


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

def _dp(dp_id: str, **target_attrs) -> dict:
    """Create a minimal Phase-3 datapoint with sampled_target_attributes."""
    return {
        'id': dp_id,
        'task_id': 'task1',
        'teacher_model_id': 'teacher1',
        'sampled_target_attributes': target_attrs,
        'prompt': 'Classify the following text.',
        'reference_response': 'positive',
        'generated_at': '2026-01-01T00:00:00Z',
    }


def _resp(resp_id: str, dp_id: str, response: str) -> dict:
    """Create a minimal Phase-4 student response."""
    return {
        'id': resp_id,
        'datapoint_id': dp_id,
        'task_id': 'task1',
        'teacher_model_id': 'teacher1',
        'student_model_id': 'student1',
        'input': 'Some input text.',
        'response': response,
        'generated_at': '2026-01-01T00:00:00Z',
    }


# ---------------------------------------------------------------------------
# extract_label — unit tests
# ---------------------------------------------------------------------------

class TestExtractLabel:
    def test_json_exact_key(self):
        assert extract_label('{"sentiment": "positive"}', 'sentiment') == 'positive'

    def test_json_alias_label(self):
        assert extract_label('{"label": "negative"}', 'sentiment') == 'negative'

    def test_json_alias_prediction(self):
        assert extract_label('{"prediction": "neutral"}', 'sentiment') == 'neutral'

    def test_json_alias_class(self):
        assert extract_label('{"class": "sports"}', 'topic') == 'sports'

    def test_json_alias_answer(self):
        assert extract_label('{"answer": "PERSON"}', 'entity_type') == 'PERSON'

    def test_json_markdown_fence_stripped(self):
        text = '```json\n{"entity_type": "LOCATION"}\n```'
        assert extract_label(text, 'entity_type') == 'LOCATION'

    def test_short_freetext(self):
        assert extract_label('positive', 'sentiment') == 'positive'

    def test_short_freetext_whitespace_stripped(self):
        assert extract_label('  negative  ', 'sentiment') == 'negative'

    def test_short_freetext_exactly_60_chars(self):
        text = 'x' * 60
        assert extract_label(text, 'attr') == text

    def test_long_freetext_returns_none(self):
        long = 'The sentiment of this text is positive, I think.' * 5
        assert extract_label(long, 'sentiment') is None

    def test_multiline_freetext_returns_none(self):
        assert extract_label('positive\nnegative', 'sentiment') is None

    def test_empty_string_returns_none(self):
        assert extract_label('', 'sentiment') is None

    def test_whitespace_only_returns_none(self):
        assert extract_label('   ', 'sentiment') is None

    def test_json_null_value_returns_none(self):
        assert extract_label('{"sentiment": null}', 'sentiment') is None

    def test_json_integer_value_coerced_to_str(self):
        result = extract_label('{"count": 3}', 'count')
        assert result == '3'

    def test_non_json_non_short_returns_none(self):
        # Not JSON but > 60 chars
        text = 'After careful analysis of the text, I conclude positive' * 2
        assert extract_label(text, 'sentiment') is None

    def test_json_preferred_over_short_text(self):
        # Short JSON: should parse JSON, not treat as short text
        text = '{"sentiment": "neg"}'  # 20 chars, but is JSON
        assert extract_label(text, 'sentiment') == 'neg'


# ---------------------------------------------------------------------------
# extract_multilabel — unit tests
# ---------------------------------------------------------------------------

class TestExtractMultilabel:
    def test_json_all_keys_present(self):
        resp = '{"sentiment": "positive", "topic": "technology"}'
        result = extract_multilabel(resp, ['sentiment', 'topic'])
        assert result == {'sentiment': 'positive', 'topic': 'technology'}

    def test_json_missing_key_returns_none(self):
        resp = '{"sentiment": "positive"}'
        result = extract_multilabel(resp, ['sentiment', 'topic'])
        assert result['sentiment'] == 'positive'
        assert result['topic'] is None

    def test_short_freetext_replicated_to_all_attrs(self):
        result = extract_multilabel('positive', ['sentiment', 'topic'])
        assert result == {'sentiment': 'positive', 'topic': 'positive'}

    def test_long_freetext_all_none(self):
        long = 'a very long explanation that exceeds sixty characters in length!!'
        result = extract_multilabel(long, ['sentiment', 'topic'])
        assert result == {'sentiment': None, 'topic': None}

    def test_empty_attr_keys(self):
        result = extract_multilabel('{"sentiment": "pos"}', [])
        assert result == {}

    def test_json_markdown_fence(self):
        resp = '```json\n{"a": "x", "b": "y"}\n```'
        result = extract_multilabel(resp, ['a', 'b'])
        assert result == {'a': 'x', 'b': 'y'}


# ---------------------------------------------------------------------------
# LabelEvaluator.evaluate — multiclass classification
# ---------------------------------------------------------------------------

class TestLabelEvaluatorMulticlass:
    def test_perfect_accuracy(self):
        dps = [
            _dp('dp1', sentiment='positive'),
            _dp('dp2', sentiment='negative'),
            _dp('dp3', sentiment='neutral'),
        ]
        resps = [
            _resp('r1', 'dp1', '{"sentiment": "positive"}'),
            _resp('r2', 'dp2', '{"sentiment": "negative"}'),
            _resp('r3', 'dp3', '{"sentiment": "neutral"}'),
        ]
        ev = LabelEvaluator(['sentiment'])
        report = ev.evaluate(dps, resps)
        assert report['sentiment']['accuracy'] == 1.0
        assert report['sentiment']['n_total'] == 3
        assert report['sentiment']['n_matched'] == 3
        assert report['sentiment']['n_skipped'] == 0

    def test_partial_accuracy(self):
        dps = [_dp('dp1', sentiment='positive'), _dp('dp2', sentiment='negative')]
        resps = [
            _resp('r1', 'dp1', 'positive'),   # ✓
            _resp('r2', 'dp2', 'positive'),   # ✗
        ]
        ev = LabelEvaluator(['sentiment'])
        report = ev.evaluate(dps, resps)
        assert report['sentiment']['n_matched'] == 1
        assert report['sentiment']['n_total'] == 2
        assert report['sentiment']['accuracy'] == pytest.approx(0.5)

    def test_zero_accuracy(self):
        dps = [_dp('dp1', sentiment='positive')]
        resps = [_resp('r1', 'dp1', 'negative')]
        ev = LabelEvaluator(['sentiment'])
        report = ev.evaluate(dps, resps)
        assert report['sentiment']['accuracy'] == 0.0
        assert report['sentiment']['n_matched'] == 0
        assert report['sentiment']['n_total'] == 1

    def test_default_match_case_insensitive(self):
        dps = [_dp('dp1', sentiment='Positive')]
        resps = [_resp('r1', 'dp1', 'positive')]
        ev = LabelEvaluator(['sentiment'])
        report = ev.evaluate(dps, resps)
        assert report['sentiment']['n_matched'] == 1

    def test_extraction_failure_counts_as_skipped_not_wrong(self):
        long_resp = 'I think the text expresses a very nuanced emotional stance.' * 3
        dps = [_dp('dp1', sentiment='positive')]
        resps = [_resp('r1', 'dp1', long_resp)]
        ev = LabelEvaluator(['sentiment'])
        report = ev.evaluate(dps, resps)
        assert report['sentiment']['n_skipped'] == 1
        assert report['sentiment']['n_total'] == 0

    def test_missing_datapoint_skipped(self):
        dps = [_dp('dp1', sentiment='positive')]
        resps = [
            _resp('r1', 'dp1', 'positive'),
            _resp('r2', 'NONEXISTENT', 'positive'),
        ]
        ev = LabelEvaluator(['sentiment'])
        report = ev.evaluate(dps, resps)
        assert report['sentiment']['n_skipped'] == 1
        assert report['sentiment']['n_total'] == 1

    def test_attribute_not_in_ground_truth_skipped(self):
        dps = [_dp('dp1', topic='sports')]   # no 'sentiment'
        resps = [_resp('r1', 'dp1', 'positive')]
        ev = LabelEvaluator(['sentiment'])
        report = ev.evaluate(dps, resps)
        assert report['sentiment']['n_skipped'] == 1

    def test_per_label_metrics_present(self):
        dps = [_dp('dp1', sentiment='positive'), _dp('dp2', sentiment='negative')]
        resps = [
            _resp('r1', 'dp1', 'positive'),   # TP for positive
            _resp('r2', 'dp2', 'positive'),   # FP for positive, FN for negative
        ]
        ev = LabelEvaluator(['sentiment'])
        report = ev.evaluate(dps, resps)
        pl = report['sentiment']['per_label']
        assert 'positive' in pl
        assert 'precision' in pl['positive']
        assert 'recall' in pl['positive']
        assert 'f1' in pl['positive']

    def test_per_label_f1_correct_for_perfect_single_class(self):
        dps = [_dp('dp1', sentiment='positive'), _dp('dp2', sentiment='positive')]
        resps = [
            _resp('r1', 'dp1', 'positive'),
            _resp('r2', 'dp2', 'positive'),
        ]
        ev = LabelEvaluator(['sentiment'])
        report = ev.evaluate(dps, resps)
        assert report['sentiment']['per_label']['positive']['f1'] == 1.0

    def test_empty_responses_zero_metrics(self):
        dps = [_dp('dp1', sentiment='positive')]
        ev = LabelEvaluator(['sentiment'])
        report = ev.evaluate(dps, [])
        assert report['sentiment']['accuracy'] == 0.0
        assert report['sentiment']['n_total'] == 0

    def test_empty_datapoints_all_skipped(self):
        resps = [_resp('r1', 'dp1', 'positive')]
        ev = LabelEvaluator(['sentiment'])
        report = ev.evaluate([], resps)
        assert report['sentiment']['n_skipped'] == 1

    def test_multiple_attributes_evaluated_independently(self):
        dps = [
            _dp('dp1', sentiment='positive', urgency='high'),
            _dp('dp2', sentiment='negative', urgency='low'),
        ]
        resps = [
            _resp('r1', 'dp1', '{"sentiment": "positive", "urgency": "high"}'),
            _resp('r2', 'dp2', '{"sentiment": "positive", "urgency": "low"}'),  # sentiment wrong
        ]
        ev = LabelEvaluator(['sentiment', 'urgency'])
        report = ev.evaluate(dps, resps)
        assert report['sentiment']['accuracy'] == pytest.approx(0.5)
        assert report['urgency']['accuracy'] == 1.0

    def test_custom_match_fn(self):
        """Custom fn: prefix match for hierarchical labels."""
        dps = [_dp('dp1', category='science/physics')]
        resps = [_resp('r1', 'dp1', 'science/astronomy')]
        ev = LabelEvaluator(
            ['category'],
            match_fn=lambda pred, gt: pred.split('/')[0] == gt.split('/')[0],
        )
        report = ev.evaluate(dps, resps)
        assert report['category']['n_matched'] == 1

    def test_empty_label_attributes_raises(self):
        with pytest.raises(ValueError):
            LabelEvaluator([])


# ---------------------------------------------------------------------------
# LabelEvaluator — information extraction
# ---------------------------------------------------------------------------

class TestLabelEvaluatorIE:
    def test_entity_type_extraction(self):
        """Named-entity recognition: entity_type as ground truth label."""
        dps = [
            _dp('dp1', entity_type='PERSON'),
            _dp('dp2', entity_type='LOCATION'),
            _dp('dp3', entity_type='ORGANIZATION'),
        ]
        resps = [
            _resp('r1', 'dp1', '{"entity_type": "PERSON"}'),       # ✓
            _resp('r2', 'dp2', '{"entity_type": "LOCATION"}'),     # ✓
            _resp('r3', 'dp3', '{"entity_type": "PERSON"}'),       # ✗
        ]
        ev = LabelEvaluator(['entity_type'])
        report = ev.evaluate(dps, resps)
        assert report['entity_type']['n_matched'] == 2
        assert report['entity_type']['accuracy'] == pytest.approx(2 / 3, abs=0.01)

    def test_ie_short_label_response(self):
        """Student responds with just the entity type (no JSON)."""
        dps = [_dp('dp1', entity_type='PERSON')]
        resps = [_resp('r1', 'dp1', 'PERSON')]
        ev = LabelEvaluator(['entity_type'])
        report = ev.evaluate(dps, resps)
        assert report['entity_type']['n_matched'] == 1

    def test_ie_case_insensitive(self):
        dps = [_dp('dp1', entity_type='PERSON')]
        resps = [_resp('r1', 'dp1', 'person')]
        ev = LabelEvaluator(['entity_type'])
        report = ev.evaluate(dps, resps)
        assert report['entity_type']['n_matched'] == 1


# ---------------------------------------------------------------------------
# LabelEvaluator.evaluate_multilabel
# ---------------------------------------------------------------------------

class TestLabelEvaluatorMultilabel:
    def test_perfect_hamming_accuracy(self):
        dps = [
            _dp('dp1', topic='sports', urgency='high'),
            _dp('dp2', topic='politics', urgency='low'),
        ]
        resps = [
            _resp('r1', 'dp1', '{"topic": "sports", "urgency": "high"}'),
            _resp('r2', 'dp2', '{"topic": "politics", "urgency": "low"}'),
        ]
        ev = LabelEvaluator(['topic', 'urgency'])
        report = ev.evaluate_multilabel(dps, resps)
        assert report['hamming_accuracy'] == 1.0
        assert report['per_attribute']['topic']['accuracy'] == 1.0
        assert report['per_attribute']['urgency']['accuracy'] == 1.0

    def test_partial_hamming_accuracy(self):
        """One attribute perfect, one zero → Hamming = 0.5."""
        dps = [_dp('dp1', topic='sports', urgency='high')]
        resps = [_resp('r1', 'dp1', '{"topic": "sports", "urgency": "low"}')]
        ev = LabelEvaluator(['topic', 'urgency'])
        report = ev.evaluate_multilabel(dps, resps)
        assert report['per_attribute']['topic']['accuracy'] == 1.0
        assert report['per_attribute']['urgency']['accuracy'] == 0.0
        assert report['hamming_accuracy'] == pytest.approx(0.5)

    def test_empty_responses_zero_hamming(self):
        dps = [_dp('dp1', topic='sports', urgency='high')]
        ev = LabelEvaluator(['topic', 'urgency'])
        report = ev.evaluate_multilabel(dps, [])
        assert report['hamming_accuracy'] == 0.0
