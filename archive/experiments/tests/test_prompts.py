"""
Tests for prompt template resolution (coeval/prompts.py).

Covers: canonical template fallback, task-level override, model-level override,
variable substitution, and all six canonical template IDs.
No LLM calls, no filesystem access.
"""
import pytest

from experiments.prompts import get_prompt, TEMPLATES


# ---------------------------------------------------------------------------
# Resolution order
# ---------------------------------------------------------------------------

def test_uses_canonical_when_no_library():
    result = get_prompt('sample', {}, 'any-model', {
        'task_description': 'T',
        'output_description': 'O',
        'target_attributes': '{}',
        'nuanced_attributes': '{}',
    })
    assert 'T' in result
    assert 'O' in result


def test_uses_task_level_override():
    library = {'sample': 'TASK_OVERRIDE task={task_description}'}
    result = get_prompt('sample', library, 'any-model',
                        {'task_description': 'MyTask'})
    assert result == 'TASK_OVERRIDE task=MyTask'


def test_model_level_override_wins_over_task_level():
    library = {
        'sample': 'TASK_OVERRIDE',
        'sample.specific-model': 'MODEL_OVERRIDE model={task_description}',
    }
    result = get_prompt('sample', library, 'specific-model',
                        {'task_description': 'T'})
    assert result == 'MODEL_OVERRIDE model=T'


def test_model_level_override_only_applies_to_named_model():
    library = {
        'sample.other-model': 'OTHER_MODEL',
    }
    result = get_prompt('sample', library, 'my-model', {
        'task_description': 'T',
        'output_description': 'O',
        'target_attributes': '{}',
        'nuanced_attributes': '{}',
    })
    # Falls through to canonical
    assert 'T' in result
    assert 'OTHER_MODEL' not in result


def test_key_error_on_missing_variable():
    with pytest.raises(KeyError):
        get_prompt('sample', {}, 'mdl', {})   # missing required variables


# ---------------------------------------------------------------------------
# All six canonical template IDs exist and are non-empty strings
# ---------------------------------------------------------------------------

@pytest.mark.parametrize('prompt_id', [
    'map_target_attrs',
    'map_nuanced_attrs',
    'autorubric',
    'sample',
    'test',
    'evaluate_single',
    'evaluate_per_factor',
])
def test_canonical_template_exists_and_nonempty(prompt_id):
    assert prompt_id in TEMPLATES
    assert isinstance(TEMPLATES[prompt_id], str)
    assert len(TEMPLATES[prompt_id]) > 10


# ---------------------------------------------------------------------------
# Variable substitution in canonical templates
# ---------------------------------------------------------------------------

def test_map_target_attrs_substitution():
    result = get_prompt('map_target_attrs', {}, 'mdl',
                        {'task_description': 'classify sentiment'})
    assert 'classify sentiment' in result


def test_map_nuanced_attrs_substitution():
    result = get_prompt('map_nuanced_attrs', {}, 'mdl',
                        {'task_description': 'classify sentiment'})
    assert 'classify sentiment' in result


def test_autorubric_substitution():
    result = get_prompt('autorubric', {}, 'mdl', {
        'task_description': 'summarise',
        'output_description': '2 sentences',
    })
    assert 'summarise' in result
    assert '2 sentences' in result


def test_sample_substitution():
    result = get_prompt('sample', {}, 'mdl', {
        'task_description': 'rate reviews',
        'output_description': 'one word',
        'target_attributes': '{"sentiment": "positive"}',
        'nuanced_attributes': '{"style": "formal"}',
    })
    assert 'rate reviews' in result
    assert 'one word' in result


def test_test_prompt_substitution():
    result = get_prompt('test', {}, 'mdl', {
        'input': 'I love this product.',
        'task_description': 'classify sentiment',
        'output_description': 'one word',
    })
    assert 'I love this product.' in result
    assert 'classify sentiment' in result


def test_evaluate_single_substitution():
    result = get_prompt('evaluate_single', {}, 'mdl', {
        'task_description': 'rate',
        'output_description': 'one word',
        'input': 'Great product.',
        'target_attributes': '{}',
        'reference_response': 'Positive',
        'response': 'Positive',
        'rubric': '{"accuracy": "Is it correct?"}',
    })
    assert 'Great product.' in result
    assert 'Positive' in result


def test_evaluate_per_factor_substitution():
    result = get_prompt('evaluate_per_factor', {}, 'mdl', {
        'task_description': 'rate',
        'output_description': 'one word',
        'input': 'Bad product.',
        'target_attributes': '{}',
        'reference_response': 'Negative',
        'response': 'Negative',
        'rubric_factor_name': 'accuracy',
        'rubric_factor_description': 'Correct classification.',
    })
    assert 'accuracy' in result
    assert 'Negative' in result


# ---------------------------------------------------------------------------
# Template variable escaping (double braces in overrides)
# ---------------------------------------------------------------------------

def test_double_brace_escaping_in_override():
    """Overrides that use {{literal}} should produce { } after formatting."""
    library = {
        'sample': (
            'Generate: {task_description}\n'
            'Example: {{"prompt": "hello", "response": "hi"}}\n'
            'Now generate a new one.'
        )
    }
    result = get_prompt('sample', library, 'mdl',
                        {'task_description': 'greeting task'})
    assert '{"prompt": "hello", "response": "hi"}' in result
    assert 'greeting task' in result
