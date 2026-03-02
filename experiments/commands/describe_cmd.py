"""coeval describe — generate a user-friendly HTML summary of an experiment config.

Produces a self-contained, styled HTML page showing models, tasks, phase
configuration, batch settings, and an estimated call budget.  No LLM API
calls are made.

Usage::

    coeval describe --config my_experiment.yaml
    coeval describe --config my_experiment.yaml --out design.html
"""
from __future__ import annotations

import argparse
import html as _html_module
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


# ---------------------------------------------------------------------------
# Role badge colours
# ---------------------------------------------------------------------------
_ROLE_COLORS = {
    "teacher":  ("teacher-badge",  "#2563eb", "#dbeafe"),   # blue
    "student":  ("student-badge",  "#16a34a", "#dcfce7"),   # green
    "judge":    ("judge-badge",    "#9333ea", "#f3e8ff"),   # purple
}

_IFACE_ICONS = {
    "openai":       "🟢",
    "anthropic":    "🟠",
    "gemini":       "🔵",
    "huggingface":  "🤗",
    "azure_openai": "🔷",
    "bedrock":      "🟡",
    "vertex":       "🔶",
    "openrouter":   "🔴",
    "benchmark":    "📊",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _esc(s: str) -> str:
    """HTML-escape a string."""
    return _html_module.escape(str(s))


def _call_budget(cfg) -> dict:
    """Return {phase: (calls, per_model_calls)} estimated call counts."""
    teachers = cfg.get_models_by_role("teacher")
    students = cfg.get_models_by_role("student")
    judges   = cfg.get_models_by_role("judge")

    # Exclude benchmark teachers from call count (they have no API calls)
    active_teachers = [t for t in teachers if t.interface != "benchmark"]

    total_items = sum(t.sampling.total for t in cfg.tasks) if cfg.tasks else 0
    # Per teacher: items; for benchmark, pre-ingested
    items_per_teacher = total_items  # each teacher generates all task items

    p3 = items_per_teacher * len(active_teachers)
    p4 = total_items * len(active_teachers + [t for t in teachers if t.interface == "benchmark"]) * len(students)
    p5 = p4 * len(judges)

    return {
        "attribute_mapping":   (0,  "Static from config — no LLM calls"),
        "rubric_mapping":      (0,  "Static from config — no LLM calls"),
        "data_generation":     (p3, f"{total_items} items × {len(active_teachers)} active teachers"),
        "response_collection": (p4, f"{total_items * (len(active_teachers) + len([t for t in teachers if t.interface == 'benchmark']))} datapoints × {len(students)} students"),
        "evaluation":          (p5, f"{p4} responses × {len(judges)} judges"),
    }


def _phase_modes(cfg) -> dict[str, str]:
    raw = cfg.experiment.phases or {}
    defaults = {
        "attribute_mapping":   "New",
        "rubric_mapping":      "New",
        "data_generation":     "New",
        "response_collection": "New",
        "evaluation":          "New",
    }
    defaults.update(raw)
    return defaults


def _batch_settings(cfg) -> list[tuple[str, str]]:
    out = []
    for iface, phases in (cfg.experiment.batch or {}).items():
        for phase, enabled in phases.items():
            if enabled:
                out.append((iface, phase))
    return out


# ---------------------------------------------------------------------------
# Provider budget probe
# ---------------------------------------------------------------------------

def _run_provider_probe(cfg, n_samples: int = 1) -> dict:
    """Make 1 sample call per non-benchmark model; return probe results dict.

    Returns a dict: model_name → {latency_s, tokens_per_second, price_input, price_output, error}
    Benchmark models are skipped (returned as {skipped: true}).
    """
    try:
        from ..interfaces.cost_estimator import (
            _run_sample_calls, _heuristic_latency, _heuristic_tps, get_prices,
        )
        from ..logger import RunLogger
        import os
        logger = RunLogger(os.devnull, min_level='WARNING', console=False)
    except Exception as exc:
        return {'_error': str(exc)}

    results = {}
    for model in cfg.models:
        if model.interface == 'benchmark':
            results[model.name] = {'skipped': True, 'reason': 'virtual (no API)'}
            continue
        if model.interface == 'huggingface':
            pi, po = get_prices(model)
            results[model.name] = {
                'skipped': True,
                'reason': 'local model (no API probe)',
                'latency_s': _heuristic_latency(model),
                'tokens_per_second': _heuristic_tps(model),
                'price_input': pi,
                'price_output': po,
            }
            continue
        pr = _run_sample_calls(model, n_samples, logger)
        pi, po = get_prices(model)
        results[model.name] = {
            'skipped': False,
            'latency_s': round(pr.latency_s, 3),
            'tokens_per_second': round(pr.tokens_per_second, 1),
            'price_input': pi,
            'price_output': po,
            'error': pr.error,
        }
    return results


# ---------------------------------------------------------------------------
# Cost estimate rendering helper
# ---------------------------------------------------------------------------

def _render_cost_section(cost_report: dict | None) -> str:
    """Render the Cost Estimate HTML section from an ``estimate_cost_static`` report.

    Returns an empty string when cost estimation failed (report is None).
    """
    if not cost_report:
        return ""

    total = cost_report['total_cost_usd']
    savings = cost_report.get('batch_savings_usd', 0.0)

    # Per-phase rows
    phase_rows = ""
    for pid, pdata in cost_report['per_phase'].items():
        if pdata['calls'] == 0:
            cls = ' class="zero-row"'
            cost_str = "—"
            calls_str = "—"
            saving_str = "—"
        else:
            cls = ""
            cost_str = f"${pdata['cost_usd']:.2f}"
            calls_str = f"{pdata['calls']:,}"
            s = pdata.get('batch_savings_usd', 0.0)
            saving_str = f"<span class='saving'>−${s:.2f}</span>" if s > 0.01 else "—"
        phase_rows += (
            f"<tr{cls}>"
            f"<td class='phase-name'>{_esc(pid.replace('_',' ').title())}</td>"
            f"<td class='calls-count'>{calls_str}</td>"
            f"<td class='cost-val'>{cost_str}</td>"
            f"<td class='saving-val'>{saving_str}</td>"
            f"</tr>"
        )

    # Provider rows (sorted by cost desc, already sorted in report)
    provider_rows = ""
    for iface, pdata in cost_report['per_provider'].items():
        icon = _IFACE_ICONS.get(iface, '⚙️')
        batch_tag = (
            '<span class="batch-badge" style="font-size:0.72rem">batch</span>'
            if pdata['batch'] else ''
        )
        models_str = _esc(', '.join(pdata['models']))
        provider_rows += (
            f"<tr>"
            f"<td>{icon} <b>{_esc(iface)}</b> {batch_tag}</td>"
            f"<td class='calls-count'>{pdata['calls']:,}</td>"
            f"<td class='cost-val'>${pdata['cost_usd']:.2f}</td>"
            f"<td class='small-text'>{models_str}</td>"
            f"</tr>"
        )

    savings_note = (
        f'<p class="savings-note">💚 Batch API saves an estimated '
        f'<b>${savings:.2f}</b> vs. real-time pricing '
        f'({100*(savings/(total+savings)):.0f}% discount applied).</p>'
        if savings > 0.01 else ""
    )

    return f"""
  <div class="section">
    <div class="section-title"><span class="section-icon">💰</span> Estimated Cost (heuristic, no sample calls)</div>
    <p class="cost-disclaimer">
      Estimates use average token-count heuristics and current prices from
      <code>benchmark/provider_pricing.yaml</code>. Actual cost may vary by ±30%.
    </p>
    {savings_note}
    <div class="cost-grid">
      <div class="cost-col">
        <h4>Per Phase</h4>
        <table class="cost-table">
          <thead><tr>
            <th>Phase</th><th style="text-align:right">Calls</th>
            <th style="text-align:right">Cost</th>
            <th style="text-align:right">Batch saving</th>
          </tr></thead>
          <tbody>{phase_rows}</tbody>
          <tfoot><tr class="total-row">
            <td colspan="2"><b>Total</b></td>
            <td class="cost-val"><b>${total:.2f}</b></td>
            <td class="saving-val">{'<span class="saving">−$'+f'{savings:.2f}</span>' if savings > 0.01 else '—'}</td>
          </tr></tfoot>
        </table>
      </div>
      <div class="cost-col">
        <h4>Per Provider</h4>
        <table class="cost-table">
          <thead><tr>
            <th>Provider</th><th style="text-align:right">Calls</th>
            <th style="text-align:right">Cost</th>
            <th>Models</th>
          </tr></thead>
          <tbody>{provider_rows}</tbody>
        </table>
      </div>
    </div>
  </div>"""


# ---------------------------------------------------------------------------
# Provider budget probe rendering helper
# ---------------------------------------------------------------------------

def _render_probe_section(probe_results: dict | None) -> str:
    """Render the Provider Budget Probe HTML section."""
    if not probe_results or probe_results.get('_error'):
        err = (probe_results or {}).get('_error', 'probe not run')
        return f'<div class="section"><div class="section-title"><span class="section-icon">📡</span> Provider Budget Probe</div><p class="cost-disclaimer">Probe unavailable: {_esc(err)}</p></div>'

    rows = ""
    for model_name, data in probe_results.items():
        if data.get('skipped'):
            reason = data.get('reason', 'skipped')
            rows += (
                f"<tr class='zero-row'>"
                f"<td>{_esc(model_name)}</td>"
                f"<td colspan='5' class='small-text'><em>{_esc(reason)}</em></td>"
                f"</tr>"
            )
            continue
        error = data.get('error')
        if error:
            status = "❌"
            latency_str = "—"
            tps_str = "—"
            cost_str = "—"
            err_str = f'<span style="color:#dc2626;font-size:0.78rem">{_esc(str(error)[:80])}</span>'
        else:
            status = "✅"
            latency_str = f"{data['latency_s']:.2f}s"
            tps_str = f"{data['tokens_per_second']:.0f}"
            pi = data.get('price_input', 0)
            po = data.get('price_output', 0)
            # cost per 1000 calls with ~400 input + 200 output tokens
            cost_per_1k = (pi * 400 + po * 200) / 1_000_000 * 1000
            cost_str = f"${cost_per_1k:.3f}"
            err_str = ""
        rows += (
            f"<tr>"
            f"<td>{_esc(model_name)}</td>"
            f"<td style='text-align:center'>{status}</td>"
            f"<td class='cost-val'>{latency_str}</td>"
            f"<td class='cost-val'>{tps_str}</td>"
            f"<td class='cost-val'>${data.get('price_input',0):.3f} / ${data.get('price_output',0):.2f}</td>"
            f"<td class='cost-val'>{cost_str} {err_str}</td>"
            f"</tr>"
        )

    return f"""
  <div class="section">
    <div class="section-title"><span class="section-icon">📡</span> Provider Budget Probe (live)</div>
    <p class="cost-disclaimer">
      1 sample call made per model. Latency and throughput are real measurements.
      Cost/1k calls = (400 input + 200 output tokens) × 1,000 × price.
    </p>
    <table class="cost-table" style="width:100%">
      <thead><tr>
        <th>Model</th><th style="text-align:center">Status</th>
        <th style="text-align:right">Latency</th>
        <th style="text-align:right">tok/s</th>
        <th style="text-align:right">Price (in/out per 1M)</th>
        <th style="text-align:right">Cost / 1k calls</th>
      </tr></thead>
      <tbody>{rows}</tbody>
    </table>
  </div>"""


# ---------------------------------------------------------------------------
# HTML generation
# ---------------------------------------------------------------------------

def _render_html(cfg, config_path: str, probe_results: dict | None = None) -> str:
    from ..config import PHASE_IDS
    try:
        from ..interfaces.cost_estimator import estimate_cost_static
        cost_report = estimate_cost_static(cfg)
    except Exception:
        cost_report = None

    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    exp = cfg.experiment
    budget = _call_budget(cfg)
    modes  = _phase_modes(cfg)
    batch  = _batch_settings(cfg)
    total_calls = sum(v[0] for v in budget.values())

    teachers  = cfg.get_models_by_role("teacher")
    students  = cfg.get_models_by_role("student")
    judges    = cfg.get_models_by_role("judge")
    benchmark_teachers = [t for t in teachers if t.interface == "benchmark"]

    # ------------------------------------------------------------------ #
    # Models section
    # ------------------------------------------------------------------ #
    model_rows_html = ""
    for m in cfg.models:
        role_badges = ""
        for r in m.roles:
            color_info = _ROLE_COLORS.get(r, ("", "#555", "#eee"))
            _, fg, bg = color_info
            role_badges += (
                f'<span class="role-badge" style="background:{bg};color:{fg}">'
                f'{_esc(r)}</span> '
            )
        icon = _IFACE_ICONS.get(m.interface, "⚙️")
        model_id = m.parameters.get("model", "—") if m.interface != "benchmark" else "pre-ingested"
        params_bits = []
        for k, v in m.parameters.items():
            if k != "model":
                params_bits.append(f"{_esc(k)}={_esc(str(v))}")
        params_str = ", ".join(params_bits) if params_bits else "—"
        role_overrides = ""
        for role, rp in (m.role_parameters or {}).items():
            rp_str = ", ".join(f"{k}={v}" for k, v in rp.items())
            _, fg, bg = _ROLE_COLORS.get(role, ("", "#555", "#eee"))
            role_overrides += (
                f'<span class="role-badge" style="background:{bg};color:{fg};font-size:0.75rem">'
                f'{_esc(role)}</span>: {_esc(rp_str)}<br>'
            )
        model_rows_html += f"""
        <tr>
          <td class="model-name">{icon} {_esc(m.name)}</td>
          <td><code>{_esc(m.interface)}</code></td>
          <td><code class="model-id">{_esc(model_id)}</code></td>
          <td>{role_badges}</td>
          <td class="small-text">{params_str}</td>
          <td class="small-text">{role_overrides or "—"}</td>
        </tr>"""

    # ------------------------------------------------------------------ #
    # Tasks section
    # ------------------------------------------------------------------ #
    tasks_html = ""
    for i, task in enumerate(cfg.tasks):
        # Target attributes
        ta = task.target_attributes
        if isinstance(ta, dict) and ta:
            attr_rows = ""
            for attr_name, vals in ta.items():
                vals_str = ", ".join(f"<code>{_esc(v)}</code>" for v in vals)
                attr_rows += f"<tr><td><b>{_esc(attr_name)}</b></td><td>{vals_str}</td></tr>"
            attrs_html = f'<table class="attr-table">{attr_rows}</table>'
        elif isinstance(ta, str):
            attrs_html = f'<span class="badge-auto">{_esc(ta)}</span>'
        else:
            attrs_html = "<em>none</em>"

        # Nuanced attributes
        na = task.nuanced_attributes
        if isinstance(na, dict) and na:
            nuance_rows = ""
            for attr_name, vals in na.items():
                vals_str = ", ".join(f"<code>{_esc(v)}</code>" for v in vals)
                nuance_rows += f"<tr><td><b>{_esc(attr_name)}</b></td><td>{vals_str}</td></tr>"
            nuance_html = f'<table class="attr-table">{nuance_rows}</table>'
        elif isinstance(na, str):
            nuance_html = f'<span class="badge-auto">{_esc(na)}</span>'
        else:
            nuance_html = "<em>none</em>"

        # Rubric
        rubric_html = '<table class="rubric-table">'
        if isinstance(task.rubric, dict):
            for criterion, desc in task.rubric.items():
                rubric_html += (
                    f"<tr><td class=\"criterion\">{_esc(criterion)}</td>"
                    f"<td>{_esc(desc)}</td></tr>"
                )
        rubric_html += "</table>"

        # Sampling
        s = task.sampling
        sampling_str = (
            f"<b>{s.total}</b> items&nbsp;&nbsp;|&nbsp;&nbsp;"
            f"target attrs: {_esc(str(s.target))}&nbsp;&nbsp;|&nbsp;&nbsp;"
            f"nuance attrs: {_esc(str(s.nuance))}"
        )
        label_eval_str = ""
        if hasattr(task, "label_attributes") and task.label_attributes:
            la_str = ", ".join(f"<code>{_esc(a)}</code>" for a in task.label_attributes)
            label_eval_str = f'<p class="label-eval-note">Judge-free evaluation via label match: {la_str}</p>'

        eval_mode_badge = f'<span class="eval-badge">{_esc(task.evaluation_mode)}</span>'

        tasks_html += f"""
        <details class="task-card" {'open' if i == 0 else ''}>
          <summary class="task-summary">
            <span class="task-num">{i+1}</span>
            <span class="task-name">{_esc(task.name)}</span>
            <span class="task-meta">
              {eval_mode_badge}
              &nbsp;{_esc(str(s.total))} items
            </span>
          </summary>
          <div class="task-body">
            <div class="task-desc"><b>Description:</b> {_esc(task.description.strip())}</div>
            <div class="task-desc"><b>Output format:</b> {_esc(task.output_description.strip())}</div>
            {label_eval_str}
            <div class="task-grid">
              <div class="task-col">
                <h4>Target Attributes</h4>{attrs_html}
                <h4 style="margin-top:1em">Nuanced Attributes</h4>{nuance_html}
                <p class="sampling-info">Sampling: {sampling_str}</p>
              </div>
              <div class="task-col">
                <h4>Rubric ({len(task.rubric) if isinstance(task.rubric, dict) else "auto"} criteria)</h4>
                {rubric_html}
              </div>
            </div>
          </div>
        </details>"""

    # ------------------------------------------------------------------ #
    # Phase plan table
    # ------------------------------------------------------------------ #
    phase_rows_html = ""
    total_cost_calls = 0
    for phase_id in PHASE_IDS:
        calls, note = budget.get(phase_id, (0, ""))
        mode = modes.get(phase_id, "New")
        is_batch = any(p == phase_id for _, p in batch)
        batch_str = ""
        if is_batch:
            ifaces = [i for i, p in batch if p == phase_id]
            batch_str = f'<span class="batch-badge">batch: {", ".join(ifaces)}</span>'
        zero_cls = ' class="zero-row"' if calls == 0 else ""
        total_cost_calls += calls
        phase_rows_html += f"""
        <tr{zero_cls}>
          <td class="phase-name">{_esc(phase_id.replace("_", " ").title())}</td>
          <td><span class="mode-badge mode-{mode.lower()}">{_esc(mode)}</span></td>
          <td class="calls-count">{"—" if calls == 0 else f"<b>{calls:,}</b>"}</td>
          <td class="phase-note">{_esc(note)} {batch_str}</td>
        </tr>"""

    # ------------------------------------------------------------------ #
    # Summary stats bar
    # ------------------------------------------------------------------ #
    n_benchmark = len(benchmark_teachers)
    n_llm_teachers = len([t for t in teachers if t.interface != "benchmark"])
    teacher_note = (
        f"{n_llm_teachers} LLM + {n_benchmark} benchmark"
        if n_benchmark else str(len(teachers))
    )

    quota_rows = ""
    for model_name, q in (exp.quota or {}).items():
        max_c = q.get("max_calls")
        max_c_str = f"{max_c:,}" if isinstance(max_c, int) else "&infin;"
        quota_rows += f"<tr><td>{_esc(model_name)}</td><td>{max_c_str}</td></tr>"
    quota_html = (
        f'<table class="quota-table"><thead><tr><th>Model</th><th>Max calls</th></tr></thead>'
        f'<tbody>{quota_rows}</tbody></table>'
        if quota_rows else "<p><em>No per-model quotas set.</em></p>"
    )

    # ------------------------------------------------------------------ #
    # Assemble full page
    # ------------------------------------------------------------------ #
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>CoEval Config: {_esc(exp.id)}</title>
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
      font-size: 14px; line-height: 1.6; color: #1e293b;
      background: #f8fafc; padding: 0 0 60px;
    }}
    a {{ color: #2563eb; }}
    code {{ font-family: "SF Mono", Consolas, monospace; font-size: 0.88em;
            background: #f1f5f9; padding: 1px 5px; border-radius: 4px; }}

    /* Header */
    .header {{
      background: linear-gradient(135deg, #1e40af 0%, #1d4ed8 100%);
      color: #fff; padding: 28px 40px 24px; box-shadow: 0 2px 8px rgba(0,0,0,.15);
    }}
    .header h1 {{ font-size: 1.65rem; font-weight: 700; margin-bottom: 4px; }}
    .header .meta {{ font-size: 0.82rem; opacity: .8; }}
    .header .exp-id {{ font-size: 1.1rem; opacity: .95; font-weight: 500; }}

    /* Stats bar */
    .stats-bar {{
      display: flex; gap: 0; background: #1e3a8a; color: #fff;
      padding: 0 40px; border-bottom: 3px solid #2563eb;
    }}
    .stat {{
      padding: 12px 28px 10px; border-right: 1px solid #2d52a6;
      text-align: center;
    }}
    .stat .val {{ font-size: 1.7rem; font-weight: 700; line-height: 1.2; }}
    .stat .lbl {{ font-size: 0.73rem; opacity: .75; text-transform: uppercase;
                  letter-spacing: .04em; }}

    /* Container */
    .container {{ max-width: 1200px; margin: 30px auto; padding: 0 24px; }}

    /* Sections */
    .section {{ background: #fff; border-radius: 10px; padding: 28px 30px;
               box-shadow: 0 1px 4px rgba(0,0,0,.07); margin-bottom: 24px; }}
    .section-title {{
      font-size: 1.05rem; font-weight: 700; color: #1e40af;
      border-bottom: 2px solid #dbeafe; padding-bottom: 10px; margin-bottom: 18px;
      display: flex; align-items: center; gap: 8px;
    }}
    .section-icon {{ font-size: 1.2rem; }}

    /* Models table */
    .models-table {{ width: 100%; border-collapse: collapse; }}
    .models-table th {{
      background: #f0f4ff; color: #374151; font-size: 0.78rem;
      text-transform: uppercase; letter-spacing: .04em;
      padding: 8px 12px; text-align: left; border-bottom: 2px solid #dbeafe;
    }}
    .models-table td {{ padding: 10px 12px; border-bottom: 1px solid #f1f5f9;
                        vertical-align: top; }}
    .models-table tr:hover {{ background: #fafcff; }}
    .model-name {{ font-weight: 600; white-space: nowrap; }}
    .model-id {{ color: #4b5563; }}
    .small-text {{ font-size: 0.82rem; color: #6b7280; }}

    /* Badges */
    .role-badge {{
      display: inline-block; padding: 2px 10px; border-radius: 999px;
      font-size: 0.78rem; font-weight: 600; margin: 1px 2px;
    }}
    .batch-badge {{
      display: inline-block; padding: 2px 8px; border-radius: 4px;
      background: #fef3c7; color: #92400e; font-size: 0.78rem; font-weight: 500;
    }}
    .eval-badge {{
      background: #e0e7ff; color: #3730a3; padding: 2px 8px;
      border-radius: 4px; font-size: 0.76rem; font-weight: 600;
    }}
    .badge-auto {{
      background: #fff7ed; color: #9a3412; padding: 2px 8px;
      border-radius: 4px; font-size: 0.82rem;
    }}

    /* Phase table */
    .phase-table {{ width: 100%; border-collapse: collapse; }}
    .phase-table th {{
      background: #f0f4ff; color: #374151; font-size: 0.78rem;
      text-transform: uppercase; letter-spacing: .04em;
      padding: 8px 14px; text-align: left; border-bottom: 2px solid #dbeafe;
    }}
    .phase-table td {{ padding: 10px 14px; border-bottom: 1px solid #f1f5f9; }}
    .phase-table .zero-row td {{ color: #9ca3af; }}
    .phase-name {{ font-weight: 600; }}
    .calls-count {{ font-family: monospace; text-align: right; padding-right: 28px; }}
    .phase-note {{ color: #4b5563; font-size: 0.85rem; }}
    .mode-badge {{
      display: inline-block; padding: 2px 10px; border-radius: 4px;
      font-size: 0.78rem; font-weight: 600;
    }}
    .mode-new     {{ background: #dcfce7; color: #166534; }}
    .mode-extend  {{ background: #dbeafe; color: #1e40af; }}
    .mode-keep    {{ background: #fef9c3; color: #854d0e; }}
    .mode-model   {{ background: #f3e8ff; color: #6b21a8; }}
    .total-row td {{ font-weight: 700; background: #f8fafc;
                     border-top: 2px solid #dbeafe; }}

    /* Task cards */
    .task-card {{
      border: 1px solid #e2e8f0; border-radius: 8px;
      margin-bottom: 14px; overflow: hidden;
    }}
    .task-summary {{
      display: flex; align-items: center; gap: 12px;
      padding: 14px 18px; background: #f8fafc; cursor: pointer;
      list-style: none; font-weight: 600;
    }}
    .task-summary:hover {{ background: #f0f4ff; }}
    .task-summary::-webkit-details-marker {{ display: none; }}
    .task-summary::before {{ content: "▶"; font-size: 0.7rem; color: #6b7280; }}
    details[open] .task-summary::before {{ content: "▼"; }}
    .task-num {{
      background: #2563eb; color: #fff; width: 26px; height: 26px;
      border-radius: 50%; display: flex; align-items: center; justify-content: center;
      font-size: 0.82rem; flex-shrink: 0;
    }}
    .task-name {{ font-size: 1rem; flex: 1; color: #1e293b; }}
    .task-meta {{ font-size: 0.8rem; color: #64748b; font-weight: 400;
                  display: flex; align-items: center; gap: 8px; }}
    .task-body {{
      padding: 20px 22px; background: #fff;
      border-top: 1px solid #e2e8f0;
    }}
    .task-desc {{ color: #374151; margin-bottom: 12px; }}
    .task-grid {{
      display: grid; grid-template-columns: 1fr 1fr; gap: 24px; margin-top: 18px;
    }}
    @media (max-width: 800px) {{ .task-grid {{ grid-template-columns: 1fr; }} }}
    .task-col h4 {{
      font-size: 0.82rem; text-transform: uppercase; letter-spacing: .05em;
      color: #6b7280; margin-bottom: 8px; font-weight: 600;
    }}
    .attr-table {{ width: 100%; border-collapse: collapse; font-size: 0.88rem; }}
    .attr-table td {{ padding: 4px 8px; border-bottom: 1px solid #f1f5f9; }}
    .attr-table td:first-child {{ white-space: nowrap; color: #374151; width: 140px; }}
    .rubric-table {{ width: 100%; border-collapse: collapse; font-size: 0.87rem; }}
    .rubric-table td {{ padding: 5px 8px; border-bottom: 1px solid #f1f5f9;
                        vertical-align: top; }}
    .criterion {{ font-weight: 600; color: #1e40af; white-space: nowrap;
                  padding-right: 14px; width: 180px; }}
    .sampling-info {{ font-size: 0.82rem; color: #6b7280; margin-top: 10px; }}
    .label-eval-note {{
      background: #f0fdf4; border-left: 3px solid #22c55e;
      padding: 6px 12px; margin: 8px 0; font-size: 0.87rem;
      color: #166534; border-radius: 0 4px 4px 0;
    }}

    /* Quota */
    .quota-table {{ border-collapse: collapse; }}
    .quota-table th, .quota-table td {{
      padding: 6px 14px; text-align: left;
      border-bottom: 1px solid #f1f5f9; font-size: 0.88rem;
    }}
    .quota-table th {{ background: #f0f4ff; font-size: 0.78rem; text-transform: uppercase; }}

    /* Cost estimate section */
    .cost-disclaimer {{
      font-size: 0.82rem; color: #6b7280; margin-bottom: 10px;
    }}
    .savings-note {{
      background: #f0fdf4; border-left: 3px solid #22c55e;
      padding: 7px 14px; margin: 0 0 14px; font-size: 0.87rem;
      color: #166534; border-radius: 0 4px 4px 0;
    }}
    .cost-grid {{
      display: grid; grid-template-columns: 1fr 1fr; gap: 24px;
    }}
    @media (max-width: 800px) {{ .cost-grid {{ grid-template-columns: 1fr; }} }}
    .cost-col h4 {{
      font-size: 0.82rem; text-transform: uppercase; letter-spacing: .05em;
      color: #6b7280; margin-bottom: 8px; font-weight: 600;
    }}
    .cost-table {{ width: 100%; border-collapse: collapse; font-size: 0.88rem; }}
    .cost-table th {{
      background: #f0f4ff; color: #374151; font-size: 0.76rem;
      text-transform: uppercase; letter-spacing: .04em;
      padding: 6px 10px; text-align: left; border-bottom: 2px solid #dbeafe;
    }}
    .cost-table td {{ padding: 7px 10px; border-bottom: 1px solid #f1f5f9;
                      vertical-align: top; }}
    .cost-table tr.zero-row td {{ color: #9ca3af; }}
    .cost-val {{ text-align: right; font-family: monospace; font-weight: 600;
                 white-space: nowrap; }}
    .saving-val {{ text-align: right; font-family: monospace; white-space: nowrap; }}
    .saving {{ color: #16a34a; font-weight: 600; }}
    .cost-table tfoot .total-row td {{
      font-weight: 700; background: #f8fafc;
      border-top: 2px solid #dbeafe;
    }}

    /* Footer */
    .footer {{
      text-align: center; color: #94a3b8; font-size: 0.78rem; margin-top: 40px;
    }}
  </style>
</head>
<body>

<div class="header">
  <h1>CoEval Experiment Configuration</h1>
  <div class="exp-id">experiment: <b>{_esc(exp.id)}</b></div>
  <div class="meta">
    Config: <code style="background:rgba(255,255,255,.15);color:#fff">{_esc(config_path)}</code>
    &nbsp;&nbsp;|&nbsp;&nbsp;Generated: {_esc(now)}
    &nbsp;&nbsp;|&nbsp;&nbsp;Storage: <code style="background:rgba(255,255,255,.15);color:#fff">{_esc(exp.storage_folder)}</code>
  </div>
</div>

<div class="stats-bar">
  <div class="stat">
    <div class="val">{len(cfg.models)}</div>
    <div class="lbl">Models</div>
  </div>
  <div class="stat">
    <div class="val">{_esc(teacher_note)}</div>
    <div class="lbl">Teachers</div>
  </div>
  <div class="stat">
    <div class="val">{len(students)}</div>
    <div class="lbl">Students</div>
  </div>
  <div class="stat">
    <div class="val">{len(judges)}</div>
    <div class="lbl">Judges</div>
  </div>
  <div class="stat">
    <div class="val">{len(cfg.tasks)}</div>
    <div class="lbl">Tasks</div>
  </div>
  <div class="stat">
    <div class="val">{total_calls:,}</div>
    <div class="lbl">LLM Calls (est.)</div>
  </div>
  {(
    f'<div class="stat"><div class="val">'
    f'${cost_report["total_cost_usd"]:.2f}'
    f'</div><div class="lbl">Est. Cost (USD)</div></div>'
  ) if cost_report else ''}
</div>

<div class="container">

  <!-- ── Models ── -->
  <div class="section">
    <div class="section-title"><span class="section-icon">🤖</span> Models</div>
    <table class="models-table">
      <thead>
        <tr>
          <th>Name</th><th>Interface</th><th>Model ID</th><th>Roles</th>
          <th>Base Parameters</th><th>Role Overrides</th>
        </tr>
      </thead>
      <tbody>{model_rows_html}</tbody>
    </table>
  </div>

  <!-- ── Tasks ── -->
  <div class="section">
    <div class="section-title"><span class="section-icon">📋</span> Tasks ({len(cfg.tasks)})</div>
    {tasks_html}
  </div>

  <!-- ── Phase Plan ── -->
  <div class="section">
    <div class="section-title"><span class="section-icon">📊</span> Phase Plan &amp; Estimated Call Budget</div>
    <table class="phase-table">
      <thead>
        <tr>
          <th>Phase</th><th>Mode</th><th style="text-align:right;padding-right:28px">Calls (est.)</th><th>Notes</th>
        </tr>
      </thead>
      <tbody>
        {phase_rows_html}
        <tr class="total-row">
          <td colspan="2">Total LLM Calls</td>
          <td class="calls-count"><b>{total_calls:,}</b></td>
          <td class="phase-note">Upper-bound estimate across all models</td>
        </tr>
      </tbody>
    </table>
  </div>

  <!-- ── Cost Estimate ── -->
  {_render_cost_section(cost_report)}

  <!-- ── Provider Budget Probe ── -->
  {_render_probe_section(probe_results) if probe_results is not None else ''}

  <!-- ── Batch & Quota ── -->
  <div class="section">
    <div class="section-title"><span class="section-icon">⚙️</span> Batch &amp; Quota Configuration</div>
    {"<p><em>No batch APIs configured.</em></p>" if not batch else
     "<p><b>Batch API enabled:</b> " +
     ", ".join(f'<span class="batch-badge">{_esc(i)}/{_esc(p)}</span>' for i,p in batch) +
     " &nbsp;(50% cost reduction per API provider)</p>"}
    <br>
    <h4 style="font-size:0.85rem;color:#374151;margin-bottom:8px">Per-model call quotas</h4>
    {quota_html}
  </div>

</div>

<p class="footer">Generated by <b>coeval describe</b> · CoEval v0.3.0</p>
</body>
</html>"""


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def cmd_describe(args: argparse.Namespace) -> None:
    """Entry point for ``coeval describe``."""
    from ..config import load_config, validate_config

    # Load config
    try:
        cfg = load_config(args.config, keys_file=getattr(args, "keys", None))
    except Exception as exc:
        print(f"ERROR: Failed to load config '{args.config}': {exc}", file=sys.stderr)
        sys.exit(1)

    # Validate (skip V-11/V-14 folder checks — describe doesn't need the folder)
    errors = validate_config(cfg, _skip_folder_validation=True)
    if errors:
        print("Configuration warnings:", file=sys.stderr)
        for e in errors:
            print(f"  • {e}", file=sys.stderr)

    # Determine output path
    config_path = os.path.abspath(args.config)
    if args.out:
        out_path = Path(args.out)
    else:
        stem = Path(args.config).stem
        out_path = Path(args.config).parent / f"{stem}_description.html"

    # Optionally probe models for real latency/throughput
    probe_results = None
    if getattr(args, 'probe', False):
        print("Running provider budget probe (1 sample call per model)...")
        probe_results = _run_provider_probe(cfg)

    # Render HTML
    html_content = _render_html(cfg, config_path, probe_results=probe_results)

    # Write file
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as fh:
        fh.write(html_content)

    size_kb = out_path.stat().st_size / 1024
    print(f"Description written to: {out_path} ({size_kb:.1f} KB)")
    if not args.no_open:
        import webbrowser
        webbrowser.open(out_path.as_uri())
        print("Opened in browser.")
