"""Judge Consistency View — REQ-A-7.8."""
from __future__ import annotations

from collections import defaultdict
from pathlib import Path

from ..loader import EESDataModel
from .html_base import build_report, get_plotly_js, make_experiment_meta


def write_judge_consistency(
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
        {'id': 'student', 'label': 'Student', 'options': [(s, s) for s in model.students]},
        {'id': 'aspect', 'label': 'Aspect',
         'options': [(a, a) for a in sorted(set(u.rubric_aspect for u in model.units))]},
    ]

    return build_report(
        out_dir=out_dir,
        title=f'Judge Consistency — {exp_meta["id"]}',
        data=data,
        views_html=_VIEWS_HTML,
        filter_defs=filter_defs,
        stats_text=exp_meta['stats'],
        experiment_meta=exp_meta,
        report_type='Judge Consistency View',
        extra_js=_APP_JS,
        partial=model.is_partial,
    )


def _build_data(model: EESDataModel) -> dict:
    units = model.units
    judges = model.judges

    # View 1: within-judge score variance by target attribute
    # IntraVar(j, attr=v, A) = sample_variance of scores for that (j, attr, aspect)
    judge_attr_asp: dict[tuple, list] = defaultdict(list)
    for u in units:
        dp = model.datapoints.get(u.datapoint_id, {})
        for k, v in dp.get('sampled_target_attributes', {}).items():
            judge_attr_asp[(u.judge_model_id, f'{k}={v}', u.rubric_aspect)].append(u.score_norm)

    all_attr_vals = sorted({k.split('=', 1)[1] if '=' in k else k
                             for (j, k, a) in judge_attr_asp for _ in [0]
                             if True}
                            | {k for (j, k, a) in judge_attr_asp})
    # Simpler: collect attr keys
    attr_keys: set[str] = set()
    for (j, k, a) in judge_attr_asp:
        attr_keys.add(k)
    attr_labels = sorted(attr_keys)

    # variance per (judge, attr_key) averaged over aspects
    judge_attr_var: dict[str, dict] = {}
    for j in judges:
        judge_attr_var[j] = {}
        for k in attr_labels:
            aspect_vars = []
            for u_asp in sorted(set(a for (jj, kk, a) in judge_attr_asp if jj == j and kk == k)):
                vals = judge_attr_asp.get((j, k, u_asp), [])
                if len(vals) >= 2:
                    mean = sum(vals)/len(vals)
                    var = sum((x-mean)**2 for x in vals)/(len(vals)-1)
                    aspect_vars.append(var)
            judge_attr_var[j][k] = round(sum(aspect_vars)/len(aspect_vars), 4) if aspect_vars else 0.0

    # View 2: score distribution per judge, per attr key → box data
    judge_attr_box: dict[str, dict] = {}
    for j in judges:
        judge_attr_box[j] = {}
        for k in attr_labels:
            vals = []
            for (jj, kk, a), v in judge_attr_asp.items():
                if jj == j and kk == k:
                    vals.extend(v)
            judge_attr_box[j][k] = vals

    # View 4: score calibration table
    calibration: list[dict] = []
    for j in judges:
        j_units = [u for u in units if u.judge_model_id == j]
        aspects = sorted(set(u.rubric_aspect for u in j_units))
        for asp in aspects:
            a_units = [u for u in j_units if u.rubric_aspect == asp]
            n = len(a_units)
            if n == 0:
                continue
            scores = [u.score_norm for u in a_units]
            mean = sum(scores)/n
            std = (sum((x-mean)**2 for x in scores)/(n-1))**0.5 if n > 1 else 0.0
            h = sum(1 for u in a_units if u.score == 'High')
            m = sum(1 for u in a_units if u.score == 'Medium')
            l = sum(1 for u in a_units if u.score == 'Low')
            most_common = max(('High', h), ('Medium', m), ('Low', l), key=lambda x: x[1])[0]
            flag_calibration = (h/n > 0.9) or (l/n > 0.9)
            calibration.append({
                'judge': j, 'aspect': asp,
                'mean': round(mean, 4), 'std': round(std, 4),
                'pct_high': round(h/n*100, 1),
                'pct_medium': round(m/n*100, 1),
                'pct_low': round(l/n*100, 1),
                'most_common': most_common,
                'flag': flag_calibration,
                'n': n,
            })

    return {
        'judges': judges,
        'attr_labels': attr_labels,
        'judge_attr_var': judge_attr_var,
        'judge_attr_box': judge_attr_box,
        'calibration': calibration,
    }


_VIEWS_HTML = """
<div class="view-section">
  <h2>View 1 — Within-Judge Score Variance by Target Attribute (Heatmap)</h2>
  <div id="v1-chart" class="chart-container"></div>
</div>
<div class="view-section">
  <h2>View 2 — Judge Score Distribution by Target Attribute (Box Plots)</h2>
  <select id="v2-judge" onchange="renderV2()" style="margin-bottom:8px;font-size:0.8rem"></select>
  <div id="v2-chart" class="chart-container"></div>
</div>
<div class="view-section">
  <h2>View 4 — Score Calibration Table</h2>
  <div id="v4-table"></div>
</div>
"""

_APP_JS = """
function renderAll() {
  var sel = document.getElementById('v2-judge');
  DATA.judges.forEach(function(j) {
    var o = document.createElement('option'); o.value = j; o.textContent = j;
    sel.appendChild(o);
  });
  renderV1(); renderV2(); renderV4();
}

function renderV1() {
  var judges = DATA.judges;
  var attrs = DATA.attr_labels;
  if (!judges.length || !attrs.length) return;
  var z = judges.map(function(j) {
    return attrs.map(function(k) {
      var v = DATA.judge_attr_var[j];
      return v ? (v[k] !== undefined ? v[k] : null) : null;
    });
  });
  Plotly.newPlot('v1-chart', [{
    type:'heatmap', z:z, x:attrs, y:judges,
    colorscale:[[0,'#f0f8ff'],[1,'#1a4fac']],
    zmin:0, zmax:0.25,
  }], {title:'Within-judge variance (higher = less consistent)', margin:{t:40}});
}

function renderV2() {
  var j = document.getElementById('v2-judge').value;
  if (!j) return;
  var boxData = DATA.judge_attr_box[j] || {};
  var keys = Object.keys(boxData).sort();
  var traces = keys.map(function(k) {
    return {type:'box', name:k, y:boxData[k], boxpoints:'outliers'};
  });
  if (!traces.length) return;
  Plotly.newPlot('v2-chart', traces,
    {yaxis:{title:'Score', range:[-.05,1.05]}, margin:{t:20}});
}

function renderV4() {
  var rows = DATA.calibration;
  var html = '<table class="data-table"><tr><th>Judge</th><th>Aspect</th>';
  html += '<th>Mean</th><th>Std Dev</th><th>% High</th><th>% Medium</th><th>% Low</th>';
  html += '<th>Most Common</th><th>N</th></tr>';
  rows.forEach(function(r) {
    var style = r.flag ? 'background:#fff3cd' : '';
    html += '<tr style="' + style + '">';
    html += '<td>' + r.judge + '</td><td>' + r.aspect + '</td>';
    html += '<td>' + fmt(r.mean) + '</td><td>' + fmt(r.std) + '</td>';
    html += '<td>' + r.pct_high + '%</td><td>' + r.pct_medium + '%</td>';
    html += '<td>' + r.pct_low + '%</td><td>' + r.most_common + '</td>';
    html += '<td>' + r.n + '</td></tr>';
  });
  document.getElementById('v4-table').innerHTML = html + '</table>';
}

document.addEventListener('DOMContentLoaded', renderAll);
"""
