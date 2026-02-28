"""coeval plan — standalone cost and time estimation.

Runs the cost/time estimator and prints a breakdown without executing any
pipeline phases.  Optionally makes a small number of sample API calls per model
to calibrate latency (use ``--estimate-samples 0`` for heuristics only).

When combined with ``--continue``, estimates only the remaining work for an
already-started experiment by reading existing phase artifacts from storage.

Usage::

    coeval plan --config my_experiment.yaml
    coeval plan --config my_experiment.yaml --estimate-samples 0
    coeval plan --config my_experiment.yaml --continue
"""
from __future__ import annotations

import argparse
import os
import sys


def cmd_plan(args: argparse.Namespace) -> None:
    """Entry point for ``coeval plan``."""
    from ..config import load_config, validate_config
    from ..interfaces.cost_estimator import estimate_experiment_cost
    from ..logger import RunLogger
    from ..storage import ExperimentStorage

    # --- Load config ---
    try:
        cfg = load_config(args.config)
    except Exception as exc:
        print(f"ERROR: Failed to load config '{args.config}': {exc}", file=sys.stderr)
        sys.exit(1)

    continue_in_place: bool = getattr(args, 'continue_in_place', False)

    # Apply CLI overrides for estimate_samples
    estimate_samples_override = getattr(args, 'estimate_samples', None)
    if estimate_samples_override is not None:
        cfg.experiment.estimate_samples = estimate_samples_override

    # --- Validate config ---
    # Skip folder checks when NOT continuing (folder may not exist yet for planning)
    errors = validate_config(
        cfg,
        continue_in_place=continue_in_place,
        _skip_folder_validation=not continue_in_place,
    )
    if errors:
        print("Configuration errors:", file=sys.stderr)
        for err in errors:
            print(f"  * {err}", file=sys.stderr)
        sys.exit(1)

    # --- Console-only logger ---
    log_level = getattr(args, 'log_level', None) or 'INFO'
    logger = RunLogger(os.devnull, min_level=log_level, console=True)

    # --- Create storage (don't initialize — just point at the path) ---
    storage = ExperimentStorage(cfg.experiment.storage_folder, cfg.experiment.id)

    # --- Read completed phases if continuing ---
    completed_phases: set[str] | None = None
    if continue_in_place:
        try:
            meta = storage.read_meta()
            completed_phases = set(meta.get('phases_completed', []))
        except Exception as exc:
            print(
                f"WARNING: Could not read meta.json, treating as fresh run: {exc}",
                file=sys.stderr,
            )

    # --- Estimation parameters ---
    n_samples = cfg.experiment.estimate_samples
    run_sample_calls = n_samples != 0

    # --- Run estimator ---
    try:
        estimate_experiment_cost(
            cfg,
            storage,
            logger,
            n_samples=n_samples,
            run_sample_calls=run_sample_calls,
            continue_in_place=continue_in_place,
            completed_phases=completed_phases,
        )
    except Exception as exc:
        print(f"ERROR: Estimation failed: {exc}", file=sys.stderr)
        sys.exit(1)
