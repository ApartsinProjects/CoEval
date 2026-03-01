"""Coverage Summary Report — REQ-A-7.9.

Three interactive stacked-bar figures:
  1. Teacher Coverage  — datapoints generated per teacher, stacked by dimension
  2. Student Coverage  — responses collected per student, stacked by dimension
  3. Judge Coverage    — valid evaluations per judge, stacked by dimension
                         (includes 'teacher' as an extra stacking option)

Stacking dimension is user-selectable via a dropdown; choices include 'task',
every target-attribute key, every nuanced-attribute key, and (for judges) 'teacher'.
"""
from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Any

from ..loader import EESDataModel
from .html_base import build_report, collect_tooltip_data, get_plotly_js, make_experiment_meta


# ---------------------------------------------------------------------------
# Python-side data builder
# ---------------------------------------------------------------------------

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

    return build_report(
        out_dir=out_dir,
        title=f'Coverage Summary — {exp_meta["id"]}',
        data=data,
        views_html=views_html,
        filter_defs=[],
        stats_text=exp_meta['stats'],
        experiment_meta=exp_meta,
        report_type='Coverage Summary',
        extra_js=_APP_JS,
        partial=model.is_partial,
    )


def _build_data(model: EESDataModel) -> dict:
    # ------------------------------------------------------------------ #
    # Collect attribute dimensions (from datapoints)                       #
    # ------------------------------------------------------------------ #
    # All target-attribute keys seen across all tasks
    target_attr_keys: list[str] = []
    nuanced_attr_keys: list[str] = []
    for task_id, attrs in model.target_attrs_by_task.items():
        for k in attrs:
            if k not in target_attr_keys:
                target_attr_keys.append(k)

    # Nuanced attrs – discover from datapoints
    nuanced_seen: set[str] = set()
    for dp in model.datapoints.values():
        for k in dp.get('sampled_nuanced_attributes', {}).keys():
            nuanced_seen.add(k)
    nuanced_attr_keys = sorted(nuanced_seen)

    # ------------------------------------------------------------------ #
    # Helper: build stacked data for a model list + item iterator          #
    # ------------------------------------------------------------------ #
    def _build_stacks(
        model_ids: list[str],
        items: list[dict],
        model_key: str,
        extra_dims: list[str] | None = None,
    ) -> tuple[dict[str, dict[str, dict[str, int]]], list[str], dict[str, str]]:
        """
        Returns:
          data[dim][model_id][value] = count
          dim_order: sorted list of dimension names
          dim_labels: {dim: human label}
        """
        dims = ['task'] + target_attr_keys + nuanced_attr_keys + (extra_dims or [])
        data: dict[str, dict[str, dict[str, int]]] = {}
        for dim in dims:
            data[dim] = {m: defaultdict(int) for m in model_ids}

        for item in items:
            mid = item.get(model_key, '')
            if mid not in data['task']:
                continue
            task = item.get('task_id', '')
            data['task'][mid][task] += 1
            attrs = item.get('sampled_target_attributes', {}) or {}
            for k in target_attr_keys:
                val = str(attrs.get(k, '(none)')) if k in attrs else '(none)'
                data[k][mid][val] += 1
            nuanced = item.get('sampled_nuanced_attributes', {}) or {}
            for k in nuanced_attr_keys:
                val = str(nuanced.get(k, '(none)')) if k in nuanced else '(none)'
                data[k][mid][val] += 1
            if extra_dims:
                for edim in extra_dims:
                    val = str(item.get(edim, '(none)'))
                    data[edim][mid][val] += 1

        dim_labels: dict[str, str] = {'task': 'Task', 'teacher': 'Teacher Model'}
        for k in target_attr_keys:
            dim_labels[k] = k.replace('_', ' ').title() + ' (target attr)'
        for k in nuanced_attr_keys:
            dim_labels[k] = k.replace('_', ' ').title() + ' (nuance attr)'

        # Convert defaultdicts to plain dicts for JSON serialisation
        serialisable: dict[str, dict[str, dict[str, int]]] = {}
        for dim in dims:
            serialisable[dim] = {
                mid: dict(data[dim][mid]) for mid in model_ids
            }

        return serialisable, dims, dim_labels

    # ------------------------------------------------------------------ #
    # Teacher coverage: count datapoints                                   #
    # ------------------------------------------------------------------ #
    teacher_items = list(model.datapoints.values())
    teacher_stacks, teacher_dims, dim_labels = _build_stacks(
        model.teachers, teacher_items, model_key='teacher_model_id'
    )

    # ------------------------------------------------------------------ #
    # Student coverage: join responses → datapoints for target attrs       #
    # ------------------------------------------------------------------ #
    student_items: list[dict[str, Any]] = []
    for resp in model.responses.values():
        dp = model.datapoints.get(resp.get('datapoint_id', ''), {})
        student_items.append({
            'student_model_id': resp.get('student_model_id', ''),
            'task_id': resp.get('task_id', ''),
            'sampled_target_attributes': dp.get('sampled_target_attributes', {}),
            'sampled_nuanced_attributes': dp.get('sampled_nuanced_attributes', {}),
        })
    student_stacks, student_dims, _ = _build_stacks(
        model.students, student_items, model_key='student_model_id'
    )

    # ------------------------------------------------------------------ #
    # Judge coverage: valid evaluations, joined → datapoints for attrs     #
    # ------------------------------------------------------------------ #
    judge_items: list[dict[str, Any]] = []
    for r in model.eval_records:
        if not r.valid:
            continue
        dp = model.datapoints.get(r.datapoint_id, {})
        judge_items.append({
            'judge_model_id': r.judge_model_id,
            'task_id': r.task_id,
            'teacher': r.teacher_model_id,
            'sampled_target_attributes': dp.get('sampled_target_attributes', {}),
            'sampled_nuanced_attributes': dp.get('sampled_nuanced_attributes', {}),
        })
    judge_stacks, judge_dims, _ = _build_stacks(
        model.judges, judge_items, model_key='judge_model_id',
        extra_dims=['teacher'],
    )

    # ------------------------------------------------------------------ #
    # Meta panel                                                           #
    # ------------------------------------------------------------------ #
    phases_completed = model.meta.get('phases_completed', [])
    phases_in_progress = model.meta.get('phases_in_progress', [])
    total_evals = model.total_records
    valid_evals = model.valid_records
    meta_panel = {
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
        'total_evals': total_evals,
        'valid_evals': valid_evals,
    }

    tips = collect_tooltip_data(model)

    return {
        'teachers': model.teachers,
        'students': model.students,
        'judges': model.judges,
        'teacher_stacks': teacher_stacks,
        'student_stacks': student_stacks,
        'judge_stacks': judge_stacks,
        'teacher_dims': teacher_dims,
        'student_dims': student_dims,
        'judge_dims': judge_dims,
        'dim_labels': dim_labels,
        'meta_panel': meta_panel,
        'tips': tips,
    }


# ---------------------------------------------------------------------------
# HTML panels
# ---------------------------------------------------------------------------

def _build_views_html() -> str:
    return """
<style>
/* ---- Coverage Summary ---- */
.stat-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(140px, 1fr));
  gap: 12px;
  margin-bottom: 16px;
}
.stat-card {
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  border-radius: 10px;
  padding: 13px 14px;
  text-align: center;
}
.stat-card .stat-val { font-size: 1.9rem; font-weight: 700; color: #1e3a5f; line-height: 1; }
.stat-card .stat-lbl { font-size: 0.71rem; color: #64748b; margin-top: 4px; text-transform: uppercase; letter-spacing:.04em; }
.stat-card.good .stat-val { color: #16a34a; }
.stat-card.warn .stat-val { color: #d97706; }
.stat-card.bad  .stat-val { color: #dc2626; }

.phase-timeline { display:flex; flex-wrap:wrap; gap:7px; margin-top:10px; }
.phase-badge {
  display:inline-flex; align-items:center; gap:4px;
  padding:3px 11px; border-radius:20px; font-size:.72rem; font-weight:600; border:1px solid;
}
.phase-badge.done    { background:#dcfce7; color:#15803d; border-color:#86efac; }
.phase-badge.running { background:#fef3c7; color:#b45309; border-color:#fcd34d; }
.phase-badge.pending { background:#f1f5f9; color:#64748b; border-color:#cbd5e1; }
.phase-badge .ph-dot { width:7px; height:7px; border-radius:50%; background:currentColor; }

.fig-controls {
  display:flex; align-items:center; gap:12px; flex-wrap:wrap;
  padding:9px 13px; background:#f8fafc; border:1px solid #e2e8f0;
  border-radius:8px; margin-bottom:10px;
}
.fig-controls label { font-size:.77rem; font-weight:600; color:#475569; }
.fig-controls select {
  border:1px solid #cbd5e1; border-radius:5px; padding:4px 8px;
  font-size:.77rem; background:#fff; cursor:pointer;
}
.fig-controls .fc-tip { font-size:.71rem; color:#94a3b8; margin-left:auto; }
</style>

<!-- ====================================================== -->
<!-- Overview                                               -->
<!-- ====================================================== -->
<div class="view-section" id="view-meta">
  <h2>Experiment Overview</h2>
  <div id="stat-grid-container"></div>
  <div id="phase-timeline-container"></div>
  <details class="fig-explain">
    <summary>About this panel</summary>
    <div class="explain-body">
      <b>Stat cards</b> summarise the experiment at a glance: tasks, teacher/student/judge counts,
      generated datapoints, and overall valid-evaluation coverage.<br>
      <b>Coverage&nbsp;%</b> = valid evaluations ÷ total evaluations. ≥&nbsp;100&nbsp;% is green;
      ≥&nbsp;90&nbsp;% amber; below 80&nbsp;% red.<br>
      <b>Phase timeline</b> shows pipeline phase status.
    </div>
  </details>
</div>

<!-- ====================================================== -->
<!-- Figure 1 — Teacher Coverage                            -->
<!-- ====================================================== -->
<div class="view-section" id="view-teacher">
  <h2>Teacher Coverage</h2>
  <div class="fig-controls">
    <label for="teacher-stack-sel">Stack by:</label>
    <select id="teacher-stack-sel" onchange="renderTeacherCoverage()"></select>
    <span class="fc-tip">Bars show datapoints generated; hover for counts.</span>
  </div>
  <div id="teacher-coverage-chart" class="chart-container"></div>
  <details class="fig-explain">
    <summary>About this figure</summary>
    <div class="explain-body">
      <b>What it shows:</b> Total datapoints generated by each teacher model
      (Phase&nbsp;3), broken down by the selected stacking dimension.<br>
      <b>Stacking options:</b>
      <b>Task</b>&nbsp;— coloured by which task each datapoint belongs to;
      <b>Target attribute</b>&nbsp;— coloured by sampled attribute value (e.g. difficulty);
      <b>Nuance attribute</b>&nbsp;— coloured by nuance sampling value.<br>
      <b>How to read it:</b> A balanced stack indicates the teacher generated a
      representative sample across all attribute values. A lopsided stack suggests
      the teacher model was biased toward certain tasks or attribute combinations.
    </div>
  </details>
</div>

<!-- ====================================================== -->
<!-- Figure 2 — Student Coverage                            -->
<!-- ====================================================== -->
<div class="view-section" id="view-student">
  <h2>Student Coverage</h2>
  <div class="fig-controls">
    <label for="student-stack-sel">Stack by:</label>
    <select id="student-stack-sel" onchange="renderStudentCoverage()"></select>
    <span class="fc-tip">Bars show responses collected; hover for counts.</span>
  </div>
  <div id="student-coverage-chart" class="chart-container"></div>
  <details class="fig-explain">
    <summary>About this figure</summary>
    <div class="explain-body">
      <b>What it shows:</b> Total responses collected from each student model
      (Phase&nbsp;4), broken down by the selected stacking dimension.<br>
      <b>How to read it:</b> All student bars should be roughly equal in height — large
      differences indicate that a student model failed on certain tasks or attribute
      combinations and produced fewer responses than expected.
    </div>
  </details>
</div>

<!-- ====================================================== -->
<!-- Figure 3 — Judge Coverage                              -->
<!-- ====================================================== -->
<div class="view-section" id="view-judge">
  <h2>Judge Coverage</h2>
  <div class="fig-controls">
    <label for="judge-stack-sel">Stack by:</label>
    <select id="judge-stack-sel" onchange="renderJudgeCoverage()"></select>
    <span class="fc-tip">Bars show valid evaluations; hover for counts.</span>
  </div>
  <div id="judge-coverage-chart" class="chart-container"></div>
  <details class="fig-explain">
    <summary>About this figure</summary>
    <div class="explain-body">
      <b>What it shows:</b> Total <em>valid</em> evaluations produced by each judge model
      (Phase&nbsp;5), broken down by the selected stacking dimension.<br>
      <b>Teacher stacking</b>&nbsp;— reveals whether a judge evaluated all teacher
      models equally, or concentrated effort on certain teacher-student pairs.<br>
      <b>Task stacking</b>&nbsp;— shows whether evaluation load is balanced across tasks.<br>
      <b>How to read it:</b> A very short bar for a judge means it produced few valid
      evaluations, which may degrade ensemble reliability for that task or teacher.
    </div>
  </details>
</div>
"""


# ---------------------------------------------------------------------------
# JavaScript
# ---------------------------------------------------------------------------

_APP_JS = r"""
// -----------------------------------------------------------------------
// Shared colour palette (20 distinguishable colours, cycles if >20 stacks)
// -----------------------------------------------------------------------
var _PALETTE = [
  '#3b82f6','#22c55e','#f59e0b','#ef4444','#8b5cf6',
  '#06b6d4','#ec4899','#84cc16','#f97316','#14b8a6',
  '#6366f1','#a3e635','#fb923c','#38bdf8','#e879f9',
  '#4ade80','#fbbf24','#f43f5e','#34d399','#818cf8',
];
function _colour(i) { return _PALETTE[i % _PALETTE.length]; }

// -----------------------------------------------------------------------
// Tooltip helpers (data-tip CSS is in html_base)
// -----------------------------------------------------------------------
function tipFor(key) {
  var tips = (DATA.tips || {});
  var task_tips = (tips.tasks || {});
  var attr_tips = (tips.attrs || {});
  return task_tips[key] || attr_tips[key] || '';
}

// -----------------------------------------------------------------------
// Build a Plotly stacked-bar chart
// params:
//   divId  : DOM id to render into
//   models : array of model names (x-axis)
//   stacks : DATA.teacher_stacks[dim] etc  → {model: {value: count}}
//   dim    : selected dimension string
//   yLabel : label for y-axis
// -----------------------------------------------------------------------
function _renderStackedBar(divId, models, stacks, dim, yLabel) {
  if (!models || models.length === 0) {
    document.getElementById(divId).innerHTML =
      '<p style="color:#94a3b8;padding:20px">No data available.</p>';
    return;
  }

  var dimData = stacks[dim] || {};

  // Collect all unique values for this dimension across all models
  var valueSet = {};
  models.forEach(function(m) {
    var mData = dimData[m] || {};
    Object.keys(mData).forEach(function(v) { valueSet[v] = true; });
  });
  var values = Object.keys(valueSet).sort();

  if (values.length === 0) {
    document.getElementById(divId).innerHTML =
      '<p style="color:#94a3b8;padding:20px">No stacking data for this dimension.</p>';
    return;
  }

  // One trace per unique value
  var traces = values.map(function(val, i) {
    var y = models.map(function(m) {
      return (dimData[m] || {})[val] || 0;
    });
    var tipText = tipFor(val) || tipFor(dim);
    var traceName = val === '(none)' ? '(unset)' : val;
    return {
      type: 'bar',
      name: traceName,
      x: models,
      y: y,
      marker: { color: _colour(i) },
      hovertemplate: '<b>' + escHtml(traceName) + '</b><br>Model: %{x}<br>Count: %{y}'
        + (tipText ? '<br><i>' + escHtml(tipText.substring(0,80)) + '…</i>' : '')
        + '<extra></extra>',
    };
  });

  // Dynamic height: taller when there are many models
  var heightPx = Math.max(340, models.length * 36 + 140);

  Plotly.newPlot(divId, traces, {
    barmode: 'stack',
    xaxis: {
      title: 'Model',
      tickangle: models.length > 5 ? -35 : 0,
      automargin: true,
    },
    yaxis: { title: yLabel, rangemode: 'tozero' },
    legend: {
      orientation: values.length > 8 ? 'v' : 'h',
      y: values.length > 8 ? 0.5 : -0.28,
      x: values.length > 8 ? 1.02 : 0.5,
      xanchor: values.length > 8 ? 'left' : 'center',
      font: { size: 11 },
    },
    margin: { t: 20, b: values.length > 8 ? 80 : 120, l: 60, r: values.length > 8 ? 180 : 40 },
    height: heightPx,
    paper_bgcolor: '#fff',
    plot_bgcolor: '#f8fafc',
  }, { responsive: true });
}

// -----------------------------------------------------------------------
// Populate a stacking-dimension dropdown
// -----------------------------------------------------------------------
function _populateDimSelect(selectId, dims) {
  var sel = document.getElementById(selectId);
  sel.innerHTML = '';
  dims.forEach(function(dim) {
    var lbl = (DATA.dim_labels || {})[dim] || dim.replace(/_/g, ' ');
    var opt = document.createElement('option');
    opt.value = dim;
    opt.textContent = lbl;
    sel.appendChild(opt);
  });
}

// -----------------------------------------------------------------------
// Render functions
// -----------------------------------------------------------------------
function renderTeacherCoverage() {
  var dim = document.getElementById('teacher-stack-sel').value || 'task';
  _renderStackedBar(
    'teacher-coverage-chart',
    DATA.teachers,
    DATA.teacher_stacks,
    dim,
    'Datapoints generated'
  );
}

function renderStudentCoverage() {
  var dim = document.getElementById('student-stack-sel').value || 'task';
  _renderStackedBar(
    'student-coverage-chart',
    DATA.students,
    DATA.student_stacks,
    dim,
    'Responses collected'
  );
}

function renderJudgeCoverage() {
  var dim = document.getElementById('judge-stack-sel').value || 'task';
  _renderStackedBar(
    'judge-coverage-chart',
    DATA.judges,
    DATA.judge_stacks,
    dim,
    'Valid evaluations'
  );
}

// -----------------------------------------------------------------------
// Overview: stat cards + phase timeline
// -----------------------------------------------------------------------
function renderMeta() {
  var m = DATA.meta_panel;
  var validPct = m.total_evals > 0
    ? Math.round(m.valid_evals / m.total_evals * 100) : 100;
  var statClass = validPct === 100 ? 'good' : (validPct >= 90 ? 'warn' : 'bad');

  var stats = [
    { val: m.tasks,        lbl: 'Tasks',       cls: '' },
    { val: m.teachers,     lbl: 'Teachers',    cls: '' },
    { val: m.students,     lbl: 'Students',    cls: '' },
    { val: m.judges,       lbl: 'Judges',      cls: '' },
    { val: m.datapoints,   lbl: 'Datapoints',  cls: '' },
    { val: m.total_evals,  lbl: 'Total Evals', cls: '' },
    { val: m.valid_evals,  lbl: 'Valid Evals', cls: statClass },
    { val: validPct + '%', lbl: 'Coverage',    cls: statClass },
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

  var allPhases = [
    'attribute_mapping','rubric_mapping','data_generation',
    'response_collection','evaluation'
  ];
  var phaseLabels = {
    attribute_mapping:   'Attr Mapping',
    rubric_mapping:      'Rubric Mapping',
    data_generation:     'Data Gen',
    response_collection: 'Resp Collection',
    evaluation:          'Evaluation'
  };
  var completed  = new Set(m.phases_completed  || []);
  var inProgress = new Set(m.phases_in_progress || []);

  var tlHtml = '<div class="phase-timeline">';
  allPhases.forEach(function(ph) {
    var cls  = completed.has(ph) ? 'done' : (inProgress.has(ph) ? 'running' : 'pending');
    var icon = completed.has(ph) ? '✓'    : (inProgress.has(ph) ? '…'       : '○');
    tlHtml += '<span class="phase-badge ' + cls + '">'
            + '<span class="ph-dot"></span>'
            + icon + ' ' + (phaseLabels[ph] || ph)
            + '</span>';
  });
  tlHtml += '</div>';
  document.getElementById('phase-timeline-container').innerHTML = tlHtml;
}

// -----------------------------------------------------------------------
// HTML-escape helper
// -----------------------------------------------------------------------
function escHtml(s) {
  return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;')
         .replace(/"/g,'&quot;');
}

// -----------------------------------------------------------------------
// Main entry
// -----------------------------------------------------------------------
function renderAll() {
  renderMeta();

  _populateDimSelect('teacher-stack-sel', DATA.teacher_dims || ['task']);
  _populateDimSelect('student-stack-sel', DATA.student_dims || ['task']);
  _populateDimSelect('judge-stack-sel',   DATA.judge_dims   || ['task']);

  renderTeacherCoverage();
  renderStudentCoverage();
  renderJudgeCoverage();
}

document.addEventListener('DOMContentLoaded', renderAll);
"""
