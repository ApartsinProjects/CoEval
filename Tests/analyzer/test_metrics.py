"""Tests for coeval.analyze.metrics — all metric computations (REQ-A-5.x).

Pure-function tests using AnalyticalUnit instances constructed directly.
No LLM calls, no network, no filesystem.
"""
import math

import pytest

from analyzer.loader import AnalyticalUnit, EESDataModel, SCORE_MAP
from analyzer.metrics import (
    AgreementResult,
    JudgeScoreResult,
    RobustFilterResult,
    StudentScoreResult,
    TeacherScoreResult,
    compute_agreement,
    compute_all_agreements,
    compute_judge_scores,
    compute_robust_student_scores,
    compute_student_scores,
    compute_teacher_scores,
    kappa_label,
    normalize,
    robust_filter,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _unit(
    response_id='r1',
    datapoint_id='dp1',
    task_id='task1',
    teacher='T1',
    student='S1',
    judge='J1',
    aspect='acc',
    score='High',
    evaluated_at='2024-01-01T00:00:00Z',
) -> AnalyticalUnit:
    return AnalyticalUnit(
        response_id=response_id,
        datapoint_id=datapoint_id,
        task_id=task_id,
        teacher_model_id=teacher,
        student_model_id=student,
        judge_model_id=judge,
        rubric_aspect=aspect,
        score=score,
        score_norm=SCORE_MAP.get(score, 0.0),
        is_self_judging=(judge == student),
        is_self_teaching=(teacher == student),
        evaluated_at=evaluated_at,
    )


def _make_model(tmp_path, units, datapoints=None, teachers=None, students=None, judges=None):
    """Build a minimal EESDataModel around the given units."""
    datapoints = datapoints or {
        'dp1': {'id': 'dp1', 'teacher_model_id': 'T1', 'task_id': 'task1'},
        'dp2': {'id': 'dp2', 'teacher_model_id': 'T1', 'task_id': 'task1'},
    }
    all_teachers = teachers or sorted({u.teacher_model_id for u in units})
    all_students = students or sorted({u.student_model_id for u in units})
    all_judges = judges or sorted({u.judge_model_id for u in units})
    return EESDataModel(
        run_path=tmp_path,
        meta={'experiment_id': 'test', 'status': 'completed'},
        config={},
        rubrics={'task1': {'acc': 'Accuracy', 'fmt': 'Format'}},
        datapoints=datapoints,
        responses={},
        eval_records=[],
        units=units,
        tasks=['task1'],
        teachers=all_teachers,
        students=all_students,
        judges=all_judges,
        aspects_by_task={'task1': ['acc', 'fmt']},
        target_attrs_by_task={},
        total_records=0,
        valid_records=0,
        self_judging_count=0,
        self_teaching_count=0,
        both_count=0,
        load_warnings=[],
        is_partial=False,
    )


# ---------------------------------------------------------------------------
# 5.1 normalize()
# ---------------------------------------------------------------------------

class TestNormalize:
    def test_high(self):
        assert normalize('High') == 1.0

    def test_medium(self):
        assert normalize('Medium') == 0.5

    def test_low(self):
        assert normalize('Low') == 0.0

    def test_unknown_returns_zero(self):
        assert normalize('X') == 0.0

    def test_all_valid_scores(self):
        for score, expected in [('High', 1.0), ('Medium', 0.5), ('Low', 0.0)]:
            assert normalize(score) == expected


# ---------------------------------------------------------------------------
# 5.3 compute_agreement()
# ---------------------------------------------------------------------------

class TestComputeAgreement:

    def _perfect_units(self):
        """J1 and J2 give identical scores on 3 responses."""
        units = []
        for resp_id, score in [('r1', 'High'), ('r2', 'Low'), ('r3', 'Medium')]:
            for judge in ('J1', 'J2'):
                units.append(_unit(response_id=resp_id, judge=judge, score=score))
        return units

    def test_perfect_agreement_spa_wpa_kappa(self):
        res = compute_agreement(self._perfect_units(), 'J1', 'J2')
        assert res.spa == pytest.approx(1.0)
        assert res.wpa == pytest.approx(1.0)
        # kappa with all same distribution → 1.0
        assert res.kappa == pytest.approx(1.0) or res.kappa is None
        assert res.count == 3

    def test_zero_agreement_high_vs_low(self):
        """J1 always High, J2 always Low on same responses → SPA = 0."""
        units = []
        for resp_id in ('r1', 'r2'):
            units.append(_unit(response_id=resp_id, judge='J1', score='High'))
            units.append(_unit(response_id=resp_id, judge='J2', score='Low'))
        res = compute_agreement(units, 'J1', 'J2')
        assert res.spa == pytest.approx(0.0)
        assert res.wpa == pytest.approx(0.0)
        assert res.count == 2

    def test_no_common_pairs_returns_none_metrics(self):
        """Disjoint response sets → no common evaluations."""
        units = [
            _unit(response_id='r1', judge='J1', score='High'),
            _unit(response_id='r2', judge='J2', score='High'),
        ]
        res = compute_agreement(units, 'J1', 'J2')
        assert res.spa is None
        assert res.wpa is None
        assert res.kappa is None
        assert res.count == 0

    def test_partial_agreement_spa(self):
        """2 agree, 2 disagree → SPA = 0.5."""
        units = []
        for resp_id, s1, s2 in [
            ('r1', 'High',   'High'),
            ('r2', 'Low',    'Low'),
            ('r3', 'High',   'Low'),
            ('r4', 'Medium', 'Low'),
        ]:
            units.append(_unit(response_id=resp_id, judge='J1', score=s1))
            units.append(_unit(response_id=resp_id, judge='J2', score=s2))
        res = compute_agreement(units, 'J1', 'J2')
        assert res.spa == pytest.approx(0.5)
        assert res.count == 4

    def test_wpa_high_vs_medium(self):
        """Adjacent scores (High vs Medium) get WPA weight 0.5."""
        units = [
            _unit(response_id='r1', judge='J1', score='High'),
            _unit(response_id='r1', judge='J2', score='Medium'),
        ]
        res = compute_agreement(units, 'J1', 'J2')
        assert res.wpa == pytest.approx(0.5)

    def test_wpa_high_vs_low(self):
        """Extreme disagreement (High vs Low) gets WPA weight 0.0."""
        units = [
            _unit(response_id='r1', judge='J1', score='High'),
            _unit(response_id='r1', judge='J2', score='Low'),
        ]
        res = compute_agreement(units, 'J1', 'J2')
        assert res.wpa == pytest.approx(0.0)

    def test_symmetry_spa_wpa_kappa(self):
        """compute_agreement(J1,J2) == compute_agreement(J2,J1) (symmetry)."""
        units = []
        for resp_id, s1, s2 in [('r1', 'High', 'Low'), ('r2', 'Medium', 'Medium')]:
            units.append(_unit(response_id=resp_id, judge='J1', score=s1))
            units.append(_unit(response_id=resp_id, judge='J2', score=s2))
        r1 = compute_agreement(units, 'J1', 'J2')
        r2 = compute_agreement(units, 'J2', 'J1')
        assert r1.spa == pytest.approx(r2.spa)
        assert r1.wpa == pytest.approx(r2.wpa)
        if r1.kappa is not None and r2.kappa is not None:
            assert r1.kappa == pytest.approx(r2.kappa)

    def test_kappa_undefined_when_all_same_class(self):
        """When both judges always give 'High', p_e = 1 → kappa undefined."""
        units = [
            _unit(response_id='r1', judge='J1', score='High'),
            _unit(response_id='r1', judge='J2', score='High'),
        ]
        res = compute_agreement(units, 'J1', 'J2')
        assert res.kappa is None

    def test_result_is_named_tuple(self):
        res = compute_agreement(self._perfect_units(), 'J1', 'J2')
        assert isinstance(res, AgreementResult)
        assert hasattr(res, 'spa')
        assert hasattr(res, 'wpa')
        assert hasattr(res, 'kappa')
        assert hasattr(res, 'count')


# ---------------------------------------------------------------------------
# compute_all_agreements()
# ---------------------------------------------------------------------------

class TestComputeAllAgreements:
    def test_two_judges_symmetric_storage(self):
        units = [
            _unit(response_id='r1', judge='J1', score='High'),
            _unit(response_id='r1', judge='J2', score='High'),
        ]
        results = compute_all_agreements(units, ['J1', 'J2'])
        assert ('J1', 'J2') in results
        assert ('J2', 'J1') in results
        # Symmetric: same values
        assert results[('J1', 'J2')].spa == results[('J2', 'J1')].spa

    def test_three_judges_six_entries(self):
        """3 judges → 3 pairs → 6 entries (both orderings)."""
        units = [
            _unit(response_id='r1', judge='J1', score='High'),
            _unit(response_id='r1', judge='J2', score='High'),
            _unit(response_id='r1', judge='J3', score='Low'),
        ]
        results = compute_all_agreements(units, ['J1', 'J2', 'J3'])
        assert len(results) == 6

    def test_single_judge_empty_result(self):
        units = [_unit(response_id='r1', judge='J1', score='High')]
        results = compute_all_agreements(units, ['J1'])
        assert results == {}


# ---------------------------------------------------------------------------
# 5.4 compute_judge_scores()
# ---------------------------------------------------------------------------

class TestComputeJudgeScores:
    def test_degenerate_single_judge_returns_1(self):
        units = [_unit(judge='J1', score='High')]
        results = compute_judge_scores(units, ['J1'])
        assert results['J1'].degenerate is True
        assert results['J1'].spa_mean == pytest.approx(1.0)
        assert results['J1'].wpa_mean == pytest.approx(1.0)
        assert results['J1'].kappa_mean == pytest.approx(1.0)

    def test_two_judges_perfect_agreement(self):
        units = [
            _unit(response_id='r1', judge='J1', score='High'),
            _unit(response_id='r1', judge='J2', score='High'),
        ]
        results = compute_judge_scores(units, ['J1', 'J2'])
        assert results['J1'].degenerate is False
        assert results['J1'].spa_mean == pytest.approx(1.0)
        assert results['J2'].spa_mean == pytest.approx(1.0)

    def test_two_judges_zero_agreement(self):
        units = [
            _unit(response_id='r1', judge='J1', score='High'),
            _unit(response_id='r1', judge='J2', score='Low'),
        ]
        results = compute_judge_scores(units, ['J1', 'J2'])
        assert results['J1'].spa_mean == pytest.approx(0.0)

    def test_empty_judges_list_empty_result(self):
        results = compute_judge_scores([], [])
        assert results == {}

    def test_precomputed_agreements_reused(self):
        """If agreements provided, they're used directly."""
        units = [
            _unit(response_id='r1', judge='J1', score='High'),
            _unit(response_id='r1', judge='J2', score='High'),
        ]
        agreements = compute_all_agreements(units, ['J1', 'J2'])
        results_with = compute_judge_scores(units, ['J1', 'J2'], agreements)
        results_without = compute_judge_scores(units, ['J1', 'J2'])
        assert results_with['J1'].spa_mean == pytest.approx(results_without['J1'].spa_mean)

    def test_weighted_mean_accounts_for_count(self):
        """Weighted mean should weight by number of common evaluations."""
        # J1 vs J2: 2 common pairs, perfect agreement
        units = [
            _unit(response_id='r1', judge='J1', score='High'),
            _unit(response_id='r1', judge='J2', score='High'),
            _unit(response_id='r2', judge='J1', score='Low'),
            _unit(response_id='r2', judge='J2', score='Low'),
        ]
        results = compute_judge_scores(units, ['J1', 'J2'])
        # Perfect agreement → weighted == unweighted
        assert results['J1'].spa_weighted == pytest.approx(1.0)


# ---------------------------------------------------------------------------
# 5.3.3 kappa_label()
# ---------------------------------------------------------------------------

class TestKappaLabel:
    def test_none_returns_na(self):
        assert kappa_label(None) == 'N/A'

    def test_negative_kappa(self):
        assert kappa_label(-0.1) == 'Less than chance'

    def test_zero(self):
        assert kappa_label(0.0) == 'Slight'

    def test_slight_boundary(self):
        assert kappa_label(0.20) == 'Slight'

    def test_fair(self):
        assert kappa_label(0.30) == 'Fair'

    def test_fair_boundary(self):
        assert kappa_label(0.40) == 'Fair'

    def test_moderate(self):
        assert kappa_label(0.50) == 'Moderate'

    def test_moderate_boundary(self):
        assert kappa_label(0.60) == 'Moderate'

    def test_substantial(self):
        assert kappa_label(0.70) == 'Substantial'

    def test_substantial_boundary(self):
        assert kappa_label(0.80) == 'Substantial'

    def test_almost_perfect(self):
        assert kappa_label(0.90) == 'Almost perfect'

    def test_perfect_one(self):
        assert kappa_label(1.0) == 'Almost perfect'


# ---------------------------------------------------------------------------
# 5.5 compute_teacher_scores()
# ---------------------------------------------------------------------------

class TestComputeTeacherScores:
    def _high_low_units(self):
        """T1 with 2 students: S1 always High, S2 always Low — high differentiation."""
        units = []
        for dp_id in ('dp1', 'dp2'):
            for student, score in [('S1', 'High'), ('S2', 'Low')]:
                units.append(_unit(
                    datapoint_id=dp_id, teacher='T1',
                    student=student, score=score,
                ))
        return units

    def test_returns_teacher_score_result(self):
        units = self._high_low_units()
        results = compute_teacher_scores(units, ['T1'], ['S1', 'S2'])
        assert 'T1' in results
        r = results['T1']
        assert isinstance(r, TeacherScoreResult)
        assert isinstance(r.v1, float)
        assert isinstance(r.s2, float)
        assert isinstance(r.r3, float)

    def test_high_differentiation_gives_positive_scores(self):
        """S1=High vs S2=Low produces positive v1, s2, r3."""
        results = compute_teacher_scores(self._high_low_units(), ['T1'], ['S1', 'S2'])
        r = results['T1']
        assert r.v1 > 0.0
        assert r.s2 > 0.0
        assert r.r3 > 0.0

    def test_no_differentiation_gives_zero(self):
        """All students score Medium → zero differentiation."""
        units = []
        for dp_id in ('dp1', 'dp2'):
            for student in ('S1', 'S2'):
                units.append(_unit(
                    datapoint_id=dp_id, teacher='T1',
                    student=student, score='Medium',
                ))
        results = compute_teacher_scores(units, ['T1'], ['S1', 'S2'])
        r = results['T1']
        assert r.v1 == pytest.approx(0.0)
        assert r.s2 == pytest.approx(0.0)
        assert r.r3 == pytest.approx(0.0)

    def test_judge_filter_excludes_other_judges(self):
        units = self._high_low_units()
        # Add contradicting J2 units (all Medium → would reduce differentiation)
        for dp_id in ('dp1', 'dp2'):
            for student in ('S1', 'S2'):
                units.append(_unit(
                    datapoint_id=dp_id, teacher='T1',
                    student=student, judge='J2', score='Medium',
                ))
        # Filtered to J1 only
        r_filtered = compute_teacher_scores(units, ['T1'], ['S1', 'S2'], judge_filter={'J1'})
        # J1-only units: S1=High, S2=Low → high diff
        assert r_filtered['T1'].v1 > 0.0

    def test_single_student_zero_differentiation(self):
        """With only 1 student, variance/range/stdev = 0."""
        units = [
            _unit(datapoint_id='dp1', teacher='T1', student='S1', score='High'),
            _unit(datapoint_id='dp2', teacher='T1', student='S1', score='High'),
        ]
        results = compute_teacher_scores(units, ['T1'], ['S1'])
        r = results['T1']
        assert r.v1 == pytest.approx(0.0)
        assert r.r3 == pytest.approx(0.0)

    def test_multiple_judges_averaged(self):
        """Multiple judges' scores are averaged per (dp, student, aspect)."""
        units = [
            _unit(datapoint_id='dp1', teacher='T1', student='S1', judge='J1', score='High'),
            _unit(datapoint_id='dp1', teacher='T1', student='S1', judge='J2', score='Low'),
            _unit(datapoint_id='dp1', teacher='T1', student='S2', judge='J1', score='High'),
            _unit(datapoint_id='dp1', teacher='T1', student='S2', judge='J2', score='High'),
        ]
        # Should not raise
        results = compute_teacher_scores(units, ['T1'], ['S1', 'S2'])
        assert 'T1' in results


# ---------------------------------------------------------------------------
# 5.6 compute_student_scores()
# ---------------------------------------------------------------------------

class TestComputeStudentScores:

    def _make_units(self):
        return [
            _unit(response_id='r1', datapoint_id='dp1', task_id='t1',
                  teacher='T1', student='S1', judge='J1', aspect='acc', score='High'),
            _unit(response_id='r1', datapoint_id='dp1', task_id='t1',
                  teacher='T1', student='S1', judge='J1', aspect='fmt', score='Medium'),
            _unit(response_id='r2', datapoint_id='dp2', task_id='t1',
                  teacher='T1', student='S1', judge='J1', aspect='acc', score='Low'),
        ]

    def test_overall_score_average(self):
        results = compute_student_scores(self._make_units(), ['S1'])
        # avg(1.0, 0.5, 0.0) = 0.5
        assert results['S1'].overall == pytest.approx(0.5)

    def test_valid_evals_count(self):
        results = compute_student_scores(self._make_units(), ['S1'])
        assert results['S1'].valid_evals == 3

    def test_by_aspect_grouping(self):
        results = compute_student_scores(self._make_units(), ['S1'])
        by_asp = results['S1'].by_aspect
        # acc: avg(1.0, 0.0) = 0.5; fmt: 0.5
        assert by_asp['acc'] == pytest.approx(0.5)
        assert by_asp['fmt'] == pytest.approx(0.5)

    def test_by_task(self):
        results = compute_student_scores(self._make_units(), ['S1'])
        assert 't1' in results['S1'].by_task

    def test_by_judge(self):
        results = compute_student_scores(self._make_units(), ['S1'])
        assert 'J1' in results['S1'].by_judge

    def test_by_teacher(self):
        results = compute_student_scores(self._make_units(), ['S1'])
        assert 'T1' in results['S1'].by_teacher

    def test_no_evaluations_returns_none_overall(self):
        results = compute_student_scores([], ['S_missing'])
        assert results['S_missing'].overall is None
        assert results['S_missing'].valid_evals == 0

    def test_by_attr_value_with_datapoints(self):
        units = self._make_units()
        datapoints = {
            'dp1': {'sampled_target_attributes': {'sentiment': 'positive'}},
            'dp2': {'sampled_target_attributes': {'sentiment': 'negative'}},
        }
        results = compute_student_scores(units, ['S1'], datapoints=datapoints)
        by_attr = results['S1'].by_attr_value
        assert 'sentiment=positive' in by_attr
        assert 'sentiment=negative' in by_attr

    def test_multiple_students(self):
        units = [
            _unit(response_id='r1', student='S1', score='High'),
            _unit(response_id='r2', student='S2', score='Low'),
        ]
        results = compute_student_scores(units, ['S1', 'S2'])
        assert results['S1'].overall == pytest.approx(1.0)
        assert results['S2'].overall == pytest.approx(0.0)

    def test_result_is_student_score_result(self):
        results = compute_student_scores(self._make_units(), ['S1'])
        assert isinstance(results['S1'], StudentScoreResult)


# ---------------------------------------------------------------------------
# 5.7 robust_filter()
# ---------------------------------------------------------------------------

def _robust_model(tmp_path):
    """
    2 teachers (T1 produces consistent data, T2 inconsistent),
    2 judges (J1, J2 agree on T1 data but disagree on T2 data),
    2 students (S1, S2).
    """
    units = []
    # T1 data: J1 and J2 fully agree
    for dp_id in ('dp1', 'dp2'):
        for student in ('S1', 'S2'):
            for aspect in ('acc', 'fmt'):
                for judge in ('J1', 'J2'):
                    units.append(_unit(
                        response_id=f'{dp_id}-{student}-{judge}-{aspect}',
                        datapoint_id=dp_id, task_id='task1',
                        teacher='T1', student=student, judge=judge,
                        aspect=aspect, score='High',
                    ))
    # T2 data: J1 and J2 disagree
    for dp_id in ('dp3', 'dp4'):
        for student in ('S1', 'S2'):
            for aspect in ('acc', 'fmt'):
                units.append(_unit(
                    response_id=f'{dp_id}-{student}-J1-{aspect}',
                    datapoint_id=dp_id, task_id='task1',
                    teacher='T2', student=student, judge='J1',
                    aspect=aspect, score='High',
                ))
                units.append(_unit(
                    response_id=f'{dp_id}-{student}-J2-{aspect}',
                    datapoint_id=dp_id, task_id='task1',
                    teacher='T2', student=student, judge='J2',
                    aspect=aspect, score='Low',  # disagrees with J1
                ))

    datapoints = {
        'dp1': {'id': 'dp1', 'teacher_model_id': 'T1', 'task_id': 'task1'},
        'dp2': {'id': 'dp2', 'teacher_model_id': 'T1', 'task_id': 'task1'},
        'dp3': {'id': 'dp3', 'teacher_model_id': 'T2', 'task_id': 'task1'},
        'dp4': {'id': 'dp4', 'teacher_model_id': 'T2', 'task_id': 'task1'},
    }
    return _make_model(
        tmp_path, units, datapoints=datapoints,
        teachers=['T1', 'T2'],
        students=['S1', 'S2'],
        judges=['J1', 'J2'],
    )


class TestRobustFilter:

    def test_returns_robust_filter_result(self, tmp_path):
        rfr = robust_filter(_robust_model(tmp_path))
        assert isinstance(rfr, RobustFilterResult)

    def test_j_star_subset_of_judges(self, tmp_path):
        model = _robust_model(tmp_path)
        rfr = robust_filter(model, judge_selection='top_half')
        assert set(rfr.J_star).issubset(set(model.judges))

    def test_j_star_all_includes_all_judges(self, tmp_path):
        model = _robust_model(tmp_path)
        rfr = robust_filter(model, judge_selection='all')
        assert set(rfr.J_star) == set(model.judges)

    def test_t_star_subset_of_teachers(self, tmp_path):
        rfr = robust_filter(_robust_model(tmp_path))
        assert set(rfr.T_star).issubset({'T1', 'T2'})

    def test_d_robust_subset_of_datapoints(self, tmp_path):
        rfr = robust_filter(_robust_model(tmp_path))
        assert rfr.D_robust.issubset({'dp1', 'dp2', 'dp3', 'dp4'})

    def test_threshold_zero_includes_more_datapoints(self, tmp_path):
        """Threshold=0.0 → any consistency fraction qualifies."""
        rfr = robust_filter(_robust_model(tmp_path), agreement_threshold=0.0)
        assert len(rfr.D_robust) > 0

    def test_threshold_one_requires_full_consistency(self, tmp_path):
        """Threshold=1.0, all judges → only dp1/dp2 (J1,J2 fully agree) qualify."""
        rfr = robust_filter(
            _robust_model(tmp_path),
            agreement_threshold=1.0,
            judge_selection='all',
        )
        # dp3/dp4 have disagreement (High vs Low) → excluded
        for dp_id in rfr.D_robust:
            assert dp_id in ('dp1', 'dp2')

    def test_q_equals_ceil_half_j_star(self, tmp_path):
        rfr = robust_filter(_robust_model(tmp_path), judge_selection='all')
        assert rfr.q == math.ceil(len(rfr.J_star) / 2)

    def test_robust_count_matches_d_robust_len(self, tmp_path):
        rfr = robust_filter(_robust_model(tmp_path))
        assert rfr.robust_count == len(rfr.D_robust)

    def test_t_star_count_matches_datapoints_from_t_star(self, tmp_path):
        rfr = robust_filter(_robust_model(tmp_path))
        assert rfr.T_star_count == len(rfr.D_robust) + sum(
            1 for dp_id in ('dp1', 'dp2', 'dp3', 'dp4')
            if dp_id not in rfr.D_robust
            and any(dp_id.startswith(t[0].lower()) for t in rfr.T_star)
        )
        # Simpler assertion: T_star_count ≥ robust_count
        assert rfr.T_star_count >= rfr.robust_count

    def test_alternative_metrics_wpa_kappa(self, tmp_path):
        for metric in ('spa', 'wpa', 'kappa'):
            rfr = robust_filter(_robust_model(tmp_path), agreement_metric=metric)
            assert rfr.agreement_metric == metric

    def test_alternative_teacher_formulas(self, tmp_path):
        for formula in ('v1', 's2', 'r3'):
            rfr = robust_filter(_robust_model(tmp_path), teacher_score_formula=formula)
            assert rfr.teacher_score_formula == formula

    def test_diagnostics_dict_present(self, tmp_path):
        rfr = robust_filter(_robust_model(tmp_path))
        assert isinstance(rfr.diagnostics, dict)
        assert 'J_star' in rfr.diagnostics
        assert 'T_star' in rfr.diagnostics

    def test_empty_experiment_no_crash(self, tmp_path):
        """An empty experiment (no units, no datapoints) should not raise."""
        model = _make_model(tmp_path, units=[], datapoints={},
                            teachers=[], students=[], judges=[])
        rfr = robust_filter(model)
        assert rfr.D_robust == set()


# ---------------------------------------------------------------------------
# compute_robust_student_scores()
# ---------------------------------------------------------------------------

class TestComputeRobustStudentScores:

    def test_empty_d_robust_returns_none(self, tmp_path):
        model = _robust_model(tmp_path)
        scores = compute_robust_student_scores(
            model.units, ['S1', 'S2'],
            D_robust=set(), J_star={'J1', 'J2'},
        )
        assert scores['S1'] is None
        assert scores['S2'] is None

    def test_nonempty_d_robust_returns_float(self, tmp_path):
        model = _robust_model(tmp_path)
        # dp1/dp2 fully agreed: all 'High' = 1.0
        scores = compute_robust_student_scores(
            model.units, ['S1', 'S2'],
            D_robust={'dp1', 'dp2'},
            J_star={'J1', 'J2'},
        )
        assert scores['S1'] == pytest.approx(1.0)
        assert scores['S2'] == pytest.approx(1.0)

    def test_result_in_range_0_1(self, tmp_path):
        model = _robust_model(tmp_path)
        rfr = robust_filter(model, agreement_threshold=0.0, judge_selection='all')
        scores = compute_robust_student_scores(
            model.units, ['S1', 'S2'],
            D_robust=rfr.D_robust,
            J_star=set(rfr.J_star),
        )
        for s, v in scores.items():
            if v is not None:
                assert 0.0 <= v <= 1.0, f"Score for {s} out of range: {v}"

    def test_empty_j_star_returns_none(self, tmp_path):
        model = _robust_model(tmp_path)
        scores = compute_robust_student_scores(
            model.units, ['S1'],
            D_robust={'dp1', 'dp2'},
            J_star=set(),           # no judges selected → no units match
        )
        assert scores['S1'] is None
