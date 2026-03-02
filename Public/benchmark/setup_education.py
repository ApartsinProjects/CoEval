#!/usr/bin/env python3
"""One-time setup script for the education domain benchmark.

Downloads and ingests three real benchmark datasets as Phase 3 teacher data:

  Dataset             | HuggingFace ID            | Task
  --------------------|---------------------------|--------------------------
  ARC-Challenge       | allenai/ai2_arc           | arc_science_reasoning
  RACE-High           | ehovy/race (high)         | race_reading_comprehension
  SciQ                | allenai/sciq              | sciq_science_questions

After ingestion the folder structure is ready for ``coeval run --continue``:

    benchmark/runs/education-benchmark-v1/
    ├── meta.json
    ├── phase1_attributes/          (empty — filled by Phase 1)
    ├── phase2_rubric/              (empty — filled by Phase 2)
    ├── phase3_datapoints/
    │   ├── arc_science_reasoning.arc-challenge.datapoints.jsonl
    │   ├── race_reading_comprehension.race-high.datapoints.jsonl
    │   └── sciq_science_questions.sciq.datapoints.jsonl
    ├── phase4_responses/           (empty — filled by Phase 4)
    └── phase5_evaluations/         (empty — filled by Phase 5)

Usage
-----
    python -m benchmark.setup_education

Then run the full experiment:
    coeval probe  --config benchmark/education.yaml
    coeval plan   --config benchmark/education.yaml
    coeval run    --config benchmark/education.yaml --continue
    coeval analyze all --run benchmark/runs/education-benchmark-v1 --out reports/education
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

EXPERIMENT_ID = "education-benchmark-v1"
RUNS_DIR      = Path(__file__).parent / "runs"
SAMPLE_SIZE   = 30      # items per benchmark task
                         # Use 150–300 for a research-grade run

# Ingestion plan: (dataset_name, loader_kwargs, task_id, teacher_name)
# teacher_name must match the model `name:` in education.yaml
_INGESTION_PLAN: list[tuple[str, dict, str, str]] = [
    (
        "arc_challenge",
        {},
        "arc_science_reasoning",
        "arc-challenge",
    ),
    (
        "race",
        {"level": "high"},
        "race_reading_comprehension",
        "race-high",
    ),
    (
        "sciq",
        {},
        "sciq_science_questions",
        "sciq",
    ),
]

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _ensure_dirs(exp_dir: Path) -> None:
    for sub in [
        "phase1_attributes",
        "phase2_rubric",
        "phase3_datapoints",
        "phase4_responses",
        "phase5_evaluations",
    ]:
        (exp_dir / sub).mkdir(parents=True, exist_ok=True)


def _write_meta(exp_dir: Path) -> None:
    meta_path = exp_dir / "meta.json"
    if meta_path.exists():
        return   # preserve any existing state
    meta = {
        "experiment_id":   EXPERIMENT_ID,
        "config_path":     str(Path(__file__).parent / "education.yaml"),
        "phases_completed": [],
        "storage_folder":  str(exp_dir),
    }
    with open(meta_path, "w", encoding="utf-8") as fh:
        json.dump(meta, fh, indent=2)
    print(f"  Wrote meta.json")

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    exp_dir    = RUNS_DIR / EXPERIMENT_ID
    phase3_dir = exp_dir / "phase3_datapoints"

    print(f"Education benchmark setup")
    print(f"  Experiment : {EXPERIMENT_ID}")
    print(f"  Folder     : {exp_dir}")
    print(f"  Sample size: {SAMPLE_SIZE} items per dataset\n")

    _ensure_dirs(exp_dir)

    from benchmark.loaders import load_benchmark  # noqa: PLC0415

    total_written = 0
    for dataset, loader_kwargs, task_id, teacher_name in _INGESTION_PLAN:
        out_path = phase3_dir / f"{task_id}.{teacher_name}.datapoints.jsonl"

        if out_path.exists():
            existing = sum(1 for _ in open(out_path, encoding="utf-8"))
            print(f"  {dataset:<20} → {out_path.name}  (already exists, {existing} records — skipping)")
            total_written += existing
            continue

        print(f"  {dataset:<20} → {out_path.name}  ingesting …", end="", flush=True)
        try:
            n = load_benchmark(
                dataset=dataset,
                out_path=out_path,
                sample_size=SAMPLE_SIZE,
                seed=42,
                **loader_kwargs,
            )
            print(f"  {n} records written")
            total_written += n
        except Exception as exc:
            print(f"\n  ERROR: {exc}", file=sys.stderr)
            sys.exit(1)

    _write_meta(exp_dir)

    print(f"\n✅  Education benchmark setup complete.")
    print(f"    Total Phase 3 records : {total_written}")
    print(f"\nNext steps:")
    print(f"  coeval probe  --config benchmark/education.yaml")
    print(f"  coeval plan   --config benchmark/education.yaml")
    print(f"  coeval run    --config benchmark/education.yaml --continue")
    print(f"  coeval analyze all --run {exp_dir} --out reports/education")


if __name__ == "__main__":
    main()
