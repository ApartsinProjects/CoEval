"""
Tests for run_experiment() — the 5-phase pipeline orchestrator (runner.runner).

Covers:
  - dry_run=True: print plan and return 0 without executing any phase runners
  - Normal run: all 5 phases run in PHASE_IDS order
  - PartialPhaseFailure in a phase: exit_code=1 but the pipeline continues to
    the next phase (downstream phases see what partial data was produced)
  - RuntimeError in a phase: exit_code=1 and the pipeline stops immediately
    (subsequent phases are NOT called)
  - continue_in_place=True: phases listed in meta.json as completed are skipped
  - only_models: phase_completed marker is NOT written to meta.json
  - Successful full run returns exit code 0

Strategy
--------
All 5 phase runner functions are replaced with MagicMocks via patch.dict so
no real LLM calls are made.  ExperimentStorage is mocked to avoid filesystem
writes.  RunLogger is mocked to avoid opening log files.  The probe is disabled
via skip_probe=True throughout.
"""
from __future__ import annotations

from unittest.mock import MagicMock, call, patch, patch as _patch
import pytest

from runner.config import PHASE_IDS
from runner.exceptions import PartialPhaseFailure


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_exp(tmp_path, exp_id: str = 'orch-test') -> MagicMock:
    """Minimal mock ExperimentConfig."""
    exp = MagicMock()
    exp.id = exp_id
    exp.storage_folder = str(tmp_path)
    exp.resume_from = None
    exp.probe_mode = None
    exp.probe_on_fail = None
    exp.estimate_samples = 0
    exp.estimate_cost = False
    exp.quota = {}
    exp.log_level = 'INFO'
    return exp


def _make_cfg(tmp_path, exp_id: str = 'orch-test') -> MagicMock:
    """Minimal mock CoEvalConfig."""
    cfg = MagicMock()
    cfg.experiment = _make_exp(tmp_path, exp_id)
    cfg._raw = {'experiment': {'id': exp_id}}
    cfg._provider_keys = None
    cfg.tasks = []
    cfg.models = []
    cfg.get_phase_mode.return_value = 'New'
    cfg.get_models_by_role.return_value = []
    return cfg


def _mock_storage() -> MagicMock:
    """Mock ExperimentStorage that satisfies all attribute accesses."""
    storage = MagicMock()
    # log_path must support .parent / 'run_...log' chaining
    storage.log_path = MagicMock()
    storage.log_path.parent = MagicMock()
    storage.log_path.parent.__truediv__ = MagicMock(return_value=MagicMock())
    storage.run_path = MagicMock()
    storage.run_path.__truediv__ = MagicMock(return_value=MagicMock())
    storage.read_meta.return_value = {}
    return storage


def _blank_phase_runners() -> dict:
    """Return a dict mapping each phase ID to a no-op MagicMock."""
    return {pid: MagicMock() for pid in PHASE_IDS}


# Convenience: the run_experiment import and the module-level dicts to patch
_RUN_EXP = 'runner.runner.run_experiment'
_PHASE_RUNNERS_DICT = 'runner.runner._PHASE_RUNNERS'
_STORAGE_CLS = 'runner.runner.ExperimentStorage'
_LOGGER_CLS = 'runner.runner.RunLogger'


# ===========================================================================
# Dry-run mode
# ===========================================================================

class TestDryRun:
    """dry_run=True must return 0 and never call any phase runner."""

    def test_dry_run_returns_zero(self, tmp_path):
        from runner.runner import run_experiment

        cfg = _make_cfg(tmp_path)
        runners = _blank_phase_runners()

        with patch.dict(_PHASE_RUNNERS_DICT, runners), \
             patch(_STORAGE_CLS, return_value=_mock_storage()), \
             patch(_LOGGER_CLS, return_value=MagicMock()):
            result = run_experiment(cfg, dry_run=True, skip_probe=True)

        assert result == 0

    def test_dry_run_calls_no_phase_runners(self, tmp_path):
        from runner.runner import run_experiment

        cfg = _make_cfg(tmp_path)
        runners = _blank_phase_runners()

        with patch.dict(_PHASE_RUNNERS_DICT, runners), \
             patch(_STORAGE_CLS, return_value=_mock_storage()), \
             patch(_LOGGER_CLS, return_value=MagicMock()):
            run_experiment(cfg, dry_run=True, skip_probe=True)

        for pid, mock_fn in runners.items():
            mock_fn.assert_not_called(), f"Phase '{pid}' should not have run in dry_run"


# ===========================================================================
# Normal (non-dry) execution
# ===========================================================================

class TestNormalRun:
    """Full pipeline execution: phases run in order, exit codes correct."""

    def test_all_phases_called_in_phase_ids_order(self, tmp_path):
        """All 5 phases are called in the order defined by PHASE_IDS."""
        from runner.runner import run_experiment

        cfg = _make_cfg(tmp_path)
        call_order: list[str] = []
        runners: dict = {}
        for pid in PHASE_IDS:
            pid_copy = pid

            def _make_mock(p):
                m = MagicMock(side_effect=lambda *a, p=p, **kw: call_order.append(p))
                return m

            runners[pid_copy] = _make_mock(pid_copy)

        with patch.dict(_PHASE_RUNNERS_DICT, runners), \
             patch(_STORAGE_CLS, return_value=_mock_storage()), \
             patch(_LOGGER_CLS, return_value=MagicMock()):
            run_experiment(cfg, skip_probe=True)

        assert call_order == PHASE_IDS

    def test_successful_run_returns_zero(self, tmp_path):
        """When all phases succeed, run_experiment returns 0."""
        from runner.runner import run_experiment

        cfg = _make_cfg(tmp_path)
        runners = _blank_phase_runners()

        with patch.dict(_PHASE_RUNNERS_DICT, runners), \
             patch(_STORAGE_CLS, return_value=_mock_storage()), \
             patch(_LOGGER_CLS, return_value=MagicMock()):
            result = run_experiment(cfg, skip_probe=True)

        assert result == 0

    def test_all_phase_runners_receive_only_models(self, tmp_path):
        """The only_models argument is forwarded to every phase runner."""
        from runner.runner import run_experiment

        cfg = _make_cfg(tmp_path)
        runners = _blank_phase_runners()
        only = {'model_x', 'model_y'}

        with patch.dict(_PHASE_RUNNERS_DICT, runners), \
             patch(_STORAGE_CLS, return_value=_mock_storage()), \
             patch(_LOGGER_CLS, return_value=MagicMock()):
            run_experiment(cfg, skip_probe=True, only_models=only)

        for pid, mock_fn in runners.items():
            _, kwargs = mock_fn.call_args
            assert kwargs.get('only_models') == only, (
                f"Phase '{pid}' did not receive expected only_models"
            )


# ===========================================================================
# Failure modes
# ===========================================================================

class TestFailureModes:
    """Phase failures: pipeline stop vs. continue, exit codes."""

    def test_partial_phase_failure_pipeline_continues(self, tmp_path):
        """PartialPhaseFailure in a phase: subsequent phases still run."""
        from runner.runner import run_experiment

        cfg = _make_cfg(tmp_path)
        runners = _blank_phase_runners()

        # Make data_generation raise PartialPhaseFailure
        failing_phase = 'data_generation'
        runners[failing_phase].side_effect = PartialPhaseFailure(
            n_failures=1, n_successes=2, errors=['oops']
        )

        with patch.dict(_PHASE_RUNNERS_DICT, runners), \
             patch(_STORAGE_CLS, return_value=_mock_storage()), \
             patch(_LOGGER_CLS, return_value=MagicMock()):
            result = run_experiment(cfg, skip_probe=True)

        # exit_code should be 1 (partial failure)
        assert result == 1

        # Phases that come AFTER data_generation must still have been called
        after_phases = PHASE_IDS[PHASE_IDS.index(failing_phase) + 1:]
        for pid in after_phases:
            runners[pid].assert_called_once(), (
                f"Phase '{pid}' should have run after PartialPhaseFailure"
            )

    def test_runtime_error_stops_pipeline(self, tmp_path):
        """RuntimeError in a phase: the pipeline aborts; later phases do NOT run."""
        from runner.runner import run_experiment

        cfg = _make_cfg(tmp_path)
        runners = _blank_phase_runners()

        # Make rubric_mapping raise a plain RuntimeError (total failure)
        failing_phase = 'rubric_mapping'
        runners[failing_phase].side_effect = RuntimeError('Total phase failure')

        with patch.dict(_PHASE_RUNNERS_DICT, runners), \
             patch(_STORAGE_CLS, return_value=_mock_storage()), \
             patch(_LOGGER_CLS, return_value=MagicMock()):
            result = run_experiment(cfg, skip_probe=True)

        assert result == 1

        # Phases that come AFTER the failing phase must NOT have been called
        after_phases = PHASE_IDS[PHASE_IDS.index(failing_phase) + 1:]
        for pid in after_phases:
            runners[pid].assert_not_called(), (
                f"Phase '{pid}' should NOT run after RuntimeError in '{failing_phase}'"
            )

    def test_runtime_error_in_first_phase_stops_all_others(self, tmp_path):
        """RuntimeError in attribute_mapping prevents all downstream phases."""
        from runner.runner import run_experiment

        cfg = _make_cfg(tmp_path)
        runners = _blank_phase_runners()
        runners['attribute_mapping'].side_effect = RuntimeError('Phase 1 exploded')

        with patch.dict(_PHASE_RUNNERS_DICT, runners), \
             patch(_STORAGE_CLS, return_value=_mock_storage()), \
             patch(_LOGGER_CLS, return_value=MagicMock()):
            result = run_experiment(cfg, skip_probe=True)

        assert result == 1
        for pid in PHASE_IDS[1:]:
            runners[pid].assert_not_called()

    def test_partial_failure_sets_exit_code_but_not_fatal(self, tmp_path):
        """PartialPhaseFailure in EVERY phase: exit_code=1, all phases called."""
        from runner.runner import run_experiment

        cfg = _make_cfg(tmp_path)
        runners = {
            pid: MagicMock(
                side_effect=PartialPhaseFailure(n_failures=1, n_successes=1, errors=['e'])
            )
            for pid in PHASE_IDS
        }

        with patch.dict(_PHASE_RUNNERS_DICT, runners), \
             patch(_STORAGE_CLS, return_value=_mock_storage()), \
             patch(_LOGGER_CLS, return_value=MagicMock()):
            result = run_experiment(cfg, skip_probe=True)

        assert result == 1
        for pid in PHASE_IDS:
            runners[pid].assert_called_once()


# ===========================================================================
# continue_in_place mode
# ===========================================================================

class TestContinueInPlace:
    """continue_in_place=True: completed phases are skipped."""

    def test_completed_phases_skipped(self, tmp_path):
        """Phases already listed in meta.json are not run again."""
        from runner.runner import run_experiment

        cfg = _make_cfg(tmp_path)
        runners = _blank_phase_runners()

        # Simulate that the first 2 phases were completed in a previous run
        completed = PHASE_IDS[:2]
        mock_storage = _mock_storage()
        mock_storage.read_meta.return_value = {'phases_completed': completed}

        with patch.dict(_PHASE_RUNNERS_DICT, runners), \
             patch(_STORAGE_CLS, return_value=mock_storage), \
             patch(_LOGGER_CLS, return_value=MagicMock()):
            result = run_experiment(cfg, skip_probe=True, continue_in_place=True)

        assert result == 0
        for pid in completed:
            runners[pid].assert_not_called(), (
                f"Phase '{pid}' should have been skipped (already completed)"
            )
        for pid in PHASE_IDS[2:]:
            runners[pid].assert_called_once(), (
                f"Phase '{pid}' should have run (not yet completed)"
            )

    def test_all_phases_completed_returns_zero_without_any_runner_calls(self, tmp_path):
        """If all phases are done, the run returns 0 immediately with no calls."""
        from runner.runner import run_experiment

        cfg = _make_cfg(tmp_path)
        runners = _blank_phase_runners()

        mock_storage = _mock_storage()
        mock_storage.read_meta.return_value = {'phases_completed': list(PHASE_IDS)}

        with patch.dict(_PHASE_RUNNERS_DICT, runners), \
             patch(_STORAGE_CLS, return_value=mock_storage), \
             patch(_LOGGER_CLS, return_value=MagicMock()):
            result = run_experiment(cfg, skip_probe=True, continue_in_place=True)

        assert result == 0
        for pid in PHASE_IDS:
            runners[pid].assert_not_called()

    def test_continue_uses_extend_mode_for_phase3_to_5(self, tmp_path):
        """In continue mode phases 3-5 receive 'Extend' mode, phases 1-2 'Keep'."""
        from runner.runner import _CONTINUE_MODE
        from runner.runner import run_experiment

        cfg = _make_cfg(tmp_path)
        received_modes: dict[str, str] = {}

        def _record_mode(pid):
            def _runner(*args, **kwargs):
                # phase_mode is the 6th positional argument (index 5)
                received_modes[pid] = args[5]
            return _runner

        runners = {pid: MagicMock(side_effect=_record_mode(pid)) for pid in PHASE_IDS}

        with patch.dict(_PHASE_RUNNERS_DICT, runners), \
             patch(_STORAGE_CLS, return_value=_mock_storage()), \
             patch(_LOGGER_CLS, return_value=MagicMock()):
            run_experiment(cfg, skip_probe=True, continue_in_place=True)

        for pid in PHASE_IDS:
            assert received_modes[pid] == _CONTINUE_MODE[pid], (
                f"Phase '{pid}' got mode '{received_modes[pid]}' "
                f"but expected '{_CONTINUE_MODE[pid]}' in continue mode"
            )


# ===========================================================================
# only_models flag
# ===========================================================================

class TestOnlyModels:
    """only_models: phase_completed is NOT written to meta.json."""

    def test_phase_completed_not_written_when_only_models_set(self, tmp_path):
        """With only_models set, update_meta(phase_completed=...) is never called."""
        from runner.runner import run_experiment

        cfg = _make_cfg(tmp_path)
        runners = _blank_phase_runners()
        mock_storage = _mock_storage()

        with patch.dict(_PHASE_RUNNERS_DICT, runners), \
             patch(_STORAGE_CLS, return_value=mock_storage), \
             patch(_LOGGER_CLS, return_value=MagicMock()):
            run_experiment(cfg, skip_probe=True, only_models={'model_a'})

        # update_meta may be called for other things (phase_started) but
        # it must never receive phase_completed when only_models is set.
        for c in mock_storage.update_meta.call_args_list:
            kwargs = c.kwargs if c.kwargs else {}
            assert 'phase_completed' not in kwargs, (
                "update_meta(phase_completed=...) must not be called with only_models"
            )

    def test_phase_completed_written_without_only_models(self, tmp_path):
        """Without only_models, update_meta(phase_completed=...) IS called per phase."""
        from runner.runner import run_experiment

        cfg = _make_cfg(tmp_path)
        runners = _blank_phase_runners()
        mock_storage = _mock_storage()

        with patch.dict(_PHASE_RUNNERS_DICT, runners), \
             patch(_STORAGE_CLS, return_value=mock_storage), \
             patch(_LOGGER_CLS, return_value=MagicMock()):
            run_experiment(cfg, skip_probe=True)

        completed_calls = [
            c for c in mock_storage.update_meta.call_args_list
            if c.kwargs.get('phase_completed') is not None
        ]
        # One call per phase (5 phases)
        assert len(completed_calls) == len(PHASE_IDS)
