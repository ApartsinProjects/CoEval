"""Shared HTML report infrastructure (REQ-A-7.2).

Handles:
- Plotly.js acquisition (download-once cache, REQ-A-10.3)
- Self-contained HTML report folder creation
- Common HTML template (header, filter panel, metric selector, stats bar)
"""
from __future__ import annotations

import json
import shutil
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Plotly.js management
# ---------------------------------------------------------------------------

_PLOTLY_CDN = (
    "https://cdn.plot.ly/plotly-2.35.2.min.js"
)
_PLOTLY_FILENAME = "plotly.min.js"


def _cache_dir() -> Path:
    """Return (and create) the CoEval plotly cache directory."""
    import os
    base = Path(os.environ.get('COEVAL_CACHE', Path.home() / '.cache' / 'coeval'))
    (base / 'plotly').mkdir(parents=True, exist_ok=True)
    return base / 'plotly'


def get_plotly_js(out_dir: Path) -> Path:
    """Ensure plotly.min.js is in out_dir. Download if needed (REQ-A-10.3).

    Returns the Path to the file inside out_dir.
    """
    dest = out_dir / _PLOTLY_FILENAME
    if dest.exists():
        return dest

    # Check cache first
    cached = _cache_dir() / _PLOTLY_FILENAME
    if cached.exists():
        shutil.copy2(cached, dest)
        return dest

    # Download
    print(f"Downloading Plotly.js from {_PLOTLY_CDN} ...")
    try:
        urllib.request.urlretrieve(_PLOTLY_CDN, str(cached))
        shutil.copy2(cached, dest)
        print(f"  Saved to cache: {cached}")
    except Exception as exc:
        raise RuntimeError(
            f"Failed to download Plotly.js from {_PLOTLY_CDN}: {exc}\n"
            f"To fix: manually download plotly.min.js to {cached}"
        ) from exc

    return dest


# ---------------------------------------------------------------------------
# HTML template
# ---------------------------------------------------------------------------

_HTML_TEMPLATE = """\
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
  <title>{title}</title>
  <script src="{plotly_src}"></script>
  <script>
{data_js}
  </script>
  <style>
{css}
  </style>
</head>
<body>
{header_html}
{filter_html}
<div id="main">
{views_html}
</div>
{footer_html}
<script>
{app_js}
</script>
</body>
</html>
"""

_BASE_CSS = """
* { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
       background: #f5f5f5; color: #333; }
#header { background: #1a1a2e; color: #fff; padding: 14px 20px;
          display: flex; flex-wrap: wrap; gap: 16px; align-items: center; }
#header h1 { font-size: 1.1rem; font-weight: 600; }
.header-meta { font-size: 0.78rem; opacity: 0.8; }
.header-badge { background: rgba(255,255,255,.15); border-radius: 4px;
                padding: 2px 8px; font-size: 0.75rem; }
.partial-notice { background: #f59e0b; color: #000; padding: 8px 20px;
                  font-size: 0.85rem; font-weight: 500; }
#filter-panel { background: #fff; border-bottom: 1px solid #e0e0e0;
                padding: 10px 20px; display: flex; flex-wrap: wrap; gap: 12px;
                align-items: center; }
.filter-group { display: flex; align-items: center; gap: 6px; }
.filter-group label { font-size: 0.8rem; font-weight: 500; color: #555; }
.filter-group select { font-size: 0.8rem; border: 1px solid #ccc;
                        border-radius: 4px; padding: 3px 6px; }
#stats-bar { background: #e8f4f8; padding: 6px 20px; font-size: 0.78rem;
             color: #555; border-bottom: 1px solid #c9e3ee; }
#main { padding: 16px 20px; }
.view-section { background: #fff; border-radius: 8px; box-shadow: 0 1px 3px rgba(0,0,0,.1);
                padding: 16px; margin-bottom: 16px; }
.view-section h2 { font-size: 1rem; font-weight: 600; margin-bottom: 12px; color: #1a1a2e; }
.view-section p.note { font-size: 0.8rem; color: #666; background: #fffbeb;
                       border-left: 3px solid #f59e0b; padding: 6px 10px;
                       margin-bottom: 10px; border-radius: 0 4px 4px 0; }
.chart-container { min-height: 360px; }
table.data-table { border-collapse: collapse; width: 100%; font-size: 0.82rem; }
table.data-table th { background: #f0f4f8; text-align: left;
                       padding: 6px 10px; border-bottom: 2px solid #d0d8e0;
                       font-weight: 600; color: #444; white-space: nowrap; }
table.data-table td { padding: 5px 10px; border-bottom: 1px solid #eee; }
table.data-table tr:hover td { background: #f8f9fb; }
.warn-flag { color: #d97706; font-size: 0.85em; cursor: help; }
.degenerate-notice { background: #fef3c7; border: 1px solid #fbbf24;
                     border-radius: 6px; padding: 10px 14px; margin-bottom: 12px;
                     font-size: 0.82rem; }
.na { color: #aaa; font-style: italic; }
.tag { display: inline-block; font-size: 0.7rem; border-radius: 3px;
       padding: 1px 5px; margin: 0 2px; }
.tag-partial { background: #fef3c7; color: #92400e; }
.tag-completed { background: #d1fae5; color: #065f46; }
footer { text-align: center; padding: 16px; font-size: 0.75rem; color: #999; }
"""


def build_report(
    out_dir: Path,
    title: str,
    data: dict[str, Any],
    views_html: str,
    filter_defs: list[dict],      # [{id, label, options: [(val, label), ...]}]
    stats_text: str,
    experiment_meta: dict,
    report_type: str,
    plotly_src: str = _PLOTLY_FILENAME,
    extra_css: str = '',
    extra_js: str = '',
    partial: bool = False,
) -> Path:
    """Write a self-contained HTML report to out_dir/index.html (REQ-A-7.2).

    Parameters
    ----------
    out_dir:
        Output directory.  Created if it does not exist.
    title:
        Browser window title.
    data:
        Dict serialised as ``window.DATA`` in the HTML.
    views_html:
        Inner HTML for the main content area.
    filter_defs:
        List of filter control definitions.
    stats_text:
        Plain text for the stats bar.
    experiment_meta:
        Dict with keys: id, status, ees_path, tasks, models, datapoints,
        analysis_date.
    report_type:
        Human-readable report name for header.
    plotly_src:
        Relative path to plotly.min.js.
    extra_css:
        Additional CSS appended to base styles.
    extra_js:
        Additional JavaScript appended to the app JS.
    partial:
        If True, show the partial-run notice banner.

    Returns
    -------
    Path to the written index.html.
    """
    out_dir.mkdir(parents=True, exist_ok=True)

    data_js = f'const DATA = {json.dumps(data, ensure_ascii=False)};'

    header_html = _build_header(experiment_meta, report_type, partial)
    filter_html = _build_filter_panel(filter_defs)
    footer_html = f'<footer>Generated by CoEval EEA &mdash; {experiment_meta.get("analysis_date", "")}</footer>'

    html = _HTML_TEMPLATE.format(
        title=title,
        plotly_src=plotly_src,
        data_js=data_js,
        css=_BASE_CSS + extra_css,
        header_html=header_html,
        filter_html=filter_html,
        views_html=views_html,
        footer_html=footer_html,
        app_js=_BASE_APP_JS + extra_js,
    )

    index_path = out_dir / 'index.html'
    index_path.write_text(html, encoding='utf-8')
    return index_path


def _build_header(meta: dict, report_type: str, partial: bool) -> str:
    status = meta.get('status', 'unknown')
    badge_cls = 'tag-completed' if status == 'completed' else 'tag-partial'
    partial_banner = (
        '<div class="partial-notice">⚠ This experiment is not yet complete '
        '— analysis reflects only artifacts present so far.</div>'
        if partial else ''
    )
    return f"""
{partial_banner}
<div id="header">
  <h1>CoEval EEA &mdash; {report_type}</h1>
  <span class="header-meta">Experiment: <b>{meta.get('id','?')}</b></span>
  <span class="header-badge {badge_cls}">{status}</span>
  <span class="header-meta">Tasks: {meta.get('tasks','?')}</span>
  <span class="header-meta">Models: {meta.get('models','?')}</span>
  <span class="header-meta">Datapoints: {meta.get('datapoints','?')}</span>
  <span class="header-meta">Self-judging: {meta.get('self_judging',0)}</span>
  <span class="header-meta">Self-teaching: {meta.get('self_teaching',0)}</span>
  <span class="header-meta">Analyzed: {meta.get('analysis_date','?')}</span>
</div>
<div id="stats-bar">{meta.get('stats','')}</div>"""


def _build_filter_panel(filter_defs: list[dict]) -> str:
    if not filter_defs:
        return ''
    parts = ['<div id="filter-panel">']
    for fd in filter_defs:
        fid = fd['id']
        label = fd['label']
        options = fd.get('options', [])
        opts_html = '<option value="__all__">All</option>' + ''.join(
            f'<option value="{v}">{lbl}</option>'
            for v, lbl in options
        )
        parts.append(
            f'<div class="filter-group">'
            f'<label for="flt_{fid}">{label}:</label>'
            f'<select id="flt_{fid}" onchange="applyFilters()">{opts_html}</select>'
            f'</div>'
        )
    parts.append('</div>')
    return '\n'.join(parts)


# Minimal shared client-side JS skeleton
_BASE_APP_JS = """
function getFilter(id) {
  var el = document.getElementById('flt_' + id);
  return el ? el.value : '__all__';
}

function applyFilters() {
  if (typeof renderAll === 'function') renderAll();
}

function fmt(v, decimals) {
  if (v === null || v === undefined) return '<span class="na">N/A</span>';
  return parseFloat(v).toFixed(decimals !== undefined ? decimals : 3);
}

function fmtPct(v) {
  if (v === null || v === undefined) return '<span class="na">N/A</span>';
  return (parseFloat(v) * 100).toFixed(1) + '%';
}

function selfFlag(is_self_judging, is_self_teaching) {
  var flags = [];
  if (is_self_judging) flags.push('<span class="warn-flag" title="Self-evaluation: judge model = student model.">⚠SJ</span>');
  if (is_self_teaching) flags.push('<span class="warn-flag" title="Self-teaching: teacher model = student model.">⚠ST</span>');
  return flags.join(' ');
}

// Colour helpers
function scoreColor(v) {
  if (v === null || v === undefined) return '#eee';
  var r = Math.round(255 * (1 - v));
  var g = Math.round(200 * v);
  return 'rgb(' + r + ',' + g + ',60)';
}
"""


# ---------------------------------------------------------------------------
# Shared helper: experiment meta dict from EESDataModel
# ---------------------------------------------------------------------------

def make_experiment_meta(model: 'EESDataModel') -> dict:
    from ..loader import EESDataModel
    exp_id = model.meta.get('experiment_id', model.run_path.name)
    status = model.meta.get('status', 'unknown')
    tasks_count = len(model.tasks)
    models_count = len(set(model.teachers + model.students + model.judges))
    dp_count = len(model.datapoints)
    return {
        'id': exp_id,
        'status': status,
        'ees_path': str(model.run_path),
        'tasks': tasks_count,
        'models': models_count,
        'datapoints': dp_count,
        'analysis_date': datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
        'self_judging': model.self_judging_count,
        'self_teaching': model.self_teaching_count,
        'stats': (
            f"Total eval records: {model.total_records} | "
            f"Valid: {model.valid_records} | "
            f"Invalid: {model.total_records - model.valid_records}"
        ),
    }
