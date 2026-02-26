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
<div class="view-section" id="view-meta">
  <h2>View 4 — Experiment Meta</h2>
  <div id="meta-panel"></div>
</div>

<div class="view-section" id="view-coverage">
  <h2>View 1 — Coverage Matrix</h2>
  <div id="coverage-table-container"></div>
</div>

<div class="view-section" id="view-waterfall">
  <h2>View 2 — Phase Coverage Waterfall</h2>
  <div id="waterfall-chart" class="chart-container"></div>
</div>

<div class="view-section" id="view-errors">
  <h2>View 3 — Error Code Breakdown</h2>
  <div id="error-chart" class="chart-container"></div>
</div>
"""


_APP_JS = """
function renderAll() {
  renderMeta();
  renderCoverageTable();
  renderWaterfall();
  renderErrors();
}

function renderMeta() {
  var m = DATA.meta_panel;
  var html = '<table class="data-table"><tbody>';
  html += '<tr><th>Experiment ID</th><td>' + m.experiment_id + '</td></tr>';
  html += '<tr><th>Status</th><td>' + m.status + '</td></tr>';
  html += '<tr><th>Created</th><td>' + m.created_at + '</td></tr>';
  html += '<tr><th>Updated</th><td>' + m.updated_at + '</td></tr>';
  html += '<tr><th>Phases Completed</th><td>' + (m.phases_completed || []).join(', ') + '</td></tr>';
  html += '<tr><th>Phases In Progress</th><td>' + (m.phases_in_progress || []).join(', ') + '</td></tr>';
  html += '<tr><th>Tasks</th><td>' + m.tasks + '</td></tr>';
  html += '<tr><th>Models (T/S/J)</th><td>' + m.teachers + ' / ' + m.students + ' / ' + m.judges + '</td></tr>';
  html += '<tr><th>Datapoints</th><td>' + m.datapoints + '</td></tr>';
  html += '<tr><th>Total Eval Records</th><td>' + m.total_evals + '</td></tr>';
  html += '<tr><th>Valid Eval Records</th><td>' + m.valid_evals + '</td></tr>';
  html += '</tbody></table>';
  document.getElementById('meta-panel').innerHTML = html;
}

function renderCoverageTable() {
  var taskFilter = getFilter('task');
  var rows = DATA.coverage_rows.filter(function(r) {
    return taskFilter === '__all__' || r.task === taskFilter;
  });
  var html = '<table class="data-table">';
  html += '<tr><th>Task</th><th>Teacher</th><th>Student</th><th>Judge</th>';
  html += '<th>Expected</th><th>Actual</th><th>Valid</th><th>Invalid</th>';
  html += '<th>Coverage%</th><th>Errors</th></tr>';
  rows.forEach(function(r) {
    var rowStyle = r.valid === 0 ? 'background:#ffe0e0' : (r.coverage_pct < 100 ? 'background:#fff3cd' : '');
    html += '<tr style="' + rowStyle + '">';
    html += '<td>' + r.task + '</td><td>' + r.teacher + '</td>';
    html += '<td>' + r.student + '</td><td>' + r.judge + '</td>';
    html += '<td>' + r.expected + '</td><td>' + r.actual + '</td>';
    html += '<td>' + r.valid + '</td><td>' + r.invalid + '</td>';
    html += '<td>' + r.coverage_pct + '%</td>';
    html += '<td>' + (r.errors || '') + '</td></tr>';
  });
  html += '</table>';
  document.getElementById('coverage-table-container').innerHTML = html;
}

function renderWaterfall() {
  var wf = DATA.waterfall;
  if (!wf || wf.length === 0) return;
  var tasks = wf.map(function(w) { return w.task; });
  var traces = [
    {name: 'Datapoints (P3)', y: wf.map(function(w){return w.datapoints;}), x: tasks,
     type: 'bar', marker: {color: '#4a90d9'}},
    {name: 'Responses (P4)', y: wf.map(function(w){return w.responses;}), x: tasks,
     type: 'bar', marker: {color: '#7bc67e'}},
    {name: 'Evals Actual (P5)', y: wf.map(function(w){return w.eval_actual;}), x: tasks,
     type: 'bar', marker: {color: '#f0a500'}},
    {name: 'Valid Evals', y: wf.map(function(w){return w.eval_valid;}), x: tasks,
     type: 'bar', marker: {color: '#27ae60'}},
  ];
  Plotly.newPlot('waterfall-chart', traces,
    {title: 'Artifact counts by phase', barmode: 'group',
     xaxis: {title: 'Task'}, yaxis: {title: 'Count'},
     margin: {t: 40}});
}

function renderErrors() {
  var et = DATA.error_totals;
  var keys = Object.keys(et);
  if (keys.length === 0) {
    document.getElementById('error-chart').innerHTML = '<p style="color:#27ae60;padding:16px">No errors found in evaluation records.</p>';
    return;
  }
  var vals = keys.map(function(k) { return et[k]; });
  Plotly.newPlot('error-chart',
    [{type: 'bar', x: keys, y: vals, marker: {color: '#e74c3c'}}],
    {title: 'Error codes', xaxis: {title: 'Error code'}, yaxis: {title: 'Count'},
     margin: {t: 40}});
}

document.addEventListener('DOMContentLoaded', renderAll);
"""
