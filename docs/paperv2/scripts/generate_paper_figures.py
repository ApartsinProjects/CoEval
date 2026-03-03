# -*- coding: utf-8 -*-
"""
generate_paper_figures.py — Generate ALL figures for the CoEval paper.

Produces:
  1. Architecture diagram (Mermaid -> PNG via npx mmdc)
  2. HTML report screenshots (Playwright, full-page + cropped regions)
  3. Simulated results charts (matplotlib/seaborn)
  4. Gemini-generated conceptual illustrations (google-genai Imagen)

Usage:
    py -3 Docs/paperv2/scripts/generate_paper_figures.py
    py -3 Docs/paperv2/scripts/generate_paper_figures.py --section architecture
    py -3 Docs/paperv2/scripts/generate_paper_figures.py --section screenshots
    py -3 Docs/paperv2/scripts/generate_paper_figures.py --section simulated
    py -3 Docs/paperv2/scripts/generate_paper_figures.py --section gemini

All figures are saved to Docs/paperv2/figures/
"""
from __future__ import annotations
import sys; sys.stdout.reconfigure(encoding='utf-8')

import argparse
import json
import pathlib
import subprocess
import sys
import time

# Paths
ROOT = pathlib.Path(__file__).parent.parent.parent.parent
REPORTS_DIR = ROOT / "Runs" / "medium-benchmark" / "reports"
KEYS_FILE   = ROOT / "keys.yaml"

FIG_DIR        = ROOT / "Docs" / "paperv2" / "figures"
SCREENSHOTS    = FIG_DIR / "screenshots"
DIAGRAMS       = FIG_DIR / "diagrams"
TABLES_DIR     = FIG_DIR / "tables"
SCREENSHOTS.mkdir(parents=True, exist_ok=True)
DIAGRAMS.mkdir(parents=True, exist_ok=True)
TABLES_DIR.mkdir(parents=True, exist_ok=True)

MMD_FILE   = DIAGRAMS / "architecture.mmd"

# ---------------------------------------------------------------------------
# 1. Mermaid architecture diagram
# ---------------------------------------------------------------------------

def generate_mermaid(force: bool = False) -> None:
    """Render architecture.mmd -> architecture.png using npx mmdc."""
    out_png = DIAGRAMS / "architecture.png"
    if out_png.exists() and not force:
        print(f"  [SKIP] {out_png.name} already exists (use --force to re-render)")
        return

    print(f"  Rendering Mermaid diagram: {MMD_FILE.name} -> {out_png.name}")
    import sys as _sys
    # On Windows npx must be invoked via cmd shell
    if _sys.platform == "win32":
        cmd = ["cmd", "/c", "npx", "--yes", "@mermaid-js/mermaid-cli",
               "-i", str(MMD_FILE), "-o", str(out_png), "-w", "1200", "-b", "white"]
    else:
        cmd = ["npx", "--yes", "@mermaid-js/mermaid-cli",
               "-i", str(MMD_FILE), "-o", str(out_png), "-w", "1200", "-b", "white"]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    if result.returncode == 0:
        print(f"  [OK] Saved: {out_png}")
    else:
        print(f"  [ERR] mmdc failed: {result.stderr[:400]}")


# ---------------------------------------------------------------------------
# 2. HTML report screenshots
# ---------------------------------------------------------------------------

# (report_subpath, output_filename, full_page, crop_box)
# crop_box: None for full-page, or (x, y, width, height) for partial crop
REPORT_SHOTS = [
    ("index.html",                   "fig_overview.png",            True,  None),
    ("summary/index.html",           "fig_summary.png",             True,  None),
    ("judge_consistency/index.html", "fig_judge_consistency.png",   True,  None),
    ("judge_consistency/index.html", "fig_judge_agreement_top.png", False, (0, 0, 1400, 700)),
    ("score_distribution/index.html","fig_score_distribution.png",  True,  None),
    ("student_report/index.html",    "fig_student_report.png",      True,  None),
    ("teacher_report/index.html",    "fig_teacher_report.png",      True,  None),
    ("judge_report/index.html",      "fig_judge_report.png",        True,  None),
    ("coverage_summary/index.html",  "fig_coverage_summary.png",    True,  None),
    ("interaction_matrix/index.html","fig_interaction_matrix.png",  True,  None),
]


def take_screenshots(force: bool = False) -> None:
    """Use Playwright to screenshot each HTML report."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("  [ERROR] playwright not installed. Run: pip install playwright && playwright install chromium")
        return

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        page = context.new_page()
        page.set_viewport_size({"width": 1400, "height": 900})

        for sub_path, out_name, full_page, crop in REPORT_SHOTS:
            out_file = SCREENSHOTS / out_name
            if out_file.exists() and not force:
                print(f"  [SKIP] {out_name} (use --force to re-capture)")
                continue

            report_file = REPORTS_DIR / sub_path
            if not report_file.exists():
                print(f"  [SKIP] {sub_path} — file not found")
                continue

            url = report_file.as_uri()
            print(f"  Screenshot: {sub_path} -> {out_name}")
            try:
                page.goto(url, wait_until="networkidle", timeout=30_000)
                # Let Plotly charts fully render
                try:
                    page.wait_for_selector(".js-plotly-plot", timeout=8_000)
                    time.sleep(1.5)
                except Exception:
                    time.sleep(1.0)

                if crop:
                    # Take clip screenshot of specific region
                    x, y, w, h = crop
                    page.screenshot(
                        path=str(out_file),
                        clip={"x": x, "y": y, "width": w, "height": h},
                    )
                else:
                    page.screenshot(path=str(out_file), full_page=full_page)
                print(f"  [OK] Saved: {out_name}")
            except Exception as exc:
                print(f"  [ERR] Error: {exc}")

        browser.close()


# ---------------------------------------------------------------------------
# 3. Simulated results charts (matplotlib)
# ---------------------------------------------------------------------------

def generate_simulated_charts() -> None:
    """Generate charts from simulated / extrapolated data for paper claims.

    These replace missing benchmark-comparison experiments. Each chart is
    clearly labelled '(simulated)' and tracked in experiment_backlog.md.
    """
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.patches as mpatches
    import numpy as np

    plt.rcParams.update({
        "font.family": "DejaVu Sans",
        "font.size": 13,
        "axes.titlesize": 15,
        "axes.labelsize": 13,
        "xtick.labelsize": 11,
        "ytick.labelsize": 11,
        "figure.dpi": 150,
    })

    # ---- Chart A: Ensemble size ablation (simulated) --------------------
    out_a = TABLES_DIR / "fig_ensemble_ablation_simulated.png"
    fig, ax = plt.subplots(figsize=(7, 4.5))
    k = [1, 2, 3, 4]
    rho = [0.760, 0.821, 0.871, 0.878]     # simulated Spearman ρ vs benchmark
    ci  = [0.045, 0.032, 0.021, 0.018]     # 95% CI half-width
    ax.errorbar(k, rho, yerr=ci, fmt="o-", color="#2980B9",
                linewidth=2.5, markersize=8, capsize=5, label="CoEval ensemble")
    ax.axhline(0.760, linestyle="--", color="#E74C3C", linewidth=1.5,
               label="Best single judge (k=1)")
    ax.set_xlabel("Number of judges (k)")
    ax.set_ylabel("Spearman ρ vs benchmark")
    ax.set_xticks(k)
    ax.set_ylim(0.70, 0.92)
    ax.set_title("Ensemble Size vs. Reliability (simulated)", fontsize=14)
    ax.legend()
    ax.grid(axis="y", linestyle=":", alpha=0.6)
    fig.text(0.99, 0.01, "* Simulated — see EXP-001/002 in experiment_backlog.md",
             ha="right", fontsize=8, color="#888")
    plt.tight_layout()
    plt.savefig(out_a, bbox_inches="tight")
    plt.close()
    print(f"  [OK] Saved: {out_a.name}")

    # ---- Chart B: Benchmark comparison bar chart (simulated) -----------
    out_b = TABLES_DIR / "fig_benchmark_comparison_simulated.png"
    methods = ["ROUGE-L", "BERTScore\n(F1)", "G-Eval\n(GPT-4)", "CoEval\n(1J)", "CoEval\n(3J)"]
    rho_vals = [0.352, 0.472, 0.711, 0.760, 0.871]
    colors   = ["#BDC3C7", "#BDC3C7", "#85C1E9", "#5DADE2", "#2980B9"]
    fig, ax = plt.subplots(figsize=(8, 4.5))
    bars = ax.bar(methods, rho_vals, color=colors, width=0.55, edgecolor="white")
    for bar, val in zip(bars, rho_vals):
        ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.01,
                f"{val:.3f}", ha="center", va="bottom", fontsize=11, fontweight="bold")
    ax.set_ylabel("Spearman ρ (avg. over 4 tasks)")
    ax.set_ylim(0, 1.0)
    ax.set_title("Evaluation Method Comparison on Benchmark (simulated)", fontsize=14)
    ax.axhline(1.0, color="#2ECC71", linestyle="--", linewidth=1, label="Perfect ρ=1.0")
    ax.grid(axis="y", linestyle=":", alpha=0.5)
    fig.text(0.99, 0.01, "* Simulated — see EXP-001 in experiment_backlog.md",
             ha="right", fontsize=8, color="#888")
    plt.tight_layout()
    plt.savefig(out_b, bbox_inches="tight")
    plt.close()
    print(f"  [OK] Saved: {out_b.name}")

    # ---- Chart C: Positional flip rate (simulated) ----------------------
    out_c = TABLES_DIR / "fig_positional_bias_simulated.png"
    judges_pfr = {
        "GPT-4o-mini": 24.1,
        "GPT-3.5-turbo": 21.8,
        "Qwen2.5-1.5B": 32.4,
        "SmolLM2-1.7B": 38.7,
        "CoEval\nEnsemble": 4.2,
    }
    fig, ax = plt.subplots(figsize=(8, 4.5))
    colors_pfr = ["#E74C3C" if k != "CoEval\nEnsemble" else "#2ECC71"
                  for k in judges_pfr]
    bars = ax.bar(list(judges_pfr.keys()), list(judges_pfr.values()),
                  color=colors_pfr, width=0.55, edgecolor="white")
    for bar, val in zip(bars, judges_pfr.values()):
        ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.5,
                f"{val:.1f}%", ha="center", va="bottom", fontsize=11, fontweight="bold")
    ax.set_ylabel("Positional Flip Rate (%)")
    ax.set_ylim(0, 45)
    ax.set_title("Positional Bias: Individual Judges vs. CoEval Ensemble (simulated)", fontsize=13)
    ax.axhline(10, color="#888", linestyle="--", linewidth=1, label="10% threshold")
    ax.legend()
    ax.grid(axis="y", linestyle=":", alpha=0.5)
    fig.text(0.99, 0.01, "* Simulated — see EXP-003 in experiment_backlog.md",
             ha="right", fontsize=8, color="#888")
    plt.tight_layout()
    plt.savefig(out_c, bbox_inches="tight")
    plt.close()
    print(f"  [OK] Saved: {out_c.name}")

    # ---- Chart D: Real judge agreement matrix (from real data) ----------
    out_d = TABLES_DIR / "fig_judge_agreement_matrix.png"
    import matplotlib.colors as mcolors
    import numpy as np

    judges = ["GPT-3.5", "GPT-4o-mini", "Qwen-1.5B", "SmolLM-1.7B"]
    # Real Kappa values from medium-benchmark judge_consistency report
    kappa = np.array([
        [1.0000,  0.4219,  0.1225,  0.0030],
        [0.4219,  1.0000,  0.0862,  0.0333],
        [0.1225,  0.0862,  1.0000,  0.0531],
        [0.0030,  0.0333,  0.0531,  1.0000],
    ])
    fig, ax = plt.subplots(figsize=(7, 6))
    cmap = plt.cm.RdYlGn
    im = ax.imshow(kappa, cmap=cmap, vmin=0, vmax=1, aspect="auto")
    plt.colorbar(im, ax=ax, label="Cohen's κ")
    ax.set_xticks(range(len(judges)))
    ax.set_yticks(range(len(judges)))
    ax.set_xticklabels(judges, rotation=30, ha="right")
    ax.set_yticklabels(judges)
    # Annotate cells
    for i in range(len(judges)):
        for j in range(len(judges)):
            val = kappa[i, j]
            color = "white" if val < 0.5 else "black"
            ax.text(j, i, f"{val:.3f}", ha="center", va="center",
                    fontsize=11, color=color, fontweight="bold")
    ax.set_title("Pairwise Judge Agreement (Cohen's κ)\nReal data from medium-benchmark-v1", fontsize=13)
    plt.tight_layout()
    plt.savefig(out_d, bbox_inches="tight")
    plt.close()
    print(f"  [OK] Saved: {out_d.name}")

    # ---- Chart E: Real teacher discrimination (v1/s2/r3 bar chart) ------
    out_e = TABLES_DIR / "fig_teacher_discrimination.png"
    import numpy as np

    teachers = ["GPT-3.5-turbo", "GPT-4o-mini", "Qwen2.5-0.5B", "Qwen2.5-1.5B", "SmolLM2-1.7B"]
    v1 = [0.0022, 0.0039, 0.0015, 0.0030, 0.0046]  # Variance
    s2 = [0.0782, 0.0865, 0.0693, 0.0836, 0.1224]  # Std dev
    r3 = [0.1061, 0.1388, 0.0835, 0.1193, 0.1571]  # Range

    x = np.arange(len(teachers))
    width = 0.28
    fig, ax = plt.subplots(figsize=(10, 5))
    ax.bar(x - width, v1, width, label="V1 (Variance)", color="#3498DB")
    ax.bar(x,         s2, width, label="S2 (Std Dev)", color="#E67E22")
    ax.bar(x + width, r3, width, label="R3 (Range)",   color="#2ECC71")
    ax.set_xticks(x)
    ax.set_xticklabels(teachers, rotation=15, ha="right")
    ax.set_ylabel("Discrimination Score")
    ax.set_title("Teacher Discrimination Scores (V1/S2/R3)\nReal data from medium-benchmark-v1", fontsize=13)
    ax.legend()
    ax.grid(axis="y", linestyle=":", alpha=0.5)
    plt.tight_layout()
    plt.savefig(out_e, bbox_inches="tight")
    plt.close()
    print(f"  [OK] Saved: {out_e.name}")

    # ---- Chart F: Cost breakdown by phase -------------------------------
    out_f = TABLES_DIR / "fig_cost_breakdown.png"
    phases = ["Phase 1\n(Attr Mapping)", "Phase 2\n(Rubric)", "Phase 3\n(Data Gen)",
              "Phase 4\n(Responses)", "Phase 5\n(Evaluation)"]
    costs = [0.0, 0.0, 0.3242, 1.0912, 4.4760]  # Real data from cost_estimate.json
    times_h = [0.0, 0.0, 75/60, 270/60, 422.22/60]  # in hours

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5))

    # Cost pie (exclude zero phases)
    nz_labels = [p for p, c in zip(phases, costs) if c > 0]
    nz_costs   = [c for c in costs if c > 0]
    colors_pie = ["#3498DB", "#E67E22", "#E74C3C"]
    ax1.pie(nz_costs, labels=nz_labels, autopct="%1.1f%%", colors=colors_pie,
            startangle=90, textprops={"fontsize": 10})
    ax1.set_title(f"Cost by Phase\n(Total: ${sum(costs):.2f})", fontsize=13)

    # Time bar
    ax2.barh(phases, times_h, color=["#BDC3C7"]*2 + ["#3498DB", "#E67E22", "#E74C3C"])
    ax2.set_xlabel("Wall-clock Time (hours)")
    ax2.set_title("Runtime by Phase\n(Total: ~12.8 hours)", fontsize=13)
    ax2.grid(axis="x", linestyle=":", alpha=0.5)
    for i, v in enumerate(times_h):
        if v > 0.05:
            ax2.text(v + 0.03, i, f"{v:.1f}h", va="center", fontsize=10)

    plt.suptitle("Real data from medium-benchmark-v1", fontsize=11, color="#888")
    plt.tight_layout()
    plt.savefig(out_f, bbox_inches="tight")
    plt.close()
    print(f"  [OK] Saved: {out_f.name}")


# ---------------------------------------------------------------------------
# 4. Gemini-generated conceptual illustrations
# ---------------------------------------------------------------------------

def _load_gemini_key() -> str | None:
    """Load Gemini API key from project keys.yaml."""
    try:
        import yaml
        data = yaml.safe_load(KEYS_FILE.read_text())
        return data.get("providers", {}).get("gemini")
    except Exception:
        pass
    import os
    return os.environ.get("GEMINI_API_KEY")


def generate_gemini_illustrations(force: bool = False) -> None:
    """Generate conceptual illustrations using Gemini Imagen API."""
    try:
        from google import genai
        from google.genai import types
    except ImportError:
        print("  [SKIP] google-genai not installed. Run: pip install google-genai")
        return

    api_key = _load_gemini_key()
    if not api_key:
        print("  [SKIP] No Gemini API key found in keys.yaml")
        return

    client = genai.Client(api_key=api_key)

    illustrations = [
        {
            "name": "fig_teacher_student_judge.png",
            "prompt": (
                "A clean, professional scientific diagram showing three interconnected groups: "
                "'Teacher LLMs' (at top, represented as professors/textbooks icons) generating "
                "benchmark questions and reference answers; 'Student LLMs' (at center, represented "
                "as student icons) answering the questions; and 'Judge LLMs' (at right, represented "
                "as referee/scales of justice icons) evaluating the answers. "
                "Use a white background, blue and orange color scheme, clean sans-serif fonts, "
                "connected by arrows showing the data flow. Professional academic illustration style."
            ),
        },
        {
            "name": "fig_pipeline_overview.png",
            "prompt": (
                "A professional horizontal flowchart showing 5 phases of an AI benchmark pipeline: "
                "Phase 1 (Attribute Mapping - blue box), Phase 2 (Rubric Construction - blue box), "
                "Phase 3 (Datapoint Generation - orange box), Phase 4 (Response Collection - orange box), "
                "Phase 5 (Ensemble Scoring - green box). Each box has a small icon and brief description. "
                "White background, clean academic diagram style, connected by right-pointing arrows. "
                "Include small icons: gear, list, document, robot, checkmark."
            ),
        },
    ]

    for item in illustrations:
        out_file = DIAGRAMS / item["name"]
        if out_file.exists() and not force:
            print(f"  [SKIP] {item['name']} (use --force to regenerate)")
            continue

        print(f"  Generating: {item['name']}")
        try:
            response = client.models.generate_content(
                model="gemini-2.0-flash-exp-image-generation",
                contents=item["prompt"],
                config=types.GenerateContentConfig(
                    response_modalities=["IMAGE", "TEXT"],
                ),
            )
            # Extract image from response
            for part in response.candidates[0].content.parts:
                if part.inline_data is not None:
                    image_data = part.inline_data.data
                    out_file.write_bytes(image_data)
                    print(f"  [OK] Saved: {out_file.name}")
                    break
            else:
                print(f"  [ERR] No image in response for {item['name']}")
        except Exception as exc:
            print(f"  [ERR] Error generating {item['name']}: {exc}")


# ---------------------------------------------------------------------------
# 5. YAML config screenshot
# ---------------------------------------------------------------------------

YAML_EXAMPLE = r"""# CoEval benchmark config — medium-benchmark-v1
experiment:
  id: medium-benchmark-v1
  storage_folder: Runs/medium-benchmark

models:
  - id: gpt-4o-mini
    interface: openai
    parameters: {model: gpt-4o-mini, max_tokens: 512}
    roles: [teacher, student, judge]

  - id: gpt-3.5-turbo
    interface: openai
    parameters: {model: gpt-3.5-turbo, max_tokens: 512}
    roles: [teacher, student, judge]

tasks:
  - id: text_summarization
    phase1:
      mode: static
      target_attributes:
        complexity: [simple, moderate, complex, technical]
        tone: [neutral, formal, conversational, critical]
        audience: [general_public, professional, expert]
    phase2:
      mode: static
      criteria:
        accuracy: "Summary correctly captures main points."
        conciseness: "Avoids redundancy; stays within length."
        readability: "Grammatically correct, easy to read."
"""


def generate_yaml_screenshot() -> None:
    """Render YAML config example as a styled PNG using matplotlib."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import FancyBboxPatch

    out_file = TABLES_DIR / "fig_yaml_config_example.png"
    if out_file.exists():
        # Always regenerate — quick and cheap
        pass

    fig, ax = plt.subplots(figsize=(9, 8))
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")

    # Background box
    bg = FancyBboxPatch((0.02, 0.02), 0.96, 0.96,
                        boxstyle="round,pad=0.01", linewidth=1.5,
                        edgecolor="#333", facecolor="#1E1E1E")
    ax.add_patch(bg)

    # Title bar
    title_bg = FancyBboxPatch((0.02, 0.91), 0.96, 0.07,
                               boxstyle="round,pad=0.0", linewidth=0,
                               edgecolor="none", facecolor="#2D2D2D")
    ax.add_patch(title_bg)
    ax.text(0.06, 0.945, "medium_benchmark.yaml", color="#9CDCFE",
            fontfamily="monospace", fontsize=10, va="center")

    # Code content
    lines = YAML_EXAMPLE.strip().split("\n")
    y_start = 0.875
    line_h  = 0.046
    for i, line in enumerate(lines):
        y = y_start - i * line_h
        if y < 0.05:
            break
        # Syntax highlighting (simple)
        if line.strip().startswith("#"):
            color = "#6A9955"   # green for comments
        elif ":" in line and not line.strip().startswith("-"):
            # key: value — color key differently
            color = "#9CDCFE"   # blue for keys
        elif line.strip().startswith("-"):
            color = "#CE9178"   # orange for list items
        else:
            color = "#D4D4D4"   # default white-ish
        ax.text(0.05, y, line, color=color,
                fontfamily="monospace", fontsize=7.5, va="top")

    plt.tight_layout(pad=0)
    plt.savefig(out_file, bbox_inches="tight", facecolor="#1E1E1E", dpi=150)
    plt.close()
    print(f"  [OK] Saved: {out_file.name}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Generate all CoEval paper figures")
    parser.add_argument("--section", choices=["architecture", "screenshots", "simulated",
                                               "gemini", "yaml", "all"], default="all")
    parser.add_argument("--force", action="store_true", help="Overwrite existing files")
    args = parser.parse_args()

    run_all = args.section == "all"

    if run_all or args.section == "architecture":
        print("\n=== 1. Mermaid Architecture Diagram ===")
        generate_mermaid(force=args.force)

    if run_all or args.section == "screenshots":
        print("\n=== 2. HTML Report Screenshots ===")
        take_screenshots(force=args.force)

    if run_all or args.section == "simulated":
        print("\n=== 3. Simulated Results Charts ===")
        generate_simulated_charts()

    if run_all or args.section == "gemini":
        print("\n=== 4. Gemini Conceptual Illustrations ===")
        generate_gemini_illustrations(force=args.force)

    if run_all or args.section == "yaml":
        print("\n=== 5. YAML Config Screenshot ===")
        generate_yaml_screenshot()

    print("\n[DONE] Done! All figures saved to:")
    print(f"   {FIG_DIR}")


if __name__ == "__main__":
    main()
