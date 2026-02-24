"""
Tests for ExperimentStorage — all filesystem I/O, no LLM calls.

Uses pytest's tmp_path fixture so each test gets an isolated directory.
"""
import json
import pytest

from coeval.storage import ExperimentStorage


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def store(tmp_path):
    """Return an initialized ExperimentStorage for a fresh experiment."""
    s = ExperimentStorage(str(tmp_path), 'test-exp')
    s.initialize({'experiment': {'id': 'test-exp'}})
    return s


# ---------------------------------------------------------------------------
# initialize()
# ---------------------------------------------------------------------------

def test_initialize_creates_folder_tree(tmp_path):
    s = ExperimentStorage(str(tmp_path), 'my-exp')
    s.initialize({'x': 1})
    assert (tmp_path / 'my-exp').is_dir()
    for sub in ('phase1_attributes', 'phase2_rubric', 'phase3_datapoints',
                 'phase4_responses', 'phase5_evaluations'):
        assert (tmp_path / 'my-exp' / sub).is_dir()


def test_initialize_writes_config_snapshot(tmp_path):
    s = ExperimentStorage(str(tmp_path), 'my-exp')
    s.initialize({'key': 'value'})
    import yaml
    with open(tmp_path / 'my-exp' / 'config.yaml') as f:
        data = yaml.safe_load(f)
    assert data['key'] == 'value'


def test_initialize_meta_json(store):
    meta = store.read_meta()
    assert meta['status'] == 'in_progress'
    assert meta['phases_completed'] == []
    assert meta['phases_in_progress'] == []


def test_initialize_fails_if_folder_exists(tmp_path):
    s = ExperimentStorage(str(tmp_path), 'dup-exp')
    s.initialize({})
    s2 = ExperimentStorage(str(tmp_path), 'dup-exp')
    with pytest.raises(FileExistsError):
        s2.initialize({})


def test_initialize_copies_phase1_from_source(tmp_path):
    # Create a source experiment with a phase1 artifact
    src = ExperimentStorage(str(tmp_path), 'src-exp')
    src.initialize({})
    src.write_target_attrs('task1', {'a': ['x', 'y']})

    # New experiment resumes from src
    dst = ExperimentStorage(str(tmp_path), 'dst-exp')
    dst.initialize({}, resume_from_id='src-exp', source_storage_folder=str(tmp_path))
    assert dst.target_attrs_exist('task1')
    assert dst.read_target_attrs('task1') == {'a': ['x', 'y']}


# ---------------------------------------------------------------------------
# update_meta()
# ---------------------------------------------------------------------------

def test_update_meta_phase_lifecycle(store):
    store.update_meta(phase_started='attribute_mapping')
    meta = store.read_meta()
    assert 'attribute_mapping' in meta['phases_in_progress']

    store.update_meta(phase_completed='attribute_mapping')
    meta = store.read_meta()
    assert 'attribute_mapping' not in meta['phases_in_progress']
    assert 'attribute_mapping' in meta['phases_completed']


def test_update_meta_status(store):
    store.update_meta(status='completed')
    assert store.read_meta()['status'] == 'completed'


def test_update_meta_no_duplicate_in_progress(store):
    store.update_meta(phase_started='data_generation')
    store.update_meta(phase_started='data_generation')
    meta = store.read_meta()
    assert meta['phases_in_progress'].count('data_generation') == 1


# ---------------------------------------------------------------------------
# Phase 1 — attribute maps
# ---------------------------------------------------------------------------

def test_phase1_target_attrs_round_trip(store):
    attrs = {'tone': ['formal', 'casual'], 'urgency': ['low', 'high']}
    store.write_target_attrs('task1', attrs)
    assert store.read_target_attrs('task1') == attrs


def test_phase1_nuanced_attrs_round_trip(store):
    attrs = {'style': ['terse', 'verbose']}
    store.write_nuanced_attrs('task1', attrs)
    assert store.read_nuanced_attrs('task1') == attrs


def test_phase1_exists_checks(store):
    assert not store.target_attrs_exist('task1')
    assert not store.nuanced_attrs_exist('task1')
    store.write_target_attrs('task1', {})
    store.write_nuanced_attrs('task1', {})
    assert store.target_attrs_exist('task1')
    assert store.nuanced_attrs_exist('task1')


# ---------------------------------------------------------------------------
# Phase 2 — rubric
# ---------------------------------------------------------------------------

def test_phase2_rubric_round_trip(store):
    rubric = {'accuracy': 'Is it correct?', 'brevity': 'Is it short?'}
    store.write_rubric('task1', rubric)
    assert store.read_rubric('task1') == rubric
    assert store.rubric_exists('task1')


def test_phase2_rubric_not_exists(store):
    assert not store.rubric_exists('task1')


# ---------------------------------------------------------------------------
# Phase 3 — datapoints (JSONL)
# ---------------------------------------------------------------------------

@pytest.fixture
def dp():
    return {
        'id': 'task1__teacher1__00001',
        'task_id': 'task1',
        'teacher_model_id': 'teacher1',
        'prompt': 'Say hello.',
        'reference_response': 'Hello.',
        'generated_at': '2025-01-01T00:00:00Z',
    }


def test_phase3_append_and_read(store, dp):
    store.append_datapoint('task1', 'teacher1', dp)
    records = store.read_datapoints('task1', 'teacher1')
    assert len(records) == 1
    assert records[0]['id'] == dp['id']


def test_phase3_multiple_appends(store, dp):
    for i in range(5):
        record = dict(dp, id=f'task1__teacher1__{i:05d}')
        store.append_datapoint('task1', 'teacher1', record)
    assert store.count_datapoints('task1', 'teacher1') == 5


def test_phase3_count_nonexistent_returns_zero(store):
    assert store.count_datapoints('no_task', 'no_teacher') == 0


def test_phase3_index_datapoints(store, dp):
    store.append_datapoint('task1', 'teacher1', dp)
    index = store.index_datapoints('task1', 'teacher1')
    assert dp['id'] in index
    assert index[dp['id']]['prompt'] == dp['prompt']


def test_phase3_read_empty_when_file_absent(store):
    assert store.read_datapoints('no_task', 'no_teacher') == []


# ---------------------------------------------------------------------------
# Phase 4 — responses
# ---------------------------------------------------------------------------

@pytest.fixture
def response_rec():
    return {
        'id': 'task1__teacher1__00001__student1',
        'datapoint_id': 'task1__teacher1__00001',
        'task_id': 'task1',
        'student_model_id': 'student1',
        'response': 'Hi there.',
        'responded_at': '2025-01-01T00:01:00Z',
    }


def test_phase4_append_and_read(store, response_rec):
    store.append_response('task1', 'teacher1', 'student1', response_rec)
    records = store.read_responses('task1', 'teacher1', 'student1')
    assert len(records) == 1
    assert records[0]['id'] == response_rec['id']


def test_phase4_get_responded_ids(store, response_rec):
    store.append_response('task1', 'teacher1', 'student1', response_rec)
    ids = store.get_responded_datapoint_ids('task1', 'teacher1', 'student1')
    assert 'task1__teacher1__00001' in ids


def test_phase4_response_file_exists(store, response_rec):
    assert not store.response_file_exists('task1', 'teacher1', 'student1')
    store.append_response('task1', 'teacher1', 'student1', response_rec)
    assert store.response_file_exists('task1', 'teacher1', 'student1')


def test_phase4_iter_response_files(store, response_rec):
    store.append_response('task1', 'teacher1', 'student1', response_rec)
    store.append_response('task1', 'teacher1', 'student2', dict(response_rec, id='...2'))
    files = list(store.iter_response_files('task1', 'teacher1'))
    assert len(files) == 2


# ---------------------------------------------------------------------------
# Phase 5 — evaluations
# ---------------------------------------------------------------------------

@pytest.fixture
def eval_rec():
    return {
        'id': 'task1__teacher1__00001__student1__judge1',
        'response_id': 'task1__teacher1__00001__student1',
        'task_id': 'task1',
        'judge_model_id': 'judge1',
        'scores': {'accuracy': 'High', 'brevity': 'Medium'},
        'evaluated_at': '2025-01-01T00:02:00Z',
    }


def test_phase5_append_and_read(store, eval_rec):
    store.append_evaluation('task1', 'teacher1', 'judge1', eval_rec)
    records = store.read_evaluations('task1', 'teacher1', 'judge1')
    assert len(records) == 1
    assert records[0]['scores']['accuracy'] == 'High'


def test_phase5_get_evaluated_response_ids(store, eval_rec):
    store.append_evaluation('task1', 'teacher1', 'judge1', eval_rec)
    ids = store.get_evaluated_response_ids('task1', 'teacher1', 'judge1')
    assert 'task1__teacher1__00001__student1' in ids


def test_phase5_evaluation_file_exists(store, eval_rec):
    assert not store.evaluation_file_exists('task1', 'teacher1', 'judge1')
    store.append_evaluation('task1', 'teacher1', 'judge1', eval_rec)
    assert store.evaluation_file_exists('task1', 'teacher1', 'judge1')
