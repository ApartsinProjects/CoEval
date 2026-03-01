"""coeval repair — scan for invalid/missing phase records and prepare re-generation.

Scans Phase 3 (datapoints), Phase 4 (responses), and Phase 5 (evaluations)
JSONL files for two classes of problems:

**Class 1 — Invalid records**: records that exist in the file but have empty
required fields, null values, or existing ``status='failed'`` markers.
These are marked ``status='failed'`` in-place so that ``--continue`` (Extend
mode) regenerates them.

**Class 2 — Coverage gaps**: phases where the existing JSONL files have fewer
records than expected (i.e. the model crashed mid-run, leaving whole response
or evaluation IDs unprocessed).  These are detected by cross-referencing the
upstream phase: Phase 4 gaps are found by comparing phase 4 response IDs
against phase 3 datapoint IDs; Phase 5 gaps are found by comparing phase 5
evaluation response IDs against phase 4 response IDs.  When gaps are detected,
the affected phase is removed from ``phases_completed`` in ``meta.json`` so
that ``--continue`` runs it again (in Extend mode, which skips existing records).

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

    # 2. Scan and repair (marks invalid records as failed + updates meta.json)
    coeval repair --run benchmark/runs/my-exp

    # 3. Re-generate the marked/missing records
    coeval run --config my-experiment.yaml --continue
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from collections import defaultdict
from datetime import datetime, timezone

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
# Scanning — invalid records
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
# Scanning — coverage gaps (missing records)
# ---------------------------------------------------------------------------

def scan_coverage_gaps(run_path: Path) -> dict:
    """Detect phases with missing records by cross-referencing upstream data.

    Returns a dict::

        {
          'phase4_gaps': [{'file': str, 'missing': int, 'datapoint_ids': [...]}],
          'phase5_gaps': [{'file': str, 'missing': int, 'response_ids': [...]}],
          'phases_to_reopen': set[str],   # phase IDs to remove from phases_completed
        }

    Phase 4 gap: a (task, teacher, student) response file has fewer records
    than there are valid (non-failed) datapoints for (task, teacher).

    Phase 5 gap: a (task, teacher, judge) evaluation file is missing
    evaluations for some response IDs present in Phase 4 response files.
    """
    gaps: dict = {
        'phase4_gaps': [],
        'phase5_gaps': [],
        'phases_to_reopen': set(),
    }

    p3_dir = run_path / 'phase3_datapoints'
    p4_dir = run_path / 'phase4_responses'
    p5_dir = run_path / 'phase5_evaluations'

    # Build index: (task_id, teacher_id) -> set of valid datapoint IDs
    dp_ids: dict[tuple, set[str]] = defaultdict(set)
    if p3_dir.exists():
        for f in p3_dir.glob('*.jsonl'):
            for _, rec in _iter_jsonl(f):
                if rec and rec.get('status') != 'failed':
                    key = (rec.get('task_id', ''), rec.get('teacher_model_id', ''))
                    dp_ids[key].add(rec['id'])

    # Build index: (task_id, teacher_id, student_id) -> set of valid response IDs
    resp_ids: dict[tuple, set[str]] = defaultdict(set)
    if p4_dir.exists():
        for f in p4_dir.glob('*.jsonl'):
            for _, rec in _iter_jsonl(f):
                if rec and rec.get('status') != 'failed' and rec.get('response'):
                    key = (
                        rec.get('task_id', ''),
                        rec.get('teacher_model_id', ''),
                        rec.get('student_model_id', ''),
                    )
                    resp_ids[key].add(rec['id'])

    # Check Phase 4: for each response file, are all datapoints covered?
    if p4_dir.exists():
        for f in sorted(p4_dir.glob('*.jsonl')):
            responded: set[str] = set()
            task_id = teacher_id = ''
            for _, rec in _iter_jsonl(f):
                if rec and rec.get('status') != 'failed' and rec.get('response'):
                    responded.add(rec.get('datapoint_id', ''))
                    task_id = rec.get('task_id', task_id)
                    teacher_id = rec.get('teacher_model_id', teacher_id)
            if not task_id:
                continue
            expected = dp_ids.get((task_id, teacher_id), set())
            missing_dp_ids = expected - responded
            if missing_dp_ids:
                gaps['phase4_gaps'].append({
                    'file': str(f),
                    'missing': len(missing_dp_ids),
                    'have': len(responded),
                    'expected': len(expected),
                    'datapoint_ids': sorted(missing_dp_ids),
                })
                gaps['phases_to_reopen'].add('response_collection')

    # Load active judge IDs from config (if available) — orphaned judge files from
    # removed models are not counted as gaps.
    active_judge_ids: set[str] | None = None
    config_path = run_path / 'config.yaml'
    if config_path.exists():
        try:
            import yaml as _yaml  # noqa: PLC0415
            cfg_raw = _yaml.safe_load(config_path.read_text(encoding='utf-8'))
            judge_ids_from_cfg: set[str] = set()
            for model in (cfg_raw or {}).get('models', []):
                if 'judge' in (model.get('roles') or []):
                    judge_ids_from_cfg.add(model.get('name', ''))
            # Only filter by config judges if the config actually defines any judges.
            # A config without a 'models' list (e.g. a minimal stub) should not
            # cause all evaluation files to be skipped.
            if judge_ids_from_cfg:
                active_judge_ids = judge_ids_from_cfg
        except Exception:
            pass  # if config can't be loaded, check all files

    # Check Phase 5: for each evaluation file, are all responses covered?
    if p5_dir.exists():
        for f in sorted(p5_dir.glob('*.jsonl')):
            # Count ALL records (success and failed) as "covered" — failed records
            # are recorded attempts, not missing data. Use coeval repair to clear
            # failed records and retry.
            evaluated: set[str] = set()
            task_id = teacher_id = judge_id = ''
            for _, rec in _iter_jsonl(f):
                if rec:
                    evaluated.add(rec.get('response_id', ''))
                    task_id = rec.get('task_id', task_id)
                    teacher_id = rec.get('teacher_model_id', teacher_id)
                    judge_id = rec.get('judge_model_id', judge_id)
            if not task_id:
                continue
            # Skip files for judges no longer in the active config
            if active_judge_ids is not None and judge_id and judge_id not in active_judge_ids:
                continue
            # Collect all valid responses for this (task, teacher) across all students
            all_resp_for_pair: set[str] = set()
            for (t, tch, _stu), rids in resp_ids.items():
                if t == task_id and tch == teacher_id:
                    all_resp_for_pair |= rids
            missing_resp_ids = all_resp_for_pair - evaluated
            if missing_resp_ids:
                gaps['phase5_gaps'].append({
                    'file': str(f),
                    'missing': len(missing_resp_ids),
                    'have': len(evaluated),
                    'expected': len(all_resp_for_pair),
                    'response_ids': sorted(missing_resp_ids)[:10],  # sample only
                    'judge_id': judge_id,
                })
                gaps['phases_to_reopen'].add('evaluation')

    return gaps


# ---------------------------------------------------------------------------
# Fixing — invalid records
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
        fname = fpath.name
        if 'evaluations' in fname:
            # Phase 5: mark the invalid records as failed first, then remove ALL
            # failed evaluation records so that get_evaluated_response_ids no longer
            # returns those response_ids, allowing --continue to re-attempt them.
            # Parse the task/teacher/judge from the filename: {task}.{teacher}.{judge}.evaluations.jsonl
            parts = fname.replace('.evaluations.jsonl', '').split('.')
            if len(parts) >= 3:
                task_id = parts[0]
                teacher_id = parts[1]
                judge_id = '.'.join(parts[2:])
                # Step 1: mark the invalid records as failed
                storage.mark_failed_records(fpath, rid_set)
                # Step 2: remove ALL failed records (newly marked + any pre-existing)
                n = storage.remove_failed_evaluations(task_id, teacher_id, judge_id)
                counts['phase5'] += n
        else:
            n = storage.mark_failed_records(fpath, rid_set)
            if 'datapoints' in fname:
                counts['phase3'] += n
            elif 'responses' in fname:
                counts['phase4'] += n

    return counts


# ---------------------------------------------------------------------------
# Fixing — coverage gaps: update meta.json phases_completed
# ---------------------------------------------------------------------------

def reopen_phases(run_path: Path, phases_to_reopen: set[str]) -> list[str]:
    """Remove *phases_to_reopen* from ``phases_completed`` in ``meta.json``.

    This causes ``coeval run --continue`` to re-run those phases in Extend
    mode, filling in the missing records without re-processing existing ones.

    Returns the list of phase IDs actually removed (those that were marked
    completed before this call).
    """
    meta_path = run_path / 'meta.json'
    with open(meta_path, encoding='utf-8') as f:
        meta = json.load(f)

    completed = set(meta.get('phases_completed', []))
    removed = sorted(phases_to_reopen & completed)

    if removed:
        meta['phases_completed'] = [p for p in meta.get('phases_completed', [])
                                     if p not in phases_to_reopen]
        meta['status'] = 'in_progress'
        meta['updated_at'] = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
        with open(meta_path, 'w', encoding='utf-8') as f:
            json.dump(meta, f, ensure_ascii=False)

    return removed


# ---------------------------------------------------------------------------
# Report printing
# ---------------------------------------------------------------------------

def _print_report(report: dict, gaps: dict, run_path: Path) -> None:
    invalid_total = sum(len(v) for v in report.values())
    gap_total = sum(g['missing'] for g in gaps['phase4_gaps'] + gaps['phase5_gaps'])

    print(f"\nRepair scan: {run_path}")
    print('=' * 70)

    # Invalid records
    phase_labels = [('phase3', '3', 'datapoints'), ('phase4', '4', 'responses'),
                    ('phase5', '5', 'evaluations')]
    print("\n--- Invalid records (exist but have empty/null required fields) ---")
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
                    print(f"    * id={rid}: {iss['reason']}")
                if len(file_issues) > 5:
                    print(f"    * ... and {len(file_issues) - 5} more")
        else:
            print(f"\nPhase {num} ({kind}) — OK (no invalid records)")

    # Coverage gaps
    print("\n--- Coverage gaps (records expected but entirely missing) ---")
    if gaps['phase4_gaps']:
        print(f"\nPhase 4 (responses) — {len(gaps['phase4_gaps'])} file(s) incomplete:")
        for g in gaps['phase4_gaps']:
            fname = Path(g['file']).name
            print(f"  {fname}: {g['have']}/{g['expected']} records ({g['missing']} missing)")
    else:
        print("\nPhase 4 (responses) — OK (full coverage)")

    if gaps['phase5_gaps']:
        print(f"\nPhase 5 (evaluations) — {len(gaps['phase5_gaps'])} file(s) incomplete:")
        for g in gaps['phase5_gaps']:
            fname = Path(g['file']).name
            print(f"  {fname}: {g['have']}/{g['expected']} records ({g['missing']} missing)")
    else:
        print("\nPhase 5 (evaluations) — OK (full coverage)")

    print(f"\n{'=' * 70}")
    print(f"Invalid records: {invalid_total}  |  Missing records: {gap_total}")
    if gaps['phases_to_reopen']:
        print(
            f"Phases with coverage gaps: {sorted(gaps['phases_to_reopen'])} "
            f"(will be re-opened in meta.json)"
        )


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
    gaps = scan_coverage_gaps(run_path)
    _print_report(report, gaps, run_path)

    invalid_total = sum(len(v) for v in report.values())
    gap_total = sum(g['missing'] for g in gaps['phase4_gaps'] + gaps['phase5_gaps'])
    anything_to_fix = invalid_total > 0 or gap_total > 0

    if not anything_to_fix:
        print("\nAll records are valid and coverage is complete — no repair needed.")
        sys.exit(0)

    if args.dry_run:
        print(f"\nDry-run: no files modified.")
        if invalid_total:
            print(
                f"  Would mark {invalid_total} invalid record(s) as status='failed'."
            )
        if gap_total:
            print(
                f"  Would re-open phase(s) {sorted(gaps['phases_to_reopen'])} "
                f"in meta.json to trigger Extend-mode re-generation of "
                f"{gap_total} missing record(s)."
            )
        print("\nRe-run without --dry-run to apply repairs.")
        sys.exit(0)

    # Fix 1: mark invalid records as failed
    if invalid_total:
        print(f"\nMarking {invalid_total} invalid record(s) as status='failed' ...")
        counts = fix_invalid_records(run_path, report)
        print(f"  Phase 3 datapoints : {counts['phase3']} newly marked")
        print(f"  Phase 4 responses  : {counts['phase4']} newly marked")
        print(f"  Phase 5 evaluations: {counts['phase5']} newly marked")
        total_marked = sum(counts.values())
        already_failed = invalid_total - total_marked
        if already_failed:
            print(f"  ({already_failed} already had status='failed' — unchanged)")

    # Fix 2: reopen phases with coverage gaps so --continue fills them in
    if gaps['phases_to_reopen']:
        print(
            f"\nRe-opening phase(s) {sorted(gaps['phases_to_reopen'])} in meta.json "
            f"(removing from phases_completed) ..."
        )
        removed = reopen_phases(run_path, gaps['phases_to_reopen'])
        if removed:
            print(f"  Removed from phases_completed: {removed}")
            print(f"  Experiment status set to 'in_progress'.")
        else:
            print(f"  Phases were not marked completed — no meta.json change needed.")

    print("\nRepair complete.")
    print(
        "\nTo regenerate the missing/failed records, re-run the experiment with:\n"
        "  coeval run --config <your-config.yaml> --continue\n"
        "\nOnly the missing/marked records will be re-generated; "
        "all valid data is preserved."
    )
