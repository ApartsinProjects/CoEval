"""Score Distribution Report — REQ-A-7.3.

Three interactive charts:
  1. Student Score Distribution — per student model performance
  2. Teacher Score Distribution — quality of teacher-generated datapoints
  3. Judge Score Distribution   — judge scoring behaviour

Each chart has:
  • Aggregation selector: change x-axis grouping (rubric / judge / teacher /
    student / task / target attribute)
  • View selector: Stacked (H/M/L fractions) | Average (mean normalised score)
  • Tooltips on rubric aspects, tasks, attributes (floating chart tooltips)
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
    <span class="help-icon" data-tip="Shows how each student model scores on evaluations.\nX-axis: selected aggregation dimension.\nStacked view: fraction High/Medium/Low across all students.\nAverage view: mean normalised score per student (Low=0, Med=0.5, High=1).\nFilters above narrow the data to a specific task/judge/teacher.">ℹ</span>
  </h2>
  <div class="sd-controls">
    <label>Aggregate by:</label>
    <select id="s1-agg"  onchange="renderStudent()"></select>
    <label style="margin-left:8px">View:</label>
    <select id="s1-view" onchange="renderStudent()">
      <option value="stacked">Stacked (H / M / L)</option>
      <option value="average">Average (mean score)</option>
    </select>
  </div>
  <div id="student-dist-chart" class="chart-container"></div>
  <details class="fig-explain">
    <summary>About this figure</summary>
    <div class="explain-body">
      <b>Stacked view:</b> For each value of the aggregation dimension (e.g. rubric aspect),
      one stacked bar shows the fraction of evaluations scored High (green) / Medium (amber) /
      Low (red), aggregated across all student models in the current filter.<br>
      <b>Average view:</b> Grouped bars — one bar per student model per x-value — showing
      mean normalised score (Low = 0, Medium = 0.5, High = 1).<br>
      <b>Tip:</b> Switch to Stacked and aggregate by "aspect" to see overall rubric difficulty.
      Switch to Average and aggregate by "judge" to compare student performance across judges.
    </div>
  </details>
</div>

<!-- ====================================================== -->
<!-- Chart 2 — Teacher Score Distribution                   -->
<!-- ====================================================== -->
<div class="view-section" id="view-teacher">
  <h2>
    Teacher Score Distribution
    <span class="help-icon" data-tip="Shows average student scores on each teacher's datapoints.\nHigh scores → teacher generates well-differentiated, appropriate problems.\nStacked: fraction H/M/L across all teachers.\nAverage: mean score per teacher.">ℹ</span>
  </h2>
  <div class="sd-controls">
    <label>Aggregate by:</label>
    <select id="s2-agg"  onchange="renderTeacher()"></select>
    <label style="margin-left:8px">View:</label>
    <select id="s2-view" onchange="renderTeacher()">
      <option value="stacked">Stacked (H / M / L)</option>
      <option value="average">Average (mean score)</option>
    </select>
  </div>
  <div id="teacher-dist-chart" class="chart-container"></div>
  <details class="fig-explain">
    <summary>About this figure</summary>
    <div class="explain-body">
      <b>What it shows:</b> For each teacher model, the distribution of student evaluation
      scores on items that teacher generated, broken down by the selected aggregation dimension.<br>
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
    <span class="help-icon" data-tip="Shows scoring behaviour of each judge model.\nLarge differences between judges on the same aspect → calibration issues.\nStacked: fraction H/M/L across all judges.\nAverage: mean score per judge.">ℹ</span>
  </h2>
  <div class="sd-controls">
    <label>Aggregate by:</label>
    <select id="s3-agg"  onchange="renderJudge()"></select>
    <label style="margin-left:8px">View:</label>
    <select id="s3-view" onchange="renderJudge()">
      <option value="average">Average (mean score)</option>
      <option value="stacked">Stacked (H / M / L)</option>
    </select>
  </div>
  <div id="judge-dist-chart" class="chart-container"></div>
  <details class="fig-explain">
    <summary>About this figure</summary>
    <div class="explain-body">
      <b>What it shows:</b> For each judge model, the distribution of scores awarded,
      broken down by the chosen aggregation dimension.<br>
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

function _tipText(key) {
  var tips = DATA.tips || {};
  return (tips.aspects && tips.aspects[key])
      || (tips.tasks   && tips.tasks[key])
      || (tips.attrs   && tips.attrs[key])
      || '';
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
    'teacher': 'Teacher model', 'student': 'Student model', 'task': 'Task'
  };
  sel.innerHTML = '';
  var dims = DATA.agg_dims || ['aspect', 'judge', 'teacher', 'student', 'task'];
  dims.forEach(function(d) {
    if (d === excludeDim) return;
    var opt = document.createElement('option');
    opt.value = d;
    opt.textContent = dimLabels[d] || d.replace(/_/g,' ').replace(/\b\w/g,function(c){return c.toUpperCase();});
    sel.appendChild(opt);
  });
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
// Core chart renderer
// modelDim: 'student' | 'teacher' | 'judge'  (which field is the "model")
// aggDim:   x-axis grouping dimension
// view:     'stacked' | 'average'
// divId:    DOM element id
// -----------------------------------------------------------------------
function _renderDistChart(modelDim, aggDim, view, divId) {
  var units = filteredUnits();

  var xSet = {};
  units.forEach(function(u) { xSet[_getAggValue(u, aggDim)] = true; });
  var xVals = Object.keys(xSet).sort();

  if (!xVals.length) {
    document.getElementById(divId).innerHTML =
      '<p style="padding:16px;color:#64748b">No data for the current filter selection.</p>';
    return;
  }

  if (view === 'stacked') {
    // ----- Stacked H/M/L view: aggregate across all models -----
    var xCounts = {};
    xVals.forEach(function(x) { xCounts[x] = {High:0, Medium:0, Low:0, total:0}; });
    units.forEach(function(u) {
      var x = _getAggValue(u, aggDim);
      var c = xCounts[x];
      if (c) { c[u.score] = (c[u.score] || 0) + 1; c.total++; }
    });

    var levelColors = {High:'#22c55e', Medium:'#fbbf24', Low:'#ef4444'};
    var traces = ['High','Medium','Low'].map(function(level) {
      var y = xVals.map(function(x) {
        var c = xCounts[x];
        return c.total > 0 ? +(c[level] / c.total).toFixed(3) : 0;
      });
      var hover = xVals.map(function(x) {
        var c = xCounts[x];
        var tip = _tipText(x);
        return '<b>' + escHtml(x) + '</b>'
          + (tip ? '<br><i style="font-size:.85em">' + escHtml(tip.substring(0,80)) + '</i>' : '')
          + '<br><b>' + level + ':</b> ' + c[level]
          + ' / ' + c.total
          + ' (' + (c.total > 0 ? (c[level]/c.total*100).toFixed(0) : '0') + '%)';
      });
      return {
        name: level, type: 'bar', x: xVals, y: y,
        text: hover, hovertemplate: '%{text}<extra></extra>',
        marker: { color: levelColors[level] },
      };
    });

    var hPx = Math.max(300, xVals.length * 28 + 140);
    hPx = Math.min(hPx, 560);

    Plotly.newPlot(divId, traces, {
      barmode: 'stack',
      xaxis: { title: _dimLabel(aggDim), tickangle: xVals.length > 5 ? -35 : 0, automargin: true },
      yaxis: { title: 'Fraction of evaluations', range: [0, 1.02], rangemode: 'tozero', gridcolor: '#f1f5f9' },
      legend: { orientation: 'h', y: -0.25, x: 0.5, xanchor: 'center', font: {size:11} },
      margin: { t: 20, b: 130, l: 60, r: 20 },
      height: hPx,
      paper_bgcolor: '#fff', plot_bgcolor: '#f8fafc',
    }, { responsive: true });

  } else {
    // ----- Average view: per-model grouped bars (mean score_norm) -----
    var modelSet = {};
    units.forEach(function(u) { modelSet[u[modelDim] || '(none)'] = true; });
    var models = Object.keys(modelSet).sort();

    var counts = {};  // 'model||xval' → {sum, n}
    units.forEach(function(u) {
      var m = u[modelDim] || '(none)';
      var x = _getAggValue(u, aggDim);
      var k = m + '||' + x;
      if (!counts[k]) counts[k] = {sum:0, n:0};
      counts[k].sum += u.score_norm;
      counts[k].n++;
    });

    var palette = [
      '#3b82f6','#22c55e','#f59e0b','#ef4444','#8b5cf6',
      '#06b6d4','#ec4899','#84cc16','#f97316','#14b8a6',
      '#6366f1','#a3e635','#fb923c','#38bdf8','#e879f9',
    ];
    var traces = models.map(function(m, mi) {
      var y = xVals.map(function(x) {
        var c = counts[m + '||' + x];
        return (c && c.n > 0) ? +(c.sum / c.n).toFixed(3) : 0;
      });
      var hover = xVals.map(function(x) {
        var c = counts[m + '||' + x] || {sum:0, n:0};
        var tip = _tipText(x);
        return '<b>' + escHtml(x) + '</b>'
          + (tip ? '<br><i style="font-size:.85em">' + escHtml(tip.substring(0,80)) + '</i>' : '')
          + '<br>Model: ' + escHtml(m)
          + '<br>Mean: ' + (c.n > 0 ? (c.sum/c.n).toFixed(3) : 'N/A')
          + '  (n=' + c.n + ')';
      });
      return {
        name: m, type: 'bar', x: xVals, y: y,
        text: hover, hovertemplate: '%{text}<extra></extra>',
        marker: { color: palette[mi % palette.length] },
      };
    });

    var hPx = Math.max(300, xVals.length * (models.length * 14 + 16) + 120);
    hPx = Math.min(hPx, 600);

    Plotly.newPlot(divId, traces, {
      barmode: 'group',
      xaxis: { title: _dimLabel(aggDim), tickangle: xVals.length > 5 ? -35 : 0, automargin: true },
      yaxis: { title: 'Mean score (Low=0, Med=0.5, High=1)', range: [0, 1.08], rangemode: 'tozero', gridcolor: '#f1f5f9' },
      legend: { orientation: 'h', y: -0.28, x: 0.5, xanchor: 'center', font: {size:11} },
      margin: { t: 20, b: 130, l: 60, r: 20 },
      height: hPx,
      paper_bgcolor: '#fff', plot_bgcolor: '#f8fafc',
    }, { responsive: true });
  }

  _addPlotTooltips(divId);
}

// -----------------------------------------------------------------------
// Per-chart render functions
// -----------------------------------------------------------------------
function renderStudent() {
  var agg  = (document.getElementById('s1-agg')  || {}).value || 'aspect';
  var view = (document.getElementById('s1-view') || {}).value || 'stacked';
  _renderDistChart('student', agg, view, 'student-dist-chart');
}

function renderTeacher() {
  var agg  = (document.getElementById('s2-agg')  || {}).value || 'aspect';
  var view = (document.getElementById('s2-view') || {}).value || 'stacked';
  _renderDistChart('teacher', agg, view, 'teacher-dist-chart');
}

function renderJudge() {
  var agg  = (document.getElementById('s3-agg')  || {}).value || 'aspect';
  var view = (document.getElementById('s3-view') || {}).value || 'average';
  _renderDistChart('judge', agg, view, 'judge-dist-chart');
}

// -----------------------------------------------------------------------
// Entry point
// -----------------------------------------------------------------------
function renderAll() {
  _populateAgg('s1-agg', 'student');
  _populateAgg('s2-agg', 'teacher');
  _populateAgg('s3-agg', 'judge');
  renderStudent();
  renderTeacher();
  renderJudge();
}

document.addEventListener('DOMContentLoaded', renderAll);
"""
