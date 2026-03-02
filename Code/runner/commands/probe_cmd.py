"""coeval probe — standalone model availability probe.

Runs the same probe that ``coeval run`` executes before starting the pipeline,
but without starting any experiment phases.  Useful for verifying API keys and
model access before committing to a full run.

Usage::

    coeval probe --config my_experiment.yaml
    coeval probe --config my_experiment.yaml --probe resume
    coeval probe --config my_experiment.yaml --probe-on-fail warn
"""
from __future__ import annotations

import argparse
import os
import sys


def cmd_probe(args: argparse.Namespace) -> None:
    """Entry point for ``coeval probe``."""
    from ..config import load_config, validate_config
    from ..interfaces.probe import run_probe
    from ..logger import RunLogger

    # --- Load config ---
    try:
        cfg = load_config(args.config)
    except Exception as exc:
        print(f"ERROR: Failed to load config '{args.config}': {exc}", file=sys.stderr)
        sys.exit(1)

    # --- Apply CLI overrides ---
    probe_mode = getattr(args, 'probe_mode', None)
    if probe_mode:
        cfg.experiment.probe_mode = probe_mode

    probe_on_fail = getattr(args, 'probe_on_fail', None)
    if probe_on_fail:
        cfg.experiment.probe_on_fail = probe_on_fail

    # --- Validate (skip folder checks — probe is folder-state-agnostic) ---
    errors = validate_config(cfg, _skip_folder_validation=True)
    if errors:
        print("Configuration errors:", file=sys.stderr)
        for err in errors:
            print(f"  * {err}", file=sys.stderr)
        sys.exit(1)

    # --- Console-only logger (no file output for standalone commands) ---
    log_level = getattr(args, 'log_level', None) or 'INFO'
    logger = RunLogger(os.devnull, min_level=log_level, console=True)

    # --- Run probe ---
    mode = cfg.experiment.probe_mode
    on_fail = cfg.experiment.probe_on_fail

    results, _probed = run_probe(cfg, logger, mode=mode, on_fail=on_fail)

    # --- Print summary ---
    if not results:
        print("\nNo models probed (probe mode may be 'disable' or all phases done).")
        sys.exit(0)

    width = max(len(n) for n in results) + 2
    print(f"\n{'='*60}")
    print(f"Probe Results  (mode='{mode}', on_fail='{on_fail}')")
    print(f"{'='*60}")
    n_ok = n_fail = 0
    for model_name in sorted(results):
        status = results[model_name]
        if status == 'ok':
            status_str = '[OK]'
            n_ok += 1
        else:
            status_str = f'[FAIL] {status}'
            n_fail += 1
        print(f"  {model_name:{width}s}  {status_str}")
    print(f"{'='*60}")
    print(f"Total: {n_ok} available, {n_fail} unavailable\n")

    if n_fail and on_fail == 'abort':
        sys.exit(2)
