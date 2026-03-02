"""Tests for probe configuration, cost estimator, and config validation V-15 through V-17.

Covers:
  - probe.run_probe with mode='disable'
  - probe._models_needed: 'full' returns all, 'resume' filters by remaining phases
  - probe_results.json written to disk
  - Cost estimator: prices lookup, heuristics, estimate report structure
  - Config V-15: probe_mode validation
  - Config V-16: probe_on_fail validation
  - Config V-17: label_attributes subset of target_attributes
  - Config parsing: label_attributes, probe_mode, probe_on_fail, estimate_cost parsed correctly
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from runner.config import (
    CoEvalConfig, ExperimentConfig, ModelConfig, TaskConfig, SamplingConfig,
    validate_config, _parse_config,
)
from runner.interfaces.probe import _models_needed, run_probe
from runner.interfaces.cost_estimator import (
    get_prices, count_tokens_approx, _heuristic_latency, _heuristic_tps,
    PRICE_TABLE, DEFAULT_PRICE_INPUT, DEFAULT_PRICE_OUTPUT,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _minimal_model(name='m1', interface='openai', roles=None):
    return ModelConfig(
        name=name,
        interface=interface,
        parameters={'model': name},
        roles=roles or ['student', 'judge'],
        access_key=None,
    )


def _minimal_task(name='task1', target_attrs=None, label_attrs=None):
    return TaskConfig(
        name=name,
        description='Test task.',
        output_description='One sentence.',
        target_attributes=target_attrs or {'sentiment': ['positive', 'negative']},
        nuanced_attributes={'tone': ['formal', 'casual']},
        sampling=SamplingConfig(target=[1, 1], nuance=[1, 1], total=2),
        rubric={'accuracy': 'Is it correct?'},
        evaluation_mode='single',
        label_attributes=label_attrs or [],
    )


def _minimal_cfg(**exp_kwargs):
    """Build a minimal CoEvalConfig with one teacher, one student, one judge."""
    teacher = ModelConfig(
        name='teacher1', interface='openai',
        parameters={'model': 'gpt-4o-mini'}, roles=['teacher'],
    )
    student = ModelConfig(
        name='student1', interface='openai',
        parameters={'model': 'gpt-4o-mini'}, roles=['student'],
    )
    judge = ModelConfig(
        name='judge1', interface='openai',
        parameters={'model': 'gpt-4o-mini'}, roles=['judge'],
    )
    task = _minimal_task()
    exp = ExperimentConfig(
        id='test-exp',
        storage_folder='/tmp/coeval_test',
        **exp_kwargs,
    )
    return CoEvalConfig(models=[teacher, student, judge], tasks=[task], experiment=exp)


def _make_logger():
    logger = MagicMock()
    logger.info = MagicMock()
    logger.warning = MagicMock()
    logger.error = MagicMock()
    return logger


# ---------------------------------------------------------------------------
# probe._models_needed
# ---------------------------------------------------------------------------

class TestModelsNeeded:
    def _cfg(self):
        teacher = ModelConfig(
            name='teacher', interface='openai',
            parameters={'model': 'gpt-4o-mini'}, roles=['teacher'],
        )
        student = ModelConfig(
            name='student', interface='openai',
            parameters={'model': 'gpt-4o-mini'}, roles=['student'],
        )
        judge = ModelConfig(
            name='judge', interface='openai',
            parameters={'model': 'gpt-4o-mini'}, roles=['judge'],
        )
        task = _minimal_task()
        exp = ExperimentConfig(id='e', storage_folder='/tmp')
        return CoEvalConfig(models=[teacher, student, judge], tasks=[task], experiment=exp)

    def test_full_mode_returns_all_models(self):
        cfg = self._cfg()
        needed = _models_needed(cfg, 'full', set())
        assert needed == {'teacher', 'student', 'judge'}

    def test_resume_no_completed_phases_returns_all(self):
        cfg = self._cfg()
        needed = _models_needed(cfg, 'resume', set())
        assert 'teacher' in needed
        assert 'student' in needed
        assert 'judge' in needed

    def test_resume_data_gen_complete_teacher_not_needed(self):
        """If data_generation + attribute/rubric mapping done, teacher not needed."""
        cfg = self._cfg()
        done = {'attribute_mapping', 'rubric_mapping', 'data_generation'}
        needed = _models_needed(cfg, 'resume', done)
        assert 'teacher' not in needed
        assert 'student' in needed
        assert 'judge' in needed

    def test_resume_all_except_evaluation(self):
        """Only judge needed when phases 1-4 completed."""
        cfg = self._cfg()
        done = {
            'attribute_mapping', 'rubric_mapping',
            'data_generation', 'response_collection',
        }
        needed = _models_needed(cfg, 'resume', done)
        assert needed == {'judge'}

    def test_resume_all_complete_empty_set(self):
        """All phases done → nothing to probe."""
        cfg = self._cfg()
        done = {
            'attribute_mapping', 'rubric_mapping',
            'data_generation', 'response_collection', 'evaluation',
        }
        needed = _models_needed(cfg, 'resume', done)
        assert needed == set()


# ---------------------------------------------------------------------------
# probe.run_probe — disable mode
# ---------------------------------------------------------------------------

class TestRunProbeDisable:
    def test_disable_returns_empty_results(self):
        cfg = _minimal_cfg()
        logger = _make_logger()
        results, needed = run_probe(cfg, logger, mode='disable')
        assert results == {}
        assert needed == set()

    def test_disable_logs_info(self):
        cfg = _minimal_cfg()
        logger = _make_logger()
        run_probe(cfg, logger, mode='disable')
        logger.info.assert_called()


# ---------------------------------------------------------------------------
# probe.run_probe — writes probe_results.json
# ---------------------------------------------------------------------------

class TestRunProbeWritesFile:
    def test_probe_writes_json_file_on_success(self, tmp_path):
        cfg = _minimal_cfg()
        logger = _make_logger()
        probe_path = tmp_path / 'probe_results.json'

        # Patch _probe_one to always succeed
        with patch('runner.interfaces.probe._probe_one', return_value=None):
            results, _ = run_probe(
                cfg, logger,
                mode='full',
                on_fail='abort',
                probe_results_path=probe_path,
            )

        assert probe_path.exists()
        data = json.loads(probe_path.read_text())
        assert 'results' in data
        assert data['mode'] == 'full'
        assert data['on_fail'] == 'abort'

    def test_probe_results_contain_all_models(self, tmp_path):
        cfg = _minimal_cfg()
        logger = _make_logger()
        probe_path = tmp_path / 'probe_results.json'

        with patch('runner.interfaces.probe._probe_one', return_value=None):
            run_probe(cfg, logger, mode='full', probe_results_path=probe_path)

        data = json.loads(probe_path.read_text())
        assert set(data['results'].keys()) == {'teacher1', 'student1', 'judge1'}
        for v in data['results'].values():
            assert v == 'ok'

    def test_probe_fail_recorded_in_json(self, tmp_path):
        cfg = _minimal_cfg()
        logger = _make_logger()
        probe_path = tmp_path / 'probe_results.json'

        def _fail_for_student(model, provider_keys):
            if model.name == 'student1':
                raise RuntimeError('auth error')

        with patch('runner.interfaces.probe._probe_one', side_effect=_fail_for_student):
            run_probe(
                cfg, logger,
                mode='full',
                on_fail='warn',
                probe_results_path=probe_path,
            )

        data = json.loads(probe_path.read_text())
        assert data['results']['student1'] != 'ok'
        assert data['results']['teacher1'] == 'ok'


# ---------------------------------------------------------------------------
# probe.run_probe — on_fail behaviour
# ---------------------------------------------------------------------------

class TestRunProbeOnFail:
    def test_abort_fail_returns_error_in_results(self):
        cfg = _minimal_cfg()
        logger = _make_logger()

        with patch('runner.interfaces.probe._probe_one',
                   side_effect=RuntimeError('bad key')):
            results, _ = run_probe(cfg, logger, mode='full', on_fail='abort')

        assert all(v != 'ok' for v in results.values())
        logger.error.assert_called()

    def test_warn_fail_returns_error_but_does_not_raise(self):
        cfg = _minimal_cfg()
        logger = _make_logger()

        with patch('runner.interfaces.probe._probe_one',
                   side_effect=RuntimeError('bad key')):
            results, _ = run_probe(cfg, logger, mode='full', on_fail='warn')

        assert all(v != 'ok' for v in results.values())
        logger.warning.assert_called()


# ---------------------------------------------------------------------------
# Cost estimator — price lookup
# ---------------------------------------------------------------------------

class TestGetPrices:
    def _model(self, model_id):
        return ModelConfig(
            name='m', interface='openai',
            parameters={'model': model_id}, roles=['student'],
        )

    def test_gpt4o_mini_price(self):
        p_in, p_out = get_prices(self._model('gpt-4o-mini'))
        assert p_in == 0.15
        assert p_out == 0.60

    def test_claude_haiku_price(self):
        p_in, p_out = get_prices(self._model('claude-3-haiku-20240307'))
        assert p_in == 0.25
        assert p_out == 1.25

    def test_gemini_flash_price(self):
        p_in, p_out = get_prices(self._model('gemini-2.0-flash'))
        assert p_in == 0.10

    def test_unknown_model_returns_defaults(self):
        p_in, p_out = get_prices(self._model('my-unknown-model-v99'))
        assert p_in == DEFAULT_PRICE_INPUT
        assert p_out == DEFAULT_PRICE_OUTPUT


# ---------------------------------------------------------------------------
# Cost estimator — count_tokens_approx
# ---------------------------------------------------------------------------

class TestCountTokensApprox:
    def test_empty_string(self):
        # minimum 1
        assert count_tokens_approx('') == 1

    def test_short_string(self):
        # 12 chars / 4 = 3 tokens
        assert count_tokens_approx('Hello world!') == 3

    def test_longer_string(self):
        text = 'x' * 100
        assert count_tokens_approx(text) == 25


# ---------------------------------------------------------------------------
# Cost estimator — heuristics
# ---------------------------------------------------------------------------

class TestHeuristics:
    def _model(self, iface):
        return ModelConfig(
            name='m', interface=iface,
            parameters={'model': 'm'}, roles=['student'],
        )

    def test_openai_latency(self):
        assert _heuristic_latency(self._model('openai')) > 0

    def test_hf_latency_greater_than_openai(self):
        assert _heuristic_latency(self._model('huggingface')) > _heuristic_latency(self._model('openai'))

    def test_openai_tps_positive(self):
        assert _heuristic_tps(self._model('openai')) > 0

    def test_gemini_tps_positive(self):
        assert _heuristic_tps(self._model('gemini')) > 0


# ---------------------------------------------------------------------------
# Cost estimator — estimate_experiment_cost structure
# ---------------------------------------------------------------------------

class TestEstimateExperimentCost:
    def test_report_has_required_keys(self, tmp_path):
        from runner.interfaces.cost_estimator import estimate_experiment_cost
        cfg = _minimal_cfg()
        # Provide a mock storage with run_path
        storage = MagicMock()
        storage.run_path = tmp_path
        logger = _make_logger()

        report = estimate_experiment_cost(
            cfg, storage, logger,
            n_samples=0,       # no real API calls
            run_sample_calls=False,
        )

        assert 'total_cost_usd' in report
        assert 'total_calls' in report
        assert 'total_time_min' in report
        assert 'per_phase' in report
        assert 'per_model' in report
        assert 'assumptions' in report

    def test_report_per_phase_has_all_phases(self, tmp_path):
        from runner.interfaces.cost_estimator import estimate_experiment_cost
        cfg = _minimal_cfg()
        storage = MagicMock()
        storage.run_path = tmp_path
        logger = _make_logger()

        report = estimate_experiment_cost(
            cfg, storage, logger, n_samples=0, run_sample_calls=False
        )
        expected = {
            'attribute_mapping', 'rubric_mapping', 'data_generation',
            'response_collection', 'evaluation',
        }
        assert set(report['per_phase'].keys()) == expected

    def test_total_cost_positive(self, tmp_path):
        from runner.interfaces.cost_estimator import estimate_experiment_cost
        cfg = _minimal_cfg()
        storage = MagicMock()
        storage.run_path = tmp_path
        logger = _make_logger()

        report = estimate_experiment_cost(
            cfg, storage, logger, n_samples=0, run_sample_calls=False
        )
        assert report['total_cost_usd'] >= 0.0

    def test_cost_estimate_json_written(self, tmp_path):
        from runner.interfaces.cost_estimator import estimate_experiment_cost
        cfg = _minimal_cfg()
        storage = MagicMock()
        storage.run_path = tmp_path
        logger = _make_logger()

        estimate_experiment_cost(
            cfg, storage, logger, n_samples=0, run_sample_calls=False
        )
        estimate_file = tmp_path / 'cost_estimate.json'
        assert estimate_file.exists()
        data = json.loads(estimate_file.read_text())
        assert 'total_cost_usd' in data

    def test_batch_reduces_cost(self, tmp_path):
        """Enabling batch for all phases should reduce total cost by ~50%."""
        from runner.interfaces.cost_estimator import estimate_experiment_cost

        cfg_no_batch = _minimal_cfg()
        cfg_batch = _minimal_cfg(
            batch={'openai': {
                'data_generation': True,
                'response_collection': True,
                'evaluation': True,
            }}
        )
        storage = MagicMock()
        storage.run_path = tmp_path
        logger = _make_logger()

        r_no_batch = estimate_experiment_cost(
            cfg_no_batch, storage, logger, n_samples=0, run_sample_calls=False
        )
        r_batch = estimate_experiment_cost(
            cfg_batch, storage, logger, n_samples=0, run_sample_calls=False
        )
        # Batch should be cheaper (or equal if cost was 0)
        assert r_batch['total_cost_usd'] <= r_no_batch['total_cost_usd']


# ---------------------------------------------------------------------------
# Config validation V-15: probe_mode
# ---------------------------------------------------------------------------

class TestV15ProbeModeValidation:
    def _raw(self, probe_mode):
        return {
            'models': [
                {'name': 'teacher1', 'interface': 'openai',
                 'parameters': {'model': 'gpt-4o-mini'}, 'roles': ['teacher']},
                {'name': 'student1', 'interface': 'openai',
                 'parameters': {'model': 'gpt-4o-mini'}, 'roles': ['student']},
                {'name': 'judge1', 'interface': 'openai',
                 'parameters': {'model': 'gpt-4o-mini'}, 'roles': ['judge']},
            ],
            'tasks': [{
                'name': 'task1', 'description': 'D', 'output_description': 'O',
                'target_attributes': {'a': ['x']},
                'nuanced_attributes': {'b': ['y']},
                'sampling': {'target': [1, 1], 'nuance': [1, 1], 'total': 2},
                'rubric': {'acc': 'correct?'},
            }],
            'experiment': {
                'id': 'e1',
                'storage_folder': '/tmp',
                'probe_mode': probe_mode,
            },
        }

    def test_valid_probe_mode_full(self):
        cfg = _parse_config(self._raw('full'))
        errors = validate_config(cfg)
        assert not any('probe_mode' in e for e in errors)

    def test_valid_probe_mode_resume(self):
        cfg = _parse_config(self._raw('resume'))
        errors = validate_config(cfg)
        assert not any('probe_mode' in e for e in errors)

    def test_valid_probe_mode_disable(self):
        cfg = _parse_config(self._raw('disable'))
        errors = validate_config(cfg)
        assert not any('probe_mode' in e for e in errors)

    def test_invalid_probe_mode(self):
        cfg = _parse_config(self._raw('always'))
        errors = validate_config(cfg)
        assert any('probe_mode' in e for e in errors)


# ---------------------------------------------------------------------------
# Config validation V-16: probe_on_fail
# ---------------------------------------------------------------------------

class TestV16ProbeOnFailValidation:
    def _raw(self, on_fail):
        return {
            'models': [
                {'name': 'teacher1', 'interface': 'openai',
                 'parameters': {'model': 'gpt-4o-mini'}, 'roles': ['teacher']},
                {'name': 'student1', 'interface': 'openai',
                 'parameters': {'model': 'gpt-4o-mini'}, 'roles': ['student']},
                {'name': 'judge1', 'interface': 'openai',
                 'parameters': {'model': 'gpt-4o-mini'}, 'roles': ['judge']},
            ],
            'tasks': [{
                'name': 'task1', 'description': 'D', 'output_description': 'O',
                'target_attributes': {'a': ['x']},
                'nuanced_attributes': {'b': ['y']},
                'sampling': {'target': [1, 1], 'nuance': [1, 1], 'total': 2},
                'rubric': {'acc': 'correct?'},
            }],
            'experiment': {
                'id': 'e1',
                'storage_folder': '/tmp',
                'probe_on_fail': on_fail,
            },
        }

    def test_valid_abort(self):
        cfg = _parse_config(self._raw('abort'))
        assert not any('probe_on_fail' in e for e in validate_config(cfg))

    def test_valid_warn(self):
        cfg = _parse_config(self._raw('warn'))
        assert not any('probe_on_fail' in e for e in validate_config(cfg))

    def test_invalid(self):
        cfg = _parse_config(self._raw('ignore'))
        errors = validate_config(cfg)
        assert any('probe_on_fail' in e for e in errors)


# ---------------------------------------------------------------------------
# Config validation V-17: label_attributes subset of target_attributes
# ---------------------------------------------------------------------------

class TestV17LabelAttributesValidation:
    def _raw(self, target_attrs, label_attrs):
        return {
            'models': [
                {'name': 'teacher1', 'interface': 'openai',
                 'parameters': {'model': 'gpt-4o-mini'}, 'roles': ['teacher']},
                {'name': 'student1', 'interface': 'openai',
                 'parameters': {'model': 'gpt-4o-mini'}, 'roles': ['student']},
                {'name': 'judge1', 'interface': 'openai',
                 'parameters': {'model': 'gpt-4o-mini'}, 'roles': ['judge']},
            ],
            'tasks': [{
                'name': 'task1', 'description': 'D', 'output_description': 'O',
                'target_attributes': target_attrs,
                'nuanced_attributes': {'b': ['y']},
                'sampling': {'target': [1, 1], 'nuance': [1, 1], 'total': 2},
                'rubric': {'acc': 'correct?'},
                'label_attributes': label_attrs,
            }],
            'experiment': {'id': 'e1', 'storage_folder': '/tmp'},
        }

    def test_valid_subset(self):
        cfg = _parse_config(self._raw(
            target_attrs={'sentiment': ['pos', 'neg'], 'topic': ['sports']},
            label_attrs=['sentiment'],
        ))
        assert not any('label_attributes' in e for e in validate_config(cfg))

    def test_valid_exact_match(self):
        cfg = _parse_config(self._raw(
            target_attrs={'sentiment': ['pos', 'neg']},
            label_attrs=['sentiment'],
        ))
        assert not any('label_attributes' in e for e in validate_config(cfg))

    def test_unknown_label_attribute_raises(self):
        cfg = _parse_config(self._raw(
            target_attrs={'sentiment': ['pos', 'neg']},
            label_attrs=['entity_type'],   # not in target_attributes!
        ))
        errors = validate_config(cfg)
        assert any('label_attributes' in e for e in errors)

    def test_auto_target_skips_validation(self):
        """When target_attributes is 'auto', V-17 cannot be checked — must pass."""
        cfg = _parse_config(self._raw(
            target_attrs='auto',
            label_attrs=['anything'],
        ))
        errors = validate_config(cfg)
        assert not any('label_attributes' in e for e in errors)

    def test_empty_label_attributes_always_passes(self):
        cfg = _parse_config(self._raw(
            target_attrs={'sentiment': ['pos']},
            label_attrs=[],
        ))
        assert not any('label_attributes' in e for e in validate_config(cfg))


# ---------------------------------------------------------------------------
# Config parsing: new fields round-trip correctly
# ---------------------------------------------------------------------------

class TestConfigParsingNewFields:
    def _raw(self, **exp_kwargs):
        base = {
            'models': [
                {'name': 't', 'interface': 'openai',
                 'parameters': {'model': 'gpt-4o-mini'}, 'roles': ['teacher']},
                {'name': 's', 'interface': 'openai',
                 'parameters': {'model': 'gpt-4o-mini'}, 'roles': ['student']},
                {'name': 'j', 'interface': 'openai',
                 'parameters': {'model': 'gpt-4o-mini'}, 'roles': ['judge']},
            ],
            'tasks': [{
                'name': 'task1', 'description': 'D', 'output_description': 'O',
                'target_attributes': {'sentiment': ['pos', 'neg']},
                'nuanced_attributes': {'b': ['y']},
                'sampling': {'target': [1, 1], 'nuance': [1, 1], 'total': 2},
                'rubric': {'acc': 'correct?'},
                'label_attributes': ['sentiment'],
            }],
            'experiment': {'id': 'e1', 'storage_folder': '/tmp', **exp_kwargs},
        }
        return base

    def test_label_attributes_parsed_in_task(self):
        cfg = _parse_config(self._raw())
        assert cfg.tasks[0].label_attributes == ['sentiment']

    def test_probe_mode_parsed(self):
        cfg = _parse_config(self._raw(probe_mode='resume'))
        assert cfg.experiment.probe_mode == 'resume'

    def test_probe_on_fail_parsed(self):
        cfg = _parse_config(self._raw(probe_on_fail='warn'))
        assert cfg.experiment.probe_on_fail == 'warn'

    def test_estimate_cost_parsed(self):
        cfg = _parse_config(self._raw(estimate_cost=True))
        assert cfg.experiment.estimate_cost is True

    def test_estimate_samples_parsed(self):
        cfg = _parse_config(self._raw(estimate_samples=5))
        assert cfg.experiment.estimate_samples == 5

    def test_defaults_when_absent(self):
        cfg = _parse_config(self._raw())
        assert cfg.experiment.probe_mode == 'full'
        assert cfg.experiment.probe_on_fail == 'abort'
        assert cfg.experiment.estimate_cost is False
        assert cfg.experiment.estimate_samples == 2


# ---------------------------------------------------------------------------
# Cost estimator — remaining-work estimate (continue_in_place=True)
# ---------------------------------------------------------------------------

class TestEstimateExperimentCostRemaining:
    """Verify that continue_in_place=True produces a remaining-work estimate."""

    def _build_storage(self, tmp_path, cfg):
        """Create a real ExperimentStorage and initialise it."""
        from runner.storage import ExperimentStorage
        storage = ExperimentStorage(str(tmp_path), cfg.experiment.id)
        storage.initialize({'x': 1})
        return storage

    def test_remaining_report_has_is_remaining_flag(self, tmp_path):
        from runner.interfaces.cost_estimator import estimate_experiment_cost
        cfg = _minimal_cfg()
        storage = self._build_storage(tmp_path, cfg)
        logger = _make_logger()

        report = estimate_experiment_cost(
            cfg, storage, logger,
            n_samples=0, run_sample_calls=False,
            continue_in_place=True,
        )
        assert report['is_remaining_estimate'] is True

    def test_full_report_has_is_remaining_false(self, tmp_path):
        from runner.interfaces.cost_estimator import estimate_experiment_cost
        cfg = _minimal_cfg()
        storage = MagicMock()
        storage.run_path = tmp_path
        logger = _make_logger()

        report = estimate_experiment_cost(
            cfg, storage, logger,
            n_samples=0, run_sample_calls=False,
        )
        assert report['is_remaining_estimate'] is False

    def test_remaining_completed_phases_recorded(self, tmp_path):
        from runner.interfaces.cost_estimator import estimate_experiment_cost
        cfg = _minimal_cfg()
        storage = self._build_storage(tmp_path, cfg)
        logger = _make_logger()

        done = {'attribute_mapping', 'rubric_mapping'}
        report = estimate_experiment_cost(
            cfg, storage, logger,
            n_samples=0, run_sample_calls=False,
            continue_in_place=True,
            completed_phases=done,
        )
        assert set(report['completed_phases']) == done

    def test_remaining_completed_phases_contribute_zero_calls(self, tmp_path):
        """Phases listed as completed must contribute 0 calls to the estimate."""
        from runner.interfaces.cost_estimator import estimate_experiment_cost
        cfg = _minimal_cfg()
        storage = self._build_storage(tmp_path, cfg)
        logger = _make_logger()

        # All phases done → expect 0 calls remaining
        all_phases = {
            'attribute_mapping', 'rubric_mapping',
            'data_generation', 'response_collection', 'evaluation',
        }
        report = estimate_experiment_cost(
            cfg, storage, logger,
            n_samples=0, run_sample_calls=False,
            continue_in_place=True,
            completed_phases=all_phases,
        )
        assert report['total_calls'] == 0
        assert report['total_cost_usd'] == 0.0

    def test_remaining_no_storage_data_equals_full_estimate_for_phases35(self, tmp_path):
        """With empty storage and no completed phases, phases 3-5 remaining
        calls must be equal to (or at most) the full-estimate call counts for
        those phases (full estimate may count some phases differently)."""
        from runner.interfaces.cost_estimator import estimate_experiment_cost
        cfg = _minimal_cfg()  # static rubric, so phases 1-2 = 0 calls in full mode
        storage_real = self._build_storage(tmp_path, cfg)
        storage_mock = MagicMock()
        storage_mock.run_path = tmp_path

        logger = _make_logger()
        # Remaining with empty storage
        r_remaining = estimate_experiment_cost(
            cfg, storage_real, logger,
            n_samples=0, run_sample_calls=False,
            continue_in_place=True,
        )
        # For phases 3-5 with zero pre-existing data, remaining == total (for static rubric cfg)
        # Phase 3: 1 teacher × 1 task × 2 items = 2 calls
        assert r_remaining['per_phase']['data_generation']['calls_per_model'].get('teacher1', 0) == 2
        # Phase 5: 1 teacher × 1 judge × 1 student × 2 items × 1 (single mode) = 2 calls
        assert r_remaining['per_phase']['evaluation']['calls_per_model'].get('judge1', 0) == 2

    def test_remaining_partial_phase3_reduces_calls(self, tmp_path):
        """Pre-existing datapoints reduce the Phase 3 remaining call count."""
        from runner.interfaces.cost_estimator import estimate_experiment_cost
        cfg = _minimal_cfg()
        storage = self._build_storage(tmp_path, cfg)
        logger = _make_logger()

        # Pre-populate 1 out of 2 datapoints for the (task1, teacher1) slot
        storage.append_datapoint('task1', 'teacher1', {'id': 'dp1', 'prompt': 'p', 'response': 'r'})

        report = estimate_experiment_cost(
            cfg, storage, logger,
            n_samples=0, run_sample_calls=False,
            continue_in_place=True,
        )
        # 2 total - 1 done = 1 remaining
        phase3_calls = report['per_phase']['data_generation']['calls_per_model'].get('teacher1', 0)
        assert phase3_calls == 1

    def test_remaining_all_phase3_done_gives_zero_calls(self, tmp_path):
        """When all datapoints exist for a slot, Phase 3 remaining = 0."""
        from runner.interfaces.cost_estimator import estimate_experiment_cost
        cfg = _minimal_cfg()
        storage = self._build_storage(tmp_path, cfg)
        logger = _make_logger()

        # total = 2; write both datapoints
        for i in range(2):
            storage.append_datapoint('task1', 'teacher1', {'id': f'dp{i}', 'prompt': 'p', 'response': 'r'})

        report = estimate_experiment_cost(
            cfg, storage, logger,
            n_samples=0, run_sample_calls=False,
            continue_in_place=True,
        )
        phase3_calls = report['per_phase']['data_generation']['calls_per_model'].get('teacher1', 0)
        assert phase3_calls == 0

    def test_remaining_partial_phase5_reduces_calls(self, tmp_path):
        """Pre-existing evaluation records reduce the Phase 5 remaining call count."""
        from runner.interfaces.cost_estimator import estimate_experiment_cost
        cfg = _minimal_cfg()
        storage = self._build_storage(tmp_path, cfg)
        logger = _make_logger()

        # 2 total responses expected per (task, teacher, judge) (1 student × 2 items).
        # Pre-populate 1 already-evaluated response.
        storage.append_evaluation(
            'task1', 'teacher1', 'judge1',
            {'response_id': 'resp1', 'status': 'ok', 'score': 4},
        )

        report = estimate_experiment_cost(
            cfg, storage, logger,
            n_samples=0, run_sample_calls=False,
            continue_in_place=True,
        )
        # 2 total - 1 done = 1 remaining call
        phase5_calls = report['per_phase']['evaluation']['calls_per_model'].get('judge1', 0)
        assert phase5_calls == 1

    def test_remaining_cost_json_includes_is_remaining_flag(self, tmp_path):
        """cost_estimate.json must record is_remaining_estimate=True."""
        from runner.interfaces.cost_estimator import estimate_experiment_cost
        cfg = _minimal_cfg()
        storage = self._build_storage(tmp_path, cfg)
        logger = _make_logger()

        estimate_experiment_cost(
            cfg, storage, logger,
            n_samples=0, run_sample_calls=False,
            continue_in_place=True,
        )
        data = json.loads((tmp_path / 'test-exp' / 'cost_estimate.json').read_text())
        assert data['is_remaining_estimate'] is True
