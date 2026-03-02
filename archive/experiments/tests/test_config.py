"""
Tests for config loading and validation rules V-01 through V-11.

All tests use in-memory dicts / tmp_path; no LLM calls, no network.
Each test focuses on exactly one validation rule so failures are obvious.
"""
import os
import pytest

from experiments.config import (
    load_config,
    validate_config,
    _parse_config,
    CoEvalConfig,
    ModelConfig,
    TaskConfig,
    SamplingConfig,
    ExperimentConfig,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _minimal_raw(*, model_roles=None, extra_models=None, extra_tasks=None,
                  exp_overrides=None, task_overrides=None):
    """Return a minimal valid raw config dict."""
    roles = model_roles or ['teacher', 'student', 'judge']
    raw = {
        'models': [
            {
                'name': 'mdl',
                'interface': 'openai',
                'parameters': {'model': 'gpt-4o'},
                'roles': roles,
            }
        ],
        'tasks': [
            {
                'name': 'task1',
                'description': 'Test task.',
                'output_description': 'One word.',
                'target_attributes': {'a': ['x', 'y']},
                'nuanced_attributes': {'b': ['p', 'q']},
                'sampling': {'target': [1, 1], 'nuance': [1, 1], 'total': 2},
                'rubric': {'quality': 'Good output.'},
                **(task_overrides or {}),
            }
        ],
        'experiment': {
            'id': 'exp-test',
            'storage_folder': '/tmp/coeval_tests',
            **(exp_overrides or {}),
        },
    }
    if extra_models:
        raw['models'].extend(extra_models)
    if extra_tasks:
        raw['tasks'].extend(extra_tasks)
    return raw


def _cfg(raw=None, **kw):
    """Parse raw dict into CoEvalConfig."""
    return _parse_config(raw or _minimal_raw(**kw))


# ---------------------------------------------------------------------------
# V-01: models and tasks must be present and non-empty
# ---------------------------------------------------------------------------

def test_v01_missing_models():
    raw = _minimal_raw()
    raw['models'] = []
    errors = validate_config(_cfg(raw))
    assert any('models' in e for e in errors)


def test_v01_missing_tasks():
    raw = _minimal_raw()
    raw['tasks'] = []
    errors = validate_config(_cfg(raw))
    assert any('tasks' in e for e in errors)


def test_v01_valid_passes():
    errors = validate_config(_cfg())
    # Expect no V-01 errors (may still have V-11 if folder exists, but that's fine here)
    model_task_errors = [e for e in errors if 'models' in e or 'tasks' in e]
    assert model_task_errors == []


# ---------------------------------------------------------------------------
# V-02: model names must be unique
# ---------------------------------------------------------------------------

def test_v02_duplicate_model_name():
    raw = _minimal_raw()
    raw['models'].append(dict(raw['models'][0]))  # exact copy
    errors = validate_config(_cfg(raw))
    assert any('Duplicate model' in e for e in errors)


def test_v02_unique_model_names_ok():
    extra = {'name': 'mdl2', 'interface': 'openai',
              'parameters': {'model': 'gpt-4o'}, 'roles': ['student']}
    raw = _minimal_raw(extra_models=[extra])
    errors = validate_config(_cfg(raw))
    assert not any('Duplicate model' in e for e in errors)


# ---------------------------------------------------------------------------
# V-03: task names must be unique
# ---------------------------------------------------------------------------

def test_v03_duplicate_task_name():
    raw = _minimal_raw()
    raw['tasks'].append(dict(raw['tasks'][0]))
    errors = validate_config(_cfg(raw))
    assert any('Duplicate task' in e for e in errors)


# ---------------------------------------------------------------------------
# V-04: name character sets and reserved separator
# ---------------------------------------------------------------------------

@pytest.mark.parametrize('bad_name', ['my model', 'my/model', 'my:model'])
def test_v04_invalid_model_name_chars(bad_name):
    raw = _minimal_raw()
    raw['models'][0]['name'] = bad_name
    errors = validate_config(_cfg(raw))
    assert any('Invalid model name' in e for e in errors)


def test_v04_model_name_reserved_separator():
    raw = _minimal_raw()
    raw['models'][0]['name'] = 'my__model'
    errors = validate_config(_cfg(raw))
    assert any('reserved separator' in e for e in errors)


def test_v04_task_name_reserved_separator():
    raw = _minimal_raw()
    raw['tasks'][0]['name'] = 'task__one'
    errors = validate_config(_cfg(raw))
    assert any('reserved separator' in e for e in errors)


def test_v04_invalid_experiment_id():
    raw = _minimal_raw(exp_overrides={'id': 'bad id!'})
    errors = validate_config(_cfg(raw))
    assert any('Invalid experiment id' in e for e in errors)


def test_v04_valid_names_ok():
    # Dots, dashes, underscores allowed in model and experiment IDs
    raw = _minimal_raw()
    raw['models'][0]['name'] = 'gpt-4o.turbo-v1'
    raw['experiment']['id'] = 'run.2025-01-01'
    errors = validate_config(_cfg(raw))
    assert not any('Invalid model name' in e or 'Invalid experiment id' in e for e in errors)


# ---------------------------------------------------------------------------
# V-05: roles valid and non-empty
# ---------------------------------------------------------------------------

def test_v05_no_roles():
    raw = _minimal_raw()
    raw['models'][0]['roles'] = []
    errors = validate_config(_cfg(raw))
    assert any('no roles' in e for e in errors)


def test_v05_invalid_role():
    raw = _minimal_raw()
    raw['models'][0]['roles'] = ['superuser']
    errors = validate_config(_cfg(raw))
    assert any('Unknown role' in e for e in errors)


# ---------------------------------------------------------------------------
# V-06: interface must be openai, anthropic, gemini, or huggingface
# ---------------------------------------------------------------------------

def test_v06_invalid_interface():
    raw = _minimal_raw()
    raw['models'][0]['interface'] = 'foobar'
    errors = validate_config(_cfg(raw))
    assert any('Unknown interface' in e for e in errors)


def test_v06_huggingface_ok():
    raw = _minimal_raw()
    raw['models'][0]['interface'] = 'huggingface'
    errors = validate_config(_cfg(raw))
    assert not any('Unknown interface' in e for e in errors)


# ---------------------------------------------------------------------------
# V-07: required roles present
# ---------------------------------------------------------------------------

def test_v07_no_student():
    raw = _minimal_raw(model_roles=['teacher', 'judge'])
    errors = validate_config(_cfg(raw))
    assert any('student' in e for e in errors)


def test_v07_no_judge():
    raw = _minimal_raw(model_roles=['teacher', 'student'])
    errors = validate_config(_cfg(raw))
    assert any('judge' in e for e in errors)


def test_v07_auto_attrs_needs_teacher():
    raw = _minimal_raw(model_roles=['student', 'judge'])
    raw['tasks'][0]['target_attributes'] = 'auto'
    errors = validate_config(_cfg(raw))
    assert any('teacher' in e for e in errors)


def test_v07_static_attrs_no_teacher_needed():
    # Static map + static rubric: teacher not required
    raw = _minimal_raw(model_roles=['student', 'judge'])
    errors = validate_config(_cfg(raw))
    # no "teacher" error expected
    assert not any("required for phases 1-3" in e for e in errors)


# ---------------------------------------------------------------------------
# V-08: Model mode not allowed for phases 1 and 2
# ---------------------------------------------------------------------------

def test_v08_model_mode_phase1_rejected():
    raw = _minimal_raw(exp_overrides={'phases': {'attribute_mapping': 'Model'}})
    errors = validate_config(_cfg(raw))
    assert any("does not support mode 'Model'" in e for e in errors)


def test_v08_model_mode_phase2_rejected():
    raw = _minimal_raw(exp_overrides={'phases': {'rubric_mapping': 'Model'}})
    errors = validate_config(_cfg(raw))
    assert any("does not support mode 'Model'" in e for e in errors)


def test_v08_model_mode_phase3_ok():
    raw = _minimal_raw(exp_overrides={'phases': {'data_generation': 'Model'}})
    errors = validate_config(_cfg(raw))
    assert not any("does not support mode 'Model'" in e for e in errors)


# ---------------------------------------------------------------------------
# V-09: rubric: extend requires resume_from
# ---------------------------------------------------------------------------

def test_v09_rubric_extend_no_resume_from():
    raw = _minimal_raw(task_overrides={'rubric': 'extend'})
    errors = validate_config(_cfg(raw))
    assert any('extend requires resume_from' in e for e in errors)


def test_v09_rubric_extend_with_resume_from_valid(tmp_path):
    # Create a fake source folder so V-10 doesn't also fire
    source_dir = tmp_path / 'prior-run'
    source_dir.mkdir()
    raw = _minimal_raw(
        task_overrides={'rubric': 'extend'},
        exp_overrides={
            'storage_folder': str(tmp_path),
            'resume_from': 'prior-run',
            'id': 'new-run',
        },
    )
    errors = validate_config(_cfg(raw))
    v09_errors = [e for e in errors if 'extend requires resume_from' in e]
    assert v09_errors == []


# ---------------------------------------------------------------------------
# V-10: resume_from source folder must exist
# ---------------------------------------------------------------------------

def test_v10_resume_from_folder_missing(tmp_path):
    raw = _minimal_raw(
        exp_overrides={
            'storage_folder': str(tmp_path),
            'resume_from': 'does-not-exist',
            'id': 'new-run',
        }
    )
    errors = validate_config(_cfg(raw))
    assert any("not found" in e for e in errors)


def test_v10_resume_from_folder_present(tmp_path):
    source = tmp_path / 'source-run'
    source.mkdir()
    raw = _minimal_raw(
        exp_overrides={
            'storage_folder': str(tmp_path),
            'resume_from': 'source-run',
            'id': 'new-run',
        }
    )
    errors = validate_config(_cfg(raw))
    assert not any("not found" in e for e in errors)


# ---------------------------------------------------------------------------
# V-11: target folder must NOT already exist for new experiments
# ---------------------------------------------------------------------------

def test_v11_target_folder_already_exists(tmp_path):
    (tmp_path / 'exp-test').mkdir()
    raw = _minimal_raw(
        exp_overrides={'storage_folder': str(tmp_path), 'id': 'exp-test'}
    )
    errors = validate_config(_cfg(raw))
    assert any('already exists' in e for e in errors)


def test_v11_target_folder_absent_ok(tmp_path):
    raw = _minimal_raw(
        exp_overrides={'storage_folder': str(tmp_path), 'id': 'brand-new'}
    )
    errors = validate_config(_cfg(raw))
    assert not any('already exists' in e for e in errors)


# ---------------------------------------------------------------------------
# V-11 / V-12: continue_in_place interaction
# ---------------------------------------------------------------------------

def test_v11_skipped_when_continue_in_place(tmp_path):
    """V-11 must not fire when continue_in_place=True."""
    exp_dir = tmp_path / 'exp-test'
    exp_dir.mkdir()
    (exp_dir / 'meta.json').write_text('{}')
    raw = _minimal_raw(exp_overrides={'storage_folder': str(tmp_path), 'id': 'exp-test'})
    cfg = _parse_config(raw)
    # V-11 fires normally
    assert any('already exists' in e for e in validate_config(cfg))
    # V-11 suppressed with continue_in_place
    errors = validate_config(cfg, continue_in_place=True)
    assert not any('already exists' in e for e in errors)


def test_v12_continue_requires_existing_meta(tmp_path):
    """V-12: continue_in_place on a non-existent folder is an error."""
    raw = _minimal_raw(exp_overrides={'storage_folder': str(tmp_path), 'id': 'exp-test'})
    cfg = _parse_config(raw)
    errors = validate_config(cfg, continue_in_place=True)
    assert any('no existing experiment found' in e for e in errors)


def test_v12_passes_when_meta_exists(tmp_path):
    """V-12: no error when meta.json is present."""
    exp_dir = tmp_path / 'exp-test'
    exp_dir.mkdir()
    (exp_dir / 'meta.json').write_text('{}')
    raw = _minimal_raw(exp_overrides={'storage_folder': str(tmp_path), 'id': 'exp-test'})
    cfg = _parse_config(raw)
    errors = validate_config(cfg, continue_in_place=True)
    assert not any('no existing experiment found' in e for e in errors)


# ---------------------------------------------------------------------------
# get_phase_mode default logic
# ---------------------------------------------------------------------------

def test_get_phase_mode_default_new():
    cfg = _cfg()
    assert cfg.get_phase_mode('data_generation') == 'New'


def test_get_phase_mode_default_keep_when_resume_from():
    raw = _minimal_raw(exp_overrides={'resume_from': 'some-prior-run'})
    # Skip V-10 by not actually checking the folder here (just parse)
    cfg = _parse_config(raw)
    assert cfg.get_phase_mode('data_generation') == 'Keep'


def test_get_phase_mode_explicit_override():
    raw = _minimal_raw(exp_overrides={'phases': {'evaluation': 'Extend'}})
    cfg = _parse_config(raw)
    assert cfg.get_phase_mode('evaluation') == 'Extend'


# ---------------------------------------------------------------------------
# role_parameters merge
# ---------------------------------------------------------------------------

def test_role_parameters_merge():
    raw = _minimal_raw()
    raw['models'][0]['parameters'] = {'model': 'gpt-4o', 'temperature': 0.7}
    raw['models'][0]['role_parameters'] = {
        'teacher': {'temperature': 0.9, 'max_tokens': 256}
    }
    cfg = _parse_config(raw)
    params = cfg.models[0].get_parameters_for_role('teacher')
    assert params['temperature'] == 0.9    # overridden
    assert params['model'] == 'gpt-4o'     # inherited
    assert params['max_tokens'] == 256     # added


def test_role_parameters_no_override():
    cfg = _cfg()
    params = cfg.models[0].get_parameters_for_role('student')
    # student has no role_parameters entry → base params unchanged
    assert params == cfg.models[0].parameters
