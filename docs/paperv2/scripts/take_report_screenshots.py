"""
take_report_screenshots.py — Screenshot all medium-benchmark HTML reports for paper figures.

Usage:
    py -3 Docs/paperv2/scripts/take_report_screenshots.py

Saves screenshots to Docs/paperv2/figures/screenshots/
"""
from __future__ import annotations

import pathlib
import time
from playwright.sync_api import sync_playwright

# Paths
ROOT = pathlib.Path(__file__).parent.parent.parent.parent
REPORTS_DIR = ROOT / "Runs" / "medium-benchmark" / "reports"
OUT_DIR = ROOT / "Docs" / "paperv2" / "figures" / "screenshots"
OUT_DIR.mkdir(parents=True, exist_ok=True)

# Report pages to screenshot
PAGES = [
    # (report_subpath, output_filename, viewport_width, viewport_height, wait_selector)
    ("index.html",                      "fig_overview.png",           1400, 900,  "body"),
    ("summary/index.html",              "fig_summary.png",            1400, 1000, "body"),
    ("judge_consistency/index.html",    "fig_judge_consistency.png",  1400, 1100, "body"),
    ("score_distribution/index.html",   "fig_score_distribution.png", 1400, 900,  "body"),
    ("student_report/index.html",       "fig_student_report.png",     1400, 1000, "body"),
    ("teacher_report/index.html",       "fig_teacher_report.png",     1400, 1000, "body"),
    ("judge_report/index.html",         "fig_judge_report.png",       1400, 1000, "body"),
    ("coverage_summary/index.html",     "fig_coverage_summary.png",   1400, 900,  "body"),
    ("interaction_matrix/index.html",   "fig_interaction_matrix.png", 1400, 900,  "body"),
]


def screenshot_report(page, report_path: pathlib.Path, out_path: pathlib.Path,
                       width: int, height: int, wait_selector: str) -> None:
    """Navigate to a local HTML report and take a full-page screenshot."""
    url = report_path.as_uri()
    print(f"  Navigating to: {url}")
    page.set_viewport_size({"width": width, "height": height})
    page.goto(url, wait_until="networkidle", timeout=30_000)

    # Wait for Plotly charts to render
    try:
        page.wait_for_selector(".js-plotly-plot", timeout=8_000)
        time.sleep(1.5)  # Let animations settle
    except Exception:
        time.sleep(1.0)  # Fallback: just wait a bit

    page.screenshot(path=str(out_path), full_page=True)
    print(f"  Saved: {out_path.name}")


def main():
    print(f"Reports dir: {REPORTS_DIR}")
    print(f"Output dir:  {OUT_DIR}")
    print()

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        page = context.new_page()

        for sub_path, out_name, w, h, sel in PAGES:
            report_file = REPORTS_DIR / sub_path
            if not report_file.exists():
                print(f"  [SKIP] {sub_path} — file not found")
                continue
            out_file = OUT_DIR / out_name
            print(f"Screenshot: {sub_path}")
            try:
                screenshot_report(page, report_file, out_file, w, h, sel)
            except Exception as exc:
                print(f"  [ERROR] {exc}")

        browser.close()

    print(f"\nDone! Screenshots saved to {OUT_DIR}")


if __name__ == "__main__":
    main()
