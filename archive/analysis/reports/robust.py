"""Robust Student Summary Report — REQ-A-7.10."""
from __future__ import annotations

import json
import math
import sys
from collections import defaultdict
from pathlib import Path

from ..loader import EESDataModel
from ..metrics import (
    RobustFilterResult,
    compute_all_agreements,
    compute_judge_scores,
    compute_student_scores,
    compute_robust_student_scores,
    compute_teacher_scores,
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
        title=f'Robust Summary \u2014 {exp_meta["id"]}',
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
    teachers = model.teachers
    judges = model.judges

    # ------------------------------------------------------------------
    # Teacher scores for all three formulas
    # ------------------------------------------------------------------
    teacher_scores_v1 = compute_teacher_scores(units, teachers, students)
    teacher_scores_s2 = compute_teacher_scores(units, teachers, students)
    teacher_scores_r3 = compute_teacher_scores(units, teachers, students)

    def _t_score(scores_map, teacher, attr):
        ts = scores_map.get(teacher)
        return round(getattr(ts, attr, 0.0), 4) if ts else 0.0

    teacher_scores = {
        'v1': {t: _t_score(teacher_scores_v1, t, 'v1') for t in teachers},
        's2': {t: _t_score(teacher_scores_s2, t, 's2') for t in teachers},
        'r3': {t: _t_score(teacher_scores_r3, t, 'r3') for t in teachers},
    }

    # ------------------------------------------------------------------
    # Judge scores for all three metrics
    # ------------------------------------------------------------------
    agreements = compute_all_agreements(units, judges)
    judge_scores_map = compute_judge_scores(units, judges, agreements)

    def _j_score(j, attr):
        jr = judge_scores_map.get(j)
        v = getattr(jr, attr, None) if jr else None
        return round(v, 4) if v is not None else 0.0

    judge_scores = {
        'spa':   {j: _j_score(j, 'spa_mean')   for j in judges},
        'wpa':   {j: _j_score(j, 'wpa_mean')   for j in judges},
        'kappa': {j: _j_score(j, 'kappa_mean') for j in judges},
    }

    # ------------------------------------------------------------------
    # units_tsj:  (teacher||student||judge)         -> average score_norm
    # asp_units_tsja: (teacher||student||judge||aspect) -> average score_norm
    # ------------------------------------------------------------------
    tsj_sums: dict[str, float] = defaultdict(float)
    tsj_counts: dict[str, int] = defaultdict(int)
    tsja_sums: dict[str, float] = defaultdict(float)
    tsja_counts: dict[str, int] = defaultdict(int)
    for u in units:
        key = f'{u.teacher_model_id}||{u.student_model_id}||{u.judge_model_id}'
        tsj_sums[key] += u.score_norm
        tsj_counts[key] += 1
        akey = f'{u.teacher_model_id}||{u.student_model_id}||{u.judge_model_id}||{u.rubric_aspect}'
        tsja_sums[akey] += u.score_norm
        tsja_counts[akey] += 1
    units_tsj = {
        k: round(tsj_sums[k] / tsj_counts[k], 4)
        for k in tsj_sums
    }
    asp_units_tsja = {
        k: round(tsja_sums[k] / tsja_counts[k], 4)
        for k in tsja_sums
    }

    # ------------------------------------------------------------------
    # Full-run and initial robust student scores (for initial render)
    # ------------------------------------------------------------------
    full_scores_map = compute_student_scores(units, students, model.datapoints)
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

    # Robust aspect heatmap: student x aspect (initial — based on rfr)
    J_star_set = set(rfr.J_star)
    rob_units = [u for u in units
                 if u.datapoint_id in rfr.D_robust and u.judge_model_id in J_star_set]

    all_aspects = sorted(set(u.rubric_aspect for u in units))
    asp_student: dict = {}
    for s in students:
        for asp in all_aspects:
            vals = [u.score_norm for u in rob_units
                    if u.student_model_id == s and u.rubric_aspect == asp]
            if vals:
                asp_student[f'{s}||{asp}'] = round(sum(vals)/len(vals), 4)

    # Coverage breakdown per teacher
    coverage_rows = []
    for teacher in teachers:
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

    # Filtering summary panel (initial settings)
    summary = {
        'agreement_metric': rfr.agreement_metric,
        'judge_selection': rfr.judge_selection,
        'J_star': rfr.J_star,
        'n_total_judges': len(judges),
        'teacher_formula': rfr.teacher_score_formula,
        'T_star': rfr.T_star,
        'n_total_teachers': len(teachers),
        'theta': rfr.agreement_threshold,
        'q': rfr.q,
        'all_count': rfr.all_count,
        'T_star_count': rfr.T_star_count,
        'robust_count': rfr.robust_count,
        'pct_all': round(rfr.robust_count/rfr.all_count*100, 1) if rfr.all_count else 0,
        'pct_T_star': round(rfr.robust_count/rfr.T_star_count*100, 1) if rfr.T_star_count else 0,
    }

    # Datapoints by teacher (for coverage in dynamic mode)
    dp_by_teacher: dict[str, list[str]] = defaultdict(list)
    for dp_id, dp in model.datapoints.items():
        t = dp.get('teacher_model_id', '')
        if t:
            dp_by_teacher[t].append(dp_id)
    dp_by_teacher_plain = {t: list(v) for t, v in dp_by_teacher.items()}

    # All datapoint IDs (for dynamic coverage computation)
    all_dp_count = len(model.datapoints)

    return {
        'students': students,
        'teachers': teachers,
        'judges': judges,
        'aspects': all_aspects,
        'ranking': ranking_rows,
        'asp_student': asp_student,
        'coverage_rows': coverage_rows,
        'summary': summary,
        # Dynamic data
        'teacher_scores': teacher_scores,
        'judge_scores': judge_scores,
        'units_tsj': units_tsj,
        'asp_units_tsja': asp_units_tsja,
        'dp_by_teacher': dp_by_teacher_plain,
        'all_dp_count': all_dp_count,
        # Full-run scores for reference (pre-computed for JS)
        'full_scores': {
            s: round(full_scores_map[s].overall, 4)
            if full_scores_map.get(s) else None
            for s in students
        },
    }


def _print_empty_diagnostics(rfr: RobustFilterResult) -> None:
    d = rfr.diagnostics
    print("ERROR: Robust filter produced 0 datapoints. No report generated.\n",
          file=sys.stderr)
    print("Filtering diagnostics:", file=sys.stderr)
    print(f"  Step 1 \u2014 Judge selection (J*):", file=sys.stderr)
    print(f"    Judges ranked:        {d.get('judges_ranked', [])}", file=sys.stderr)
    print(f"    J* selected:          {d.get('J_star', [])}", file=sys.stderr)
    print(f"    Agreement metric:     {d.get('agreement_metric', '')}", file=sys.stderr)
    print(f"  Step 2 \u2014 Teacher selection (T*):", file=sys.stderr)
    print(f"    Teachers ranked:      {d.get('teachers_ranked', [])}", file=sys.stderr)
    print(f"    T* selected:          {d.get('T_star', [])}", file=sys.stderr)
    print(f"    Formula:              {d.get('formula', '')}", file=sys.stderr)
    print(f"    Datapoints remaining: {d.get('T_star_count', 0)} / {d.get('all_count', 0)}", file=sys.stderr)
    print(f"  Step 3 \u2014 Datapoint consistency filter:", file=sys.stderr)
    print(f"    Agreement threshold (theta): {d.get('agreement_threshold', '')}", file=sys.stderr)
    print(f"    Min judges/pair q:     {d.get('q', '')}", file=sys.stderr)
    print(f"    Datapoints passing:    0 / {d.get('T_star_count', 0)}", file=sys.stderr)
    print("\n  Suggested actions:", file=sys.stderr)
    print("    \u2022 Lower --agreement-threshold (current: "
          f"{d.get('agreement_threshold', 1.0)}, try: 0.8)", file=sys.stderr)
    print("    \u2022 Use --judge-selection all to include all judges in J*", file=sys.stderr)
    print("    \u2022 Use --teacher-score-formula s2 or r3", file=sys.stderr)
    print("    \u2022 Check coverage-summary report for invalid evaluation records", file=sys.stderr)


_VIEWS_HTML = """
<div id="controls-panel" style="position:sticky;top:0;z-index:100;background:#fff;padding:12px 16px;border-bottom:2px solid #e0e4ea;display:flex;flex-wrap:wrap;gap:16px;align-items:center">
  <div>
    <label style="font-weight:600;font-size:0.88rem">Teacher Formula:</label>
    <span class="btn-group">
      <button class="formula-btn active" data-formula="v1">V1</button>
      <button class="formula-btn" data-formula="s2">S2</button>
      <button class="formula-btn" data-formula="r3">R3</button>
    </span>
  </div>
  <div style="display:flex;align-items:center;gap:6px">
    <label style="font-weight:600;font-size:0.88rem">Teacher Threshold: <span id="t-thresh-val">0.00</span></label>
    <input type="range" id="t-thresh" min="0" max="1" step="0.01" value="0" style="width:120px">
    <span id="t-effective-count" style="color:#666;font-size:0.82rem"></span>
  </div>
  <div>
    <label style="font-weight:600;font-size:0.88rem">Judge Selection:</label>
    <span class="btn-group">
      <button class="jsel-btn active" data-jsel="top_half">Top Half</button>
      <button class="jsel-btn" data-jsel="all">All</button>
    </span>
  </div>
  <div>
    <label style="font-weight:600;font-size:0.88rem">Judge Metric:</label>
    <span class="btn-group">
      <button class="jmet-btn active" data-jmet="spa">SPA</button>
      <button class="jmet-btn" data-jmet="wpa">WPA</button>
      <button class="jmet-btn" data-jmet="kappa">&kappa;</button>
    </span>
  </div>
  <div style="display:flex;align-items:center;gap:6px">
    <label style="font-weight:600;font-size:0.88rem">Judge Threshold: <span id="j-thresh-val">0.50</span></label>
    <input type="range" id="j-thresh" min="0" max="1" step="0.01" value="0.5" style="width:120px">
    <span id="j-effective-count" style="color:#666;font-size:0.82rem"></span>
  </div>
</div>

<div class="view-section" id="v-summary">
  <h2>View 1 &mdash; Active Filter Settings</h2>
  <div id="summary-panel" style="font-family:monospace;font-size:0.85rem;padding:12px;background:#f0f4f8;border-radius:6px;white-space:pre"></div>
</div>
<div class="view-section">
  <h2>View 2 &mdash; Robust Student Ranking</h2>
  <div id="v2-table"></div>
  <p class="note">Students where |Robust &minus; Full| &gt; 0.1 are flagged. Scores update live with the controls above.</p>
</div>
<div class="view-section">
  <h2>View 3 &mdash; Robust vs. Full-Run Score Comparison</h2>
  <div id="v3-chart" class="chart-container"></div>
</div>
<div class="view-section">
  <h2>View 4 &mdash; Aspect Heatmap (Student &times; Aspect, filtered)</h2>
  <div id="v4-chart" class="chart-container"></div>
</div>
<div class="view-section">
  <h2>View 5 &mdash; Coverage Breakdown by Teacher</h2>
  <div id="v5-table"></div>
</div>
<div class="view-section">
  <p class="note"><b>How to read this report:</b> Use the controls above to adjust which
  teachers and judges are considered &ldquo;high quality&rdquo;. Robust scores
  include only evaluations from active teachers and judges. A student that ranks
  the same in both the full-run and robust columns is genuinely better or worse.</p>
</div>
"""

_APP_JS = """
/* ---------------------------------------------------------------
   Button-group style
--------------------------------------------------------------- */
(function() {
  var style = document.createElement('style');
  style.textContent = [
    '.btn-group button { padding:4px 10px; border:1px solid #ccc; background:#f5f5f5;',
    '  cursor:pointer; font-size:0.83rem; margin:0; }',
    '.btn-group button.active { background:#2980b9; color:#fff; border-color:#2980b9; }',
    '.btn-group button:first-child { border-radius:4px 0 0 4px; }',
    '.btn-group button:last-child  { border-radius:0 4px 4px 0; }',
    '.btn-group button:not(:first-child) { border-left:none; }',
  ].join('\\n');
  document.head.appendChild(style);
})();

/* ---------------------------------------------------------------
   State
--------------------------------------------------------------- */
var state = {
  formula: 'v1',
  tThresh: 0.0,
  jSel: 'top_half',
  jMet: 'spa',
  jThresh: 0.5
};

/* ---------------------------------------------------------------
   Filter helpers
--------------------------------------------------------------- */
function getEffectiveTeachers() {
  var scores = DATA.teacher_scores[state.formula];
  return DATA.teachers.filter(function(t) {
    return (scores[t] !== undefined ? scores[t] : 0) >= state.tThresh;
  });
}

function getConsensusJudges() {
  var scores = DATA.judge_scores[state.jMet];
  var judges = DATA.judges.slice();
  if (state.jSel === 'top_half') {
    judges.sort(function(a, b) {
      return (scores[b] !== undefined ? scores[b] : 0) -
             (scores[a] !== undefined ? scores[a] : 0);
    });
    judges = judges.slice(0, Math.ceil(judges.length / 2));
  }
  return judges.filter(function(j) {
    return (scores[j] !== undefined ? scores[j] : 0) >= state.jThresh;
  });
}

function computeStudentScores(tStar, jStar) {
  var tSet = {};
  tStar.forEach(function(t) { tSet[t] = true; });
  var jSet = {};
  jStar.forEach(function(j) { jSet[j] = true; });

  var sums = {}, counts = {};
  DATA.students.forEach(function(s) { sums[s] = 0; counts[s] = 0; });

  Object.keys(DATA.units_tsj).forEach(function(key) {
    var parts = key.split('||');
    var t = parts[0], s = parts[1], j = parts[2];
    if (tSet[t] && jSet[j] && sums.hasOwnProperty(s)) {
      sums[s] += DATA.units_tsj[key];
      counts[s]++;
    }
  });

  var result = {};
  DATA.students.forEach(function(s) {
    result[s] = counts[s] > 0 ? Math.round(sums[s] / counts[s] * 10000) / 10000 : null;
  });
  return result;
}

function computeAspectScores(tStar, jStar) {
  var tSet = {};
  tStar.forEach(function(t) { tSet[t] = true; });
  var jSet = {};
  jStar.forEach(function(j) { jSet[j] = true; });

  // units_tsja: teacher||student||judge||aspect -> avg score
  // We need to re-derive from units_tsj by aspect; we don't have it pre-grouped,
  // so use DATA.asp_units_tsja if present, else fall back to DATA.asp_student
  if (DATA.asp_units_tsja) {
    var sums = {}, counts = {};
    Object.keys(DATA.asp_units_tsja).forEach(function(key) {
      var parts = key.split('||');
      var t = parts[0], s = parts[1], j = parts[2], a = parts[3];
      if (tSet[t] && jSet[j]) {
        var sk = s + '||' + a;
        sums[sk] = (sums[sk] || 0) + DATA.asp_units_tsja[key];
        counts[sk] = (counts[sk] || 0) + 1;
      }
    });
    var result = {};
    Object.keys(sums).forEach(function(sk) {
      result[sk] = Math.round(sums[sk] / counts[sk] * 10000) / 10000;
    });
    return result;
  }
  return DATA.asp_student;
}

/* ---------------------------------------------------------------
   renderAll — called on every control change
--------------------------------------------------------------- */
function renderAll() {
  var tStar = getEffectiveTeachers();
  var jStar = getConsensusJudges();

  // Update count labels
  var tCountEl = document.getElementById('t-effective-count');
  if (tCountEl) tCountEl.textContent =
    '(' + tStar.length + '/' + DATA.teachers.length + ' active)';
  var jCountEl = document.getElementById('j-effective-count');
  if (jCountEl) jCountEl.textContent =
    '(' + jStar.length + '/' + DATA.judges.length + ' active)';

  renderSummaryDynamic(tStar, jStar);

  var robustScores = computeStudentScores(tStar, jStar);
  var fullScores   = DATA.full_scores;

  renderRankingDynamic(robustScores, fullScores, tStar, jStar);
  renderChartsDynamic(robustScores, fullScores, tStar, jStar);
}

/* ---------------------------------------------------------------
   View 1 — Summary panel
--------------------------------------------------------------- */
function renderSummaryDynamic(tStar, jStar) {
  var tScores = DATA.teacher_scores[state.formula];
  var jScores = DATA.judge_scores[state.jMet];
  var tScoreStr = tStar.map(function(t) {
    return t + '(' + fmt(tScores[t]) + ')';
  }).join(', ') || '(none)';
  var jScoreStr = jStar.map(function(j) {
    return j + '(' + fmt(jScores[j]) + ')';
  }).join(', ') || '(none)';

  var lines = [
    'Active Filter Settings',
    '\u2500'.repeat(50),
    'Teacher formula:       ' + state.formula,
    'Teacher threshold:     \u2265 ' + state.tThresh.toFixed(2),
    'Active teachers (T*):  [' + tStar.join(', ') + ']  (N=' + tStar.length + '/' + DATA.teachers.length + ')',
    'Teacher scores:        ' + tScoreStr,
    '',
    'Judge selection:       ' + state.jSel,
    'Judge metric:          ' + state.jMet,
    'Judge threshold:       \u2265 ' + state.jThresh.toFixed(2),
    'Active judges (J*):    [' + jStar.join(', ') + ']  (N=' + jStar.length + '/' + DATA.judges.length + ')',
    'Judge scores:          ' + jScoreStr,
  ];
  var el = document.getElementById('summary-panel');
  if (el) el.textContent = lines.join('\\n');
}

/* ---------------------------------------------------------------
   View 2 — Ranking table
--------------------------------------------------------------- */
function renderRankingDynamic(robustScores, fullScores, tStar, jStar) {
  var students = DATA.students.slice();
  students.sort(function(a, b) {
    return (robustScores[b] !== null ? robustScores[b] : -1) -
           (robustScores[a] !== null ? robustScores[a] : -1);
  });

  var html = '<table class="data-table"><tr><th>#</th><th>Student</th>';
  html += '<th>Robust Avg</th><th>Full-Run Avg</th><th>Delta</th></tr>';
  students.forEach(function(s, idx) {
    var robAvg = robustScores[s];
    var fullAvg = fullScores[s] !== undefined ? fullScores[s] : null;
    var delta = (robAvg !== null && fullAvg !== null)
      ? Math.round((robAvg - fullAvg) * 10000) / 10000 : null;
    var large = delta !== null && Math.abs(delta) > 0.1;
    var style = large ? 'background:#fff3cd' : '';
    var flag  = large ? '<span class="warn-flag" title="Large difference.">&#9888;</span>' : '';
    html += '<tr style="' + style + '"><td>' + (idx+1) + '</td><td>' + s + '</td>';
    html += '<td>' + fmt(robAvg) + '</td>';
    html += '<td>' + fmt(fullAvg) + '</td>';
    html += '<td>' + fmt(delta) + flag + '</td></tr>';
  });
  var el = document.getElementById('v2-table');
  if (el) el.innerHTML = html + '</table>';
}

/* ---------------------------------------------------------------
   Views 3, 4, 5 — Charts
--------------------------------------------------------------- */
function renderChartsDynamic(robustScores, fullScores, tStar, jStar) {
  // V3 — Scatter: Full vs Robust
  var students = DATA.students.filter(function(s) {
    return robustScores[s] !== null && fullScores[s] !== null;
  });
  if (students.length) {
    Plotly.react('v3-chart', [
      {
        type:'scatter', mode:'markers+text',
        x: students.map(function(s) { return fullScores[s]; }),
        y: students.map(function(s) { return robustScores[s]; }),
        text: students.map(function(s) { return s; }),
        textposition:'top center',
        marker:{size:10, color:'#2980b9'},
        hovertemplate:'%{text}<br>Full: %{x:.3f}<br>Robust: %{y:.3f}<extra></extra>',
      },
      {
        type:'scatter', mode:'lines', x:[0,1], y:[0,1],
        line:{color:'#aaa', dash:'dash'}, showlegend:false,
      },
    ], {
      xaxis:{title:'Full-run avg', range:[0,1.05]},
      yaxis:{title:'Robust avg', range:[0,1.05]},
      margin:{t:20},
    });
  }

  // V4 — Aspect heatmap filtered by tStar/jStar
  var aspScores = computeAspectScores(tStar, jStar);
  var studs = DATA.students;
  var aspects = DATA.aspects;
  if (studs.length && aspects.length) {
    var z = studs.map(function(s) {
      return aspects.map(function(a) {
        var v = aspScores[s + '||' + a];
        return v !== undefined ? v : null;
      });
    });
    Plotly.react('v4-chart', [{
      type:'heatmap', z:z, x:aspects, y:studs,
      colorscale:[[0,'#ffe0e0'],[0.5,'#fff7e0'],[1,'#e0ffe0']],
      zmin:0, zmax:1,
    }], {
      title:'Filtered scores (active T* + J*)',
      margin:{t:40},
    });
  }

  // V5 — Coverage by teacher (how many units from that teacher are in active set)
  var tSet = {};
  tStar.forEach(function(t) { tSet[t] = true; });
  var rows = DATA.coverage_rows.map(function(r) {
    var isActive = tSet[r.teacher] ? 'Yes' : 'No';
    return {
      teacher: r.teacher,
      all_dp: r.all_dp,
      active: isActive,
    };
  });
  var html = '<table class="data-table"><tr><th>Teacher</th>';
  html += '<th>All Datapoints</th><th>In Active T*</th></tr>';
  rows.forEach(function(r) {
    var style = r.active === 'Yes' ? 'background:#e8f5e9' : '';
    html += '<tr style="' + style + '"><td>' + r.teacher + '</td>';
    html += '<td>' + r.all_dp + '</td><td>' + r.active + '</td></tr>';
  });
  var el = document.getElementById('v5-table');
  if (el) el.innerHTML = html + '</table>';
}

/* ---------------------------------------------------------------
   Event wiring
--------------------------------------------------------------- */
function wireControls() {
  // Formula buttons
  document.querySelectorAll('.formula-btn').forEach(function(btn) {
    btn.addEventListener('click', function() {
      document.querySelectorAll('.formula-btn').forEach(function(b) {
        b.classList.remove('active');
      });
      btn.classList.add('active');
      state.formula = btn.getAttribute('data-formula');
      renderAll();
    });
  });

  // Judge selection buttons
  document.querySelectorAll('.jsel-btn').forEach(function(btn) {
    btn.addEventListener('click', function() {
      document.querySelectorAll('.jsel-btn').forEach(function(b) {
        b.classList.remove('active');
      });
      btn.classList.add('active');
      state.jSel = btn.getAttribute('data-jsel');
      renderAll();
    });
  });

  // Judge metric buttons
  document.querySelectorAll('.jmet-btn').forEach(function(btn) {
    btn.addEventListener('click', function() {
      document.querySelectorAll('.jmet-btn').forEach(function(b) {
        b.classList.remove('active');
      });
      btn.classList.add('active');
      state.jMet = btn.getAttribute('data-jmet');
      renderAll();
    });
  });

  // Teacher threshold slider
  var tSlider = document.getElementById('t-thresh');
  var tVal    = document.getElementById('t-thresh-val');
  if (tSlider) {
    tSlider.addEventListener('input', function() {
      state.tThresh = parseFloat(tSlider.value);
      if (tVal) tVal.textContent = state.tThresh.toFixed(2);
      renderAll();
    });
  }

  // Judge threshold slider
  var jSlider = document.getElementById('j-thresh');
  var jVal    = document.getElementById('j-thresh-val');
  if (jSlider) {
    jSlider.addEventListener('input', function() {
      state.jThresh = parseFloat(jSlider.value);
      if (jVal) jVal.textContent = state.jThresh.toFixed(2);
      renderAll();
    });
  }
}

document.addEventListener('DOMContentLoaded', function() {
  wireControls();
  renderAll();
});
"""
