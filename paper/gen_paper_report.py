#!/usr/bin/env python3
"""Generate a self-contained HTML paper report with all tables and figures.

Usage:
    python paper/gen_paper_report.py \\
        --run benchmark/runs/paper-dual-track-v1 \\
        --out paper/paper_report.html

This generates a single HTML file with:
  - Tables 3-9 (from analysis.paper_tables)
  - Figures 1-8 (Plotly charts embedded as JSON)
  - Run metadata and data availability status
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import math
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Ensure project root is on sys.path when run as a script
# ---------------------------------------------------------------------------
_REPO_ROOT = Path(__file__).parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from analysis.loader import load_ees, EESDataModel
from analysis.paper_tables import (
    table3_spearman,
    table4_coverage,
    table5_student_scores,
    table6_ensemble_ablation,
    table7_sampling_ablation,
    table8_calibration,
    table9_positional_bias,
    _load_benchmark_scores,
)


# ---------------------------------------------------------------------------
# CSS
# ---------------------------------------------------------------------------

_CSS = """
* { box-sizing: border-box; margin: 0; padding: 0; }
body {
    font-family: 'Georgia', serif;
    font-size: 14px;
    line-height: 1.6;
    color: #1a1a1a;
    background: #f9f9f7;
    padding: 0 0 60px 0;
}
header {
    background: #1a3a5c;
    color: #fff;
    padding: 28px 40px 20px;
    border-bottom: 4px solid #e8a020;
}
header h1 { font-size: 22px; letter-spacing: 0.5px; margin-bottom: 6px; }
header .subtitle { font-size: 13px; opacity: 0.82; }
header .meta-row { margin-top: 12px; font-size: 12px; opacity: 0.75; }

.status-bar {
    background: #fff;
    border-bottom: 1px solid #ddd;
    padding: 10px 40px;
    display: flex;
    flex-wrap: wrap;
    gap: 10px;
    align-items: center;
    font-size: 12px;
}
.status-bar .label { font-weight: bold; margin-right: 6px; color: #555; }
.badge {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    padding: 2px 8px;
    border-radius: 10px;
    font-size: 11px;
    font-weight: 600;
}
.badge.ok   { background: #d4edda; color: #155724; }
.badge.warn { background: #fff3cd; color: #856404; }

main { max-width: 1100px; margin: 0 auto; padding: 30px 20px; }

.data-summary {
    background: #fff;
    border: 1px solid #ddd;
    border-radius: 6px;
    padding: 16px 20px;
    margin-bottom: 28px;
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
    gap: 12px;
}
.data-summary .stat-block { text-align: center; }
.data-summary .stat-num {
    font-size: 28px;
    font-weight: bold;
    color: #1a3a5c;
    display: block;
}
.data-summary .stat-label { font-size: 11px; color: #666; text-transform: uppercase; letter-spacing: 0.4px; }

section {
    background: #fff;
    border: 1px solid #ddd;
    border-radius: 6px;
    margin-bottom: 32px;
    overflow: hidden;
}
section > .section-header {
    background: #1a3a5c;
    color: #fff;
    padding: 12px 20px;
    font-size: 15px;
    font-weight: bold;
    letter-spacing: 0.3px;
}
section > .section-body { padding: 20px; }

h3 {
    font-size: 14px;
    color: #1a3a5c;
    margin: 20px 0 10px;
    border-bottom: 1px solid #e0e0e0;
    padding-bottom: 4px;
}
h3:first-child { margin-top: 0; }

.table-wrap { overflow-x: auto; margin-bottom: 8px; }
table {
    border-collapse: collapse;
    width: 100%;
    font-size: 13px;
}
thead tr { background: #f0f4f8; }
thead th {
    padding: 8px 12px;
    text-align: left;
    font-weight: 600;
    border-bottom: 2px solid #1a3a5c;
    white-space: nowrap;
    color: #1a3a5c;
}
tbody tr:nth-child(even) { background: #fafafa; }
tbody td {
    padding: 6px 12px;
    border-bottom: 1px solid #e8e8e8;
    font-family: 'Courier New', monospace;
    font-size: 12px;
}
tbody tr:last-child td { border-bottom: none; }
tbody td:first-child { font-family: 'Georgia', serif; font-size: 13px; }

.placeholder-note {
    font-size: 11px;
    color: #856404;
    background: #fff3cd;
    border: 1px solid #ffc107;
    border-radius: 4px;
    padding: 4px 10px;
    margin-bottom: 12px;
    display: inline-block;
}

.figure-wrap { margin: 16px 0; }
.figure-caption {
    font-size: 12px;
    color: #555;
    text-align: center;
    margin-top: 6px;
    font-style: italic;
}

footer {
    border-top: 1px solid #ddd;
    padding: 20px 40px;
    font-size: 11px;
    color: #888;
    background: #fff;
    margin-top: 40px;
}
footer strong { color: #555; }

.two-col { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }
@media (max-width: 700px) { .two-col { grid-template-columns: 1fr; } }
"""

# ---------------------------------------------------------------------------
# Plotly figure generators
# ---------------------------------------------------------------------------

def _placeholder_watermark(fig_dict: dict) -> dict:
    """Add a diagonal watermark annotation to a Plotly figure dict."""
    fig_dict.setdefault("layout", {}).setdefault("annotations", [])
    fig_dict["layout"]["annotations"].append({
        "text": "PLACEHOLDER DATA",
        "xref": "paper", "yref": "paper",
        "x": 0.5, "y": 0.5,
        "xanchor": "center", "yanchor": "middle",
        "showarrow": False,
        "font": {"size": 28, "color": "rgba(200,80,0,0.20)"},
        "textangle": -30,
    })
    return fig_dict


def fig1_architecture() -> tuple[dict, bool]:
    """Fig 1: CoEval 5-phase pipeline architecture (info graphic using Plotly)."""
    phases = [
        ("Phase 1", "Attribute\nMapping", "#4e79a7"),
        ("Phase 2", "Rubric\nConstruction", "#f28e2b"),
        ("Phase 3", "Data\nGeneration", "#59a14f"),
        ("Phase 4", "Response\nCollection", "#e15759"),
        ("Phase 5", "Ensemble\nScoring", "#76b7b2"),
    ]
    n = len(phases)
    box_w, box_h = 1.4, 0.9
    gap = 0.5
    total_w = n * box_w + (n - 1) * gap
    xs = [i * (box_w + gap) for i in range(n)]

    shapes = []
    annotations = []

    for i, (ph, label, color) in enumerate(phases):
        x0 = xs[i]
        x1 = x0 + box_w
        y0, y1 = 0, box_h

        shapes.append({
            "type": "rect",
            "x0": x0, "y0": y0, "x1": x1, "y1": y1,
            "line": {"color": color, "width": 2},
            "fillcolor": color,
            "opacity": 0.85,
        })
        annotations.append({
            "x": (x0 + x1) / 2,
            "y": y1 + 0.07,
            "text": f"<b>{ph}</b>",
            "showarrow": False,
            "font": {"size": 11, "color": "#222"},
            "xanchor": "center",
        })
        annotations.append({
            "x": (x0 + x1) / 2,
            "y": (y0 + y1) / 2,
            "text": label.replace("\n", "<br>"),
            "showarrow": False,
            "font": {"size": 10, "color": "#fff"},
            "xanchor": "center",
            "yanchor": "middle",
            "align": "center",
        })

        if i < n - 1:
            arrow_x = x1 + gap / 2
            shapes.append({
                "type": "line",
                "x0": x1, "y0": (y0 + y1) / 2,
                "x1": x1 + gap, "y1": (y0 + y1) / 2,
                "line": {"color": "#555", "width": 2},
            })
            annotations.append({
                "x": x1 + gap,
                "y": (y0 + y1) / 2,
                "ax": x1,
                "ay": (y0 + y1) / 2,
                "axref": "x", "ayref": "y",
                "showarrow": True,
                "arrowhead": 2,
                "arrowcolor": "#555",
                "arrowsize": 1.2,
                "arrowwidth": 2,
            })

    role_labels = [
        ("Teachers", 0, -0.3, "#4e79a7"),
        ("Teachers", 1, -0.3, "#4e79a7"),
        ("Teachers", 2, -0.3, "#4e79a7"),
        ("Students", 3, -0.3, "#e15759"),
        ("Judges", 4, -0.3, "#76b7b2"),
    ]
    for label, idx, y_off, color in role_labels:
        cx = xs[idx] + box_w / 2
        annotations.append({
            "x": cx,
            "y": y_off,
            "text": label,
            "showarrow": False,
            "font": {"size": 9, "color": color},
            "xanchor": "center",
        })

    fig = {
        "data": [{"type": "scatter", "x": [], "y": [], "mode": "markers"}],
        "layout": {
            "title": {"text": "Fig 1: CoEval Pipeline Architecture (5 Phases)", "font": {"size": 14}},
            "xaxis": {"range": [-0.2, total_w + 0.2], "visible": False, "showgrid": False},
            "yaxis": {"range": [-0.5, 1.3], "visible": False, "showgrid": False},
            "shapes": shapes,
            "annotations": annotations,
            "height": 220,
            "margin": {"l": 10, "r": 10, "t": 40, "b": 30},
            "plot_bgcolor": "#fff",
            "paper_bgcolor": "#fff",
        },
    }
    return fig, True  # is_real=True (no real data needed for architecture diagram)


def fig2_spearman_bar(model: EESDataModel) -> tuple[dict, bool]:
    """Fig 2: Spearman rho bar chart — CoEval ensemble vs single-judge baselines."""
    bm_scores = _load_benchmark_scores(model)
    is_real = bool(bm_scores)

    tasks_display = [t.replace("_", " ").title() for t in sorted(model.tasks)] or [
        "Text Summarization", "Code Explanation", "Email Composition", "Data Interpretation"
    ]

    if is_real:
        from analysis.paper_tables import (
            _coeval_scores_by_dp, spearmanr as _sr, _NAN, _mean
        )
        tasks = sorted(model.tasks)
        judges = sorted(model.judges)
        bm = bm_scores
        coeval_dp = _coeval_scores_by_dp(model)

        def task_rho(dp_scores: dict, task: str) -> float:
            ids = [d for d in dp_scores if model.datapoints.get(d, {}).get("task_id") == task]
            cx = [dp_scores[d] for d in ids if d in bm]
            by = [bm[d] for d in ids if d in bm]
            r, _ = _sr(cx, by)
            return r

        ensemble_rhos = [task_rho(coeval_dp, t) for t in tasks]

        judge_traces = []
        for j in judges[:3]:  # limit to 3 judges for readability
            from analysis.paper_tables import _coeval_scores_by_dp as _cdp
            j_dp = _cdp(model, judge_filter={j})
            rhos = [task_rho(j_dp, t) for t in tasks]
            judge_traces.append((j, rhos))
    else:
        tasks = ["text_summarization", "code_explanation", "email_composition", "data_interpretation"]
        tasks_display = ["Text Summary", "Code Expl.", "Email Comp.", "Data Interp."]
        ensemble_rhos = [0.871, 0.843, 0.856, 0.829]
        judge_traces = [
            ("gpt-4o-mini", [0.821, 0.798, 0.812, 0.784]),
            ("claude-3-5-haiku", [0.835, 0.811, 0.826, 0.799]),
            ("gemini-2.0-flash", [0.808, 0.782, 0.793, 0.769]),
        ]

    colors = ["#1a3a5c", "#4e79a7", "#f28e2b", "#59a14f"]

    traces = [{
        "type": "bar",
        "name": "CoEval Ensemble",
        "x": tasks_display,
        "y": [r if not (isinstance(r, float) and math.isnan(r)) else None for r in ensemble_rhos],
        "marker": {"color": "#1a3a5c"},
        "text": [f"{r:.3f}" if not (isinstance(r, float) and math.isnan(r)) else "n/a"
                 for r in ensemble_rhos],
        "textposition": "outside",
    }]
    for i, (jname, rhos) in enumerate(judge_traces):
        traces.append({
            "type": "bar",
            "name": f"G-Eval ({jname})",
            "x": tasks_display,
            "y": [r if not (isinstance(r, float) and math.isnan(r)) else None for r in rhos],
            "marker": {"color": colors[i + 1 % len(colors)]},
        })

    fig = {
        "data": traces,
        "layout": {
            "title": {"text": "Fig 2: Spearman \u03c1 — CoEval Ensemble vs Single-Judge Baselines",
                      "font": {"size": 14}},
            "barmode": "group",
            "xaxis": {"title": "Task"},
            "yaxis": {"title": "Spearman \u03c1", "range": [0.6, 1.0]},
            "height": 360,
            "legend": {"orientation": "h", "y": -0.2},
            "margin": {"l": 60, "r": 20, "t": 50, "b": 80},
            "plot_bgcolor": "#fafafa",
            "paper_bgcolor": "#fff",
        },
    }
    if not is_real:
        _placeholder_watermark(fig)
    return fig, is_real


def fig3_coverage_heatmap(model: EESDataModel) -> tuple[dict, bool]:
    """Fig 3: Coverage heatmap — ACR values by task x attribute."""
    tasks = sorted(model.tasks)
    is_real = bool(tasks and model.target_attrs_by_task)

    if is_real:
        # Build a matrix of (task, attr) -> coverage fraction
        all_attrs: list[str] = sorted({
            attr
            for attrs in model.target_attrs_by_task.values()
            for attr in attrs
        })
        z: list[list[float | None]] = []
        for task in tasks:
            row: list[float | None] = []
            task_attrs = model.target_attrs_by_task.get(task, {})
            dp_task = [dp for dp in model.datapoints.values() if dp.get("task_id") == task]
            for attr in all_attrs:
                vals_expected = set(task_attrs.get(attr, []))
                if not vals_expected:
                    row.append(None)
                    continue
                vals_seen = set()
                for dp in dp_task:
                    v = dp.get("sampled_target_attributes", {}).get(attr)
                    if v is not None:
                        vals_seen.add(str(v))
                row.append(len(vals_seen & vals_expected) / len(vals_expected))
            z.append(row)

        x_labels = [a.replace("_", " ").title() for a in all_attrs]
        y_labels = [t.replace("_", " ").title() for t in tasks]
    else:
        x_labels = ["Complexity", "Tone", "Domain", "Length", "Style"]
        y_labels = ["Text Summary", "Code Expl.", "Email Comp.", "Data Interp."]
        z = [
            [0.92, 1.00, 0.83, 0.67, 0.75],
            [0.88, 1.00, 0.91, 0.72, 0.80],
            [0.95, 1.00, 0.79, 0.63, 0.85],
            [0.90, 1.00, 0.87, 0.70, 0.78],
        ]

    fig = {
        "data": [{
            "type": "heatmap",
            "z": z,
            "x": x_labels,
            "y": y_labels,
            "colorscale": "Blues",
            "showscale": True,
            "colorbar": {"title": "ACR"},
            "zmin": 0, "zmax": 1,
        }],
        "layout": {
            "title": {"text": "Fig 3: Coverage Heatmap (ACR by Task \u00d7 Attribute)",
                      "font": {"size": 14}},
            "xaxis": {"title": "Attribute"},
            "yaxis": {"title": "Task"},
            "height": 320,
            "margin": {"l": 120, "r": 60, "t": 50, "b": 80},
            "paper_bgcolor": "#fff",
        },
    }
    if not is_real:
        _placeholder_watermark(fig)
    return fig, is_real


def fig4_acr_vs_rho(model: EESDataModel) -> tuple[dict, bool]:
    """Fig 4: ACR vs Spearman rho scatter per task."""
    from analysis.paper_tables import (
        _compute_acr, _coeval_scores_by_dp, spearmanr as _sr, _NAN
    )

    bm_scores = _load_benchmark_scores(model)
    acr_by_task = _compute_acr(model)
    is_real = bool(bm_scores and model.tasks)

    if is_real:
        coeval_dp = _coeval_scores_by_dp(model)
        tasks = sorted(model.tasks)
        xs, ys, labels = [], [], []
        for task in tasks:
            acr = acr_by_task.get(task, float("nan"))
            if math.isnan(acr):
                continue
            ids = [d for d in coeval_dp if model.datapoints.get(d, {}).get("task_id") == task]
            cx = [coeval_dp[d] for d in ids if d in bm_scores]
            by = [bm_scores[d] for d in ids if d in bm_scores]
            rho, _ = _sr(cx, by)
            if not math.isnan(rho):
                xs.append(acr)
                ys.append(rho)
                labels.append(task.replace("_", " ").title())
    else:
        xs = [0.612, 0.598, 0.631, 0.589]
        ys = [0.871, 0.843, 0.856, 0.829]
        labels = ["Text Summary", "Code Expl.", "Email Comp.", "Data Interp."]

    fig = {
        "data": [{
            "type": "scatter",
            "x": xs,
            "y": ys,
            "mode": "markers+text",
            "text": labels,
            "textposition": "top center",
            "marker": {"size": 12, "color": "#1a3a5c", "opacity": 0.85},
        }],
        "layout": {
            "title": {"text": "Fig 4: ACR vs Spearman \u03c1 per Task", "font": {"size": 14}},
            "xaxis": {"title": "Attribute Coverage Ratio (ACR)"},
            "yaxis": {"title": "Spearman \u03c1"},
            "height": 360,
            "margin": {"l": 60, "r": 20, "t": 50, "b": 60},
            "plot_bgcolor": "#fafafa",
            "paper_bgcolor": "#fff",
        },
    }
    if not is_real:
        _placeholder_watermark(fig)
    return fig, is_real


def fig5_radar_chart(model: EESDataModel) -> tuple[dict, bool]:
    """Fig 5: Radar chart comparing CoEval ensemble vs baselines on 5 dimensions."""
    dims = ["Correlation", "Coverage", "Efficiency", "Bias Resist.", "Reliability"]
    methods = {
        "CoEval Ensemble": [0.871, 0.871, 0.70, 0.88, 0.85],
        "Best Single Judge": [0.835, 0.50, 0.90, 0.65, 0.72],
        "Random Sampling": [0.72, 0.43, 0.95, 0.78, 0.61],
    }
    colors = ["#1a3a5c", "#e15759", "#59a14f"]
    is_real = False  # radar always uses normalized paper values

    traces = []
    for (name, values), color in zip(methods.items(), colors):
        traces.append({
            "type": "scatterpolar",
            "r": values + [values[0]],
            "theta": dims + [dims[0]],
            "name": name,
            "fill": "toself",
            "fillcolor": color,
            "opacity": 0.2,
            "line": {"color": color, "width": 2},
        })

    fig = {
        "data": traces,
        "layout": {
            "title": {"text": "Fig 5: Method Comparison — 5 Dimensions", "font": {"size": 14}},
            "polar": {
                "radialaxis": {"visible": True, "range": [0, 1]},
            },
            "legend": {"orientation": "h", "y": -0.1},
            "height": 400,
            "margin": {"l": 60, "r": 60, "t": 50, "b": 60},
            "paper_bgcolor": "#fff",
        },
    }
    _placeholder_watermark(fig)
    return fig, is_real


def fig6_ensemble_size(model: EESDataModel) -> tuple[dict, bool]:
    """Fig 6: Ensemble size line chart — rho vs number of judges."""
    from analysis.paper_tables import (
        _coeval_scores_by_dp, spearmanr as _sr
    )
    from itertools import combinations as _combs

    bm_scores = _load_benchmark_scores(model)
    judges = sorted(model.judges)
    is_real = bool(bm_scores and len(judges) >= 2)

    if is_real:
        # Compute mean rho for each ensemble size
        size_rhos: dict[int, list[float]] = {}
        for size in range(1, len(judges) + 1):
            rhos = []
            for combo in _combs(judges, size):
                dp = _coeval_scores_by_dp(model, judge_filter=set(combo))
                common = sorted(set(dp) & set(bm_scores))
                cx = [dp[d] for d in common]
                by = [bm_scores[d] for d in common]
                r, _ = _sr(cx, by)
                if not math.isnan(r):
                    rhos.append(r)
            if rhos:
                size_rhos[size] = rhos

        xs = sorted(size_rhos.keys())
        ys_mean = [sum(size_rhos[s]) / len(size_rhos[s]) for s in xs]
        ys_max = [max(size_rhos[s]) for s in xs]
        ys_min = [min(size_rhos[s]) for s in xs]
    else:
        xs = [1, 2, 3]
        ys_mean = [0.822, 0.851, 0.871]
        ys_max = [0.835, 0.858, 0.871]
        ys_min = [0.808, 0.842, 0.871]

    traces = [
        {
            "type": "scatter",
            "x": xs + xs[::-1],
            "y": ys_max + ys_min[::-1],
            "fill": "toself",
            "fillcolor": "rgba(26,58,92,0.15)",
            "line": {"color": "rgba(255,255,255,0)"},
            "showlegend": False,
            "name": "Range",
        },
        {
            "type": "scatter",
            "x": xs,
            "y": ys_mean,
            "mode": "lines+markers",
            "name": "Mean \u03c1",
            "line": {"color": "#1a3a5c", "width": 2.5},
            "marker": {"size": 10, "color": "#1a3a5c"},
        },
    ]

    fig = {
        "data": traces,
        "layout": {
            "title": {"text": "Fig 6: Ensemble Size Ablation — Spearman \u03c1 vs No. of Judges",
                      "font": {"size": 14}},
            "xaxis": {"title": "Number of Judges", "tickvals": xs, "dtick": 1},
            "yaxis": {"title": "Spearman \u03c1"},
            "height": 340,
            "margin": {"l": 60, "r": 20, "t": 50, "b": 60},
            "plot_bgcolor": "#fafafa",
            "paper_bgcolor": "#fff",
        },
    }
    if not is_real:
        _placeholder_watermark(fig)
    return fig, is_real


def fig7_verbosity_bias(model: EESDataModel) -> tuple[dict, bool]:
    """Fig 7: Verbosity bias scatter — response length vs CoEval score."""
    from analysis.paper_tables import _coeval_scores_by_dp, _composite_score

    # Collect (response_length, score_norm) pairs
    pairs: list[tuple[int, float]] = []
    for resp_id, resp in model.responses.items():
        resp_text = resp.get("response", resp.get("content", ""))
        length = len(resp_text.split()) if resp_text else 0
        if length == 0:
            continue
        # Average score_norm for this response
        r_units = [u for u in model.units if u.response_id == resp_id]
        if not r_units:
            continue
        avg_score = sum(u.score_norm for u in r_units) / len(r_units)
        pairs.append((length, _composite_score(avg_score)))

    is_real = len(pairs) >= 10

    if is_real:
        xs = [p[0] for p in pairs]
        ys = [p[1] for p in pairs]
        # Simple OLS trend line
        n = len(xs)
        mx = sum(xs) / n
        my = sum(ys) / n
        slope = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / max(
            sum((x - mx) ** 2 for x in xs), 1e-9
        )
        intercept = my - slope * mx
        x_min, x_max = min(xs), max(xs)
        trend_x = [x_min, x_max]
        trend_y = [slope * x + intercept for x in trend_x]
    else:
        import random
        rng = random.Random(42)
        xs = [rng.randint(50, 600) for _ in range(120)]
        ys = [max(1.0, min(5.0, 2.5 + (x - 300) * 0.002 + rng.gauss(0, 0.4)))
              for x in xs]
        trend_x = [50, 600]
        trend_y = [2.4, 2.8]

    traces = [
        {
            "type": "scatter",
            "x": xs, "y": ys,
            "mode": "markers",
            "marker": {"size": 5, "color": "#1a3a5c", "opacity": 0.45},
            "name": "Response",
        },
        {
            "type": "scatter",
            "x": trend_x, "y": trend_y,
            "mode": "lines",
            "line": {"color": "#e15759", "width": 2, "dash": "dash"},
            "name": "Trend",
        },
    ]

    fig = {
        "data": traces,
        "layout": {
            "title": {"text": "Fig 7: Verbosity Bias — Response Length vs Score", "font": {"size": 14}},
            "xaxis": {"title": "Response Length (words)"},
            "yaxis": {"title": "CoEval Score (1-5 scale)", "range": [0.5, 5.5]},
            "height": 360,
            "margin": {"l": 60, "r": 20, "t": 50, "b": 60},
            "plot_bgcolor": "#fafafa",
            "paper_bgcolor": "#fff",
        },
    }
    if not is_real:
        _placeholder_watermark(fig)
    return fig, is_real


def fig8_student_heatmap(model: EESDataModel) -> tuple[dict, bool]:
    """Fig 8: Student x task score heatmap."""
    from analysis.paper_tables import _composite_score
    from collections import defaultdict

    students = sorted(model.students)
    tasks = sorted(model.tasks)
    is_real = bool(students and tasks and model.units)

    if is_real:
        st_task: dict[str, dict[str, list[float]]] = {s: defaultdict(list) for s in students}
        for u in model.units:
            if u.student_model_id in st_task:
                st_task[u.student_model_id][u.task_id].append(u.score_norm)

        z = []
        for student in students:
            row = []
            for task in tasks:
                scores = st_task[student].get(task, [])
                row.append(_composite_score(sum(scores) / len(scores)) if scores else None)
            z.append(row)

        x_labels = [t.replace("_", " ").title() for t in tasks]
        y_labels = students
    else:
        x_labels = ["Text Summary", "Code Expl.", "Email Comp.", "Data Interp."]
        y_labels = ["gpt-4o-mini", "gpt-3.5-turbo", "claude-3-haiku", "gemini-flash", "llama-3-8b"]
        z = [
            [3.82, 3.95, 3.78, 3.89],
            [3.21, 3.15, 3.30, 3.25],
            [3.65, 3.71, 3.58, 3.62],
            [3.48, 3.52, 3.41, 3.55],
            [2.98, 2.85, 3.02, 2.91],
        ]

    fig = {
        "data": [{
            "type": "heatmap",
            "z": z,
            "x": x_labels,
            "y": y_labels,
            "colorscale": [
                [0.0, "#d62728"], [0.4, "#ff7f0e"],
                [0.7, "#2ca02c"], [1.0, "#1a3a5c"],
            ],
            "showscale": True,
            "colorbar": {"title": "Score (1-5)"},
            "zmin": 1, "zmax": 5,
            "text": [[f"{v:.2f}" if v is not None else "n/a" for v in row] for row in z],
            "texttemplate": "%{text}",
        }],
        "layout": {
            "title": {"text": "Fig 8: Student Score Heatmap (Student \u00d7 Task)",
                      "font": {"size": 14}},
            "xaxis": {"title": "Task"},
            "yaxis": {"title": "Student Model"},
            "height": 300 + len(y_labels) * 25,
            "margin": {"l": 140, "r": 80, "t": 50, "b": 80},
            "paper_bgcolor": "#fff",
        },
    }
    if not is_real:
        _placeholder_watermark(fig)
    return fig, is_real


# ---------------------------------------------------------------------------
# CSV -> HTML table renderer
# ---------------------------------------------------------------------------

def _csv_to_html_table(csv_path: Path) -> str:
    """Read a CSV file and return an HTML <table> string."""
    rows: list[list[str]] = []
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        for row in reader:
            rows.append(row)
    if not rows:
        return "<p><em>(empty table)</em></p>"

    header = rows[0]
    data = rows[1:]

    th_cells = "".join(f"<th>{_h(c)}</th>" for c in header)
    tbody_rows = []
    for row in data:
        cells = "".join(f"<td>{_h(c)}</td>" for c in row)
        tbody_rows.append(f"<tr>{cells}</tr>")

    return (
        '<div class="table-wrap">'
        f'<table><thead><tr>{th_cells}</tr></thead>'
        f'<tbody>{"".join(tbody_rows)}</tbody></table>'
        '</div>'
    )


def _h(text: str) -> str:
    """Minimal HTML escape."""
    return (
        text.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
    )


# ---------------------------------------------------------------------------
# Figure HTML wrapper
# ---------------------------------------------------------------------------

def _figure_html(fig_id: str, fig_dict: dict, caption: str, is_real: bool) -> str:
    json_str = json.dumps(fig_dict)
    real_badge = ""
    if not is_real:
        real_badge = '<div class="placeholder-note">&#9888; Placeholder data — run benchmark/compute_scores.py to populate with real values</div>'
    return f"""
<div class="figure-wrap">
{real_badge}<div id="{fig_id}"></div>
<script>
(function() {{
  var fig = {json_str};
  Plotly.newPlot('{fig_id}', fig.data, fig.layout, {{responsive: true, displayModeBar: false}});
}})();
</script>
<p class="figure-caption">{_h(caption)}</p>
</div>
"""


# ---------------------------------------------------------------------------
# Status badge helper
# ---------------------------------------------------------------------------

def _badge(label: str, is_real: bool) -> str:
    cls = "ok" if is_real else "warn"
    icon = "&#10003;" if is_real else "&#9888;"
    return f'<span class="badge {cls}">{icon} {_h(label)}</span>'


# ---------------------------------------------------------------------------
# Main HTML assembler
# ---------------------------------------------------------------------------

def generate_report(
    run_path: Path,
    out_path: Path,
    partial_ok: bool = False,
) -> None:
    print(f"Loading EES data from: {run_path}")
    model = load_ees(run_path, partial_ok=partial_ok)
    for w in model.load_warnings:
        print(f"  WARN: {w}")

    bm_scores = _load_benchmark_scores(model)
    has_bm = bool(bm_scores)

    print(f"Loaded: {len(model.units):,} analytical units, "
          f"{len(model.datapoints):,} datapoints, "
          f"{len(bm_scores):,} benchmark scores")

    # --- Generate tables into a temp dir ---
    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)
        print("Generating tables...")
        table3_spearman(model, tmp_dir)
        table4_coverage(model, tmp_dir)
        table5_student_scores(model, tmp_dir)
        table6_ensemble_ablation(model, tmp_dir)
        table7_sampling_ablation(model, tmp_dir)
        table8_calibration(model, tmp_dir)
        table9_positional_bias(model, tmp_dir)

        # Read CSVs
        def read_table(stem: str) -> str:
            p = tmp_dir / f"{stem}.csv"
            return _csv_to_html_table(p) if p.exists() else "<p><em>(table not generated)</em></p>"

        t3 = read_table("table3_spearman")
        t4 = read_table("table4_coverage")
        t5 = read_table("table5_student_scores")
        t6 = read_table("table6_ensemble_ablation")
        t7 = read_table("table7_sampling_ablation")
        t8 = read_table("table8_calibration")
        t9 = read_table("table9_positional_bias")

    # --- Generate figures ---
    print("Generating figures...")
    f1, r1 = fig1_architecture()
    f2, r2 = fig2_spearman_bar(model)
    f3, r3 = fig3_coverage_heatmap(model)
    f4, r4 = fig4_acr_vs_rho(model)
    f5, r5 = fig5_radar_chart(model)
    f6, r6 = fig6_ensemble_size(model)
    f7, r7 = fig7_verbosity_bias(model)
    f8, r8 = fig8_student_heatmap(model)

    real_count = sum([r1, r2, r3, r4, r5, r6, r7, r8])
    print(f"  {real_count}/8 figures use real data; {8 - real_count} use placeholder data")

    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    exp_id = model.meta.get("experiment_id", run_path.name)
    exp_status = model.meta.get("status", "unknown")
    phases_done = model.meta.get("phases_completed", [])

    # Status bar badges
    badge_t3 = _badge("Table 3 (Spearman)", has_bm)
    badge_t4 = _badge("Table 4 (Coverage)", bool(model.datapoints))
    badge_t5 = _badge("Table 5 (Students)", bool(model.units))
    badge_t6 = _badge("Table 6 (Ensemble)", has_bm)
    badge_t7 = _badge("Table 7 (Sampling)", has_bm)
    badge_t8 = _badge("Table 8 (Calibration)", has_bm)
    badge_t9 = _badge("Table 9 (Bias)", False)  # always needs swap pairs

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>CoEval Paper Report — {_h(exp_id)}</title>
<script src="https://cdn.plot.ly/plotly-2.35.2.min.js" charset="utf-8"></script>
<style>
{_CSS}
</style>
</head>
<body>

<header>
  <h1>CoEval Paper Report</h1>
  <div class="subtitle">Tables 3&#8211;9 and Figures 1&#8211;8 from EES experiment data</div>
  <div class="meta-row">
    Experiment: <strong>{_h(exp_id)}</strong> &nbsp;&bull;&nbsp;
    Status: <strong>{_h(exp_status)}</strong> &nbsp;&bull;&nbsp;
    Phases completed: {_h(str(phases_done))}
  </div>
</header>

<div class="status-bar">
  <span class="label">Table data status:</span>
  {badge_t3} {badge_t4} {badge_t5} {badge_t6} {badge_t7} {badge_t8} {badge_t9}
</div>

<main>

<div class="data-summary">
  <div class="stat-block">
    <span class="stat-num">{len(model.units):,}</span>
    <span class="stat-label">Analytical Units</span>
  </div>
  <div class="stat-block">
    <span class="stat-num">{len(model.datapoints):,}</span>
    <span class="stat-label">Datapoints</span>
  </div>
  <div class="stat-block">
    <span class="stat-num">{len(model.eval_records):,}</span>
    <span class="stat-label">Eval Records</span>
  </div>
  <div class="stat-block">
    <span class="stat-num">{len(bm_scores):,}</span>
    <span class="stat-label">Benchmark Scores</span>
  </div>
  <div class="stat-block">
    <span class="stat-num">{len(model.tasks)}</span>
    <span class="stat-label">Tasks</span>
  </div>
  <div class="stat-block">
    <span class="stat-num">{len(model.students)}</span>
    <span class="stat-label">Students</span>
  </div>
  <div class="stat-block">
    <span class="stat-num">{len(model.judges)}</span>
    <span class="stat-label">Judges</span>
  </div>
</div>

<!-- ===== Section 1: Primary Results ===== -->
<section>
  <div class="section-header">Section 1: Primary Results</div>
  <div class="section-body">
    <div class="two-col">
      <div>
        <h3>Table 3: Spearman &#961; vs. Benchmark Ground Truth</h3>
        {"" if has_bm else '<div class="placeholder-note">&#9888; Placeholder values &#8212; benchmark scores not computed yet</div>'}
        {t3}
      </div>
      <div>
        {_figure_html("fig2", f2,
          "Fig 2: Spearman ρ — CoEval Ensemble vs Single-Judge Baselines across 4 tasks.",
          r2)}
      </div>
    </div>
  </div>
</section>

<!-- ===== Section 2: Coverage Analysis ===== -->
<section>
  <div class="section-header">Section 2: Coverage Analysis</div>
  <div class="section-body">
    <h3>Table 4: Attribute Coverage Metrics</h3>
    {t4}
    <div class="two-col">
      <div>
        {_figure_html("fig3", f3,
          "Fig 3: Coverage Heatmap — Attribute Coverage Ratio (ACR) by task and attribute.",
          r3)}
      </div>
      <div>
        {_figure_html("fig4", f4,
          "Fig 4: ACR vs Spearman ρ scatter — tasks with higher coverage tend to have higher correlation.",
          r4)}
      </div>
    </div>
  </div>
</section>

<!-- ===== Section 3: Student Rankings ===== -->
<section>
  <div class="section-header">Section 3: Student Rankings</div>
  <div class="section-body">
    <div class="two-col">
      <div>
        <h3>Table 5: Student Composite Scores and Rankings</h3>
        {t5}
      </div>
      <div>
        {_figure_html("fig8", f8,
          "Fig 8: Student Score Heatmap — composite scores (1–5 scale) per student and task.",
          r8)}
      </div>
    </div>
  </div>
</section>

<!-- ===== Section 4: Ablations ===== -->
<section>
  <div class="section-header">Section 4: Ablations</div>
  <div class="section-body">
    <div class="two-col">
      <div>
        <h3>Table 6: Ensemble Size Ablation</h3>
        {"" if has_bm else '<div class="placeholder-note">&#9888; Requires benchmark scores</div>'}
        {t6}
        <h3 style="margin-top:20px">Table 7: Sampling Strategy Ablation</h3>
        {t7}
        <h3 style="margin-top:20px">Table 8: Judge Calibration Effect</h3>
        {t8}
      </div>
      <div>
        {_figure_html("fig5", f5,
          "Fig 5: Radar chart — CoEval Ensemble vs baselines across 5 evaluation dimensions.",
          r5)}
        {_figure_html("fig6", f6,
          "Fig 6: Ensemble size ablation — Spearman ρ increases with more judges.",
          r6)}
      </div>
    </div>
  </div>
</section>

<!-- ===== Section 5: Bias Analysis ===== -->
<section>
  <div class="section-header">Section 5: Bias Analysis</div>
  <div class="section-body">
    <div class="two-col">
      <div>
        <h3>Table 9: Positional Bias Rates</h3>
        <div class="placeholder-note">&#9888; Requires Phase 5 with positional_swap: true in config</div>
        {t9}
      </div>
      <div>
        {_figure_html("fig7", f7,
          "Fig 7: Verbosity bias — response length (words) vs CoEval score (1–5 scale).",
          r7)}
      </div>
    </div>
  </div>
</section>

<!-- ===== Section 6: Architecture ===== -->
<section>
  <div class="section-header">Section 6: Architecture</div>
  <div class="section-body">
    {_figure_html("fig1", f1,
      "Fig 1: CoEval 5-phase pipeline — from attribute mapping through ensemble scoring.",
      r1)}
  </div>
</section>

</main>

<footer>
  <strong>Generated:</strong> {_h(now_str)} &nbsp;&bull;&nbsp;
  <strong>Run path:</strong> {_h(str(run_path))} &nbsp;&bull;&nbsp;
  <strong>Output:</strong> {_h(str(out_path))}
  <br><br>
  <strong>Next steps:</strong>
  {"Run <code>python -m benchmark.compute_scores --run " + _h(str(run_path)) + "</code> to populate benchmark_native_score fields for real correlation values." if not has_bm else "All benchmark scores available. Review tables for publication-ready values."}
  &nbsp; Use <code>python -m analysis.paper_tables --run ...</code> for LaTeX output.
</footer>

</body>
</html>
"""

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(html, encoding="utf-8")
    print(f"\nReport written: {out_path}")
    print(f"  Size: {out_path.stat().st_size / 1024:.1f} KB")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Generate a self-contained HTML paper report with Tables 3-9 and Figures 1-8 "
            "from a completed CoEval EES experiment run."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--run", required=True, metavar="PATH",
        help="Path to EES experiment folder (must contain meta.json)"
    )
    parser.add_argument(
        "--out", default="paper/paper_report.html", metavar="PATH",
        help="Output HTML file path (default: paper/paper_report.html)"
    )
    parser.add_argument(
        "--partial-ok", action="store_true",
        help="Suppress warning when experiment is not fully completed"
    )
    args = parser.parse_args(argv)

    run_path = Path(args.run)
    out_path = Path(args.out)

    if not run_path.exists():
        print(f"ERROR: Run path does not exist: {run_path}", file=sys.stderr)
        return 1

    try:
        generate_report(run_path, out_path, partial_ok=args.partial_ok)
    except FileNotFoundError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise

    return 0


if __name__ == "__main__":
    sys.exit(main())
