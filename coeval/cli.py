"""CLI entry point for `coeval run` (REQ-8.1) and `coeval analyze` (REQ-A-8.1)."""
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

    # ---- coeval analyze ---- (REQ-A-8.1)
    analyze_p = sub.add_parser('analyze', help='Analyze an EES experiment (EEA)')
    analyze_sub = analyze_p.add_subparsers(dest='subcommand', required=True)

    _SUBCOMMANDS = [
        ('complete-report',   'Excel workbook with all slice/aggregate data'),
        ('score-distribution','HTML: score distribution by aspect, model, attribute'),
        ('teacher-report',    'HTML: teacher differentiation scores'),
        ('judge-report',      'HTML: judge agreement and reliability scores'),
        ('student-report',    'HTML: student model performance report'),
        ('interaction-matrix','HTML: teacher-student interaction heatmap'),
        ('judge-consistency', 'HTML: within-judge consistency analysis'),
        ('coverage-summary',  'HTML: EES artifact coverage and error breakdown'),
        ('robust-summary',    'HTML: robust student ranking with filtered datapoints'),
        ('export-benchmark',  'JSONL/Parquet: export robust benchmark datapoints'),
        ('all',               'Generate all HTML reports + Excel into subdirectories'),
    ]

    for sc_name, sc_help in _SUBCOMMANDS:
        sc_p = analyze_sub.add_parser(sc_name, help=sc_help)
        sc_p.add_argument('--run', required=True, metavar='PATH',
                          help='Path to the EES experiment folder')
        sc_p.add_argument('--out', required=True, metavar='PATH',
                          help='Output path (file for Excel/JSONL; folder for HTML/all)')
        sc_p.add_argument('--partial-ok', action='store_true',
                          help='Allow analysis on in-progress experiments without warning')
        sc_p.add_argument('--log-level', metavar='LEVEL',
                          choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
                          default='INFO', help='Log level')
        # Robust filtering options (apply to robust-summary, export-benchmark, all)
        if sc_name in ('robust-summary', 'export-benchmark', 'all'):
            sc_p.add_argument('--judge-selection', default='top_half',
                              choices=['top_half', 'all'],
                              help='Judge selection for robust filtering (default: top_half)')
            sc_p.add_argument('--agreement-metric', default='spa',
                              choices=['spa', 'wpa', 'kappa'],
                              help='Agreement metric for judge ranking (default: spa)')
            sc_p.add_argument('--agreement-threshold', type=float, default=1.0,
                              metavar='FLOAT',
                              help='Min judge-consistency fraction θ (default: 1.0)')
            sc_p.add_argument('--teacher-score-formula', default='v1',
                              choices=['v1', 's2', 'r3'],
                              help='Teacher score formula for T* selection (default: v1)')
        if sc_name == 'export-benchmark':
            sc_p.add_argument('--benchmark-format', default='jsonl',
                              choices=['jsonl', 'parquet'],
                              help='Output format (default: jsonl)')

    return parser


def main(argv: list[str] | None = None) -> None:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.command == 'run':
        _cmd_run(args)
    elif args.command == 'analyze':
        _cmd_analyze(args)


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


def _cmd_analyze(args: argparse.Namespace) -> None:
    from .analyze.main import run_analyze

    # Build robust kwargs (only if the subcommand supports them)
    robust_supported = args.subcommand in ('robust-summary', 'export-benchmark', 'all')

    exit_code = run_analyze(
        run_path=args.run,
        out_path=args.out,
        subcommand=args.subcommand,
        judge_selection=getattr(args, 'judge_selection', 'top_half') if robust_supported else 'top_half',
        agreement_metric=getattr(args, 'agreement_metric', 'spa') if robust_supported else 'spa',
        agreement_threshold=getattr(args, 'agreement_threshold', 1.0) if robust_supported else 1.0,
        teacher_score_formula=getattr(args, 'teacher_score_formula', 'v1') if robust_supported else 'v1',
        benchmark_format=getattr(args, 'benchmark_format', 'jsonl'),
        partial_ok=getattr(args, 'partial_ok', False),
        log_level=getattr(args, 'log_level', 'INFO'),
    )
    sys.exit(exit_code)


if __name__ == '__main__':
    main()
