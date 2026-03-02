"""benchmark/run_baselines.py — Baseline evaluation methods for paper comparison.

Computes three standalone baseline methods against CoEval's composite judge scores:

    1. BERTScore-F1  — similarity between student response and benchmark reference
    2. G-Eval (GPT-4o)     — single LLM-as-judge score using GPT-4o
    3. G-Eval (Claude-3.5) — single LLM-as-judge score using Claude-3.5-Sonnet

For each method × task, computes Spearman ρ against ``benchmark_native_score``
(the ground-truth metric stored in Phase 3 JSONL by compute_scores.py).

Output
------
``<out>/baselines.csv`` — rows: (task_id, method, n_pairs, rho, p_value, coverage)

Usage
-----
    python -m benchmark.run_baselines \\
        --run benchmark/runs/paper-eval-v1 \\
        --out paper/tables \\
        [--methods bertscore geval-gpt4o geval-claude] \\
        [--bertscore-model distilbert-base-uncased] \\
        [--geval-model gpt-4o] \\
        [--max-pairs 200]        # subsample for cost control

Dependencies
------------
    pip install bert-score scipy
    OPENAI_API_KEY and/or ANTHROPIC_API_KEY must be set (or present in keys.yaml)
    for G-Eval methods.
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from pathlib import Path
from typing import Any

# Force UTF-8 I/O on Windows
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# ---------------------------------------------------------------------------
# Optional heavy dependencies — lazy imports
# ---------------------------------------------------------------------------

def _require_scipy():
    try:
        from scipy.stats import spearmanr
        return spearmanr
    except ImportError:
        print("ERROR: scipy not installed.\n  pip install scipy", file=sys.stderr)
        sys.exit(1)


def _require_bertscore():
    try:
        from bert_score import score as _bs
        return _bs
    except ImportError:
        print(
            "ERROR: bert-score not installed.\n  pip install bert-score",
            file=sys.stderr,
        )
        sys.exit(1)


# ---------------------------------------------------------------------------
# G-Eval prompt template
# ---------------------------------------------------------------------------

_GEVAL_SYSTEM = (
    "You are an impartial evaluator. Score the quality of the response below "
    "on a scale of 1 (very poor) to 5 (excellent). "
    "Consider: accuracy, clarity, relevance, and completeness. "
    "Reply with a SINGLE integer between 1 and 5 and nothing else."
)

_GEVAL_USER = (
    "Task: {task_description}\n\n"
    "Input prompt given to the model:\n{prompt}\n\n"
    "Model response:\n{response}\n\n"
    "Score (1-5):"
)


# ---------------------------------------------------------------------------
# Data loading helpers
# ---------------------------------------------------------------------------

def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    records = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if line:
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                pass
    return records


def _load_phase3(p3_dir: Path) -> dict[str, dict[str, Any]]:
    """Load all Phase 3 datapoints.  Key: datapoint_id -> record."""
    index: dict[str, dict[str, Any]] = {}
    for f in sorted(p3_dir.glob("*.datapoints.jsonl")):
        for rec in _read_jsonl(f):
            dp_id = rec.get("id")
            if dp_id:
                index[dp_id] = rec
    return index


def _load_phase4(p4_dir: Path) -> list[dict[str, Any]]:
    """Load all Phase 4 response records."""
    records: list[dict[str, Any]] = []
    for f in sorted(p4_dir.glob("*.responses.jsonl")):
        records.extend(_read_jsonl(f))
    return records


def _build_pairs(
    phase3: dict[str, dict[str, Any]],
    phase4: list[dict[str, Any]],
    max_pairs: int | None,
) -> dict[str, list[dict[str, Any]]]:
    """Join Phase 3 + Phase 4 on datapoint_id; group by task_id.

    Each resulting item has:
        task_id, datapoint_id, student_model_id,
        prompt, student_response, reference_response, benchmark_native_score
    """
    by_task: dict[str, list[dict[str, Any]]] = {}

    for resp in phase4:
        dp_id = resp.get("datapoint_id")
        dp = phase3.get(dp_id or "")
        if dp is None:
            continue

        bns = dp.get("benchmark_native_score")
        if bns is None:
            continue  # skip records without ground-truth score

        ref = dp.get("reference_response", "")
        if not ref:
            continue

        student_resp = resp.get("response", "")
        if not student_resp or resp.get("status") == "failed":
            continue

        task_id = resp.get("task_id") or dp.get("task_id", "unknown")
        if task_id not in by_task:
            by_task[task_id] = []

        by_task[task_id].append({
            "task_id": task_id,
            "datapoint_id": dp_id,
            "student_model_id": resp.get("student_model_id", ""),
            "prompt": resp.get("input", dp.get("prompt", "")),
            "student_response": student_resp,
            "reference_response": ref,
            "benchmark_native_score": float(bns),
        })

    # Sub-sample if requested
    if max_pairs:
        import random
        rng = random.Random(42)
        by_task = {
            t: rng.sample(items, min(max_pairs, len(items)))
            for t, items in by_task.items()
        }

    return by_task


# ---------------------------------------------------------------------------
# BERTScore baseline
# ---------------------------------------------------------------------------

def compute_bertscore_baseline(
    pairs: list[dict[str, Any]],
    model_type: str = "distilbert-base-uncased",
    batch_size: int = 32,
) -> tuple[float, float, int]:
    """Return (spearman_rho, p_value, n_pairs) for BERTScore vs benchmark_native_score."""
    spearmanr = _require_scipy()
    bs_score = _require_bertscore()

    if len(pairs) < 2:
        return (float("nan"), float("nan"), len(pairs))

    hyps = [p["student_response"] for p in pairs]
    refs = [p["reference_response"] for p in pairs]
    gt_scores = [p["benchmark_native_score"] for p in pairs]

    print(
        f"      BERTScore: scoring {len(hyps)} pairs "
        f"with {model_type} ...",
        end=" ",
        flush=True,
    )
    try:
        _P, _R, F1 = bs_score(
            hyps, refs,
            model_type=model_type,
            batch_size=batch_size,
            verbose=False,
            lang="en",
        )
        bs_scores = F1.tolist()
    except Exception as exc:
        print(f"FAILED ({exc})", file=sys.stderr)
        return (float("nan"), float("nan"), len(pairs))

    rho, pval = spearmanr(bs_scores, gt_scores)
    print(f"ρ = {rho:.3f}")
    return (float(rho), float(pval), len(pairs))


# ---------------------------------------------------------------------------
# G-Eval baseline (single LLM-as-judge)
# ---------------------------------------------------------------------------

_TASK_DESCRIPTIONS: dict[str, str] = {
    "text_summarization": "Summarise the given passage of text accurately and concisely.",
    "code_explanation": "Explain the given code snippet clearly for the specified audience.",
    "email_composition": "Write a professional email matching the specified purpose and tone.",
    "data_interpretation": "Interpret the described dataset or visualisation for the audience.",
}


def _parse_score(text: str) -> float | None:
    """Extract a 1-5 integer from LLM reply and normalize to [0, 1]."""
    text = text.strip()
    for tok in text.split():
        tok = tok.strip(".,;:()")
        try:
            v = int(tok)
            if 1 <= v <= 5:
                return (v - 1) / 4.0
        except ValueError:
            continue
    # fallback: try the whole string
    try:
        v = int(text)
        if 1 <= v <= 5:
            return (v - 1) / 4.0
    except ValueError:
        pass
    return None


def compute_geval_baseline(
    pairs: list[dict[str, Any]],
    provider: str,
    model_id: str,
    api_key: str | None,
) -> tuple[float, float, int]:
    """Return (spearman_rho, p_value, n_pairs) for G-Eval vs benchmark_native_score."""
    spearmanr = _require_scipy()

    if len(pairs) < 2:
        return (float("nan"), float("nan"), len(pairs))

    # Lazy import of provider SDK
    if provider == "openai":
        try:
            import openai
        except ImportError:
            print("ERROR: openai not installed.  pip install openai", file=sys.stderr)
            return (float("nan"), float("nan"), 0)
        client = openai.OpenAI(api_key=api_key or os.environ.get("OPENAI_API_KEY"))
        def _call(prompt_text: str, task_id: str, resp_text: str) -> str:
            user_msg = _GEVAL_USER.format(
                task_description=_TASK_DESCRIPTIONS.get(task_id, task_id),
                prompt=prompt_text,
                response=resp_text,
            )
            completion = client.chat.completions.create(
                model=model_id,
                messages=[
                    {"role": "system", "content": _GEVAL_SYSTEM},
                    {"role": "user", "content": user_msg},
                ],
                max_tokens=8,
                temperature=0.0,
            )
            return completion.choices[0].message.content or ""

    elif provider == "anthropic":
        try:
            import anthropic
        except ImportError:
            print("ERROR: anthropic not installed.  pip install anthropic", file=sys.stderr)
            return (float("nan"), float("nan"), 0)
        client = anthropic.Anthropic(api_key=api_key or os.environ.get("ANTHROPIC_API_KEY"))
        def _call(prompt_text: str, task_id: str, resp_text: str) -> str:
            user_msg = _GEVAL_USER.format(
                task_description=_TASK_DESCRIPTIONS.get(task_id, task_id),
                prompt=prompt_text,
                response=resp_text,
            )
            msg = client.messages.create(
                model=model_id,
                max_tokens=8,
                system=_GEVAL_SYSTEM,
                messages=[{"role": "user", "content": user_msg}],
            )
            return msg.content[0].text if msg.content else ""
    else:
        print(f"ERROR: unsupported G-Eval provider '{provider}'", file=sys.stderr)
        return (float("nan"), float("nan"), 0)

    geval_scores: list[float] = []
    gt_scores: list[float] = []
    n_failed = 0

    print(
        f"      G-Eval ({model_id}): scoring {len(pairs)} pairs ...",
        end=" ",
        flush=True,
    )

    for p in pairs:
        try:
            raw = _call(p["prompt"], p["task_id"], p["student_response"])
            score = _parse_score(raw)
        except Exception as exc:
            score = None
            n_failed += 1
            if n_failed <= 3:
                print(f"\n        WARN: G-Eval call failed: {exc}", file=sys.stderr)

        if score is not None:
            geval_scores.append(score)
            gt_scores.append(p["benchmark_native_score"])

    n_scored = len(geval_scores)
    print(f"scored {n_scored}/{len(pairs)}", end=" ")

    if n_scored < 2:
        print(f"(too few for ρ)")
        return (float("nan"), float("nan"), n_scored)

    rho, pval = spearmanr(geval_scores, gt_scores)
    print(f"ρ = {rho:.3f}")
    return (float(rho), float(pval), n_scored)


# ---------------------------------------------------------------------------
# Key resolution
# ---------------------------------------------------------------------------

def _resolve_api_key(provider: str, run_path: Path) -> str | None:
    """Try keys.yaml in the project root (3 dirs above benchmark/), then env vars."""
    # Walk up to find keys.yaml
    candidate_dirs = [run_path]
    d = run_path
    for _ in range(6):
        d = d.parent
        candidate_dirs.append(d)
        keys_path = d / "keys.yaml"
        if keys_path.exists():
            try:
                import yaml
                with open(keys_path, encoding="utf-8") as fh:
                    kf = yaml.safe_load(fh) or {}
                providers = kf.get("providers", {})
                val = providers.get(provider)
                if isinstance(val, str):
                    return val
                if isinstance(val, dict):
                    return val.get("api_key")
            except Exception:
                pass

    env_map = {"openai": "OPENAI_API_KEY", "anthropic": "ANTHROPIC_API_KEY"}
    return os.environ.get(env_map.get(provider, ""), None)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

_ALL_METHODS = ["bertscore", "geval-gpt4o", "geval-claude"]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Compute baseline evaluation scores for paper comparison (Table 3)."
    )
    parser.add_argument(
        "--run", required=True,
        help="Path to EES experiment folder (e.g. benchmark/runs/paper-eval-v1)",
    )
    parser.add_argument(
        "--out", default="paper/tables",
        help="Output directory for baselines.csv (default: paper/tables)",
    )
    parser.add_argument(
        "--methods", nargs="+", choices=_ALL_METHODS, default=_ALL_METHODS,
        help=f"Baseline methods to run (default: all — {_ALL_METHODS})",
    )
    parser.add_argument(
        "--bertscore-model", default="distilbert-base-uncased",
        help="BERTScore backbone (default: distilbert-base-uncased)",
    )
    parser.add_argument(
        "--bertscore-batch-size", type=int, default=32,
        help="BERTScore batch size (default: 32)",
    )
    parser.add_argument(
        "--geval-gpt4o-model", default="gpt-4o",
        help="OpenAI model for G-Eval baseline (default: gpt-4o)",
    )
    parser.add_argument(
        "--geval-claude-model", default="claude-3-5-sonnet-20241022",
        help="Anthropic model for G-Eval baseline (default: claude-3-5-sonnet-20241022)",
    )
    parser.add_argument(
        "--max-pairs", type=int, default=None,
        help="Maximum pairs per task (subsample for cost control; default: all)",
    )
    parser.add_argument(
        "--tasks", nargs="+",
        help="Limit to these task IDs (default: all found)",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Print what would be done without making API calls",
    )
    args = parser.parse_args(argv)

    run_path = Path(args.run).resolve()
    out_path = Path(args.out)
    out_path.mkdir(parents=True, exist_ok=True)
    csv_out = out_path / "baselines.csv"

    p3_dir = run_path / "phase3_datapoints"
    p4_dir = run_path / "phase4_responses"

    for label, d in [("phase3_datapoints", p3_dir), ("phase4_responses", p4_dir)]:
        if not d.exists():
            print(f"ERROR: {label}/ not found in {run_path}", file=sys.stderr)
            return 1

    print(f"[baselines] Run path    : {run_path}")
    print(f"[baselines] Output      : {csv_out}")
    print(f"[baselines] Methods     : {args.methods}")

    # ---- Load data ----------------------------------------------------------
    print("\n[baselines] Loading Phase 3 datapoints ...")
    phase3 = _load_phase3(p3_dir)
    print(f"  {len(phase3)} datapoints loaded")

    print("[baselines] Loading Phase 4 responses ...")
    phase4 = _load_phase4(p4_dir)
    print(f"  {len(phase4)} response records loaded")

    print("[baselines] Joining pairs (requires benchmark_native_score) ...")
    by_task = _build_pairs(phase3, phase4, max_pairs=args.max_pairs)

    if args.tasks:
        by_task = {t: v for t, v in by_task.items() if t in args.tasks}

    if not by_task:
        print(
            "WARNING: No valid (response, reference, benchmark_native_score) triples found.\n"
            "  Check that compute_scores.py has been run first.",
            file=sys.stderr,
        )
        return 1

    for task_id, pairs in sorted(by_task.items()):
        print(f"  task '{task_id}': {len(pairs)} pairs")

    if args.dry_run:
        print("\n[baselines] DRY RUN — no API calls made.")
        return 0

    # ---- Compute baselines --------------------------------------------------
    rows: list[dict[str, Any]] = []

    for task_id, pairs in sorted(by_task.items()):
        print(f"\n[baselines] Task: {task_id}  ({len(pairs)} pairs)")

        if "bertscore" in args.methods:
            rho, pval, n = compute_bertscore_baseline(
                pairs,
                model_type=args.bertscore_model,
                batch_size=args.bertscore_batch_size,
            )
            rows.append({
                "task_id": task_id,
                "method": "BERTScore",
                "model": args.bertscore_model,
                "n_pairs": n,
                "spearman_rho": f"{rho:.4f}" if rho == rho else "nan",
                "p_value": f"{pval:.4f}" if pval == pval else "nan",
                "coverage": f"{n / len(pairs):.3f}",
            })

        if "geval-gpt4o" in args.methods:
            api_key = _resolve_api_key("openai", run_path)
            rho, pval, n = compute_geval_baseline(
                pairs,
                provider="openai",
                model_id=args.geval_gpt4o_model,
                api_key=api_key,
            )
            rows.append({
                "task_id": task_id,
                "method": "G-Eval",
                "model": args.geval_gpt4o_model,
                "n_pairs": n,
                "spearman_rho": f"{rho:.4f}" if rho == rho else "nan",
                "p_value": f"{pval:.4f}" if pval == pval else "nan",
                "coverage": f"{n / len(pairs):.3f}",
            })

        if "geval-claude" in args.methods:
            api_key = _resolve_api_key("anthropic", run_path)
            rho, pval, n = compute_geval_baseline(
                pairs,
                provider="anthropic",
                model_id=args.geval_claude_model,
                api_key=api_key,
            )
            rows.append({
                "task_id": task_id,
                "method": "G-Eval",
                "model": args.geval_claude_model,
                "n_pairs": n,
                "spearman_rho": f"{rho:.4f}" if rho == rho else "nan",
                "p_value": f"{pval:.4f}" if pval == pval else "nan",
                "coverage": f"{n / len(pairs):.3f}",
            })

    # ---- Write CSV ----------------------------------------------------------
    if not rows:
        print("\n[baselines] No results to write.", file=sys.stderr)
        return 1

    fieldnames = ["task_id", "method", "model", "n_pairs",
                  "spearman_rho", "p_value", "coverage"]
    with open(csv_out, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    # ---- Pretty-print summary -----------------------------------------------
    print(f"\n{'=' * 70}")
    print(f"  Baseline Results (Spearman ρ vs benchmark_native_score)")
    print(f"{'=' * 70}")
    header = f"  {'Task':<30}  {'Method':<12}  {'Model':<35}  {'ρ':>6}  {'n':>5}"
    print(header)
    print("  " + "-" * (len(header) - 2))
    for row in rows:
        print(
            f"  {row['task_id']:<30}  {row['method']:<12}  {row['model']:<35}  "
            f"{row['spearman_rho']:>6}  {row['n_pairs']:>5}"
        )
    print(f"{'=' * 70}")
    print(f"\nWritten: {csv_out}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
