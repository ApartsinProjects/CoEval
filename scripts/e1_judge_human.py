"""E1: CoEval cross-family judge panel vs HUMAN ratings on SummEval.

Scores SummEval machine summaries with the real CoEval judge prompt
(evaluate_single) using a cross-family panel (gpt-4o-mini + claude-haiku +
gemini-flash) on relevance / coherence / consistency, then correlates the panel
score against human expert ratings per dimension. Reports panel vs single-judge
Spearman (the judge-choice story) and the construct-matched dimension.

Usage:  python scripts/e1_judge_human.py [N_SUMMARIES]   (default 300; small N = probe)
"""
from __future__ import annotations
import json
import re
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np
from scipy.stats import spearmanr

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "Code"))
from runner.interfaces.registry import resolve_provider_keys  # noqa: E402
from runner.interfaces.pool import ModelPool  # noqa: E402
from runner.config import ModelConfig  # noqa: E402
from runner.prompts import get_prompt  # noqa: E402
import datasets  # noqa: E402

N = int(sys.argv[1]) if len(sys.argv) > 1 else 300
DIMS = {
    "relevance": "the summary captures the important information from the source article",
    "coherence": "the summary is well-structured and well-organized",
    "consistency": "the summary is factually consistent with the source article",
}
JUDGES = [
    ModelConfig(name="judge-gpt4o-mini", interface="openai",
                parameters={"model": "gpt-4o-mini"}, roles=["judge"]),
    # Anthropic direct API is unreachable from this host (APIConnectionError);
    # route the Anthropic-family judge via OpenRouter (same Claude model, keeps panel cross-family).
    ModelConfig(name="judge-claude-haiku", interface="openrouter",
                parameters={"model": "anthropic/claude-3.5-haiku"}, roles=["judge"]),
    ModelConfig(name="judge-gemini-flash", interface="gemini",
                parameters={"model": "gemini-2.5-flash"}, roles=["judge"]),
]
NUM = {"high": 1.0, "medium": 0.5, "low": 0.0}


def parse_json(text):
    if not text:
        return {}
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if not m:
        return {}
    try:
        return json.loads(m.group(0))
    except Exception:
        return {}


def main():
    ds = datasets.load_dataset("mteb/summeval", split="test")
    rows = []  # (text, ref, summary, {dim: human_score})
    for art in ds:
        ref = (art["human_summaries"] or [""])[0]
        for k, summ in enumerate(art["machine_summaries"]):
            rows.append((art["text"], ref, summ,
                         {d: float(art[d][k]) for d in DIMS}))
            if len(rows) >= N:
                break
        if len(rows) >= N:
            break
    print(f"E1 SummEval: {len(rows)} summaries x {len(JUDGES)} judges x {len(DIMS)} dims")

    pk = resolve_provider_keys(str(ROOT / "keys.yaml"))
    pool = ModelPool(pk)
    rubric = "\n".join(f"{d}: {desc}" for d, desc in DIMS.items())

    def score_one(args):
        i, jcfg = args
        text, ref, summ, _ = rows[i]
        prompt = get_prompt("evaluate_single", {}, jcfg.parameters["model"], {
            "task_description": "summarize the news article into a short abstract",
            "output_description": "a concise summary of the article",
            "input": text[:2500], "target_attributes": "{}",
            "reference_response": ref[:800], "response": summ, "rubric": rubric,
        })
        params = {"model": jcfg.parameters["model"], "temperature": 0.0, "max_tokens": 1024}
        try:
            out = pool.get(jcfg).generate(prompt, params)
        except Exception as e:
            return (i, jcfg.name, None, f"ERR {type(e).__name__}: {str(e)[:80]}")
        obj = parse_json(out)
        scores = {}
        for d in DIMS:
            v = str(obj.get(d, "")).strip().lower()
            if v in NUM:
                scores[d] = NUM[v]
        return (i, jcfg.name, scores or None, out.strip()[:60])

    tasks = [(i, j) for i in range(len(rows)) for j in JUDGES]
    results = {}
    errs = 0
    with ThreadPoolExecutor(max_workers=8) as ex:
        for i, jname, scores, raw in ex.map(score_one, tasks):
            results[(i, jname)] = scores
            if scores is None:
                errs += 1
                if errs <= 6:
                    print(f"  MISS [{i}/{jname}]: {raw}")

    # aggregate + correlate per dimension
    jnames = [j.name for j in JUDGES]
    report = {"experiment": "e1_judge_human_summeval", "dataset": "mteb/summeval",
              "n_summaries": len(rows), "judges": jnames, "dims": list(DIMS),
              "misses": errs, "per_dim": {}}
    print(f"\nvalid (summary,judge) cells: {len([1 for v in results.values() if v])}/{len(tasks)} "
          f"(misses {errs})")
    for d in DIMS:
        human, panel, per_judge = [], [], {jn: [] for jn in jnames}
        for i in range(len(rows)):
            cell = [results.get((i, jn)) for jn in jnames]
            vals = [c[d] for c in cell if c and d in c]
            if len(vals) < len(jnames):
                continue  # complete cases only
            human.append(rows[i][3][d])
            panel.append(float(np.mean(vals)))
            for jn in jnames:
                per_judge[jn].append(results[(i, jn)][d])
        if len(panel) < 5:
            continue
        pj = {jn: round(float(spearmanr(per_judge[jn], human).correlation), 3) for jn in jnames}
        panel_rho = round(float(spearmanr(panel, human).correlation), 3)
        # label-free judge-agreement weights (mean peer Spearman), per dimension (cf. E4 / Section 5.2)
        jw = {}
        for jn in jnames:
            ags = [spearmanr(per_judge[jn], per_judge[o]).correlation for o in jnames if o != jn]
            ags = [a for a in ags if a == a]
            jw[jn] = max(0.0, float(np.mean(ags))) if ags else 0.0
        tot = sum(jw.values()) or 1.0
        jw = {jn: jw[jn] / tot for jn in jnames}
        wpanel = [sum(jw[jn] * per_judge[jn][k] for jn in jnames) for k in range(len(human))]
        wpanel_rho = round(float(spearmanr(wpanel, human).correlation), 3)
        report["per_dim"][d] = {
            "n": len(panel), "panel_spearman": panel_rho,
            "judge_weighted_panel_spearman": wpanel_rho,
            "judge_weights": {jn: round(jw[jn], 3) for jn in jnames},
            "per_judge_spearman": pj,
            "best_single": max(pj.values()), "worst_single": min(pj.values()),
        }
        print(f"  {d:12s} n={len(panel):3d}  PANEL={panel_rho:.3f}  WEIGHTED={wpanel_rho:.3f}  "
              f"best_single={max(pj.values()):.3f}  worst={min(pj.values()):.3f}")

    out = ROOT / "Runs" / "E1-summeval-human" / "reports" / "e1_judge_human_summeval.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    # save raw per-cell scores so future re-aggregation (other weightings) costs $0
    raw = {f"{i}|{jn}": results.get((i, jn)) for i in range(len(rows)) for jn in jnames}
    (out.parent / "e1_raw_cells.json").write_text(json.dumps(raw))
    out.write_text(json.dumps(report, indent=2))
    print(f"\nsaved {out.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
