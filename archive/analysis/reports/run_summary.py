"""HTML run-startup summary report (REQ-A-7.x).

Generates a self-contained HTML dashboard showing the current state of an
EES experiment run: phase completion, model inventory, data counts, and any
warnings — useful as a quick health-check before or after a run.

Usage
-----
    python -m analysis.reports.run_summary \\
        --run benchmark/runs/medium-benchmark-v1 \\
        --out reports/medium-benchmark-v1_summary.html

The output is a single self-contained .html file (no external assets).
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..loader import load_ees, EESDataModel


# ---------------------------------------------------------------------------
# HTML primitives (no Plotly required — pure CSS/HTML)
# ---------------------------------------------------------------------------

_CSS = """
* { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
       background: #f4f6f9; color: #24292f; line-height: 1.5; }
.container { max-width: 1100px; margin: 0 auto; padding: 24px; }
h1 { font-size: 1.6rem; font-weight: 700; margin-bottom: 4px; }
h2 { font-size: 1.1rem; font-weight: 600; margin: 24px 0 12px; color: #1f6feb; }
.subtitle { color: #656d76; font-size: 0.9rem; margin-bottom: 20px; }
.grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr)); gap: 14px; }
.card { background: #fff; border: 1px solid #d0d7de; border-radius: 8px; padding: 18px; }
.card .label { font-size: 0.75rem; color: #656d76; text-transform: uppercase; letter-spacing: 0.04em; }
.card .value { font-size: 2rem; font-weight: 700; margin: 4px 0 2px; }
.card .sub { font-size: 0.8rem; color: #57606a; }
.status-badge { display: inline-block; padding: 2px 10px; border-radius: 20px;
                font-size: 0.78rem; font-weight: 600; }
.status-completed { background: #dafbe1; color: #1a7f37; }
.status-in_progress { background: #fff8c5; color: #9a6700; }
.status-failed { background: #ffebe9; color: #cf222e; }
.status-pending { background: #f6f8fa; color: #57606a; }
table { width: 100%; border-collapse: collapse; font-size: 0.86rem; }
th { background: #f6f8fa; border: 1px solid #d0d7de; padding: 7px 12px;
     text-align: left; font-weight: 600; }
td { border: 1px solid #d0d7de; padding: 6px 12px; }
tr:nth-child(even) td { background: #f6f8fa; }
.prog-bar-bg { background: #eaeef2; border-radius: 4px; height: 8px; min-width: 80px; }
.prog-bar { background: #2da44e; border-radius: 4px; height: 8px; }
.prog-bar.warn { background: #d29922; }
.prog-bar.danger { background: #cf222e; }
.warn-box { background: #fff8c5; border: 1px solid #e3b341; border-radius: 6px;
            padding: 10px 14px; margin: 8px 0; font-size: 0.85rem; }
.ok-box { background: #dafbe1; border: 1px solid #2da44e; border-radius: 6px;
          padding: 10px 14px; margin: 8px 0; font-size: 0.85rem; }
.section { background: #fff; border: 1px solid #d0d7de; border-radius: 8px;
           padding: 20px; margin-bottom: 18px; }
.mono { font-family: 'SFMono-Regular', Consolas, 'Liberation Mono', monospace;
        font-size: 0.82rem; }
footer { text-align: center; color: #8c959f; font-size: 0.78rem; margin-top: 32px; }
"""


def _badge(status: str) -> str:
    cls = f"status-{status.replace(' ', '_')}"
    return f'<span class="status-badge {cls}">{status}</span>'


def _progress_bar(frac: float, width: int = 100) -> str:
    pct = min(100, max(0, round(frac * 100)))
    cls = "prog-bar danger" if pct < 50 else ("prog-bar warn" if pct < 80 else "prog-bar")
    return (
        f'<div class="prog-bar-bg" style="width:{width}px">'
        f'<div class="{cls}" style="width:{pct}%"></div></div>'
        f'<small>{pct}%</small>'
    )


def _stat_card(label: str, value: str | int, sub: str = "") -> str:
    return (
        f'<div class="card"><div class="label">{label}</div>'
        f'<div class="value">{value}</div>'
        f'<div class="sub">{sub}</div></div>'
    )


# ---------------------------------------------------------------------------
# Phase completion analysis
# ---------------------------------------------------------------------------

PHASE_ORDER = [
    "attribute_mapping",
    "rubric_mapping",
    "data_generation",
    "response_collection",
    "evaluation",
]

PHASE_DISPLAY = {
    "attribute_mapping": "Phase 1 — Attribute Mapping",
    "rubric_mapping": "Phase 2 — Rubric Mapping",
    "data_generation": "Phase 3 — Data Generation",
    "response_collection": "Phase 4 — Response Collection",
    "evaluation": "Phase 5 — Evaluation",
}


def _phase_rows(model: EESDataModel) -> str:
    meta = model.meta
    completed = set(meta.get("phases_completed", []))
    in_progress = set(meta.get("phases_in_progress", []))
    run_path = model.run_path

    rows = []
    for phase in PHASE_ORDER:
        display = PHASE_DISPLAY.get(phase, phase)
        if phase in completed:
            status_html = _badge("completed")
        elif phase in in_progress:
            status_html = _badge("in_progress")
        else:
            status_html = _badge("pending")

        # Count artifacts for each phase
        details = ""
        if phase == "attribute_mapping":
            p1_dir = run_path / "phase1_attributes"
            n = len(list(p1_dir.glob("*.attributes.json"))) if p1_dir.exists() else 0
            details = f"{n} attribute file(s)"
        elif phase == "rubric_mapping":
            p2_dir = run_path / "phase2_rubric"
            n = len(list(p2_dir.glob("*.rubric.json"))) if p2_dir.exists() else 0
            details = f"{n} rubric file(s)"
        elif phase == "data_generation":
            p3_dir = run_path / "phase3_datapoints"
            if p3_dir.exists():
                files = list(p3_dir.glob("*.datapoints.jsonl"))
                total = 0
                complete = 0
                for f in files:
                    c = sum(1 for l in f.read_text(
                        encoding="utf-8", errors="replace").splitlines() if l.strip())
                    total += c
                    if c >= 20:
                        complete += 1
                frac = complete / len(files) if files else 0
                bar = _progress_bar(frac)
                details = f"{total:,} items across {len(files)} files · {complete}/{len(files)} slots full · {bar}"
            else:
                details = "not started"
        elif phase == "response_collection":
            p4_dir = run_path / "phase4_responses"
            if p4_dir.exists():
                files = list(p4_dir.glob("*.responses.jsonl"))
                total = 0
                complete = 0
                for f in files:
                    c = sum(1 for l in f.read_text(
                        encoding="utf-8", errors="replace").splitlines() if l.strip())
                    total += c
                    if c >= 20:
                        complete += 1
                frac = complete / len(files) if files else 0
                bar = _progress_bar(frac)
                details = f"{total:,} responses across {len(files)} files · {complete}/{len(files)} slots full · {bar}"
            else:
                details = "not started"
        elif phase == "evaluation":
            p5_dir = run_path / "phase5_evaluations"
            if p5_dir.exists():
                files = list(p5_dir.glob("*.evaluations.jsonl"))
                total = 0
                complete = 0
                for f in files:
                    c = sum(1 for l in f.read_text(
                        encoding="utf-8", errors="replace").splitlines() if l.strip())
                    total += c
                    if c >= 100:
                        complete += 1
                frac = complete / len(files) if files else 0
                bar = _progress_bar(frac)
                details = f"{total:,} evaluations across {len(files)} files · {complete}/{len(files)} slots done · {bar}"
            else:
                details = "not started"

        rows.append(
            f"<tr><td>{display}</td><td>{status_html}</td>"
            f'<td class="mono">{details}</td></tr>'
        )
    return "\n".join(rows)


# ---------------------------------------------------------------------------
# Model inventory table
# ---------------------------------------------------------------------------

def _model_rows(model: EESDataModel) -> str:
    config_models = model.config.get("models", [])
    rows = []
    for m in config_models:
        name = m.get("name", "?")
        interface = m.get("interface", "?")
        roles = ", ".join(m.get("roles", []))
        params = m.get("parameters", {})
        max_tok = params.get("max_tokens") or params.get("max_new_tokens") or "?"
        model_id = params.get("model", "?")
        rows.append(
            f"<tr><td>{name}</td><td>{interface}</td>"
            f"<td>{model_id}</td><td>{roles}</td><td>{max_tok}</td></tr>"
        )
    return "\n".join(rows)


# ---------------------------------------------------------------------------
# Per-task data summary
# ---------------------------------------------------------------------------

def _task_rows(model: EESDataModel) -> str:
    run_path = model.run_path
    p3_dir = run_path / "phase3_datapoints"
    p4_dir = run_path / "phase4_responses"
    p5_dir = run_path / "phase5_evaluations"

    # Count per task
    tasks = sorted(model.tasks or [])
    rows = []
    for task in tasks:
        # Phase 3: sum up datapoints for this task
        p3_count = 0
        p3_slots = 0
        if p3_dir.exists():
            for f in p3_dir.glob(f"{task}.*.datapoints.jsonl"):
                c = sum(1 for l in f.read_text(
                    encoding="utf-8", errors="replace").splitlines() if l.strip())
                p3_count += c
                p3_slots += 1
        p3_bar = _progress_bar(p3_count / (p3_slots * 20) if p3_slots else 0, 60)

        # Phase 4: response count
        p4_count = 0
        p4_slots = 0
        if p4_dir.exists():
            for f in p4_dir.glob(f"{task}.*.responses.jsonl"):
                c = sum(1 for l in f.read_text(
                    encoding="utf-8", errors="replace").splitlines() if l.strip())
                p4_count += c
                p4_slots += 1

        # Phase 5: evaluation count and valid units
        p5_count = 0
        p5_slots = 0
        if p5_dir.exists():
            for f in p5_dir.glob(f"{task}.*.evaluations.jsonl"):
                c = sum(1 for l in f.read_text(
                    encoding="utf-8", errors="replace").splitlines() if l.strip())
                p5_count += c
                p5_slots += 1

        valid_units = sum(1 for u in model.units if u.task_id == task)
        aspects = model.aspects_by_task.get(task, [])

        rows.append(
            f"<tr><td>{task}</td>"
            f"<td>{p3_count:,} ({p3_slots} teachers) {p3_bar}</td>"
            f"<td>{p4_count:,} ({p4_slots} files)</td>"
            f"<td>{p5_count:,} ({p5_slots} files)</td>"
            f"<td>{valid_units:,}</td>"
            f"<td>{len(aspects)}</td></tr>"
        )
    return "\n".join(rows)


# ---------------------------------------------------------------------------
# Warnings section
# ---------------------------------------------------------------------------

def _warnings_html(model: EESDataModel) -> str:
    if not model.load_warnings:
        return '<div class="ok-box">No load warnings.</div>'
    items = "\n".join(
        f'<div class="warn-box">⚠ {w}</div>' for w in model.load_warnings
    )
    return items


# ---------------------------------------------------------------------------
# Main HTML assembly
# ---------------------------------------------------------------------------

def generate_run_summary(model: EESDataModel) -> str:
    meta = model.meta
    run_id = meta.get("experiment_id", model.run_path.name)
    status = meta.get("status", "unknown")
    started_at = meta.get("started_at", "?")
    updated_at = meta.get("updated_at", "?")
    phases_completed = meta.get("phases_completed", [])
    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    # Summary stat cards
    stat_cards = "".join([
        _stat_card("Experiment ID", run_id),
        _stat_card("Status", _badge(status), f"Started: {started_at}"),
        _stat_card("Phases done", len(phases_completed), f"of {len(PHASE_ORDER)}"),
        _stat_card("Datapoints (P3)", f"{len(model.datapoints):,}", f"{len(model.tasks)} tasks"),
        _stat_card("Responses (P4)", f"{len(model.responses):,}", "collected"),
        _stat_card("Eval records (P5)", f"{model.total_records:,}",
                   f"{model.valid_records:,} valid"),
        _stat_card("Analytical units", f"{len(model.units):,}", "valid (response × aspect)"),
        _stat_card("Load warnings", len(model.load_warnings), ""),
    ])

    # Aspect breakdown per task
    aspects_rows = ""
    for task in sorted(model.tasks):
        aspects = model.aspects_by_task.get(task, [])
        attrs = model.target_attrs_by_task.get(task, {})
        attr_summary = ", ".join(f"{k} ({len(v)} vals)" for k, v in attrs.items())
        aspects_rows += (
            f"<tr><td>{task}</td>"
            f"<td>{', '.join(aspects)}</td>"
            f"<td class='mono'>{attr_summary or '—'}</td></tr>\n"
        )

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>CoEval Run Summary — {run_id}</title>
<style>{_CSS}</style>
</head>
<body>
<div class="container">
  <h1>CoEval Run Summary</h1>
  <p class="subtitle">
    Run: <strong>{run_id}</strong> &nbsp;·&nbsp;
    Status: {_badge(status)} &nbsp;·&nbsp;
    Generated: {generated_at}
  </p>

  <!-- Stat grid -->
  <div class="grid">{stat_cards}</div>

  <!-- Phase pipeline -->
  <h2>Pipeline Phases</h2>
  <div class="section">
    <table>
      <thead><tr><th>Phase</th><th>Status</th><th>Details</th></tr></thead>
      <tbody>{_phase_rows(model)}</tbody>
    </table>
  </div>

  <!-- Model inventory -->
  <h2>Model Inventory</h2>
  <div class="section">
    <table>
      <thead>
        <tr><th>Name</th><th>Interface</th><th>Model ID</th><th>Roles</th><th>Max tokens</th></tr>
      </thead>
      <tbody>{_model_rows(model)}</tbody>
    </table>
  </div>

  <!-- Per-task data -->
  <h2>Per-Task Data Counts</h2>
  <div class="section">
    <table>
      <thead>
        <tr>
          <th>Task</th>
          <th>Phase 3 datapoints</th>
          <th>Phase 4 responses</th>
          <th>Phase 5 evaluations</th>
          <th>Valid units</th>
          <th>Rubric aspects</th>
        </tr>
      </thead>
      <tbody>{_task_rows(model)}</tbody>
    </table>
  </div>

  <!-- Rubric aspects and attributes -->
  <h2>Tasks — Rubric Aspects & Target Attributes</h2>
  <div class="section">
    <table>
      <thead><tr><th>Task</th><th>Rubric aspects</th><th>Target attributes</th></tr></thead>
      <tbody>{aspects_rows}</tbody>
    </table>
  </div>

  <!-- Warnings -->
  <h2>Load Warnings ({len(model.load_warnings)})</h2>
  <div class="section">{_warnings_html(model)}</div>

  <!-- Meta JSON -->
  <h2>Raw meta.json</h2>
  <div class="section">
    <pre class="mono">{json.dumps(meta, indent=2, default=str)}</pre>
  </div>

  <footer>CoEval run summary &nbsp;·&nbsp; {generated_at}</footer>
</div>
</body>
</html>"""
    return html


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Generate a self-contained HTML run-summary report."
    )
    parser.add_argument("--run", required=True, help="EES experiment folder path")
    parser.add_argument("--out", help="Output HTML file path (default: <run>/run_summary.html)")
    parser.add_argument("--partial-ok", action="store_true",
                        help="Suppress incomplete-experiment warning")
    args = parser.parse_args(argv)

    print(f"Loading EES from: {args.run}")
    try:
        model = load_ees(args.run, partial_ok=args.partial_ok)
    except FileNotFoundError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    html = generate_run_summary(model)

    out_path = Path(args.out) if args.out else Path(args.run) / "run_summary.html"
    out_path.write_text(html, encoding="utf-8")
    print(f"Summary written to: {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
