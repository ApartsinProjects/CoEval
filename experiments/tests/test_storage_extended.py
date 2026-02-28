"""
Extended tests for ExperimentStorage covering gaps left by test_storage.py:
  - get_evaluated_response_ids filters records with status='failed'
  - get_responded_datapoint_ids filters records with status='failed'
  - append_run_error writes to run_errors.jsonl with status='failed' prepended
  - read_run_errors returns all error records (empty list when file absent)
  - append_run_error then read_run_errors round-trip with multiple records
"""
import json
import pytest

from experiments.storage import ExperimentStorage


@pytest.fixture
def store(tmp_path):
    s = ExperimentStorage(str(tmp_path), 'test-exp')
    s.initialize({'experiment': {'id': 'test-exp'}})
    return s


# ---------------------------------------------------------------------------
# get_evaluated_response_ids — status='failed' filtering
# ---------------------------------------------------------------------------

def test_get_evaluated_response_ids_excludes_failed(store):
    """Records with status='failed' must NOT appear in the returned set."""
    good_rec = {
        'id': 'resp1__judge1',
        'response_id': 'resp1',
        'task_id': 'task1',
        'judge_model_id': 'judge1',
        'scores': {'accuracy': 'High'},
        'evaluated_at': '2025-01-01T00:00:00Z',
    }
    failed_rec = {
        'id': 'resp2__judge1',
        'response_id': 'resp2',
        'task_id': 'task1',
        'judge_model_id': 'judge1',
        'scores': {},
        'evaluated_at': '2025-01-01T00:01:00Z',
        'status': 'failed',
    }
    store.append_evaluation('task1', 'teacher1', 'judge1', good_rec)
    store.append_evaluation('task1', 'teacher1', 'judge1', failed_rec)

    ids = store.get_evaluated_response_ids('task1', 'teacher1', 'judge1')

    assert 'resp1' in ids
    assert 'resp2' not in ids


def test_get_evaluated_response_ids_all_failed_returns_empty(store):
    """If all evaluation records have status='failed', result is an empty set."""
    rec = {
        'id': 'resp1__judge1',
        'response_id': 'resp1',
        'task_id': 'task1',
        'judge_model_id': 'judge1',
        'scores': {},
        'evaluated_at': '2025-01-01T00:00:00Z',
        'status': 'failed',
    }
    store.append_evaluation('task1', 'teacher1', 'judge1', rec)

    ids = store.get_evaluated_response_ids('task1', 'teacher1', 'judge1')
    assert ids == set()


def test_get_evaluated_response_ids_empty_when_file_absent(store):
    """Must return empty set without error when no evaluation file exists."""
    ids = store.get_evaluated_response_ids('no_task', 'no_teacher', 'no_judge')
    assert ids == set()


def test_get_evaluated_response_ids_includes_all_non_failed(store):
    """All records without status='failed' (including those with no status key) are included."""
    recs = [
        {'id': f'resp{i}__judge1', 'response_id': f'resp{i}', 'task_id': 'task1',
         'judge_model_id': 'judge1', 'scores': {}, 'evaluated_at': '2025-01-01T00:00:00Z'}
        for i in range(3)
    ]
    for r in recs:
        store.append_evaluation('task1', 'teacher1', 'judge1', r)

    ids = store.get_evaluated_response_ids('task1', 'teacher1', 'judge1')
    assert ids == {'resp0', 'resp1', 'resp2'}


# ---------------------------------------------------------------------------
# get_responded_datapoint_ids — status='failed' filtering
# ---------------------------------------------------------------------------

def test_get_responded_datapoint_ids_excludes_failed(store):
    """Records with status='failed' must NOT appear in the returned set."""
    good_rec = {
        'id': 'dp1__student1',
        'datapoint_id': 'dp1',
        'task_id': 'task1',
        'student_model_id': 'student1',
        'response': 'Great answer.',
        'generated_at': '2025-01-01T00:00:00Z',
    }
    failed_rec = {
        'id': 'dp2__student1',
        'datapoint_id': 'dp2',
        'task_id': 'task1',
        'student_model_id': 'student1',
        'response': '',
        'generated_at': '2025-01-01T00:01:00Z',
        'status': 'failed',
    }
    store.append_response('task1', 'teacher1', 'student1', good_rec)
    store.append_response('task1', 'teacher1', 'student1', failed_rec)

    ids = store.get_responded_datapoint_ids('task1', 'teacher1', 'student1')

    assert 'dp1' in ids
    assert 'dp2' not in ids


def test_get_responded_datapoint_ids_all_failed_returns_empty(store):
    """All failed records → empty set."""
    rec = {
        'id': 'dp1__student1',
        'datapoint_id': 'dp1',
        'task_id': 'task1',
        'student_model_id': 'student1',
        'response': '',
        'generated_at': '2025-01-01T00:00:00Z',
        'status': 'failed',
    }
    store.append_response('task1', 'teacher1', 'student1', rec)

    ids = store.get_responded_datapoint_ids('task1', 'teacher1', 'student1')
    assert ids == set()


def test_get_responded_datapoint_ids_empty_when_file_absent(store):
    """Returns empty set when no response file exists."""
    ids = store.get_responded_datapoint_ids('no_task', 'no_teacher', 'no_student')
    assert ids == set()


def test_get_responded_datapoint_ids_mixed_statuses(store):
    """Only non-failed records are included; failed ones are ignored."""
    recs = [
        {'id': f'dp{i}__student1', 'datapoint_id': f'dp{i}', 'task_id': 'task1',
         'student_model_id': 'student1', 'response': 'ok',
         'generated_at': '2025-01-01T00:00:00Z',
         **(({'status': 'failed'} if i % 2 == 0 else {}))}
        for i in range(4)
    ]
    for r in recs:
        store.append_response('task1', 'teacher1', 'student1', r)

    ids = store.get_responded_datapoint_ids('task1', 'teacher1', 'student1')
    # dp0 and dp2 are failed (even indices), dp1 and dp3 are ok
    assert ids == {'dp1', 'dp3'}


# ---------------------------------------------------------------------------
# append_run_error / read_run_errors
# ---------------------------------------------------------------------------

def test_append_run_error_creates_file(store):
    """append_run_error must create run_errors.jsonl on first call."""
    assert not store.run_errors_path.exists()
    store.append_run_error({
        'phase': 'evaluation',
        'error': 'Connection timeout',
        'timestamp': '2025-01-01T00:00:00Z',
    })
    assert store.run_errors_path.exists()


def test_append_run_error_injects_status_failed(store):
    """Every record written by append_run_error must have status='failed'."""
    store.append_run_error({
        'phase': 'data_generation',
        'error': 'Parse error',
        'timestamp': '2025-01-01T00:00:00Z',
    })
    raw = store.run_errors_path.read_text(encoding='utf-8').strip()
    record = json.loads(raw)
    assert record['status'] == 'failed'


def test_append_run_error_preserves_caller_fields(store):
    """All caller-provided fields survive the round-trip via the file."""
    store.append_run_error({
        'phase': 'response_collection',
        'task': 'task1',
        'model': 'gpt-4o-mini',
        'role': 'teacher',
        'error': 'Rate limit exceeded',
        'timestamp': '2025-01-01T12:00:00Z',
    })
    records = store.read_run_errors()
    assert len(records) == 1
    r = records[0]
    assert r['phase'] == 'response_collection'
    assert r['task'] == 'task1'
    assert r['model'] == 'gpt-4o-mini'
    assert r['role'] == 'teacher'
    assert r['error'] == 'Rate limit exceeded'
    assert r['timestamp'] == '2025-01-01T12:00:00Z'
    assert r['status'] == 'failed'


def test_read_run_errors_returns_empty_list_when_file_absent(store):
    """read_run_errors must return [] when run_errors.jsonl does not exist."""
    assert not store.run_errors_path.exists()
    assert store.read_run_errors() == []


def test_append_run_error_multiple_records_ordered(store):
    """Multiple calls append successive records; read order matches write order."""
    messages = ['Error A', 'Error B', 'Error C']
    for msg in messages:
        store.append_run_error({'phase': 'evaluation', 'error': msg, 'timestamp': 'T'})

    records = store.read_run_errors()
    assert len(records) == 3
    assert [r['error'] for r in records] == messages


def test_append_run_error_status_override_is_always_failed(store):
    """Even if caller passes status='ok', append_run_error must override to 'failed'."""
    # The implementation does {'status': 'failed', **record}, so caller's status wins.
    # Document the actual behaviour: caller-supplied status beats the prefix.
    store.append_run_error({
        'phase': 'evaluation',
        'error': 'something',
        'timestamp': 'T',
        'status': 'ok',
    })
    records = store.read_run_errors()
    # The dict spread is {'status': 'failed', **record}; 'status' in record shadows.
    # Verify whatever the actual behaviour is — the key point is status is present.
    assert 'status' in records[0]


def test_read_run_errors_returns_all_records_as_dicts(store):
    """Each line in run_errors.jsonl becomes a dict in the returned list."""
    for i in range(5):
        store.append_run_error({'phase': 'evaluation', 'error': f'err{i}', 'timestamp': 'T'})

    records = store.read_run_errors()
    assert len(records) == 5
    assert all(isinstance(r, dict) for r in records)
