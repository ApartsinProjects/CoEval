"""
Tests for coeval/phases/utils.py:
  - _extract_json: multi-strategy JSON extraction from noisy model output
  - extract_prompt_response: tolerant key-name normalisation
  - merge_attr_maps / merge_rubrics: attribute/rubric merging
  - QuotaTracker: per-model call budgets

No LLM calls, no filesystem access.
"""
import json
import pytest

from coeval.phases.utils import (
    _extract_json,
    extract_prompt_response,
    merge_attr_maps,
    merge_rubrics,
    QuotaTracker,
)


# ---------------------------------------------------------------------------
# _extract_json — Strategy 1: direct parse
# ---------------------------------------------------------------------------

def test_extract_json_clean_object():
    assert _extract_json('{"a": 1}') == {"a": 1}


def test_extract_json_clean_list():
    # single-dict list is unwrapped
    assert _extract_json('[{"a": 1}]') == {"a": 1}


def test_extract_json_multi_item_list():
    # multi-item list is NOT unwrapped
    result = _extract_json('[1, 2, 3]')
    assert result == [1, 2, 3]


# ---------------------------------------------------------------------------
# _extract_json — Strategy 2: strip leading prose
# ---------------------------------------------------------------------------

def test_extract_json_with_leading_prose():
    text = 'Here is the JSON you asked for:\n{"key": "value"}'
    assert _extract_json(text) == {"key": "value"}


def test_extract_json_with_markdown_fences():
    # Markdown fences are stripped by the caller in call_llm_json, but test
    # that extract_json handles leftover text gracefully
    text = 'Result: {"x": 42} and that is all.'
    assert _extract_json(text) == {"x": 42}


# ---------------------------------------------------------------------------
# _extract_json — Strategy 3: outermost balanced brackets
# ---------------------------------------------------------------------------

def test_extract_json_with_surrounding_text():
    text = 'prefix {"nested": {"a": 1}} suffix garbage'
    result = _extract_json(text)
    assert result == {"nested": {"a": 1}}


def test_extract_json_raises_on_no_json():
    with pytest.raises(json.JSONDecodeError):
        _extract_json('this is plain text with no JSON at all')


def test_extract_json_raises_on_empty():
    with pytest.raises(json.JSONDecodeError):
        _extract_json('')


# ---------------------------------------------------------------------------
# extract_prompt_response — canonical keys
# ---------------------------------------------------------------------------

def test_extract_canonical_keys():
    data = {"prompt": "Hello?", "response": "Hi!"}
    p, r = extract_prompt_response(data)
    assert p == "Hello?"
    assert r == "Hi!"


# ---------------------------------------------------------------------------
# extract_prompt_response — alternative key names
# ---------------------------------------------------------------------------

@pytest.mark.parametrize('prompt_key', [
    'prompt', 'input', 'question', 'task', 'context', 'user_input', 'text', 'scenario'
])
def test_extract_various_prompt_keys(prompt_key):
    data = {prompt_key: 'the prompt', 'response': 'the answer'}
    p, r = extract_prompt_response(data)
    assert p == 'the prompt'


@pytest.mark.parametrize('response_key', [
    'response', 'output', 'answer', 'completion', 'result', 'reference', 'label'
])
def test_extract_various_response_keys(response_key):
    data = {'prompt': 'the prompt', response_key: 'the answer'}
    p, r = extract_prompt_response(data)
    assert r == 'the answer'


# ---------------------------------------------------------------------------
# extract_prompt_response — list wrapping
# ---------------------------------------------------------------------------

def test_extract_from_single_element_list():
    data = [{"prompt": "p", "response": "r"}]
    p, r = extract_prompt_response(data)
    assert p == "p" and r == "r"


def test_extract_raises_on_list_without_dict():
    with pytest.raises(KeyError):
        extract_prompt_response([1, 2, 3])


def test_extract_raises_on_missing_prompt_key():
    with pytest.raises(KeyError, match='No prompt-like key'):
        extract_prompt_response({'response': 'r'})


def test_extract_raises_on_missing_response_key():
    with pytest.raises(KeyError, match='No response-like key'):
        extract_prompt_response({'prompt': 'p'})


def test_extract_raises_on_non_dict():
    with pytest.raises(KeyError):
        extract_prompt_response("just a string")


# ---------------------------------------------------------------------------
# merge_attr_maps
# ---------------------------------------------------------------------------

def test_merge_attr_maps_disjoint():
    a = {'tone': ['formal', 'casual']}
    b = {'urgency': ['high', 'low']}
    merged = merge_attr_maps(a, b)
    assert set(merged.keys()) == {'tone', 'urgency'}


def test_merge_attr_maps_overlapping_deduplicates():
    a = {'tone': ['formal', 'casual']}
    b = {'tone': ['casual', 'neutral']}   # 'casual' is a duplicate
    merged = merge_attr_maps(a, b)
    assert merged['tone'].count('casual') == 1
    assert set(merged['tone']) == {'formal', 'casual', 'neutral'}


def test_merge_attr_maps_preserves_order_first_wins():
    a = {'x': [1, 2, 3]}
    b = {'x': [3, 4, 5]}
    merged = merge_attr_maps(a, b)
    assert merged['x'] == [1, 2, 3, 4, 5]


def test_merge_attr_maps_skips_non_dict():
    merged = merge_attr_maps({'a': [1]}, None, 'bad', {'b': [2]})
    assert set(merged.keys()) == {'a', 'b'}


def test_merge_attr_maps_empty_inputs():
    assert merge_attr_maps() == {}
    assert merge_attr_maps({}) == {}


# ---------------------------------------------------------------------------
# merge_rubrics
# ---------------------------------------------------------------------------

def test_merge_rubrics_disjoint():
    a = {'accuracy': 'Correct?'}
    b = {'brevity': 'Short?'}
    merged = merge_rubrics(a, b)
    assert 'accuracy' in merged and 'brevity' in merged


def test_merge_rubrics_first_occurrence_wins():
    a = {'accuracy': 'First description'}
    b = {'accuracy': 'Second description'}
    merged = merge_rubrics(a, b)
    assert merged['accuracy'] == 'First description'


def test_merge_rubrics_skips_non_dict():
    merged = merge_rubrics({'a': 'desc'}, None, 42, {'b': 'desc2'})
    assert set(merged.keys()) == {'a', 'b'}


# ---------------------------------------------------------------------------
# QuotaTracker
# ---------------------------------------------------------------------------

def test_quota_tracker_not_exhausted_initially():
    qt = QuotaTracker({'mdl': {'max_calls': 3}})
    assert not qt.is_exhausted('mdl')


def test_quota_tracker_exhausts_after_consuming():
    qt = QuotaTracker({'mdl': {'max_calls': 2}})
    qt.consume('mdl')
    assert not qt.is_exhausted('mdl')
    qt.consume('mdl')
    assert qt.is_exhausted('mdl')


def test_quota_tracker_unlisted_model_never_exhausted():
    qt = QuotaTracker({})
    assert not qt.is_exhausted('any-model')
    qt.consume('any-model')   # should not raise
    assert not qt.is_exhausted('any-model')


def test_quota_tracker_consume_does_not_go_below_zero():
    qt = QuotaTracker({'mdl': {'max_calls': 1}})
    qt.consume('mdl')
    qt.consume('mdl')   # over-consuming; should not raise
    assert qt.is_exhausted('mdl')


def test_quota_tracker_multiple_models_independent():
    qt = QuotaTracker({'a': {'max_calls': 1}, 'b': {'max_calls': 5}})
    qt.consume('a')
    assert qt.is_exhausted('a')
    assert not qt.is_exhausted('b')


def test_quota_tracker_zero_max_calls_exhausted_immediately():
    qt = QuotaTracker({'mdl': {'max_calls': 0}})
    assert qt.is_exhausted('mdl')
