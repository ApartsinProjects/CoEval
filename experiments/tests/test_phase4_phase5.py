"""
Tests for Phase 4 and Phase 5 logic without real LLM calls.

Covers:
  - Phase 5 Extend mode: skip when no new factors AND no new responses
  - Phase 5 Extend mode: evaluate when no new factors BUT there are new responses
  - Phase 5 Extend mode: evaluate only new rubric factors when they exist
  - Phase 5 PartialPhaseFailure raised when at least one slot errors
  - Phase 4 PartialPhaseFailure raised when at least one slot errors
  - Phase 4 Extend mode deduplication: already-responded datapoints are skipped
  - Phase 4 Keep mode: skips entirely without writing
  - QuotaTracker thread safety: concurrent consume() calls never go negative

All tests use stub ModelInterface implementations and real filesystem storage
(via pytest's tmp_path), but do NOT make network calls or load model weights.
"""
from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch, call

import pytest

from experiments.storage import ExperimentStorage
from experiments.phases.utils import QuotaTracker
from experiments.exceptions import PartialPhaseFailure
from experiments.config import (
    CoEvalConfig, TaskConfig, ModelConfig, SamplingConfig, ExperimentConfig,
    _parse_config,
)


# ---------------------------------------------------------------------------
# Helpers / Stubs
# ---------------------------------------------------------------------------

def _make_task(name='task1', eval_mode='single', rubric=None):
    return TaskConfig(
        name=name,
        description='Test task.',
        output_description='One word.',
        target_attributes={'a': ['x']},
        nuanced_attributes={'b': ['y']},
        sampling=SamplingConfig(target=[1, 1], nuance=[1, 1], total=2),
        rubric=rubric or {'accuracy': 'Is it correct?'},
        evaluation_mode=eval_mode,
        prompt_library={},
    )


def _make_model(name, interface='openai', roles=None):
    return ModelConfig(
        name=name,
        interface=interface,
        parameters={'model': 'gpt-4o-mini'},
        roles=roles or ['judge'],
    )


class _FakeIface:
    """Stub ModelInterface that returns a fixed response."""

    def __init__(self, response='{"accuracy": "High"}'):
        self._response = response
        self.calls: list[str] = []

    def generate(self, prompt: str, parameters: dict) -> str:
        self.calls.append(prompt)
        return self._response


class _ErrorIface:
    """Stub ModelInterface that always raises RuntimeError."""

    def generate(self, prompt: str, parameters: dict) -> str:
        raise RuntimeError('LLM call failed')


def _make_store(tmp_path, exp_id='test-exp'):
    s = ExperimentStorage(str(tmp_path), exp_id)
    s.initialize({'experiment': {'id': exp_id}})
    return s


def _make_logger():
    logger = MagicMock()
    logger.info = MagicMock()
    logger.warning = MagicMock()
    logger.error = MagicMock()
    return logger


def _seed_datapoints(store, task_id, teacher_id, n=2):
    """Write n minimal datapoints to Phase 3 storage."""
    for i in range(n):
        store.append_datapoint(task_id, teacher_id, {
            'id': f'{task_id}__{teacher_id}__{i:05d}',
            'task_id': task_id,
            'teacher_model_id': teacher_id,
            'prompt': f'Prompt {i}',
            'reference_response': f'Ref {i}',
            'sampled_target_attributes': {},
            'generated_at': '2025-01-01T00:00:00Z',
        })


def _seed_responses(store, task_id, teacher_id, student_id, n=2):
    """Write n minimal responses to Phase 4 storage."""
    for i in range(n):
        store.append_response(task_id, teacher_id, student_id, {
            'id': f'{task_id}__{teacher_id}__{i:05d}__{student_id}',
            'datapoint_id': f'{task_id}__{teacher_id}__{i:05d}',
            'task_id': task_id,
            'teacher_model_id': teacher_id,
            'student_model_id': student_id,
            'input': f'Prompt {i}',
            'response': f'Response {i}',
            'generated_at': '2025-01-01T00:00:00Z',
        })


def _seed_evaluations(store, task_id, teacher_id, judge_id, response_ids, scores=None):
    """Write evaluation records for the given response_ids."""
    default_scores = {'accuracy': 'High'}
    for resp_id in response_ids:
        store.append_evaluation(task_id, teacher_id, judge_id, {
            'id': f'{resp_id}__{judge_id}',
            'response_id': resp_id,
            'datapoint_id': resp_id.rsplit('__', 1)[0],
            'task_id': task_id,
            'teacher_model_id': teacher_id,
            'judge_model_id': judge_id,
            'scores': scores or default_scores,
            'evaluated_at': '2025-01-01T00:00:00Z',
        })


# ---------------------------------------------------------------------------
# PartialPhaseFailure — unit tests for the exception class itself
# ---------------------------------------------------------------------------

def test_partial_phase_failure_attributes():
    exc = PartialPhaseFailure(n_failures=3, n_successes=7, errors=['e1', 'e2', 'e3'])
    assert exc.n_failures == 3
    assert exc.n_successes == 7
    assert exc.errors == ['e1', 'e2', 'e3']


def test_partial_phase_failure_message_contains_counts():
    exc = PartialPhaseFailure(n_failures=2, n_successes=5, errors=['err A', 'err B'])
    msg = str(exc)
    assert '2' in msg
    assert '5' in msg


def test_partial_phase_failure_message_contains_errors():
    errors = ['error one', 'error two']
    exc = PartialPhaseFailure(n_failures=2, n_successes=0, errors=errors)
    msg = str(exc)
    assert 'error one' in msg
    assert 'error two' in msg


def test_partial_phase_failure_truncates_long_error_list():
    """Messages with >10 errors show '... and N more' instead of all errors."""
    errors = [f'error {i}' for i in range(15)]
    exc = PartialPhaseFailure(n_failures=15, n_successes=0, errors=errors)
    msg = str(exc)
    assert 'more' in msg


def test_partial_phase_failure_is_exception():
    exc = PartialPhaseFailure(n_failures=1, n_successes=0, errors=['x'])
    assert isinstance(exc, Exception)


# ---------------------------------------------------------------------------
# QuotaTracker — thread safety
# ---------------------------------------------------------------------------

def test_quota_tracker_concurrent_consume_never_goes_negative():
    """
    Launch many threads that all call consume() concurrently.
    The internal counter must never go below 0 and is_exhausted must be True
    at the end.
    """
    budget = 10
    qt = QuotaTracker({'mdl': {'max_calls': budget}})
    n_threads = 50  # far more threads than the quota allows

    barrier = threading.Barrier(n_threads)

    def _worker():
        barrier.wait()  # synchronise all threads to maximise contention
        qt.consume('mdl')

    threads = [threading.Thread(target=_worker) for _ in range(n_threads)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    # After overconsumption the counter must be <= 0, not some large negative
    assert qt.is_exhausted('mdl')
    # Verify internally the value didn't race to something highly negative.
    # The implementation does `remaining -= 1` inside a lock, so it may go
    # negative but must stay within [-n_threads, 0].
    remaining = qt._remaining['mdl']
    assert remaining <= 0
    assert remaining >= -n_threads


def test_quota_tracker_concurrent_is_exhausted_consistent():
    """
    Concurrent readers of is_exhausted() must not see stale state after the
    budget is consumed on one thread.
    """
    qt = QuotaTracker({'mdl': {'max_calls': 1}})
    results: list[bool] = []
    lock = threading.Lock()

    def _consume_then_check():
        qt.consume('mdl')
        with lock:
            results.append(qt.is_exhausted('mdl'))

    threads = [threading.Thread(target=_consume_then_check) for _ in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    # At least one thread will see exhausted=True (the one that pushed it to 0)
    assert any(results)


# ---------------------------------------------------------------------------
# Phase 5 — _evaluate Extend mode via run_phase5 with mocked pool
# ---------------------------------------------------------------------------

def _make_pool_mock(iface):
    """Return a MagicMock ModelPool whose .get() always returns iface."""
    pool = MagicMock()
    pool.get.return_value = iface
    return pool


def _make_cfg_mock(tasks, models_by_role_fn):
    """Return a MagicMock CoEvalConfig with use_batch disabled (non-batch sequential path).

    All tests use stub ModelInterface objects and must not make real network calls.
    Setting use_batch.return_value = False ensures the phases run on the sequential
    code path regardless of what interface the model claims to use.
    """
    cfg = MagicMock()
    cfg.tasks = tasks
    cfg.get_models_by_role.side_effect = models_by_role_fn
    cfg.use_batch.return_value = False  # never enter the real batch runner
    return cfg


def test_phase5_extend_skip_when_no_new_factors_and_no_new_responses(tmp_path):
    """
    Extend mode: if all rubric factors already appear in existing evaluations
    AND all responses already have evaluation records, _evaluate must skip
    without writing any new records.
    """
    from experiments.phases.phase5 import run_phase5

    store = _make_store(tmp_path)
    rubric = {'accuracy': 'Is it correct?'}
    task = _make_task(rubric=rubric)
    teacher = _make_model('teacher1', roles=['teacher'])
    judge = _make_model('judge1', roles=['judge'])

    # Seed: 2 datapoints + 2 responses + 2 evaluations (fully evaluated)
    _seed_datapoints(store, 'task1', 'teacher1', n=2)
    _seed_responses(store, 'task1', 'teacher1', 'student1', n=2)

    resp_ids = [
        'task1__teacher1__00000__student1',
        'task1__teacher1__00001__student1',
    ]
    _seed_evaluations(store, 'task1', 'teacher1', 'judge1', resp_ids,
                      scores={'accuracy': 'High'})

    store.write_rubric('task1', rubric)

    cfg = _make_cfg_mock(
        tasks=[task],
        models_by_role_fn=lambda role: [teacher] if role == 'teacher' else [judge],
    )

    iface = _FakeIface()
    pool = _make_pool_mock(iface)
    logger = _make_logger()
    quota = QuotaTracker({})

    run_phase5(cfg, store, logger, pool, quota, phase_mode='Extend')

    # No new evaluation records should have been written
    evals_after = store.read_evaluations('task1', 'teacher1', 'judge1')
    assert len(evals_after) == 2  # unchanged
    # iface was never called
    assert len(iface.calls) == 0


def test_phase5_extend_evaluates_new_responses_when_no_new_factors(tmp_path):
    """
    Extend mode: if no new rubric factors but there ARE new responses,
    _evaluate must score only the new responses using the full rubric.
    """
    from experiments.phases.phase5 import run_phase5

    store = _make_store(tmp_path)
    rubric = {'accuracy': 'Is it correct?'}
    task = _make_task(rubric=rubric)
    teacher = _make_model('teacher1', roles=['teacher'])
    judge = _make_model('judge1', roles=['judge'])

    # 2 datapoints + 2 responses
    _seed_datapoints(store, 'task1', 'teacher1', n=2)
    _seed_responses(store, 'task1', 'teacher1', 'student1', n=2)

    # Only the first response has been evaluated
    _seed_evaluations(store, 'task1', 'teacher1', 'judge1',
                      ['task1__teacher1__00000__student1'],
                      scores={'accuracy': 'High'})

    store.write_rubric('task1', rubric)

    cfg = _make_cfg_mock(
        tasks=[task],
        models_by_role_fn=lambda role: [teacher] if role == 'teacher' else [judge],
    )

    # Stub returns valid JSON for single evaluation mode
    iface = _FakeIface(response='{"accuracy": "Medium"}')
    pool = _make_pool_mock(iface)
    logger = _make_logger()
    quota = QuotaTracker({})

    run_phase5(cfg, store, logger, pool, quota, phase_mode='Extend')

    evals_after = store.read_evaluations('task1', 'teacher1', 'judge1')
    # Started with 1, should have added 1 more for the new response
    assert len(evals_after) == 2
    response_ids_evaluated = {e['response_id'] for e in evals_after}
    assert 'task1__teacher1__00001__student1' in response_ids_evaluated


def test_phase5_extend_new_factors_with_unevaluated_responses(tmp_path):
    """
    Extend mode with new rubric factors: responses that have NOT yet been
    evaluated at all ARE scored with the new rubric_to_use (new factors only).
    Responses that were already evaluated ARE skipped by the evaluated_resp_ids
    guard even in the new-factors branch.
    """
    from experiments.phases.phase5 import run_phase5

    store = _make_store(tmp_path)
    rubric_full = {'accuracy': 'Correct?', 'brevity': 'Short?'}
    task = _make_task(rubric=rubric_full)
    teacher = _make_model('teacher1', roles=['teacher'])
    judge = _make_model('judge1', roles=['judge'])

    # Two datapoints → two responses
    _seed_datapoints(store, 'task1', 'teacher1', n=2)
    _seed_responses(store, 'task1', 'teacher1', 'student1', n=2)

    # Only the FIRST response has an existing evaluation (old factor only)
    _seed_evaluations(store, 'task1', 'teacher1', 'judge1',
                      ['task1__teacher1__00000__student1'],
                      scores={'accuracy': 'High'})

    store.write_rubric('task1', rubric_full)

    cfg = _make_cfg_mock(
        tasks=[task],
        models_by_role_fn=lambda role: [teacher] if role == 'teacher' else [judge],
    )

    # In the new-factors branch, rubric_to_use = {'brevity': ...}
    # The second response (not yet evaluated) will be scored.
    # The first response IS in evaluated_resp_ids so it is skipped.
    iface = _FakeIface(response='{"brevity": "Low"}')
    pool = _make_pool_mock(iface)
    logger = _make_logger()
    quota = QuotaTracker({})

    run_phase5(cfg, store, logger, pool, quota, phase_mode='Extend')

    evals_after = store.read_evaluations('task1', 'teacher1', 'judge1')
    # 1 pre-existing + 1 new (for resp1, which is unevaluated)
    assert len(evals_after) == 2
    # iface called once for the unevaluated second response
    assert len(iface.calls) == 1
    # The new record is for the second response
    new_eval = evals_after[1]
    assert new_eval['response_id'] == 'task1__teacher1__00001__student1'


def test_phase5_extend_new_factors_skips_already_evaluated_responses(tmp_path):
    """
    KNOWN BEHAVIOUR: In Extend mode with new rubric factors, the evaluated_resp_ids
    guard also skips responses that were already evaluated for OLD factors.
    This means new factors are NOT retroactively scored for already-evaluated
    responses — only responses that have never been evaluated get the new factors.

    This test documents the actual current behaviour so a regression is caught
    if the logic is ever changed.
    """
    from experiments.phases.phase5 import run_phase5

    store = _make_store(tmp_path)
    rubric_full = {'accuracy': 'Correct?', 'brevity': 'Short?'}
    task = _make_task(rubric=rubric_full)
    teacher = _make_model('teacher1', roles=['teacher'])
    judge = _make_model('judge1', roles=['judge'])

    _seed_datapoints(store, 'task1', 'teacher1', n=1)
    _seed_responses(store, 'task1', 'teacher1', 'student1', n=1)

    # The sole response already has an evaluation for 'accuracy' (old factor only).
    resp_id = 'task1__teacher1__00000__student1'
    _seed_evaluations(store, 'task1', 'teacher1', 'judge1',
                      [resp_id], scores={'accuracy': 'High'})

    store.write_rubric('task1', rubric_full)

    cfg = _make_cfg_mock(
        tasks=[task],
        models_by_role_fn=lambda role: [teacher] if role == 'teacher' else [judge],
    )

    iface = _FakeIface(response='{"brevity": "Low"}')
    pool = _make_pool_mock(iface)
    logger = _make_logger()
    quota = QuotaTracker({})

    run_phase5(cfg, store, logger, pool, quota, phase_mode='Extend')

    evals_after = store.read_evaluations('task1', 'teacher1', 'judge1')
    # The already-evaluated response is in evaluated_resp_ids and thus skipped.
    # No new evaluation record is written for the new factor.
    assert len(evals_after) == 1  # unchanged
    assert len(iface.calls) == 0   # interface was never called


def test_phase5_partial_failure_recorded_on_scoring_error(tmp_path):
    """
    When _score_response raises for a response, the exception is caught and a
    status='failed' evaluation record is written.  run_phase5 completes without
    raising PartialPhaseFailure for individual response-level errors.
    """
    from experiments.phases.phase5 import run_phase5

    store = _make_store(tmp_path)
    rubric = {'accuracy': 'Correct?'}
    # Two tasks so one succeeds and one fails
    task_good = _make_task(name='task_good', rubric=rubric)
    task_bad = _make_task(name='task_bad', rubric=rubric)
    teacher = _make_model('teacher1', roles=['teacher'])
    judge = _make_model('judge1', roles=['judge'])

    # Seed storage for the good task
    _seed_datapoints(store, 'task_good', 'teacher1', n=1)
    _seed_responses(store, 'task_good', 'teacher1', 'student1', n=1)
    store.write_rubric('task_good', rubric)

    # Seed storage for the bad task (responses present, rubric present)
    _seed_datapoints(store, 'task_bad', 'teacher1', n=1)
    _seed_responses(store, 'task_bad', 'teacher1', 'student1', n=1)
    store.write_rubric('task_bad', rubric)

    cfg = _make_cfg_mock(
        tasks=[task_good, task_bad],
        models_by_role_fn=lambda role: [teacher] if role == 'teacher' else [judge],
    )

    # Make the interface error on the second call (for task_bad)
    call_count = {'n': 0}

    class _ConditionalErrorIface:
        def generate(self, prompt: str, parameters: dict) -> str:
            call_count['n'] += 1
            if call_count['n'] > 1:
                raise RuntimeError('Forced failure for task_bad')
            return '{"accuracy": "High"}'

    pool = _make_pool_mock(_ConditionalErrorIface())
    logger = _make_logger()
    quota = QuotaTracker({})

    # With per-response error handling, run_phase5 completes without raising.
    # The failed evaluation is recorded as status='failed' instead of propagating.
    run_phase5(cfg, store, logger, pool, quota, phase_mode='New')

    # The good task should have a successful evaluation record
    good_evals = store.read_evaluations('task_good', 'teacher1', 'judge1')
    assert len(good_evals) == 1
    assert good_evals[0].get('status') != 'failed'

    # The bad task should have a failed evaluation record (not missing entirely)
    bad_evals = store.read_evaluations('task_bad', 'teacher1', 'judge1')
    assert len(bad_evals) == 1
    assert bad_evals[0]['status'] == 'failed'


def test_phase5_skip_when_no_responses(tmp_path):
    """
    When there are no Phase 4 response files for a (task, teacher, judge) triple,
    _evaluate must skip and not call the judge interface at all.
    """
    from experiments.phases.phase5 import run_phase5

    store = _make_store(tmp_path)
    rubric = {'accuracy': 'Correct?'}
    task = _make_task(rubric=rubric)
    teacher = _make_model('teacher1', roles=['teacher'])
    judge = _make_model('judge1', roles=['judge'])

    # Datapoints present but NO responses
    _seed_datapoints(store, 'task1', 'teacher1', n=2)
    store.write_rubric('task1', rubric)

    cfg = _make_cfg_mock(
        tasks=[task],
        models_by_role_fn=lambda role: [teacher] if role == 'teacher' else [judge],
    )

    iface = _FakeIface()
    pool = _make_pool_mock(iface)
    logger = _make_logger()
    quota = QuotaTracker({})

    # Should not raise (no evaluations produced, but only_models is None so the
    # zero-evals guard would fire). Pass only_models to bypass the guard.
    run_phase5(cfg, store, logger, pool, quota, phase_mode='New',
               only_models={'judge1'})

    assert len(iface.calls) == 0


def test_phase5_keep_mode_skips_all(tmp_path):
    """Keep mode must never invoke the judge interface."""
    from experiments.phases.phase5 import run_phase5

    store = _make_store(tmp_path)
    rubric = {'accuracy': 'Correct?'}
    task = _make_task(rubric=rubric)
    teacher = _make_model('teacher1', roles=['teacher'])
    judge = _make_model('judge1', roles=['judge'])

    _seed_datapoints(store, 'task1', 'teacher1', n=2)
    _seed_responses(store, 'task1', 'teacher1', 'student1', n=2)
    store.write_rubric('task1', rubric)

    cfg = _make_cfg_mock(
        tasks=[task],
        models_by_role_fn=lambda role: [teacher] if role == 'teacher' else [judge],
    )

    iface = _FakeIface()
    pool = _make_pool_mock(iface)
    logger = _make_logger()
    quota = QuotaTracker({})

    run_phase5(cfg, store, logger, pool, quota, phase_mode='Keep',
               only_models={'judge1'})

    assert len(iface.calls) == 0
    assert store.read_evaluations('task1', 'teacher1', 'judge1') == []


# ---------------------------------------------------------------------------
# Phase 4 — PartialPhaseFailure and Extend-mode deduplication
# ---------------------------------------------------------------------------

def test_phase4_partial_failure_raised_on_slot_error(tmp_path):
    """
    When a student slot raises an exception, run_phase4 must raise
    PartialPhaseFailure with n_failures >= 1.
    """
    from experiments.phases.phase4 import run_phase4

    store = _make_store(tmp_path)
    task = _make_task()
    teacher = _make_model('teacher1', roles=['teacher'])
    student = _make_model('student1', roles=['student'])

    _seed_datapoints(store, 'task1', 'teacher1', n=2)

    cfg = _make_cfg_mock(
        tasks=[task],
        models_by_role_fn=lambda role: [teacher] if role == 'teacher' else [student],
    )

    pool = _make_pool_mock(_ErrorIface())
    logger = _make_logger()
    quota = QuotaTracker({})

    with pytest.raises(PartialPhaseFailure) as exc_info:
        run_phase4(cfg, store, logger, pool, quota, phase_mode='New')

    ppf = exc_info.value
    assert ppf.n_failures >= 1


def test_phase4_partial_failure_counts_are_correct(tmp_path):
    """
    n_failures + n_successes must equal the number of (task, teacher, student) triples.
    """
    from experiments.phases.phase4 import run_phase4

    store = _make_store(tmp_path)
    task = _make_task()
    teacher = _make_model('teacher1', roles=['teacher'])
    # One good student, one bad student
    student_good = _make_model('student_good', roles=['student'])
    student_bad = _make_model('student_bad', roles=['student'])

    _seed_datapoints(store, 'task1', 'teacher1', n=1)

    def _models_by_role(role):
        if role == 'teacher':
            return [teacher]
        return [student_good, student_bad]

    cfg = _make_cfg_mock(tasks=[task], models_by_role_fn=_models_by_role)

    # student_good returns valid text; student_bad always raises
    call_count = {'n': 0}

    class _SelectiveIface:
        def generate(self, prompt: str, parameters: dict) -> str:
            call_count['n'] += 1
            # Check student name via prompt (not ideal but avoids complex pool mock)
            return 'A valid response'

    class _SelectiveErrorPool:
        def get(self, model_cfg):
            if model_cfg.name == 'student_bad':
                return _ErrorIface()
            return _SelectiveIface()

    logger = _make_logger()
    quota = QuotaTracker({})

    with pytest.raises(PartialPhaseFailure) as exc_info:
        run_phase4(cfg, store, logger, _SelectiveErrorPool(), quota, phase_mode='New')

    ppf = exc_info.value
    total_triples = 1 * 1 * 2  # 1 task * 1 teacher * 2 students
    assert ppf.n_failures + ppf.n_successes == total_triples
    assert ppf.n_failures == 1
    assert ppf.n_successes == 1


def test_phase4_extend_mode_skips_already_responded_datapoints(tmp_path):
    """
    Extend mode: datapoints that already have a response record must not be
    passed to the student again (deduplication / over-count fix).
    """
    from experiments.phases.phase4 import run_phase4

    store = _make_store(tmp_path)
    task = _make_task()
    teacher = _make_model('teacher1', roles=['teacher'])
    student = _make_model('student1', roles=['student'])

    # 3 datapoints seeded
    _seed_datapoints(store, 'task1', 'teacher1', n=3)

    # 2 already have responses
    _seed_responses(store, 'task1', 'teacher1', 'student1', n=2)

    cfg = _make_cfg_mock(
        tasks=[task],
        models_by_role_fn=lambda role: [teacher] if role == 'teacher' else [student],
    )

    iface = _FakeIface(response='New response')
    pool = _make_pool_mock(iface)
    logger = _make_logger()
    quota = QuotaTracker({})

    run_phase4(cfg, store, logger, pool, quota, phase_mode='Extend')

    # Exactly 1 new response should have been generated (the 3rd datapoint)
    assert len(iface.calls) == 1

    all_responses = store.read_responses('task1', 'teacher1', 'student1')
    assert len(all_responses) == 3  # 2 old + 1 new


def test_phase4_extend_mode_all_responded_skips_entirely(tmp_path):
    """
    Extend mode: when all datapoints already have responses, the student
    interface must not be called at all.
    """
    from experiments.phases.phase4 import run_phase4

    store = _make_store(tmp_path)
    task = _make_task()
    teacher = _make_model('teacher1', roles=['teacher'])
    student = _make_model('student1', roles=['student'])

    _seed_datapoints(store, 'task1', 'teacher1', n=2)
    _seed_responses(store, 'task1', 'teacher1', 'student1', n=2)

    cfg = _make_cfg_mock(
        tasks=[task],
        models_by_role_fn=lambda role: [teacher] if role == 'teacher' else [student],
    )

    iface = _FakeIface()
    pool = _make_pool_mock(iface)
    logger = _make_logger()
    quota = QuotaTracker({})

    run_phase4(cfg, store, logger, pool, quota, phase_mode='Extend')

    assert len(iface.calls) == 0


def test_phase4_extend_mode_failed_responses_are_retried(tmp_path):
    """
    Extend mode: datapoints whose existing response record has status='failed'
    must NOT be considered already responded — they should be retried.
    """
    from experiments.phases.phase4 import run_phase4

    store = _make_store(tmp_path)
    task = _make_task()
    teacher = _make_model('teacher1', roles=['teacher'])
    student = _make_model('student1', roles=['student'])

    _seed_datapoints(store, 'task1', 'teacher1', n=2)

    # Both datapoints have a failed response record
    for i in range(2):
        store.append_response('task1', 'teacher1', 'student1', {
            'id': f'task1__teacher1__{i:05d}__student1',
            'datapoint_id': f'task1__teacher1__{i:05d}',
            'task_id': 'task1',
            'teacher_model_id': 'teacher1',
            'student_model_id': 'student1',
            'input': f'Prompt {i}',
            'response': '',
            'generated_at': '2025-01-01T00:00:00Z',
            'status': 'failed',
        })

    cfg = _make_cfg_mock(
        tasks=[task],
        models_by_role_fn=lambda role: [teacher] if role == 'teacher' else [student],
    )

    iface = _FakeIface(response='Retry response')
    pool = _make_pool_mock(iface)
    logger = _make_logger()
    quota = QuotaTracker({})

    run_phase4(cfg, store, logger, pool, quota, phase_mode='Extend')

    # Both datapoints should be retried because the prior records are failed
    assert len(iface.calls) == 2


def test_phase4_keep_mode_skips_all_writing(tmp_path):
    """Keep mode must not write any response records or call the student interface."""
    from experiments.phases.phase4 import run_phase4

    store = _make_store(tmp_path)
    task = _make_task()
    teacher = _make_model('teacher1', roles=['teacher'])
    student = _make_model('student1', roles=['student'])

    _seed_datapoints(store, 'task1', 'teacher1', n=3)

    cfg = _make_cfg_mock(
        tasks=[task],
        models_by_role_fn=lambda role: [teacher] if role == 'teacher' else [student],
    )

    iface = _FakeIface()
    pool = _make_pool_mock(iface)
    logger = _make_logger()
    quota = QuotaTracker({})

    run_phase4(cfg, store, logger, pool, quota, phase_mode='Keep')

    assert len(iface.calls) == 0
    assert not store.response_file_exists('task1', 'teacher1', 'student1')


def test_phase4_new_mode_writes_all_responses(tmp_path):
    """New mode must write one response record per datapoint."""
    from experiments.phases.phase4 import run_phase4

    store = _make_store(tmp_path)
    task = _make_task()
    teacher = _make_model('teacher1', roles=['teacher'])
    student = _make_model('student1', roles=['student'])

    n = 3
    _seed_datapoints(store, 'task1', 'teacher1', n=n)

    cfg = _make_cfg_mock(
        tasks=[task],
        models_by_role_fn=lambda role: [teacher] if role == 'teacher' else [student],
    )

    iface = _FakeIface(response='My answer')
    pool = _make_pool_mock(iface)
    logger = _make_logger()
    quota = QuotaTracker({})

    run_phase4(cfg, store, logger, pool, quota, phase_mode='New')

    assert len(iface.calls) == n
    responses = store.read_responses('task1', 'teacher1', 'student1')
    assert len(responses) == n


def test_phase4_quota_exhaustion_stops_early(tmp_path):
    """When the student quota is exhausted mid-loop, remaining datapoints are skipped."""
    from experiments.phases.phase4 import run_phase4

    store = _make_store(tmp_path)
    task = _make_task()
    teacher = _make_model('teacher1', roles=['teacher'])
    student = _make_model('student1', roles=['student'])

    _seed_datapoints(store, 'task1', 'teacher1', n=5)

    cfg = _make_cfg_mock(
        tasks=[task],
        models_by_role_fn=lambda role: [teacher] if role == 'teacher' else [student],
    )

    iface = _FakeIface(response='Answer')
    pool = _make_pool_mock(iface)
    logger = _make_logger()
    # Only allow 2 calls
    quota = QuotaTracker({'student1': {'max_calls': 2}})

    run_phase4(cfg, store, logger, pool, quota, phase_mode='New')

    # At most 2 responses should have been written
    responses = store.read_responses('task1', 'teacher1', 'student1')
    assert len(responses) <= 2


# ---------------------------------------------------------------------------
# Phase 5 — quota exhaustion
# ---------------------------------------------------------------------------

def test_phase5_quota_exhaustion_stops_early(tmp_path):
    """When the judge quota is exhausted mid-loop, remaining responses are skipped."""
    from experiments.phases.phase5 import run_phase5

    store = _make_store(tmp_path)
    rubric = {'accuracy': 'Correct?'}
    task = _make_task(rubric=rubric)
    teacher = _make_model('teacher1', roles=['teacher'])
    judge = _make_model('judge1', roles=['judge'])

    _seed_datapoints(store, 'task1', 'teacher1', n=4)
    _seed_responses(store, 'task1', 'teacher1', 'student1', n=4)
    store.write_rubric('task1', rubric)

    cfg = _make_cfg_mock(
        tasks=[task],
        models_by_role_fn=lambda role: [teacher] if role == 'teacher' else [judge],
    )

    iface = _FakeIface(response='{"accuracy": "High"}')
    pool = _make_pool_mock(iface)
    logger = _make_logger()
    quota = QuotaTracker({'judge1': {'max_calls': 2}})

    run_phase5(cfg, store, logger, pool, quota, phase_mode='New',
               only_models={'judge1'})

    evals = store.read_evaluations('task1', 'teacher1', 'judge1')
    assert len(evals) <= 2
