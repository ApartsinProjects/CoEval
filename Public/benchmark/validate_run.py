#!/usr/bin/env python3
# validate_run.py -- CoEval run validator
# Scans a run folder and reports statistics and sanity issues.
# Usage: python benchmark/validate_run.py --run <run_folder_path>

from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:
    print("ERROR: PyYAML not installed. Run: pip install pyyaml", file=sys.stderr)
    sys.exit(1)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

VALID_SCORES = {"High", "Medium", "Low"}
P3_REQUIRED_FIELDS = {"id", "prompt", "reference_response", "generated_at"}
P4_REQUIRED_FIELDS = {"id", "response", "datapoint_id"}
P5_REQUIRED_FIELDS = {"id", "scores", "response_id"}

# ---------------------------------------------------------------------------
# Config helpers
# ---------------------------------------------------------------------------

def load_config(run_path: Path) -> dict:
    config_file = run_path / "config.yaml"
    if not config_file.exists():
        print(f"ERROR: config.yaml not found at {config_file}", file=sys.stderr)
        sys.exit(1)
    with config_file.open("r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def parse_config(config: dict):
    tasks = [t["name"] for t in config.get("tasks", [])]
    teachers, students, judges = [], [], []
    for model in config.get("models", []):
        name = model["name"]
        roles = model.get("roles", [])
        if "teacher" in roles:
            teachers.append(name)
        if "student" in roles:
            students.append(name)
        if "judge" in roles:
            judges.append(name)
    return tasks, teachers, students, judges


def get_items_per_task(config: dict) -> dict:
    result = {}
    for task in config.get("tasks", []):
        total = task.get("sampling", {}).get("total", None)
        result[task["name"]] = int(total) if total is not None else 0
    return result

# ---------------------------------------------------------------------------
# JSONL reader
# ---------------------------------------------------------------------------

def read_jsonl(path: Path):
    """Read a JSONL file. Return (valid_records, parse_errors)."""
    valid = []
    errors = []
    try:
        with path.open("r", encoding="utf-8") as fh:
            for lineno, raw in enumerate(fh, start=1):
                raw = raw.strip()
                if not raw:
                    continue
                try:
                    obj = json.loads(raw)
                    valid.append(obj)
                except json.JSONDecodeError as exc:
                    errors.append((lineno, str(exc)))
    except OSError as exc:
        errors.append((0, f"Cannot open file: {exc}"))
    return valid, errors


# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------

def pct(num: int, den: int) -> str:
    if den == 0:
        return "  N/A"
    return f"{num / den * 100:5.1f}%"


class TablePrinter:
    def __init__(self, headers, col_widths):
        self.headers = headers
        self.col_widths = col_widths

    def _fmt(self, row):
        parts = [str(v).ljust(w) for v, w in zip(row, self.col_widths)]
        return "  ".join(parts)

    def print_header(self):
        print(self._fmt(self.headers))
        print(self._fmt(["-" * w for w in self.col_widths]))

    def print_row(self, row):
        print(self._fmt(row))

# ---------------------------------------------------------------------------
# Phase 3 validator
# ---------------------------------------------------------------------------

def validate_phase3(run_path, tasks, teachers, items_per_task):
    phase_dir = run_path / "phase3_datapoints"
    stats, issues = [], []

    for task in tasks:
        expected = items_per_task.get(task, 0)
        for teacher in teachers:
            filename = f"{task}.{teacher}.datapoints.jsonl"
            filepath = phase_dir / filename
            exists = filepath.exists()

            if not exists:
                stats.append(dict(task=task, teacher=teacher, exists=False,
                                  line_count=0, expected=expected, ids=set()))
                issues.append(f"[P3] MISSING  {filename}")
                continue

            records, parse_errors = read_jsonl(filepath)
            for lineno, msg in parse_errors:
                issues.append(f"[P3] BAD_JSON {filename}:{lineno} -- {msg}")
            if len(records) == 0:
                issues.append(f"[P3] EMPTY    {filename} -- 0 valid lines")

            ids = set()
            for i, rec in enumerate(records, start=1):
                for field in P3_REQUIRED_FIELDS:
                    if field not in rec:
                        issues.append(
                            f"[P3] MISSING_FIELD {filename}:{i} -- missing field: {field!r}")
                if "id" in rec:
                    ids.add(rec["id"])

            stats.append(dict(task=task, teacher=teacher, exists=True,
                              line_count=len(records), expected=expected, ids=ids))

    return stats, issues

# ---------------------------------------------------------------------------
# Phase 4 validator
# ---------------------------------------------------------------------------

def validate_phase4(run_path, tasks, teachers, students, phase3_stats):
    """Expected per file = number of valid datapoints the teacher produced."""
    phase_dir = run_path / "phase4_responses"
    p3_lookup = {(s["task"], s["teacher"]): s for s in phase3_stats}
    stats, issues = [], []

    for task in tasks:
        for teacher in teachers:
            p3_entry = p3_lookup.get((task, teacher), {})
            expected = p3_entry.get("line_count", 0)
            known_ids = p3_entry.get("ids", set())

            for student in students:
                filename = f"{task}.{teacher}.{student}.responses.jsonl"
                filepath = phase_dir / filename
                exists = filepath.exists()

                if not exists:
                    stats.append(dict(task=task, teacher=teacher, student=student,
                                      exists=False, line_count=0, expected=expected))
                    issues.append(f"[P4] MISSING  {filename}")
                    continue

                records, parse_errors = read_jsonl(filepath)
                for lineno, msg in parse_errors:
                    issues.append(f"[P4] BAD_JSON {filename}:{lineno} -- {msg}")
                if len(records) == 0:
                    issues.append(f"[P4] EMPTY    {filename} -- 0 valid lines")

                for i, rec in enumerate(records, start=1):
                    for field in P4_REQUIRED_FIELDS:
                        if field not in rec:
                            issues.append(
                                f"[P4] MISSING_FIELD {filename}:{i} -- missing field: {field!r}")
                    dpid = rec.get("datapoint_id")
                    if dpid is not None and known_ids and dpid not in known_ids:
                        issues.append(
                            f"[P4] BAD_REF  {filename}:{i} -- "
                            f"datapoint_id {dpid!r} not found in phase3 file")

                stats.append(dict(task=task, teacher=teacher, student=student,
                                  exists=True, line_count=len(records), expected=expected))

    return stats, issues

# ---------------------------------------------------------------------------
# Phase 5 validator
# ---------------------------------------------------------------------------

def validate_phase5(run_path, tasks, teachers, judges, phase4_stats):
    """Expected per file = total responses for that teacher (all students combined)."""
    phase_dir = run_path / "phase5_evaluations"

    # Sum phase4 line counts per (task, teacher) across all students
    p4_totals: dict = {}
    for s in phase4_stats:
        key = (s["task"], s["teacher"])
        p4_totals[key] = p4_totals.get(key, 0) + s["line_count"]

    stats, issues = [], []

    for task in tasks:
        for teacher in teachers:
            expected = p4_totals.get((task, teacher), 0)
            for judge in judges:
                filename = f"{task}.{teacher}.{judge}.evaluations.jsonl"
                filepath = phase_dir / filename
                exists = filepath.exists()

                if not exists:
                    stats.append(dict(task=task, teacher=teacher, judge=judge,
                                      exists=False, line_count=0, expected=expected))
                    issues.append(f"[P5] MISSING  {filename}")
                    continue

                records, parse_errors = read_jsonl(filepath)
                for lineno, msg in parse_errors:
                    issues.append(f"[P5] BAD_JSON {filename}:{lineno} -- {msg}")
                if len(records) == 0:
                    issues.append(f"[P5] EMPTY    {filename} -- 0 valid lines")

                for i, rec in enumerate(records, start=1):
                    for field in P5_REQUIRED_FIELDS:
                        if field not in rec:
                            issues.append(
                                f"[P5] MISSING_FIELD {filename}:{i} -- missing field: {field!r}")
                    scores = rec.get("scores")
                    if scores is not None:
                        if not isinstance(scores, dict):
                            issues.append(
                                f"[P5] BAD_SCORES {filename}:{i} -- "
                                f"scores is not a dict (got {type(scores).__name__})")
                        else:
                            for criterion, value in scores.items():
                                if value not in VALID_SCORES:
                                    issues.append(
                                        f"[P5] BAD_SCORE_VALUE {filename}:{i} -- "
                                        f"scores[{criterion!r}]={value!r} "
                                        f"(expected one of {sorted(VALID_SCORES)})")

                stats.append(dict(task=task, teacher=teacher, judge=judge,
                                  exists=True, line_count=len(records), expected=expected))

    return stats, issues

# ---------------------------------------------------------------------------
# Table printers
# ---------------------------------------------------------------------------

def print_phase3_table(stats):
    print()
    print("=" * 72)
    print("PHASE 3 -- Data Generation  (task x teacher)")
    print("=" * 72)
    tp = TablePrinter(
        ["Task", "Teacher", "Exists", "Lines", "Expected", "Complete"],
        [24, 18, 6, 6, 8, 9])
    tp.print_header()
    total_lines = total_expected = 0
    for s in stats:
        exists_str = "yes" if s["exists"] else "NO"
        complete_str = pct(s["line_count"], s["expected"]) if s["exists"] else "  ---"
        tp.print_row([s["task"], s["teacher"], exists_str,
                      str(s["line_count"]), str(s["expected"]), complete_str])
        total_lines += s["line_count"]
        total_expected += s["expected"]
    print()
    p = pct(total_lines, total_expected)
    print(f"  Total: {total_lines}/{total_expected} lines  ({p} complete)")


def print_phase4_table(stats):
    print()
    print("=" * 88)
    print("PHASE 4 -- Response Collection  (task x teacher x student)")
    print("=" * 88)
    tp = TablePrinter(
        ["Task", "Teacher", "Student", "Exists", "Lines", "Expected", "Complete"],
        [24, 18, 14, 6, 6, 8, 9])
    tp.print_header()
    total_lines = total_expected = 0
    for s in stats:
        exists_str = "yes" if s["exists"] else "NO"
        complete_str = pct(s["line_count"], s["expected"]) if s["exists"] else "  ---"
        tp.print_row([s["task"], s["teacher"], s["student"], exists_str,
                      str(s["line_count"]), str(s["expected"]), complete_str])
        total_lines += s["line_count"]
        total_expected += s["expected"]
    print()
    p = pct(total_lines, total_expected)
    print(f"  Total: {total_lines}/{total_expected} lines  ({p} complete)")


def print_phase5_table(stats):
    print()
    print("=" * 88)
    print("PHASE 5 -- Evaluation  (task x teacher x judge)")
    print("=" * 88)
    tp = TablePrinter(
        ["Task", "Teacher", "Judge", "Exists", "Lines", "Expected", "Complete"],
        [24, 18, 14, 6, 6, 8, 9])
    tp.print_header()
    total_lines = total_expected = 0
    for s in stats:
        exists_str = "yes" if s["exists"] else "NO"
        complete_str = pct(s["line_count"], s["expected"]) if s["exists"] else "  ---"
        tp.print_row([s["task"], s["teacher"], s["judge"], exists_str,
                      str(s["line_count"]), str(s["expected"]), complete_str])
        total_lines += s["line_count"]
        total_expected += s["expected"]
    print()
    p = pct(total_lines, total_expected)
    print(f"  Total: {total_lines}/{total_expected} lines  ({p} complete)")


def print_issues(all_issues):
    print()
    print("=" * 72)
    print("SANITY CHECK ISSUES")
    print("=" * 72)
    if not all_issues:
        print()
        print("  (none)")
        return
    tag_labels = [("[P3]", "Phase 3"), ("[P4]", "Phase 4"), ("[P5]", "Phase 5")]
    for tag, label in tag_labels:
        phase_issues = [x for x in all_issues if x.startswith(tag)]
        if phase_issues:
            n = len(phase_issues)
            print(); print("  -- " + label + " (" + str(n) + " issue(s)) --")
            for iss in phase_issues:
                print(f"  {iss}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Validate a CoEval run folder -- statistics and sanity checks.")
    parser.add_argument("--run", required=True, metavar="PATH",
        help="Path to the run folder (e.g. benchmark/runs/medium-benchmark-v1)")
    args = parser.parse_args()

    run_path = Path(args.run).resolve()
    if not run_path.exists():
        print(f"ERROR: Run folder not found: {run_path}", file=sys.stderr)
        sys.exit(1)

    print(f"Validating run: {run_path}")

    config = load_config(run_path)
    tasks, teachers, students, judges = parse_config(config)
    items_per_task = get_items_per_task(config)

    exp_id = config.get("experiment", {}).get("id", "(unknown)")
    print(f"Experiment ID : {exp_id}")
    print(f"Tasks         : {", ".join(tasks)}")
    print(f"Teachers      : {", ".join(teachers)}")
    print(f"Students      : {", ".join(students)}")
    print(f"Judges        : {", ".join(judges)}")

    p3_stats, p3_issues = validate_phase3(run_path, tasks, teachers, items_per_task)
    print_phase3_table(p3_stats)

    p4_stats, p4_issues = validate_phase4(run_path, tasks, teachers, students, p3_stats)
    print_phase4_table(p4_stats)

    p5_stats, p5_issues = validate_phase5(run_path, tasks, teachers, judges, p4_stats)
    print_phase5_table(p5_stats)

    all_issues = p3_issues + p4_issues + p5_issues
    print_issues(all_issues)

    # Count unique filenames that have at least one issue
    files_with_issues = set()
    for iss in all_issues:
        parts = iss.split()
        if len(parts) >= 3:
            candidate = parts[2].split(":")[0]
            if "." in candidate:
                files_with_issues.add(candidate)

    print()
    print("=" * 72)
    if not all_issues:
        print("All files passed sanity checks.")
    else:
        n_iss = len(all_issues)
        n_files = len(files_with_issues)
        print(f"{n_iss} issue(s) found across {n_files} file(s).")
    print("=" * 72)


if __name__ == "__main__":
    main()
