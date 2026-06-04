"""E1 SMOKE: does the CoEval judge agree with HUMAN ratings on SummEval?

Tiny end-to-end gate before scaling: one cheap judge (gpt-4o-mini), ~15 machine
summaries drawn from SummEval, scored on the construct-matched factor 'relevance'
via the REAL CoEval judge prompt (evaluate_per_factor), correlated against the
human expert relevance scores. Success = positive Spearman + all verdicts valid.

Run:  python scripts/e1_judge_human_smoke.py
Cost: ~15 cheap-tier calls (~$0.005).
"""
from __future__ import annotations
import re
import sys
from pathlib import Path

import numpy as np
from scipy.stats import spearmanr

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "Code"))
from runner.interfaces.registry import resolve_provider_keys  # noqa: E402
from runner.interfaces.pool import ModelPool  # noqa: E402
from runner.config import ModelConfig  # noqa: E402
from runner.prompts import get_prompt  # noqa: E402

import datasets

N_SUMMARIES = 15
FACTOR = "relevance"
FACTOR_DESC = "the summary captures the important information from the source article"


def verdict_to_num(text: str):
    m = re.search(r"\b(High|Medium|Low)\b", text or "", re.IGNORECASE)
    if not m:
        return None
    return {"high": 1.0, "medium": 0.5, "low": 0.0}[m.group(1).lower()]


def main():
    ds = datasets.load_dataset("mteb/summeval", split="test")
    # Build (article, human_ref, machine_summary, human_relevance) tuples.
    # Take summaries from the first few articles to get quality spread.
    rows = []
    for art in ds:
        text = art["text"]
        ref = (art["human_summaries"] or [""])[0]
        for summ, rel in zip(art["machine_summaries"], art[FACTOR]):
            rows.append((text, ref, summ, float(rel)))
        if len(rows) >= N_SUMMARIES:
            break
    rows = rows[:N_SUMMARIES]
    print(f"smoke items: {len(rows)} | human {FACTOR} range "
          f"[{min(r[3] for r in rows):.2f}, {max(r[3] for r in rows):.2f}]")

    pk = resolve_provider_keys(str(ROOT / "keys.yaml"))
    pool = ModelPool(pk)
    judge = ModelConfig(name="judge-gpt4o-mini", interface="openai",
                        parameters={"model": "gpt-4o-mini"}, roles=["judge"])
    iface = pool.get(judge)
    params = {"model": "gpt-4o-mini", "temperature": 0.0, "max_tokens": 8}

    judge_scores, human_scores, invalid = [], [], 0
    for i, (text, ref, summ, human_rel) in enumerate(rows):
        prompt = get_prompt(
            "evaluate_per_factor", {}, "gpt-4o-mini",
            {
                "task_description": "summarize the news article into a short abstract",
                "output_description": "a concise summary of the article",
                "input": text[:2500],
                "target_attributes": "{}",
                "reference_response": ref[:800],
                "response": summ,
                "rubric_factor_name": FACTOR,
                "rubric_factor_description": FACTOR_DESC,
            },
        )
        out = iface.generate(prompt, params)
        num = verdict_to_num(out)
        if num is None:
            invalid += 1
            print(f"  [{i}] INVALID verdict: {out!r}")
            continue
        judge_scores.append(num)
        human_scores.append(human_rel)
        print(f"  [{i}] judge={num:.1f}  human={human_rel:.2f}  raw={out.strip()!r}")

    rho = spearmanr(judge_scores, human_scores).correlation if len(judge_scores) > 3 else float("nan")
    print(f"\nvalid verdicts: {len(judge_scores)}/{len(rows)} (invalid {invalid})")
    print(f"judge-vs-human Spearman ({FACTOR}): {rho:.3f}")
    print(f"SMOKE {'PASS' if (rho == rho and rho > 0 and invalid == 0) else 'CHECK'}: "
          f"{'positive correlation, all verdicts valid' if (rho==rho and rho>0 and invalid==0) else 'inspect above'}")


if __name__ == "__main__":
    main()
