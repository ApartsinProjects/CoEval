"""EEA Computation Engine — REQ-A-5.x.

All metric computations operate on AnalyticalUnit lists produced by the
data loader.  Functions are pure: they take data, return results, and
never mutate their inputs.
"""
from __future__ import annotations

import math
import statistics
from collections import defaultdict
from typing import NamedTuple

from .loader import AnalyticalUnit, EESDataModel, SCORE_MAP


# ---------------------------------------------------------------------------
# 5.1 Score normalisation
# ---------------------------------------------------------------------------

def normalize(score: str) -> float:
    """Ordinal string → numeric value [0.0, 1.0] (REQ-A-5.1.1)."""
    return SCORE_MAP.get(score, 0.0)


# ---------------------------------------------------------------------------
# 5.3 Judge agreement metrics
# ---------------------------------------------------------------------------

class AgreementResult(NamedTuple):
    spa: float | None       # Simple Percent Agreement
    wpa: float | None       # Weighted Percent Agreement
    kappa: float | None     # Cohen's Kappa
    count: int              # |E(Ja, Jb)| — common evaluation pairs


# Ordinal weight matrix (REQ-A-5.3.2)
_WPA_WEIGHT: dict[tuple[str, str], float] = {
    ('High',   'High'):   1.0,
    ('High',   'Medium'): 0.5,
    ('High',   'Low'):    0.0,
    ('Medium', 'High'):   0.5,
    ('Medium', 'Medium'): 1.0,
    ('Medium', 'Low'):    0.5,
    ('Low',    'High'):   0.0,
    ('Low',    'Medium'): 0.5,
    ('Low',    'Low'):    1.0,
}


def compute_agreement(
    units: list[AnalyticalUnit],
    ja: str,
    jb: str,
) -> AgreementResult:
    """Compute SPA, WPA, and Kappa for judge pair (ja, jb) (REQ-A-5.3)."""
    # Build common evaluation set E(ja, jb): {(response_id, aspect) -> {judge: score}}
    by_key: dict[tuple[str, str], dict[str, str]] = defaultdict(dict)
    for u in units:
        if u.judge_model_id in (ja, jb):
            key = (u.response_id, u.rubric_aspect)
            by_key[key][u.judge_model_id] = u.score

    # Common set: keys where both judges scored
    common = [(k, v) for k, v in by_key.items() if ja in v and jb in v]
    n = len(common)

    if n == 0:
        return AgreementResult(spa=None, wpa=None, kappa=None, count=0)

    # SPA — REQ-A-5.3.1
    agree = sum(1 for _, v in common if v[ja] == v[jb])
    spa = agree / n

    # WPA — REQ-A-5.3.2
    wpa = sum(_WPA_WEIGHT.get((v[ja], v[jb]), 0.0) for _, v in common) / n

    # Kappa — REQ-A-5.3.3
    p_o = spa
    counts_a: dict[str, int] = defaultdict(int)
    counts_b: dict[str, int] = defaultdict(int)
    for _, v in common:
        counts_a[v[ja]] += 1
        counts_b[v[jb]] += 1
    cats = ('High', 'Medium', 'Low')
    p_e = sum((counts_a[c] / n) * (counts_b[c] / n) for c in cats)

    if p_e >= 1.0 - 1e-12:
        kappa = None   # undefined
    else:
        kappa = (p_o - p_e) / (1.0 - p_e)

    return AgreementResult(spa=spa, wpa=wpa, kappa=kappa, count=n)


def compute_all_agreements(
    units: list[AnalyticalUnit],
    judges: list[str],
) -> dict[tuple[str, str], AgreementResult]:
    """Compute pairwise agreement for all judge pairs (REQ-A-5.3.4)."""
    results: dict[tuple[str, str], AgreementResult] = {}
    for i, ja in enumerate(judges):
        for jb in judges[i + 1:]:
            res = compute_agreement(units, ja, jb)
            # Store both orderings (metrics are symmetric)
            results[(ja, jb)] = res
            results[(jb, ja)] = res
    return results


# ---------------------------------------------------------------------------
# 5.4 Judge Score
# ---------------------------------------------------------------------------

class JudgeScoreResult(NamedTuple):
    spa_mean: float | None
    wpa_mean: float | None
    kappa_mean: float | None
    spa_weighted: float | None
    wpa_weighted: float | None
    kappa_weighted: float | None
    degenerate: bool            # True when only 1 judge in experiment


def compute_judge_scores(
    units: list[AnalyticalUnit],
    judges: list[str],
    agreements: dict[tuple[str, str], AgreementResult] | None = None,
) -> dict[str, JudgeScoreResult]:
    """Compute JudgeScore for each judge (REQ-A-5.4)."""
    if len(judges) <= 1:
        return {
            j: JudgeScoreResult(
                spa_mean=1.0, wpa_mean=1.0, kappa_mean=1.0,
                spa_weighted=1.0, wpa_weighted=1.0, kappa_weighted=1.0,
                degenerate=True,
            )
            for j in judges
        }

    if agreements is None:
        agreements = compute_all_agreements(units, judges)

    results: dict[str, JudgeScoreResult] = {}
    for ja in judges:
        pairs = [
            agreements[(ja, jb)]
            for jb in judges if jb != ja and (ja, jb) in agreements
        ]
        valid_pairs = [p for p in pairs if p.count > 0]

        def _mean(metric_vals: list[float | None]) -> float | None:
            vals = [v for v in metric_vals if v is not None]
            return sum(vals) / len(vals) if vals else None

        def _wmean(metric_vals: list[float | None], counts: list[int]) -> float | None:
            pairs_nz = [
                (v, c) for v, c in zip(metric_vals, counts)
                if v is not None and c > 0
            ]
            if not pairs_nz:
                return None
            total = sum(c for _, c in pairs_nz)
            return sum(v * c for v, c in pairs_nz) / total if total > 0 else None

        spas = [p.spa for p in valid_pairs]
        wpas = [p.wpa for p in valid_pairs]
        kappas = [p.kappa for p in valid_pairs]
        counts = [p.count for p in valid_pairs]

        results[ja] = JudgeScoreResult(
            spa_mean=_mean(spas),
            wpa_mean=_mean(wpas),
            kappa_mean=_mean(kappas),
            spa_weighted=_wmean(spas, counts),
            wpa_weighted=_wmean(wpas, counts),
            kappa_weighted=_wmean(kappas, counts),
            degenerate=False,
        )

    return results


# ---------------------------------------------------------------------------
# 5.5 Teacher Differentiation Score
# ---------------------------------------------------------------------------

class TeacherScoreResult(NamedTuple):
    v1: float   # variance of per-student averages
    s2: float   # average per-datapoint student spread
    r3: float   # range of per-student averages


def compute_teacher_scores(
    units: list[AnalyticalUnit],
    teachers: list[str],
    students: list[str],
    judge_filter: set[str] | None = None,
) -> dict[str, TeacherScoreResult]:
    """Compute teacher differentiation scores (REQ-A-5.5)."""
    results: dict[str, TeacherScoreResult] = {}

    for teacher in teachers:
        t_units = [u for u in units if u.teacher_model_id == teacher]
        if judge_filter:
            t_units = [u for u in t_units if u.judge_model_id in judge_filter]

        # Group by (task, aspect, student, datapoint) for averaging
        # μ(s, T, K, A) = mean over d of score_norm(mean over j of eval(d, s, j, A))
        # REQ-A-5.5 notation

        # First: for each (dp, student, aspect) → list of judge scores
        dp_s_a: dict[tuple[str, str, str], list[float]] = defaultdict(list)
        for u in t_units:
            key = (u.datapoint_id, u.student_model_id, u.rubric_aspect)
            dp_s_a[key].append(u.score_norm)

        # Average over judges → judge-averaged score per (dp, student, aspect)
        dp_s_a_avg: dict[tuple[str, str, str], float] = {
            k: sum(v) / len(v) for k, v in dp_s_a.items()
        }

        # Collect (task, aspect, student) → mean over datapoints
        # We need to average over datapoints for each (task, aspect, student)
        # Group by (task_id, aspect, student) — task comes from the dp record
        # Since we have task_id in units, use that
        dp_to_task: dict[str, str] = {}
        for u in t_units:
            dp_to_task[u.datapoint_id] = u.task_id

        # μ(s, T, K, A) = mean over d ∈ D(T, K) of judge-avg score
        mu_key_scores: dict[tuple[str, str, str], list[float]] = defaultdict(list)
        for (dp, s, a), avg in dp_s_a_avg.items():
            task_id = dp_to_task.get(dp, '')
            mu_key_scores[(task_id, a, s)].append(avg)

        mu: dict[tuple[str, str, str], float] = {
            k: sum(v) / len(v) for k, v in mu_key_scores.items()
        }

        # ---------------------------------------------------------------
        # Formula 1 — variance of per-student averages (REQ-A-5.5.1)
        # ---------------------------------------------------------------
        # For each (task, aspect), collect {student: mu} and compute variance
        ta_student_mu: dict[tuple[str, str], list[float]] = defaultdict(list)
        for (task_id, aspect, student), m in mu.items():
            ta_student_mu[(task_id, aspect)].append(m)

        v1_vals: list[float] = []
        for vals in ta_student_mu.values():
            if len(vals) >= 2:
                v1_vals.append(statistics.variance(vals))
            else:
                v1_vals.append(0.0)
        v1 = sum(v1_vals) / len(v1_vals) if v1_vals else 0.0

        # ---------------------------------------------------------------
        # Formula 2 — S2 = sqrt(V1) (REQ-A-5.5.2)
        # Aligned with paper v2 methodology - S2 definition (§3.8, Table 1)
        # S2(t) = sqrt(V1(t)); standard deviation of student means over
        # teacher t's datapoints.  Same ranking as V1 but in score units.
        # ---------------------------------------------------------------
        s2 = math.sqrt(v1) if v1 >= 0.0 else 0.0

        # ---------------------------------------------------------------
        # Formula 3 — range of per-student averages (REQ-A-5.5.3)
        # ---------------------------------------------------------------
        r3_vals: list[float] = []
        for vals in ta_student_mu.values():
            if vals:
                r3_vals.append(max(vals) - min(vals))
        r3 = sum(r3_vals) / len(r3_vals) if r3_vals else 0.0

        results[teacher] = TeacherScoreResult(v1=v1, s2=s2, r3=r3)

    return results


# ---------------------------------------------------------------------------
# 5.6 Student Score
# ---------------------------------------------------------------------------

class StudentScoreResult(NamedTuple):
    overall: float | None
    by_task: dict[str, float]
    by_aspect: dict[str, float]
    by_judge: dict[str, float]
    by_teacher: dict[str, float]
    by_attr_value: dict[str, float]   # "{attr}={val}" -> avg score
    valid_evals: int


def compute_student_scores(
    units: list[AnalyticalUnit],
    students: list[str],
    datapoints: dict[str, dict] | None = None,
) -> dict[str, StudentScoreResult]:
    """Compute student scores at multiple granularities (REQ-A-5.6)."""
    results: dict[str, StudentScoreResult] = {}
    datapoints = datapoints or {}

    for student in students:
        s_units = [u for u in units if u.student_model_id == student]

        if not s_units:
            results[student] = StudentScoreResult(
                overall=None,
                by_task={}, by_aspect={}, by_judge={}, by_teacher={},
                by_attr_value={},
                valid_evals=0,
            )
            continue

        def _avg(lst: list[float]) -> float | None:
            return sum(lst) / len(lst) if lst else None

        def _group_avg(key_fn) -> dict[str, float]:
            grouped: dict[str, list[float]] = defaultdict(list)
            for u in s_units:
                grouped[key_fn(u)].append(u.score_norm)
            return {k: sum(v) / len(v) for k, v in grouped.items()}

        overall = _avg([u.score_norm for u in s_units])
        by_task = _group_avg(lambda u: u.task_id)
        by_aspect = _group_avg(lambda u: u.rubric_aspect)
        by_judge = _group_avg(lambda u: u.judge_model_id)
        by_teacher = _group_avg(lambda u: u.teacher_model_id)

        # Per target-attribute-value breakdown
        by_attr: dict[str, list[float]] = defaultdict(list)
        for u in s_units:
            dp = datapoints.get(u.datapoint_id, {})
            attrs = dp.get('sampled_target_attributes', {})
            for k, v in attrs.items():
                by_attr[f'{k}={v}'].append(u.score_norm)
        by_attr_value = {k: sum(v) / len(v) for k, v in by_attr.items()}

        results[student] = StudentScoreResult(
            overall=overall,
            by_task=dict(by_task),
            by_aspect=dict(by_aspect),
            by_judge=dict(by_judge),
            by_teacher=dict(by_teacher),
            by_attr_value=by_attr_value,
            valid_evals=len(s_units),
        )

    return results


# ---------------------------------------------------------------------------
# 5.7 Robust Filtering Algorithm
# ---------------------------------------------------------------------------

class RobustFilterResult(NamedTuple):
    J_star: list[str]
    T_star: list[str]
    D_robust: set[str]              # datapoint IDs
    all_count: int
    T_star_count: int
    robust_count: int
    judge_scores: dict[str, JudgeScoreResult]
    teacher_scores: dict[str, TeacherScoreResult]
    consistent_fractions: dict[str, float]   # dp_id -> fraction of (s,c) pairs passing theta test
    agreement_metric: str
    # Aligned with paper v2 methodology - D* filter parameters
    agreement_threshold: float      # kept for backward compat; equals theta
    theta: float                    # paper v2 §3.8: score spread tolerance (default 0.05)
    q_fraction: float               # paper v2 §3.8: fraction of J* that must be within theta (default 0.5)
    teacher_score_formula: str
    judge_selection: str
    q: int                          # = ceil(q_fraction * |J*|)
    diagnostics: dict               # for the diagnostic printout


def robust_filter(
    model: EESDataModel,
    judge_selection: str = 'top_half',
    agreement_metric: str = 'wpa',
    # Aligned with paper v2 methodology - D* filter: q=0.5*|J*|, theta=0.05
    q_fraction: float = 0.5,
    theta: float = 0.05,
    # Backward-compat alias for theta (old API used agreement_threshold)
    agreement_threshold: float | None = None,
    teacher_score_formula: str = 'v1',
) -> RobustFilterResult:
    """Three-step robust filtering algorithm (REQ-A-5.7).

    D* filter (paper v2 §3.8): datapoint d is retained if, for every student s
    and every criterion c, at least q = q_fraction * |J*| judges satisfy
    |score_adj - mean_score| <= theta.  Defaults: q_fraction=0.5, theta=0.05.

    agreement_threshold is a backward-compatibility alias for theta; if both
    are supplied, agreement_threshold takes precedence.
    """
    # Backward compatibility: if old agreement_threshold kwarg was passed, use it as theta
    if agreement_threshold is not None:
        theta = agreement_threshold
    units = model.units
    judges = model.judges
    teachers = model.teachers
    all_dp_ids = set(model.datapoints.keys())

    # ------------------------------------------------------------------
    # Step 1 — Select high-quality judges (J*)
    # ------------------------------------------------------------------
    agreements = compute_all_agreements(units, judges)
    judge_scores = compute_judge_scores(units, judges, agreements)

    metric_attr = f'{agreement_metric}_weighted'

    def _judge_score_val(jid: str) -> float:
        res = judge_scores.get(jid)
        if res is None:
            return 0.0
        val = getattr(res, metric_attr, None)
        return val if val is not None else 0.0

    if judge_selection == 'all':
        J_star = list(judges)
    else:  # top_half
        ranked_judges = sorted(judges, key=_judge_score_val, reverse=True)
        n_select = math.ceil(len(judges) / 2) if judges else 0
        J_star = ranked_judges[:n_select]

    # ------------------------------------------------------------------
    # Step 2 — Select best teachers (T*)
    # ------------------------------------------------------------------
    # Recompute teacher scores using J* only
    teacher_scores = compute_teacher_scores(
        units, teachers, model.students,
        judge_filter=set(J_star),
    )

    def _teacher_score_val(tid: str) -> float:
        res = teacher_scores.get(tid)
        if res is None:
            return 0.0
        return getattr(res, teacher_score_formula, 0.0)

    ranked_teachers = sorted(teachers, key=_teacher_score_val, reverse=True)
    n_t = math.ceil(len(teachers) / 2) if teachers else 0
    T_star = ranked_teachers[:n_t]

    # Datapoints from T* teachers
    T_star_set = set(T_star)
    T_star_dps = {
        dp_id for dp_id, dp in model.datapoints.items()
        if dp.get('teacher_model_id', '') in T_star_set
    }

    # ------------------------------------------------------------------
    # Step 3 — Filter to robust datapoints (D*)
    # Aligned with paper v2 methodology - D* filter (§3.8 Eq.)
    # Retain datapoint d iff for every (s, c) pair, at least
    # q = ceil(q_fraction * |J*|) judges satisfy
    # |score_adj - mean_score_(d,s,c)| <= theta.
    # ------------------------------------------------------------------
    J_star_set = set(J_star)
    # q_fraction=0.5 and theta=0.05 are the paper v2 defaults
    q = math.ceil(q_fraction * len(J_star)) if J_star else 1

    consistent_fractions: dict[str, float] = {}
    D_robust: set[str] = set()

    # Units from J* only, for T* datapoints
    jstar_units = [
        u for u in units
        if u.judge_model_id in J_star_set and u.datapoint_id in T_star_dps
    ]

    # Group by datapoint_id
    by_dp: dict[str, list[AnalyticalUnit]] = defaultdict(list)
    for u in jstar_units:
        by_dp[u.datapoint_id].append(u)

    for dp_id, dp_units in by_dp.items():
        # Collect (student, aspect) pairs evaluated by at least one J* judge
        pairs: set[tuple[str, str]] = {
            (u.student_model_id, u.rubric_aspect) for u in dp_units
        }

        # Paper v2 §3.8: d is retained if ALL (s, c) pairs pass the theta test.
        # A pair passes iff at least q judges are within theta of the mean.
        all_pairs_pass = True
        for student, aspect in pairs:
            pair_units = [
                u for u in dp_units
                if u.student_model_id == student and u.rubric_aspect == aspect
            ]
            if not pair_units:
                all_pairs_pass = False
                break
            # Compute mean calibrated score for this (d, s, c) tuple
            mean_score = sum(u.score_norm for u in pair_units) / len(pair_units)
            # Count judges within theta of the mean
            within_theta = sum(
                1 for u in pair_units
                if abs(u.score_norm - mean_score) <= theta
            )
            if within_theta < q:
                all_pairs_pass = False
                break

        # consistent_fractions records fraction of pairs that pass (for diagnostics)
        passing_pairs = 0
        for student, aspect in pairs:
            pair_units = [
                u for u in dp_units
                if u.student_model_id == student and u.rubric_aspect == aspect
            ]
            if pair_units:
                mean_score = sum(u.score_norm for u in pair_units) / len(pair_units)
                within_theta = sum(
                    1 for u in pair_units
                    if abs(u.score_norm - mean_score) <= theta
                )
                if within_theta >= q:
                    passing_pairs += 1

        fraction = passing_pairs / len(pairs) if pairs else 0.0
        consistent_fractions[dp_id] = fraction
        if all_pairs_pass and pairs:
            D_robust.add(dp_id)

    # ------------------------------------------------------------------
    # Build diagnostics
    # ------------------------------------------------------------------
    diagnostics: dict = {
        'judges_ranked': [
            (j, round(_judge_score_val(j), 4)) for j in
            sorted(judges, key=_judge_score_val, reverse=True)
        ],
        'J_star': J_star,
        'agreement_metric': agreement_metric,
        'teachers_ranked': [
            (t, round(_teacher_score_val(t), 4)) for t in ranked_teachers
        ],
        'T_star': T_star,
        'formula': teacher_score_formula,
        'T_star_count': len(T_star_dps),
        'all_count': len(all_dp_ids),
        'robust_count': len(D_robust),
        # Aligned with paper v2 methodology - D* filter: theta and q_fraction
        'agreement_threshold': theta,   # backward-compat alias
        'theta': theta,
        'q_fraction': q_fraction,
        'q': q,
    }

    return RobustFilterResult(
        J_star=J_star,
        T_star=T_star,
        D_robust=D_robust,
        all_count=len(all_dp_ids),
        T_star_count=len(T_star_dps),
        robust_count=len(D_robust),
        judge_scores=judge_scores,
        teacher_scores=teacher_scores,
        consistent_fractions=consistent_fractions,
        agreement_metric=agreement_metric,
        # Aligned with paper v2 methodology - D* filter parameters
        agreement_threshold=theta,   # backward-compat alias
        theta=theta,
        q_fraction=q_fraction,
        teacher_score_formula=teacher_score_formula,
        judge_selection=judge_selection,
        q=q,
        diagnostics=diagnostics,
    )


def get_metric_value(
    result: 'JudgeScoreResult | AgreementResult',
    metric: str,
    weighted: bool = False,
) -> float | None:
    """Helper to extract a named metric from result objects."""
    if weighted:
        attr = f'{metric}_weighted'
    else:
        attr = f'{metric}_mean'
    return getattr(result, attr, None)


def kappa_label(kappa: float | None) -> str:
    """Conventional interpretation label for Cohen's kappa (REQ-A-5.3.3)."""
    if kappa is None:
        return 'N/A'
    if kappa < 0.0:
        return 'Less than chance'
    if kappa <= 0.20:
        return 'Slight'
    if kappa <= 0.40:
        return 'Fair'
    if kappa <= 0.60:
        return 'Moderate'
    if kappa <= 0.80:
        return 'Substantial'
    return 'Almost perfect'


# ---------------------------------------------------------------------------
# Robust student scores
# ---------------------------------------------------------------------------

def compute_robust_student_scores(
    units: list[AnalyticalUnit],
    students: list[str],
    D_robust: set[str],
    J_star: set[str],
) -> dict[str, float | None]:
    """REQ-A-5.7.4 — mean over D_robust × J* evaluations."""
    results: dict[str, float | None] = {}
    for student in students:
        s_units = [
            u for u in units
            if u.student_model_id == student
            and u.datapoint_id in D_robust
            and u.judge_model_id in J_star
        ]
        if not s_units:
            results[student] = None
        else:
            # Average judge scores per (dp, aspect), then average across those
            dp_a: dict[tuple[str, str], list[float]] = defaultdict(list)
            for u in s_units:
                dp_a[(u.datapoint_id, u.rubric_aspect)].append(u.score_norm)
            pair_avgs = [sum(v) / len(v) for v in dp_a.values()]
            results[student] = sum(pair_avgs) / len(pair_avgs)
    return results
