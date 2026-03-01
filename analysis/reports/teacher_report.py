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

    teacher_scores_map = compute_teacher_scores(units, teachers, students)

    # Per-aspect scores per teacher
    asp_teacher_score: dict[str, dict[str, dict]] = {}
    for teacher in teachers:
        t_units = [u for u in units if u.teacher_model_id == teacher]
        by_asp_student: dict[tuple, list] = defaultdict(list)
        for u in t_units:
            by_asp_student[(u.rubric_aspect, u.student_model_id)].append(u.score_norm)
        asp_avgs = {}
        for (asp, _), vals in by_asp_student.items():
            asp_avgs.setdefault(asp, []).append(sum(vals)/len(vals))
        # variance per aspect
        asp_teacher_score[teacher] = {}
        for asp, student_avgs in asp_avgs.items():
            if len(student_avgs) >= 2:
                mean = sum(student_avgs) / len(student_avgs)
                var = sum((x - mean)**2 for x in student_avgs) / (len(student_avgs) - 1)
                asp_teacher_score[teacher][asp] = round(var, 4)
            else:
                asp_teacher_score[teacher][asp] = 0.0

    # Mean student score per (teacher, aspect) for heatmap (0–1 scale)
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

    # Box plot data: per (teacher, student) score distribution
    teacher_student_boxes: dict[str, dict] = {}
    for teacher in teachers:
        for student in students:
            ts_units = [u for u in units
                        if u.teacher_model_id == teacher and u.student_model_id == student]
            teacher_student_boxes[f'{teacher}||{student}'] = [u.score_norm for u in ts_units]

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

    all_aspects = sorted(set(u.rubric_aspect for u in units))

    return {
        'teachers': teachers,
        'students': students,
        'aspects': all_aspects,
        'single_student': single_student,
        'single_student_notice': _SINGLE_STUDENT_NOTICE if single_student else '',
        'ranking': ranking_rows,
        'asp_scores': asp_teacher_score,
        'asp_mean': asp_teacher_mean,
        'teacher_student_boxes': teacher_student_boxes,
        'tips': collect_tooltip_data(model),
    }


_VIEWS_HTML = """
<div id="degenerate-notice" class="degenerate-notice" style="display:none"></div>
<div class="view-section">
  <h2>View 1 — Teacher Ranking</h2>
  <div id="v1-table"></div>
  <details class="fig-explain">
    <summary>About this table</summary>
    <div class="explain-body">
      <b>What it shows:</b> Each row is a teacher model. Columns include the mean student
      score on items generated by that teacher, a discrimination index, and per-aspect
      breakdowns.<br>
      <b>Mean score</b> reflects the average quality of the teacher's generated datapoints:
      higher-quality, well-designed items tend to yield more discriminating scores.<br>
      <b>Discrimination</b> measures the spread of student scores — a teacher with high
      discrimination creates items where strong students outperform weak ones. Low
      discrimination may indicate items that are too easy, too hard, or ambiguously phrased.<br>
      <b>⚠ST</b> flags self-teaching (teacher = student) — scores may be inflated.
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
      using the selected scoring formula. Error bars (if shown) represent ±1 standard
      deviation across evaluation units.<br>
      <b>How to read it:</b> Teachers that produce consistently lower or higher student
      scores may be generating easier or harder items respectively. Compare across teacher
      models while holding the student and judge filters fixed to isolate the teacher effect.
    </div>
  </details>
</div>
<div class="view-section">
  <h2>View 3 — Per-Aspect Score Heatmap</h2>
  <div id="v3-chart" class="chart-container"></div>
  <details class="fig-explain">
    <summary>About this figure</summary>
    <div class="explain-body">
      <b>What it shows:</b> A heatmap where rows = teacher models, columns = rubric aspects,
      and cell colour = mean student score on items from that teacher for that aspect.<br>
      <b>How to read it:</b> Cells reveal which teacher–aspect combinations produce
      systematically easier or harder items. A teacher with a red cell on one aspect but
      green on others may be generating domain-inappropriate or poorly-scoped items for
      that specific criterion.
    </div>
  </details>
</div>
<div class="view-section">
  <h2>View 4 — Student Score Distribution per Teacher (Box Plots)</h2>
  <div id="v4-chart" class="chart-container"></div>
  <details class="fig-explain">
    <summary>About this figure</summary>
    <div class="explain-body">
      <b>What it shows:</b> Box plots of student normalised scores grouped by teacher model.
      Each box shows median, IQR, whiskers (1.5 × IQR), and outliers.<br>
      <b>How to read it:</b> A narrow box with a high median indicates a teacher that
      reliably generates items where students score well. A wide box indicates high variance
      — the teacher's items vary in difficulty or clarity. Compare median positions to rank
      teachers by the average quality signal their items provide.
    </div>
  </details>
</div>
<div class="view-section">
  <p class="note"><b>Interpretation warning:</b> Teacher scores depend on which student and
  judge models are included. A teacher may appear highly discriminative only because one
  student model performs very poorly on all its items. Use the student and judge filters
  to verify that the differentiation is genuine.</p>
</div>
"""

_APP_JS = """
// Tooltip helpers — wrap text with a data-tip attribute when a definition exists
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
  renderV1(); renderV2(); renderV3(); renderV4();
}

function renderV1() {
  var f = getFormula();
  var rows = DATA.ranking.slice().sort(function(a,b){return (b[f]||0)-(a[f]||0);});
  var v1tip = 'V1 (Variance): variance of per-student average scores. High = teacher items spread students apart well.';
  var s2tip = 'S2 (Spread): mean absolute deviation of per-student averages. Robust alternative to variance.';
  var r3tip = 'R3 (Range): max minus min per-student average. Simple spread measure.';
  var html = '<table class="data-table"><tr>'
    + '<th>' + tipFor('Teacher', 'tasks') + '</th>'
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
}

function renderV2() {
  var f = getFormula();
  var rows = DATA.ranking.slice().sort(function(a,b){return (b[f]||0)-(a[f]||0);});
  var names = rows.map(function(r){return r.teacher;});
  var vals = rows.map(function(r){return r[f];});
  var labels = vals.map(function(v){return (typeof v === 'number') ? v.toFixed(4) : '';});
  Plotly.newPlot('v2-chart',
    [{type:'bar', x: names, y: vals, marker:{color:'#2980b9'},
      text: labels, textposition: 'outside', cliponaxis: false}],
    {yaxis:{title:'Teacher differentiation score (' + f + ')', autorange: true},
     xaxis:{title:'Teacher'}, margin:{t:40}});
}

function renderV3() {
  var teachers = DATA.teachers;
  var aspects = DATA.aspects;
  if (!teachers.length || !aspects.length) return;
  var z = teachers.map(function(t) {
    return aspects.map(function(a) {
      var s = DATA.asp_mean[t];
      return s ? (s[a] !== undefined ? s[a] : null) : null;
    });
  });
  // Dynamic range: pad by 5% each side, clamp to [0,1]
  var flat = [].concat.apply([], z).filter(function(v){return v !== null;});
  var zmin = flat.length ? Math.max(0, Math.min.apply(null, flat) - 0.05) : 0;
  var zmax = flat.length ? Math.min(1, Math.max.apply(null, flat) + 0.05) : 1;
  Plotly.newPlot('v3-chart', [{
    type:'heatmap', z: z, x: aspects, y: teachers,
    colorscale:[[0,'#ef4444'],[0.5,'#fef9c3'],[1,'#22c55e']],
    zmin: zmin, zmax: zmax,
    colorbar:{title:'Mean Score'},
    hoverongaps: false,
  }], {margin:{t:20}});
}

function renderV4() {
  var teachers = DATA.teachers;
  var students = DATA.students;
  var traces = [];
  teachers.forEach(function(t) {
    students.forEach(function(s) {
      var key = t + '||' + s;
      var vals = DATA.teacher_student_boxes[key] || [];
      if (vals.length) {
        traces.push({type:'box', name: t + ' / ' + s, y: vals, boxpoints:'outliers'});
      }
    });
  });
  if (!traces.length) return;
  Plotly.newPlot('v4-chart', traces,
    {yaxis:{title:'Score', range:[-.05,1.05]}, margin:{t:20}});
}

document.addEventListener('DOMContentLoaded', renderAll);
"""
