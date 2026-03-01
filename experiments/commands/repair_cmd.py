"""coeval repair — scan for invalid phase records and mark them for re-generation.

Scans Phase 3 (datapoints), Phase 4 (responses), and Phase 5 (evaluations)
JSONL files for invalid records — empty required fields, JSON parse errors,
or existing ``status='failed'`` markers — and marks them with
``status='failed'`` so that a subsequent ``coeval run --continue`` regenerates
only the minimum necessary set.

**What counts as invalid?**

+--------+--------------------+-------------------------------------------+
| Phase  | JSONL suffix       | Invalid when …                            |
+========+====================+===========================================+
| 3      | ``.datapoints``    | ``reference_response`` is ``''`` / null   |
|        |                    | or record already has ``status='failed'`` |
+--------+--------------------+-------------------------------------------+
| 4      | ``.responses``     | ``response`` is ``''`` / null             |
|        |                    | or record already has ``status='failed'`` |
+--------+--------------------+-------------------------------------------+
| 5      | ``.evaluations``   | ``scores`` is missing / all-null          |
|        |                    | or record already has ``status='failed'`` |
+--------+--------------------+-------------------------------------------+

Any unparseable JSONL line is also reported as invalid.

**Workflow**::

    # 1. Scan only — print report without modifying anything
    coeval repair --run benchmark/runs/my-exp --dry-run

    # 2. Scan and mark invalid records as failed (in-place file rewrite)
    coeval repair --run benchmark/runs/my-exp

    # 3. Re-generate the marked records
    coeval run --config my-experiment.yaml --continue

After step 2 the experiment's JSONL files are updated in-place: previously
invalid records gain ``"status": "failed"``, which causes the existing
Extend-mode skip logic in phases 3–5 to treat them as missing and regenerate
them on the next ``--continue`` run.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from collections import defaultdict

import argparse


# ---------------------------------------------------------------------------
# Validity criteria per phase
# ---------------------------------------------------------------------------

def _is_invalid_p3(rec: dict) -> bool:
    """Phase 3 datapoint is invalid when reference_response is absent/empty."""
    if rec.get('status') == 'failed':
        return True
    v = rec.get('reference_response')
    return v is None or v == ''


def _is_invalid_p4(rec: dict) -> bool:
    """Phase 4 response is invalid when response text is absent/empty."""
    if rec.get('status') == 'failed':
        return True
    v = rec.get('response')
    return v is None or v == ''


def _is_invalid_p5(rec: dict) -> bool:
    """Phase 5 evaluation is invalid when scores are missing or all-null."""
    if rec.get('status') == 'failed':
        return True
    scores = rec.get('scores') or {}
    if not scores:
        return True
    return all(v is None or v == '' for v in scores.values())


def _reason_p3(rec: dict) -> str:
    if rec.get('status') == 'failed':
        return 'already status=failed'
    v = rec.get('reference_response')
    return 'reference_response is null' if v is None else 'reference_response is empty'


def _reason_p4(rec: dict) -> str:
    if rec.get('status') == 'failed':
        return 'already status=failed'
    v = rec.get('response')
    return 'response is null' if v is None else 'response is empty'


def _reason_p5(rec: dict) -> str:
    if rec.get('status') == 'failed':
        return 'already status=failed'
    scores = rec.get('scores') or {}
    if not scores:
        return 'scores dict is missing or empty'
    return 'all score values are null/empty'


# ---------------------------------------------------------------------------
# Scanning
# ---------------------------------------------------------------------------

def scan_experiment(run_path: Path) -> dict:
    """Scan all phase JSONL files in *run_path* for invalid records.

    Returns a dict with keys ``'phase3'``, ``'phase4'``, ``'phase5'``,
    each holding a list of issue dicts.  Each issue dict has:

    * ``file`` — absolute path to the JSONL file (str)
    * ``line`` — 1-based line number in the file
    * ``record_id`` — value of the ``'id'`` field, or ``None`` for parse errors
    * ``reason`` — human-readable explanation

    Phase 4 issues additionally carry ``'datapoint_id'``.
    Phase 5 issues additionally carry ``'response_id'``.
    """
    report: dict[str, list[dict]] = {'phase3': [], 'phase4': [], 'phase5': []}

    # -- Phase 3 datapoints --
    p3_dir = run_path / 'phase3_datapoints'
    if p3_dir.exists():
        for f in sorted(p3_dir.glob('*.jsonl')):
            for lineno, rec in _iter_jsonl(f):
                if rec is None:
                    report['phase3'].append({
                        'file': str(f), 'line': lineno, 'record_id': None,
                        'reason': 'JSON parse error',
                    })
                elif _is_invalid_p3(rec):
                    report['phase3'].append({
                        'file': str(f), 'line': lineno,
                        'record_id': rec.get('id'),
                        'reason': _reason_p3(rec),
                    })

    # -- Phase 4 responses --
    p4_dir = run_path / 'phase4_responses'
    if p4_dir.exists():
        for f in sorted(p4_dir.glob('*.jsonl')):
            for lineno, rec in _iter_jsonl(f):
                if rec is None:
                    report['phase4'].append({
                        'file': str(f), 'line': lineno, 'record_id': None,
                        'reason': 'JSON parse error',
                    })
                elif _is_invalid_p4(rec):
                    report['phase4'].append({
                        'file': str(f), 'line': lineno,
                        'record_id': rec.get('id'),
                        'datapoint_id': rec.get('datapoint_id'),
                        'reason': _reason_p4(rec),
                    })

    # -- Phase 5 evaluations --
    p5_dir = run_path / 'phase5_evaluations'
    if p5_dir.exists():
        for f in sorted(p5_dir.glob('*.jsonl')):
            for lineno, rec in _iter_jsonl(f):
                if rec is None:
                    report['phase5'].append({
                        'file': str(f), 'line': lineno, 'record_id': None,
                        'reason': 'JSON parse error',
                    })
                elif _is_invalid_p5(rec):
                    report['phase5'].append({
                        'file': str(f), 'line': lineno,
                        'record_id': rec.get('id'),
                        'response_id': rec.get('response_id'),
                        'reason': _reason_p5(rec),
                    })

    return report


def _iter_jsonl(path: Path):
    """Yield ``(lineno, record_or_None)`` for each non-empty line in *path*."""
    for lineno, raw in enumerate(path.read_text(encoding='utf-8').splitlines(), 1):
        stripped = raw.strip()
        if not stripped:
            continue
        try:
            yield lineno, json.loads(stripped)
        except json.JSONDecodeError:
            yield lineno, None


# ---------------------------------------------------------------------------
# Fixing
# ---------------------------------------------------------------------------

def fix_invalid_records(run_path: Path, report: dict) -> dict[str, int]:
    """Mark all invalid records reported by :func:`scan_experiment` as failed.

    Rewrites the affected JSONL files in-place, adding ``"status": "failed"``
    to each invalid record.  Records that already carry ``status='failed'`` are
    not double-marked (they are already excluded by the skip logic in phases
    3–5).

    After this call, ``ExperimentStorage.count_datapoints()`` will exclude the
    marked Phase 3 records, and
    ``ExperimentStorage.get_responded_datapoint_ids()`` /
    ``get_evaluated_response_ids()`` will exclude the marked Phase 4/5 records.
    A subsequent ``coeval run --continue`` will therefore regenerate exactly the
    marked records and nothing else.

    Returns:
        ``{'phase3': n, 'phase4': n, 'phase5': n}`` — records newly marked.
    """
    from ..storage import ExperimentStorage

    storage = ExperimentStorage(str(run_path.parent), run_path.name)
    counts: dict[str, int] = {'phase3': 0, 'phase4': 0, 'phase5': 0}

    # Build a mapping: file path → set of record IDs to mark
    by_file: dict[str, set[str]] = defaultdict(set)
    for phase_key in ('phase3', 'phase4', 'phase5'):
        for issue in report[phase_key]:
            rid = issue.get('record_id')
            if rid:  # skip JSON-parse-error issues (no id to key on)
                by_file[issue['file']].add(rid)

    for fpath_str, rid_set in by_file.items():
        fpath = Path(fpath_str)
        if not fpath.exists() or not rid_set:
            continue
        n = storage.mark_failed_records(fpath, rid_set)
        fname = fpath.name
        if 'datapoints' in fname:
            counts['phase3'] += n
        elif 'responses' in fname:
            counts['phase4'] += n
        elif 'evaluations' in fname:
            counts['phase5'] += n

    return counts


# ---------------------------------------------------------------------------
# Report printing
# ---------------------------------------------------------------------------

def _print_report(report: dict, run_path: Path) -> None:
    total = sum(len(v) for v in report.values())
    print(f"\nRepair scan: {run_path}")
    print('=' * 70)

    phase_labels = [('phase3', '3', 'datapoints'), ('phase4', '4', 'responses'),
                    ('phase5', '5', 'evaluations')]
    for key, num, kind in phase_labels:
        issues = report[key]
        if issues:
            print(f"\nPhase {num} ({kind}) — {len(issues)} invalid record(s):")
            by_file: dict[str, list] = defaultdict(list)
            for iss in issues:
                by_file[Path(iss['file']).name].append(iss)
            for fname, file_issues in sorted(by_file.items()):
                print(f"  {fname}: {len(file_issues)} invalid")
                for iss in file_issues[:5]:
                    rid = iss.get('record_id') or f"<line {iss.get('line', '?')}>"
                    print(f"    • id={rid}: {iss['reason']}")
                if len(file_issues) > 5:
                    print(f"    • ... and {len(file_issues) - 5} more")
        else:
            print(f"\nPhase {num} ({kind}) — OK (no invalid records)")

    print(f"\n{'=' * 70}")
    print(f"Total invalid records found: {total}")


# ---------------------------------------------------------------------------
# Command entry point
# ---------------------------------------------------------------------------

def cmd_repair(args: argparse.Namespace) -> None:
    """Entry point for ``coeval repair``."""
    run_path = Path(args.run).resolve()

    if not run_path.exists():
        print(f"ERROR: Experiment folder not found: {run_path}", file=sys.stderr)
        sys.exit(1)

    if not (run_path / 'meta.json').exists():
        print(
            f"ERROR: Not a valid experiment folder (no meta.json): {run_path}",
            file=sys.stderr,
        )
        sys.exit(1)

    print(f"Scanning experiment: {run_path.name}")
    report = scan_experiment(run_path)
    _print_report(report, run_path)

    total = sum(len(v) for v in report.values())

    if total == 0:
        print("\nAll records are valid — no repair needed.")
        sys.exit(0)

    if args.dry_run:
        print(f"\nDry-run: no files modified.")
        print(
            f"Re-run without --dry-run to mark {total} record(s) as failed\n"
            f"so they are regenerated by the next `coeval run --continue`."
        )
        sys.exit(0)

    # Mark invalid records
    print(f"\nMarking {total} invalid record(s) as status='failed' …")
    counts = fix_invalid_records(run_path, report)
    print(f"  Phase 3 datapoints : {counts['phase3']} newly marked")
    print(f"  Phase 4 responses  : {counts['phase4']} newly marked")
    print(f"  Phase 5 evaluations: {counts['phase5']} newly marked")

    total_marked = sum(counts.values())
    already_failed = total - total_marked
    if already_failed:
        print(
            f"  ({already_failed} record(s) already had status='failed' — unchanged)"
        )

    print("\nRepair complete.")
    if total_marked:
        print(
            "\nTo regenerate the repaired records, re-run the experiment with:\n"
            "  coeval run --config <your-config.yaml> --continue\n"
            "\nOnly the marked records will be re-generated; all valid data is preserved."
        )
