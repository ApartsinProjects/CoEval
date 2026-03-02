"""Teacher-Student Interaction Matrix — REQ-A-7.7."""
from __future__ import annotations

from collections import defaultdict
from pathlib import Path

from ..loader import EESDataModel
from .html_base import build_report, get_plotly_js, make_experiment_meta


def write_interaction_matrix(
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
        {'id': 'judge', 'label': 'Judge', 'options': [(j, j) for j in model.judges]},
    ]

    return build_report(
        out_dir=out_dir,
        title=f'Interaction Matrix — {exp_meta["id"]}',
        data=data,
        views_html=_VIEWS_HTML,
        filter_defs=filter_defs,
        stats_text=exp_meta['stats'],
        experiment_meta=exp_meta,
        report_type='Teacher-Student Interaction Matrix',
        extra_js=_APP_JS,
        partial=model.is_partial,
    )


def _build_data(model: EESDataModel) -> dict:
    units = model.units
    teachers = model.teachers
    students = model.students
    aspects = sorted(set(u.rubric_aspect for u in units))

    # (teacher, student) -> avg score
    ts_scores: dict[tuple, list] = defaultdict(list)
    for u in units:
        ts_scores[(u.teacher_model_id, u.student_model_id)].append(u.score_norm)

    ts_avg = {
        f'{t}||{s}': round(sum(v)/len(v), 4)
        for (t, s), v in ts_scores.items()
    }
    ts_count = {
        f'{t}||{s}': len(v)
        for (t, s), v in ts_scores.items()
    }

    # Deviation from row mean (student perspective)
    # For each student: mean across teachers; deviation = teacher_score - student_mean
    student_overall: dict[str, float] = {}
    for s in students:
        vals = [u.score_norm for u in units if u.student_model_id == s]
        student_overall[s] = sum(vals)/len(vals) if vals else 0.0

    ts_deviation = {
        k: round(v - student_overall.get(k.split('||')[1], 0.0), 4)
        for k, v in ts_avg.items()
    }

    # Per-aspect breakdown
    asp_ts_avg: dict[str, dict] = {}
    for asp in aspects:
        asp_units = [u for u in units if u.rubric_aspect == asp]
        asp_ts: dict[tuple, list] = defaultdict(list)
        for u in asp_units:
            asp_ts[(u.teacher_model_id, u.student_model_id)].append(u.score_norm)
        asp_ts_avg[asp] = {
            f'{t}||{s}': round(sum(v)/len(v), 4)
            for (t, s), v in asp_ts.items()
        }

    # Self-flagging: cells where teacher=student
    self_flag_keys = {f'{t}||{s}' for t in teachers for s in students if t == s}

    return {
        'teachers': teachers,
        'students': students,
        'aspects': aspects,
        'ts_avg': ts_avg,
        'ts_count': ts_count,
        'ts_deviation': ts_deviation,
        'asp_ts_avg': asp_ts_avg,
        'self_flag_keys': list(self_flag_keys),
        'all_units': [
            {
                'task': u.task_id, 'teacher': u.teacher_model_id,
                'student': u.student_model_id, 'judge': u.judge_model_id,
                'aspect': u.rubric_aspect, 'score_norm': u.score_norm,
            }
            for u in units
        ],
    }


_VIEWS_HTML = """
<div class="view-section">
  <p class="note"><b>Self-evaluation warning:</b> Cells where teacher = student or
  judge = student may reflect self-evaluation bias. These cells are highlighted.
  Interpret them with caution.</p>
  <h2>View 1 — Interaction Heatmap (Teacher × Student)</h2>
  <details class="fig-explain">
    <summary>What does this show?</summary>
    <div class="explain-body">
      <p>Mean normalised score for every teacher–student pair.
      <b>Green cells</b> indicate a teacher's datapoints consistently elicited
      high-quality responses from that student; <b>red cells</b> indicate low scores.
      Patterns reveal which teachers are most challenging for each student —
      or whether a particular combination is systematically biased.</p>
      <p>Score normalisation: Low = 0, Medium = 0.5, High = 1.</p>
    </div>
  </details>
  <div id="v1-chart" class="chart-container"></div>
</div>
<div class="view-section">
  <h2>View 2 — Deviation Heatmap (score − student mean across teachers)</h2>
  <details class="fig-explain">
    <summary>What does this show?</summary>
    <div class="explain-body">
      <p>How much each teacher's score for a student deviates from that student's
      overall mean score across all teachers.
      <b>Red cells</b> = teacher scored the student <em>above</em> their average;
      <b>blue cells</b> = <em>below</em>-average scores.</p>
      <p>Use this view to identify teachers that systematically advantage or challenge
      specific students beyond what their general ability would predict.</p>
    </div>
  </details>
  <div id="v2-chart" class="chart-container"></div>
</div>
<div class="view-section">
  <h2>View 3 — Per-Aspect Breakdown</h2>
  <details class="fig-explain">
    <summary>What does this show?</summary>
    <div class="explain-body">
      <p>The same teacher–student interaction heatmap filtered to a single rubric aspect.
      Select <em>All aspects</em> to show the overall mean (same as View 1).</p>
      <p>Use this view to check whether interaction patterns differ by rubric criterion —
      a teacher may challenge one student on <em>clarity</em> but not on
      <em>accuracy</em>.</p>
    </div>
  </details>
  <select id="v3-aspect" onchange="renderV3()" style="margin-bottom:8px;font-size:0.8rem">
    <option value="__all__">All aspects</option>
  </select>
  <div id="v3-chart" class="chart-container"></div>
</div>
"""

_APP_JS = """
function renderAll() {
  // Populate aspect dropdown
  var sel = document.getElementById('v3-aspect');
  DATA.aspects.forEach(function(a) {
    var o = document.createElement('option'); o.value = a; o.textContent = a;
    sel.appendChild(o);
  });
  renderV1(); renderV2(); renderV3();
}

function renderHeatmap(divId, zMatrix, title, colorscale, zmin, zmax) {
  Plotly.newPlot(divId, [{
    type:'heatmap', z:zMatrix,
    x: DATA.students, y: DATA.teachers,
    colorscale: colorscale,
    zmin: zmin, zmax: zmax,
    hovertemplate:'Teacher: %{y}<br>Student: %{x}<br>Value: %{z:.3f}<extra></extra>',
  }], {title: title, margin:{t:40}});
}

function renderV1() {
  var z = DATA.teachers.map(function(t) {
    return DATA.students.map(function(s) {
      var v = DATA.ts_avg[t+'||'+s];
      return v !== undefined ? v : null;
    });
  });
  renderHeatmap('v1-chart', z, 'Avg score (teacher × student)',
    [[0,'#ffe0e0'],[0.5,'#fff7e0'],[1,'#e0ffe0']], 0, 1);
}

function renderV2() {
  var z = DATA.teachers.map(function(t) {
    return DATA.students.map(function(s) {
      var v = DATA.ts_deviation[t+'||'+s];
      return v !== undefined ? v : null;
    });
  });
  renderHeatmap('v2-chart', z, 'Score deviation (teacher score − student overall mean)',
    [[0,'#2980b9'],[0.5,'#f7f7f7'],[1,'#c0392b']], -0.5, 0.5);
}

function renderV3() {
  var asp = document.getElementById('v3-aspect').value;
  if (asp === '__all__') { renderV1(); return; }
  var aspData = DATA.asp_ts_avg[asp] || {};
  var z = DATA.teachers.map(function(t) {
    return DATA.students.map(function(s) {
      var v = aspData[t+'||'+s];
      return v !== undefined ? v : null;
    });
  });
  renderHeatmap('v3-chart', z, 'Avg score — aspect: ' + asp,
    [[0,'#ffe0e0'],[0.5,'#fff7e0'],[1,'#e0ffe0']], 0, 1);
}

document.addEventListener('DOMContentLoaded', renderAll);
"""
