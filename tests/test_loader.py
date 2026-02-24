"""Tests for coeval.analyze.loader — EES data loading and validity classification.

All tests use tmp_path; no LLM calls, no network.
"""
import json
import shutil

import pytest
import yaml

from coeval.analyze.loader import (
    EvalRecord,
    AnalyticalUnit,
    EESDataModel,
    SCORE_MAP,
    VALID_SCORES,
    load_ees,
    score_norm,
    _iter_jsonl,
    _classify_eval_record,
    _phase_tag_from_path,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write_jsonl(path, records):
    path.write_text('\n'.join(json.dumps(r) for r in records), encoding='utf-8')


def _make_ees_folder(
    tmp_path,
    *,
    meta_overrides=None,
    rubric=None,
    datapoints=None,
    responses=None,
    evaluations=None,
    config_override=None,
    status='completed',
):
    """Build a minimal valid EES experiment folder under tmp_path/exp01."""
    run = tmp_path / 'exp01'
    run.mkdir(exist_ok=True)

    # meta.json
    meta = {'experiment_id': 'exp01', 'status': status, **(meta_overrides or {})}
    (run / 'meta.json').write_text(json.dumps(meta), encoding='utf-8')

    # config.yaml
    cfg = config_override or {
        'models': [
            {'name': 'teacher1', 'interface': 'openai', 'parameters': {}, 'roles': ['teacher']},
            {'name': 'student1', 'interface': 'openai', 'parameters': {}, 'roles': ['student']},
            {'name': 'judge1',   'interface': 'openai', 'parameters': {}, 'roles': ['judge']},
        ],
        'tasks': [{'name': 'task1', 'description': 'T1', 'output_description': 'OD'}],
        'experiment': {'id': 'exp01', 'storage_folder': str(tmp_path)},
    }
    (run / 'config.yaml').write_text(yaml.dump(cfg), encoding='utf-8')

    # phase2_rubric/
    (run / 'phase2_rubric').mkdir(exist_ok=True)
    task_rubric = rubric or {'accuracy': 'Is it accurate?', 'format': 'Is it well-formatted?'}
    (run / 'phase2_rubric' / 'task1.rubric.json').write_text(
        json.dumps(task_rubric), encoding='utf-8',
    )

    # phase3_datapoints/
    (run / 'phase3_datapoints').mkdir(exist_ok=True)
    dps = datapoints or [
        {
            'id': 'dp001', 'task_id': 'task1', 'teacher_model_id': 'teacher1',
            'prompt': 'Hello?', 'response': 'Hi',
            'sampled_target_attributes': {'sentiment': 'positive'},
        },
        {
            'id': 'dp002', 'task_id': 'task1', 'teacher_model_id': 'teacher1',
            'prompt': 'Bye?', 'response': 'Farewell',
            'sampled_target_attributes': {'sentiment': 'negative'},
        },
    ]
    _write_jsonl(run / 'phase3_datapoints' / 'teacher1.task1.datapoints.jsonl', dps)

    # phase4_responses/
    (run / 'phase4_responses').mkdir(exist_ok=True)
    resps = responses or [
        {
            'id': 'resp001', 'datapoint_id': 'dp001', 'task_id': 'task1',
            'teacher_model_id': 'teacher1', 'student_model_id': 'student1',
            'response': 'Positive',
        },
        {
            'id': 'resp002', 'datapoint_id': 'dp002', 'task_id': 'task1',
            'teacher_model_id': 'teacher1', 'student_model_id': 'student1',
            'response': 'Negative',
        },
    ]
    _write_jsonl(run / 'phase4_responses' / 'student1.teacher1.task1.responses.jsonl', resps)

    # phase5_evaluations/
    (run / 'phase5_evaluations').mkdir(exist_ok=True)
    evals = evaluations or [
        {
            'id': 'ev001', 'response_id': 'resp001', 'datapoint_id': 'dp001',
            'task_id': 'task1', 'teacher_model_id': 'teacher1',
            'judge_model_id': 'judge1',
            'scores': {'accuracy': 'High', 'format': 'High'},
            'evaluated_at': '2024-01-01T00:00:00Z',
        },
        {
            'id': 'ev002', 'response_id': 'resp002', 'datapoint_id': 'dp002',
            'task_id': 'task1', 'teacher_model_id': 'teacher1',
            'judge_model_id': 'judge1',
            'scores': {'accuracy': 'Low', 'format': 'Medium'},
            'evaluated_at': '2024-01-01T00:01:00Z',
        },
    ]
    _write_jsonl(run / 'phase5_evaluations' / 'judge1.teacher1.task1.evaluations.jsonl', evals)

    return run


# ---------------------------------------------------------------------------
# score_norm()
# ---------------------------------------------------------------------------

class TestScoreNorm:
    def test_high(self):
        assert score_norm('High') == 1.0

    def test_medium(self):
        assert score_norm('Medium') == 0.5

    def test_low(self):
        assert score_norm('Low') == 0.0

    def test_unknown_returns_zero(self):
        assert score_norm('Unknown') == 0.0

    def test_empty_string_returns_zero(self):
        assert score_norm('') == 0.0

    def test_case_sensitive(self):
        # 'high' (lowercase) is not a recognised value
        assert score_norm('high') == 0.0


# ---------------------------------------------------------------------------
# _iter_jsonl()
# ---------------------------------------------------------------------------

class TestIterJsonl:
    def test_valid_lines(self, tmp_path):
        f = tmp_path / 'test.jsonl'
        f.write_text('{"a": 1}\n{"b": 2}\n', encoding='utf-8')
        warnings = []
        result = _iter_jsonl(f, warnings)
        assert result == [{'a': 1}, {'b': 2}]
        assert not warnings

    def test_skip_blank_lines(self, tmp_path):
        f = tmp_path / 'test.jsonl'
        f.write_text('{"a": 1}\n\n\n{"b": 2}\n', encoding='utf-8')
        warnings = []
        result = _iter_jsonl(f, warnings)
        assert len(result) == 2

    def test_invalid_line_adds_warning_and_skips_line(self, tmp_path):
        phase5 = tmp_path / 'phase5_evaluations'
        phase5.mkdir()
        f = phase5 / 'x.evaluations.jsonl'
        f.write_text('{"a": 1}\nNOT_JSON\n{"b": 2}\n', encoding='utf-8')
        warnings = []
        result = _iter_jsonl(f, warnings)
        assert len(result) == 2            # invalid line skipped
        assert len(warnings) == 1
        assert 'PARSE_ERROR_P5' in warnings[0]

    def test_nonexistent_file_returns_empty_no_warning(self, tmp_path):
        f = tmp_path / 'nonexistent.jsonl'
        warnings = []
        result = _iter_jsonl(f, warnings)
        assert result == []
        assert not warnings

    def test_phase_tags_p3(self, tmp_path):
        d = tmp_path / 'phase3_datapoints'
        d.mkdir()
        (d / 'x.jsonl').write_text('BAD', encoding='utf-8')
        warnings = []
        _iter_jsonl(d / 'x.jsonl', warnings)
        assert 'PARSE_ERROR_P3' in warnings[-1]

    def test_phase_tags_p4(self, tmp_path):
        d = tmp_path / 'phase4_responses'
        d.mkdir()
        (d / 'x.jsonl').write_text('BAD', encoding='utf-8')
        warnings = []
        _iter_jsonl(d / 'x.jsonl', warnings)
        assert 'PARSE_ERROR_P4' in warnings[-1]

    def test_phase_tags_p5(self, tmp_path):
        d = tmp_path / 'phase5_evaluations'
        d.mkdir()
        (d / 'x.jsonl').write_text('BAD', encoding='utf-8')
        warnings = []
        _iter_jsonl(d / 'x.jsonl', warnings)
        assert 'PARSE_ERROR_P5' in warnings[-1]


# ---------------------------------------------------------------------------
# _classify_eval_record()
# ---------------------------------------------------------------------------

class TestClassifyEvalRecord:
    """Unit tests for validity classification logic (REQ-A-5.2.1)."""

    def _line(self):
        return {
            'id': 'ev001',
            'response_id': 'resp001',
            'datapoint_id': 'dp001',
            'task_id': 'task1',
            'teacher_model_id': 'teacher1',
            'judge_model_id': 'judge1',
            'scores': {'accuracy': 'High', 'format': 'Medium'},
            'evaluated_at': '2024-01-01T00:00:00Z',
        }

    def _responses(self):
        return {'resp001': {'student_model_id': 'student1', 'id': 'resp001'}}

    def _datapoints(self):
        return {'dp001': {'id': 'dp001', 'task_id': 'task1'}}

    def _rubric_keys(self):
        return {'task1': {'accuracy', 'format'}}

    def test_valid_record(self):
        rec = _classify_eval_record(
            line=self._line(),
            responses=self._responses(),
            datapoints=self._datapoints(),
            rubric_keys=self._rubric_keys(),
            load_warnings=[],
        )
        assert rec.valid is True
        assert rec.error_codes == []
        assert rec.student_model_id == 'student1'
        assert rec.is_self_judging is False
        assert rec.is_self_teaching is False

    def test_missing_response_error(self):
        rec = _classify_eval_record(
            line=self._line(),
            responses={},
            datapoints=self._datapoints(),
            rubric_keys=self._rubric_keys(),
            load_warnings=[],
        )
        assert rec.valid is False
        assert 'MISSING_RESPONSE' in rec.error_codes

    def test_missing_datapoint_error(self):
        rec = _classify_eval_record(
            line=self._line(),
            responses=self._responses(),
            datapoints={},
            rubric_keys=self._rubric_keys(),
            load_warnings=[],
        )
        assert rec.valid is False
        assert 'MISSING_DATAPOINT' in rec.error_codes

    def test_incomplete_scores_missing_aspect(self):
        line = self._line()
        line['scores'] = {'accuracy': 'High'}       # missing 'format'
        rec = _classify_eval_record(
            line=line,
            responses=self._responses(),
            datapoints=self._datapoints(),
            rubric_keys=self._rubric_keys(),
            load_warnings=[],
        )
        assert rec.valid is False
        assert 'INCOMPLETE_SCORES' in rec.error_codes

    def test_invalid_score_value(self):
        line = self._line()
        line['scores'] = {'accuracy': 'Medium', 'format': 'INVALID'}
        rec = _classify_eval_record(
            line=line,
            responses=self._responses(),
            datapoints=self._datapoints(),
            rubric_keys=self._rubric_keys(),
            load_warnings=[],
        )
        assert rec.valid is False
        assert 'INVALID_SCORE_VALUE' in rec.error_codes

    def test_scores_not_dict_gives_incomplete_error(self):
        line = self._line()
        line['scores'] = 'not-a-dict'
        rec = _classify_eval_record(
            line=line,
            responses=self._responses(),
            datapoints=self._datapoints(),
            rubric_keys=self._rubric_keys(),
            load_warnings=[],
        )
        assert rec.valid is False
        assert 'INCOMPLETE_SCORES' in rec.error_codes

    def test_multiple_errors_accumulated(self):
        """Both MISSING_RESPONSE and MISSING_DATAPOINT can appear together."""
        rec = _classify_eval_record(
            line=self._line(),
            responses={},
            datapoints={},
            rubric_keys=self._rubric_keys(),
            load_warnings=[],
        )
        assert rec.valid is False
        assert 'MISSING_RESPONSE' in rec.error_codes
        assert 'MISSING_DATAPOINT' in rec.error_codes

    def test_self_judging_flag(self):
        line = self._line()
        line['judge_model_id'] = 'student1'
        rec = _classify_eval_record(
            line=line,
            responses={'resp001': {'student_model_id': 'student1'}},
            datapoints=self._datapoints(),
            rubric_keys=self._rubric_keys(),
            load_warnings=[],
        )
        assert rec.is_self_judging is True
        assert rec.is_self_teaching is False

    def test_self_teaching_flag(self):
        line = self._line()
        line['teacher_model_id'] = 'student1'
        rec = _classify_eval_record(
            line=line,
            responses={'resp001': {'student_model_id': 'student1'}},
            datapoints=self._datapoints(),
            rubric_keys=self._rubric_keys(),
            load_warnings=[],
        )
        assert rec.is_self_teaching is True
        assert rec.is_self_judging is False

    def test_unknown_task_rubric_skips_key_validation(self):
        """No rubric entry → score keys not validated, only values."""
        rec = _classify_eval_record(
            line=self._line(),
            responses=self._responses(),
            datapoints=self._datapoints(),
            rubric_keys={},           # no rubric for task1
            load_warnings=[],
        )
        # Valid scores → should be valid even without rubric key check
        assert rec.valid is True

    def test_student_model_id_from_phase4_join(self):
        """student_model_id must be resolved by joining Phase 4 response."""
        rec = _classify_eval_record(
            line=self._line(),
            responses={'resp001': {'student_model_id': 'my_student'}},
            datapoints=self._datapoints(),
            rubric_keys=self._rubric_keys(),
            load_warnings=[],
        )
        assert rec.student_model_id == 'my_student'


# ---------------------------------------------------------------------------
# load_ees() — end-to-end
# ---------------------------------------------------------------------------

class TestLoadEes:
    def test_happy_path(self, tmp_path):
        run = _make_ees_folder(tmp_path)
        model = load_ees(run)
        assert model.valid_records == 2
        assert model.total_records == 2
        # 2 records × 2 aspects = 4 analytical units
        assert len(model.units) == 4
        assert 'task1' in model.tasks
        assert 'teacher1' in model.teachers
        assert 'student1' in model.students
        assert 'judge1' in model.judges

    def test_missing_meta_raises_file_not_found(self, tmp_path):
        run = tmp_path / 'no_meta'
        run.mkdir()
        with pytest.raises(FileNotFoundError, match='meta.json'):
            load_ees(run)

    def test_partial_experiment_adds_warning(self, tmp_path):
        run = _make_ees_folder(tmp_path, status='running')
        model = load_ees(run, partial_ok=False)
        assert model.is_partial is True
        assert any('not completed' in w for w in model.load_warnings)

    def test_partial_ok_suppresses_status_warning(self, tmp_path):
        run = _make_ees_folder(tmp_path, status='running')
        model = load_ees(run, partial_ok=True)
        assert not any('not completed' in w for w in model.load_warnings)

    def test_completed_status_is_not_partial(self, tmp_path):
        run = _make_ees_folder(tmp_path, status='completed')
        model = load_ees(run)
        assert model.is_partial is False

    def test_missing_phase3_dir_adds_warning(self, tmp_path):
        run = _make_ees_folder(tmp_path)
        shutil.rmtree(run / 'phase3_datapoints')
        model = load_ees(run, partial_ok=True)
        assert any('phase3_datapoints' in w for w in model.load_warnings)

    def test_missing_phase5_dir_adds_warning_and_empty_units(self, tmp_path):
        run = _make_ees_folder(tmp_path)
        shutil.rmtree(run / 'phase5_evaluations')
        model = load_ees(run, partial_ok=True)
        assert any('phase5_evaluations' in w for w in model.load_warnings)
        assert model.total_records == 0
        assert len(model.units) == 0

    def test_invalid_eval_record_not_in_units(self, tmp_path):
        bad_eval = {
            'id': 'ev999', 'response_id': 'NONEXISTENT', 'datapoint_id': 'dp001',
            'task_id': 'task1', 'teacher_model_id': 'teacher1',
            'judge_model_id': 'judge1',
            'scores': {'accuracy': 'High', 'format': 'Medium'},
            'evaluated_at': '2024-01-01T00:00:00Z',
        }
        run = _make_ees_folder(tmp_path, evaluations=[bad_eval])
        model = load_ees(run, partial_ok=True)
        assert model.total_records == 1
        assert model.valid_records == 0
        assert len(model.units) == 0
        assert 'MISSING_RESPONSE' in model.eval_records[0].error_codes

    def test_units_expanded_per_rubric_aspect(self, tmp_path):
        """Each valid record expands into one AnalyticalUnit per rubric aspect."""
        run = _make_ees_folder(tmp_path)
        model = load_ees(run)
        assert len(model.units) == 4
        aspects = {u.rubric_aspect for u in model.units}
        assert aspects == {'accuracy', 'format'}

    def test_unit_score_norm_values(self, tmp_path):
        """Units carry correctly-normalised score_norm values."""
        run = _make_ees_folder(tmp_path)
        model = load_ees(run)
        # ev001: both aspects 'High' → score_norm = 1.0
        ev001_units = [u for u in model.units if u.response_id == 'resp001']
        assert all(u.score_norm == 1.0 for u in ev001_units)
        # ev002: accuracy='Low'=0.0, format='Medium'=0.5
        ev002_units = [u for u in model.units if u.response_id == 'resp002']
        acc_units = [u for u in ev002_units if u.rubric_aspect == 'accuracy']
        fmt_units = [u for u in ev002_units if u.rubric_aspect == 'format']
        assert acc_units[0].score_norm == pytest.approx(0.0)
        assert fmt_units[0].score_norm == pytest.approx(0.5)

    def test_self_judging_count(self, tmp_path):
        evals = [
            {
                'id': 'ev001', 'response_id': 'resp001', 'datapoint_id': 'dp001',
                'task_id': 'task1', 'teacher_model_id': 'teacher1',
                'judge_model_id': 'student1',  # == student
                'scores': {'accuracy': 'High', 'format': 'High'},
                'evaluated_at': '2024-01-01T00:00:00Z',
            },
        ]
        run = _make_ees_folder(tmp_path, evaluations=evals)
        model = load_ees(run, partial_ok=True)
        assert model.self_judging_count == 1
        assert model.self_teaching_count == 0

    def test_target_attrs_collected(self, tmp_path):
        run = _make_ees_folder(tmp_path)
        model = load_ees(run)
        assert 'task1' in model.target_attrs_by_task
        assert 'sentiment' in model.target_attrs_by_task['task1']
        assert set(model.target_attrs_by_task['task1']['sentiment']) == {'positive', 'negative'}

    def test_no_config_yaml_adds_warning_and_empty_config(self, tmp_path):
        run = _make_ees_folder(tmp_path)
        (run / 'config.yaml').unlink()
        model = load_ees(run, partial_ok=True)
        assert any('config.yaml' in w for w in model.load_warnings)
        assert model.config == {}

    def test_dimensions_from_config_supplemented(self, tmp_path):
        """Dimensions discovered from config.yaml (teachers/students/judges)."""
        run = _make_ees_folder(tmp_path)
        model = load_ees(run)
        # All three roles should be found via config
        assert 'teacher1' in model.teachers
        assert 'student1' in model.students
        assert 'judge1' in model.judges

    def test_aspects_by_task_from_rubric(self, tmp_path):
        run = _make_ees_folder(tmp_path)
        model = load_ees(run)
        assert 'task1' in model.aspects_by_task
        assert set(model.aspects_by_task['task1']) == {'accuracy', 'format'}

    def test_run_path_stored(self, tmp_path):
        run = _make_ees_folder(tmp_path)
        model = load_ees(run)
        assert model.run_path == run

    def test_bad_rubric_json_adds_warning(self, tmp_path):
        run = _make_ees_folder(tmp_path)
        (run / 'phase2_rubric' / 'task1.rubric.json').write_text('NOT JSON', encoding='utf-8')
        model = load_ees(run, partial_ok=True)
        assert any('rubric' in w.lower() for w in model.load_warnings)
