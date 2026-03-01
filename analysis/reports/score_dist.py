"""Score Distribution Report — REQ-A-7.3."""
from __future__ import annotations

from collections import defaultdict
from pathlib import Path

from ..loader import EESDataModel
from .html_base import build_report, get_plotly_js, make_experiment_meta


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
        {'id': 'task', 'label': 'Task', 'options': [(t, t) for t in model.tasks]},
        {'id': 'judge', 'label': 'Judge', 'options': [(j, j) for j in model.judges]},
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


def _build_data(model: EESDataModel) -> dict:
    units = model.units

    # By aspect: High/Medium/Low counts
    aspect_hist: dict[str, dict] = defaultdict(lambda: {'High': 0, 'Medium': 0, 'Low': 0})
    for u in units:
        aspect_hist[u.rubric_aspect][u.score] += 1

    # By (aspect, student): fraction High
    asp_student_high: dict[tuple, list] = defaultdict(list)
    for u in units:
        asp_student_high[(u.rubric_aspect, u.student_model_id)].append(u.score_norm)

    # By (task, attr_value, aspect): fraction High for target attr heatmap
    attr_asp_scores: dict[tuple, list] = defaultdict(list)
    for u in units:
        dp = model.datapoints.get(u.datapoint_id, {})
        for k, v in dp.get('sampled_target_attributes', {}).items():
            attr_asp_scores[(f'{k}={v}', u.rubric_aspect)].append(u.score_norm)

    # Judge drift over time (View 4) — sequences per judge
    judge_sequences: dict[str, list] = defaultdict(list)
    sorted_units = sorted(units, key=lambda u: u.evaluated_at or '')
    for u in sorted_units:
        judge_sequences[u.judge_model_id].append(u.score_norm)

    # All dimensions for the embedded data
    all_aspects = sorted(set(u.rubric_aspect for u in units))
    all_students = model.students
    all_attr_keys = sorted({av for av, _ in attr_asp_scores})

    return {
        'aspects': all_aspects,
        'students': all_students,
        'judges': model.judges,
        'aspect_hist': {k: dict(v) for k, v in aspect_hist.items()},
        'asp_student_avg': {
            f'{a}||{s}': (sum(v)/len(v)) for (a, s), v in asp_student_high.items()
        },
        'attr_labels': all_attr_keys,
        'attr_asp_avg': {
            f'{av}||{a}': (sum(v)/len(v)) for (av, a), v in attr_asp_scores.items()
        },
        'judge_sequences': {j: seq for j, seq in judge_sequences.items()},
        'all_units': [
            {
                'task': u.task_id,
                'teacher': u.teacher_model_id,
                'student': u.student_model_id,
                'judge': u.judge_model_id,
                'aspect': u.rubric_aspect,
                'score': u.score,
                'score_norm': u.score_norm,
                'evaluated_at': u.evaluated_at,
            }
            for u in units
        ],
    }


_VIEWS_HTML = """
<div class="view-section">
  <h2>View 1 — Overall Score Distribution by Rubric Aspect</h2>
  <div id="v1-chart" class="chart-container"></div>
  <details class="fig-explain">
    <summary>About this figure</summary>
    <div class="explain-body">
      <b>What it shows:</b> A stacked bar chart of evaluation scores across each rubric aspect.
      Each bar is split into <b>High / Medium / Low</b> segments, showing the proportion of
      evaluations at each level for that aspect.<br>
      <b>How to read it:</b> A tall green (High) segment means student responses frequently
      met the rubric criterion. A tall red (Low) segment flags a systematic weakness.
      Use the Task / Judge / Teacher / Student filters to isolate specific sub-populations.
    </div>
  </details>
</div>
<div class="view-section">
  <h2>View 2 — Score Distribution by Student Model</h2>
  <div class="filter-group" style="margin-bottom:8px">
    <label>Show level:</label>
    <select id="v2-level" onchange="renderV2()">
      <option value="High">High</option>
      <option value="Medium">Medium</option>
      <option value="Low">Low</option>
    </select>
  </div>
  <div id="v2-chart" class="chart-container"></div>
  <details class="fig-explain">
    <summary>About this figure</summary>
    <div class="explain-body">
      <b>What it shows:</b> For the selected score level (High / Medium / Low), this grouped
      bar chart shows the <em>fraction</em> of evaluations at that level, broken down by
      rubric aspect (x-axis) and student model (colour groups).<br>
      <b>How to read it:</b> Compare bar heights within a single aspect to see which student
      model scores highest / lowest on that criterion. Switch the level dropdown between
      <code>High</code> and <code>Low</code> to inspect both ends of the distribution.
    </div>
  </details>
</div>
<div class="view-section">
  <h2>View 3 — Score by Target Attribute Value (Heatmap)</h2>
  <div id="v3-chart" class="chart-container"></div>
  <details class="fig-explain">
    <summary>About this figure</summary>
    <div class="explain-body">
      <b>What it shows:</b> A heatmap of mean normalised score (0 = Low, 0.5 = Medium,
      1 = High) for each combination of sampled target attribute value (rows) and rubric
      aspect (columns). Only populated when tasks define <code>sampled_target_attributes</code>.<br>
      <b>How to read it:</b> Green cells indicate that items with a particular attribute
      value consistently score High on a given aspect. Red cells reveal specific
      attribute–aspect combinations that are systematically harder for student models.
    </div>
  </details>
</div>
<div class="view-section">
  <h2>View 4 — Judge Score Drift Over Evaluation Order</h2>
  <p class="note">Hidden when any judge has fewer than 20 valid evaluation records.</p>
  <div id="v4-chart" class="chart-container"></div>
  <details class="fig-explain">
    <summary>About this figure</summary>
    <div class="explain-body">
      <b>What it shows:</b> A rolling-average (window = 20) of the normalised score assigned
      by each judge model, plotted against evaluation sequence number.<br>
      <b>How to read it:</b> A flat line indicates consistent judgment throughout the run.
      An upward or downward trend may signal <em>judge drift</em> — the model becoming
      more lenient or strict as the evaluation progresses (e.g., due to context accumulation
      in batch mode). A systematic difference between judges at the same sequence position
      indicates a scoring bias between judges.
    </div>
  </details>
</div>
"""

_APP_JS = """
function filteredUnits() {
  var tf = getFilter('task'), jf = getFilter('judge');
  var tef = getFilter('teacher'), sf = getFilter('student');
  return DATA.all_units.filter(function(u) {
    return (tf === '__all__' || u.task === tf)
        && (jf === '__all__' || u.judge === jf)
        && (tef === '__all__' || u.teacher === tef)
        && (sf === '__all__' || u.student === sf);
  });
}

function renderV1() {
  var units = filteredUnits();
  var ah = {};
  units.forEach(function(u) {
    if (!ah[u.aspect]) ah[u.aspect] = {High:0,Medium:0,Low:0};
    ah[u.aspect][u.score]++;
  });
  var aspects = Object.keys(ah).sort();
  if (aspects.length === 0) { document.getElementById('v1-chart').innerHTML = '<p class="na" style="padding:16px">No data</p>'; return; }
  var total = aspects.map(function(a) { return ah[a].High + ah[a].Medium + ah[a].Low || 1; });
  var traces = [
    {name:'High', x: aspects, y: aspects.map(function(a,i){return ah[a].High/total[i]*100;}),
     type:'bar', marker:{color:'#27ae60'}, text: aspects.map(function(a){return ah[a].High.toString();}), textposition:'auto'},
    {name:'Medium', x: aspects, y: aspects.map(function(a,i){return ah[a].Medium/total[i]*100;}),
     type:'bar', marker:{color:'#f0a500'}},
    {name:'Low', x: aspects, y: aspects.map(function(a,i){return ah[a].Low/total[i]*100;}),
     type:'bar', marker:{color:'#e74c3c'}},
  ];
  Plotly.newPlot('v1-chart', traces,
    {barmode:'stack', yaxis:{title:'%', range:[0,100]}, margin:{t:20}});
}

function renderV3() {
  var units = filteredUnits();
  var attrAsp = {};
  units.forEach(function(u) {
    // Get attr-value from DATA by datapoint — we embed all_units with score only,
    // so use precomputed attr_asp_avg filtered by current filters
    // For simplicity, use DATA.attr_asp_avg as-is (no dynamic filtering by attr)
  });
  var attrLabels = DATA.attr_labels;
  var aspects = [...new Set(units.map(function(u){return u.aspect;}))].sort();
  if (!attrLabels.length || !aspects.length) return;

  var z = attrLabels.map(function(av) {
    return aspects.map(function(a) {
      var key = av + '||' + a;
      return DATA.attr_asp_avg[key] !== undefined ? DATA.attr_asp_avg[key] : null;
    });
  });
  Plotly.newPlot('v3-chart', [{
    type: 'heatmap', z: z, x: aspects, y: attrLabels,
    colorscale: [[0,'#e74c3c'],[0.5,'#f7f7f7'],[1,'#27ae60']],
    zmin: 0, zmax: 1,
  }], {margin:{t:20}});
}

function renderV4() {
  var seqs = DATA.judge_sequences;
  var judges = Object.keys(seqs);
  var WIN = 20;
  var anyShort = judges.some(function(j){return seqs[j].length < WIN;});
  if (anyShort) {
    document.getElementById('v4-chart').innerHTML =
      '<p class="na" style="padding:16px">Hidden: at least one judge has fewer than 20 evaluation records.</p>';
    return;
  }
  var traces = judges.map(function(j) {
    var seq = seqs[j];
    var rolled = seq.map(function(_, i) {
      if (i < WIN-1) return null;
      var window = seq.slice(i-WIN+1, i+1);
      return window.reduce(function(a,b){return a+b;},0) / WIN;
    }).filter(function(v){return v !== null;});
    return {name: j, type: 'scatter', mode: 'lines', y: rolled};
  });
  Plotly.newPlot('v4-chart', traces, {
    title: 'Rolling average score (window=20)',
    yaxis: {range: [0, 1], title: 'Score'},
    xaxis: {title: 'Evaluation #'},
    margin: {t: 40},
  });
}

// Fix: remove accidental dict type annotation from V2
function renderV2() {
  var level = document.getElementById('v2-level').value;
  var units = filteredUnits();
  var asp_student = {};
  units.forEach(function(u) {
    var k = u.aspect + '||' + u.student;
    if (!asp_student[k]) asp_student[k] = [];
    asp_student[k].push(u.score === level ? 1 : 0);
  });
  var aspects = [];
  units.forEach(function(u){ if(aspects.indexOf(u.aspect)<0) aspects.push(u.aspect); });
  aspects.sort();
  var students = [];
  units.forEach(function(u){ if(students.indexOf(u.student)<0) students.push(u.student); });
  students.sort();
  if (aspects.length === 0) return;
  var traces = students.map(function(s) {
    return {
      name: s, type: 'bar', x: aspects,
      y: aspects.map(function(a) {
        var k = a + '||' + s;
        var arr = asp_student[k] || [];
        return arr.length ? arr.reduce(function(a,b){return a+b;},0)/arr.length : 0;
      }),
    };
  });
  Plotly.newPlot('v2-chart', traces,
    {barmode:'group', yaxis:{title: 'Fraction ' + level, range:[0,1]}, margin:{t:20}});
}

function renderAll() { renderV1(); renderV2(); renderV3(); renderV4(); }
document.addEventListener('DOMContentLoaded', renderAll);
"""
