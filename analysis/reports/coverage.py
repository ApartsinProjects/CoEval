"""Coverage Summary Report — REQ-A-7.9."""
from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

from ..loader import EESDataModel
from .html_base import build_report, get_plotly_js, make_experiment_meta


def write_coverage_summary(
    model: EESDataModel,
    out_dir: Path,
    shared_plotly: Path | None = None,
) -> Path:
    """Generate Coverage Summary HTML folder (REQ-A-7.9)."""
    out_dir.mkdir(parents=True, exist_ok=True)

    if shared_plotly:
        import shutil
        shutil.copy2(shared_plotly, out_dir / 'plotly.min.js')
    else:
        get_plotly_js(out_dir)

    exp_meta = make_experiment_meta(model)
    data = _build_data(model)

    views_html = _build_views_html()

    filter_defs = [
        {'id': 'task', 'label': 'Task',
         'options': [(t, t) for t in model.tasks]},
    ]

    return build_report(
        out_dir=out_dir,
        title=f'Coverage Summary — {exp_meta["id"]}',
        data=data,
        views_html=views_html,
        filter_defs=filter_defs,
        stats_text=exp_meta['stats'],
        experiment_meta=exp_meta,
        report_type='Coverage Summary',
        extra_js=_APP_JS,
        partial=model.is_partial,
    )


def _build_data(model: EESDataModel) -> dict:
    """Build the DATA object for the coverage report."""
    # View 1: coverage matrix
    coverage_rows = []

    # Expected evaluations per (task, teacher, student, judge)
    config_tasks = {t['name']: t for t in model.config.get('tasks', [])}
    sampling_total: dict[str, int] = {
        name: t.get('sampling', {}).get('total', 0)
        for name, t in config_tasks.items()
    }

    # Count actual and valid evaluations per (task, teacher, student, judge)
    actual_counts: dict[tuple, int] = defaultdict(int)
    valid_counts: dict[tuple, int] = defaultdict(int)
    error_breakdown: dict[tuple, dict] = defaultdict(lambda: defaultdict(int))

    for rec in model.eval_records:
        key = (rec.task_id, rec.teacher_model_id, rec.student_model_id, rec.judge_model_id)
        actual_counts[key] += 1
        if rec.valid:
            valid_counts[key] += 1
        for ec in rec.error_codes:
            error_breakdown[key][ec] += 1

    for key in sorted(actual_counts.keys()):
        task_id, teacher_id, student_id, judge_id = key
        expected = sampling_total.get(task_id, 0)
        actual = actual_counts[key]
        valid = valid_counts[key]
        invalid = actual - valid
        denom = expected if expected > 0 else actual
        coverage_pct = (valid / denom * 100) if denom > 0 else 0
        err_str = ', '.join(
            f'{k}:{v}' for k, v in sorted(error_breakdown[key].items())
        )
        coverage_rows.append({
            'task': task_id,
            'teacher': teacher_id,
            'student': student_id,
            'judge': judge_id,
            'expected': expected,
            'actual': actual,
            'valid': valid,
            'invalid': invalid,
            'coverage_pct': round(coverage_pct, 1),
            'errors': err_str,
        })

    # View 2: waterfall data per task
    waterfall_data = []
    for task_id in model.tasks:
        dp_count = sum(
            1 for dp in model.datapoints.values() if dp.get('task_id') == task_id
        )
        resp_count = sum(
            1 for r in model.responses.values() if r.get('task_id') == task_id
        )
        eval_actual = sum(
            actual_counts.get(k, 0) for k in actual_counts
            if k[0] == task_id
        )
        eval_valid = sum(
            valid_counts.get(k, 0) for k in valid_counts
            if k[0] == task_id
        )
        waterfall_data.append({
            'task': task_id,
            'datapoints': dp_count,
            'responses': resp_count,
            'eval_actual': eval_actual,
            'eval_valid': eval_valid,
        })

    # View 3: error code breakdown
    error_totals: dict[str, int] = defaultdict(int)
    for rec in model.eval_records:
        for ec in rec.error_codes:
            error_totals[ec] += 1

    # View 4: meta panel
    phases_completed = model.meta.get('phases_completed', [])
    phases_in_progress = model.meta.get('phases_in_progress', [])

    return {
        'coverage_rows': coverage_rows,
        'waterfall': waterfall_data,
        'error_totals': dict(error_totals),
        'meta_panel': {
            'experiment_id': model.meta.get('experiment_id', ''),
            'status': model.meta.get('status', ''),
            'created_at': model.meta.get('created_at', ''),
            'updated_at': model.meta.get('updated_at', ''),
            'phases_completed': phases_completed,
            'phases_in_progress': phases_in_progress,
            'tasks': len(model.tasks),
            'teachers': len(model.teachers),
            'students': len(model.students),
            'judges': len(model.judges),
            'datapoints': len(model.datapoints),
            'total_evals': model.total_records,
            'valid_evals': model.valid_records,
        },
    }


def _build_views_html() -> str:
    return """
<style>
/* ---- Coverage report interactive panels ---- */
.stat-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(150px, 1fr));
  gap: 14px;
  margin-bottom: 18px;
}
.stat-card {
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  border-radius: 10px;
  padding: 14px 16px;
  text-align: center;
}
.stat-card .stat-val {
  font-size: 2rem;
  font-weight: 700;
  color: #1e3a5f;
  line-height: 1;
}
.stat-card .stat-lbl {
  font-size: 0.72rem;
  color: #64748b;
  margin-top: 5px;
  text-transform: uppercase;
  letter-spacing: 0.04em;
}
.stat-card.good  .stat-val { color: #16a34a; }
.stat-card.warn  .stat-val { color: #d97706; }
.stat-card.bad   .stat-val { color: #dc2626; }

.phase-timeline {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 12px;
}
.phase-badge {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 4px 12px;
  border-radius: 20px;
  font-size: 0.73rem;
  font-weight: 600;
  border: 1px solid;
}
.phase-badge.done     { background: #dcfce7; color: #15803d; border-color: #86efac; }
.phase-badge.running  { background: #fef3c7; color: #b45309; border-color: #fcd34d; }
.phase-badge.pending  { background: #f1f5f9; color: #64748b; border-color: #cbd5e1; }
.phase-badge .ph-dot  { width: 7px; height: 7px; border-radius: 50%; background: currentColor; }

.coverage-controls {
  display: flex;
  align-items: center;
  gap: 14px;
  flex-wrap: wrap;
  margin-bottom: 12px;
  padding: 10px 14px;
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
}
.coverage-controls label {
  font-size: 0.78rem;
  font-weight: 600;
  color: #475569;
}
.coverage-controls select {
  border: 1px solid #cbd5e1;
  border-radius: 5px;
  padding: 4px 8px;
  font-size: 0.78rem;
  background: #fff;
}
.coverage-legend {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 0.72rem;
  color: #64748b;
  margin-left: auto;
}
.legend-bar {
  width: 80px;
  height: 10px;
  border-radius: 4px;
  background: linear-gradient(to right, #ef4444, #facc15, #22c55e);
  border: 1px solid #e2e8f0;
}
</style>

<!-- ============================================================ -->
<!-- Panel 1 — Experiment Overview                                -->
<!-- ============================================================ -->
<div class="view-section" id="view-meta">
  <h2>Overview</h2>
  <div id="stat-grid-container"></div>
  <div id="phase-timeline-container"></div>
  <details class="fig-explain">
    <summary>About this panel</summary>
    <div class="explain-body">
      <b>Stat cards</b> summarise the experiment at a glance: number of tasks, teacher/student/judge
      models, generated datapoints, and overall valid-evaluation coverage.<br>
      <b>Coverage %</b> = valid evaluations ÷ expected evaluations × 100. Values below 90 % are
      flagged amber; below 80 % are flagged red.<br>
      <b>Phase timeline</b> shows which pipeline phases have completed (<span style="color:#15803d">✓ done</span>),
      are in progress (<span style="color:#b45309">… running</span>), or are still pending
      (<span style="color:#64748b">○ pending</span>).
    </div>
  </details>
</div>

<!-- ============================================================ -->
<!-- Panel 2 — Coverage Heatmaps                                  -->
<!-- ============================================================ -->
<div class="view-section" id="view-coverage">
  <h2>Coverage Heatmaps</h2>
  <div class="coverage-controls">
    <label>Judge:</label>
    <select id="cov-judge-select" onchange="renderCoverageHeatmaps()"></select>
    <div class="coverage-legend" id="cov-legend-label">
      <span id="cov-legend-low">0 %</span>
      <div class="legend-bar" id="cov-legend-bar"></div>
      <span id="cov-legend-high">100 %</span>
    </div>
  </div>
  <div id="coverage-heatmap-container"></div>
  <details class="fig-explain">
    <summary>About this figure</summary>
    <div class="explain-body">
      <b>What it shows:</b> One heatmap per task. Each cell represents a
      (teacher&nbsp;×&nbsp;student) pair evaluated by the selected judge. Cell colour
      encodes the valid-evaluation coverage percentage for that combination.<br>
      <b>Colour scale:</b> The palette is selected dynamically based on the actual data
      range. When all values are tightly clustered (range &lt; 20 pp), a high-contrast
      sequential scale is used to reveal small differences. When values span a wide range,
      a diverging red→yellow→green scale is used.<br>
      <b>How to read it:</b> A fully green heatmap means every expected evaluation record
      was generated and is valid. Red or orange cells indicate missing or invalid evaluations
      — often caused by judge model failures or API timeouts. Hover over a cell for counts
      and error codes.
    </div>
  </details>
</div>

<!-- ============================================================ -->
<!-- Panel 3 — Phase Coverage Waterfall                           -->
<!-- ============================================================ -->
<div class="view-section" id="view-waterfall">
  <h2>Phase Coverage Waterfall</h2>
  <div id="waterfall-chart" class="chart-container"></div>
  <details class="fig-explain">
    <summary>About this figure</summary>
    <div class="explain-body">
      <b>What it shows:</b> A grouped bar chart showing artifact counts at each pipeline
      stage, broken down by task.<br>
      <b>Bars:</b>
      <b>Datapoints (P3)</b> = items generated by teacher models in Phase 3;
      <b>Responses (P4)</b> = student-model responses collected in Phase 4;
      <b>Evals total</b> = all evaluation records written in Phase 5 (including invalid);
      <b>Evals valid</b> = evaluation records that passed validation and carry usable scores.<br>
      <b>How to read it:</b> The bars should form a waterfall: Datapoints ≥ Responses ≥ Evals.
      A large gap between <em>Evals total</em> and <em>Evals valid</em> signals systematic
      judge failures for that task. A gap between <em>Datapoints</em> and <em>Responses</em>
      indicates student models that failed or were skipped.
    </div>
  </details>
</div>

<!-- ============================================================ -->
<!-- Panel 4 — Error Code Breakdown                               -->
<!-- ============================================================ -->
<div class="view-section" id="view-errors">
  <h2>Error Code Breakdown</h2>
  <div id="error-chart" class="chart-container"></div>
  <details class="fig-explain">
    <summary>About this figure</summary>
    <div class="explain-body">
      <b>What it shows:</b> A bar chart of error code frequencies across all invalid
      evaluation records in the experiment. Each bar is labelled with its percentage
      share of total errors.<br>
      <b>Common error codes:</b>
      <code>empty_output</code> — judge produced no text;
      <code>json_parse</code> — judge output could not be parsed as JSON;
      <code>missing_scores</code> — parsed JSON lacked required score fields;
      <code>api_error</code> — provider API returned an error.<br>
      <b>How to read it:</b> The dominant error code usually reveals the root cause.
      <code>empty_output</code> and <code>json_parse</code> together typically indicate
      that the judge model is too small to reliably follow the structured evaluation prompt.
    </div>
  </details>
</div>
"""


_APP_JS = """
// -----------------------------------------------------------------------
// Main render entry
// -----------------------------------------------------------------------
function renderAll() {
  renderMeta();
  populateJudgeSelect();
  renderCoverageHeatmaps();
  renderWaterfall();
  renderErrors();
}

// -----------------------------------------------------------------------
// Panel 1 — Overview stat cards + phase timeline
// -----------------------------------------------------------------------
function renderMeta() {
  var m = DATA.meta_panel;
  var validPct = m.total_evals > 0
    ? Math.round(m.valid_evals / m.total_evals * 100) : 100;

  var statClass = validPct === 100 ? 'good' : (validPct >= 90 ? 'warn' : 'bad');

  var stats = [
    { val: m.tasks,      lbl: 'Tasks',       cls: '' },
    { val: m.teachers,   lbl: 'Teachers',    cls: '' },
    { val: m.students,   lbl: 'Students',    cls: '' },
    { val: m.judges,     lbl: 'Judges',      cls: '' },
    { val: m.datapoints, lbl: 'Datapoints',  cls: '' },
    { val: m.total_evals,lbl: 'Total Evals', cls: '' },
    { val: m.valid_evals,lbl: 'Valid Evals', cls: statClass },
    { val: validPct + '%', lbl: 'Coverage',  cls: statClass },
  ];

  var gridHtml = '<div class="stat-grid">';
  stats.forEach(function(s) {
    gridHtml += '<div class="stat-card ' + s.cls + '">'
              + '<div class="stat-val">' + s.val + '</div>'
              + '<div class="stat-lbl">' + s.lbl + '</div>'
              + '</div>';
  });
  gridHtml += '</div>';
  document.getElementById('stat-grid-container').innerHTML = gridHtml;

  // Phase timeline
  var allPhases = [
    'attribute_mapping', 'rubric_mapping', 'data_generation',
    'response_collection', 'evaluation'
  ];
  var phaseLabels = {
    attribute_mapping:  'Attr Mapping',
    rubric_mapping:     'Rubric Mapping',
    data_generation:    'Data Gen',
    response_collection:'Resp Collection',
    evaluation:         'Evaluation'
  };
  var completed = new Set(m.phases_completed || []);
  var inProgress = new Set(m.phases_in_progress || []);

  var tlHtml = '<div class="phase-timeline">';
  allPhases.forEach(function(ph) {
    var cls = completed.has(ph) ? 'done' : (inProgress.has(ph) ? 'running' : 'pending');
    var icon = completed.has(ph) ? '✓' : (inProgress.has(ph) ? '…' : '○');
    tlHtml += '<span class="phase-badge ' + cls + '">'
            + '<span class="ph-dot"></span>'
            + icon + ' ' + (phaseLabels[ph] || ph)
            + '</span>';
  });
  tlHtml += '</div>';
  document.getElementById('phase-timeline-container').innerHTML = tlHtml;
}

// -----------------------------------------------------------------------
// Panel 2 — Coverage heatmaps (one Plotly heatmap per task)
// -----------------------------------------------------------------------
function _getUniqueValues(rows, key) {
  var seen = {};
  var vals = [];
  rows.forEach(function(r) {
    if (!seen[r[key]]) { seen[r[key]] = true; vals.push(r[key]); }
  });
  return vals.sort();
}

function populateJudgeSelect() {
  var judges = _getUniqueValues(DATA.coverage_rows, 'judge');
  var sel = document.getElementById('cov-judge-select');
  sel.innerHTML = '';
  judges.forEach(function(j) {
    var opt = document.createElement('option');
    opt.value = j; opt.textContent = j;
    sel.appendChild(opt);
  });
}

function renderCoverageHeatmaps() {
  var taskFilter = getFilter('task');
  var judgeFilter = document.getElementById('cov-judge-select').value;

  var rows = DATA.coverage_rows.filter(function(r) {
    return r.judge === judgeFilter &&
           (taskFilter === '__all__' || r.task === taskFilter);
  });

  var tasks = _getUniqueValues(rows, 'task');
  var container = document.getElementById('coverage-heatmap-container');

  if (rows.length === 0) {
    container.innerHTML = '<p style="color:#94a3b8;padding:20px">No data for this selection.</p>';
    return;
  }

  // One div per task
  container.innerHTML = '';
  tasks.forEach(function(task, idx) {
    var taskRows = rows.filter(function(r) { return r.task === task; });
    var teachers = _getUniqueValues(taskRows, 'teacher');
    var students = _getUniqueValues(taskRows, 'student');

    // Build z-matrix [teacher_index][student_index] = coverage_pct
    var z = teachers.map(function(t) {
      return students.map(function(s) {
        var match = taskRows.find(function(r){ return r.teacher === t && r.student === s; });
        return match ? match.coverage_pct : null;
      });
    });

    // Hover text
    var text = teachers.map(function(t) {
      return students.map(function(s) {
        var r = taskRows.find(function(r){ return r.teacher === t && r.student === s; });
        if (!r) return 'No data';
        return 'Teacher: ' + r.teacher
          + '<br>Student: ' + r.student
          + '<br>Expected: ' + r.expected
          + '<br>Actual: ' + r.actual
          + '<br>Valid: ' + r.valid
          + '<br>Invalid: ' + r.invalid
          + '<br>Coverage: ' + r.coverage_pct + '%'
          + (r.errors ? '<br>Errors: ' + r.errors : '');
      });
    });

    // --- Dynamic colour scale based on actual data range ---
    var validZ = [];
    z.forEach(function(row) { row.forEach(function(v) { if (v !== null) validZ.push(v); }); });
    var dataMin = validZ.length ? Math.min.apply(null, validZ) : 0;
    var dataMax = validZ.length ? Math.max.apply(null, validZ) : 100;
    var dataRange = dataMax - dataMin;

    var colorscale, zminVal, zmaxVal, legendLow, legendHigh, barGradient;
    if (dataRange < 15) {
      // Very tight range — sequential high-contrast blue scale, padded ±5 pp
      zminVal = Math.max(0, dataMin - 5);
      zmaxVal = Math.min(100, dataMax + 5);
      colorscale = [[0,'#0369a1'],[0.35,'#38bdf8'],[0.7,'#a5f3fc'],[1.0,'#ecfdf5']];
      barGradient = 'linear-gradient(to right, #0369a1, #38bdf8, #ecfdf5)';
      legendLow = dataMin.toFixed(0) + ' %';
      legendHigh = dataMax.toFixed(0) + ' %';
    } else if (dataMin >= 75) {
      // All high — green gradient with precise scaling
      zminVal = Math.max(50, dataMin - 10);
      zmaxVal = 100;
      colorscale = [[0,'#fef9c3'],[0.4,'#86efac'],[1.0,'#15803d']];
      barGradient = 'linear-gradient(to right, #fef9c3, #86efac, #15803d)';
      legendLow = zminVal.toFixed(0) + ' %';
      legendHigh = '100 %';
    } else {
      // Wide or mixed range — vivid 5-stop RdYlGn
      zminVal = 0; zmaxVal = 100;
      colorscale = [
        [0.0,  '#7f0000'],
        [0.2,  '#d73027'],
        [0.5,  '#ffffbf'],
        [0.75, '#1a9850'],
        [1.0,  '#00441b'],
      ];
      barGradient = 'linear-gradient(to right, #7f0000, #d73027, #ffffbf, #1a9850, #00441b)';
      legendLow = '0 %'; legendHigh = '100 %';
    }

    // Update legend bar in the controls row (only on first task)
    if (idx === 0) {
      var lb = document.getElementById('cov-legend-bar');
      var ll = document.getElementById('cov-legend-low');
      var lh = document.getElementById('cov-legend-high');
      if (lb) lb.style.background = barGradient;
      if (ll) ll.textContent = legendLow;
      if (lh) lh.textContent = legendHigh;
    }
    // -------------------------------------------------------

    var divId = 'heatmap-task-' + idx;
    var divEl = document.createElement('div');
    divEl.id = divId;
    divEl.style.marginBottom = '28px';
    container.appendChild(divEl);

    var heightPx = Math.max(200, teachers.length * 44 + 80);

    Plotly.newPlot(divId, [{
      type: 'heatmap',
      z: z,
      x: students,
      y: teachers,
      text: text,
      hovertemplate: '%{text}<extra></extra>',
      colorscale: colorscale,
      zmin: zminVal, zmax: zmaxVal,
      colorbar: {
        title: { text: 'Coverage %', side: 'right' },
        thickness: 14,
        len: 0.8,
        ticksuffix: '%',
      },
      xgap: 2, ygap: 2,
    }], {
      title: { text: 'Task: ' + task + ' &nbsp;|&nbsp; Judge: ' + judgeFilter,
               font: { size: 13 } },
      xaxis: { title: 'Student', tickangle: -30, automargin: true },
      yaxis: { title: 'Teacher', automargin: true },
      margin: { t: 50, l: 130, r: 80, b: 90 },
      height: heightPx,
      paper_bgcolor: '#fff',
      plot_bgcolor: '#f8fafc',
    }, { responsive: true });
  });
}

// -----------------------------------------------------------------------
// Panel 3 — Phase Coverage Waterfall (grouped bar chart)
// -----------------------------------------------------------------------
function renderWaterfall() {
  var wf = DATA.waterfall;
  if (!wf || wf.length === 0) return;
  var tasks = wf.map(function(w) { return w.task; });
  var traces = [
    { name: 'Datapoints (P3)',
      y: wf.map(function(w){return w.datapoints;}), x: tasks,
      type: 'bar', marker: { color: '#3b82f6' }, width: 0.18 },
    { name: 'Responses (P4)',
      y: wf.map(function(w){return w.responses;}), x: tasks,
      type: 'bar', marker: { color: '#8b5cf6' }, width: 0.18 },
    { name: 'Evals (total)',
      y: wf.map(function(w){return w.eval_actual;}), x: tasks,
      type: 'bar', marker: { color: '#f59e0b' }, width: 0.18 },
    { name: 'Evals (valid)',
      y: wf.map(function(w){return w.eval_valid;}), x: tasks,
      type: 'bar', marker: { color: '#22c55e' }, width: 0.18 },
  ];
  Plotly.newPlot('waterfall-chart', traces, {
    barmode: 'group',
    xaxis: { title: 'Task', automargin: true },
    yaxis: { title: 'Artifact count', rangemode: 'tozero' },
    legend: { orientation: 'h', y: -0.22 },
    margin: { t: 20, b: 100 },
    paper_bgcolor: '#fff',
    plot_bgcolor: '#f8fafc',
  }, { responsive: true });
}

// -----------------------------------------------------------------------
// Panel 4 — Error Code Breakdown
// -----------------------------------------------------------------------
function renderErrors() {
  var et = DATA.error_totals;
  var keys = Object.keys(et).sort(function(a, b){ return et[b] - et[a]; });
  if (keys.length === 0) {
    document.getElementById('error-chart').innerHTML =
      '<div style="display:flex;align-items:center;gap:10px;padding:20px;color:#16a34a;">'
      + '<span style="font-size:1.5rem;">&#10003;</span>'
      + '<span style="font-size:0.9rem;font-weight:500;">No errors found in evaluation records.</span></div>';
    return;
  }
  var vals = keys.map(function(k) { return et[k]; });
  var total = vals.reduce(function(a, b){ return a + b; }, 0);
  var pcts  = vals.map(function(v){ return (v / total * 100).toFixed(1) + '%'; });

  Plotly.newPlot('error-chart', [{
    type: 'bar',
    x: keys,
    y: vals,
    text: pcts,
    textposition: 'outside',
    marker: {
      color: vals.map(function(_, i) {
        var colors = ['#ef4444','#f97316','#f59e0b','#84cc16','#06b6d4'];
        return colors[i % colors.length];
      }),
    },
    hovertemplate: '<b>%{x}</b><br>Count: %{y}<br>Share: %{text}<extra></extra>',
  }], {
    xaxis: { title: 'Error code', automargin: true },
    yaxis: { title: 'Count', rangemode: 'tozero' },
    margin: { t: 20, b: 80 },
    paper_bgcolor: '#fff',
    plot_bgcolor: '#f8fafc',
  }, { responsive: true });
}

document.addEventListener('DOMContentLoaded', renderAll);
"""
