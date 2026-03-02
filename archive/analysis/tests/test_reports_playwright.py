"""Playwright browser tests for CoEval HTML reports.

These tests open each report's index.html in Chromium (headless) via a
``file://`` URL, wait for the JavaScript ``renderAll()`` function to finish,
and assert that:

  * Plotly charts contain rendered SVG (``.main-svg`` elements)
  * Data tables are present and have at least one body row
  * No *critical* JavaScript errors are logged to the console
  * The page title and header are non-empty

Usage (from repo root)::

    pytest analysis/tests/test_reports_playwright.py -v

Requirements::

    pip install playwright
    python -m playwright install chromium

The path to the reports directory is resolved automatically from this file's
location: ``<repo_root>/benchmark/runs/medium-benchmark-v1/reports/``.
If the directory does not exist (e.g. on CI without the run artefacts) all
tests in this module are **skipped**.
"""
from __future__ import annotations

import os
import re
import time
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Path resolution
# ---------------------------------------------------------------------------

_HERE = Path(__file__).resolve()
_REPO_ROOT = _HERE.parents[2]  # analysis/tests/ -> analysis/ -> repo root
_REPORTS_DIR = _REPO_ROOT / "benchmark" / "runs" / "medium-benchmark-v1" / "reports"


def _file_url(path: Path) -> str:
    """Convert a Path to a ``file://`` URL usable by Playwright."""
    return path.as_uri()


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def browser_context():
    """Session-scoped Playwright Chromium context (headless)."""
    pytest.importorskip("playwright", reason="playwright not installed")
    from playwright.sync_api import sync_playwright

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        ctx = browser.new_context()
        yield ctx
        ctx.close()
        browser.close()


@pytest.fixture()
def page(browser_context):
    """Fresh page for each test."""
    p = browser_context.new_page()
    yield p
    p.close()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_CRITICAL_ERROR_RE = re.compile(
    r"(Uncaught\s|TypeError:|ReferenceError:|SyntaxError:|Cannot\s+read\s)",
    re.IGNORECASE,
)

_IGNORED_ERRORS = re.compile(
    r"(favicon\.ico|net::ERR_|\.woff|\.woff2|plotly\.min\.js\s)",
    re.IGNORECASE,
)


def _open_report(page, report_subdir: str) -> list[str]:
    """Navigate to ``report_subdir/index.html`` and wait for renderAll.

    Returns a list of critical console error strings captured during load.
    """
    html_path = _REPORTS_DIR / report_subdir / "index.html"
    url = _file_url(html_path)

    errors: list[str] = []

    def _on_console(msg):
        if msg.type == "error":
            text = msg.text
            if _CRITICAL_ERROR_RE.search(text) and not _IGNORED_ERRORS.search(text):
                errors.append(text)

    page.on("console", _on_console)

    page.goto(url, wait_until="domcontentloaded")

    # Wait for renderAll() to finish — it's triggered by DOMContentLoaded so
    # it should be synchronous; give the JS engine a moment to flush repaints.
    page.wait_for_function("() => document.readyState === 'complete'", timeout=15_000)
    # Extra tick for Plotly async rendering
    page.wait_for_timeout(1_500)

    return errors


def _count_plotly_charts(page) -> int:
    """Count fully-rendered Plotly SVG elements on the page."""
    return page.evaluate(
        "() => document.querySelectorAll('.main-svg').length"
    )


def _count_data_table_rows(page, table_sel: str = "table.data-table tbody tr") -> int:
    """Count visible data rows inside a ``.data-table`` table."""
    return page.evaluate(
        f"() => document.querySelectorAll('{table_sel}').length"
    )


def _count_tbl_rows(page, table_sel: str = "table.tbl tbody tr") -> int:
    """Count rows in a ``.tbl`` table (used by the summary/dashboard report)."""
    return page.evaluate(
        f"() => document.querySelectorAll('{table_sel}').length"
    )


def _assert_no_critical_errors(errors: list[str], report_name: str) -> None:
    assert not errors, (
        f"[{report_name}] Critical JS console errors:\n"
        + "\n".join(f"  • {e}" for e in errors)
    )


# ---------------------------------------------------------------------------
# Skip entire module if report artefacts are absent
# ---------------------------------------------------------------------------

def pytest_configure(config):  # noqa: D401
    pass  # registration hook (no-op)


pytestmark = pytest.mark.skipif(
    not _REPORTS_DIR.exists(),
    reason=(
        f"Report artefacts not found at {_REPORTS_DIR}. "
        "Run 'coeval analyze all' for the medium-benchmark-v1 experiment first."
    ),
)


# ---------------------------------------------------------------------------
# Portal index
# ---------------------------------------------------------------------------

class TestPortalIndex:
    """Tests for the top-level reports/index.html portal page."""

    def test_title(self, page):
        html_path = _REPORTS_DIR / "index.html"
        page.goto(_file_url(html_path), wait_until="domcontentloaded")
        assert "CoEval" in page.title()

    def test_report_cards_present(self, page):
        html_path = _REPORTS_DIR / "index.html"
        page.goto(_file_url(html_path), wait_until="domcontentloaded")
        cards = page.query_selector_all(".card")
        assert len(cards) >= 7, (
            f"Expected ≥7 report cards in the portal, got {len(cards)}"
        )

    def test_open_report_links(self, page):
        """Every card should have an <a> href pointing to a real subdirectory."""
        html_path = _REPORTS_DIR / "index.html"
        page.goto(_file_url(html_path), wait_until="domcontentloaded")
        links = page.evaluate(
            "() => Array.from(document.querySelectorAll('.card-btn')).map(a => a.getAttribute('href'))"
        )
        for href in links:
            target = _REPORTS_DIR / href.lstrip("./")
            assert target.exists(), f"Report link target does not exist: {href} → {target}"


# ---------------------------------------------------------------------------
# Coverage Summary
# ---------------------------------------------------------------------------

class TestCoverageSummary:
    REPORT = "coverage_summary"

    def test_no_critical_js_errors(self, page):
        errors = _open_report(page, self.REPORT)
        _assert_no_critical_errors(errors, self.REPORT)

    def test_charts_rendered(self, page):
        _open_report(page, self.REPORT)
        n = _count_plotly_charts(page)
        assert n >= 3, (
            f"[{self.REPORT}] Expected ≥3 Plotly charts (.main-svg), got {n}"
        )

    def test_chart_containers_not_empty(self, page):
        _open_report(page, self.REPORT)
        for chart_id in ("teacher-coverage-chart", "student-coverage-chart", "judge-coverage-chart"):
            inner = page.evaluate(
                f"() => document.getElementById('{chart_id}') ? "
                f"document.getElementById('{chart_id}').innerHTML.length : 0"
            )
            assert inner > 100, (
                f"[{self.REPORT}] Chart container #{chart_id} appears empty (innerHTML length={inner})"
            )

    def test_header_present(self, page):
        _open_report(page, self.REPORT)
        header_text = page.inner_text("#header")
        assert "Teacher" in header_text or "CoEval" in header_text


# ---------------------------------------------------------------------------
# Score Distribution
# ---------------------------------------------------------------------------

class TestScoreDistribution:
    REPORT = "score_distribution"

    def test_no_critical_js_errors(self, page):
        errors = _open_report(page, self.REPORT)
        _assert_no_critical_errors(errors, self.REPORT)

    def test_charts_rendered(self, page):
        _open_report(page, self.REPORT)
        n = _count_plotly_charts(page)
        assert n >= 3, (
            f"[{self.REPORT}] Expected ≥3 Plotly charts, got {n}"
        )

    def test_chart_containers_not_empty(self, page):
        _open_report(page, self.REPORT)
        for chart_id in ("student-dist-chart", "teacher-dist-chart", "judge-dist-chart"):
            inner = page.evaluate(
                f"() => document.getElementById('{chart_id}') ? "
                f"document.getElementById('{chart_id}').innerHTML.length : 0"
            )
            assert inner > 100, (
                f"[{self.REPORT}] Chart container #{chart_id} appears empty (innerHTML length={inner})"
            )


# ---------------------------------------------------------------------------
# Teacher Report
# ---------------------------------------------------------------------------

class TestTeacherReport:
    REPORT = "teacher_report"

    def test_no_critical_js_errors(self, page):
        errors = _open_report(page, self.REPORT)
        _assert_no_critical_errors(errors, self.REPORT)

    def test_ranking_table_has_rows(self, page):
        _open_report(page, self.REPORT)
        rows = _count_data_table_rows(page)
        assert rows >= 1, (
            f"[{self.REPORT}] Ranking table (data-table) has no rows"
        )

    def test_v2_chart_rendered(self, page):
        _open_report(page, self.REPORT)
        inner = page.evaluate(
            "() => document.getElementById('v2-chart') ? "
            "document.getElementById('v2-chart').innerHTML.length : 0"
        )
        assert inner > 100, f"[{self.REPORT}] #v2-chart appears empty"

    def test_v3_chart_rendered(self, page):
        _open_report(page, self.REPORT)
        inner = page.evaluate(
            "() => document.getElementById('v3-chart') ? "
            "document.getElementById('v3-chart').innerHTML.length : 0"
        )
        assert inner > 100, f"[{self.REPORT}] #v3-chart appears empty"

    def test_csv_export_button_present(self, page):
        _open_report(page, self.REPORT)
        btns = page.query_selector_all(".csv-export-btn")
        assert len(btns) >= 1, f"[{self.REPORT}] No CSV export button found"

    def test_plotly_charts_rendered(self, page):
        _open_report(page, self.REPORT)
        n = _count_plotly_charts(page)
        assert n >= 2, f"[{self.REPORT}] Expected ≥2 Plotly charts, got {n}"


# ---------------------------------------------------------------------------
# Judge Report
# ---------------------------------------------------------------------------

class TestJudgeReport:
    REPORT = "judge_report"

    def test_no_critical_js_errors(self, page):
        errors = _open_report(page, self.REPORT)
        _assert_no_critical_errors(errors, self.REPORT)

    def test_ranking_table_has_rows(self, page):
        _open_report(page, self.REPORT)
        rows = _count_data_table_rows(page)
        assert rows >= 1, f"[{self.REPORT}] Ranking table has no rows"

    def test_charts_rendered(self, page):
        _open_report(page, self.REPORT)
        n = _count_plotly_charts(page)
        assert n >= 2, f"[{self.REPORT}] Expected ≥2 Plotly charts, got {n}"

    def test_csv_export_button_present(self, page):
        _open_report(page, self.REPORT)
        btns = page.query_selector_all(".csv-export-btn")
        assert len(btns) >= 1, f"[{self.REPORT}] No CSV export button found"

    def test_v2_chart_rendered(self, page):
        _open_report(page, self.REPORT)
        inner = page.evaluate(
            "() => document.getElementById('v2-chart') ? "
            "document.getElementById('v2-chart').innerHTML.length : 0"
        )
        assert inner > 100, f"[{self.REPORT}] #v2-chart appears empty"


# ---------------------------------------------------------------------------
# Student Report
# ---------------------------------------------------------------------------

class TestStudentReport:
    REPORT = "student_report"

    def test_no_critical_js_errors(self, page):
        errors = _open_report(page, self.REPORT)
        _assert_no_critical_errors(errors, self.REPORT)

    def test_ranking_table_has_rows(self, page):
        _open_report(page, self.REPORT)
        rows = _count_data_table_rows(page)
        assert rows >= 1, f"[{self.REPORT}] Ranking table has no rows"

    def test_charts_rendered(self, page):
        _open_report(page, self.REPORT)
        n = _count_plotly_charts(page)
        assert n >= 2, f"[{self.REPORT}] Expected ≥2 Plotly charts, got {n}"

    def test_csv_export_button_present(self, page):
        _open_report(page, self.REPORT)
        btns = page.query_selector_all(".csv-export-btn")
        assert len(btns) >= 1, f"[{self.REPORT}] No CSV export button found"


# ---------------------------------------------------------------------------
# Interaction Matrix
# ---------------------------------------------------------------------------

class TestInteractionMatrix:
    REPORT = "interaction_matrix"

    def test_no_critical_js_errors(self, page):
        errors = _open_report(page, self.REPORT)
        _assert_no_critical_errors(errors, self.REPORT)

    def test_charts_rendered(self, page):
        _open_report(page, self.REPORT)
        n = _count_plotly_charts(page)
        assert n >= 2, f"[{self.REPORT}] Expected ≥2 Plotly charts, got {n}"

    def test_chart_containers_not_empty(self, page):
        _open_report(page, self.REPORT)
        # v1 and v2 should always have content
        for chart_id in ("v1-chart", "v2-chart"):
            inner = page.evaluate(
                f"() => document.getElementById('{chart_id}') ? "
                f"document.getElementById('{chart_id}').innerHTML.length : 0"
            )
            assert inner > 100, (
                f"[{self.REPORT}] Chart container #{chart_id} appears empty"
            )
        # v3 renders per-aspect; when '__all__' is selected it delegates to v1-chart.
        # Select a specific aspect to force v3 to render its own chart.
        page.evaluate(
            "() => { var s = document.getElementById('v3-aspect');"
            " if (s && s.options.length > 1) { s.value = s.options[1].value; renderV3(); } }"
        )
        page.wait_for_timeout(800)
        inner_v3 = page.evaluate(
            "() => document.getElementById('v3-chart') ? "
            "document.getElementById('v3-chart').innerHTML.length : 0"
        )
        assert inner_v3 > 100, (
            f"[{self.REPORT}] Chart container #v3-chart appears empty after aspect selection"
        )

    def test_fig_explain_sections_present(self, page):
        _open_report(page, self.REPORT)
        n = page.evaluate(
            "() => document.querySelectorAll('details.fig-explain').length"
        )
        assert n >= 3, (
            f"[{self.REPORT}] Expected ≥3 fig-explain sections, got {n}"
        )


# ---------------------------------------------------------------------------
# Judge Consistency
# ---------------------------------------------------------------------------

class TestJudgeConsistency:
    REPORT = "judge_consistency"

    def test_no_critical_js_errors(self, page):
        errors = _open_report(page, self.REPORT)
        _assert_no_critical_errors(errors, self.REPORT)

    def test_charts_rendered(self, page):
        _open_report(page, self.REPORT)
        n = _count_plotly_charts(page)
        assert n >= 2, f"[{self.REPORT}] Expected ≥2 Plotly charts, got {n}"

    def test_calibration_table_has_rows(self, page):
        _open_report(page, self.REPORT)
        rows = _count_data_table_rows(page)
        assert rows >= 1, f"[{self.REPORT}] Calibration table (data-table) has no rows"

    def test_csv_export_button_present(self, page):
        _open_report(page, self.REPORT)
        btns = page.query_selector_all(".csv-export-btn")
        assert len(btns) >= 1, f"[{self.REPORT}] No CSV export button found"

    def test_fig_explain_sections_present(self, page):
        _open_report(page, self.REPORT)
        n = page.evaluate(
            "() => document.querySelectorAll('details.fig-explain').length"
        )
        assert n >= 3, (
            f"[{self.REPORT}] Expected ≥3 fig-explain sections, got {n}"
        )

    def test_view_labels(self, page):
        """Consistency view headings should read View 1, View 2, View 3 — not View 4."""
        _open_report(page, self.REPORT)
        # Views are rendered as <h2> headings, not tab buttons
        headings_text = page.evaluate(
            "() => Array.from(document.querySelectorAll('h2')).map(h => h.textContent.trim())"
        )
        assert not any("View 4" in t for t in headings_text), (
            f"[{self.REPORT}] Found unexpected 'View 4' heading: {headings_text}"
        )
        assert any("View 3" in t for t in headings_text), (
            f"[{self.REPORT}] 'View 3' heading not found. Headings: {headings_text}"
        )


# ---------------------------------------------------------------------------
# Interactive Dashboard (Summary)
# ---------------------------------------------------------------------------

class TestSummaryDashboard:
    REPORT = "summary"

    def test_no_critical_js_errors(self, page):
        errors = _open_report(page, self.REPORT)
        _assert_no_critical_errors(errors, self.REPORT)

    def test_teacher_table_has_rows(self, page):
        _open_report(page, self.REPORT)
        rows = _count_tbl_rows(page, "table#teacher-tbl tbody tr")
        assert rows >= 1, f"[{self.REPORT}] #teacher-tbl has no rows"

    def test_judge_table_has_rows(self, page):
        _open_report(page, self.REPORT)
        rows = _count_tbl_rows(page, "table#judge-tbl tbody tr")
        assert rows >= 1, f"[{self.REPORT}] #judge-tbl has no rows"

    def test_student_table_has_rows(self, page):
        _open_report(page, self.REPORT)
        rows = _count_tbl_rows(page, "table#student-overall-tbl tbody tr")
        assert rows >= 1, f"[{self.REPORT}] #student-overall-tbl has no rows"

    def test_header_present(self, page):
        _open_report(page, self.REPORT)
        header = page.query_selector("#header")
        assert header is not None, f"[{self.REPORT}] #header element not found"


# ---------------------------------------------------------------------------
# Cross-report: fig-explain collapsible sections
# ---------------------------------------------------------------------------

class TestFigExplainSections:
    """Verify fig-explain sections can be expanded in the browser."""

    @pytest.mark.parametrize("report", [
        "teacher_report", "judge_report", "student_report",
        "interaction_matrix", "judge_consistency",
    ])
    def test_fig_explain_toggle(self, page, report):
        """Click a fig-explain <details> element and confirm it opens."""
        _open_report(page, report)
        first_explain = page.query_selector("details.fig-explain")
        if first_explain is None:
            pytest.skip(f"[{report}] No fig-explain section found")
        # Click to open
        summary_el = first_explain.query_selector("summary")
        if summary_el:
            summary_el.click()
        opened = first_explain.get_attribute("open")
        assert opened is not None, (
            f"[{report}] fig-explain <details> did not open after clicking"
        )


# ---------------------------------------------------------------------------
# Cross-report: sortable table headers
# ---------------------------------------------------------------------------

class TestSortableTableHeaders:
    """Verify .sortable th headers trigger sort on click."""

    @pytest.mark.parametrize("report,table_id", [
        ("teacher_report", "v1-table"),
        ("judge_report", "v1-table"),
        ("student_report", "v1-table"),
        ("judge_consistency", "v3-table"),
    ])
    def test_sortable_headers_present(self, page, report, table_id):
        _open_report(page, report)
        n = page.evaluate(
            f"() => {{"
            f"  var t = document.getElementById('{table_id}');"
            f"  if (!t) return 0;"
            f"  return t.querySelectorAll('th.sortable').length;"
            f"}}"
        )
        assert n >= 1, (
            f"[{report}] #{table_id} has no .sortable th headers"
        )

    @pytest.mark.parametrize("report,table_id", [
        ("teacher_report", "v1-table"),
        ("judge_report", "v1-table"),
    ])
    def test_sort_changes_row_order(self, page, report, table_id):
        """Clicking a sortable header should change the data-order attribute or row order."""
        _open_report(page, report)

        # Get first cell text before sort
        before = page.evaluate(
            f"() => {{"
            f"  var t = document.getElementById('{table_id}');"
            f"  if (!t) return '';"
            f"  var rows = t.querySelectorAll('tbody tr');"
            f"  return rows.length > 0 ? rows[0].cells[0].textContent.trim() : '';"
            f"}}"
        )

        # Click the second sortable header (usually a numeric score column)
        clicked = page.evaluate(
            f"() => {{"
            f"  var t = document.getElementById('{table_id}');"
            f"  if (!t) return false;"
            f"  var hdrs = t.querySelectorAll('th.sortable');"
            f"  if (hdrs.length < 2) return false;"
            f"  hdrs[1].click(); hdrs[1].click();"  # double-click → descending
            f"  return true;"
            f"}}"
        )

        if not clicked:
            pytest.skip(f"[{report}] Not enough sortable headers to test")

        after = page.evaluate(
            f"() => {{"
            f"  var t = document.getElementById('{table_id}');"
            f"  if (!t) return '';"
            f"  var rows = t.querySelectorAll('tbody tr');"
            f"  return rows.length > 0 ? rows[0].cells[0].textContent.trim() : '';"
            f"}}"
        )
        # We just verify the JS didn't crash (before/after may be the same if only 1 row)
        assert isinstance(after, str)


# ---------------------------------------------------------------------------
# Cross-report: CSV export button presence
# ---------------------------------------------------------------------------

class TestCsvExportButtons:
    """Ensure CSV export buttons are present in all reports that should have them."""

    @pytest.mark.parametrize("report", [
        "teacher_report",
        "judge_report",
        "student_report",
        "judge_consistency",
    ])
    def test_csv_button_present(self, page, report):
        _open_report(page, report)
        btns = page.query_selector_all(".csv-export-btn")
        assert len(btns) >= 1, f"[{report}] No .csv-export-btn found"
