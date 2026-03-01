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
html { scroll-behavior: smooth; }
body {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Inter', sans-serif;
  background: #f0f4f8; color: #1e293b; font-size: 14px; line-height: 1.5;
}
/* ---- Header ---- */
#header {
  background: linear-gradient(135deg, #0f172a 0%, #1e3a5f 60%, #1e40af 100%);
  color: #fff; padding: 14px 24px;
  display: flex; flex-wrap: wrap; gap: 14px; align-items: center;
  box-shadow: 0 2px 8px rgba(0,0,0,.35);
}
#header h1 { font-size: 1.05rem; font-weight: 700; letter-spacing: 0.01em; }
#header h1 .report-type { opacity: 0.75; font-weight: 400; }
.header-meta { font-size: 0.76rem; opacity: 0.78; }
.header-badge {
  background: rgba(255,255,255,.18); border: 1px solid rgba(255,255,255,.25);
  border-radius: 12px; padding: 2px 10px; font-size: 0.72rem; font-weight: 600;
}
.header-badge.tag-completed { background: rgba(34,197,94,.25); border-color: rgba(34,197,94,.4); }
.header-badge.tag-partial   { background: rgba(245,158,11,.25); border-color: rgba(245,158,11,.4); }
.partial-notice {
  background: linear-gradient(90deg, #f59e0b, #fbbf24);
  color: #1c1917; padding: 7px 24px; font-size: 0.82rem; font-weight: 600;
  border-bottom: 2px solid #d97706;
}
/* ---- Filter Panel ---- */
#filter-panel {
  background: #fff; border-bottom: 1px solid #dde3ed;
  padding: 9px 24px; display: flex; flex-wrap: wrap; gap: 14px;
  align-items: center; box-shadow: 0 1px 3px rgba(0,0,0,.06);
  position: sticky; top: 0; z-index: 100;
}
.filter-group { display: flex; align-items: center; gap: 7px; }
.filter-group label {
  font-size: 0.76rem; font-weight: 600; color: #475569;
  text-transform: uppercase; letter-spacing: 0.04em;
}
.filter-group select {
  font-size: 0.8rem; border: 1px solid #cbd5e1; border-radius: 6px;
  padding: 4px 8px; background: #f8fafc; cursor: pointer; color: #1e293b;
  transition: border-color .15s;
}
.filter-group select:focus { outline: none; border-color: #3b82f6; }
/* ---- Stats Bar ---- */
#stats-bar {
  background: linear-gradient(90deg, #dbeafe 0%, #e0f2fe 100%);
  padding: 6px 24px; font-size: 0.77rem; color: #1e40af;
  border-bottom: 1px solid #bfdbfe; letter-spacing: 0.01em;
}
/* ---- Main Content ---- */
#main { padding: 18px 24px; max-width: 1400px; margin: 0 auto; }
.view-section {
  background: #fff; border-radius: 12px;
  box-shadow: 0 2px 6px rgba(15,23,42,.08), 0 0 0 1px rgba(15,23,42,.04);
  padding: 20px 22px; margin-bottom: 20px;
  border-top: 3px solid transparent;
}
.view-section:hover { border-top-color: #3b82f6; }
.view-section h2 {
  font-size: 1rem; font-weight: 700; margin-bottom: 14px; color: #0f172a;
  display: flex; align-items: center; gap: 8px;
}
.view-section h2::before {
  content: ''; display: inline-block; width: 4px; height: 18px;
  background: linear-gradient(180deg, #3b82f6, #6366f1);
  border-radius: 2px; flex-shrink: 0;
}
.view-section p.note {
  font-size: 0.8rem; color: #78350f; background: #fffbeb;
  border-left: 4px solid #f59e0b; padding: 8px 12px;
  margin-bottom: 12px; border-radius: 0 6px 6px 0;
}
.chart-container { min-height: 360px; }
/* ---- Data Tables ---- */
table.data-table { border-collapse: collapse; width: 100%; font-size: 0.81rem; }
table.data-table th {
  background: linear-gradient(180deg, #f1f5f9 0%, #e9eef4 100%);
  text-align: left; padding: 8px 12px;
  border-bottom: 2px solid #cbd5e1; border-top: 1px solid #e2e8f0;
  font-weight: 700; color: #334155; white-space: nowrap;
  font-size: 0.78rem; text-transform: uppercase; letter-spacing: 0.04em;
}
table.data-table td { padding: 6px 12px; border-bottom: 1px solid #f1f5f9; color: #334155; }
table.data-table tbody tr:nth-child(odd) td  { background: #fafbfc; }
table.data-table tbody tr:nth-child(even) td { background: #fff; }
table.data-table tr:hover td { background: #eff6ff !important; }
/* ---- Utility classes ---- */
.warn-flag { color: #d97706; font-size: 0.85em; cursor: help; margin-left: 3px; }
.degenerate-notice {
  background: linear-gradient(90deg, #fef9c3, #fef3c7);
  border: 1px solid #fcd34d; border-radius: 8px;
  padding: 11px 16px; margin-bottom: 14px; font-size: 0.82rem; color: #78350f;
}
.na { color: #94a3b8; font-style: italic; }
.tag { display: inline-block; font-size: 0.7rem; border-radius: 12px;
       padding: 2px 8px; margin: 0 2px; font-weight: 600; }
.tag-partial   { background: #fef3c7; color: #92400e; border: 1px solid #fde68a; }
.tag-completed { background: #d1fae5; color: #065f46; border: 1px solid #a7f3d0; }
footer {
  text-align: center; padding: 20px; font-size: 0.74rem; color: #94a3b8;
  border-top: 1px solid #e2e8f0; margin-top: 8px;
  background: linear-gradient(180deg, #f8fafc, #f0f4f8);
}
/* ---- Collapsible figure explanations ---- */
details.fig-explain {
  margin-top: 14px; border-top: 1px dashed #e2e8f0; padding-top: 10px;
}
details.fig-explain summary {
  font-size: 0.75rem; color: #64748b; cursor: pointer; user-select: none;
  display: inline-flex; align-items: center; gap: 6px; outline: none;
  list-style: none; padding: 4px 8px; border-radius: 6px;
  transition: background .12s, color .12s;
}
details.fig-explain summary::-webkit-details-marker { display: none; }
details.fig-explain summary::before {
  content: "ℹ"; color: #94a3b8; font-size: 0.85rem;
}
details.fig-explain summary:hover {
  background: #f1f5f9; color: #1e40af;
}
details.fig-explain[open] summary { color: #1e40af; background: #eff6ff; }
details.fig-explain[open] summary::before { content: "ℹ"; color: #3b82f6; }
details.fig-explain .explain-body {
  font-size: 0.79rem; color: #475569; line-height: 1.7; margin-top: 10px;
  padding: 12px 16px; background: #f8fafc; border-radius: 8px;
  border-left: 4px solid #3b82f6;
}
details.fig-explain .explain-body b { color: #1e293b; }
details.fig-explain .explain-body code {
  background: #e2e8f0; padding: 1px 5px; border-radius: 4px;
  font-size: 0.84em; font-family: 'SF Mono', 'Fira Code', monospace;
}
/* ---- Inline definition tooltips ---- */
[data-tip] {
  border-bottom: 1px dashed #93c5fd; cursor: help; position: relative;
  text-decoration-skip-ink: none;
}
[data-tip]::after {
  content: attr(data-tip);
  position: absolute; bottom: 130%; left: 50%; transform: translateX(-50%);
  white-space: normal; max-width: 320px; min-width: 160px;
  background: #0f172a; color: #e2e8f0;
  font-size: 0.72rem; font-weight: 400; line-height: 1.55;
  padding: 8px 12px; border-radius: 8px;
  box-shadow: 0 8px 24px rgba(0,0,0,.4), 0 0 0 1px rgba(99,102,241,.3);
  z-index: 9999; opacity: 0; pointer-events: none;
  transition: opacity .18s ease;
}
[data-tip]:hover::after { opacity: 1; }
"""


def collect_tooltip_data(model: Any) -> dict:
    """Extract task descriptions, rubric definitions and attribute definitions
    for use as hover tooltips in all report views.

    Returns a dict with:
      - 'tasks':   {task_id: description_str}
      - 'aspects': {aspect_name: description_str}  (merged across tasks)
      - 'attrs':   {'{key}={val}': 'key: one of [...]'}
    """
    tips: dict = {'tasks': {}, 'aspects': {}, 'attrs': {}}

    # Task descriptions from config
    for t_cfg in model.config.get('tasks', []):
        name = t_cfg.get('name', '')
        if name:
            desc = t_cfg.get('description', '')
            if desc:
                tips['tasks'][name] = desc

    # Rubric aspect descriptions (merged across all tasks)
    for _task_id, rubric in (model.rubrics or {}).items():
        for aspect, desc in rubric.items():
            if desc and aspect not in tips['aspects']:
                tips['aspects'][aspect] = desc

    # Target attribute value descriptions
    for _task_id, attrs in (model.target_attrs_by_task or {}).items():
        for k, vals in attrs.items():
            vals_str = ', '.join(str(v) for v in vals)
            for v in vals:
                key = f'{k}={v}'
                if key not in tips['attrs']:
                    tips['attrs'][key] = f'{k}: one of [{vals_str}]'

    return tips


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
    self_judging  = meta.get('self_judging', 0)
    self_teaching = meta.get('self_teaching', 0)
    sj_notice = (
        f' <span class="header-badge" title="Self-judging evaluations detected">'
        f'⚠ {self_judging} self-judging</span>'
    ) if self_judging else ''
    st_notice = (
        f' <span class="header-badge" title="Self-teaching evaluations detected">'
        f'⚠ {self_teaching} self-teaching</span>'
    ) if self_teaching else ''
    return f"""
{partial_banner}
<div id="header">
  <h1>CoEval EEA &nbsp;·&nbsp; <span class="report-type">{report_type}</span></h1>
  <span class="header-meta">Experiment:&nbsp;<b>{meta.get('id','?')}</b></span>
  <span class="header-badge {badge_cls}">{status}</span>
  <span class="header-meta">Tasks:&nbsp;{meta.get('tasks','?')}</span>
  <span class="header-meta">Models:&nbsp;{meta.get('models','?')}</span>
  <span class="header-meta">Datapoints:&nbsp;{meta.get('datapoints','?')}</span>
  {sj_notice}{st_notice}
  <span class="header-meta" style="margin-left:auto;opacity:.6">Analyzed:&nbsp;{meta.get('analysis_date','?')}</span>
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
