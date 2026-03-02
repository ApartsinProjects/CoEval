"""CLI script: download benchmark datasets and emit CoEval Phase 3 JSONL files.

Usage
-----
# Emit all four benchmarks to a run folder:
    python -m benchmark.emit_datapoints --run-id paper-eval-v1

# Emit a single benchmark:
    python -m benchmark.emit_datapoints --dataset xsum --run-id paper-eval-v1

# Custom output directory:
    python -m benchmark.emit_datapoints \\
        --dataset codesearchnet \\
        --out-dir ./Runs/my-run/phase3_datapoints \\
        --sample-size 300

All output files follow the Phase 3 naming convention:
    {task_id}.{teacher_id}.datapoints.jsonl

so they can be placed directly in a CoEval experiment's
``phase3_datapoints/`` folder.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Dataset → (loader args, default output filename, task_id)
# ---------------------------------------------------------------------------
_DATASETS: dict[str, dict] = {
    "xsum": {
        "task_id": "text_summarization",
        "loader_kwargs": {},
        "teacher_id": "xsum",
    },
    "codesearchnet": {
        "task_id": "code_explanation",
        "loader_kwargs": {"language": "python"},
        "teacher_id": "codesearchnet-python",
    },
    "aeslc": {
        "task_id": "email_composition",
        "loader_kwargs": {},
        "teacher_id": "aeslc",
    },
    "wikitablequestions": {
        "task_id": "data_interpretation",
        "loader_kwargs": {},
        "teacher_id": "wikitablequestions",
    },
}


def _out_filename(task_id: str, teacher_id: str) -> str:
    return f"{task_id}.{teacher_id}.datapoints.jsonl"


def emit_dataset(
    dataset: str,
    out_dir: Path,
    sample_size: int,
    split: str | None,
    seed: int,
    attribute_map_path: str | None,
) -> int:
    from benchmark.loaders import load_benchmark

    info = _DATASETS[dataset]
    task_id = info["task_id"]
    teacher_id = info["teacher_id"]
    loader_kwargs = info["loader_kwargs"].copy()

    out_file = out_dir / _out_filename(task_id, teacher_id)

    print(f"  [{dataset}] -> {out_file}")
    n = load_benchmark(
        dataset=dataset,
        out_path=out_file,
        attribute_map_path=attribute_map_path,
        sample_size=sample_size,
        split=split,
        seed=seed,
        **loader_kwargs,
    )
    print(f"  [{dataset}] wrote {n} records  OK")
    return n


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Download benchmark datasets and emit CoEval Phase 3 JSONL."
    )
    parser.add_argument(
        "--dataset", "-d",
        choices=list(_DATASETS.keys()) + ["all"],
        default="all",
        help="Dataset to emit (default: all)",
    )
    parser.add_argument(
        "--run-id", "-r",
        default=None,
        help="Experiment run ID; output goes to Runs/<run-id>/phase3_datapoints/",
    )
    parser.add_argument(
        "--out-dir", "-o",
        default=None,
        help="Override output directory (takes precedence over --run-id)",
    )
    parser.add_argument(
        "--sample-size", "-n",
        type=int,
        default=620,
        help="Items to emit per dataset (default: 620)",
    )
    parser.add_argument(
        "--split",
        default=None,
        help="Dataset split override (default: loader's default, usually 'validation')",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed for stratified sampling (default: 42)",
    )
    parser.add_argument(
        "--attribute-map",
        default=None,
        help="Override attribute map YAML path (applies to all datasets if --dataset=all)",
    )

    args = parser.parse_args(argv)

    # Resolve output directory
    if args.out_dir:
        out_dir = Path(args.out_dir)
    elif args.run_id:
        out_dir = Path("Runs") / args.run_id / "phase3_datapoints"
    else:
        parser.error("Provide --run-id or --out-dir")
        return 1

    out_dir.mkdir(parents=True, exist_ok=True)
    print(f"Output directory: {out_dir}\n")

    datasets = list(_DATASETS.keys()) if args.dataset == "all" else [args.dataset]
    total = 0
    errors = []

    for ds in datasets:
        try:
            n = emit_dataset(
                dataset=ds,
                out_dir=out_dir,
                sample_size=args.sample_size,
                split=args.split,
                seed=args.seed,
                attribute_map_path=args.attribute_map,
            )
            total += n
        except Exception as exc:
            msg = f"  [{ds}] FAILED: {exc}"
            print(msg, file=sys.stderr)
            errors.append(msg)

    print(f"\nTotal records written: {total}")
    if errors:
        print(f"\nErrors ({len(errors)}):", file=sys.stderr)
        for e in errors:
            print(e, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
