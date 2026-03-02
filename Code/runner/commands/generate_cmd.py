"""coeval generate — generate task design (attributes + rubric) and write a
materialized YAML configuration.

Runs Phase 1 (attribute mapping) and Phase 2 (rubric mapping) for all tasks
using the teacher models in the config.  All ``target_attributes: auto/complete``
and ``rubric: auto/extend`` entries are replaced with the generated static values
and written to a new YAML file that can be reviewed, edited, and passed directly
to ``coeval run``.

Because phases 1 and 2 run in a temporary staging directory, the output YAML has
the same ``experiment.id`` as the source config with no folder conflict.

Usage::

    # Step 1 — generate attributes and rubric:
    coeval generate --config draft.yaml --out design.yaml

    # Step 2 — review/edit design.yaml (attributes and rubric are now static lists)

    # Step 3 — run the full pipeline from the materialized design:
    coeval run --config design.yaml
"""
from __future__ import annotations

import argparse
import copy
import os
import shutil
import sys
import tempfile
from datetime import datetime, timezone


def cmd_generate(args: argparse.Namespace) -> None:
    """Entry point for ``coeval generate``."""
    from ..config import load_config, validate_config
    from ..interfaces.pool import ModelPool
    from ..interfaces.probe import run_probe
    from ..logger import RunLogger
    from ..phases.phase1 import run_phase1
    from ..phases.phase2 import run_phase2
    from ..phases.utils import QuotaTracker
    from ..storage import ExperimentStorage

    # --- Load config ---
    try:
        cfg = load_config(args.config, keys_file=getattr(args, 'keys', None))
    except Exception as exc:
        print(f"ERROR: Failed to load config '{args.config}': {exc}", file=sys.stderr)
        sys.exit(1)

    # --- Validate (skip folder checks — generation uses a temp dir) ---
    errors = validate_config(cfg, _skip_folder_validation=True)
    if errors:
        print("Configuration errors:", file=sys.stderr)
        for err in errors:
            print(f"  * {err}", file=sys.stderr)
        sys.exit(1)

    log_level = getattr(args, 'log_level', None) or 'INFO'
    probe_mode = getattr(args, 'probe_mode', None) or cfg.experiment.probe_mode or 'full'
    probe_on_fail = getattr(args, 'probe_on_fail', None) or cfg.experiment.probe_on_fail or 'abort'

    # Verify at least one teacher exists
    teachers = cfg.get_models_by_role('teacher')
    has_dynamic = any(
        not isinstance(t.target_attributes, dict) or not isinstance(t.rubric, dict)
        for t in cfg.tasks
    )
    if not teachers and has_dynamic:
        print(
            "ERROR: No teacher models defined.  At least one model with role 'teacher' "
            "is required to generate attributes and rubric.",
            file=sys.stderr,
        )
        sys.exit(1)

    # --- Run phases 1–2 in a temporary staging directory ---
    staging_dir = tempfile.mkdtemp(prefix='coeval_generate_')
    try:
        staging_storage = ExperimentStorage(staging_dir, cfg.experiment.id)
        staging_storage.initialize(cfg._raw)

        log_path = os.path.join(staging_dir, cfg.experiment.id, 'generate.log')
        logger = RunLogger(log_path, min_level=log_level, console=True)

        if probe_mode != 'disable':
            run_probe(cfg, logger, mode=probe_mode, on_fail=probe_on_fail)

        pool = ModelPool()
        quota = QuotaTracker(cfg.experiment.quota)

        print("\n[coeval generate] Phase 1 — attribute mapping")
        run_phase1(cfg, staging_storage, logger, pool, quota, phase_mode='New')

        print("\n[coeval generate] Phase 2 — rubric mapping")
        run_phase2(cfg, staging_storage, logger, pool, quota, phase_mode='New')

        # --- Build materialized config ---
        materialized_raw, changes = _materialize_config(cfg, staging_storage)

    finally:
        shutil.rmtree(staging_dir, ignore_errors=True)

    # --- Write output YAML ---
    _write_design_yaml(materialized_raw, args.out, args.config, changes)

    print(f"\n[coeval generate] Design written to: {args.out}")
    print("[coeval generate] Changes applied:")
    for ch in changes:
        print(f"  {ch}")
    print(f"\nReview and edit {args.out}, then run:")
    print(f"  coeval run --config {args.out}")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _materialize_config(cfg, storage) -> tuple[dict, list[str]]:
    """Read generated phase 1–2 artifacts and embed them as static values.

    Returns ``(materialized_raw_dict, list_of_change_descriptions)``.
    Static attributes/rubric already present in the draft config are left unchanged.
    """
    raw = copy.deepcopy(cfg._raw)
    changes: list[str] = []

    for i, task_cfg in enumerate(cfg.tasks):
        task_id = task_cfg.name
        task_raw = raw['tasks'][i]

        # target_attributes ---------------------------------------------------
        if not isinstance(task_cfg.target_attributes, dict):
            try:
                generated = storage.read_target_attrs(task_id)
                task_raw['target_attributes'] = generated
                task_raw.pop('target_attributes_seed', None)
                changes.append(
                    f"[{task_id}] target_attributes: '{task_cfg.target_attributes}' "
                    f"→ {_attr_summary(generated)}"
                )
            except Exception as exc:
                changes.append(
                    f"[{task_id}] target_attributes: WARNING — could not read: {exc}"
                )

        # nuanced_attributes --------------------------------------------------
        nuanced = task_cfg.nuanced_attributes
        if nuanced and not isinstance(nuanced, dict):
            try:
                generated = storage.read_nuanced_attrs(task_id)
                task_raw['nuanced_attributes'] = generated
                task_raw.pop('nuanced_attributes_seed', None)
                changes.append(
                    f"[{task_id}] nuanced_attributes: '{nuanced}' "
                    f"→ {_attr_summary(generated)}"
                )
            except Exception as exc:
                changes.append(
                    f"[{task_id}] nuanced_attributes: WARNING — could not read: {exc}"
                )

        # rubric --------------------------------------------------------------
        if not isinstance(task_cfg.rubric, dict):
            try:
                generated = storage.read_rubric(task_id)
                task_raw['rubric'] = generated
                changes.append(
                    f"[{task_id}] rubric: '{task_cfg.rubric}' "
                    f"→ {len(generated)} factors: {list(generated.keys())}"
                )
            except Exception as exc:
                changes.append(
                    f"[{task_id}] rubric: WARNING — could not read: {exc}"
                )

    if not changes:
        changes.append("(nothing to generate — all attributes and rubrics are already static)")

    return raw, changes


def _attr_summary(attr_map: dict) -> str:
    """Short human-readable summary, e.g. {tone(3), urgency(2)}."""
    if not attr_map:
        return '{}'
    parts = [f"{k}({len(v)})" for k, v in attr_map.items()]
    return '{' + ', '.join(parts) + '}'


def _write_design_yaml(raw: dict, out_path: str, source_config: str, changes: list[str]) -> None:
    """Write the materialized config as a YAML file with an informative header comment."""
    try:
        import yaml
    except ImportError:
        raise ImportError("PyYAML is required: pip install pyyaml")

    ts = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    header_lines = [
        f"# Generated by: coeval generate --config {source_config} --out {out_path}",
        f"# Generated at: {ts}",
        "#",
        "# Review and edit the generated attributes and rubric below, then run:",
        f"#   coeval run --config {out_path}",
        "#",
        "# Changes from source config:",
    ]
    for ch in changes:
        header_lines.append(f"#   {ch}")
    header_lines.append("#")
    header = '\n'.join(header_lines) + '\n\n'

    body = yaml.dump(raw, default_flow_style=False, allow_unicode=True, sort_keys=False)

    with open(out_path, 'w', encoding='utf-8') as f:
        f.write(header)
        f.write(body)
