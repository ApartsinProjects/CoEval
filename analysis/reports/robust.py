"""Robust Student Summary Report — REQ-A-7.10."""
from __future__ import annotations

import math
import sys
from pathlib import Path

from ..loader import EESDataModel
from ..metrics import (
    RobustFilterResult,
    compute_student_scores,
    compute_robust_student_scores,
    robust_filter,
)
from .html_base import build_report, get_plotly_js, make_experiment_meta


def write_robust_summary(
    model: EESDataModel,
    out_dir: Path,
    judge_selection: str = 'top_half',
    agreement_metric: str = 'spa',
    agreement_threshold: float = 1.0,
    teacher_score_formula: str = 'v1',
    shared_plotly: Path | None = None,
) -> Path:
    """Generate Robust Student Summary Report (REQ-A-7.10)."""
    rfr = robust_filter(
        model=model,
        judge_selection=judge_selection,
        agreement_metric=agreement_metric,
        agreement_threshold=agreement_threshold,
        teacher_score_formula=teacher_score_formula,
    )

    if rfr.robust_count == 0:
        _print_empty_diagnostics(rfr)
        raise SystemExit(1)

    out_dir.mkdir(parents=True, exist_ok=True)
    if shared_plotly:
        import shutil; shutil.copy2(shared_plotly, out_dir / 'plotly.min.js')
    else:
        get_plotly_js(out_dir)

    exp_meta = make_experiment_meta(model)
    data = _build_data(model, rfr)

    return build_report(
        out_dir=out_dir,
        title=f'Robust Summary — {exp_meta["id"]}',
        data=data,
        views_html=_VIEWS_HTML,
        filter_defs=[],
        stats_text=exp_meta['stats'],
        experiment_meta=exp_meta,
        report_type='Robust Student Summary',
        extra_js=_APP_JS,
        partial=model.is_partial,
    )


def _build_data(model: EESDataModel, rfr: RobustFilterResult) -> dict:
    units = model.units
    students = model.students

    # Full-run student scores
    full_scores_map = compute_student_scores(units, students, model.datapoints)

    # Robust student scores
    robust_scores = compute_robust_student_scores(
        units=units,
        students=students,
        D_robust=rfr.D_robust,
        J_star=set(rfr.J_star),
    )

    ranking_rows = []
    for s in students:
        full = full_scores_map.get(s)
        full_avg = full.overall if full else None
        robust_avg = robust_scores.get(s)
        delta = None
        if full_avg is not None and robust_avg is not None:
            delta = round(robust_avg - full_avg, 4)
        large_delta = abs(delta) > 0.1 if delta is not None else False
        ranking_rows.append({
            'student': s,
            'robust_avg': round(robust_avg, 4) if robust_avg is not None else None,
            'full_avg': round(full_avg, 4) if full_avg is not None else None,
            'delta': delta,
            'large_delta': large_delta,
            'valid_robust_evals': sum(
                1 for u in units
                if u.student_model_id == s and u.datapoint_id in rfr.D_robust
                and u.judge_model_id in rfr.J_star
            ),
        })
    ranking_rows.sort(key=lambda r: r['robust_avg'] or 0, reverse=True)

    # Robust aspect heatmap: student × aspect
    J_star_set = set(rfr.J_star)
    rob_units = [u for u in units
                 if u.datapoint_id in rfr.D_robust and u.judge_model_id in J_star_set]

    all_aspects = sorted(set(u.rubric_aspect for u in rob_units))
    asp_student: dict = {}
    for s in students:
        for asp in all_aspects:
            vals = [u.score_norm for u in rob_units
                    if u.student_model_id == s and u.rubric_aspect == asp]
            if vals:
                asp_student[f'{s}||{asp}'] = round(sum(vals)/len(vals), 4)

    # Coverage breakdown per teacher
    coverage_rows = []
    for teacher in model.teachers:
        t_dps = {dp_id for dp_id, dp in model.datapoints.items()
                 if dp.get('teacher_model_id') == teacher}
        t_robust = t_dps & rfr.D_robust
        pct = round(len(t_robust)/len(t_dps)*100, 1) if t_dps else 0
        coverage_rows.append({
            'teacher': teacher,
            'all_dp': len(t_dps),
            'robust_dp': len(t_robust),
            'pct': pct,
        })

    # Filtering summary panel
    summary = {
        'agreement_metric': rfr.agreement_metric,
        'judge_selection': rfr.judge_selection,
        'J_star': rfr.J_star,
        'n_total_judges': len(model.judges),
        'teacher_formula': rfr.teacher_score_formula,
        'T_star': rfr.T_star,
        'n_total_teachers': len(model.teachers),
        'theta': rfr.agreement_threshold,
        'q': rfr.q,
        'all_count': rfr.all_count,
        'T_star_count': rfr.T_star_count,
        'robust_count': rfr.robust_count,
        'pct_all': round(rfr.robust_count/rfr.all_count*100, 1) if rfr.all_count else 0,
        'pct_T_star': round(rfr.robust_count/rfr.T_star_count*100, 1) if rfr.T_star_count else 0,
    }

    return {
        'students': students,
        'aspects': all_aspects,
        'ranking': ranking_rows,
        'asp_student': asp_student,
        'coverage_rows': coverage_rows,
        'summary': summary,
    }


def _print_empty_diagnostics(rfr: RobustFilterResult) -> None:
    d = rfr.diagnostics
    print("ERROR: Robust filter produced 0 datapoints. No report generated.\n",
          file=sys.stderr)
    print("Filtering diagnostics:", file=sys.stderr)
    print(f"  Step 1 — Judge selection (J*):", file=sys.stderr)
    print(f"    Judges ranked:        {d.get('judges_ranked', [])}", file=sys.stderr)
    print(f"    J* selected:          {d.get('J_star', [])}", file=sys.stderr)
    print(f"    Agreement metric:     {d.get('agreement_metric', '')}", file=sys.stderr)
    print(f"  Step 2 — Teacher selection (T*):", file=sys.stderr)
    print(f"    Teachers ranked:      {d.get('teachers_ranked', [])}", file=sys.stderr)
    print(f"    T* selected:          {d.get('T_star', [])}", file=sys.stderr)
    print(f"    Formula:              {d.get('formula', '')}", file=sys.stderr)
    print(f"    Datapoints remaining: {d.get('T_star_count', 0)} / {d.get('all_count', 0)}", file=sys.stderr)
    print(f"  Step 3 — Datapoint consistency filter:", file=sys.stderr)
    print(f"    Agreement threshold (theta): {d.get('agreement_threshold', '')}", file=sys.stderr)
    print(f"    Min judges/pair q:     {d.get('q', '')}", file=sys.stderr)
    print(f"    Datapoints passing:    0 / {d.get('T_star_count', 0)}", file=sys.stderr)
    print("\n  Suggested actions:", file=sys.stderr)
    print("    • Lower --agreement-threshold (current: "
          f"{d.get('agreement_threshold', 1.0)}, try: 0.8)", file=sys.stderr)
    print("    • Use --judge-selection all to include all judges in J*", file=sys.stderr)
    print("    • Use --teacher-score-formula s2 or r3", file=sys.stderr)
    print("    • Check coverage-summary report for invalid evaluation records", file=sys.stderr)


_VIEWS_HTML = """
<div class="view-section" id="v-summary">
  <h2>View 1 — Robust Filtering Settings</h2>
  <div id="summary-panel" style="font-family:monospace;font-size:0.85rem;padding:12px;background:#f0f4f8;border-radius:6px"></div>
</div>
<div class="view-section">
  <h2>View 2 — Robust Student Ranking</h2>
  <div id="v2-table"></div>
  <p class="note">Students where |Robust − Full| > 0.1 are flagged.</p>
</div>
<div class="view-section">
  <h2>View 3 — Robust vs. Full-Run Score Comparison</h2>
  <div id="v3-chart" class="chart-container"></div>
</div>
<div class="view-section">
  <h2>View 4 — Robust Aspect Heatmap (Student × Aspect)</h2>
  <div id="v4-chart" class="chart-container"></div>
</div>
<div class="view-section">
  <h2>View 5 — Coverage Breakdown by Teacher</h2>
  <div id="v5-table"></div>
</div>
<div class="view-section">
  <p class="note"><b>How to read this report:</b> Robust scores are computed from datapoints
  where all selected high-quality judges agreed on the student outcomes. A student that
  ranks the same in both the full-run and robust reports is likely to be genuinely
  better or worse.</p>
</div>
"""

_APP_JS = """
function renderAll() {
  renderSummary(); renderV2(); renderV3(); renderV4(); renderV5();
}

function renderSummary() {
  var s = DATA.summary;
  var lines = [
    'Robust Filtering Settings',
    '─'.repeat(50),
    'Agreement metric:      ' + s.agreement_metric + '  (--agreement-metric)',
    'Judge selection:       ' + s.judge_selection + '  (--judge-selection)',
    'Selected judges (J*):  [' + s.J_star.join(', ') + ']  (N=' + s.J_star.length + ' of ' + s.n_total_judges + ')',
    'Teacher formula:       ' + s.teacher_formula + '  (--teacher-score-formula)',
    'Teacher selection (T*):[' + s.T_star.join(', ') + ']  (N=' + s.T_star.length + ' of ' + s.n_total_teachers + ')',
    'Agreement threshold θ: ' + s.theta + '  (--agreement-threshold)',
    'Consistency minimum q: ' + s.q + '  (ceil(|J*|/2))',
    '',
    'Coverage impact:',
    '  All datapoints:      ' + s.all_count,
    '  From T* only:        ' + s.T_star_count + '  (' + s.pct_all + '% via T* of all)',
    '  Robust datapoints:   ' + s.robust_count + '  (' + s.pct_T_star + '% of T*, ' + s.pct_all + '% of all)',
  ];
  document.getElementById('summary-panel').textContent = lines.join('\\n');
}

function renderV2() {
  var rows = DATA.ranking;
  var html = '<table class="data-table"><tr><th>Student</th><th>Robust Avg</th>';
  html += '<th>Full-Run Avg</th><th>Delta</th><th>Robust Evals</th></tr>';
  rows.forEach(function(r) {
    var style = r.large_delta ? 'background:#fff3cd' : '';
    var flag = r.large_delta
      ? '<span class="warn-flag" title="Large difference between robust and full-run score.">⚠</span>' : '';
    html += '<tr style="' + style + '"><td>' + r.student + '</td>';
    html += '<td>' + fmt(r.robust_avg) + '</td><td>' + fmt(r.full_avg) + '</td>';
    html += '<td>' + fmt(r.delta) + flag + '</td><td>' + r.valid_robust_evals + '</td></tr>';
  });
  document.getElementById('v2-table').innerHTML = html + '</table>';
}

function renderV3() {
  var rows = DATA.ranking.filter(function(r){return r.full_avg !== null && r.robust_avg !== null;});
  if (!rows.length) return;
  var maxVal = 1.0;
  Plotly.newPlot('v3-chart', [
    {type:'scatter', mode:'markers+text',
     x: rows.map(function(r){return r.full_avg;}),
     y: rows.map(function(r){return r.robust_avg;}),
     text: rows.map(function(r){return r.student;}),
     textposition:'top center',
     marker:{size:10, color:'#2980b9'},
     hovertemplate:'%{text}<br>Full: %{x:.3f}<br>Robust: %{y:.3f}<extra></extra>'},
    {type:'scatter', mode:'lines', x:[0,1], y:[0,1],
     line:{color:'#aaa', dash:'dash'}, showlegend:false},
  ], {xaxis:{title:'Full-run avg', range:[0,1.05]},
      yaxis:{title:'Robust avg', range:[0,1.05]},
      margin:{t:20}});
}

function renderV4() {
  var students = DATA.students;
  var aspects = DATA.aspects;
  if (!students.length || !aspects.length) return;
  var z = students.map(function(s) {
    return aspects.map(function(a) {
      var v = DATA.asp_student[s+'||'+a];
      return v !== undefined ? v : null;
    });
  });
  Plotly.newPlot('v4-chart', [{
    type:'heatmap', z:z, x:aspects, y:students,
    colorscale:[[0,'#ffe0e0'],[0.5,'#fff7e0'],[1,'#e0ffe0']],
    zmin:0, zmax:1,
  }], {title:'Robust scores (J* judges, D_robust datapoints)', margin:{t:40}});
}

function renderV5() {
  var rows = DATA.coverage_rows;
  var html = '<table class="data-table"><tr><th>Teacher</th><th>All Datapoints</th>';
  html += '<th>Robust Datapoints</th><th>Coverage%</th></tr>';
  rows.forEach(function(r) {
    html += '<tr><td>' + r.teacher + '</td><td>' + r.all_dp + '</td>';
    html += '<td>' + r.robust_dp + '</td><td>' + r.pct + '%</td></tr>';
  });
  document.getElementById('v5-table').innerHTML = html + '</table>';
}

document.addEventListener('DOMContentLoaded', renderAll);
"""
