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

**Diagnostic flags**::

    # Compact per-phase summary table (valid/invalid/gap counts)
    coeval repair --run benchmark/runs/my-exp --stats

    # Detailed per-file breakdown table (valid/invalid/gap per JSONL file)
    coeval repair --run benchmark/runs/my-exp --breakdown

    # Combine for full picture: per-phase + per-file
    coeval repair --run benchmark/runs/my-exp --stats --breakdown

    # Control how many example records are shown per issue group (default 5)
    coeval repair --run benchmark/runs/my-exp --examples 10 --dry-run

    # Show valid record examples for spot-checking (3 per phase)
    coeval repair --run benchmark/runs/my-exp --show-valid 3 --dry-run

    # Full diagnostics: examples for every case (valid/invalid/gap)
    coeval repair --run benchmark/runs/my-exp --examples 5 --show-valid 3 --dry-run

    # Restrict output to a specific phase only
    coeval repair --run benchmark/runs/my-exp --phase 5 --dry-run

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


def count_valid_records(run_path: Path) -> dict[str, int]:
    """Count valid (non-invalid) records per phase in *run_path*.

    Returns a dict with keys ``'phase3'``, ``'phase4'``, ``'phase5'``
    containing the number of records that pass the per-phase validity check.
    These are records that are neither failed nor have empty required fields.
    """
    counts: dict[str, int] = {'phase3': 0, 'phase4': 0, 'phase5': 0}

    p3_dir = run_path / 'phase3_datapoints'
    if p3_dir.exists():
        for f in p3_dir.glob('*.jsonl'):
            for _, rec in _iter_jsonl(f):
                if rec and not _is_invalid_p3(rec):
                    counts['phase3'] += 1

    p4_dir = run_path / 'phase4_responses'
    if p4_dir.exists():
        for f in p4_dir.glob('*.jsonl'):
            for _, rec in _iter_jsonl(f):
                if rec and not _is_invalid_p4(rec):
                    counts['phase4'] += 1

    p5_dir = run_path / 'phase5_evaluations'
    if p5_dir.exists():
        for f in p5_dir.glob('*.jsonl'):
            for _, rec in _iter_jsonl(f):
                if rec and not _is_invalid_p5(rec):
                    counts['phase5'] += 1

    return counts


def collect_valid_examples(run_path: Path, n: int) -> dict[str, list[dict]]:
    """Collect up to *n* valid record examples per phase for spot-checking.

    Returns a dict with keys ``'phase3'``, ``'phase4'``, ``'phase5'``, each
    holding a list of up to *n* valid record dicts (first found, sorted by
    filename so results are deterministic).
    """
    samples: dict[str, list[dict]] = {'phase3': [], 'phase4': [], 'phase5': []}
    phase_config = [
        ('phase3', 'phase3_datapoints', _is_invalid_p3),
        ('phase4', 'phase4_responses',  _is_invalid_p4),
        ('phase5', 'phase5_evaluations', _is_invalid_p5),
    ]
    for key, subdir, is_invalid_fn in phase_config:
        d = run_path / subdir
        if not d.exists():
            continue
        for f in sorted(d.glob('*.jsonl')):
            if len(samples[key]) >= n:
                break
            for _, rec in _iter_jsonl(f):
                if isinstance(rec, dict) and not is_invalid_fn(rec):
                    samples[key].append(rec)
                    if len(samples[key]) >= n:
                        break
    return samples


def scan_file_breakdown(run_path: Path, gaps: dict) -> dict[str, list[dict]]:
    """Compute per-file valid/invalid/gap counts for all phase JSONL files.

    Returns a dict with keys ``'phase3'``, ``'phase4'``, ``'phase5'``, each
    holding a list of row dicts with keys:

    * ``file`` — filename (basename only)
    * ``valid`` — count of valid records
    * ``invalid`` — count of invalid records
    * ``gaps`` — count of missing records (from upstream cross-reference)
    """
    # Build gap counts per filename from the already-computed gap report
    gap_by_file: dict[str, int] = {}
    for g in gaps.get('phase4_gaps', []) + gaps.get('phase5_gaps', []):
        gap_by_file[Path(g['file']).name] = g.get('missing', 0)

    breakdown: dict[str, list[dict]] = {'phase3': [], 'phase4': [], 'phase5': []}
    phase_config = [
        ('phase3', 'phase3_datapoints',  _is_invalid_p3),
        ('phase4', 'phase4_responses',   _is_invalid_p4),
        ('phase5', 'phase5_evaluations', _is_invalid_p5),
    ]
    for key, subdir, is_invalid_fn in phase_config:
        d = run_path / subdir
        if not d.exists():
            continue
        for f in sorted(d.glob('*.jsonl')):
            valid = invalid = 0
            for _, rec in _iter_jsonl(f):
                if not isinstance(rec, dict):
                    invalid += 1
                elif is_invalid_fn(rec):
                    invalid += 1
                else:
                    valid += 1
            breakdown[key].append({
                'file': f.name,
                'valid': valid,
                'invalid': invalid,
                'gaps': gap_by_file.get(f.name, 0),
            })
    return breakdown


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
                if isinstance(rec, dict) and rec.get('status') != 'failed':
                    key = (rec.get('task_id', ''), rec.get('teacher_model_id', ''))
                    dp_ids[key].add(rec['id'])

    # Build index: (task_id, teacher_id, student_id) -> set of valid response IDs
    resp_ids: dict[tuple, set[str]] = defaultdict(set)
    if p4_dir.exists():
        for f in p4_dir.glob('*.jsonl'):
            for _, rec in _iter_jsonl(f):
                if isinstance(rec, dict) and rec.get('status') != 'failed' and rec.get('response'):
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
                if isinstance(rec, dict) and rec.get('status') != 'failed' and rec.get('response'):
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
            # Parse task/teacher/judge from the filename as primary key source.
            # This is needed when the file is empty (e.g. after repair removed all
            # failed records) — the records can't supply the IDs in that case.
            stem = f.name.replace('.evaluations.jsonl', '')
            stem_parts = stem.split('.')
            if len(stem_parts) < 3:
                continue  # malformed filename — skip
            fname_task_id = stem_parts[0]
            fname_teacher_id = stem_parts[1]
            fname_judge_id = '.'.join(stem_parts[2:])

            # Count ALL records (success and failed) as "covered" — failed records
            # are recorded attempts, not missing data. Use coeval repair to clear
            # failed records and retry.
            evaluated: set[str] = set()
            task_id = fname_task_id
            teacher_id = fname_teacher_id
            judge_id = fname_judge_id
            for _, rec in _iter_jsonl(f):
                if isinstance(rec, dict):
                    evaluated.add(rec.get('response_id', ''))
                    # Prefer record-sourced IDs (more authoritative), but fall back
                    # to filename-derived ones when the file is empty.
                    task_id = rec.get('task_id', task_id)
                    teacher_id = rec.get('teacher_model_id', teacher_id)
                    judge_id = rec.get('judge_model_id', judge_id)

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

def _print_breakdown(breakdown: dict, run_path: Path) -> None:
    """Print a detailed per-file valid/invalid/gap table for each phase."""
    PHASE_LABELS = {
        'phase3': 'Phase 3 — datapoints',
        'phase4': 'Phase 4 — responses',
        'phase5': 'Phase 5 — evaluations',
    }
    COL = 58   # filename column width

    print(f"\nPer-file breakdown: {run_path.name}")
    print('=' * (COL + 36))

    grand_valid = grand_invalid = grand_gaps = 0
    for key in ('phase3', 'phase4', 'phase5'):
        rows = breakdown.get(key, [])
        if not rows:
            continue
        phase_valid = sum(r['valid'] for r in rows)
        phase_invalid = sum(r['invalid'] for r in rows)
        phase_gaps = sum(r['gaps'] for r in rows)
        grand_valid += phase_valid
        grand_invalid += phase_invalid
        grand_gaps += phase_gaps

        print(f"\n  {PHASE_LABELS[key]}")
        print(f"  {'File':<{COL}} {'Valid':>7} {'Invalid':>8} {'Gaps':>6}")
        print(f"  {'-'*COL} {'-'*7} {'-'*8} {'-'*6}")
        for r in rows:
            flag = ' !' if (r['invalid'] > 0 or r['gaps'] > 0) else ''
            fname = r['file']
            if len(fname) > COL:
                fname = '…' + fname[-(COL - 1):]
            print(f"  {fname:<{COL}} {r['valid']:>7,} {r['invalid']:>8,} {r['gaps']:>6,}{flag}")
        print(f"  {'  subtotal':<{COL}} {phase_valid:>7,} {phase_invalid:>8,} {phase_gaps:>6,}")

    print()
    print(f"  {'GRAND TOTAL':<{COL}} {grand_valid:>7,} {grand_invalid:>8,} {grand_gaps:>6,}")
    print('=' * (COL + 36))


def _print_valid_examples(
    samples: dict[str, list[dict]],
    phase_labels: list[tuple],
) -> None:
    """Print spot-check examples of valid records per phase."""
    print("\n--- Valid record examples (spot-check) ---")
    KEY_FIELDS = {
        'phase3': ('id', 'task_id', 'teacher_model_id', 'reference_response'),
        'phase4': ('id', 'task_id', 'teacher_model_id', 'student_model_id', 'response'),
        'phase5': ('id', 'task_id', 'teacher_model_id', 'judge_model_id', 'scores'),
    }
    any_shown = False
    for key, num, kind in phase_labels:
        recs = samples.get(key, [])
        if not recs:
            print(f"\nPhase {num} ({kind}) — no valid records found")
            continue
        any_shown = True
        print(f"\nPhase {num} ({kind}) — {len(recs)} example(s):")
        for rec in recs:
            rid = rec.get('id', '?')
            fields = KEY_FIELDS.get(key, ('id',))
            parts = []
            for field in fields:
                if field == 'id':
                    continue   # id shown in prefix
                val = rec.get(field, '–')
                if isinstance(val, str) and len(val) > 80:
                    val = val[:77] + '…'
                elif isinstance(val, dict):
                    val = '{' + ', '.join(f'{k}: {v}' for k, v in list(val.items())[:4]) + '}'
                parts.append(f"{field}={val!r}")
            print(f"  [{rid}]")
            for p in parts:
                print(f"    {p}")
    if not any_shown:
        print("  (no valid records found in selected phases)")


def _print_stats(report: dict, gaps: dict, valid_counts: dict, run_path: Path) -> None:
    """Print a compact per-phase summary table of valid/invalid/gap counts."""
    invalid_total = sum(len(v) for v in report.values())
    gap_total = sum(g['missing'] for g in gaps['phase4_gaps'] + gaps['phase5_gaps'])
    valid_total = sum(valid_counts.values())

    print(f"\nDiagnostic summary: {run_path.name}")
    print('=' * 70)
    header = f"{'Phase':<26} {'Valid':>8} {'Invalid':>8} {'Gaps':>8} {'Total':>8}"
    print(header)
    print('-' * 70)

    phase_labels = [
        ('phase3', 'Phase 3 (datapoints)'),
        ('phase4', 'Phase 4 (responses)'),
        ('phase5', 'Phase 5 (evaluations)'),
    ]
    phase_gap_counts = {
        'phase3': 0,  # no phase3 gap detection
        'phase4': sum(g['missing'] for g in gaps['phase4_gaps']),
        'phase5': sum(g['missing'] for g in gaps['phase5_gaps']),
    }
    for key, label in phase_labels:
        v = valid_counts.get(key, 0)
        i = len(report.get(key, []))
        g = phase_gap_counts.get(key, 0)
        t = v + i + g
        flag = '' if (i == 0 and g == 0) else ' !'
        print(f"{label:<26} {v:>8,} {i:>8,} {g:>8,} {t:>8,}{flag}")

    print('-' * 70)
    total_total = valid_total + invalid_total + gap_total
    print(f"{'Total':<26} {valid_total:>8,} {invalid_total:>8,} {gap_total:>8,} {total_total:>8,}")
    print('=' * 70)

    if invalid_total == 0 and gap_total == 0:
        print("✓ All records valid — no repair needed.")
    else:
        if invalid_total:
            print(f"  {invalid_total} invalid record(s) — run repair to mark as failed.")
        if gap_total:
            print(f"  {gap_total} missing record(s) — repair will re-open phase(s) for retry.")
        print("\nRun without --stats to see detailed report.")


def _print_report(
    report: dict,
    gaps: dict,
    run_path: Path,
    valid_counts: dict | None = None,
    examples: int = 5,
    phase_filter: int | None = None,
    show_valid: int = 0,
    breakdown: dict | None = None,
) -> None:
    invalid_total = sum(len(v) for v in report.values())
    gap_total = sum(g['missing'] for g in gaps['phase4_gaps'] + gaps['phase5_gaps'])

    print(f"\nRepair scan: {run_path}")
    print('=' * 70)

    # Determine which phases to include in the report
    all_phases = [('phase3', '3', 'datapoints'), ('phase4', '4', 'responses'),
                  ('phase5', '5', 'evaluations')]
    if phase_filter is not None:
        phase_labels = [(k, n, knd) for k, n, knd in all_phases if n == str(phase_filter)]
    else:
        phase_labels = all_phases

    # Invalid records section
    print("\n--- Invalid records (exist but have empty/null required fields) ---")
    for key, num, kind in phase_labels:
        issues = report[key]
        valid = (valid_counts or {}).get(key, 0)
        valid_str = f" | {valid:,} valid" if valid_counts else ""
        if issues:
            print(f"\nPhase {num} ({kind}) — {len(issues)} invalid record(s){valid_str}:")
            by_file: dict[str, list] = defaultdict(list)
            for iss in issues:
                by_file[Path(iss['file']).name].append(iss)
            for fname, file_issues in sorted(by_file.items()):
                print(f"  {fname}: {len(file_issues)} invalid")
                show = file_issues[:examples] if examples > 0 else []
                for iss in show:
                    rid = iss.get('record_id') or f"<line {iss.get('line', '?')}>"
                    print(f"    * id={rid}: {iss['reason']}")
                remaining = len(file_issues) - len(show)
                if remaining > 0:
                    print(f"    * ... and {remaining} more (use --examples N for more)")
        else:
            valid_note = f" ({valid:,} valid)" if valid_counts else ""
            print(f"\nPhase {num} ({kind}) — OK (no invalid records){valid_note}")

    # Coverage gaps section (skip if phase_filter set to phase 3)
    if phase_filter != 3:
        print("\n--- Coverage gaps (records expected but entirely missing) ---")
        if phase_filter in (None, 4):
            if gaps['phase4_gaps']:
                print(f"\nPhase 4 (responses) — {len(gaps['phase4_gaps'])} file(s) incomplete:")
                for g in gaps['phase4_gaps']:
                    fname = Path(g['file']).name
                    print(f"  {fname}: {g['have']:,}/{g['expected']:,} records ({g['missing']:,} missing)")
                    sample_ids = g.get('datapoint_ids', [])[:examples] if examples > 0 else []
                    for dp_id in sample_ids:
                        print(f"    - missing datapoint: {dp_id}")
                    remaining = len(g.get('datapoint_ids', [])) - len(sample_ids)
                    if remaining > 0:
                        print(f"    - ... and {remaining} more")
            else:
                print("\nPhase 4 (responses) — OK (full coverage)")

        if phase_filter in (None, 5):
            if gaps['phase5_gaps']:
                print(f"\nPhase 5 (evaluations) — {len(gaps['phase5_gaps'])} file(s) incomplete:")
                for g in gaps['phase5_gaps']:
                    fname = Path(g['file']).name
                    print(f"  {fname}: {g['have']:,}/{g['expected']:,} records ({g['missing']:,} missing)")
                    sample_ids = g.get('response_ids', [])[:examples] if examples > 0 else []
                    for rid in sample_ids:
                        print(f"    - missing response: {rid}")
                    remaining = g['missing'] - len(sample_ids)
                    if remaining > 0:
                        print(f"    - ... and {remaining} more")
            else:
                print("\nPhase 5 (evaluations) — OK (full coverage)")

    # Valid record examples section
    if show_valid > 0:
        samples = collect_valid_examples(run_path, show_valid)
        _print_valid_examples(samples, phase_labels)

    # Per-file breakdown section
    if breakdown is not None:
        _print_breakdown(breakdown, run_path)

    print(f"\n{'=' * 70}")
    print(f"Invalid records: {invalid_total:,}  |  Missing records: {gap_total:,}")
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
    examples: int = getattr(args, 'examples', 5)
    phase_filter: int | None = getattr(args, 'phase', None)
    stats_mode: bool = getattr(args, 'stats', False)
    show_breakdown: bool = getattr(args, 'breakdown', False)
    show_valid: int = getattr(args, 'show_valid', 0)

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

    if stats_mode:
        valid_counts = count_valid_records(run_path)
        _print_stats(report, gaps, valid_counts, run_path)
        if show_breakdown:
            bd = scan_file_breakdown(run_path, gaps)
            _print_breakdown(bd, run_path)
        sys.exit(0)

    valid_counts = count_valid_records(run_path) if examples >= 0 else None
    bd = scan_file_breakdown(run_path, gaps) if show_breakdown else None
    _print_report(report, gaps, run_path,
                  valid_counts=valid_counts,
                  examples=examples,
                  phase_filter=phase_filter,
                  show_valid=show_valid,
                  breakdown=bd)

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

    # Fix 1: mark invalid records as failed (and for phase 5: remove failed records)
    if invalid_total:
        print(f"\nMarking {invalid_total} invalid record(s) as status='failed' ...")
        counts = fix_invalid_records(run_path, report)
        print(f"  Phase 3 datapoints : {counts['phase3']:,} newly marked")
        print(f"  Phase 4 responses  : {counts['phase4']:,} newly marked")
        print(f"  Phase 5 evaluations: {counts['phase5']:,} removed (failed records cleared)")
        total_marked = sum(counts.values())
        already_failed = invalid_total - total_marked
        if already_failed:
            print(f"  ({already_failed} already had status='failed' — removed from p5 files)")

        # Re-scan coverage gaps after fixing invalids: removing phase 5 failed records
        # creates new coverage gaps that must be detected so the phase can be reopened.
        if counts.get('phase5', 0) > 0:
            print("\n  Re-scanning coverage gaps after removing failed phase 5 records ...")
            updated_gaps = scan_coverage_gaps(run_path)
            new_phases = updated_gaps['phases_to_reopen'] - gaps['phases_to_reopen']
            if new_phases:
                print(f"  Newly detected gap phase(s): {sorted(new_phases)}")
                gaps['phases_to_reopen'] |= new_phases
                gaps['phase5_gaps'].extend(updated_gaps['phase5_gaps'])
            updated_gap_total = sum(
                g['missing'] for g in updated_gaps['phase4_gaps'] + updated_gaps['phase5_gaps']
            )
            if updated_gap_total:
                print(f"  Total coverage gaps after fix: {updated_gap_total:,} missing record(s)")

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
