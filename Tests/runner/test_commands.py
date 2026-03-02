"""
Tests for the standalone CLI commands: probe, plan, status.

All tests use tmp_path and mocking; no real LLM calls, no network.
Tests verify:
  - probe_cmd: loads config, runs probe, prints table, exits correctly
  - plan_cmd: loads config, runs estimator (heuristics only), exits 0
  - status_cmd: reads experiment folder, prints progress, handles batches
  - config.validate_config: _skip_folder_validation suppresses V-11 and V-14
  - status_cmd: _apply_phase4_results / _apply_phase5_results helpers
"""
import argparse
import json
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import yaml

from runner.config import _parse_config, validate_config
from runner.storage import ExperimentStorage


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _minimal_raw(*, storage_folder, exp_id='exp-test', exp_overrides=None):
    return {
        'models': [
            {
                'name': 'mdl',
                'interface': 'openai',
                'parameters': {'model': 'gpt-4o-mini'},
                'roles': ['teacher', 'student', 'judge'],
            }
        ],
        'tasks': [
            {
                'name': 'task1',
                'description': 'Test task.',
                'output_description': 'One word.',
                'target_attributes': {'quality': ['high', 'low']},
                'nuanced_attributes': {'style': ['formal', 'casual']},
                'sampling': {'target': [1, 1], 'nuance': [1, 1], 'total': 2},
                'rubric': {'quality': 'Output quality.'},
            }
        ],
        'experiment': {
            'id': exp_id,
            'storage_folder': str(storage_folder),
            **(exp_overrides or {}),
        },
    }


def _write_config(path: Path, raw: dict) -> Path:
    cfg_path = path / 'config.yaml'
    with open(cfg_path, 'w') as f:
        yaml.dump(raw, f)
    return cfg_path


def _make_store(tmp_path, exp_id='exp-test') -> ExperimentStorage:
    s = ExperimentStorage(str(tmp_path), exp_id)
    s.initialize({'x': 1})
    return s


# ---------------------------------------------------------------------------
# validate_config — _skip_folder_validation
# ---------------------------------------------------------------------------

class TestSkipFolderValidation:
    """Tests for the new _skip_folder_validation parameter on validate_config."""

    def test_v11_fires_normally_when_folder_exists(self, tmp_path):
        """V-11 should error if folder exists and _skip_folder_validation=False."""
        (tmp_path / 'exp-test').mkdir()
        raw = _minimal_raw(storage_folder=tmp_path)
        cfg = _parse_config(raw)
        errors = validate_config(cfg, continue_in_place=False, _skip_folder_validation=False)
        assert any('already exists' in e for e in errors)

    def test_v11_suppressed_by_skip_folder_validation(self, tmp_path):
        """V-11 must NOT fire when _skip_folder_validation=True."""
        (tmp_path / 'exp-test').mkdir()
        raw = _minimal_raw(storage_folder=tmp_path)
        cfg = _parse_config(raw)
        errors = validate_config(cfg, _skip_folder_validation=True)
        assert not any('already exists' in e for e in errors)

    def test_v14_fires_normally_when_continue_and_no_meta(self, tmp_path):
        """V-14 should error if continue_in_place=True and meta.json is missing."""
        raw = _minimal_raw(storage_folder=tmp_path)
        cfg = _parse_config(raw)
        errors = validate_config(cfg, continue_in_place=True)
        assert any('no existing experiment found' in e for e in errors)

    def test_v14_suppressed_by_skip_folder_validation(self, tmp_path):
        """V-14 must NOT fire when _skip_folder_validation=True (even with continue_in_place)."""
        raw = _minimal_raw(storage_folder=tmp_path)
        cfg = _parse_config(raw)
        # continue_in_place=True would normally trigger V-14; skip_folder_validation must suppress it
        errors = validate_config(
            cfg, continue_in_place=True, _skip_folder_validation=True
        )
        assert not any('no existing experiment found' in e for e in errors)

    def test_skip_folder_validation_preserves_other_rules(self, tmp_path):
        """_skip_folder_validation must not suppress unrelated validation rules (e.g. V-02)."""
        (tmp_path / 'exp-test').mkdir()
        raw = _minimal_raw(storage_folder=tmp_path)
        # Introduce a duplicate model name (triggers V-02)
        raw['models'].append({
            'name': 'mdl',  # duplicate
            'interface': 'openai',
            'parameters': {'model': 'gpt-4o-mini'},
            'roles': ['student'],
        })
        cfg = _parse_config(raw)
        errors = validate_config(cfg, _skip_folder_validation=True)
        assert any('Duplicate model name' in e for e in errors)


# ---------------------------------------------------------------------------
# probe_cmd
# ---------------------------------------------------------------------------

class TestCmdProbe:
    """Tests for experiments.commands.probe_cmd.cmd_probe."""

    def _make_args(self, config_path, probe_mode=None, probe_on_fail=None, log_level='INFO'):
        ns = argparse.Namespace(
            config=str(config_path),
            probe_mode=probe_mode,
            probe_on_fail=probe_on_fail,
            log_level=log_level,
        )
        return ns

    def test_probe_all_ok_returns_normally(self, tmp_path, capsys):
        """When all models probe OK, cmd_probe returns without raising SystemExit."""
        raw = _minimal_raw(storage_folder=tmp_path)
        cfg_path = _write_config(tmp_path, raw)
        args = self._make_args(cfg_path)

        with patch(
            'runner.interfaces.probe.run_probe',
            return_value=({'mdl': 'ok'}, {'mdl'}),
        ):
            from runner.commands.probe_cmd import cmd_probe
            cmd_probe(args)  # should not raise

    def test_probe_one_fail_abort_exits_2(self, tmp_path, capsys):
        """When a model fails and on_fail='abort', cmd_probe exits 2."""
        raw = _minimal_raw(storage_folder=tmp_path, exp_overrides={'probe_on_fail': 'abort'})
        cfg_path = _write_config(tmp_path, raw)
        args = self._make_args(cfg_path, probe_on_fail='abort')

        with patch(
            'runner.interfaces.probe.run_probe',
            return_value=({'mdl': 'connection refused'}, {'mdl'}),
        ):
            with pytest.raises(SystemExit) as exc_info:
                from runner.commands.probe_cmd import cmd_probe
                cmd_probe(args)
        assert exc_info.value.code == 2

    def test_probe_one_fail_warn_returns_normally(self, tmp_path):
        """When a model fails and on_fail='warn', cmd_probe returns without raising."""
        raw = _minimal_raw(storage_folder=tmp_path, exp_overrides={'probe_on_fail': 'warn'})
        cfg_path = _write_config(tmp_path, raw)
        args = self._make_args(cfg_path, probe_on_fail='warn')

        with patch(
            'runner.interfaces.probe.run_probe',
            return_value=({'mdl': 'connection refused'}, {'mdl'}),
        ):
            from runner.commands.probe_cmd import cmd_probe
            cmd_probe(args)  # should not raise (warn mode)

    def test_probe_bad_config_exits_1(self, tmp_path):
        """A config YAML with a load error should exit 1."""
        bad_path = tmp_path / 'bad.yaml'
        bad_path.write_text("not: [valid: yaml: here", encoding='utf-8')
        args = self._make_args(bad_path)

        with pytest.raises(SystemExit) as exc_info:
            from runner.commands.probe_cmd import cmd_probe
            cmd_probe(args)
        assert exc_info.value.code == 1

    def test_probe_prints_results_table(self, tmp_path, capsys):
        """Results table should be printed to stdout."""
        raw = _minimal_raw(storage_folder=tmp_path)
        cfg_path = _write_config(tmp_path, raw)
        args = self._make_args(cfg_path)

        with patch(
            'runner.interfaces.probe.run_probe',
            return_value=({'mdl': 'ok'}, {'mdl'}),
        ):
            from runner.commands.probe_cmd import cmd_probe
            cmd_probe(args)

        out = capsys.readouterr().out
        assert 'mdl' in out
        assert '[OK]' in out

    def test_probe_validation_errors_exit_1(self, tmp_path):
        """Config validation errors (e.g. duplicate model) should exit 1."""
        raw = _minimal_raw(storage_folder=tmp_path)
        # Introduce a duplicate model to trigger V-02
        raw['models'].append({
            'name': 'mdl',
            'interface': 'openai',
            'parameters': {'model': 'gpt-4o-mini'},
            'roles': ['student'],
        })
        cfg_path = _write_config(tmp_path, raw)
        args = self._make_args(cfg_path)

        with pytest.raises(SystemExit) as exc_info:
            from runner.commands.probe_cmd import cmd_probe
            cmd_probe(args)
        assert exc_info.value.code == 1

    def test_probe_skip_folder_validation_folder_already_exists(self, tmp_path):
        """V-11 must be suppressed for probe even when folder already exists."""
        # Create the experiment folder (would normally trigger V-11 for a 'run')
        exp_folder = tmp_path / 'exp-test'
        exp_folder.mkdir()
        raw = _minimal_raw(storage_folder=tmp_path)
        cfg_path = _write_config(tmp_path, raw)
        args = self._make_args(cfg_path)

        with patch(
            'runner.interfaces.probe.run_probe',
            return_value=({'mdl': 'ok'}, {'mdl'}),
        ):
            # Should not raise SystemExit(1) — V-11 is suppressed for probe
            from runner.commands.probe_cmd import cmd_probe
            cmd_probe(args)


# ---------------------------------------------------------------------------
# plan_cmd
# ---------------------------------------------------------------------------

class TestCmdPlan:
    """Tests for experiments.commands.plan_cmd.cmd_plan."""

    def _make_args(
        self,
        config_path,
        continue_in_place=False,
        estimate_samples=0,
        log_level='INFO',
    ):
        return argparse.Namespace(
            config=str(config_path),
            continue_in_place=continue_in_place,
            estimate_samples=estimate_samples,
            log_level=log_level,
        )

    def test_plan_fresh_exits_0(self, tmp_path, capsys):
        """plan for a fresh config (no --continue) should exit 0."""
        raw = _minimal_raw(storage_folder=tmp_path)
        cfg_path = _write_config(tmp_path, raw)
        args = self._make_args(cfg_path, estimate_samples=0)

        with patch(
            'runner.interfaces.cost_estimator.estimate_experiment_cost',
            return_value={'total_cost_usd': 0.01, 'total_time_min': 1.0},
        ):
            # cmd_plan does not sys.exit on success — just returns
            from runner.commands.plan_cmd import cmd_plan
            cmd_plan(args)  # Should not raise

    def test_plan_bad_config_exits_1(self, tmp_path):
        """A bad config path should exit 1."""
        args = self._make_args(tmp_path / 'nonexistent.yaml')

        with pytest.raises(SystemExit) as exc_info:
            from runner.commands.plan_cmd import cmd_plan
            cmd_plan(args)
        assert exc_info.value.code == 1

    def test_plan_continue_reads_completed_phases(self, tmp_path):
        """--continue should read phases_completed from meta.json."""
        raw = _minimal_raw(storage_folder=tmp_path)
        cfg_path = _write_config(tmp_path, raw)
        store = _make_store(tmp_path)
        store.update_meta(phase_completed='attribute_mapping')

        args = self._make_args(cfg_path, continue_in_place=True, estimate_samples=0)

        captured_kwargs = {}

        def fake_estimate(cfg, storage, logger, **kwargs):
            captured_kwargs.update(kwargs)
            return {}

        with patch(
            'runner.interfaces.cost_estimator.estimate_experiment_cost',
            side_effect=fake_estimate,
        ):
            from runner.commands.plan_cmd import cmd_plan
            cmd_plan(args)

        assert captured_kwargs.get('continue_in_place') is True
        completed = captured_kwargs.get('completed_phases') or set()
        assert 'attribute_mapping' in completed

    def test_plan_no_continue_passes_none_for_completed_phases(self, tmp_path):
        """Without --continue, completed_phases passed to estimator should be None."""
        raw = _minimal_raw(storage_folder=tmp_path)
        cfg_path = _write_config(tmp_path, raw)
        args = self._make_args(cfg_path, estimate_samples=0)

        captured_kwargs = {}

        def fake_estimate(cfg, storage, logger, **kwargs):
            captured_kwargs.update(kwargs)
            return {}

        with patch(
            'runner.interfaces.cost_estimator.estimate_experiment_cost',
            side_effect=fake_estimate,
        ):
            from runner.commands.plan_cmd import cmd_plan
            cmd_plan(args)

        assert captured_kwargs.get('completed_phases') is None

    def test_plan_estimate_samples_override(self, tmp_path):
        """--estimate-samples N should be forwarded to the estimator."""
        raw = _minimal_raw(storage_folder=tmp_path)
        cfg_path = _write_config(tmp_path, raw)
        args = self._make_args(cfg_path, estimate_samples=5)

        captured_kwargs = {}

        def fake_estimate(cfg, storage, logger, **kwargs):
            captured_kwargs.update(kwargs)
            return {}

        with patch(
            'runner.interfaces.cost_estimator.estimate_experiment_cost',
            side_effect=fake_estimate,
        ):
            from runner.commands.plan_cmd import cmd_plan
            cmd_plan(args)

        assert captured_kwargs.get('n_samples') == 5

    def test_plan_validation_errors_exit_1(self, tmp_path):
        """Config validation errors should exit 1."""
        raw = _minimal_raw(storage_folder=tmp_path)
        raw['models'].append({
            'name': 'mdl',  # duplicate
            'interface': 'openai',
            'parameters': {'model': 'gpt-4o-mini'},
            'roles': ['student'],
        })
        cfg_path = _write_config(tmp_path, raw)
        args = self._make_args(cfg_path)

        with pytest.raises(SystemExit) as exc_info:
            from runner.commands.plan_cmd import cmd_plan
            cmd_plan(args)
        assert exc_info.value.code == 1


# ---------------------------------------------------------------------------
# status_cmd — helper functions
# ---------------------------------------------------------------------------

class TestStatusCmdHelpers:
    """Unit tests for status_cmd helper functions (no subprocess / CLI needed)."""

    @pytest.fixture
    def store(self, tmp_path):
        s = ExperimentStorage(str(tmp_path), 'exp-test')
        s.initialize({'x': 1})
        return s

    # --- _apply_phase4_results ---

    def test_apply_phase4_writes_response_record(self, store, tmp_path):
        """_apply_phase4_results must write a response record for a valid key."""
        from runner.commands.status_cmd import _apply_phase4_results

        # Set up a datapoint
        store.append_datapoint('task1', 'teacher1', {
            'id': 'dp001',
            'prompt': 'hello world',
            'response': 'hi',
        })

        key = '\x00'.join(['task1', 'teacher1', 'student1', 'dp001'])
        n = _apply_phase4_results({key: 'response text'}, store)

        assert n == 1
        responses = store.read_responses('task1', 'teacher1', 'student1')
        assert len(responses) == 1
        rec = responses[0]
        assert rec['task_id'] == 'task1'
        assert rec['teacher_model_id'] == 'teacher1'
        assert rec['student_model_id'] == 'student1'
        assert rec['datapoint_id'] == 'dp001'
        assert rec['response'] == 'response text'
        assert rec['input'] == 'hello world'

    def test_apply_phase4_empty_response_marks_failed(self, store, tmp_path):
        """Empty response_text in Phase 4 should set status='failed'."""
        from runner.commands.status_cmd import _apply_phase4_results

        key = '\x00'.join(['task1', 'teacher1', 'student1', 'dp002'])
        _apply_phase4_results({key: ''}, store)

        responses = store.read_responses('task1', 'teacher1', 'student1')
        assert responses[0].get('status') == 'failed'

    def test_apply_phase4_ignores_invalid_keys(self, store):
        """Keys with wrong number of parts should be skipped silently."""
        from runner.commands.status_cmd import _apply_phase4_results

        bad_key = 'only\x00two_parts'
        n = _apply_phase4_results({bad_key: 'text'}, store)
        assert n == 0

    def test_apply_phase4_multiple_records(self, store):
        """Multiple keys in one batch should each produce a record."""
        from runner.commands.status_cmd import _apply_phase4_results

        keys = {
            '\x00'.join(['task1', 'teacher1', 'student1', f'dp{i:03d}']): f'resp {i}'
            for i in range(5)
        }
        n = _apply_phase4_results(keys, store)
        assert n == 5
        responses = store.read_responses('task1', 'teacher1', 'student1')
        assert len(responses) == 5

    # --- _apply_phase5_results (single mode) ---

    def test_apply_phase5_single_writes_eval_record(self, store):
        """_apply_phase5_results must write an eval record for single-mode keys."""
        from runner.commands.status_cmd import _apply_phase5_results

        # Set up rubric
        store.write_rubric('task1', {'quality': 'Overall quality.'})

        # Single-mode key: task\x00teacher\x00judge\x00response_id\x01
        key = '\x00'.join(['task1', 'teacher1', 'judge1', 'dp001__student1']) + '\x01'
        response_text = json.dumps({'quality': 'High'})

        n = _apply_phase5_results({key: response_text}, store)

        assert n == 1
        evals = store.read_evaluations('task1', 'teacher1', 'judge1')
        assert len(evals) == 1
        rec = evals[0]
        assert rec['task_id'] == 'task1'
        assert rec['judge_model_id'] == 'judge1'
        assert rec['scores']['quality'] == 'High'

    def test_apply_phase5_single_bad_json_defaults_to_low(self, store):
        """Unparseable JSON for single-mode should default all factors to 'Low'."""
        from runner.commands.status_cmd import _apply_phase5_results

        store.write_rubric('task1', {'quality': 'Overall quality.'})
        key = '\x00'.join(['task1', 'teacher1', 'judge1', 'dp001__student1']) + '\x01'

        n = _apply_phase5_results({key: 'not json'}, store)

        evals = store.read_evaluations('task1', 'teacher1', 'judge1')
        assert n == 1
        assert evals[0]['scores'].get('quality') == 'Low'

    def test_apply_phase5_per_factor_aggregates(self, store):
        """Per-factor keys should be aggregated into a single eval record."""
        from runner.commands.status_cmd import _apply_phase5_results

        # per_factor keys: task\x00teacher\x00judge\x00response_id\x00factor
        keys = {
            '\x00'.join(['task1', 'teacher1', 'judge1', 'dp001__student1', 'quality']): 'High',
            '\x00'.join(['task1', 'teacher1', 'judge1', 'dp001__student1', 'style']): 'Medium',
        }
        n = _apply_phase5_results(keys, store)

        assert n == 1
        evals = store.read_evaluations('task1', 'teacher1', 'judge1')
        assert len(evals) == 1
        scores = evals[0]['scores']
        assert scores['quality'] == 'High'
        assert scores['style'] == 'Medium'

    def test_apply_phase5_empty_response_marks_failed(self, store):
        """Empty response_text for single-mode should set status='failed'."""
        from runner.commands.status_cmd import _apply_phase5_results

        store.write_rubric('task1', {'quality': 'Quality.'})
        key = '\x00'.join(['task1', 'teacher1', 'judge1', 'dp001__student1']) + '\x01'

        _apply_phase5_results({key: ''}, store)
        evals = store.read_evaluations('task1', 'teacher1', 'judge1')
        assert evals[0].get('status') == 'failed'

    # --- Count helpers ---

    def test_count_jsonl_records(self, tmp_path):
        """_count_jsonl_records should return exact line count."""
        from runner.commands.status_cmd import _count_jsonl_records

        f = tmp_path / 'test.jsonl'
        f.write_text('{"a":1}\n{"b":2}\n\n', encoding='utf-8')
        assert _count_jsonl_records(f) == 2

    def test_count_jsonl_records_missing_file(self, tmp_path):
        """_count_jsonl_records should return 0 for a missing file."""
        from runner.commands.status_cmd import _count_jsonl_records
        assert _count_jsonl_records(tmp_path / 'no_such.jsonl') == 0

    def test_count_failed_records(self, tmp_path):
        """_count_failed_records should count only records with status='failed'."""
        from runner.commands.status_cmd import _count_failed_records

        f = tmp_path / 'test.jsonl'
        f.write_text(
            json.dumps({'id': '1', 'status': 'failed'}) + '\n' +
            json.dumps({'id': '2'}) + '\n',
            encoding='utf-8',
        )
        assert _count_failed_records(f) == 1


# ---------------------------------------------------------------------------
# status_cmd — CLI integration (cmd_status)
# ---------------------------------------------------------------------------

class TestCmdStatus:
    """Integration-level tests for cmd_status (no real API calls)."""

    @pytest.fixture
    def exp_store(self, tmp_path):
        s = ExperimentStorage(str(tmp_path), 'exp-test')
        s.initialize({'x': 1})
        s.update_meta(phase_completed='attribute_mapping')
        return s, tmp_path

    def _make_args(self, run_path, fetch_batches=False):
        return argparse.Namespace(
            run=str(run_path),
            fetch_batches=fetch_batches,
        )

    def test_status_prints_metadata(self, exp_store, capsys):
        """cmd_status should print experiment metadata."""
        store, tmp_path = exp_store
        args = self._make_args(tmp_path / 'exp-test')

        from runner.commands.status_cmd import cmd_status
        cmd_status(args)

        out = capsys.readouterr().out
        assert 'exp-test' in out
        assert 'attribute_mapping' in out

    def test_status_prints_phase_artifacts(self, exp_store, capsys):
        """cmd_status should show phase 1 and 2 artifact counts."""
        store, tmp_path = exp_store
        store.write_target_attrs('task1', {'quality': ['high', 'low']})
        store.write_rubric('task1', {'quality': 'Quality.'})
        args = self._make_args(tmp_path / 'exp-test')

        from runner.commands.status_cmd import cmd_status
        cmd_status(args)

        out = capsys.readouterr().out
        assert 'Phase 1' in out
        assert 'Phase 2' in out

    def test_status_nonexistent_folder_exits_1(self, tmp_path, capsys):
        """cmd_status on a non-existent path should exit 1."""
        args = self._make_args(tmp_path / 'does-not-exist')

        with pytest.raises(SystemExit) as exc_info:
            from runner.commands.status_cmd import cmd_status
            cmd_status(args)
        assert exc_info.value.code == 1

    def test_status_no_meta_json_exits_1(self, tmp_path, capsys):
        """cmd_status on a folder without meta.json should exit 1."""
        folder = tmp_path / 'empty-exp'
        folder.mkdir()
        args = self._make_args(folder)

        with pytest.raises(SystemExit) as exc_info:
            from runner.commands.status_cmd import cmd_status
            cmd_status(args)
        assert exc_info.value.code == 1

    def test_status_shows_pending_batches(self, exp_store, capsys):
        """cmd_status should display pending batch information."""
        store, tmp_path = exp_store
        store.add_pending_batch(
            'batch_abc123',
            'openai',
            'evaluation',
            'Phase 5 evaluations',
            100,
            {'r0': 'key0', 'r1': 'key1'},
        )
        args = self._make_args(tmp_path / 'exp-test')

        from runner.commands.status_cmd import cmd_status
        cmd_status(args)

        out = capsys.readouterr().out
        assert 'batch_abc' in out
        assert 'openai' in out
        assert 'evaluation' in out

    def test_status_no_pending_batches_says_none(self, exp_store, capsys):
        """When no batches are pending, the output should say 'None'."""
        store, tmp_path = exp_store
        args = self._make_args(tmp_path / 'exp-test')

        from runner.commands.status_cmd import cmd_status
        cmd_status(args)

        out = capsys.readouterr().out
        assert 'None' in out  # "Pending Batch Jobs: None"

    def test_status_fetch_batches_without_batches(self, exp_store, capsys):
        """--fetch-batches with no pending batches should print 'No pending batches'."""
        store, tmp_path = exp_store
        args = self._make_args(tmp_path / 'exp-test', fetch_batches=True)

        from runner.commands.status_cmd import cmd_status
        cmd_status(args)

        out = capsys.readouterr().out
        assert 'No pending batches' in out

    def test_status_shows_run_errors(self, exp_store, capsys):
        """cmd_status should display run errors when present."""
        store, tmp_path = exp_store
        store.append_run_error({
            'phase': 'evaluation',
            'error': 'JSON parse failed',
            'timestamp': '2026-02-28T12:00:00Z',
        })
        args = self._make_args(tmp_path / 'exp-test')

        from runner.commands.status_cmd import cmd_status
        cmd_status(args)

        out = capsys.readouterr().out
        assert 'JSON parse failed' in out

    def test_status_counts_phase3_records(self, exp_store, capsys):
        """cmd_status should show phase 3 record counts."""
        store, tmp_path = exp_store
        store.append_datapoint('task1', 'teacher1', {'id': 'dp001', 'prompt': 'p', 'response': 'r'})
        store.append_datapoint('task1', 'teacher1', {'id': 'dp002', 'prompt': 'p2', 'response': 'r2'})
        args = self._make_args(tmp_path / 'exp-test')

        from runner.commands.status_cmd import cmd_status
        cmd_status(args)

        out = capsys.readouterr().out
        # Should mention 2 records in phase 3
        assert '2 records' in out or '2 files' in out or 'Phase 3' in out


# ---------------------------------------------------------------------------
# CLI integration — subcommand dispatch
# ---------------------------------------------------------------------------

class TestCLIDispatch:
    """Verify that cli.main() dispatches probe/plan/status correctly."""

    def test_probe_subcommand_dispatches(self, tmp_path):
        """coeval probe --config X.yaml should call cmd_probe."""
        raw = _minimal_raw(storage_folder=tmp_path)
        cfg_path = _write_config(tmp_path, raw)

        with patch('runner.commands.probe_cmd.cmd_probe') as mock_cmd:
            mock_cmd.side_effect = SystemExit(0)
            with pytest.raises(SystemExit):
                from runner.cli import main
                main(['probe', '--config', str(cfg_path)])
        mock_cmd.assert_called_once()

    def test_plan_subcommand_dispatches(self, tmp_path):
        """coeval plan --config X.yaml should call cmd_plan."""
        raw = _minimal_raw(storage_folder=tmp_path)
        cfg_path = _write_config(tmp_path, raw)

        with patch('runner.commands.plan_cmd.cmd_plan') as mock_cmd:
            mock_cmd.return_value = None  # doesn't exit
            from runner.cli import main
            main(['plan', '--config', str(cfg_path), '--estimate-samples', '0'])
        mock_cmd.assert_called_once()

    def test_status_subcommand_dispatches(self, tmp_path):
        """coeval status --run PATH should call cmd_status."""
        store = _make_store(tmp_path)
        run_path = tmp_path / 'exp-test'

        with patch('runner.commands.status_cmd.cmd_status') as mock_cmd:
            mock_cmd.return_value = None
            from runner.cli import main
            main(['status', '--run', str(run_path)])
        mock_cmd.assert_called_once()
