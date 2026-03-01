"""Student Model Score Report — REQ-A-7.6."""
from __future__ import annotations

from collections import defaultdict
from pathlib import Path

from ..loader import EESDataModel
from ..metrics import compute_student_scores
from .html_base import build_report, get_plotly_js, make_experiment_meta


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

    # Aspect heatmap: student x aspect
    asp_student_avg: dict = {}
    for s in students:
        for asp in all_aspects:
            vals = [u.score_norm for u in units
                    if u.student_model_id == s and u.rubric_aspect == asp]
            asp_student_avg[f'{s}||{asp}'] = round(sum(vals)/len(vals), 4) if vals else None

    # Per-judge score comparison: (student, judge) -> avg
    student_judge_avg: dict = {}
    for s in students:
        for j in model.judges:
            vals = [u.score_norm for u in units
                    if u.student_model_id == s and u.judge_model_id == j]
            if vals:
                student_judge_avg[f'{s}||{j}'] = round(sum(vals)/len(vals), 4)

    # Per-attribute box plot data
    attr_scores: dict[str, dict] = {}
    for s in students:
        s_units = [u for u in units if u.student_model_id == s]
        by_attr: dict[str, list] = defaultdict(list)
        for u in s_units:
            dp = model.datapoints.get(u.datapoint_id, {})
            for k, v in dp.get('sampled_target_attributes', {}).items():
                by_attr[f'{k}={v}'].append(u.score_norm)
        attr_scores[s] = {k: v for k, v in by_attr.items()}

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
        'ranking': ranking_rows,
        'asp_student': asp_student_avg,
        'student_judge': student_judge_avg,
        'attr_scores': attr_scores,
        'all_units': all_units_compact,
    }


_VIEWS_HTML = """
<div class="view-section">
  <h2>View 1 — Student Ranking</h2>
  <div id="v1-table"></div>
  <details class="fig-explain">
    <summary>About this table</summary>
    <div class="explain-body">
      <b>What it shows:</b> Each row is a student model. Columns report the mean normalised
      score (0 = all Low, 1 = all High) for each rubric aspect, plus an overall average
      and the raw evaluation counts.<br>
      <b>How to read it:</b> Higher scores indicate better performance on that aspect.
      Use the Task, Teacher, and Judge filters to narrow the comparison to a specific
      experimental configuration. <b>⚠SJ</b> = self-judging; <b>⚠ST</b> = self-teaching
      — both flags suggest the score may be inflated.
    </div>
  </details>
</div>
<div class="view-section">
  <h2>View 2 — Aspect Heatmap (Student × Aspect)</h2>
  <div id="v2-chart" class="chart-container"></div>
  <details class="fig-explain">
    <summary>About this figure</summary>
    <div class="explain-body">
      <b>What it shows:</b> A heatmap where rows = student models, columns = rubric aspects,
      and cell colour = mean normalised score (green = high, red = low).<br>
      <b>How to read it:</b> A row that is uniformly green indicates a strong student model.
      A row with a mix of green and red shows strengths and weaknesses across different
      evaluation criteria. A column that is uniformly red suggests a rubric aspect that is
      difficult for all students, possibly reflecting the task design rather than model quality.
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
<div class="view-section">
  <h2>View 4 — Per-Attribute Score Breakdown</h2>
  <select id="v4-student" onchange="renderV4()" style="margin-bottom:8px;font-size:0.8rem"></select>
  <div id="v4-chart" class="chart-container"></div>
  <details class="fig-explain">
    <summary>About this figure</summary>
    <div class="explain-body">
      <b>What it shows:</b> For the selected student model, a bar chart of mean score
      broken down by each sampled target attribute value. Only visible when tasks use
      <code>sampled_target_attributes</code> in their config.<br>
      <b>How to read it:</b> Differences across attribute values reveal input characteristics
      that systematically affect model performance. For example, a student model may score
      well on <code>difficulty=easy</code> items but poorly on <code>difficulty=hard</code>
      items, exposing a capability boundary.
    </div>
  </details>
</div>
"""

_APP_JS = """
function filteredUnits() {
  var tf = getFilter('task'), tef = getFilter('teacher'), jf = getFilter('judge');
  return DATA.all_units.filter(function(u) {
    return (tf === '__all__' || u.task === tf)
        && (tef === '__all__' || u.teacher === tef)
        && (jf === '__all__' || u.judge === jf);
  });
}

function renderAll() {
  // Populate student dropdown for V4
  var sel = document.getElementById('v4-student');
  DATA.students.forEach(function(s) {
    var o = document.createElement('option'); o.value = s; o.textContent = s;
    sel.appendChild(o);
  });
  renderV1(); renderV2(); renderV3(); renderV4();
}

function renderV1() {
  var units = filteredUnits();
  // Re-compute averages from filtered units
  var studentAvg = {};
  units.forEach(function(u) {
    if (!studentAvg[u.student]) studentAvg[u.student] = [];
    studentAvg[u.student].push(u.score_norm);
  });
  var rows = DATA.ranking.slice().sort(function(a,b){return (b.overall||0)-(a.overall||0);});
  var html = '<table class="data-table"><tr><th>Student</th><th>Overall Avg Score</th>';
  DATA.tasks.forEach(function(t){html += '<th>' + t + '</th>';});
  html += '<th>Valid Evals</th></tr>';
  rows.forEach(function(r) {
    var arr = studentAvg[r.student] || [];
    var avg = arr.length ? arr.reduce(function(a,b){return a+b;},0)/arr.length : null;
    var sj_flag = r.is_also_judge ? '<span class="warn-flag" title="This student also acts as judge.">⚠</span>' : '';
    var st_flag = r.is_also_teacher ? '<span class="warn-flag" title="Self-teaching included.">⚠</span>' : '';
    html += '<tr><td>' + r.student + sj_flag + st_flag + '</td>';
    html += '<td>' + fmt(avg) + '</td>';
    DATA.tasks.forEach(function(t) {
      var t_units = units.filter(function(u){return u.student===r.student && u.task===t;});
      var t_avg = t_units.length ? t_units.reduce(function(a,u){return a+u.score_norm;},0)/t_units.length : null;
      html += '<td>' + fmt(t_avg) + '</td>';
    });
    html += '<td>' + arr.length + '</td></tr>';
  });
  document.getElementById('v1-table').innerHTML = html + '</table>';
}

function renderV2() {
  var students = DATA.students;
  var aspects = DATA.aspects;
  if (!students.length || !aspects.length) return;
  var z = students.map(function(s) {
    return aspects.map(function(a) {
      var v = DATA.asp_student[s + '||' + a];
      return v !== undefined ? v : null;
    });
  });
  Plotly.newPlot('v2-chart', [{
    type:'heatmap', z:z, x:aspects, y:students,
    colorscale:[[0,'#ffe0e0'],[0.5,'#fff7e0'],[1,'#e0ffe0']],
    zmin:0, zmax:1,
  }], {margin:{t:20}});
}

function renderV3() {
  var students = DATA.students;
  var judges = DATA.judges;
  if (!students.length || !judges.length) return;
  var traces = judges.map(function(j) {
    return {
      name: j, type:'bar',
      x: students,
      y: students.map(function(s) {
        return DATA.student_judge[s+'||'+j] !== undefined ? DATA.student_judge[s+'||'+j] : 0;
      }),
    };
  });
  Plotly.newPlot('v3-chart', traces,
    {barmode:'group', yaxis:{title:'Avg Score', range:[0,1]}, margin:{t:20}});
}

function renderV4() {
  var sel = document.getElementById('v4-student');
  var s = sel.value;
  if (!s) return;
  var attrData = DATA.attr_scores[s] || {};
  var keys = Object.keys(attrData).sort();
  if (!keys.length) {
    document.getElementById('v4-chart').innerHTML = '<p class="na" style="padding:16px">No attribute data.</p>';
    return;
  }
  var traces = keys.map(function(k) {
    return {type:'box', name:k, y:attrData[k], boxpoints:'outliers'};
  });
  Plotly.newPlot('v4-chart', traces,
    {yaxis:{title:'Score', range:[-.05,1.05]}, margin:{t:20}});
}

document.addEventListener('DOMContentLoaded', renderAll);
"""
