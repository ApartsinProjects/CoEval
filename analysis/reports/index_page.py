"""Analysis Portal Index Page — generates a directory index.html for all reports."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from ..loader import EESDataModel
from .html_base import make_experiment_meta

# Report registry: (folder_name, display_name, description, color)
REPORTS = [
    (
        'coverage_summary',
        'Coverage Summary',
        'Phase-level coverage and evaluation record counts. Shows what fraction of the pipeline completed successfully.',
        '#2980b9',
    ),
    (
        'score_distribution',
        'Score Distribution',
        'Distribution of rubric scores across all models, tasks, and aspects. Histograms and box plots.',
        '#27ae60',
    ),
    (
        'teacher_report',
        'Teacher Report',
        'Teacher effectiveness scores (V1/S2/R3 formulas). Measures how well each teacher\u2019s datapoints discriminate between student abilities.',
        '#e67e22',
    ),
    (
        'judge_report',
        'Judge Report',
        'Inter-judge agreement (SPA/WPA/\u03ba). Shows how consistently each judge aligns with the majority scoring pattern.',
        '#8e44ad',
    ),
    (
        'student_report',
        'Student Report',
        'Student rankings by rubric score averaged across all teachers and judges. Task-level and aspect-level breakdowns.',
        '#16a085',
    ),
    (
        'interaction_matrix',
        'Interaction Matrix',
        'Pairwise teacher\u2013student interaction heat-map. Reveals which teacher\u2013student combinations produced the best outcomes.',
        '#c0392b',
    ),
    (
        'judge_consistency',
        'Judge Consistency',
        'Within-judge score variance across rubric aspects and attribute slices. Diagnoses degenerate or noisy judges.',
        '#d35400',
    ),
    (
        'summary',
        'Interactive Dashboard',
        'Comprehensive teacher/judge/student effectiveness dashboard with live threshold controls, sortable tables, and multiple views.',
        '#2c3e50',
    ),
]

# One icon per report (positional, matching REPORTS order)
_ICONS = [
    '\U0001f4ca',  # coverage_summary       — bar chart
    '\U0001f4c8',  # score_distribution     — chart increasing
    '\U0001f9d1\u200d\U0001f3eb',  # teacher_report — teacher
    '\u2696\ufe0f',  # judge_report          — scales
    '\U0001f393',  # student_report         — graduation cap
    '\U0001f525',  # interaction_matrix     — fire / heatmap
    '\U0001f50d',  # judge_consistency      — magnifying glass
    '\U0001f4ca',  # summary               — bar chart
]


def write_index_page(
    model: EESDataModel,
    out_dir: Path,
    shared_plotly: Path | None = None,
) -> Path:
    """Generate portal index.html in out_dir."""
    out_dir.mkdir(parents=True, exist_ok=True)
    exp_meta = make_experiment_meta(model)

    # Determine which report subdirs actually exist (link even if missing; grey them)
    existing = {r[0] for r in REPORTS if (out_dir / r[0] / 'index.html').exists()}

    now_str = datetime.now(tz=timezone.utc).strftime('%Y-%m-%d %H:%M UTC')

    cards_html = _build_cards(existing, out_dir)
    meta_html = _build_meta_bar(exp_meta, model)
    html = _PAGE_TEMPLATE.format(
        exp_id=exp_meta['id'],
        meta_bar=meta_html,
        cards=cards_html,
        generated=now_str,
    )

    out_path = out_dir / 'index.html'
    out_path.write_text(html, encoding='utf-8')
    return out_path


def _build_meta_bar(exp_meta: dict, model: EESDataModel) -> str:
    status = exp_meta.get('status', 'unknown')
    status_color = '#27ae60' if status == 'complete' else '#e67e22'
    stats = exp_meta.get('stats', '')
    return (
        f'<span class="meta-chip">'
        f'<b>Experiment:</b> {exp_meta["id"]}'
        f'</span>'
        f'<span class="meta-chip" style="border-color:{status_color};color:{status_color}">'
        f'<b>Status:</b> {status}'
        f'</span>'
        f'<span class="meta-chip">'
        f'{stats}'
        f'</span>'
    )


def _build_cards(existing: set, out_dir: Path) -> str:
    parts = []
    for i, (folder, name, desc, color) in enumerate(REPORTS):
        icon = _ICONS[i] if i < len(_ICONS) else '\U0001f4c4'
        is_present = folder in existing
        link = f'{folder}/index.html'
        opacity = '1' if is_present else '0.45'
        btn_style = (
            f'background:{color};color:#fff;'
            if is_present
            else 'background:#bbb;color:#fff;cursor:not-allowed'
        )
        btn_label = 'Open Report \u2192' if is_present else 'Not generated'
        btn_tag = (
            f'<a href="{link}" class="card-btn" style="{btn_style}">{btn_label}</a>'
            if is_present
            else f'<span class="card-btn" style="{btn_style}">{btn_label}</span>'
        )
        card = f"""
    <div class="card" style="opacity:{opacity};border-top:4px solid {color}">
      <div class="card-icon">{icon}</div>
      <div class="card-name" style="color:{color}">{name}</div>
      <div class="card-desc">{desc}</div>
      {btn_tag}
    </div>"""
        parts.append(card)
    return '\n'.join(parts)


_PAGE_TEMPLATE = """\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>CoEval Analysis — {exp_id}</title>
<style>
  *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    background: #f0f2f5;
    color: #1a1a2e;
    min-height: 100vh;
  }}
  /* Header */
  .site-header {{
    background: linear-gradient(135deg, #1a1a2e 0%, #16213e 60%, #0f3460 100%);
    color: #fff;
    padding: 36px 40px 28px;
  }}
  .site-header h1 {{
    font-size: 1.9rem;
    font-weight: 700;
    letter-spacing: -0.5px;
    margin-bottom: 6px;
  }}
  .site-header .subtitle {{
    font-size: 0.95rem;
    color: #a0aec0;
    margin-bottom: 20px;
  }}
  .meta-bar {{
    display: flex;
    flex-wrap: wrap;
    gap: 10px;
    margin-top: 14px;
  }}
  .meta-chip {{
    background: rgba(255,255,255,0.08);
    border: 1px solid rgba(255,255,255,0.18);
    border-radius: 20px;
    padding: 4px 14px;
    font-size: 0.82rem;
    color: #e2e8f0;
  }}
  /* Grid */
  .reports-grid {{
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 20px;
    padding: 32px 40px;
    max-width: 1200px;
    margin: 0 auto;
  }}
  @media (max-width: 900px) {{
    .reports-grid {{ grid-template-columns: repeat(2, 1fr); padding: 20px; }}
  }}
  @media (max-width: 580px) {{
    .reports-grid {{ grid-template-columns: 1fr; padding: 16px; }}
  }}
  /* Card */
  .card {{
    background: #fff;
    border-radius: 10px;
    box-shadow: 0 2px 8px rgba(0,0,0,0.07);
    padding: 22px 20px 18px;
    display: flex;
    flex-direction: column;
    gap: 10px;
    transition: box-shadow 0.15s, transform 0.15s;
  }}
  .card:hover {{
    box-shadow: 0 6px 20px rgba(0,0,0,0.12);
    transform: translateY(-2px);
  }}
  .card-icon {{ font-size: 1.8rem; line-height: 1; }}
  .card-name {{
    font-size: 1.05rem;
    font-weight: 700;
    line-height: 1.2;
  }}
  .card-desc {{
    font-size: 0.85rem;
    color: #555;
    line-height: 1.5;
    flex: 1;
  }}
  .card-btn {{
    display: inline-block;
    margin-top: 6px;
    padding: 7px 16px;
    border-radius: 6px;
    font-size: 0.85rem;
    font-weight: 600;
    text-decoration: none;
    text-align: center;
    transition: opacity 0.12s;
  }}
  .card-btn:hover {{ opacity: 0.85; }}
  /* Footer */
  .site-footer {{
    text-align: center;
    padding: 20px 40px 30px;
    font-size: 0.78rem;
    color: #888;
  }}
</style>
</head>
<body>
<header class="site-header">
  <h1>CoEval Analysis Portal</h1>
  <p class="subtitle">All analysis reports for this experiment run</p>
  <div class="meta-bar">
    {meta_bar}
  </div>
</header>

<main class="reports-grid">
{cards}
</main>

<footer class="site-footer">
  Generated by CoEval &mdash; {generated}
</footer>
</body>
</html>
"""
