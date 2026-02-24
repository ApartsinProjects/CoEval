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
</div>
<div class="view-section">
  <h2>View 2 — Pairwise Agreement Matrix</h2>
  <div id="v2-chart" class="chart-container"></div>
</div>
<div class="view-section">
  <h2>View 3 — Per-Aspect Agreement</h2>
  <div id="v3-chart" class="chart-container"></div>
</div>
<div class="view-section">
  <h2>View 4 — Score Distribution per Judge</h2>
  <div id="v4-chart" class="chart-container"></div>
</div>
"""

_APP_JS = """
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
  Plotly.newPlot('v2-chart', [{
    type: 'heatmap', z: z, x: judges, y: judges,
    colorscale: m === 'kappa'
      ? [[0,'#e74c3c'],[0.5,'#f7f7f7'],[1,'#27ae60']]
      : [[0,'#e74c3c'],[0.5,'#f7f7f7'],[1,'#27ae60']],
    zmin: m === 'kappa' ? -1 : 0, zmax: 1,
    hovertemplate: 'Ja: %{y}<br>Jb: %{x}<br>Value: %{z}<extra></extra>',
  }], {margin:{t:20}});
}

function renderV3() {
  var m = getMetric();
  var rows = DATA.aspect_rows;
  if (!rows.length) return;
  var aspects = rows.map(function(r){return r.aspect;});
  var vals = rows.map(function(r){return r[m];});
  Plotly.newPlot('v3-chart', [{
    type:'bar', x: aspects, y: vals, marker:{color:'#8e44ad'},
  }], {yaxis:{title:'Mean ' + m.toUpperCase() + ' across judge pairs', range:[0,1]},
       margin:{t:20}});
}

function renderV4() {
  var hist = DATA.judge_score_hist;
  var judges = Object.keys(hist);
  var traces = judges.map(function(j) {
    return {type:'histogram', name:j, x:hist[j], xbins:{start:0,end:1.01,size:0.1},
            opacity:0.7};
  });
  Plotly.newPlot('v4-chart', traces,
    {barmode:'overlay', xaxis:{title:'Score value'},
     yaxis:{title:'Count'}, margin:{t:20}});
}

document.addEventListener('DOMContentLoaded', renderAll);
"""
