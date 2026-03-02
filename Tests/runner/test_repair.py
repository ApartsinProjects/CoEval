"""
Tests for coeval repair — invalid-record scanning and marking.

Covers:
- scan_experiment: detects invalid records in all three phases
- scan_coverage_gaps: detects missing records by cross-referencing upstream data
- fix_invalid_records: marks invalid records as status='failed'
- reopen_phases: removes phases from phases_completed in meta.json
- storage.mark_failed_records: low-level rewrite helper
- storage.count_datapoints: skips status='failed' records (Extend mode fix)
"""
import json
import pytest
from pathlib import Path

from runner.storage import ExperimentStorage
from runner.commands.repair_cmd import (
    scan_experiment,
    scan_coverage_gaps,
    count_valid_records,
    collect_valid_examples,
    scan_file_breakdown,
    fix_invalid_records,
    reopen_phases,
    _is_invalid_p3,
    _is_invalid_p4,
    _is_invalid_p5,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write_jsonl(path: Path, records: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        '\n'.join(json.dumps(r) for r in records) + '\n', encoding='utf-8'
    )


def _read_jsonl(path: Path) -> list[dict]:
    return [json.loads(ln) for ln in path.read_text(encoding='utf-8').splitlines() if ln.strip()]


def _make_exp(tmp_path: Path) -> tuple[Path, ExperimentStorage]:
    """Create a minimal experiment folder and return (run_path, storage)."""
    s = ExperimentStorage(str(tmp_path), 'exp')
    s.initialize({'experiment': {'id': 'exp'}})
    return tmp_path / 'exp', s


# ---------------------------------------------------------------------------
# Validity predicate unit tests
# ---------------------------------------------------------------------------

class TestValidityPredicates:
    def test_p3_valid_record(self):
        assert not _is_invalid_p3({'reference_response': 'hello'})

    def test_p3_empty_reference_response(self):
        assert _is_invalid_p3({'reference_response': ''})

    def test_p3_null_reference_response(self):
        assert _is_invalid_p3({'reference_response': None})

    def test_p3_missing_reference_response(self):
        assert _is_invalid_p3({})

    def test_p3_status_failed(self):
        assert _is_invalid_p3({'reference_response': 'ok', 'status': 'failed'})

    def test_p4_valid_record(self):
        assert not _is_invalid_p4({'response': 'some text'})

    def test_p4_empty_response(self):
        assert _is_invalid_p4({'response': ''})

    def test_p4_null_response(self):
        assert _is_invalid_p4({'response': None})

    def test_p4_status_failed(self):
        assert _is_invalid_p4({'response': 'ok', 'status': 'failed'})

    def test_p5_valid_record(self):
        assert not _is_invalid_p5({'scores': {'clarity': 'High'}})

    def test_p5_empty_scores_dict(self):
        assert _is_invalid_p5({'scores': {}})

    def test_p5_all_null_scores(self):
        assert _is_invalid_p5({'scores': {'clarity': None, 'depth': None}})

    def test_p5_all_empty_string_scores(self):
        assert _is_invalid_p5({'scores': {'clarity': '', 'depth': ''}})

    def test_p5_partial_null_not_invalid(self):
        # Only "all null" is invalid; partial is fine
        assert not _is_invalid_p5({'scores': {'clarity': 'High', 'depth': None}})

    def test_p5_missing_scores_key(self):
        assert _is_invalid_p5({})

    def test_p5_status_failed(self):
        assert _is_invalid_p5({'scores': {'ok': 'High'}, 'status': 'failed'})


# ---------------------------------------------------------------------------
# scan_experiment
# ---------------------------------------------------------------------------

class TestScanExperiment:
    def test_scan_clean_experiment_returns_empty(self, tmp_path):
        run_path, s = _make_exp(tmp_path)
        # Write one valid record per phase
        _write_jsonl(
            run_path / 'phase3_datapoints' / 'task.teacher.datapoints.jsonl',
            [{'id': 'dp1', 'reference_response': 'valid ref'}],
        )
        _write_jsonl(
            run_path / 'phase4_responses' / 'task.teacher.student.responses.jsonl',
            [{'id': 'r1', 'datapoint_id': 'dp1', 'response': 'valid response'}],
        )
        _write_jsonl(
            run_path / 'phase5_evaluations' / 'task.teacher.judge.evaluations.jsonl',
            [{'id': 'e1', 'response_id': 'r1', 'scores': {'clarity': 'High'}}],
        )
        report = scan_experiment(run_path)
        assert report['phase3'] == []
        assert report['phase4'] == []
        assert report['phase5'] == []

    def test_scan_detects_empty_reference_response(self, tmp_path):
        run_path, _ = _make_exp(tmp_path)
        _write_jsonl(
            run_path / 'phase3_datapoints' / 'task.teacher.datapoints.jsonl',
            [
                {'id': 'dp1', 'reference_response': 'ok'},
                {'id': 'dp2', 'reference_response': ''},        # invalid
                {'id': 'dp3', 'reference_response': None},      # invalid
            ],
        )
        report = scan_experiment(run_path)
        assert len(report['phase3']) == 2
        ids = {iss['record_id'] for iss in report['phase3']}
        assert ids == {'dp2', 'dp3'}

    def test_scan_detects_empty_response(self, tmp_path):
        run_path, _ = _make_exp(tmp_path)
        _write_jsonl(
            run_path / 'phase4_responses' / 'task.t.s.responses.jsonl',
            [
                {'id': 'r1', 'datapoint_id': 'dp1', 'response': 'good'},
                {'id': 'r2', 'datapoint_id': 'dp2', 'response': ''},  # invalid
                {'id': 'r3', 'datapoint_id': 'dp3', 'response': None, 'status': 'failed'},
            ],
        )
        report = scan_experiment(run_path)
        assert len(report['phase4']) == 2
        ids = {iss['record_id'] for iss in report['phase4']}
        assert ids == {'r2', 'r3'}

    def test_scan_detects_failed_evaluations(self, tmp_path):
        run_path, _ = _make_exp(tmp_path)
        _write_jsonl(
            run_path / 'phase5_evaluations' / 'task.t.j.evaluations.jsonl',
            [
                {'id': 'e1', 'response_id': 'r1', 'scores': {'c': 'High'}},
                {'id': 'e2', 'response_id': 'r2', 'scores': {}, 'status': 'failed'},
                {'id': 'e3', 'response_id': 'r3', 'scores': {}},
            ],
        )
        report = scan_experiment(run_path)
        assert len(report['phase5']) == 2
        ids = {iss['record_id'] for iss in report['phase5']}
        assert ids == {'e2', 'e3'}

    def test_scan_detects_json_parse_errors(self, tmp_path):
        run_path, _ = _make_exp(tmp_path)
        p = run_path / 'phase4_responses' / 'bad.jsonl'
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text('{"id": "r1", "response": "ok"}\n{BAD JSON\n', encoding='utf-8')
        report = scan_experiment(run_path)
        json_issues = [i for i in report['phase4'] if i['reason'] == 'JSON parse error']
        assert len(json_issues) == 1
        assert json_issues[0]['record_id'] is None

    def test_scan_returns_file_and_line_info(self, tmp_path):
        run_path, _ = _make_exp(tmp_path)
        _write_jsonl(
            run_path / 'phase3_datapoints' / 'task.teacher.datapoints.jsonl',
            [
                {'id': 'dp1', 'reference_response': 'ok'},
                {'id': 'dp2', 'reference_response': ''},
            ],
        )
        report = scan_experiment(run_path)
        issue = report['phase3'][0]
        assert 'file' in issue
        assert issue['line'] == 2          # second line is invalid
        assert issue['record_id'] == 'dp2'


# ---------------------------------------------------------------------------
# fix_invalid_records
# ---------------------------------------------------------------------------

class TestFixInvalidRecords:
    def test_fix_marks_phase4_records_as_failed(self, tmp_path):
        run_path, _ = _make_exp(tmp_path)
        fpath = run_path / 'phase4_responses' / 'task.t.s.responses.jsonl'
        _write_jsonl(fpath, [
            {'id': 'r1', 'datapoint_id': 'dp1', 'response': 'good'},
            {'id': 'r2', 'datapoint_id': 'dp2', 'response': ''},
        ])

        report = scan_experiment(run_path)
        counts = fix_invalid_records(run_path, report)

        assert counts['phase4'] == 1
        records = _read_jsonl(fpath)
        assert records[0].get('status') != 'failed'   # r1 untouched
        assert records[1]['status'] == 'failed'         # r2 marked

    def test_fix_marks_phase3_records_as_failed(self, tmp_path):
        run_path, _ = _make_exp(tmp_path)
        fpath = run_path / 'phase3_datapoints' / 'task.t.datapoints.jsonl'
        _write_jsonl(fpath, [
            {'id': 'dp1', 'reference_response': 'ok'},
            {'id': 'dp2', 'reference_response': ''},
            {'id': 'dp3', 'reference_response': 'also ok'},
        ])

        report = scan_experiment(run_path)
        counts = fix_invalid_records(run_path, report)

        assert counts['phase3'] == 1
        records = _read_jsonl(fpath)
        assert records[1]['status'] == 'failed'

    def test_fix_does_not_double_mark_already_failed(self, tmp_path):
        run_path, _ = _make_exp(tmp_path)
        fpath = run_path / 'phase4_responses' / 'task.t.s.responses.jsonl'
        _write_jsonl(fpath, [
            {'id': 'r1', 'response': '', 'status': 'failed'},  # already failed
        ])

        report = scan_experiment(run_path)
        counts = fix_invalid_records(run_path, report)

        assert counts['phase4'] == 0   # not double-marked
        records = _read_jsonl(fpath)
        assert records[0]['status'] == 'failed'   # still failed (unchanged)

    def test_fix_preserves_valid_records_unchanged(self, tmp_path):
        run_path, _ = _make_exp(tmp_path)
        fpath = run_path / 'phase5_evaluations' / 'task.t.j.evaluations.jsonl'
        _write_jsonl(fpath, [
            {'id': 'e1', 'response_id': 'r1', 'scores': {'c': 'High'}},
            {'id': 'e2', 'response_id': 'r2', 'scores': {}},
        ])

        report = scan_experiment(run_path)
        fix_invalid_records(run_path, report)

        # Phase 5 behavior: invalid records (e2) are removed entirely so that
        # get_evaluated_response_ids will not return them, enabling --continue
        # to re-attempt those evaluations.
        records = _read_jsonl(fpath)
        assert len(records) == 1                   # only e1 remains
        assert 'status' not in records[0]          # e1 untouched
        # e2 has been removed (not just marked) — coeval repair removes it


# ---------------------------------------------------------------------------
# storage.mark_failed_records
# ---------------------------------------------------------------------------

class TestMarkFailedRecords:
    def test_marks_specified_ids(self, tmp_path):
        s = ExperimentStorage(str(tmp_path), 'exp')
        s.initialize({})
        fpath = tmp_path / 'exp' / 'test.jsonl'
        _write_jsonl(fpath, [
            {'id': 'a', 'val': 1},
            {'id': 'b', 'val': 2},
            {'id': 'c', 'val': 3},
        ])
        n = s.mark_failed_records(fpath, {'a', 'c'})
        assert n == 2
        recs = _read_jsonl(fpath)
        assert recs[0]['status'] == 'failed'
        assert 'status' not in recs[1]
        assert recs[2]['status'] == 'failed'

    def test_skips_already_failed(self, tmp_path):
        s = ExperimentStorage(str(tmp_path), 'exp')
        s.initialize({})
        fpath = tmp_path / 'exp' / 'test.jsonl'
        _write_jsonl(fpath, [{'id': 'a', 'status': 'failed'}])
        n = s.mark_failed_records(fpath, {'a'})
        assert n == 0   # already failed, not counted as newly marked

    def test_nonexistent_file_returns_zero(self, tmp_path):
        s = ExperimentStorage(str(tmp_path), 'exp')
        s.initialize({})
        fpath = tmp_path / 'exp' / 'ghost.jsonl'
        n = s.mark_failed_records(fpath, {'x'})
        assert n == 0

    def test_preserves_malformed_lines(self, tmp_path):
        s = ExperimentStorage(str(tmp_path), 'exp')
        s.initialize({})
        fpath = tmp_path / 'exp' / 'test.jsonl'
        fpath.write_text('{"id": "a", "v": 1}\n{BAD}\n', encoding='utf-8')
        n = s.mark_failed_records(fpath, {'a'})
        assert n == 1
        lines = [l for l in fpath.read_text(encoding='utf-8').splitlines() if l.strip()]
        assert len(lines) == 2
        assert json.loads(lines[0])['status'] == 'failed'
        assert lines[1] == '{BAD}'   # malformed preserved verbatim


# ---------------------------------------------------------------------------
# storage.count_datapoints — skips status='failed' records
# ---------------------------------------------------------------------------

class TestCountDatapointsSkipsFailed:
    def test_counts_only_valid_records(self, tmp_path):
        s = ExperimentStorage(str(tmp_path), 'exp')
        s.initialize({'experiment': {'id': 'exp'}})
        # Write 3 records: 2 valid, 1 failed
        dp_path = (tmp_path / 'exp' / 'phase3_datapoints'
                   / 'task1.teacher1.datapoints.jsonl')
        _write_jsonl(dp_path, [
            {'id': 'dp1', 'reference_response': 'ok'},
            {'id': 'dp2', 'reference_response': '', 'status': 'failed'},
            {'id': 'dp3', 'reference_response': 'also ok'},
        ])
        assert s.count_datapoints('task1', 'teacher1') == 2

    def test_all_valid_returns_full_count(self, tmp_path):
        s = ExperimentStorage(str(tmp_path), 'exp')
        s.initialize({'experiment': {'id': 'exp'}})
        dp_path = (tmp_path / 'exp' / 'phase3_datapoints'
                   / 'task1.teacher1.datapoints.jsonl')
        _write_jsonl(dp_path, [
            {'id': 'dp1', 'reference_response': 'ok'},
            {'id': 'dp2', 'reference_response': 'ok2'},
        ])
        assert s.count_datapoints('task1', 'teacher1') == 2

    def test_all_failed_returns_zero(self, tmp_path):
        s = ExperimentStorage(str(tmp_path), 'exp')
        s.initialize({'experiment': {'id': 'exp'}})
        dp_path = (tmp_path / 'exp' / 'phase3_datapoints'
                   / 'task1.teacher1.datapoints.jsonl')
        _write_jsonl(dp_path, [
            {'id': 'dp1', 'reference_response': '', 'status': 'failed'},
        ])
        assert s.count_datapoints('task1', 'teacher1') == 0

    def test_extend_mode_regenerates_after_repair(self, tmp_path):  # noqa: E501
        """End-to-end: repair marks failed → count drops → Extend mode detects gap."""
        s = ExperimentStorage(str(tmp_path), 'exp')
        s.initialize({'experiment': {'id': 'exp'}})
        dp_path = (tmp_path / 'exp' / 'phase3_datapoints'
                   / 'task1.teacher1.datapoints.jsonl')
        # Start with 3 records (2 valid, 1 invalid)
        _write_jsonl(dp_path, [
            {'id': 'dp1', 'reference_response': 'ok'},
            {'id': 'dp2', 'reference_response': ''},       # invalid — will be repaired
            {'id': 'dp3', 'reference_response': 'ok3'},
        ])
        assert s.count_datapoints('task1', 'teacher1') == 3  # before repair

        # Repair: mark dp2 as failed
        s.mark_failed_records(dp_path, {'dp2'})

        assert s.count_datapoints('task1', 'teacher1') == 2  # after repair
        # Extend mode would compute: total=3, existing=2 → generate 1 more


# ---------------------------------------------------------------------------
# scan_coverage_gaps
# ---------------------------------------------------------------------------

class TestScanCoverageGaps:
    def _setup_p3(self, run_path, task, teacher, dp_ids):
        f = run_path / 'phase3_datapoints' / f'{task}.{teacher}.datapoints.jsonl'
        _write_jsonl(f, [
            {'id': dp, 'task_id': task, 'teacher_model_id': teacher,
             'reference_response': 'ok'}
            for dp in dp_ids
        ])

    def _setup_p4(self, run_path, task, teacher, student, dp_ids, respond_ids=None):
        if respond_ids is None:
            respond_ids = dp_ids
        f = run_path / 'phase4_responses' / f'{task}.{teacher}.{student}.responses.jsonl'
        _write_jsonl(f, [
            {'id': f'{dp}__{student}', 'task_id': task,
             'teacher_model_id': teacher, 'student_model_id': student,
             'datapoint_id': dp, 'response': 'answer'}
            for dp in respond_ids
        ])

    def _setup_p5(self, run_path, task, teacher, student, judge, resp_ids,
                  eval_ids=None):
        if eval_ids is None:
            eval_ids = resp_ids
        f = run_path / 'phase5_evaluations' / f'{task}.{teacher}.{judge}.evaluations.jsonl'
        _write_jsonl(f, [
            {'id': f'{r}__{judge}', 'task_id': task,
             'teacher_model_id': teacher, 'judge_model_id': judge,
             'response_id': r, 'scores': {'clarity': 'High'}}
            for r in eval_ids
        ])

    def test_no_gaps_returns_empty(self, tmp_path):
        run_path, _ = _make_exp(tmp_path)
        dp_ids = ['dp1', 'dp2', 'dp3']
        resp_ids = [f'{dp}__stu' for dp in dp_ids]
        self._setup_p3(run_path, 'task', 'tch', dp_ids)
        self._setup_p4(run_path, 'task', 'tch', 'stu', dp_ids)
        self._setup_p5(run_path, 'task', 'tch', 'stu', 'jud', resp_ids)
        gaps = scan_coverage_gaps(run_path)
        assert gaps['phase4_gaps'] == []
        assert gaps['phase5_gaps'] == []
        assert gaps['phases_to_reopen'] == set()

    def test_detects_phase5_missing_evaluations(self, tmp_path):
        run_path, _ = _make_exp(tmp_path)
        dp_ids = ['dp1', 'dp2', 'dp3']
        resp_ids = [f'{dp}__stu' for dp in dp_ids]
        self._setup_p3(run_path, 'task', 'tch', dp_ids)
        self._setup_p4(run_path, 'task', 'tch', 'stu', dp_ids)
        # Judge only evaluated 1 of 3 responses
        self._setup_p5(run_path, 'task', 'tch', 'stu', 'jud', resp_ids,
                       eval_ids=[resp_ids[0]])
        gaps = scan_coverage_gaps(run_path)
        assert len(gaps['phase5_gaps']) == 1
        assert gaps['phase5_gaps'][0]['missing'] == 2
        assert 'evaluation' in gaps['phases_to_reopen']

    def test_detects_phase4_missing_responses(self, tmp_path):
        run_path, _ = _make_exp(tmp_path)
        dp_ids = ['dp1', 'dp2', 'dp3']
        self._setup_p3(run_path, 'task', 'tch', dp_ids)
        # Student only responded to 2 of 3 datapoints
        self._setup_p4(run_path, 'task', 'tch', 'stu', dp_ids,
                       respond_ids=['dp1', 'dp2'])
        gaps = scan_coverage_gaps(run_path)
        assert len(gaps['phase4_gaps']) == 1
        assert gaps['phase4_gaps'][0]['missing'] == 1
        assert 'response_collection' in gaps['phases_to_reopen']

    def test_complete_coverage_no_reopen(self, tmp_path):
        run_path, _ = _make_exp(tmp_path)
        dp_ids = ['dp1', 'dp2']
        resp_ids = [f'{dp}__stu' for dp in dp_ids]
        self._setup_p3(run_path, 'task', 'tch', dp_ids)
        self._setup_p4(run_path, 'task', 'tch', 'stu', dp_ids)
        self._setup_p5(run_path, 'task', 'tch', 'stu', 'jud', resp_ids)
        gaps = scan_coverage_gaps(run_path)
        assert gaps['phases_to_reopen'] == set()

    def test_failed_evaluations_not_counted_as_gap(self, tmp_path):
        """Phase5 file where all records have status='failed' should NOT be a gap.

        Failed records are recorded attempts; gaps only occur when a response has
        NO evaluation record at all.
        """
        run_path, _ = _make_exp(tmp_path)
        dp_ids = ['dp1', 'dp2', 'dp3']
        resp_ids = [f'{dp}__stu' for dp in dp_ids]
        self._setup_p3(run_path, 'task', 'tch', dp_ids)
        self._setup_p4(run_path, 'task', 'tch', 'stu', dp_ids)
        # Write evaluation file with all records marked as failed
        f = run_path / 'phase5_evaluations' / 'task.tch.jud.evaluations.jsonl'
        _write_jsonl(f, [
            {'id': f'{r}__jud', 'task_id': 'task',
             'teacher_model_id': 'tch', 'judge_model_id': 'jud',
             'response_id': r, 'scores': {}, 'status': 'failed'}
            for r in resp_ids
        ])
        gaps = scan_coverage_gaps(run_path)
        assert gaps['phase5_gaps'] == [], (
            "All-failed phase5 records should count as covered, not as a gap"
        )
        assert gaps['phases_to_reopen'] == set()

    def test_judge_removed_from_config_not_counted_as_gap(self, tmp_path):
        """Evaluation file for a judge not in config should be skipped entirely."""
        import yaml
        run_path, _ = _make_exp(tmp_path)
        dp_ids = ['dp1', 'dp2']
        resp_ids = [f'{dp}__stu' for dp in dp_ids]
        self._setup_p3(run_path, 'task', 'tch', dp_ids)
        self._setup_p4(run_path, 'task', 'tch', 'stu', dp_ids)
        # Write evaluation file with only 1 of 2 responses evaluated — for a
        # judge that is NOT in the config.
        self._setup_p5(run_path, 'task', 'tch', 'stu', 'old-judge', resp_ids,
                       eval_ids=[resp_ids[0]])
        # Write config with only 'active-judge' as the judge model
        config_path = run_path / 'config.yaml'
        config_path.write_text(yaml.dump({
            'models': [
                {'name': 'active-judge', 'roles': ['judge']},
                {'name': 'tch', 'roles': ['teacher']},
            ]
        }), encoding='utf-8')
        gaps = scan_coverage_gaps(run_path)
        assert gaps['phase5_gaps'] == [], (
            "Evaluation file for removed judge should not be flagged as a gap"
        )
        assert 'evaluation' not in gaps['phases_to_reopen']


# ---------------------------------------------------------------------------
# reopen_phases
# ---------------------------------------------------------------------------

class TestReopenPhases:
    def test_removes_phase_from_completed(self, tmp_path):
        run_path, s = _make_exp(tmp_path)
        s.update_meta(phase_completed='evaluation')
        assert 'evaluation' in s.read_meta()['phases_completed']
        removed = reopen_phases(run_path, {'evaluation'})
        assert removed == ['evaluation']
        assert 'evaluation' not in s.read_meta()['phases_completed']

    def test_sets_status_to_in_progress(self, tmp_path):
        run_path, s = _make_exp(tmp_path)
        s.update_meta(phase_completed='evaluation')
        reopen_phases(run_path, {'evaluation'})
        assert s.read_meta()['status'] == 'in_progress'

    def test_phase_not_completed_returns_empty(self, tmp_path):
        run_path, s = _make_exp(tmp_path)
        # 'evaluation' was never marked completed
        removed = reopen_phases(run_path, {'evaluation'})
        assert removed == []

    def test_removes_only_specified_phases(self, tmp_path):
        run_path, s = _make_exp(tmp_path)
        s.update_meta(phase_completed='attribute_mapping')
        s.update_meta(phase_completed='rubric_mapping')
        s.update_meta(phase_completed='evaluation')
        removed = reopen_phases(run_path, {'evaluation'})
        assert removed == ['evaluation']
        meta = s.read_meta()
        assert 'attribute_mapping' in meta['phases_completed']
        assert 'rubric_mapping' in meta['phases_completed']
        assert 'evaluation' not in meta['phases_completed']


# ---------------------------------------------------------------------------
# count_valid_records
# ---------------------------------------------------------------------------

class TestCountValidRecords:
    """count_valid_records() returns per-phase counts of non-invalid records."""

    def _write_p3(self, run_path, task, teacher, records):
        f = run_path / 'phase3_datapoints' / f'{task}.{teacher}.datapoints.jsonl'
        _write_jsonl(f, records)

    def _write_p4(self, run_path, task, teacher, student, records):
        f = run_path / 'phase4_responses' / f'{task}.{teacher}.{student}.responses.jsonl'
        _write_jsonl(f, records)

    def _write_p5(self, run_path, task, teacher, judge, records):
        f = run_path / 'phase5_evaluations' / f'{task}.{teacher}.{judge}.evaluations.jsonl'
        _write_jsonl(f, records)

    def test_counts_valid_p3(self, tmp_path):
        run_path, _ = _make_exp(tmp_path)
        self._write_p3(run_path, 't', 'tch', [
            {'id': 'a', 'reference_response': 'ok'},
            {'id': 'b', 'reference_response': ''},     # invalid
            {'id': 'c', 'reference_response': 'good'},
            {'id': 'd', 'status': 'failed', 'reference_response': 'ok'},  # invalid
        ])
        counts = count_valid_records(run_path)
        assert counts['phase3'] == 2   # a and c
        assert counts['phase4'] == 0
        assert counts['phase5'] == 0

    def test_counts_valid_p4(self, tmp_path):
        run_path, _ = _make_exp(tmp_path)
        self._write_p4(run_path, 't', 'tch', 'stu', [
            {'id': 'r1', 'response': 'answer'},
            {'id': 'r2', 'response': None},            # invalid
            {'id': 'r3', 'response': 'another answer'},
        ])
        counts = count_valid_records(run_path)
        assert counts['phase4'] == 2   # r1, r3

    def test_counts_valid_p5(self, tmp_path):
        run_path, _ = _make_exp(tmp_path)
        self._write_p5(run_path, 't', 'tch', 'jud', [
            {'id': 'e1', 'response_id': 'r1', 'scores': {'quality': 'High'}},
            {'id': 'e2', 'response_id': 'r2', 'scores': {}, 'status': 'failed'},  # invalid
            {'id': 'e3', 'response_id': 'r3', 'scores': {'quality': 'Medium'}},
        ])
        counts = count_valid_records(run_path)
        assert counts['phase5'] == 2   # e1, e3

    def test_empty_dirs_return_zeros(self, tmp_path):
        run_path, _ = _make_exp(tmp_path)
        counts = count_valid_records(run_path)
        assert counts == {'phase3': 0, 'phase4': 0, 'phase5': 0}

    def test_all_invalid_returns_zeros(self, tmp_path):
        run_path, _ = _make_exp(tmp_path)
        self._write_p3(run_path, 't', 'tch', [
            {'id': 'a', 'reference_response': ''},
            {'id': 'b', 'status': 'failed', 'reference_response': 'ok'},
        ])
        counts = count_valid_records(run_path)
        assert counts['phase3'] == 0


# ---------------------------------------------------------------------------
# Diagnostic re-scan behaviour
# ---------------------------------------------------------------------------

class TestRescanAfterFixInvalids:
    """After fix_invalid_records removes phase5 failed records, the caller must
    re-scan coverage gaps to detect that those response slots are now empty.
    This mimics the cmd_repair logic of re-scanning when counts['phase5'] > 0.
    """

    def _setup(self, run_path, dp_ids, resp_ids):
        # Phase 3: valid datapoints
        f3 = run_path / 'phase3_datapoints' / 'task.tch.datapoints.jsonl'
        _write_jsonl(f3, [
            {'id': dp, 'task_id': 'task', 'teacher_model_id': 'tch',
             'reference_response': 'ref'} for dp in dp_ids
        ])
        # Phase 4: valid responses
        f4 = run_path / 'phase4_responses' / 'task.tch.stu.responses.jsonl'
        _write_jsonl(f4, [
            {'id': rid, 'task_id': 'task', 'teacher_model_id': 'tch',
             'student_model_id': 'stu', 'datapoint_id': dp, 'response': 'ans'}
            for rid, dp in zip(resp_ids, dp_ids)
        ])

    def test_removing_failed_p5_records_creates_new_gap(self, tmp_path):
        """After fix removes failed p5 records, a second scan detects them as gaps."""
        run_path, _ = _make_exp(tmp_path)
        dp_ids = ['dp1', 'dp2', 'dp3']
        resp_ids = ['r1', 'r2', 'r3']
        self._setup(run_path, dp_ids, resp_ids)

        # Phase 5: all records are status='failed'
        f5 = run_path / 'phase5_evaluations' / 'task.tch.jud.evaluations.jsonl'
        _write_jsonl(f5, [
            {'id': f'{rid}__jud', 'task_id': 'task', 'teacher_model_id': 'tch',
             'judge_model_id': 'jud', 'response_id': rid,
             'scores': {}, 'status': 'failed'}
            for rid in resp_ids
        ])

        # First scan: no gaps (failed records count as covered)
        report = scan_experiment(run_path)
        gaps_before = scan_coverage_gaps(run_path)
        assert gaps_before['phase5_gaps'] == [], "Failed records should count as covered"

        # Fix: remove failed records from phase5 file
        counts = fix_invalid_records(run_path, report)
        assert counts['phase5'] == 3, "All 3 failed records should be removed"

        # Second scan: now the 3 response slots are truly empty → coverage gap
        gaps_after = scan_coverage_gaps(run_path)
        assert len(gaps_after['phase5_gaps']) == 1
        assert gaps_after['phase5_gaps'][0]['missing'] == 3
        assert 'evaluation' in gaps_after['phases_to_reopen']


# ---------------------------------------------------------------------------
# collect_valid_examples
# ---------------------------------------------------------------------------

class TestCollectValidExamples:
    """collect_valid_examples() samples up to n valid records per phase."""

    def _write_p3(self, run_path, fname, records):
        f = run_path / 'phase3_datapoints' / fname
        _write_jsonl(f, records)

    def _write_p4(self, run_path, fname, records):
        f = run_path / 'phase4_responses' / fname
        _write_jsonl(f, records)

    def _write_p5(self, run_path, fname, records):
        f = run_path / 'phase5_evaluations' / fname
        _write_jsonl(f, records)

    def test_collects_up_to_n_valid_records(self, tmp_path):
        run_path, _ = _make_exp(tmp_path)
        self._write_p3(run_path, 'task.tch.datapoints.jsonl', [
            {'id': f'dp{i}', 'reference_response': f'ref {i}'} for i in range(10)
        ])
        samples = collect_valid_examples(run_path, n=3)
        assert len(samples['phase3']) == 3
        assert all('reference_response' in r for r in samples['phase3'])

    def test_skips_invalid_records(self, tmp_path):
        run_path, _ = _make_exp(tmp_path)
        self._write_p3(run_path, 'task.tch.datapoints.jsonl', [
            {'id': 'dp1', 'reference_response': ''},        # invalid
            {'id': 'dp2', 'reference_response': None},      # invalid
            {'id': 'dp3', 'reference_response': 'good'},    # valid
            {'id': 'dp4', 'status': 'failed', 'reference_response': 'ok'},  # invalid
            {'id': 'dp5', 'reference_response': 'also good'},  # valid
        ])
        samples = collect_valid_examples(run_path, n=5)
        assert len(samples['phase3']) == 2
        ids = {r['id'] for r in samples['phase3']}
        assert ids == {'dp3', 'dp5'}

    def test_returns_fewer_than_n_when_not_enough_valid(self, tmp_path):
        run_path, _ = _make_exp(tmp_path)
        self._write_p3(run_path, 'task.tch.datapoints.jsonl', [
            {'id': 'dp1', 'reference_response': 'ok'},
        ])
        samples = collect_valid_examples(run_path, n=10)
        assert len(samples['phase3']) == 1

    def test_empty_dirs_return_empty_lists(self, tmp_path):
        run_path, _ = _make_exp(tmp_path)
        samples = collect_valid_examples(run_path, n=5)
        assert samples == {'phase3': [], 'phase4': [], 'phase5': []}

    def test_samples_all_three_phases(self, tmp_path):
        run_path, _ = _make_exp(tmp_path)
        self._write_p3(run_path, 'task.tch.datapoints.jsonl', [
            {'id': 'dp1', 'reference_response': 'good ref'},
        ])
        self._write_p4(run_path, 'task.tch.stu.responses.jsonl', [
            {'id': 'r1', 'response': 'good response'},
        ])
        self._write_p5(run_path, 'task.tch.jud.evaluations.jsonl', [
            {'id': 'e1', 'response_id': 'r1', 'scores': {'quality': 'High'}},
        ])
        samples = collect_valid_examples(run_path, n=5)
        assert len(samples['phase3']) == 1
        assert len(samples['phase4']) == 1
        assert len(samples['phase5']) == 1

    def test_n_zero_returns_empty_lists(self, tmp_path):
        run_path, _ = _make_exp(tmp_path)
        self._write_p3(run_path, 'task.tch.datapoints.jsonl', [
            {'id': 'dp1', 'reference_response': 'good ref'},
        ])
        samples = collect_valid_examples(run_path, n=0)
        assert samples['phase3'] == []

    def test_results_are_deterministic_by_filename_sort(self, tmp_path):
        """Records from lexicographically earlier files appear first."""
        run_path, _ = _make_exp(tmp_path)
        self._write_p3(run_path, 'b_task.tch.datapoints.jsonl', [
            {'id': 'dp_b', 'reference_response': 'from b'},
        ])
        self._write_p3(run_path, 'a_task.tch.datapoints.jsonl', [
            {'id': 'dp_a', 'reference_response': 'from a'},
        ])
        samples = collect_valid_examples(run_path, n=1)
        # 'a_task...' sorts before 'b_task...', so dp_a should appear
        assert samples['phase3'][0]['id'] == 'dp_a'


# ---------------------------------------------------------------------------
# scan_file_breakdown
# ---------------------------------------------------------------------------

class TestScanFileBreakdown:
    """scan_file_breakdown() returns per-file valid/invalid/gap counts."""

    def _empty_gaps(self):
        return {'phase4_gaps': [], 'phase5_gaps': [], 'phases_to_reopen': set()}

    def test_all_valid_records_shows_zero_invalid(self, tmp_path):
        run_path, _ = _make_exp(tmp_path)
        fname = 'task.tch.datapoints.jsonl'
        _write_jsonl(run_path / 'phase3_datapoints' / fname, [
            {'id': f'dp{i}', 'reference_response': f'ref {i}'} for i in range(5)
        ])
        bd = scan_file_breakdown(run_path, self._empty_gaps())
        assert len(bd['phase3']) == 1
        row = bd['phase3'][0]
        assert row['file'] == fname
        assert row['valid'] == 5
        assert row['invalid'] == 0
        assert row['gaps'] == 0

    def test_mixed_valid_invalid_counted_correctly(self, tmp_path):
        run_path, _ = _make_exp(tmp_path)
        fname = 'task.tch.datapoints.jsonl'
        _write_jsonl(run_path / 'phase3_datapoints' / fname, [
            {'id': 'dp1', 'reference_response': 'ok'},      # valid
            {'id': 'dp2', 'reference_response': ''},         # invalid
            {'id': 'dp3', 'reference_response': None},       # invalid
            {'id': 'dp4', 'status': 'failed', 'reference_response': 'ok'},  # invalid
            {'id': 'dp5', 'reference_response': 'good'},     # valid
        ])
        bd = scan_file_breakdown(run_path, self._empty_gaps())
        row = bd['phase3'][0]
        assert row['valid'] == 2
        assert row['invalid'] == 3

    def test_gap_counts_attributed_from_gaps_dict(self, tmp_path):
        run_path, _ = _make_exp(tmp_path)
        fname = 'task.tch.jud.evaluations.jsonl'
        _write_jsonl(run_path / 'phase5_evaluations' / fname, [
            {'id': 'e1', 'response_id': 'r1', 'scores': {'q': 'High'}},
        ])
        gaps = {
            'phase4_gaps': [],
            'phase5_gaps': [{'file': str(run_path / 'phase5_evaluations' / fname), 'missing': 4}],
            'phases_to_reopen': {'evaluation'},
        }
        bd = scan_file_breakdown(run_path, gaps)
        row = bd['phase5'][0]
        assert row['file'] == fname
        assert row['valid'] == 1
        assert row['invalid'] == 0
        assert row['gaps'] == 4

    def test_multiple_files_listed(self, tmp_path):
        run_path, _ = _make_exp(tmp_path)
        for i in range(3):
            fname = f'task{i}.tch.datapoints.jsonl'
            _write_jsonl(run_path / 'phase3_datapoints' / fname, [
                {'id': f'dp{i}', 'reference_response': f'ref {i}'},
            ])
        bd = scan_file_breakdown(run_path, self._empty_gaps())
        assert len(bd['phase3']) == 3
        # Returned in sorted order
        files = [row['file'] for row in bd['phase3']]
        assert files == sorted(files)

    def test_empty_dirs_return_empty_lists(self, tmp_path):
        run_path, _ = _make_exp(tmp_path)
        bd = scan_file_breakdown(run_path, self._empty_gaps())
        assert bd == {'phase3': [], 'phase4': [], 'phase5': []}

    def test_non_dict_json_line_counted_as_invalid(self, tmp_path):
        run_path, _ = _make_exp(tmp_path)
        fname = 'task.tch.datapoints.jsonl'
        f = run_path / 'phase3_datapoints' / fname
        f.parent.mkdir(parents=True, exist_ok=True)
        # Write one valid dict and one JSON string (non-dict)
        f.write_text(
            '{"id": "dp1", "reference_response": "ok"}\n'
            '"this is a plain JSON string, not a dict"\n',
            encoding='utf-8',
        )
        bd = scan_file_breakdown(run_path, self._empty_gaps())
        row = bd['phase3'][0]
        assert row['valid'] == 1
        assert row['invalid'] == 1

    def test_phase4_and_phase5_files_included(self, tmp_path):
        run_path, _ = _make_exp(tmp_path)
        _write_jsonl(run_path / 'phase4_responses' / 'task.tch.stu.responses.jsonl', [
            {'id': 'r1', 'response': 'answer'},
            {'id': 'r2', 'response': ''},  # invalid
        ])
        _write_jsonl(run_path / 'phase5_evaluations' / 'task.tch.jud.evaluations.jsonl', [
            {'id': 'e1', 'response_id': 'r1', 'scores': {'q': 'High'}},
        ])
        bd = scan_file_breakdown(run_path, self._empty_gaps())
        assert len(bd['phase4']) == 1
        assert bd['phase4'][0]['valid'] == 1
        assert bd['phase4'][0]['invalid'] == 1
        assert len(bd['phase5']) == 1
        assert bd['phase5'][0]['valid'] == 1
        assert bd['phase5'][0]['invalid'] == 0
