"""
Tests for coeval repair — invalid-record scanning and marking.

Covers:
- scan_experiment: detects invalid records in all three phases
- fix_invalid_records: marks invalid records as status='failed'
- storage.mark_failed_records: low-level rewrite helper
- storage.count_datapoints: skips status='failed' records (Extend mode fix)
"""
import json
import pytest
from pathlib import Path

from experiments.storage import ExperimentStorage
from experiments.commands.repair_cmd import (
    scan_experiment,
    fix_invalid_records,
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

        records = _read_jsonl(fpath)
        assert 'status' not in records[0]          # e1 untouched
        assert records[1]['status'] == 'failed'     # e2 marked


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

    def test_extend_mode_regenerates_after_repair(self, tmp_path):
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
        # Extend mode would compute: total=3, existing=2 → generate 1 more ✓
