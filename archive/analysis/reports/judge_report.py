"""Judge Model Score Report — REQ-A-7.5."""
from __future__ import annotations

from collections import defaultdict
from pathlib import Path

from ..loader import EESDataModel
from ..metrics import (
    compute_all_agreements,
    compute_judge_scores,
    kappa_label,
)
from .html_base import build_report, collect_tooltip_data, get_plotly_js, make_experiment_meta

_SINGLE_JUDGE_NOTICE = (
    "⚠ Only 1 judge model in this experiment. "
    "Agreement metrics are trivially 1.0 and carry no information. "
    "Add ≥2 judge models to obtain meaningful agreement estimates."
)


def write_judge_report(
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
        {'id': 'metric', 'label': 'Agreement metric',
         'options': [('spa', 'SPA'), ('wpa', 'WPA'), ('kappa', 'Kappa')]},
    ]

    return build_report(
        out_dir=out_dir,
        title=f'Judge Report — {exp_meta["id"]}',
        data=data,
        views_html=_VIEWS_HTML,
        filter_defs=filter_defs,
        stats_text=exp_meta['stats'],
        experiment_meta=exp_meta,
        report_type='Judge Model Score Report',
        extra_js=_APP_JS,
        partial=model.is_partial,
    )


def _build_data(model: EESDataModel) -> dict:
    units = model.units
    judges = model.judges
    single = len(judges) <= 1

    agreements = compute_all_agreements(units, judges)
    judge_scores_map = compute_judge_scores(units, judges, agreements)

    # Ranking table rows
    ranking_rows = []
    for j in judges:
        jr = judge_scores_map.get(j)
        n_evals = sum(1 for u in units if u.judge_model_id == j)
        is_student_too = j in model.students
        ranking_rows.append({
            'judge': j,
            'spa': round(jr.spa_mean, 4) if jr and jr.spa_mean is not None else None,
            'wpa': round(jr.wpa_mean, 4) if jr and jr.wpa_mean is not None else None,
            'kappa': round(jr.kappa_mean, 4) if jr and jr.kappa_mean is not None else None,
            'kappa_label': kappa_label(jr.kappa_mean if jr else None),
            'spa_w': round(jr.spa_weighted, 4) if jr and jr.spa_weighted is not None else None,
            'wpa_w': round(jr.wpa_weighted, 4) if jr and jr.wpa_weighted is not None else None,
            'kappa_w': round(jr.kappa_weighted, 4) if jr and jr.kappa_weighted is not None else None,
            'valid_evals': n_evals,
            'degenerate': jr.degenerate if jr else False,
            'is_also_student': is_student_too,
        })

    # Pairwise matrix
    matrix = {}
    for ja in judges:
        for jb in judges:
            if ja == jb:
                matrix[f'{ja}||{jb}'] = None
            else:
                res = agreements.get((ja, jb))
                if res:
                    matrix[f'{ja}||{jb}'] = {
                        'spa': round(res.spa, 4) if res.spa is not None else None,
                        'wpa': round(res.wpa, 4) if res.wpa is not None else None,
                        'kappa': round(res.kappa, 4) if res.kappa is not None else None,
                        'count': res.count,
                    }

    # Per-aspect agreement
    aspect_agreement: dict[str, dict] = defaultdict(lambda: {'spa': [], 'wpa': [], 'kappa': []})
    for (ja, jb), res in agreements.items():
        if ja >= jb:
            continue
        by_key: dict[tuple, dict[str, str]] = defaultdict(dict)
        for u in units:
            if u.judge_model_id in (ja, jb):
                key = (u.response_id, u.rubric_aspect)
                by_key[key][u.judge_model_id] = u.score
        asp_data: dict[str, dict] = defaultdict(lambda: {'agree': 0, 'n': 0, 'wsum': 0.0})
        for (resp_id, asp), scores in by_key.items():
            if ja in scores and jb in scores:
                asp_data[asp]['n'] += 1
                if scores[ja] == scores[jb]:
                    asp_data[asp]['agree'] += 1
                asp_data[asp]['wsum'] += _wpa_weight(scores[ja], scores[jb])
        for asp, d in asp_data.items():
            if d['n'] > 0:
                aspect_agreement[asp]['spa'].append(d['agree'] / d['n'])
                aspect_agreement[asp]['wpa'].append(d['wsum'] / d['n'])

    aspect_rows = [
        {
            'aspect': asp,
            'spa': round(sum(v['spa'])/len(v['spa']), 4) if v['spa'] else None,
            'wpa': round(sum(v['wpa'])/len(v['wpa']), 4) if v['wpa'] else None,
        }
        for asp, v in sorted(aspect_agreement.items())
    ]

    # Per-teacher agreement breakdown
    teacher_agreement: dict[str, dict] = defaultdict(lambda: {'spa': [], 'wpa': []})
    for (ja, jb), res in agreements.items():
        if ja >= jb:
            continue
        by_key2: dict[tuple, dict[str, str]] = defaultdict(dict)
        teacher_map: dict[tuple, str] = {}
        for u in units:
            if u.judge_model_id in (ja, jb):
                key = (u.response_id, u.rubric_aspect)
                by_key2[key][u.judge_model_id] = u.score
                teacher_map[key] = u.teacher_model_id
        tdata: dict[str, dict] = defaultdict(lambda: {'agree': 0, 'n': 0, 'wsum': 0.0})
        for key, scores in by_key2.items():
            t = teacher_map.get(key, '(unknown)')
            if ja in scores and jb in scores:
                tdata[t]['n'] += 1
                if scores[ja] == scores[jb]:
                    tdata[t]['agree'] += 1
                tdata[t]['wsum'] += _wpa_weight(scores[ja], scores[jb])
        for t, d in tdata.items():
            if d['n'] > 0:
                teacher_agreement[t]['spa'].append(d['agree'] / d['n'])
                teacher_agreement[t]['wpa'].append(d['wsum'] / d['n'])

    teacher_rows = [
        {
            'teacher': t,
            'spa': round(sum(v['spa'])/len(v['spa']), 4) if v['spa'] else None,
            'wpa': round(sum(v['wpa'])/len(v['wpa']), 4) if v['wpa'] else None,
        }
        for t, v in sorted(teacher_agreement.items())
    ]

    # Per-student agreement breakdown
    student_agreement: dict[str, dict] = defaultdict(lambda: {'spa': [], 'wpa': []})
    for (ja, jb), res in agreements.items():
        if ja >= jb:
            continue
        by_key3: dict[tuple, dict[str, str]] = defaultdict(dict)
        student_map: dict[tuple, str] = {}
        for u in units:
            if u.judge_model_id in (ja, jb):
                key = (u.response_id, u.rubric_aspect)
                by_key3[key][u.judge_model_id] = u.score
                student_map[key] = u.student_model_id
        sdata: dict[str, dict] = defaultdict(lambda: {'agree': 0, 'n': 0, 'wsum': 0.0})
        for key, scores in by_key3.items():
            s = student_map.get(key, '(unknown)')
            if ja in scores and jb in scores:
                sdata[s]['n'] += 1
                if scores[ja] == scores[jb]:
                    sdata[s]['agree'] += 1
                sdata[s]['wsum'] += _wpa_weight(scores[ja], scores[jb])
        for s, d in sdata.items():
            if d['n'] > 0:
                student_agreement[s]['spa'].append(d['agree'] / d['n'])
                student_agreement[s]['wpa'].append(d['wsum'] / d['n'])

    student_rows = [
        {
            'student': s,
            'spa': round(sum(v['spa'])/len(v['spa']), 4) if v['spa'] else None,
            'wpa': round(sum(v['wpa'])/len(v['wpa']), 4) if v['wpa'] else None,
        }
        for s, v in sorted(student_agreement.items())
    ]

    # Per-task agreement breakdown
    task_agreement: dict[str, dict] = defaultdict(lambda: {'spa': [], 'wpa': []})
    for (ja, jb), res in agreements.items():
        if ja >= jb:
            continue
        by_key4: dict[tuple, dict[str, str]] = defaultdict(dict)
        task_map: dict[tuple, str] = {}
        for u in units:
            if u.judge_model_id in (ja, jb):
                key = (u.response_id, u.rubric_aspect)
                by_key4[key][u.judge_model_id] = u.score
                task_map[key] = u.task_id
        tkdata: dict[str, dict] = defaultdict(lambda: {'agree': 0, 'n': 0, 'wsum': 0.0})
        for key, scores in by_key4.items():
            tk = task_map.get(key, '(unknown)')
            if ja in scores and jb in scores:
                tkdata[tk]['n'] += 1
                if scores[ja] == scores[jb]:
                    tkdata[tk]['agree'] += 1
                tkdata[tk]['wsum'] += _wpa_weight(scores[ja], scores[jb])
        for tk, d in tkdata.items():
            if d['n'] > 0:
                task_agreement[tk]['spa'].append(d['agree'] / d['n'])
                task_agreement[tk]['wpa'].append(d['wsum'] / d['n'])

    task_rows = [
        {
            'task': tk,
            'spa': round(sum(v['spa'])/len(v['spa']), 4) if v['spa'] else None,
            'wpa': round(sum(v['wpa'])/len(v['wpa']), 4) if v['wpa'] else None,
        }
        for tk, v in sorted(task_agreement.items())
    ]

    # Check if any matrix data exists
    has_matrix_data = any(
        v is not None and (v.get('spa') is not None or v.get('wpa') is not None
                           or v.get('kappa') is not None)
        for v in matrix.values()
    ) if matrix else False

    tips = collect_tooltip_data(model)

    return {
        'judges': judges,
        'single_judge': single,
        'single_judge_notice': _SINGLE_JUDGE_NOTICE if single else '',
        'ranking': ranking_rows,
        'matrix': matrix,
        'has_matrix_data': has_matrix_data,
        'aspect_rows': aspect_rows,
        'teacher_rows': teacher_rows,
        'student_rows': student_rows,
        'task_rows': task_rows,
        'tips': tips,
    }


def _wpa_weight(a: str, b: str) -> float:
    table = {
        ('High', 'High'): 1.0, ('High', 'Medium'): 0.5, ('High', 'Low'): 0.0,
        ('Medium', 'High'): 0.5, ('Medium', 'Medium'): 1.0, ('Medium', 'Low'): 0.5,
        ('Low', 'High'): 0.0, ('Low', 'Medium'): 0.5, ('Low', 'Low'): 1.0,
    }
    return table.get((a, b), 0.0)


_VIEWS_HTML = """
<style>
.v3-controls {
  display:flex; align-items:center; gap:12px; flex-wrap:wrap;
  padding:8px 12px; background:#f8fafc; border:1px solid #e2e8f0;
  border-radius:8px; margin-bottom:10px;
}
.v3-controls label { font-size:.77rem; font-weight:600; color:#475569; }
.v3-controls select {
  border:1px solid #cbd5e1; border-radius:5px; padding:4px 8px;
  font-size:.77rem; background:#fff; cursor:pointer;
}
</style>
<div id="degenerate-notice" class="degenerate-notice" style="display:none"></div>
<div class="view-section">
  <h2>View 1 — Judge Ranking</h2>
  <button class="csv-export-btn" onclick="_csvExportTable('v1-table','judge_ranking.csv')">⬇ CSV</button>
  <div id="v1-table"></div>
  <details class="fig-explain">
    <summary>About this table</summary>
    <div class="explain-body">
      <b>What it shows:</b> Each row is a judge model with inter-judge agreement scores
      averaged across all rubric aspects and task–teacher–student combinations.<br>
      <b>SPA</b> (Simple Percent Agreement) = fraction of pairwise evaluation pairs where
      both judges assigned the same score level. Range 0–1; higher is better.<br>
      <b>WPA</b> (Weighted Percent Agreement) = SPA with partial credit for near-misses
      (High/Medium = 0.5 weight, High/Low = 0 weight).<br>
      <b>κ (Kappa)</b> = Cohen's κ; corrects for chance agreement. Interpretation:
      &lt;0 = worse than chance; 0–0.2 = slight; 0.2–0.4 = fair; 0.4–0.6 = moderate;
      0.6–0.8 = substantial; &gt;0.8 = near-perfect.<br>
      <b>Coverage-Weighted</b> = same metric weighted by number of evaluation units per pair.<br>
      <b>⚠SJ</b> = self-judging (judge = student). Click any column to sort.
    </div>
  </details>
</div>
<div class="view-section">
  <h2>View 2 — Pairwise Agreement Matrix</h2>
  <div id="v2-chart" class="chart-container"></div>
  <details class="fig-explain">
    <summary>About this figure</summary>
    <div class="explain-body">
      <b>What it shows:</b> A symmetric heatmap where each cell (i,&thinsp;j) shows the
      agreement between judge <em>i</em> (y-axis) and judge <em>j</em> (x-axis) on the same
      evaluation units. Both axes label the judge model name.<br>
      The diagonal is excluded (a judge trivially agrees with itself).<br>
      <b>How to read it:</b> Green = high agreement; red = low agreement / systematic bias.
      Use the Agreement metric filter (SPA / WPA / Kappa) to switch measures.<br>
      <b>Note:</b> Agreement can only be computed when two judges evaluated the same
      response–aspect pairs. If this heatmap shows no data, judges evaluated disjoint sets
      of responses (common in batch-split evaluation designs).
    </div>
  </details>
</div>
<div class="view-section">
  <h2>View 3 — Agreement by Dimension</h2>
  <div class="v3-controls">
    <label for="v3-dim-sel">X axis:</label>
    <select id="v3-dim-sel" onchange="renderV3()">
      <option value="aspect">Rubric Aspect</option>
      <option value="teacher">Teacher Model</option>
      <option value="student">Student Model</option>
      <option value="task">Task</option>
    </select>
  </div>
  <div id="v3-chart" class="chart-container"></div>
  <details class="fig-explain">
    <summary>About this figure</summary>
    <div class="explain-body">
      <b>What it shows:</b> Mean inter-judge agreement broken down by the selected dimension.
      Switch between Rubric Aspect, Teacher, Student, or Task to explore where
      judges agree or disagree most.<br>
      <b>Per-aspect:</b> Low agreement on a specific rubric criterion means judges interpret
      it inconsistently — consider improving the rubric description.<br>
      <b>Per-teacher:</b> Low agreement on one teacher's items may indicate those items are
      ambiguously phrased or outside the rubric scope.<br>
      <b>Per-student:</b> Low agreement on one student may indicate edge-case or borderline
      responses that are hard to classify consistently.<br>
      <b>Per-task:</b> Low agreement on a specific task reveals systematic rubric–task mismatch.
    </div>
  </details>
</div>
"""

_APP_JS = """
function escHtml(s) {
  return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}
function getMetric() { return getFilter('metric') || 'spa'; }

// Column header tooltip text for V1
var _COL_TIPS = {
  'SPA': 'Simple Percent Agreement: fraction of evaluation pairs where both judges gave the same score (0–1, higher is better).',
  'WPA': 'Weighted Percent Agreement: like SPA but with partial credit for near-misses (High vs Medium = 0.5 weight).',
  'κ':   "Cohen's Kappa: agreement corrected for chance. <0=worse than chance; 0-0.2=slight; 0.2-0.4=fair; 0.4-0.6=moderate; 0.6-0.8=substantial; >0.8=near-perfect.",
  'κ label': "Qualitative interpretation of κ (Cohen's Kappa).",
  'Coverage-Weighted': 'Same as selected metric, but weighted by number of evaluation units per judge pair — larger pairs contribute more.',
  'Valid Evals': 'Total number of valid evaluation records produced by this judge.',
};

function renderAll() {
  if (DATA.single_judge && DATA.single_judge_notice) {
    var el = document.getElementById('degenerate-notice');
    el.style.display = 'block';
    el.textContent = DATA.single_judge_notice;
  }
  renderV1(); renderV2(); renderV3();
}

function renderV1() {
  var m = getMetric();
  var rows = DATA.ranking.slice().sort(function(a,b){ return (b[m]||0)-(a[m]||0); });
  var cols = ['SPA','WPA','κ','κ label','Coverage-Weighted','Valid Evals'];
  var html = '<table class="data-table"><tr><th>Judge</th>';
  cols.forEach(function(c) {
    var tip = _COL_TIPS[c];
    html += '<th>' + (tip ? '<span data-tip="' + escHtml(tip) + '">' + escHtml(c) + '</span>' : escHtml(c)) + '</th>';
  });
  html += '</tr>';
  rows.forEach(function(r) {
    var flag = r.is_also_student
      ? '<span class="warn-flag" title="This judge also acts as a student.">⚠SJ</span>' : '';
    html += '<tr><td>' + escHtml(r.judge) + flag + '</td>';
    html += '<td>' + fmt(r.spa) + '</td><td>' + fmt(r.wpa) + '</td>';
    html += '<td>' + fmt(r.kappa) + '</td><td>' + escHtml(r.kappa_label) + '</td>';
    var w = m === 'spa' ? r.spa_w : m === 'wpa' ? r.wpa_w : r.kappa_w;
    html += '<td>' + fmt(w) + '</td><td>' + r.valid_evals + '</td></tr>';
  });
  html += '</table>';
  document.getElementById('v1-table').innerHTML = html;
  _makeSortable('v1-table');
}

function renderV2() {
  var m = getMetric();
  var judges = DATA.judges;
  if (judges.length < 2) {
    document.getElementById('v2-chart').innerHTML =
      '<p class="na" style="padding:16px">Need \\u22652 judges for agreement matrix.</p>';
    return;
  }
  if (!DATA.has_matrix_data) {
    document.getElementById('v2-chart').innerHTML =
      '<p class="na" style="padding:16px">No shared evaluation units found between judges. '
      + 'Pairwise agreement requires two or more judges to evaluate the same response-aspect '
      + 'pairs. In split-batch designs each judge evaluates a disjoint set of responses, '
      + 'so agreement cannot be computed.</p>';
    return;
  }

  var z = judges.map(function(ja) {
    return judges.map(function(jb) {
      if (ja === jb) return 1.0;  // diagonal = 1
      var key = ja + '||' + jb;
      var entry = DATA.matrix[key];
      return (entry && entry[m] !== null && entry[m] !== undefined) ? entry[m] : null;
    });
  });

  var metricLabel = m.toUpperCase();
  var zmin = m === 'kappa' ? -1 : 0;
  var colorscale = m === 'kappa'
    ? [[0,'#dc2626'],[0.25,'#f97316'],[0.5,'#f3f4f6'],[0.75,'#4ade80'],[1,'#16a34a']]
    : [[0,'#dc2626'],[0.33,'#fb923c'],[0.5,'#fbbf24'],[0.67,'#84cc16'],[1,'#16a34a']];

  // Dynamic scale for more contrast
  var flat = [].concat.apply([], z).filter(function(v){return v !== null;});
  var dataMin = flat.length ? Math.min.apply(null,flat) : zmin;
  var dataMax = flat.length ? Math.max.apply(null,flat) : 1;
  var useMin = Math.max(zmin, dataMin - 0.02);
  var useMax = Math.min(1, dataMax + 0.02);

  var hovertext = judges.map(function(ja) {
    return judges.map(function(jb) {
      if (ja === jb) return 'Same judge (diagonal)';
      var key = ja + '||' + jb;
      var entry = DATA.matrix[key];
      var val = (entry && entry[m] != null) ? entry[m].toFixed(4) : 'N/A';
      var cnt = (entry && entry.count) ? entry.count : 0;
      return 'Judge A (y): ' + ja + '<br>Judge B (x): ' + jb + '<br>'
           + metricLabel + ': ' + val + '<br>Shared evals: ' + cnt;
    });
  });

  Plotly.newPlot('v2-chart', [{
    type: 'heatmap', z: z, x: judges, y: judges,
    colorscale: colorscale,
    zmin: useMin, zmax: useMax,
    colorbar: { title: metricLabel, thickness: 14, len: 0.8 },
    hoverinfo: 'text', text: hovertext,
    hoverongaps: false,
  }], {
    xaxis: { title: 'Judge model (x-axis)', tickangle: judges.length > 4 ? -35 : 0, side: 'bottom' },
    yaxis: { title: 'Judge model (y-axis)', autorange: 'reversed' },
    margin: { t: 40, b: 120, l: 160, r: 80 },
    paper_bgcolor: '#fff', plot_bgcolor: '#fafbfc',
  }, { responsive: true });
  _addPlotTooltips('v2-chart');
}

function renderV3() {
  var m = getMetric();
  var dimSel = document.getElementById('v3-dim-sel');
  var dim = dimSel ? dimSel.value : 'aspect';

  var rows;
  var labelKey;
  if (dim === 'aspect') {
    rows = DATA.aspect_rows || [];
    labelKey = 'aspect';
  } else if (dim === 'teacher') {
    rows = DATA.teacher_rows || [];
    labelKey = 'teacher';
  } else if (dim === 'student') {
    rows = DATA.student_rows || [];
    labelKey = 'student';
  } else if (dim === 'task') {
    rows = DATA.task_rows || [];
    labelKey = 'task';
  } else {
    rows = []; labelKey = 'aspect';
  }

  if (!rows.length) {
    document.getElementById('v3-chart').innerHTML =
      '<p class="na" style="padding:16px">No agreement data for this dimension (requires shared evaluation units between judge pairs).</p>';
    return;
  }

  var labels = rows.map(function(r){return r[labelKey];});
  var vals   = rows.map(function(r){return r[m];});
  var palette = [
    '#6366f1','#22c55e','#f59e0b','#ef4444','#06b6d4',
    '#ec4899','#84cc16','#f97316','#8b5cf6','#14b8a6',
  ];
  var colors = labels.map(function(a, i) { return palette[i % palette.length]; });
  var metricLabel = m.toUpperCase();

  var tipMap = {};
  if (dim === 'aspect') {
    tipMap = (DATA.tips && DATA.tips.aspects) ? DATA.tips.aspects : {};
  }

  var hoverLines = labels.map(function(a, i) {
    var t = tipMap[a];
    return '<b>' + escHtml(a) + '</b>'
      + (t ? '<br><i style="font-size:.85em">' + escHtml(t.substring(0,90)) + '</i>' : '')
      + '<br>' + metricLabel + ': ' + (vals[i] != null ? vals[i].toFixed(4) : 'N/A');
  });

  // Dynamic scale
  var flat2 = vals.filter(function(v){return v!==null&&v!==undefined;});
  var dMin = flat2.length ? Math.max(0, Math.min.apply(null,flat2)-0.02) : 0;
  var dMax = flat2.length ? Math.min(1, Math.max.apply(null,flat2)+0.02) : 1;

  Plotly.newPlot('v3-chart', [{
    type: 'bar', x: labels, y: vals,
    marker: { color: colors, line: { color: 'rgba(0,0,0,.1)', width: 1 } },
    text: hoverLines, hovertemplate: '%{text}<extra></extra>',
  }], {
    yaxis: {
      title: 'Mean ' + metricLabel,
      range: [dMin, dMax + 0.05],
      gridcolor: '#f1f5f9',
    },
    xaxis: { tickangle: labels.length > 5 ? -35 : 0, automargin: true },
    margin: { t: 24, b: 100, l: 60, r: 20 },
    paper_bgcolor: '#fff', plot_bgcolor: '#fafbfc',
  }, { responsive: true });
  _addPlotTooltips('v3-chart');
}

document.addEventListener('DOMContentLoaded', renderAll);
"""
