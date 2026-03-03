"""
Tests for Phase 1 (Attribute Mapping) and Phase 2 (Rubric Mapping).

Covers:
  Phase 1:
    - Keep mode: reuse existing artifact when file exists
    - Keep mode: fall through when file does not exist (static branch)
    - Static dict (target_attributes / nuanced_attributes is a dict): write
      directly without any LLM call
    - Auto mode: call all teachers, merge results, write artifact
    - Complete mode: merge new results with per-task seed values (seed wins)
    - Error accumulation: RuntimeError raised listing all task failures
    - Quota exhaustion: teacher skipped when its budget is depleted
    - only_models kwarg accepted without TypeError (bug-fix regression)

  Phase 2:
    - Keep mode: reuse existing rubric when file exists
    - Static dict (task.rubric is a dict): write directly without LLM call
    - Auto mode: call teachers, merge rubric factors, write rubric
    - Extend mode: load existing rubric as merge seed; existing factors win
    - Error accumulation: RuntimeError raised listing all task failures
    - Quota exhaustion: teacher skipped when its budget is depleted
    - only_models kwarg accepted without TypeError (bug-fix regression)

All tests use stub LLM interfaces and mock storage — no real filesystem I/O or
network calls are made.
"""
from __future__ import annotations

import json
from unittest.mock import MagicMock, call, patch

import pytest

from runner.phases.utils import QuotaTracker


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

class _FakeIface:
    """Stub ModelInterface that returns a fixed JSON-serialisable response."""

    def __init__(self, result: dict | None = None):
        self._result = result if result is not None else {}
        self.calls: list[str] = []

    def generate(self, prompt: str, parameters: dict) -> str:
        self.calls.append(prompt)
        return json.dumps(self._result)


class _ErrorIface:
    """Stub ModelInterface that always raises RuntimeError."""

    def generate(self, prompt: str, parameters: dict) -> str:
        raise RuntimeError('Simulated LLM failure')


def _make_logger() -> MagicMock:
    logger = MagicMock()
    logger.info = MagicMock()
    logger.warning = MagicMock()
    logger.error = MagicMock()
    return logger


def _make_teacher(name: str = 'teacher1') -> MagicMock:
    teacher = MagicMock()
    teacher.name = name
    teacher.get_parameters_for_role.return_value = {'model': 'gpt-4o'}
    return teacher


def _make_cfg(tasks: list, teachers: list) -> MagicMock:
    cfg = MagicMock()
    cfg.tasks = tasks
    cfg.get_models_by_role.side_effect = (
        lambda role: teachers if role == 'teacher' else []
    )
    return cfg


def _make_storage(
    target_exists: bool = False,
    nuanced_exists: bool = False,
    rubric_exists: bool = False,
    rubric_data: dict | None = None,
) -> MagicMock:
    storage = MagicMock()
    storage.target_attrs_exist.return_value = target_exists
    storage.nuanced_attrs_exist.return_value = nuanced_exists
    storage.rubric_exists.return_value = rubric_exists
    storage.read_rubric.return_value = rubric_data or {}
    return storage


def _make_pool(iface=None) -> MagicMock:
    pool = MagicMock()
    pool.get.return_value = iface or _FakeIface()
    return pool


def _make_task(
    name: str = 'task1',
    target_attributes='auto',
    nuanced_attributes='auto',
    rubric='auto',
    target_attributes_seed: dict | None = None,
    nuanced_attributes_seed: dict | None = None,
) -> MagicMock:
    task = MagicMock()
    task.name = name
    task.description = 'A test task.'
    task.output_description = 'A test output.'
    task.target_attributes = target_attributes
    task.nuanced_attributes = nuanced_attributes
    task.rubric = rubric
    task.target_attributes_seed = target_attributes_seed
    task.nuanced_attributes_seed = nuanced_attributes_seed
    task.prompt_library = {}
    return task


# Patch target for get_prompt so no real template loading is required
_P1_GET_PROMPT = 'runner.phases.phase1.get_prompt'
_P2_GET_PROMPT = 'runner.phases.phase2.get_prompt'
# Patch target for time.sleep inside call_llm_json (prevents retry delays)
_UTILS_SLEEP = 'runner.phases.utils.time.sleep'


# ===========================================================================
# Phase 1 — Attribute Mapping
# ===========================================================================

class TestPhase1KeepMode:
    """Phase 1 Keep mode: skip when artifact already exists."""

    def test_keep_mode_target_exists_no_write(self):
        """Keep mode: existing target_attrs file is reused; no write called."""
        from runner.phases.phase1 import run_phase1

        task = _make_task(target_attributes='auto', nuanced_attributes='auto')
        storage = _make_storage(target_exists=True, nuanced_exists=True)
        pool = _make_pool()
        logger = _make_logger()
        quota = QuotaTracker({})
        cfg = _make_cfg([task], [_make_teacher()])

        with patch(_P1_GET_PROMPT, return_value='prompt text'):
            run_phase1(cfg, storage, logger, pool, quota, phase_mode='Keep')

        storage.write_target_attrs.assert_not_called()
        storage.write_nuanced_attrs.assert_not_called()

    def test_keep_mode_target_not_exists_falls_through_to_static(self):
        """Keep mode: if artifact absent, static dict is written instead of skipped."""
        from runner.phases.phase1 import run_phase1

        task = _make_task(
            target_attributes={'quality': ['good', 'bad']},
            nuanced_attributes={'style': ['formal']},
        )
        # Files do not exist yet
        storage = _make_storage(target_exists=False, nuanced_exists=False)
        pool = _make_pool()
        logger = _make_logger()
        quota = QuotaTracker({})
        cfg = _make_cfg([task], [_make_teacher()])

        with patch(_P1_GET_PROMPT, return_value='prompt text'):
            run_phase1(cfg, storage, logger, pool, quota, phase_mode='Keep')

        # Static dict branch triggers a write even in Keep mode when file absent
        storage.write_target_attrs.assert_called_once()
        storage.write_nuanced_attrs.assert_called_once()


class TestPhase1StaticDict:
    """Phase 1 static-dict branch: write directly without LLM calls."""

    def test_static_target_attrs_written_directly(self):
        """When target_attributes is a dict, it is written without an LLM call."""
        from runner.phases.phase1 import run_phase1

        attrs = {'length': ['short', 'long'], 'tone': ['formal']}
        task = _make_task(target_attributes=attrs, nuanced_attributes='auto')
        storage = _make_storage()
        iface = _FakeIface()
        pool = _make_pool(iface)
        logger = _make_logger()
        quota = QuotaTracker({})
        cfg = _make_cfg([task], [_make_teacher()])

        with patch(_P1_GET_PROMPT, return_value='prompt text'):
            run_phase1(cfg, storage, logger, pool, quota, phase_mode='New')

        storage.write_target_attrs.assert_called_once_with(task.name, attrs)

    def test_static_nuanced_attrs_written_directly(self):
        """When nuanced_attributes is a dict, it is written without an LLM call."""
        from runner.phases.phase1 import run_phase1

        attrs = {'complexity': ['simple', 'complex']}
        task = _make_task(target_attributes='auto', nuanced_attributes=attrs)
        storage = _make_storage()
        iface = _FakeIface({'level': ['x']})  # for target auto call
        pool = _make_pool(iface)
        logger = _make_logger()
        quota = QuotaTracker({})
        cfg = _make_cfg([task], [_make_teacher()])

        with patch(_P1_GET_PROMPT, return_value='p'):
            run_phase1(cfg, storage, logger, pool, quota, phase_mode='New')

        storage.write_nuanced_attrs.assert_called_once_with(task.name, attrs)

    def test_static_dict_makes_no_llm_call(self):
        """Static dict branch: the pool.get() interface is never invoked."""
        from runner.phases.phase1 import run_phase1

        task = _make_task(
            target_attributes={'a': ['1']},
            nuanced_attributes={'b': ['2']},
        )
        storage = _make_storage()
        iface = _FakeIface()
        pool = _make_pool(iface)
        logger = _make_logger()
        quota = QuotaTracker({})
        cfg = _make_cfg([task], [_make_teacher()])

        with patch(_P1_GET_PROMPT, return_value='p'):
            run_phase1(cfg, storage, logger, pool, quota, phase_mode='New')

        assert len(iface.calls) == 0


class TestPhase1AutoMode:
    """Phase 1 auto / complete mode: LLM is called and results merged."""

    def test_auto_mode_calls_teacher_once_per_attr_kind(self):
        """Auto mode calls teacher once for target and once for nuanced."""
        from runner.phases.phase1 import run_phase1

        teacher = _make_teacher('t1')
        task = _make_task(target_attributes='auto', nuanced_attributes='auto')
        storage = _make_storage()
        iface = _FakeIface({'key': ['v1']})
        pool = _make_pool(iface)
        logger = _make_logger()
        quota = QuotaTracker({})
        cfg = _make_cfg([task], [teacher])

        with patch(_P1_GET_PROMPT, return_value='prompt'):
            run_phase1(cfg, storage, logger, pool, quota, phase_mode='New')

        # 2 calls: one for target, one for nuanced
        assert len(iface.calls) == 2
        storage.write_target_attrs.assert_called_once()
        storage.write_nuanced_attrs.assert_called_once()

    def test_auto_mode_multiple_teachers_all_called(self):
        """Auto mode calls each teacher once per attribute kind."""
        from runner.phases.phase1 import run_phase1

        teacher_a = _make_teacher('tA')
        teacher_b = _make_teacher('tB')
        task = _make_task(target_attributes='auto', nuanced_attributes='auto')
        storage = _make_storage()

        calls_per_iface: dict[str, list] = {'tA': [], 'tB': []}

        class _TrackingPool:
            def get(self, model_cfg):
                name = model_cfg.name

                class _Iface:
                    def generate(self, prompt, params):
                        calls_per_iface[name].append(prompt)
                        return json.dumps({'k': ['v']})

                return _Iface()

        logger = _make_logger()
        quota = QuotaTracker({})
        cfg = _make_cfg([task], [teacher_a, teacher_b])

        with patch(_P1_GET_PROMPT, return_value='p'):
            run_phase1(cfg, storage, logger, _TrackingPool(), quota, phase_mode='New')

        assert len(calls_per_iface['tA']) == 2  # target + nuanced
        assert len(calls_per_iface['tB']) == 2

    def test_auto_mode_merges_teacher_results(self):
        """merge_attr_maps is used: all values from all teachers appear in output."""
        from runner.phases.phase1 import run_phase1

        teacher_a = _make_teacher('tA')
        teacher_b = _make_teacher('tB')
        task = _make_task(
            target_attributes='auto',
            nuanced_attributes={'dummy': ['x']},  # nuanced static to isolate target
        )
        storage = _make_storage()

        call_n = [0]

        class _TwoResultPool:
            def get(self, model_cfg):
                n = model_cfg.name

                class _Iface:
                    def generate(self, prompt, params):
                        call_n[0] += 1
                        # First teacher returns 'a', second returns 'b'
                        val = 'a' if n == 'tA' else 'b'
                        return json.dumps({'quality': [val]})

                return _Iface()

        written: list[dict] = []
        storage.write_target_attrs.side_effect = lambda tid, v: written.append(v)
        logger = _make_logger()
        quota = QuotaTracker({})
        cfg = _make_cfg([task], [teacher_a, teacher_b])

        with patch(_P1_GET_PROMPT, return_value='p'):
            run_phase1(cfg, storage, logger, _TwoResultPool(), quota, phase_mode='New')

        assert len(written) == 1
        # Both values should appear in the merged map
        merged_values = written[0].get('quality', [])
        assert 'a' in merged_values
        assert 'b' in merged_values

    def test_complete_mode_seed_values_preserved(self):
        """Complete mode: seed dict is included in merge; seed keys win dedup."""
        from runner.phases.phase1 import run_phase1

        seed = {'quality': ['seed_val']}
        task = _make_task(
            target_attributes='complete',
            nuanced_attributes={'dummy': ['x']},
            target_attributes_seed=seed,
        )
        storage = _make_storage()

        written: list[dict] = []
        storage.write_target_attrs.side_effect = lambda tid, v: written.append(v)

        # Teacher returns a different value for the same key
        iface = _FakeIface({'quality': ['teacher_val']})
        pool = _make_pool(iface)
        logger = _make_logger()
        quota = QuotaTracker({})
        cfg = _make_cfg([task], [_make_teacher()])

        with patch(_P1_GET_PROMPT, return_value='p'):
            run_phase1(cfg, storage, logger, pool, quota, phase_mode='New')

        assert len(written) == 1
        merged = written[0]
        # Both seed and teacher values must appear; merge_attr_maps is a union
        assert 'seed_val' in merged.get('quality', [])
        assert 'teacher_val' in merged.get('quality', [])


class TestPhase1Errors:
    """Phase 1 error handling and quota enforcement."""

    def test_error_in_task_raises_runtime_error(self):
        """When _resolve_attrs raises, run_phase1 accumulates and re-raises RuntimeError."""
        from runner.phases.phase1 import run_phase1

        # Force pool.get to raise on LLM call so _resolve_attrs propagates
        task = _make_task(target_attributes='auto', nuanced_attributes='auto')
        storage = _make_storage()
        pool = _make_pool(_ErrorIface())
        logger = _make_logger()
        quota = QuotaTracker({})
        cfg = _make_cfg([task], [_make_teacher()])

        with patch(_P1_GET_PROMPT, return_value='p'), \
             patch(_UTILS_SLEEP):
            with pytest.raises(RuntimeError) as exc_info:
                run_phase1(cfg, storage, logger, pool, quota, phase_mode='New')

        assert 'error' in str(exc_info.value).lower()

    def test_all_task_errors_accumulated(self):
        """Multiple task failures are all listed in the RuntimeError message.

        Phase 1 generates two errors per failing task (target_attrs + nuanced_attrs),
        so two failing tasks produce 4 error entries total.
        """
        from runner.phases.phase1 import run_phase1

        task_a = _make_task('tA', target_attributes='auto', nuanced_attributes='auto')
        task_b = _make_task('tB', target_attributes='auto', nuanced_attributes='auto')
        storage = _make_storage()
        pool = _make_pool(_ErrorIface())
        logger = _make_logger()
        quota = QuotaTracker({})
        cfg = _make_cfg([task_a, task_b], [_make_teacher()])

        with patch(_P1_GET_PROMPT, return_value='p'), \
             patch(_UTILS_SLEEP):
            with pytest.raises(RuntimeError) as exc_info:
                run_phase1(cfg, storage, logger, pool, quota, phase_mode='New')

        msg = str(exc_info.value)
        # Both task names should appear in the accumulated error message
        assert 'tA' in msg
        assert 'tB' in msg

    def test_quota_exhausted_teacher_is_skipped(self):
        """A teacher whose quota is exhausted is not called."""
        from runner.phases.phase1 import run_phase1

        teacher = _make_teacher('t1')
        task = _make_task(target_attributes='auto', nuanced_attributes='auto')
        storage = _make_storage()
        iface = _FakeIface({'k': ['v']})
        pool = _make_pool(iface)
        logger = _make_logger()
        # Exhaust the quota immediately
        quota = QuotaTracker({'t1': {'max_calls': 0}})
        cfg = _make_cfg([task], [teacher])

        with patch(_P1_GET_PROMPT, return_value='p'):
            run_phase1(cfg, storage, logger, pool, quota, phase_mode='New')

        assert len(iface.calls) == 0

    def test_only_models_kwarg_accepted(self):
        """Passing only_models=... must not raise TypeError (regression for bug fix)."""
        from runner.phases.phase1 import run_phase1

        task = _make_task(
            target_attributes={'a': ['1']},
            nuanced_attributes={'b': ['2']},
        )
        storage = _make_storage()
        pool = _make_pool()
        logger = _make_logger()
        quota = QuotaTracker({})
        cfg = _make_cfg([task], [_make_teacher()])

        # Should not raise TypeError
        with patch(_P1_GET_PROMPT, return_value='p'):
            run_phase1(
                cfg, storage, logger, pool, quota,
                phase_mode='New', only_models={'some_model'},
            )


# ===========================================================================
# Phase 2 — Rubric Mapping
# ===========================================================================

class TestPhase2KeepMode:
    """Phase 2 Keep mode: skip when rubric already exists."""

    def test_keep_mode_rubric_exists_no_write(self):
        """Keep mode: existing rubric file is reused; no write called."""
        from runner.phases.phase2 import run_phase2

        task = _make_task(rubric='auto')
        storage = _make_storage(rubric_exists=True)
        iface = _FakeIface({'accuracy': 'Is it correct?'})
        pool = _make_pool(iface)
        logger = _make_logger()
        quota = QuotaTracker({})
        cfg = _make_cfg([task], [_make_teacher()])

        with patch(_P2_GET_PROMPT, return_value='p'):
            run_phase2(cfg, storage, logger, pool, quota, phase_mode='Keep')

        storage.write_rubric.assert_not_called()
        assert len(iface.calls) == 0

    def test_keep_mode_rubric_not_exists_falls_through_to_static(self):
        """Keep mode: if rubric absent, static dict branch is still triggered."""
        from runner.phases.phase2 import run_phase2

        rubric = {'accuracy': 'Is it correct?'}
        task = _make_task(rubric=rubric)
        storage = _make_storage(rubric_exists=False)
        pool = _make_pool()
        logger = _make_logger()
        quota = QuotaTracker({})
        cfg = _make_cfg([task], [_make_teacher()])

        with patch(_P2_GET_PROMPT, return_value='p'):
            run_phase2(cfg, storage, logger, pool, quota, phase_mode='Keep')

        storage.write_rubric.assert_called_once_with(task.name, rubric)


class TestPhase2StaticDict:
    """Phase 2 static-dict branch: write directly without LLM calls."""

    def test_static_rubric_written_directly(self):
        """When rubric is a dict, it is written without an LLM call."""
        from runner.phases.phase2 import run_phase2

        rubric = {'accuracy': 'Is it correct?', 'clarity': 'Is it clear?'}
        task = _make_task(rubric=rubric)
        storage = _make_storage()
        iface = _FakeIface()
        pool = _make_pool(iface)
        logger = _make_logger()
        quota = QuotaTracker({})
        cfg = _make_cfg([task], [_make_teacher()])

        with patch(_P2_GET_PROMPT, return_value='p'):
            run_phase2(cfg, storage, logger, pool, quota, phase_mode='New')

        storage.write_rubric.assert_called_once_with(task.name, rubric)
        assert len(iface.calls) == 0


class TestPhase2AutoMode:
    """Phase 2 auto mode: LLM is called and results merged."""

    def test_auto_mode_calls_teacher_and_writes_rubric(self):
        """Auto mode: each teacher is called once; merged rubric written."""
        from runner.phases.phase2 import run_phase2

        teacher = _make_teacher('t1')
        task = _make_task(rubric='auto')
        storage = _make_storage()
        iface = _FakeIface({'accuracy': 'Is it correct?'})
        pool = _make_pool(iface)
        logger = _make_logger()
        quota = QuotaTracker({})
        cfg = _make_cfg([task], [teacher])

        with patch(_P2_GET_PROMPT, return_value='p'):
            run_phase2(cfg, storage, logger, pool, quota, phase_mode='New')

        assert len(iface.calls) == 1
        storage.write_rubric.assert_called_once()

    def test_auto_mode_multiple_teachers_merged(self):
        """Factors from all teachers appear in the written rubric (union)."""
        from runner.phases.phase2 import run_phase2

        teacher_a = _make_teacher('tA')
        teacher_b = _make_teacher('tB')
        task = _make_task(rubric='auto')
        storage = _make_storage()

        written: list[dict] = []
        storage.write_rubric.side_effect = lambda tid, v: written.append(v)

        class _RubricPool:
            def get(self, model_cfg):
                n = model_cfg.name

                class _Iface:
                    def generate(self, prompt, params):
                        factor = 'accuracy' if n == 'tA' else 'clarity'
                        return json.dumps({factor: f'desc from {n}'})

                return _Iface()

        logger = _make_logger()
        quota = QuotaTracker({})
        cfg = _make_cfg([task], [teacher_a, teacher_b])

        with patch(_P2_GET_PROMPT, return_value='p'):
            run_phase2(cfg, storage, logger, _RubricPool(), quota, phase_mode='New')

        assert len(written) == 1
        merged = written[0]
        assert 'accuracy' in merged
        assert 'clarity' in merged

    def test_extend_mode_loads_existing_rubric_as_seed(self):
        """Extend mode: existing rubric factors take precedence over new teacher output."""
        from runner.phases.phase2 import run_phase2

        existing = {'accuracy': 'Original description'}
        task = _make_task(rubric='extend')
        storage = _make_storage(rubric_exists=True, rubric_data=existing)

        written: list[dict] = []
        storage.write_rubric.side_effect = lambda tid, v: written.append(v)

        # Teacher also returns 'accuracy' with a different description
        iface = _FakeIface({'accuracy': 'Teacher description', 'clarity': 'New factor'})
        pool = _make_pool(iface)
        logger = _make_logger()
        quota = QuotaTracker({})
        cfg = _make_cfg([task], [_make_teacher()])

        with patch(_P2_GET_PROMPT, return_value='p'):
            run_phase2(cfg, storage, logger, pool, quota, phase_mode='New')

        assert len(written) == 1
        merged = written[0]
        # Existing rubric is first in merge sources → its description wins
        assert merged['accuracy'] == 'Original description'
        # New factor from teacher should also appear
        assert 'clarity' in merged

    def test_extend_mode_no_existing_rubric_just_uses_teacher(self):
        """Extend mode with no prior rubric: teacher's result is used directly."""
        from runner.phases.phase2 import run_phase2

        task = _make_task(rubric='extend')
        # rubric_exists=False → existing_rubric stays {}
        storage = _make_storage(rubric_exists=False, rubric_data={})

        written: list[dict] = []
        storage.write_rubric.side_effect = lambda tid, v: written.append(v)

        iface = _FakeIface({'fluency': 'Is it fluent?'})
        pool = _make_pool(iface)
        logger = _make_logger()
        quota = QuotaTracker({})
        cfg = _make_cfg([task], [_make_teacher()])

        with patch(_P2_GET_PROMPT, return_value='p'):
            run_phase2(cfg, storage, logger, pool, quota, phase_mode='New')

        assert len(written) == 1
        assert 'fluency' in written[0]


class TestPhase2Errors:
    """Phase 2 error handling and quota enforcement."""

    def test_error_in_task_raises_runtime_error(self):
        """When a teacher call fails, run_phase2 accumulates and re-raises RuntimeError."""
        from runner.phases.phase2 import run_phase2

        task = _make_task(rubric='auto')
        storage = _make_storage()
        pool = _make_pool(_ErrorIface())
        logger = _make_logger()
        quota = QuotaTracker({})
        cfg = _make_cfg([task], [_make_teacher()])

        with patch(_P2_GET_PROMPT, return_value='p'), \
             patch(_UTILS_SLEEP):
            with pytest.raises(RuntimeError) as exc_info:
                run_phase2(cfg, storage, logger, pool, quota, phase_mode='New')

        assert 'error' in str(exc_info.value).lower()

    def test_multiple_task_errors_accumulated(self):
        """Errors from multiple tasks are all listed in the raised RuntimeError."""
        from runner.phases.phase2 import run_phase2

        task_a = _make_task('tA', rubric='auto')
        task_b = _make_task('tB', rubric='auto')
        storage = _make_storage()
        pool = _make_pool(_ErrorIface())
        logger = _make_logger()
        quota = QuotaTracker({})
        cfg = _make_cfg([task_a, task_b], [_make_teacher()])

        with patch(_P2_GET_PROMPT, return_value='p'), \
             patch(_UTILS_SLEEP):
            with pytest.raises(RuntimeError) as exc_info:
                run_phase2(cfg, storage, logger, pool, quota, phase_mode='New')

        msg = str(exc_info.value)
        assert '2' in msg

    def test_quota_exhausted_teacher_skipped(self):
        """A teacher whose quota is depleted is not called for Phase 2."""
        from runner.phases.phase2 import run_phase2

        teacher = _make_teacher('t1')
        task = _make_task(rubric='auto')
        storage = _make_storage()
        iface = _FakeIface({'acc': 'desc'})
        pool = _make_pool(iface)
        logger = _make_logger()
        quota = QuotaTracker({'t1': {'max_calls': 0}})
        cfg = _make_cfg([task], [teacher])

        with patch(_P2_GET_PROMPT, return_value='p'):
            run_phase2(cfg, storage, logger, pool, quota, phase_mode='New')

        assert len(iface.calls) == 0

    def test_only_models_kwarg_accepted(self):
        """Passing only_models=... must not raise TypeError (regression for bug fix)."""
        from runner.phases.phase2 import run_phase2

        task = _make_task(rubric={'acc': 'desc'})
        storage = _make_storage()
        pool = _make_pool()
        logger = _make_logger()
        quota = QuotaTracker({})
        cfg = _make_cfg([task], [_make_teacher()])

        with patch(_P2_GET_PROMPT, return_value='p'):
            run_phase2(
                cfg, storage, logger, pool, quota,
                phase_mode='New', only_models={'some_model'},
            )
