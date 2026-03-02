"""Setup script for the 'mixed' CoEval experiment.

Downloads 4 public benchmark datasets (10 items each) and places them into
the experiment's ``phase3_datapoints/`` folder as virtual benchmark teachers
(xsum, codesearchnet-python, aeslc, wikitablequestions),
then creates the skeleton folders and ``meta.json`` required by ``--continue``.

Run once before starting the experiment:

    python -m benchmark.setup_mixed

Then launch the experiment:

    coeval run --config Runs/mixed/mixed.yaml --continue

The script is idempotent: if a Phase 3 file already contains >= 10 records it is
left untouched, and if ``meta.json`` already exists it is not overwritten.

Benchmarks → CoEval tasks
--------------------------
  XSum            → text_summarization
  CodeSearchNet   → code_explanation      (Python-only subset)
  AESLC           → email_composition
  WikiTableQs     → data_interpretation
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

# Force UTF-8 I/O on Windows (avoids charmap encoding errors from HuggingFace
# progress bars and article text that contains non-Latin Unicode characters).
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

EXPERIMENT_ID = "mixed"
RUNS_DIR = Path("Runs")
SAMPLE_SIZE = 10

# Maps (dataset_name, loader_kwargs, task_id, teacher_name)
_INGESTION_PLAN: list[tuple[str, dict, str, str]] = [
    ("xsum",               {},                      "text_summarization",  "xsum"),
    ("codesearchnet",      {"language": "python"},  "code_explanation",    "codesearchnet-python"),
    ("aeslc",              {},                      "email_composition",   "aeslc"),
    ("wikitablequestions", {},                      "data_interpretation", "wikitablequestions"),
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _count_jsonl_lines(path: Path) -> int:
    """Return number of non-empty lines in a JSONL file (0 if missing)."""
    if not path.exists():
        return 0
    count = 0
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            if line.strip():
                count += 1
    return count


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    exp_dir = RUNS_DIR / EXPERIMENT_ID
    phase3_dir = exp_dir / "phase3_datapoints"

    # 1. Create full directory skeleton (idempotent)
    for subdir in (
        "phase1_attributes",
        "phase2_rubric",
        "phase3_datapoints",
        "phase4_responses",
        "phase5_evaluations",
    ):
        (exp_dir / subdir).mkdir(parents=True, exist_ok=True)
    print(f"[setup] Experiment directory: {exp_dir.resolve()}")

    # 2. Ingest each benchmark dataset → phase3_datapoints/{task_id}.{teacher_name}.datapoints.jsonl
    from benchmark.loaders import load_benchmark

    for dataset, loader_kwargs, task_id, teacher_name in _INGESTION_PLAN:
        dst_path = phase3_dir / f"{task_id}.{teacher_name}.datapoints.jsonl"
        existing = _count_jsonl_lines(dst_path)

        if existing >= SAMPLE_SIZE:
            print(
                f"[setup] [{dataset}] {dst_path.name} already has {existing} records "
                f"(>= {SAMPLE_SIZE}) — skipping"
            )
            continue

        print(f"[setup] [{dataset}] downloading and sampling {SAMPLE_SIZE} items...")
        try:
            n = load_benchmark(
                dataset=dataset,
                out_path=dst_path,
                sample_size=SAMPLE_SIZE,
                split=None,   # use each loader's default split
                seed=42,
                **loader_kwargs,
            )
            print(f"[setup] [{dataset}] wrote {n} records -> {dst_path.name}")
        except Exception as exc:
            print(
                f"[setup] [{dataset}] FAILED: {exc}",
                file=sys.stderr,
            )
            return 1

    # 3. Write meta.json (required by V-14 / --continue validation)
    meta_path = exp_dir / "meta.json"
    if meta_path.exists():
        print(f"[setup] meta.json already exists — not overwriting")
    else:
        meta = {
            "experiment_id": EXPERIMENT_ID,
            "status": "in_progress",
            "created_at": _now_iso(),
            "updated_at": _now_iso(),
            "phases_completed": [],
            "phases_in_progress": [],
            "resume_from": None,
        }
        with open(meta_path, "w", encoding="utf-8") as fh:
            json.dump(meta, fh, indent=2)
            fh.write("\n")
        print(f"[setup] Wrote meta.json")

    # 4. Summary
    print()
    print("=" * 65)
    print(" Mixed benchmark setup complete!")
    print("=" * 65)
    print()
    print(" Phase 3 datapoints ingested:")
    for _, _, task_id, teacher_name in _INGESTION_PLAN:
        p = phase3_dir / f"{task_id}.{teacher_name}.datapoints.jsonl"
        n = _count_jsonl_lines(p)
        print(f"   {p.name:55s}  {n:3d} records")
    print()
    print(" Next step — run the experiment:")
    print()
    print("   coeval run --config benchmark/mixed.yaml --continue")
    print()

    return 0


if __name__ == "__main__":
    sys.exit(main())
