"""coeval status — experiment progress dashboard with batch job tracking.

Prints a summary of an experiment's current state:
  - Metadata from meta.json (status, phases completed/in-progress)
  - Per-phase artifact counts (files and JSONL records)
  - Pending batch jobs from pending_batches.json (with live API status)
  - Recent errors from run_errors.jsonl

With ``--fetch-batches``, polls the provider APIs for each pending batch job
and, for completed jobs, downloads and applies the results to the experiment
storage.  Phase 4 (response_collection) and Phase 5 (evaluation) results can
be fully reconstructed; Phase 3 (data_generation) results cannot be applied
automatically — the command reports their status and instructs the user to
rerun with ``--continue`` for re-submission.

Usage::

    coeval status --run path/to/experiment
    coeval status --run path/to/experiment --fetch-batches
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path


# ---------------------------------------------------------------------------
# Key encoding constants (must match phase3/4/5)
# ---------------------------------------------------------------------------
_KEY_SEP = "\x00"
_SINGLE_SUFFIX = "\x01"


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


# ---------------------------------------------------------------------------
# Main command entry point
# ---------------------------------------------------------------------------

def cmd_status(args: argparse.Namespace) -> None:
    """Entry point for ``coeval status``."""
    run_path = Path(args.run).resolve()

    if not run_path.exists():
        print(f"ERROR: Experiment folder not found: {run_path}", file=sys.stderr)
        sys.exit(1)

    from ..storage import ExperimentStorage
    storage = ExperimentStorage(str(run_path.parent), run_path.name)

    meta_path = run_path / 'meta.json'
    if not meta_path.exists():
        print(f"ERROR: Not an experiment folder (no meta.json): {run_path}", file=sys.stderr)
        sys.exit(1)

    # 1. Metadata summary
    _print_meta(storage, run_path)

    # 2. Per-phase record counts
    _print_phase_progress(storage, run_path)

    # 3. Pending batch jobs
    batches = storage.read_pending_batches()
    _print_pending_batches(batches)

    # 4. Recent errors
    _print_recent_errors(storage)

    # 5. Optional: fetch batch results from provider APIs
    if getattr(args, 'fetch_batches', False):
        if batches:
            print("\n" + "="*60)
            print("Fetching batch results from provider APIs ...")
            print("="*60)
            _fetch_batch_results(storage, batches)
        else:
            print("\nNo pending batches to fetch.")


# ---------------------------------------------------------------------------
# Display helpers
# ---------------------------------------------------------------------------

def _print_meta(storage, run_path: Path) -> None:
    try:
        meta = storage.read_meta()
    except Exception as exc:
        print(f"WARNING: Could not read meta.json: {exc}", file=sys.stderr)
        meta = {}

    exp_id = meta.get('experiment_id', run_path.name)
    status = meta.get('status', 'unknown')
    created = meta.get('created_at', 'unknown')
    updated = meta.get('updated_at', 'unknown')
    phases_done = meta.get('phases_completed', [])
    phases_wip = meta.get('phases_in_progress', [])
    resume_from = meta.get('resume_from')

    print(f"\n{'='*60}")
    print(f"Experiment: {exp_id}")
    print(f"{'='*60}")
    print(f"  Status:             {status}")
    print(f"  Created:            {created}")
    print(f"  Last updated:       {updated}")
    if resume_from:
        print(f"  Resumed from:       {resume_from}")
    print(f"  Phases completed:   {phases_done or 'none'}")
    print(f"  Phases in-progress: {phases_wip or 'none'}")
    print(f"  Folder:             {run_path}")


def _print_phase_progress(storage, run_path: Path) -> None:
    print(f"\n{'='*60}")
    print("Phase Artifacts")
    print(f"{'='*60}")

    # Phase 1 — attribute maps
    phase1_dir = run_path / 'phase1_attributes'
    if phase1_dir.exists():
        target_files = list(phase1_dir.glob('*.target_attrs.json'))
        nuanced_files = list(phase1_dir.glob('*.nuanced_attrs.json'))
        print(f"  Phase 1 (attributes):   {len(target_files)} target_attrs files, "
              f"{len(nuanced_files)} nuanced_attrs files")
    else:
        print("  Phase 1 (attributes):   folder not found")

    # Phase 2 — rubrics
    phase2_dir = run_path / 'phase2_rubric'
    if phase2_dir.exists():
        rubric_files = list(phase2_dir.glob('*.rubric.json'))
        print(f"  Phase 2 (rubric):       {len(rubric_files)} rubric files")
    else:
        print("  Phase 2 (rubric):       folder not found")

    # Phases 3-5 — JSONL records
    for phase_num, phase_name, folder_name in [
        (3, 'data_generation',    'phase3_datapoints'),
        (4, 'response_collection', 'phase4_responses'),
        (5, 'evaluation',          'phase5_evaluations'),
    ]:
        phase_dir = run_path / folder_name
        if not phase_dir.exists():
            print(f"  Phase {phase_num} ({phase_name:<22}): folder not found")
            continue
        jsonl_files = list(phase_dir.glob('*.jsonl'))
        total_records = sum(_count_jsonl_records(f) for f in jsonl_files)
        failed_records = sum(_count_failed_records(f) for f in jsonl_files)
        label = phase_name + ':'
        detail = f"{len(jsonl_files)} files, {total_records} records"
        if failed_records:
            detail += f" ({failed_records} failed)"
        print(f"  Phase {phase_num} ({label:<22}  {detail}")


def _print_pending_batches(batches: dict) -> None:
    print(f"\n{'='*60}")
    print("Pending Batch Jobs")
    print(f"{'='*60}")
    if not batches:
        print("  None")
        return

    for batch_id, info in batches.items():
        iface = info.get('interface', '?')
        phase = info.get('phase', '?')
        n_req = info.get('n_requests', '?')
        submitted = info.get('submitted_at', '?')
        status = info.get('status', 'pending')
        desc = info.get('description', '')
        short_id = batch_id[:20] + ('...' if len(batch_id) > 20 else '')
        print(f"  [{iface}] {short_id}")
        print(f"    phase={phase}, requests={n_req}, status={status}")
        print(f"    submitted={submitted}, desc={desc!r}")


def _print_recent_errors(storage) -> None:
    try:
        errors = storage.read_run_errors()
    except Exception:
        errors = []

    print(f"\n{'='*60}")
    print("Recent Errors")
    print(f"{'='*60}")
    if not errors:
        print("  None")
        return

    # Show last 10 errors
    recent = errors[-10:]
    if len(errors) > 10:
        print(f"  (showing last 10 of {len(errors)} total errors)")
    for e in recent:
        phase = e.get('phase', '?')
        ts = e.get('timestamp', '?')
        err = e.get('error', str(e))[:120]
        print(f"  [{ts}] phase={phase}: {err}")


# ---------------------------------------------------------------------------
# Batch fetch
# ---------------------------------------------------------------------------

def _fetch_batch_results(storage, batches: dict) -> None:
    """Poll provider APIs for each pending batch; apply completed results."""
    updated = False
    for batch_id, info in list(batches.items()):
        iface = info.get('interface', '')
        phase = info.get('phase', '')
        n_req = info.get('n_requests', '?')
        id_to_key: dict[str, str] = info.get('id_to_key', {})

        print(f"\n  Checking [{iface}] batch: {batch_id[:24]}...")
        print(f"    phase={phase}, n_requests={n_req}")

        try:
            if iface == 'openai':
                done, results = _poll_openai_batch(batch_id)
            elif iface == 'anthropic':
                done, results = _poll_anthropic_batch(batch_id)
            else:
                print(f"    Unknown interface '{iface}', skipping.")
                continue
        except Exception as exc:
            print(f"    ERROR polling batch: {exc}")
            continue

        if not done:
            print("    Status: still in progress — run again later.")
            continue

        if results is None:
            # Batch ended in error/expired state
            print("    Status: FAILED or EXPIRED at provider — removing from tracking.")
            storage.update_pending_batch_status(batch_id, 'provider_failed')
            updated = True
            continue

        # Map compact IDs back to user batch_keys
        key_to_text: dict[str, str] = {}
        for compact_id, response_text in results.items():
            user_key = id_to_key.get(compact_id, compact_id)
            key_to_text[user_key] = response_text

        print(f"    Status: COMPLETED — {len(key_to_text)} results available.")

        # Apply results based on phase
        if phase == 'response_collection':
            n_written = _apply_phase4_results(key_to_text, storage)
            print(f"    Applied {n_written} response records to Phase 4 storage.")
        elif phase == 'evaluation':
            n_written = _apply_phase5_results(key_to_text, storage)
            print(f"    Applied {n_written} evaluation records to Phase 5 storage.")
        elif phase == 'data_generation':
            print(
                "    Phase 3 (data_generation) results cannot be auto-applied.\n"
                "    The sampled attributes are not stored in the batch record.\n"
                "    Action: run `coeval run --config <cfg> --continue` to\n"
                "    re-submit missing datapoints."
            )
            # Still remove from pending so --continue doesn't try to re-check it
        else:
            print(f"    Unknown phase '{phase}' — results not applied.")

        storage.remove_pending_batch(batch_id)
        updated = True

    if updated:
        print("\n  Pending batch tracking updated.")
        print("  Run `coeval run --config <cfg> --continue` to finish any remaining work.")
    else:
        print("\n  No batch status changes.")


def _poll_openai_batch(batch_id: str) -> tuple[bool, dict | None]:
    """Poll an OpenAI batch.

    Returns (done, results_dict).
    done=True means the batch is no longer in_progress.
    results_dict=None means it ended in a non-completed state.
    """
    try:
        from openai import OpenAI
    except ImportError:
        raise RuntimeError("openai package not installed (pip install openai)")

    key = os.environ.get('OPENAI_API_KEY')
    client = OpenAI(api_key=key)
    batch = client.batches.retrieve(batch_id)

    _IN_PROGRESS = {'validating', 'in_progress', 'finalising', 'finalizing'}
    if batch.status in _IN_PROGRESS:
        return False, None

    if batch.status != 'completed':
        return True, None  # Failed/expired/cancelled

    # Download output
    raw = client.files.content(batch.output_file_id).text
    results: dict[str, str] = {}
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        item = json.loads(line)
        custom_id: str = item['custom_id']
        err = item.get('error')
        if err:
            results[custom_id] = ''
            continue
        resp_body = (item.get('response') or {}).get('body') or {}
        choices = resp_body.get('choices') or []
        if choices:
            results[custom_id] = choices[0]['message']['content'].strip()
        else:
            results[custom_id] = ''

    return True, results


def _poll_anthropic_batch(batch_id: str) -> tuple[bool, dict | None]:
    """Poll an Anthropic batch.

    Returns (done, results_dict).
    """
    try:
        import anthropic
    except ImportError:
        raise RuntimeError("anthropic package not installed (pip install anthropic)")

    key = os.environ.get('ANTHROPIC_API_KEY')
    client = anthropic.Anthropic(api_key=key)
    batch = client.beta.messages.batches.retrieve(batch_id)

    if batch.processing_status == 'in_progress':
        return False, None

    if batch.processing_status != 'ended':
        return True, None  # Unknown terminal state

    # Stream results
    results: dict[str, str] = {}
    for result in client.beta.messages.batches.results(batch_id):
        custom_id: str = result.custom_id
        if result.result.type == 'succeeded':
            content = result.result.message.content
            results[custom_id] = content[0].text.strip() if content else ''
        else:
            results[custom_id] = ''

    return True, results


# ---------------------------------------------------------------------------
# Result application helpers
# ---------------------------------------------------------------------------

def _apply_phase4_results(key_to_text: dict[str, str], storage) -> int:
    """Decode Phase 4 batch_keys and write response records to storage.

    Returns number of records written.
    """
    n_written = 0
    for batch_key, response_text in key_to_text.items():
        parts = batch_key.split(_KEY_SEP)
        if len(parts) != 4:
            continue  # Not a phase-4 key
        task_id, teacher_id, student_id, datapoint_id = parts

        # Look up the datapoint to get the original prompt text
        prompt = ''
        try:
            dp_index = storage.index_datapoints(task_id, teacher_id)
            dp = dp_index.get(datapoint_id)
            if dp:
                prompt = dp.get('prompt', '')
        except Exception:
            pass

        response_id = f"{datapoint_id}__{student_id}"
        record: dict = {
            'id': response_id,
            'datapoint_id': datapoint_id,
            'task_id': task_id,
            'teacher_model_id': teacher_id,
            'student_model_id': student_id,
            'input': prompt,
            'response': response_text,
            'generated_at': _now_iso(),
        }
        if not response_text:
            record['status'] = 'failed'
        storage.append_response(task_id, teacher_id, student_id, record)
        n_written += 1

    return n_written


def _apply_phase5_results(key_to_text: dict[str, str], storage) -> int:
    """Decode Phase 5 batch_keys and write evaluation records to storage.

    Handles both 'single' and 'per_factor' evaluation modes.
    Returns number of evaluation records written.
    """
    single_results: dict[str, str] = {}   # core_key -> response_text
    factor_acc: dict[tuple, dict[str, str]] = defaultdict(dict)  # (t,tc,j,r) -> {factor: word}

    for batch_key, response_text in key_to_text.items():
        if batch_key.endswith(_SINGLE_SUFFIX):
            core = batch_key[:-1]  # strip \x01
            single_results[core] = response_text
        else:
            parts = batch_key.split(_KEY_SEP)
            if len(parts) == 5:
                task_id, teacher_id, judge_id, response_id, factor = parts
                resp_key = (task_id, teacher_id, judge_id, response_id)
                from ..phases.utils import parse_word_text
                word = parse_word_text(response_text) if response_text else 'Low'
                factor_acc[resp_key][factor] = word

    n_written = 0

    # --- Apply single-mode results ---
    for core_key, response_text in single_results.items():
        parts = core_key.split(_KEY_SEP)
        if len(parts) != 4:
            continue
        task_id, teacher_id, judge_id, response_id = parts

        # Read rubric to discover factor names
        rubric_factors: list[str] = []
        try:
            rubric = storage.read_rubric(task_id)
            rubric_factors = list(rubric.keys())
        except Exception:
            pass

        scores: dict[str, str] = {}
        if response_text and rubric_factors:
            try:
                from ..phases.utils import parse_json_text
                result_json = parse_json_text(response_text)
                for factor in rubric_factors:
                    val = str(result_json.get(factor, '')).strip()
                    if val not in ('High', 'Medium', 'Low'):
                        val = 'Low'
                    scores[factor] = val
            except Exception:
                for factor in rubric_factors:
                    scores[factor] = 'Low'
        else:
            for factor in rubric_factors:
                scores[factor] = 'Low'

        # datapoint_id is embedded as the prefix of response_id (format: dp_id__student_id)
        dp_id = response_id.rsplit('__', 1)[0]
        eval_id = f"{response_id}__{judge_id}"
        record: dict = {
            'id': eval_id,
            'response_id': response_id,
            'datapoint_id': dp_id,
            'task_id': task_id,
            'teacher_model_id': teacher_id,
            'judge_model_id': judge_id,
            'scores': scores,
            'evaluated_at': _now_iso(),
        }
        if not response_text:
            record['status'] = 'failed'
        storage.append_evaluation(task_id, teacher_id, judge_id, record)
        n_written += 1

    # --- Apply per_factor aggregated results ---
    for (task_id, teacher_id, judge_id, response_id), scores in factor_acc.items():
        dp_id = response_id.rsplit('__', 1)[0]
        eval_id = f"{response_id}__{judge_id}"
        record = {
            'id': eval_id,
            'response_id': response_id,
            'datapoint_id': dp_id,
            'task_id': task_id,
            'teacher_model_id': teacher_id,
            'judge_model_id': judge_id,
            'scores': scores,
            'evaluated_at': _now_iso(),
        }
        storage.append_evaluation(task_id, teacher_id, judge_id, record)
        n_written += 1

    return n_written


# ---------------------------------------------------------------------------
# Low-level helpers
# ---------------------------------------------------------------------------

def _count_jsonl_records(path: Path) -> int:
    try:
        return sum(1 for ln in path.read_text(encoding='utf-8').splitlines() if ln.strip())
    except Exception:
        return 0


def _count_failed_records(path: Path) -> int:
    try:
        count = 0
        for ln in path.read_text(encoding='utf-8').splitlines():
            ln = ln.strip()
            if ln:
                try:
                    obj = json.loads(ln)
                    if obj.get('status') == 'failed':
                        count += 1
                except Exception:
                    pass
        return count
    except Exception:
        return 0
