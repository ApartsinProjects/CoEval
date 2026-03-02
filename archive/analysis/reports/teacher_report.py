"""Teacher Model Score Report — REQ-A-7.4."""
from __future__ import annotations

from collections import defaultdict
from pathlib import Path

from ..loader import EESDataModel
from ..metrics import compute_teacher_scores
from .html_base import build_report, collect_tooltip_data, get_plotly_js, make_experiment_meta

_SINGLE_STUDENT_NOTICE = (
    "⚠ Only 1 student model in this experiment. "
    "Teacher differentiation scores are trivially 0.0 and carry no information. "
    "Add ≥2 student models to obtain meaningful differentiation estimates."
)


def write_teacher_report(
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
        {'id': 'formula', 'label': 'Formula',
         'options': [('v1', 'V1: Variance'), ('s2', 'S2: Spread'), ('r3', 'R3: Range')]},
        {'id': 'task', 'label': 'Task', 'options': [(t, t) for t in model.tasks]},
        {'id': 'judge', 'label': 'Judge', 'options': [(j, j) for j in model.judges]},
    ]

    return build_report(
        out_dir=out_dir,
        title=f'Teacher Report — {exp_meta["id"]}',
        data=data,
        views_html=_VIEWS_HTML,
        filter_defs=filter_defs,
        stats_text=exp_meta['stats'],
        experiment_meta=exp_meta,
        report_type='Teacher Model Score Report',
        extra_js=_APP_JS,
        partial=model.is_partial,
    )


def _build_data(model: EESDataModel) -> dict:
    units = model.units
    teachers = model.teachers
    students = model.students
    single_student = len(students) <= 1

    # Discover target attribute keys
    attr_keys: list[str] = []
    for _tid, attrs in model.target_attrs_by_task.items():
        for k in attrs:
            if k not in attr_keys:
                attr_keys.append(k)

    teacher_scores_map = compute_teacher_scores(units, teachers, students)

    # Per-aspect scores per teacher (variance)
    asp_teacher_score: dict[str, dict] = {}
    for teacher in teachers:
        t_units = [u for u in units if u.teacher_model_id == teacher]
        by_asp_student: dict[tuple, list] = defaultdict(list)
        for u in t_units:
            by_asp_student[(u.rubric_aspect, u.student_model_id)].append(u.score_norm)
        asp_avgs = {}
        for (asp, _), vals in by_asp_student.items():
            asp_avgs.setdefault(asp, []).append(sum(vals) / len(vals))
        asp_teacher_score[teacher] = {}
        for asp, student_avgs in asp_avgs.items():
            if len(student_avgs) >= 2:
                mean = sum(student_avgs) / len(student_avgs)
                var = sum((x - mean)**2 for x in student_avgs) / (len(student_avgs) - 1)
                asp_teacher_score[teacher][asp] = round(var, 4)
            else:
                asp_teacher_score[teacher][asp] = 0.0

    # Mean student score per (teacher, aspect) — heatmap default dimension
    asp_teacher_mean: dict[str, dict[str, float]] = {}
    for teacher in teachers:
        t_units = [u for u in units if u.teacher_model_id == teacher]
        by_asp: dict[str, list] = defaultdict(list)
        for u in t_units:
            by_asp[u.rubric_aspect].append(u.score_norm)
        asp_teacher_mean[teacher] = {
            asp: round(sum(vals) / len(vals), 4)
            for asp, vals in by_asp.items()
        }

    # Mean student score per (teacher, task)
    task_teacher_mean: dict[str, dict[str, float]] = {}
    for teacher in teachers:
        t_units = [u for u in units if u.teacher_model_id == teacher]
        by_task: dict[str, list] = defaultdict(list)
        for u in t_units:
            by_task[u.task_id].append(u.score_norm)
        task_teacher_mean[teacher] = {
            task: round(sum(vals) / len(vals), 4)
            for task, vals in by_task.items()
        }

    # Mean student score per (teacher, attrKey=attrVal)
    attr_teacher_mean: dict[str, dict[str, float]] = {}  # teacher → {attrKey=val: score}
    for teacher in teachers:
        t_units = [u for u in units if u.teacher_model_id == teacher]
        by_attr: dict[str, list] = defaultdict(list)
        for u in t_units:
            dp = model.datapoints.get(u.datapoint_id, {})
            attrs = dp.get('sampled_target_attributes', {}) or {}
            for k, v in attrs.items():
                by_attr[f'{k}={v}'].append(u.score_norm)
        attr_teacher_mean[teacher] = {
            kv: round(sum(vals) / len(vals), 4)
            for kv, vals in by_attr.items()
        }

    # Available heatmap X-axis dimensions
    all_aspects = sorted(set(u.rubric_aspect for u in units))
    dim_options = [{'value': 'aspect', 'label': 'Rubric Aspect'}]
    dim_options.append({'value': 'task', 'label': 'Task'})
    for k in attr_keys:
        dim_options.append({'value': 'attr:' + k, 'label': k.replace('_', ' ').title() + ' (attr)'})

    # Ranking rows
    ranking_rows = []
    for teacher in teachers:
        ts = teacher_scores_map.get(teacher)
        dp_count = sum(1 for dp in model.datapoints.values()
                       if dp.get('teacher_model_id') == teacher)
        is_student_too = teacher in students
        ranking_rows.append({
            'teacher': teacher,
            'v1': round(ts.v1, 4) if ts else 0.0,
            's2': round(ts.s2, 4) if ts else 0.0,
            'r3': round(ts.r3, 4) if ts else 0.0,
            'datapoints': dp_count,
            'is_also_student': is_student_too,
        })

    return {
        'teachers': teachers,
        'students': students,
        'aspects': all_aspects,
        'tasks': model.tasks,
        'attr_keys': attr_keys,
        'dim_options': dim_options,
        'single_student': single_student,
        'single_student_notice': _SINGLE_STUDENT_NOTICE if single_student else '',
        'ranking': ranking_rows,
        'asp_scores': asp_teacher_score,
        'asp_mean': asp_teacher_mean,
        'task_mean': task_teacher_mean,
        'attr_mean': attr_teacher_mean,
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
<div id="degenerate-notice" class="degenerate-notice" style="display:none"></div>
<div class="view-section">
  <h2>View 1 — Teacher Ranking</h2>
  <button class="csv-export-btn" onclick="_csvExportTable('v1-table','teacher_ranking.csv')">⬇ CSV</button>
  <div id="v1-table"></div>
  <details class="fig-explain">
    <summary>About this table</summary>
    <div class="explain-body">
      <b>What it shows:</b> Each row is a teacher model. Columns include discrimination
      metrics (V1/S2/R3) measuring how well the teacher's items spread students apart,
      plus the count of generated datapoints.<br>
      <b>V1 (Variance)</b> — variance of per-student average scores. Higher = teacher items
      discriminate better between strong and weak students.<br>
      <b>S2 (Spread)</b> — mean absolute deviation of per-student averages. Robust alternative.<br>
      <b>R3 (Range)</b> — max minus min per-student average. Simple spread measure.<br>
      <b>⚠ST</b> flags self-teaching (teacher = student) — scores may be inflated.<br>
      <b>Click any column header</b> to sort the table.
    </div>
  </details>
</div>
<div class="view-section">
  <h2>View 2 — Teacher Score Bar Chart</h2>
  <div id="v2-chart" class="chart-container"></div>
  <details class="fig-explain">
    <summary>About this figure</summary>
    <div class="explain-body">
      <b>What it shows:</b> Mean student score on items generated by each teacher model,
      using the selected scoring formula (V1 / S2 / R3 from the filter above).<br>
      <b>How to read it:</b> Teachers that produce consistently lower or higher student
      scores may be generating easier or harder items respectively. Compare across teacher
      models while holding the student and judge filters fixed to isolate the teacher effect.<br>
      <b>Colours</b> indicate relative rank: green = top tier, blue = mid, orange = lower.
    </div>
  </details>
</div>
<div class="view-section">
  <h2>View 3 — Mean Score Heatmap (Teacher × Dimension)</h2>
  <div class="dim-controls">
    <label for="v3-dim-sel">X axis:</label>
    <select id="v3-dim-sel" onchange="renderV3()"></select>
  </div>
  <div id="v3-chart" class="chart-container"></div>
  <details class="fig-explain">
    <summary>About this figure</summary>
    <div class="explain-body">
      <b>What it shows:</b> A heatmap where rows = teacher models and columns = values of
      the selected X-axis dimension (rubric aspect, task, or target attribute).<br>
      Cell colour = mean student score on items from that teacher for that column value.<br>
      <b>Colour scale</b> adapts dynamically to the data range for maximum contrast.<br>
      <b>How to read it:</b> Cells reveal which teacher–dimension combinations produce
      systematically easier or harder items. Switch the X axis to "Task" to compare
      teachers across tasks, or to an attribute to see if teacher quality varies by
      difficulty level or other attributes.
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

function getFormula() { return getFilter('formula') || 'v1'; }

function renderAll() {
  if (DATA.single_student && DATA.single_student_notice) {
    var el = document.getElementById('degenerate-notice');
    el.style.display = 'block';
    el.textContent = DATA.single_student_notice;
  }
  // Populate V3 dim select
  var dimSel = document.getElementById('v3-dim-sel');
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
  var f = getFormula();
  var rows = DATA.ranking.slice().sort(function(a,b){return (b[f]||0)-(a[f]||0);});
  var v1tip = 'V1 (Variance): variance of per-student average scores. High = teacher items spread students apart well.';
  var s2tip = 'S2 (Spread): mean absolute deviation of per-student averages. Robust alternative to variance.';
  var r3tip = 'R3 (Range): max minus min per-student average. Simple spread measure.';
  var html = '<table class="data-table"><tr>'
    + '<th>Teacher</th>'
    + '<th>Datapoints</th>'
    + '<th><span data-tip="' + v1tip + '">V1 (Variance)</span></th>'
    + '<th><span data-tip="' + s2tip + '">S2 (Spread)</span></th>'
    + '<th><span data-tip="' + r3tip + '">R3 (Range)</span></th>'
    + '</tr>';
  rows.forEach(function(r) {
    var flag = r.is_also_student ? '<span class="warn-flag" title="Self-teaching responses included.">⚠ST</span>' : '';
    html += '<tr><td>' + tipFor(r.teacher, 'tasks') + flag + '</td><td>' + r.datapoints + '</td>';
    html += '<td>' + fmt(r.v1) + '</td><td>' + fmt(r.s2) + '</td><td>' + fmt(r.r3) + '</td></tr>';
  });
  document.getElementById('v1-table').innerHTML = html + '</table>';
  _makeSortable('v1-table');
}

function renderV2() {
  var f = getFormula();
  var rows = DATA.ranking.slice().sort(function(a,b){return (b[f]||0)-(a[f]||0);});
  var names = rows.map(function(r){return r.teacher;});
  var vals  = rows.map(function(r){return r[f];});
  var labels = vals.map(function(v){return (typeof v === 'number') ? v.toFixed(4) : '';});
  var maxV = vals.reduce(function(a,b){return Math.max(a,b||0);}, 0) || 1;
  var colors = vals.map(function(v) {
    var t = maxV > 0 ? (v||0) / maxV : 0;
    if (t >= 0.66) return '#22c55e';
    if (t >= 0.33) return '#3b82f6';
    return '#f97316';
  });
  var formulaLabel = {'v1':'V1 Variance','s2':'S2 Spread','r3':'R3 Range'}[f] || f;
  Plotly.newPlot('v2-chart',
    [{
      type: 'bar', x: names, y: vals,
      marker: { color: colors, line: { color: 'rgba(0,0,0,.12)', width: 1 } },
      text: labels, textposition: 'outside', cliponaxis: false,
      hovertemplate: '<b>%{x}</b><br>' + formulaLabel + ': %{y:.4f}<extra></extra>',
    }],
    {
      yaxis: { title: formulaLabel + ' score', autorange: true, gridcolor: '#f1f5f9' },
      xaxis: { title: 'Teacher model', tickangle: names.length > 5 ? -35 : 0 },
      margin: { t: 32, b: 100, l: 60, r: 20 },
      paper_bgcolor: '#fff', plot_bgcolor: '#fafbfc',
      showlegend: false,
    }, { responsive: true });
  _addPlotTooltips('v2-chart');
}

function renderV3() {
  var teachers = DATA.teachers;
  if (!teachers.length) return;

  var dimSel = document.getElementById('v3-dim-sel');
  var selectedDim = dimSel ? dimSel.value : 'aspect';

  var meanMap, xLabels, xTitle;
  if (selectedDim === 'aspect') {
    xTitle = 'Rubric Aspect';
    xLabels = DATA.aspects || [];
    meanMap = DATA.asp_mean || {};
  } else if (selectedDim === 'task') {
    xTitle = 'Task';
    xLabels = DATA.tasks || [];
    meanMap = DATA.task_mean || {};
  } else if (selectedDim.indexOf('attr:') === 0) {
    var attrKey = selectedDim.slice(5);
    xTitle = attrKey.replace(/_/g,' ');
    // Collect all values for this attrKey from attr_mean
    var valSet = {};
    teachers.forEach(function(t) {
      var m = (DATA.attr_mean || {})[t] || {};
      Object.keys(m).forEach(function(kv) {
        if (kv.indexOf(attrKey + '=') === 0) valSet[kv.slice(attrKey.length+1)] = true;
      });
    });
    xLabels = Object.keys(valSet).sort();
    // Build a wrapper that looks like asp_mean
    meanMap = {};
    teachers.forEach(function(t) {
      meanMap[t] = {};
      var m = (DATA.attr_mean || {})[t] || {};
      xLabels.forEach(function(val) {
        var v = m[attrKey + '=' + val];
        if (v !== undefined) meanMap[t][val] = v;
      });
    });
  } else {
    return;
  }

  if (!xLabels.length) {
    document.getElementById('v3-chart').innerHTML =
      '<p class="na" style="padding:16px">No data for this dimension.</p>';
    return;
  }

  var z = teachers.map(function(t) {
    return xLabels.map(function(a) {
      var s = meanMap[t];
      return s ? (s[a] !== undefined ? s[a] : null) : null;
    });
  });

  // Dynamic range based on actual data for maximum contrast
  var flat = [].concat.apply([], z).filter(function(v){return v !== null;});
  var zmin = flat.length ? Math.max(0, Math.min.apply(null, flat) - 0.02) : 0;
  var zmax = flat.length ? Math.min(1, Math.max.apply(null, flat) + 0.02) : 1;

  Plotly.newPlot('v3-chart', [{
    type: 'heatmap', z: z, x: xLabels, y: teachers,
    colorscale: [[0,'#ef4444'],[0.5,'#fef9c3'],[1,'#22c55e']],
    zmin: zmin, zmax: zmax,
    colorbar: { title: 'Mean Score', thickness: 14, len: 0.8 },
    hoverongaps: false,
    hovertemplate: 'Teacher: %{y}<br>' + xTitle + ': %{x}<br>Mean score: %{z:.3f}<extra></extra>',
  }], {
    xaxis: { title: xTitle, tickangle: xLabels.length > 5 ? -35 : 0, automargin: true },
    yaxis: { autorange: 'reversed' },
    margin: { t: 20, b: 100, l: 100, r: 80 },
    paper_bgcolor: '#fff', plot_bgcolor: '#fafbfc',
  }, { responsive: true });
  _addPlotTooltips('v3-chart');
}

document.addEventListener('DOMContentLoaded', renderAll);
"""
