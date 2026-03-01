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
from .html_base import build_report, get_plotly_js, make_experiment_meta

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
            continue  # deduplicate
        # per-aspect breakdown
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

    # Agreement distribution histogram data (View 4)
    judge_score_hist: dict[str, list] = {}
    for j in judges:
        vals = [u.score_norm for u in units if u.judge_model_id == j]
        judge_score_hist[j] = vals

    return {
        'judges': judges,
        'single_judge': single,
        'single_judge_notice': _SINGLE_JUDGE_NOTICE if single else '',
        'ranking': ranking_rows,
        'matrix': matrix,
        'aspect_rows': aspect_rows,
        'judge_score_hist': judge_score_hist,
    }


def _wpa_weight(a: str, b: str) -> float:
    table = {
        ('High', 'High'): 1.0, ('High', 'Medium'): 0.5, ('High', 'Low'): 0.0,
        ('Medium', 'High'): 0.5, ('Medium', 'Medium'): 1.0, ('Medium', 'Low'): 0.5,
        ('Low', 'High'): 0.0, ('Low', 'Medium'): 0.5, ('Low', 'Low'): 1.0,
    }
    return table.get((a, b), 0.0)


_VIEWS_HTML = """
<div id="degenerate-notice" class="degenerate-notice" style="display:none"></div>
<div class="view-section">
  <h2>View 1 — Judge Ranking</h2>
  <div id="v1-table"></div>
  <details class="fig-explain">
    <summary>About this table</summary>
    <div class="explain-body">
      <b>What it shows:</b> Each row is a judge model. Columns report inter-judge agreement
      scores averaged across all rubric aspects and all task–teacher–student combinations
      in the current filter.<br>
      <b>SPA</b> (Simple Percent Agreement) = fraction of pairwise evaluation pairs where
      both judges assigned the same score level. Range 0–1; higher is better.<br>
      <b>WPA</b> (Weighted Percent Agreement) = SPA weighted by the number of evaluation
      units — larger combinations contribute proportionally more.<br>
      <b>κ (Kappa)</b> = Cohen's κ; corrects for chance agreement. Interpretation:
      &lt; 0 = worse than chance; 0–0.2 = slight; 0.2–0.4 = fair; 0.4–0.6 = moderate;
      0.6–0.8 = substantial; &gt; 0.8 = near-perfect.<br>
      <b>⚠SJ</b> flags self-judging (judge = student). <b>⚠ST</b> flags self-teaching.
    </div>
  </details>
</div>
<div class="view-section">
  <h2>View 2 — Pairwise Agreement Matrix</h2>
  <div id="v2-chart" class="chart-container"></div>
  <details class="fig-explain">
    <summary>About this figure</summary>
    <div class="explain-body">
      <b>What it shows:</b> A symmetric heatmap where each cell (i, j) shows the
      agreement between judge <em>i</em> and judge <em>j</em> on the same evaluation units.
      The diagonal is always 1.0 (a judge agrees with itself).<br>
      <b>How to read it:</b> High off-diagonal values (green) indicate that two judges
      produce consistent scores. Low values (red) suggest one judge is systematically
      more lenient or strict than another, or that the judges apply the rubric differently.
      Use the Agreement metric filter (SPA / WPA / Kappa) to switch the measure shown.
    </div>
  </details>
</div>
<div class="view-section">
  <h2>View 3 — Per-Aspect Agreement</h2>
  <div id="v3-chart" class="chart-container"></div>
  <details class="fig-explain">
    <summary>About this figure</summary>
    <div class="explain-body">
      <b>What it shows:</b> Mean inter-judge agreement broken down by rubric aspect.
      Each bar represents one aspect; bar height = average agreement across all judge pairs
      for that aspect.<br>
      <b>How to read it:</b> Low agreement on a specific aspect means judges interpret
      that criterion inconsistently — the rubric description for that aspect may need
      clarification. High-variance aspects are less reliable for comparing student models.
    </div>
  </details>
</div>
<div class="view-section">
  <h2>View 4 — Score Distribution per Judge</h2>
  <div id="v4-chart" class="chart-container"></div>
  <details class="fig-explain">
    <summary>About this figure</summary>
    <div class="explain-body">
      <b>What it shows:</b> A grouped bar chart of the fraction of High / Medium / Low
      scores awarded by each judge model across all evaluated responses.<br>
      <b>How to read it:</b> A judge that gives mostly High scores is lenient; one that
      gives mostly Low scores is strict. Large differences between judges indicate scoring
      bias. When using multiple judges, CoEval metrics are computed per-judge to avoid
      conflating genuine performance differences with judge calibration differences.
    </div>
  </details>
</div>
"""

_APP_JS = """
function escHtml(s) {
  return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}
function getMetric() { return getFilter('metric') || 'spa'; }

function renderAll() {
  if (DATA.single_judge && DATA.single_judge_notice) {
    var el = document.getElementById('degenerate-notice');
    el.style.display = 'block';
    el.textContent = DATA.single_judge_notice;
  }
  renderV1();
  renderV2();
  renderV3();
  renderV4();
}

function renderV1() {
  var m = getMetric();
  var rows = DATA.ranking.slice().sort(function(a,b){ return (b[m]||0)-(a[m]||0); });
  var html = '<table class="data-table">';
  html += '<tr><th>Judge</th><th>SPA</th><th>WPA</th><th>κ</th><th>κ label</th>';
  html += '<th>Coverage-Weighted</th><th>Valid Evals</th></tr>';
  rows.forEach(function(r) {
    var flag = r.is_also_student
      ? '<span class="warn-flag" title="This judge also acts as a student.">⚠</span>' : '';
    html += '<tr><td>' + r.judge + flag + '</td>';
    html += '<td>' + fmt(r.spa) + '</td><td>' + fmt(r.wpa) + '</td>';
    html += '<td>' + fmt(r.kappa) + '</td><td>' + r.kappa_label + '</td>';
    var w = m === 'spa' ? r.spa_w : m === 'wpa' ? r.wpa_w : r.kappa_w;
    html += '<td>' + fmt(w) + '</td><td>' + r.valid_evals + '</td></tr>';
  });
  html += '</table>';
  document.getElementById('v1-table').innerHTML = html;
}

function renderV2() {
  var m = getMetric();
  var judges = DATA.judges;
  if (judges.length < 2) {
    document.getElementById('v2-chart').innerHTML =
      '<p class="na" style="padding:16px">Need ≥2 judges for agreement matrix.</p>';
    return;
  }
  var z = judges.map(function(ja) {
    return judges.map(function(jb) {
      if (ja === jb) return null;
      var key = ja + '||' + jb;
      var entry = DATA.matrix[key];
      return entry ? entry[m] : null;
    });
  });
  var metricLabel = m.toUpperCase();
  var zmin = m === 'kappa' ? -1 : 0;
  var colorscale = m === 'kappa'
    ? [[0,'#dc2626'],[0.25,'#f97316'],[0.5,'#f3f4f6'],[0.75,'#4ade80'],[1,'#16a34a']]
    : [[0,'#dc2626'],[0.33,'#fb923c'],[0.5,'#fbbf24'],[0.67,'#84cc16'],[1,'#16a34a']];
  Plotly.newPlot('v2-chart', [{
    type: 'heatmap', z: z, x: judges, y: judges,
    colorscale: colorscale,
    zmin: zmin, zmax: 1,
    colorbar: { title: metricLabel, thickness: 14, len: 0.8 },
    hovertemplate: 'Judge A: %{y}<br>Judge B: %{x}<br>' + metricLabel + ': %{z:.3f}<extra></extra>',
  }], {
    xaxis: { tickangle: judges.length > 4 ? -35 : 0, side: 'bottom' },
    yaxis: { autorange: 'reversed' },
    margin: { t: 40, b: 100, l: 100, r: 60 },
    paper_bgcolor: '#fff', plot_bgcolor: '#fafbfc',
  }, { responsive: true });
}

function renderV3() {
  var m = getMetric();
  var rows = DATA.aspect_rows;
  if (!rows.length) return;
  var aspects = rows.map(function(r){return r.aspect;});
  var vals    = rows.map(function(r){return r[m];});
  var palette = [
    '#6366f1','#22c55e','#f59e0b','#ef4444','#06b6d4',
    '#ec4899','#84cc16','#f97316','#8b5cf6','#14b8a6',
  ];
  var colors = aspects.map(function(a, i) { return palette[i % palette.length]; });
  var metricLabel = m.toUpperCase();
  var tipMap = DATA.tips && DATA.tips.aspects ? DATA.tips.aspects : {};
  var hoverLines = aspects.map(function(a, i) {
    var t = tipMap[a];
    return '<b>' + escHtml(a) + '</b>'
      + (t ? '<br><i style="font-size:.85em">' + escHtml(t.substring(0,90)) + '</i>' : '')
      + '<br>' + metricLabel + ': ' + (vals[i] != null ? vals[i].toFixed(4) : 'N/A');
  });
  Plotly.newPlot('v3-chart', [{
    type: 'bar', x: aspects, y: vals,
    marker: { color: colors, line: { color: 'rgba(0,0,0,.1)', width: 1 } },
    text: hoverLines, hovertemplate: '%{text}<extra></extra>',
  }], {
    yaxis: {
      title: 'Mean ' + metricLabel + ' (0–1)', range: [0, 1.05], gridcolor: '#f1f5f9',
    },
    xaxis: { tickangle: aspects.length > 5 ? -35 : 0, automargin: true },
    margin: { t: 24, b: 100, l: 60, r: 20 },
    paper_bgcolor: '#fff', plot_bgcolor: '#fafbfc',
  }, { responsive: true });
}

function renderV4() {
  var hist = DATA.judge_score_hist;
  var judges = Object.keys(hist);
  if (!judges.length) return;
  var palette = [
    '#3b82f6','#22c55e','#f59e0b','#ef4444','#8b5cf6',
    '#06b6d4','#ec4899','#84cc16','#f97316','#14b8a6',
  ];
  var traces = judges.map(function(j, ji) {
    var col = palette[ji % palette.length];
    return {
      type: 'histogram', name: j, x: hist[j],
      xbins: { start: 0, end: 1.01, size: 0.1 },
      opacity: 0.72,
      marker: { color: col, line: { color: col, width: 1 } },
      hovertemplate: 'Judge: ' + escHtml(j) + '<br>Score bin: %{x}<br>Count: %{y}<extra></extra>',
    };
  });
  Plotly.newPlot('v4-chart', traces, {
    barmode: 'overlay',
    xaxis: { title: 'Normalised score value (0=Low, 0.5=Medium, 1=High)', dtick: 0.1 },
    yaxis: { title: 'Count', gridcolor: '#f1f5f9' },
    legend: { orientation: 'h', y: -0.25, x: 0.5, xanchor: 'center', font: { size: 11 } },
    margin: { t: 24, b: 110, l: 60, r: 20 },
    paper_bgcolor: '#fff', plot_bgcolor: '#fafbfc',
  }, { responsive: true });
}

document.addEventListener('DOMContentLoaded', renderAll);
"""
