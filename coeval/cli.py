"""CLI entry point for `coeval run` (REQ-8.1)."""
from __future__ import annotations

import argparse
import sys

from .config import load_config, validate_config
from .runner import print_execution_plan, run_experiment


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog='coeval',
        description='CoEval — Self-evaluating LLM ensemble benchmarking system',
    )
    sub = parser.add_subparsers(dest='command', required=True)

    # ---- coeval run ----
    run_p = sub.add_parser('run', help='Execute an evaluation experiment (EER)')
    run_p.add_argument(
        '--config', required=True, metavar='PATH',
        help='Path to the YAML configuration file',
    )
    run_p.add_argument(
        '--resume', metavar='EXPERIMENT_ID',
        help='Experiment ID to resume. Overrides experiment.resume_from in config.',
    )
    run_p.add_argument(
        '--dry-run', action='store_true',
        help='Validate config and print execution plan without making LLM calls',
    )
    run_p.add_argument(
        '--log-level', metavar='LEVEL',
        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
        help='Override the log level from config',
    )

    return parser


def main(argv: list[str] | None = None) -> None:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.command == 'run':
        _cmd_run(args)


def _cmd_run(args: argparse.Namespace) -> None:
    # Load config
    try:
        cfg = load_config(args.config)
    except Exception as exc:
        print(f"ERROR: Failed to load config '{args.config}': {exc}", file=sys.stderr)
        sys.exit(1)

    # Apply CLI overrides
    if args.resume:
        cfg.experiment.resume_from = args.resume
    if args.log_level:
        cfg.experiment.log_level = args.log_level

    # Validate — report all errors, exit 1 if any (REQ-8.1.5)
    errors = validate_config(cfg)
    if errors:
        print("Configuration errors:", file=sys.stderr)
        for err in errors:
            print(f"  • {err}", file=sys.stderr)
        sys.exit(1)

    # Print execution plan (always, not just dry-run)
    print_execution_plan(cfg)

    if args.dry_run:
        print("Dry-run: config valid. Exiting without making LLM calls.")
        sys.exit(0)

    exit_code = run_experiment(cfg, dry_run=False)
    sys.exit(exit_code)


if __name__ == '__main__':
    main()
