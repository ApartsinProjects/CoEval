"""``coeval ingest`` — inject benchmark data into an existing EES run.

This command reads a downloaded benchmark dataset and writes the items as
Phase-3 datapoints attributed to a virtual *benchmark teacher* model.  The
experiment config is updated in-place so subsequent ``coeval run --continue``
will run Phase 4 (responses) and Phase 5 (evaluation) on the new teacher.

Phases 1–2 are also written for the benchmark task if they don't already exist,
so the pipeline has the rubric and attribute schema it needs.

Workflow
--------
1. Download benchmarks::

       python stdbenchmarks/download_benchmarks.py --benchmarks mmlu hellaswag

2. Ingest into an existing run::

       coeval ingest --run benchmark/runs/my-exp --benchmark mmlu

3. Continue the experiment (Phases 4–5 only for the new teacher)::

       coeval run --config benchmark/runs/my-exp/config.yaml --continue

Design decisions
----------------
* Teacher model name in EES: ``<benchmark_name>-benchmark``
  (e.g. ``mmlu-benchmark``).  This is stable and doesn't collide with real
  model IDs.
* The virtual model is added to the config with ``interface: benchmark`` and
  ``roles: [teacher]``.  Phase 3 skips benchmark teachers; Phases 4–5 treat
  them identically to real teachers.
* Re-running ingest on the same benchmark is idempotent: existing JSONL lines
  are kept; only new items (higher seq numbers) are appended (Extend mode).
* Phase-1 and Phase-2 files are written only if they don't already exist
  (Keep mode), so a merge with an existing task's attributes/rubric is safe.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


def _read_json(path: Path) -> dict:
    with open(path, encoding='utf-8') as fh:
        return json.load(fh)


def _write_json(path: Path, obj: dict) -> None:
    with open(path, 'w', encoding='utf-8') as fh:
        json.dump(obj, fh, indent=2, ensure_ascii=False)
    fh.close()


def _read_yaml(path: Path) -> dict:
    with open(path, encoding='utf-8') as fh:
        return yaml.safe_load(fh) or {}


def _write_yaml(path: Path, obj: dict) -> None:
    with open(path, 'w', encoding='utf-8') as fh:
        yaml.dump(obj, fh, default_flow_style=False, allow_unicode=True)


def _count_jsonl(path: Path) -> int:
    if not path.exists():
        return 0
    count = 0
    for line in path.read_text(encoding='utf-8').splitlines():
        line = line.strip()
        if line:
            try:
                rec = json.loads(line)
                if rec.get('status') != 'failed':
                    count += 1
            except Exception:
                pass
    return count


def _existing_ids(path: Path) -> set[str]:
    """Return all datapoint IDs already written in a JSONL file."""
    if not path.exists():
        return set()
    ids: set[str] = set()
    for line in path.read_text(encoding='utf-8').splitlines():
        line = line.strip()
        if line:
            try:
                rec = json.loads(line)
                ids.add(rec.get('id', ''))
            except Exception:
                pass
    return ids


# ---------------------------------------------------------------------------
# Core ingest logic
# ---------------------------------------------------------------------------

def ingest_benchmark(
    run_path: Path,
    benchmark_name: str,
    data_dir: Path,
    split: str = 'test',
    limit: int | None = None,
    task_name: str | None = None,
    verbose: bool = False,
) -> int:
    """Ingest one benchmark into *run_path*.

    Returns the number of new datapoints written.
    """
    from experiments.benchmarks import get_adapter

    adapter = get_adapter(benchmark_name)
    effective_task_name = task_name or adapter.task_name
    teacher_id = f'{benchmark_name}-benchmark'

    print(f"[ingest] Benchmark : {benchmark_name}")
    print(f"[ingest] Task name : {effective_task_name}")
    print(f"[ingest] Teacher ID: {teacher_id}")
    print(f"[ingest] Run path  : {run_path}")

    # ------------------------------------------------------------------
    # Validate run folder
    # ------------------------------------------------------------------
    meta_path = run_path / 'meta.json'
    config_path = run_path / 'config.yaml'
    if not meta_path.exists() or not config_path.exists():
        print(
            f"ERROR: '{run_path}' does not look like a valid EES run folder "
            f"(missing meta.json or config.yaml).",
            file=sys.stderr,
        )
        sys.exit(1)

    phase1_dir = run_path / 'phase1_attributes'
    phase2_dir = run_path / 'phase2_rubric'
    phase3_dir = run_path / 'phase3_datapoints'
    for d in (phase1_dir, phase2_dir, phase3_dir):
        d.mkdir(exist_ok=True)

    # ------------------------------------------------------------------
    # Phase 1 — write target attribute schema (if not exists)
    # ------------------------------------------------------------------
    target_attrs_path = phase1_dir / f'{effective_task_name}.target_attrs.json'
    if not target_attrs_path.exists():
        schema = adapter.get_target_attribute_schema()
        _write_json(target_attrs_path, schema)
        print(f"[ingest] Wrote Phase-1 target_attrs → {target_attrs_path.name}")
    else:
        print(f"[ingest] Phase-1 target_attrs already exists — keeping")

    # Phase 1 — nuanced_attrs (empty for benchmark tasks)
    nuanced_attrs_path = phase1_dir / f'{effective_task_name}.nuanced_attrs.json'
    if not nuanced_attrs_path.exists():
        _write_json(nuanced_attrs_path, {})
        print(f"[ingest] Wrote Phase-1 nuanced_attrs → {nuanced_attrs_path.name}")

    # ------------------------------------------------------------------
    # Phase 2 — write rubric (if not exists)
    # ------------------------------------------------------------------
    rubric_path = phase2_dir / f'{effective_task_name}.rubric.json'
    if not rubric_path.exists():
        rubric = adapter.get_rubric()
        _write_json(rubric_path, rubric)
        print(f"[ingest] Wrote Phase-2 rubric → {rubric_path.name}")
    else:
        print(f"[ingest] Phase-2 rubric already exists — keeping")

    # ------------------------------------------------------------------
    # Phase 3 — write datapoints (Extend mode: skip existing IDs)
    # ------------------------------------------------------------------
    dp_path = phase3_dir / f'{effective_task_name}.{teacher_id}.datapoints.jsonl'
    existing_ids = _existing_ids(dp_path)
    existing_count = len(existing_ids)
    if existing_count:
        print(f"[ingest] Found {existing_count} existing datapoints — skipping those")

    items = adapter.load(data_dir, split=split)
    n_written = 0
    n_skipped = 0

    with open(dp_path, 'a', encoding='utf-8') as fh:
        for i, item in enumerate(items, start=1):
            if limit is not None and n_written >= limit:
                break

            # Build a stable CoEval datapoint ID
            dp_id = f'{effective_task_name}__{teacher_id}__{item.id}'

            if dp_id in existing_ids:
                n_skipped += 1
                continue

            record: dict[str, Any] = {
                'id': dp_id,
                'task_id': effective_task_name,
                'teacher_model_id': teacher_id,
                'sampled_target_attributes': item.target_attributes,
                'prompt': item.prompt,
                'reference_response': item.reference_answer or '',
                'generated_at': _now_iso(),
            }
            fh.write(json.dumps(record, ensure_ascii=False) + '\n')
            n_written += 1

            if verbose and n_written % 100 == 0:
                print(f"[ingest]   … {n_written} written")

    total = existing_count + n_written
    print(
        f"[ingest] Phase-3 datapoints: {n_written} new written, "
        f"{n_skipped} skipped (duplicate), {total} total → {dp_path.name}"
    )

    if n_written == 0 and existing_count == 0:
        print(
            "WARNING: No datapoints were written. Check that the benchmark data "
            f"is downloaded at '{data_dir / benchmark_name / split}.jsonl'.",
            file=sys.stderr,
        )

    # ------------------------------------------------------------------
    # Update config.yaml — add benchmark teacher and task if missing
    # ------------------------------------------------------------------
    cfg = _read_yaml(config_path)
    cfg = _patch_config(cfg, adapter, teacher_id, effective_task_name)
    _write_yaml(config_path, cfg)
    print(f"[ingest] Updated config.yaml")

    # ------------------------------------------------------------------
    # Update meta.json — record ingest event
    # ------------------------------------------------------------------
    meta = _read_json(meta_path)
    if 'ingest_log' not in meta:
        meta['ingest_log'] = []
    meta['ingest_log'].append({
        'benchmark': benchmark_name,
        'teacher_id': teacher_id,
        'task_name': effective_task_name,
        'n_written': n_written,
        'n_skipped': n_skipped,
        'ingested_at': _now_iso(),
    })
    meta['updated_at'] = _now_iso()
    _write_json(meta_path, meta)
    print(f"[ingest] Updated meta.json")

    return n_written


def _patch_config(
    cfg: dict,
    adapter: Any,
    teacher_id: str,
    task_name: str,
) -> dict:
    """Ensure *cfg* contains the benchmark teacher model and task definitions."""
    # --- Models ---
    models: list[dict] = cfg.setdefault('models', [])
    existing_model_names = {m.get('name') for m in models}
    if teacher_id not in existing_model_names:
        models.append({
            'name': teacher_id,
            'interface': 'benchmark',
            'roles': ['teacher'],
            'parameters': {
                'description': adapter.description,
                'homepage': adapter.homepage,
            },
        })

    # --- Tasks ---
    tasks: list[dict] = cfg.setdefault('tasks', [])
    existing_task_names = {t.get('name') for t in tasks}
    if task_name not in existing_task_names:
        schema = adapter.get_target_attribute_schema()
        label_attrs = adapter.get_label_attributes()
        task_def: dict[str, Any] = {
            'name': task_name,
            'description': adapter.description,
            'output_description': adapter.output_description,
            'target_attributes': schema or {},
            'nuanced_attributes': {},
            'sampling': {
                'target': [1, 1],
                'nuance': [0, 0],
                'total': 0,
            },
            'rubric': adapter.get_rubric(),
        }
        if label_attrs:
            task_def['label_attributes'] = label_attrs
        tasks.append(task_def)

    return cfg


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def cmd_ingest(args: argparse.Namespace) -> None:
    run_path = Path(args.run)
    if not run_path.exists():
        print(f"ERROR: Run path '{run_path}' does not exist.", file=sys.stderr)
        sys.exit(1)

    data_dir = Path(args.data_dir)
    benchmarks: list[str] = args.benchmarks

    total_written = 0
    for bname in benchmarks:
        try:
            from experiments.benchmarks import get_adapter as _get_adapter
            _adapter = _get_adapter(bname)
            effective_split = args.split or _adapter.default_split
            n = ingest_benchmark(
                run_path=run_path,
                benchmark_name=bname,
                data_dir=data_dir,
                split=effective_split,
                limit=args.limit,
                task_name=getattr(args, 'task_name', None),
                verbose=getattr(args, 'verbose', False),
            )
            total_written += n
        except KeyError as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            sys.exit(1)
        except FileNotFoundError as exc:
            print(
                f"ERROR: Benchmark data not found: {exc}\n"
                "  Run:  python stdbenchmarks/download_benchmarks.py"
                f" --benchmarks {bname}",
                file=sys.stderr,
            )
            sys.exit(1)

    print(
        f"\n[ingest] Done. {total_written} total datapoints written.\n"
        f"  Next step: coeval run --config {run_path}/config.yaml --continue"
    )
