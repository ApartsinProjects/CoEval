"""Score Distribution Report — REQ-A-7.3.

Three interactive charts:
  1. Student Score Distribution — per student model performance
  2. Teacher Score Distribution — quality of teacher-generated datapoints
  3. Judge Score Distribution   — judge scoring behaviour

Each chart has:
  • Aggregation selector: change x-axis grouping (rubric / judge / teacher /
    student / task / target attribute)
  • Score-level selector: High | Medium | Low | Mean
  • Tooltips on rubric aspects, tasks, attributes (data-tip CSS)
  • ℹ help icon on chart title explaining the figure
  • Cross-filter with global Task / Judge / Teacher / Student dropdowns
"""
from __future__ import annotations

from collections import defaultdict
from pathlib import Path

from ..loader import EESDataModel
from .html_base import build_report, collect_tooltip_data, get_plotly_js, make_experiment_meta


def write_score_distribution(
    model: EESDataModel,
    out_dir: Path,
    shared_plotly: Path | None = None,
) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    if shared_plotly:
        import shutil; shutil.copy2(shared_plotly, out_dir / 'plotly.min.js')
    else:
        get_plotly_js(out_dir)

    exp_meta = make_experiment_meta(model)
    data = _build_data(model)

    filter_defs = [
        {'id': 'task',    'label': 'Task',    'options': [(t, t) for t in model.tasks]},
        {'id': 'judge',   'label': 'Judge',   'options': [(j, j) for j in model.judges]},
        {'id': 'teacher', 'label': 'Teacher', 'options': [(t, t) for t in model.teachers]},
        {'id': 'student', 'label': 'Student', 'options': [(s, s) for s in model.students]},
    ]

    return build_report(
        out_dir=out_dir,
        title=f'Score Distribution — {exp_meta["id"]}',
        data=data,
        views_html=_VIEWS_HTML,
        filter_defs=filter_defs,
        stats_text=exp_meta['stats'],
        experiment_meta=exp_meta,
        report_type='Score Distribution',
        extra_js=_APP_JS,
        partial=model.is_partial,
    )


# ---------------------------------------------------------------------------
# Data builder
# ---------------------------------------------------------------------------

def _build_data(model: EESDataModel) -> dict:
    units = model.units

    # Pre-compute attribute keys discovered across all datapoints
    attr_keys: list[str] = []
    for task_id, attrs in model.target_attrs_by_task.items():
        for k in attrs:
            if k not in attr_keys:
                attr_keys.append(k)

    # Flat unit records for JS (include dp-level target attrs)
    all_units = []
    for u in units:
        dp = model.datapoints.get(u.datapoint_id, {})
        attrs = dp.get('sampled_target_attributes', {}) or {}
        all_units.append({
            'task':       u.task_id,
            'teacher':    u.teacher_model_id,
            'student':    u.student_model_id,
            'judge':      u.judge_model_id,
            'aspect':     u.rubric_aspect,
            'score':      u.score,
            'score_norm': u.score_norm,
            'evaluated_at': u.evaluated_at,
            'attrs':      attrs,
        })

    tips = collect_tooltip_data(model)

    # Aggregation dimension options (same for all 3 charts)
    agg_dims = ['aspect', 'judge', 'teacher', 'student', 'task'] + attr_keys

    return {
        'all_units': all_units,
        'tasks':    model.tasks,
        'teachers': model.teachers,
        'students': model.students,
        'judges':   model.judges,
        'aspects':  sorted(set(u.rubric_aspect for u in units)),
        'attr_keys': attr_keys,
        'agg_dims': agg_dims,
        'tips':     tips,
    }


# ---------------------------------------------------------------------------
# HTML panels
# ---------------------------------------------------------------------------

_VIEWS_HTML = """
<style>
/* ---- Score Distribution extras ---- */
.sd-controls {
  display:flex; align-items:center; gap:14px; flex-wrap:wrap;
  padding:9px 13px; background:#f8fafc; border:1px solid #e2e8f0;
  border-radius:8px; margin-bottom:10px;
}
.sd-controls label { font-size:.77rem; font-weight:600; color:#475569; }
.sd-controls select {
  border:1px solid #cbd5e1; border-radius:5px; padding:4px 8px;
  font-size:.77rem; background:#fff; cursor:pointer;
}
.help-icon {
  display:inline-block; width:17px; height:17px; line-height:17px; text-align:center;
  border-radius:50%; background:#64748b; color:#fff; font-size:.7rem; font-weight:700;
  cursor:help; margin-left:6px; vertical-align:middle; position:relative;
}
.help-icon::after {
  content: attr(data-tip);
  position:absolute; bottom:130%; left:50%; transform:translateX(-50%);
  background:#1e293b; color:#f1f5f9; padding:7px 11px; border-radius:6px;
  font-size:.72rem; font-weight:400; white-space:pre-wrap; max-width:280px;
  opacity:0; pointer-events:none; z-index:200; line-height:1.45;
  transition:opacity .18s; text-align:left;
}
.help-icon:hover::after { opacity:1; }
</style>

<!-- ====================================================== -->
<!-- Chart 1 — Student Score Distribution                   -->
<!-- ====================================================== -->
<div class="view-section" id="view-student">
  <h2>
    Student Score Distribution
    <span class="help-icon" data-tip="Shows how each student model scores on evaluations.\nX-axis: selected aggregation dimension.\nY-axis: fraction of scores at the chosen level.\nUse 'Mean' for normalised avg (0=Low, 0.5=Medium, 1=High).\nFilters above narrow the data to a specific task/judge/teacher.">ℹ</span>
  </h2>
  <div class="sd-controls">
    <label>Aggregate by:</label>
    <select id="s1-agg"   onchange="renderStudent()"></select>
    <label style="margin-left:8px">Score:</label>
    <select id="s1-level" onchange="renderStudent()">
      <option value="High">High</option>
      <option value="Medium">Medium</option>
      <option value="Low">Low</option>
      <option value="mean">Mean score</option>
    </select>
  </div>
  <div id="student-dist-chart" class="chart-container"></div>
  <details class="fig-explain">
    <summary>About this figure</summary>
    <div class="explain-body">
      <b>What it shows:</b> For each student model, the fraction of evaluations
      at the selected score level (High / Medium / Low) or the mean normalised
      score, broken down by the selected aggregation dimension.<br>
      <b>Aggregation options:</b>
      <b>aspect</b> — break down by rubric criterion;
      <b>judge</b> — compare student scores given by different judge models (reveals judge bias);
      <b>teacher</b> — compare performance on different teachers' datapoints;
      <b>task</b> — compare across tasks.<br>
      <b>Tip:</b> Switch to "Low" level and group by "aspect" to identify the rubric criterion
      where student models fail most.
    </div>
  </details>
</div>

<!-- ====================================================== -->
<!-- Chart 2 — Teacher Score Distribution                   -->
<!-- ====================================================== -->
<div class="view-section" id="view-teacher">
  <h2>
    Teacher Score Distribution
    <span class="help-icon" data-tip="Shows average student scores on each teacher's datapoints.\nHigh scores → teacher generates well-differentiated, appropriate problems.\nX-axis: aggregation dim; Y-axis: fraction/mean of student scores.">ℹ</span>
  </h2>
  <div class="sd-controls">
    <label>Aggregate by:</label>
    <select id="s2-agg"   onchange="renderTeacher()"></select>
    <label style="margin-left:8px">Score:</label>
    <select id="s2-level" onchange="renderTeacher()">
      <option value="High">High</option>
      <option value="Medium">Medium</option>
      <option value="Low">Low</option>
      <option value="mean">Mean score</option>
    </select>
  </div>
  <div id="teacher-dist-chart" class="chart-container"></div>
  <details class="fig-explain">
    <summary>About this figure</summary>
    <div class="explain-body">
      <b>What it shows:</b> For each teacher model, the fraction of student evaluations
      at the selected score level, broken down by the selected aggregation dimension.<br>
      <b>How to read it:</b> A teacher whose datapoints consistently yield Low scores
      may be generating overly difficult or ambiguous problems. A teacher with very high
      scores may not be creating sufficient challenge for students.
    </div>
  </details>
</div>

<!-- ====================================================== -->
<!-- Chart 3 — Judge Score Distribution                     -->
<!-- ====================================================== -->
<div class="view-section" id="view-judge">
  <h2>
    Judge Score Distribution
    <span class="help-icon" data-tip="Shows scoring behaviour of each judge model.\nLarge differences between judges on the same aspect → calibration issues.\nX-axis: aggregation dim; Y-axis: fraction/mean of scores assigned.">ℹ</span>
  </h2>
  <div class="sd-controls">
    <label>Aggregate by:</label>
    <select id="s3-agg"   onchange="renderJudge()"></select>
    <label style="margin-left:8px">Score:</label>
    <select id="s3-level" onchange="renderJudge()">
      <option value="High">High</option>
      <option value="Medium">Medium</option>
      <option value="Low">Low</option>
      <option value="mean">Mean score</option>
    </select>
  </div>
  <div id="judge-dist-chart" class="chart-container"></div>
  <details class="fig-explain">
    <summary>About this figure</summary>
    <div class="explain-body">
      <b>What it shows:</b> For each judge model, the fraction of evaluations at the
      selected score level, broken down by the chosen aggregation dimension.<br>
      <b>How to read it:</b> Judges that award very high or very low scores compared
      to peers on the same rubric aspect may be miscalibrated.  Use teacher or
      student aggregation to check whether judge behaviour is consistent across
      different teacher / student combinations.
    </div>
  </details>
</div>
"""


# ---------------------------------------------------------------------------
# JavaScript
# ---------------------------------------------------------------------------

_APP_JS = r"""
// -----------------------------------------------------------------------
// Helpers
// -----------------------------------------------------------------------
function escHtml(s) {
  return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

// Return tooltip text for a key (aspect / task / attr)
function _tipText(key) {
  var tips = DATA.tips || {};
  return (tips.aspects && tips.aspects[key])
      || (tips.tasks   && tips.tasks[key])
      || (tips.attrs   && tips.attrs[key])
      || '';
}

// Build a hover-template-aware label for an aspect
function _hoverTip(key) {
  var t = _tipText(key);
  return t ? escHtml(key) + ' — ' + escHtml(t.substring(0, 100)) : escHtml(key);
}

// -----------------------------------------------------------------------
// Shared filter logic
// -----------------------------------------------------------------------
function filteredUnits() {
  var tf = getFilter('task'),    jf = getFilter('judge');
  var tef = getFilter('teacher'), sf = getFilter('student');
  return DATA.all_units.filter(function(u) {
    return (tf  === '__all__' || u.task    === tf)
        && (jf  === '__all__' || u.judge   === jf)
        && (tef === '__all__' || u.teacher === tef)
        && (sf  === '__all__' || u.student === sf);
  });
}

// -----------------------------------------------------------------------
// Populate an aggregation dropdown
// -----------------------------------------------------------------------
function _populateAgg(selId, excludeDim) {
  var sel = document.getElementById(selId);
  if (!sel) return;
  var dimLabels = {
    'aspect': 'Rubric aspect', 'judge': 'Judge model',
    'teacher': 'Teacher model', 'student': 'Student model',
    'task': 'Task'
  };
  sel.innerHTML = '';
  var dims = DATA.agg_dims || ['aspect', 'judge', 'teacher', 'student', 'task'];
  dims.forEach(function(d) {
    if (d === excludeDim) return;  // skip self-dimension
    var opt = document.createElement('option');
    opt.value = d;
    opt.textContent = dimLabels[d] || d.replace(/_/g,' ').replace(/\b\w/g,function(c){return c.toUpperCase();});
    sel.appendChild(opt);
  });
}

// -----------------------------------------------------------------------
// Core chart renderer
// -----------------------------------------------------------------------
// modelDim:   which unit field identifies the "model" being analysed
//             ('student', 'teacher', 'judge')
// aggDim:     which unit field is the x-axis grouping
// level:      'High'|'Medium'|'Low'|'mean'
// divId:      DOM element to render into
// yLabel:     y-axis title
// -----------------------------------------------------------------------
function _renderDistChart(modelDim, aggDim, level, divId, yLabel) {
  var units = filteredUnits();

  // Collect models and x-values
  var modelSet = {}, xSet = {};
  units.forEach(function(u) {
    var m = u[modelDim] || '(none)';
    var xVal = _getAggValue(u, aggDim);
    modelSet[m] = true;
    xSet[xVal] = true;
  });
  var models = Object.keys(modelSet).sort();
  var xVals  = Object.keys(xSet).sort();

  if (models.length === 0 || xVals.length === 0) {
    document.getElementById(divId).innerHTML =
      '<p style="padding:16px;color:#64748b">No data for the current filter selection.</p>';
    return;
  }

  // Accumulate per (model, xVal)
  var counts = {};  // key = model+'||'+xVal → {High:0,Medium:0,Low:0,total:0,sum:0}
  units.forEach(function(u) {
    var m = u[modelDim] || '(none)';
    var xVal = _getAggValue(u, aggDim);
    var k = m + '||' + xVal;
    if (!counts[k]) counts[k] = {High:0, Medium:0, Low:0, total:0, sum:0};
    counts[k][u.score]++;
    counts[k].total++;
    counts[k].sum += u.score_norm;
  });

  // One trace per model
  var palette = [
    '#3b82f6','#22c55e','#f59e0b','#ef4444','#8b5cf6',
    '#06b6d4','#ec4899','#84cc16','#f97316','#14b8a6',
    '#6366f1','#a3e635','#fb923c','#38bdf8','#e879f9',
  ];
  var traces = models.map(function(m, mi) {
    var y = xVals.map(function(x) {
      var k = m + '||' + x;
      var c = counts[k];
      if (!c || c.total === 0) return 0;
      if (level === 'mean') return +(c.sum / c.total).toFixed(3);
      return +(c[level] / c.total).toFixed(3);
    });
    var hoverLines = xVals.map(function(x) {
      var k = m + '||' + x;
      var c = counts[k] || {High:0,Medium:0,Low:0,total:0,sum:0};
      var tip = _tipText(x);
      return '<b>' + escHtml(x) + '</b>'
        + (tip ? '<br><i style="font-size:0.85em;">' + escHtml(tip.substring(0,80)) + '</i>' : '')
        + '<br>Model: ' + escHtml(m)
        + '<br>High: '  + c.High + ' / Med: ' + c.Medium + ' / Low: ' + c.Low
        + '<br>Total: ' + c.total;
    });
    return {
      name: m,
      type: 'bar',
      x: xVals,
      y: y,
      text: hoverLines,
      hovertemplate: '%{text}<extra></extra>',
      marker: { color: palette[mi % palette.length] },
    };
  });

  var yAxisTitle = level === 'mean'
    ? 'Mean normalised score (0–1)'
    : 'Fraction ' + level;

  var heightPx = Math.max(300, xVals.length * (models.length * 16 + 20) + 120);
  heightPx = Math.min(heightPx, 600);

  Plotly.newPlot(divId, traces, {
    barmode: 'group',
    xaxis: {
      title: _dimLabel(aggDim),
      tickangle: xVals.length > 5 ? -35 : 0,
      automargin: true,
    },
    yaxis: {
      title: yAxisTitle,
      range: [0, level === 'mean' ? 1.05 : 1.05],
      rangemode: 'tozero',
    },
    legend: { orientation: 'h', y: -0.28, x: 0.5, xanchor: 'center', font: {size:11} },
    margin: { t: 20, b: 130, l: 60, r: 20 },
    height: heightPx,
    paper_bgcolor: '#fff',
    plot_bgcolor: '#f8fafc',
  }, { responsive: true });
}

// -----------------------------------------------------------------------
// Get aggregation value for a unit (handles target attribute keys)
// -----------------------------------------------------------------------
function _getAggValue(u, aggDim) {
  if (aggDim === 'aspect')  return u.aspect  || '(none)';
  if (aggDim === 'judge')   return u.judge   || '(none)';
  if (aggDim === 'teacher') return u.teacher || '(none)';
  if (aggDim === 'student') return u.student || '(none)';
  if (aggDim === 'task')    return u.task    || '(none)';
  // Target attribute key
  var attrVal = u.attrs && u.attrs[aggDim];
  return attrVal !== undefined && attrVal !== null ? String(attrVal) : '(none)';
}

function _dimLabel(d) {
  var labels = {
    'aspect': 'Rubric aspect', 'judge': 'Judge model',
    'teacher': 'Teacher model', 'student': 'Student model', 'task': 'Task'
  };
  return labels[d] || d.replace(/_/g,' ');
}

// -----------------------------------------------------------------------
// Per-chart render functions
// -----------------------------------------------------------------------
function renderStudent() {
  var agg   = (document.getElementById('s1-agg')   || {}).value || 'aspect';
  var level = (document.getElementById('s1-level') || {}).value || 'High';
  _renderDistChart('student', agg, level, 'student-dist-chart', 'Student models');
}

function renderTeacher() {
  var agg   = (document.getElementById('s2-agg')   || {}).value || 'aspect';
  var level = (document.getElementById('s2-level') || {}).value || 'High';
  _renderDistChart('teacher', agg, level, 'teacher-dist-chart', 'Teacher models');
}

function renderJudge() {
  var agg   = (document.getElementById('s3-agg')   || {}).value || 'aspect';
  var level = (document.getElementById('s3-level') || {}).value || 'mean';
  _renderDistChart('judge', agg, level, 'judge-dist-chart', 'Judge models');
}

// -----------------------------------------------------------------------
// Entry point
// -----------------------------------------------------------------------
function renderAll() {
  _populateAgg('s1-agg', 'student');
  _populateAgg('s2-agg', 'teacher');
  _populateAgg('s3-agg', 'judge');
  // Set default aggregation (aspect for student/teacher, aspect for judge)
  var s3Agg = document.getElementById('s3-agg');
  if (s3Agg && s3Agg.options.length) s3Agg.value = 'aspect';
  // Default judge score to mean
  var s3Level = document.getElementById('s3-level');
  if (s3Level) s3Level.value = 'mean';
  renderStudent();
  renderTeacher();
  renderJudge();
}

document.addEventListener('DOMContentLoaded', renderAll);
"""
