"""Student Model Score Report — REQ-A-7.6."""
from __future__ import annotations

from collections import defaultdict
from pathlib import Path

from ..loader import EESDataModel
from ..metrics import compute_student_scores
from .html_base import build_report, collect_tooltip_data, get_plotly_js, make_experiment_meta


def write_student_report(
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
        {'id': 'task', 'label': 'Task', 'options': [(t, t) for t in model.tasks]},
        {'id': 'teacher', 'label': 'Teacher', 'options': [(t, t) for t in model.teachers]},
        {'id': 'judge', 'label': 'Judge', 'options': [(j, j) for j in model.judges]},
    ]

    return build_report(
        out_dir=out_dir,
        title=f'Student Report — {exp_meta["id"]}',
        data=data,
        views_html=_VIEWS_HTML,
        filter_defs=filter_defs,
        stats_text=exp_meta['stats'],
        experiment_meta=exp_meta,
        report_type='Student Model Score Report',
        extra_js=_APP_JS,
        partial=model.is_partial,
    )


def _build_data(model: EESDataModel) -> dict:
    units = model.units
    students = model.students

    # Discover target attribute keys
    attr_keys: list[str] = []
    for _tid, attrs in model.target_attrs_by_task.items():
        for k in attrs:
            if k not in attr_keys:
                attr_keys.append(k)

    scores_map = compute_student_scores(units, students, model.datapoints)

    ranking_rows = []
    for s in students:
        sr = scores_map.get(s)
        is_teacher_too = s in model.teachers
        is_judge_too = s in model.judges
        ranking_rows.append({
            'student': s,
            'overall': round(sr.overall, 4) if sr and sr.overall is not None else None,
            'by_task': {k: round(v, 4) for k, v in sr.by_task.items()} if sr else {},
            'valid_evals': sr.valid_evals if sr else 0,
            'is_also_teacher': is_teacher_too,
            'is_also_judge': is_judge_too,
        })

    all_aspects = sorted(set(u.rubric_aspect for u in units))

    # ---- Aspect heatmap: student × aspect ----
    asp_student_avg: dict = {}
    for s in students:
        for asp in all_aspects:
            vals = [u.score_norm for u in units
                    if u.student_model_id == s and u.rubric_aspect == asp]
            asp_student_avg[f'{s}||{asp}'] = round(sum(vals)/len(vals), 4) if vals else None

    # ---- Task heatmap: student × task ----
    task_student_avg: dict = {}
    for s in students:
        for task in model.tasks:
            vals = [u.score_norm for u in units
                    if u.student_model_id == s and u.task_id == task]
            task_student_avg[f'{s}||{task}'] = round(sum(vals)/len(vals), 4) if vals else None

    # ---- Attr heatmap: student × attr_key=val ----
    attr_student_avg: dict = {}  # attrKey → {student||val: score}
    for k in attr_keys:
        vals_for_key: set[str] = set()
        for u in units:
            dp = model.datapoints.get(u.datapoint_id, {})
            attrs = dp.get('sampled_target_attributes', {}) or {}
            if k in attrs:
                vals_for_key.add(str(attrs[k]))
        for s in students:
            for v in sorted(vals_for_key):
                scores = []
                for u in units:
                    if u.student_model_id != s:
                        continue
                    dp = model.datapoints.get(u.datapoint_id, {})
                    av = dp.get('sampled_target_attributes', {}) or {}
                    if str(av.get(k, '')) == v:
                        scores.append(u.score_norm)
                attr_student_avg.setdefault(k, {})[f'{s}||{v}'] = (
                    round(sum(scores)/len(scores), 4) if scores else None
                )

    # Available heatmap X-axis dimensions
    dim_options = [{'value': 'aspect', 'label': 'Rubric Aspect'}]
    dim_options.append({'value': 'task', 'label': 'Task'})
    for k in attr_keys:
        dim_options.append({'value': 'attr:' + k, 'label': k.replace('_', ' ').title() + ' (attr)'})

    # Per-judge score comparison: (student, judge) → avg
    student_judge_avg: dict = {}
    for s in students:
        for j in model.judges:
            vals = [u.score_norm for u in units
                    if u.student_model_id == s and u.judge_model_id == j]
            if vals:
                student_judge_avg[f'{s}||{j}'] = round(sum(vals)/len(vals), 4)

    all_units_compact = [
        {
            'task': u.task_id, 'teacher': u.teacher_model_id,
            'student': u.student_model_id, 'judge': u.judge_model_id,
            'aspect': u.rubric_aspect, 'score_norm': u.score_norm,
            'sj': u.is_self_judging, 'st': u.is_self_teaching,
        }
        for u in units
    ]

    return {
        'students': students,
        'judges': model.judges,
        'aspects': all_aspects,
        'tasks': model.tasks,
        'attr_keys': attr_keys,
        'dim_options': dim_options,
        'ranking': ranking_rows,
        'asp_student': asp_student_avg,
        'task_student': task_student_avg,
        'attr_student': attr_student_avg,
        'student_judge': student_judge_avg,
        'all_units': all_units_compact,
        'tips': collect_tooltip_data(model),
    }


_VIEWS_HTML = """
<style>
.dim-controls {
  display:flex; align-items:center; gap:12px; flex-wrap:wrap;
  padding:8px 12px; background:#f8fafc; border:1px solid #e2e8f0;
  border-radius:8px; margin-bottom:10px;
}
.dim-controls label { font-size:.77rem; font-weight:600; color:#475569; }
.dim-controls select {
  border:1px solid #cbd5e1; border-radius:5px; padding:4px 8px;
  font-size:.77rem; background:#fff; cursor:pointer;
}
</style>
<div class="view-section">
  <h2>View 1 — Student Ranking</h2>
  <button class="csv-export-btn" onclick="_csvExportTable('v1-table','student_ranking.csv')">⬇ CSV</button>
  <div id="v1-table"></div>
  <details class="fig-explain">
    <summary>About this table</summary>
    <div class="explain-body">
      <b>What it shows:</b> Each row is a student model. Columns report the mean normalised
      score (0 = all Low, 1 = all High) for each task, plus an overall average
      and the raw evaluation counts.<br>
      <b>How to read it:</b> Higher scores indicate better performance. Use the Task,
      Teacher, and Judge filters to narrow the comparison to a specific experimental
      configuration. <b>⚠SJ</b> = self-judging; <b>⚠ST</b> = self-teaching — both
      flags suggest the score may be inflated.<br>
      <b>Click any column header</b> to sort.
    </div>
  </details>
</div>
<div class="view-section">
  <h2>View 2 — Heatmap (Student × Dimension)</h2>
  <div class="dim-controls">
    <label for="v2-dim-sel">X axis:</label>
    <select id="v2-dim-sel" onchange="renderV2()"></select>
    <div class="fc-popup-wrap" style="margin-left:4px;">
      <button class="fc-popup-btn" id="v2-filter-btn"
        onclick="_toggleFilterPopup('v2hm'); return false;">⊟ Filter ▾</button>
      <div class="fc-popup" id="v2hm-filter-popup">
        <div class="fc-popup-title">Show columns</div>
        <div class="fc-popup-checks" id="v2hm-filter-checks"></div>
        <div class="fc-popup-actions">
          <button class="fc-popup-clear" onclick="_clearFilter('v2hm', renderV2)">All</button>
          <button class="fc-popup-apply" onclick="_applyFilter('v2hm', renderV2)">Apply</button>
        </div>
      </div>
    </div>
  </div>
  <div id="v2-chart" class="chart-container"></div>
  <details class="fig-explain">
    <summary>About this figure</summary>
    <div class="explain-body">
      <b>What it shows:</b> A heatmap where rows = student models and columns = values of
      the selected dimension (rubric aspect, task, or target attribute).<br>
      Cell colour = mean normalised score (green = high, red = low).<br>
      <b>Colour scale</b> adapts dynamically to the actual data range for maximum contrast.<br>
      <b>How to read it:</b> A row that is uniformly green indicates a strong student model.
      A column that is uniformly red suggests a criterion that is difficult for all students.<br>
      Use the <b>Filter</b> button to show only a subset of columns.
    </div>
  </details>
</div>
<div class="view-section">
  <h2>View 3 — Per-Judge Score Comparison</h2>
  <div id="v3-chart" class="chart-container"></div>
  <details class="fig-explain">
    <summary>About this figure</summary>
    <div class="explain-body">
      <b>What it shows:</b> Mean score per student model, shown separately for each judge
      model (grouped bars). This lets you detect whether student rankings are stable across
      judges or depend on which judge evaluated them.<br>
      <b>How to read it:</b> If bar heights are consistent across judge groups for a given
      student, the student's ranking is robust to judge choice. Large discrepancies between
      judge groups suggest judge calibration differences — check the Judge Report for
      inter-judge agreement scores.
    </div>
  </details>
</div>
"""

_APP_JS = """
// Tooltip helpers
function tipFor(text, type) {
  var def = (DATA.tips && DATA.tips[type] && DATA.tips[type][text]) ? DATA.tips[type][text] : null;
  if (!def) return escHtml(text);
  return '<span data-tip="' + escHtml(def) + '">' + escHtml(text) + '</span>';
}
function escHtml(s) {
  return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

function filteredUnits() {
  var tf = getFilter('task'), tef = getFilter('teacher'), jf = getFilter('judge');
  return DATA.all_units.filter(function(u) {
    return (tf === '__all__' || u.task === tf)
        && (tef === '__all__' || u.teacher === tef)
        && (jf === '__all__' || u.judge === jf);
  });
}

function renderAll() {
  // Populate V2 dim select
  var dimSel = document.getElementById('v2-dim-sel');
  if (dimSel && dimSel.children.length === 0) {
    (DATA.dim_options || [{value:'aspect',label:'Rubric Aspect'}]).forEach(function(opt) {
      var o = document.createElement('option');
      o.value = opt.value; o.textContent = opt.label;
      dimSel.appendChild(o);
    });
  }
  renderV1(); renderV2(); renderV3();
}

function renderV1() {
  var units = filteredUnits();
  var studentAvg = {};
  units.forEach(function(u) {
    if (!studentAvg[u.student]) studentAvg[u.student] = [];
    studentAvg[u.student].push(u.score_norm);
  });
  var rows = DATA.ranking.slice().sort(function(a,b){return (b.overall||0)-(a.overall||0);});
  var html = '<table class="data-table"><tr><th>Student</th><th>Overall Avg Score</th>';
  DATA.tasks.forEach(function(t){html += '<th>' + tipFor(t, 'tasks') + '</th>';});
  html += '<th>Valid Evals</th></tr>';
  rows.forEach(function(r) {
    var arr = studentAvg[r.student] || [];
    var avg = arr.length ? arr.reduce(function(a,b){return a+b;},0)/arr.length : null;
    var sj_flag = r.is_also_judge ? '<span class="warn-flag" title="This student also acts as judge — scores may be biased.">⚠SJ</span>' : '';
    var st_flag = r.is_also_teacher ? '<span class="warn-flag" title="Self-teaching included — this model generated the prompts it answered.">⚠ST</span>' : '';
    html += '<tr><td>' + escHtml(r.student) + sj_flag + st_flag + '</td>';
    html += '<td>' + fmt(avg) + '</td>';
    DATA.tasks.forEach(function(t) {
      var t_units = units.filter(function(u){return u.student===r.student && u.task===t;});
      var t_avg = t_units.length ? t_units.reduce(function(a,u){return a+u.score_norm;},0)/t_units.length : null;
      html += '<td>' + fmt(t_avg) + '</td>';
    });
    html += '<td>' + arr.length + '</td></tr>';
  });
  document.getElementById('v1-table').innerHTML = html + '</table>';
  _makeSortable('v1-table');
}

function renderV2() {
  var dimSel = document.getElementById('v2-dim-sel');
  var selectedDim = dimSel ? dimSel.value : 'aspect';
  var students = DATA.students;

  var xLabels, meanData, xTitle;
  if (selectedDim === 'aspect') {
    xTitle = 'Rubric Aspect';
    xLabels = DATA.aspects || [];
    meanData = DATA.asp_student || {};
  } else if (selectedDim === 'task') {
    xTitle = 'Task';
    xLabels = DATA.tasks || [];
    meanData = DATA.task_student || {};
  } else if (selectedDim.indexOf('attr:') === 0) {
    var attrKey = selectedDim.slice(5);
    xTitle = attrKey.replace(/_/g,' ');
    var attrData = (DATA.attr_student || {})[attrKey] || {};
    var valSet = {};
    Object.keys(attrData).forEach(function(k) {
      var v = k.split('||')[1];
      if (v) valSet[v] = true;
    });
    xLabels = Object.keys(valSet).sort();
    meanData = {};
    students.forEach(function(s) {
      xLabels.forEach(function(v) {
        meanData[s + '||' + v] = attrData[s + '||' + v];
      });
    });
  } else {
    return;
  }

  if (!students.length || !xLabels.length) return;

  // Sync filter popup
  _syncFilterPopup('v2hm', selectedDim, xLabels);
  var filteredX = _getFilteredVals('v2hm', selectedDim, xLabels);
  if (!filteredX.length) filteredX = xLabels;

  var z = students.map(function(s) {
    return filteredX.map(function(a) {
      var v = meanData[s + '||' + a];
      return (v !== undefined && v !== null) ? v : null;
    });
  });

  // Dynamic scale for contrast
  var flat = [].concat.apply([], z).filter(function(v){return v !== null;});
  var zmin = flat.length ? Math.max(0, Math.min.apply(null,flat) - 0.02) : 0;
  var zmax = flat.length ? Math.min(1, Math.max.apply(null,flat) + 0.02) : 1;

  Plotly.newPlot('v2-chart', [{
    type: 'heatmap', z: z, x: filteredX, y: students,
    colorscale: [
      [0, '#dc2626'], [0.25, '#f97316'], [0.5, '#fbbf24'],
      [0.75, '#86efac'], [1, '#16a34a']
    ],
    zmin: zmin, zmax: zmax, hoverongaps: false,
    colorbar: { title: 'Score', thickness: 14, len: 0.8 },
    hovertemplate: 'Student: %{y}<br>' + xTitle + ': %{x}<br>Mean score: %{z:.3f}<extra></extra>',
  }], {
    xaxis: { title: xTitle, tickangle: filteredX.length > 5 ? -35 : 0, automargin: true },
    yaxis: { autorange: 'reversed' },
    margin: { t: 24, b: 100, l: 100, r: 80 },
    paper_bgcolor: '#fff', plot_bgcolor: '#fafbfc',
  }, { responsive: true });
  _addPlotTooltips('v2-chart');
}

function renderV3() {
  var units = filteredUnits();
  var students = DATA.students;
  var judges = DATA.judges;
  if (!students.length || !judges.length) return;
  var sjMap = {};
  units.forEach(function(u) {
    var k = u.student + '||' + u.judge;
    if (!sjMap[k]) sjMap[k] = [];
    sjMap[k].push(u.score_norm);
  });
  var palette = [
    '#3b82f6','#22c55e','#f59e0b','#ef4444','#8b5cf6',
    '#06b6d4','#ec4899','#84cc16','#f97316','#14b8a6',
  ];
  var traces = judges.map(function(j, ji) {
    var col = palette[ji % palette.length];
    return {
      name: j, type: 'bar',
      x: students,
      y: students.map(function(s) {
        var arr = sjMap[s + '||' + j];
        return arr ? arr.reduce(function(a, b){return a + b;}, 0) / arr.length : 0;
      }),
      marker: { color: col, line: { color: 'rgba(0,0,0,.08)', width: 1 } },
      hovertemplate: 'Student: %{x}<br>Judge: ' + j + '<br>Avg score: %{y:.3f}<extra></extra>',
    };
  });
  Plotly.newPlot('v3-chart', traces, {
    barmode: 'group',
    yaxis: { title: 'Mean normalised score (0\u20131)', range: [0, 1.08], gridcolor: '#f1f5f9' },
    xaxis: { title: 'Student model', tickangle: students.length > 5 ? -35 : 0 },
    legend: { orientation: 'h', y: -0.3, x: 0.5, xanchor: 'center', font: { size: 11 } },
    margin: { t: 24, b: 110, l: 60, r: 20 },
    paper_bgcolor: '#fff', plot_bgcolor: '#fafbfc',
  }, { responsive: true });
  _addPlotTooltips('v3-chart');
}

document.addEventListener('DOMContentLoaded', renderAll);
"""
