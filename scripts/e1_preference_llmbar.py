"""E1 (breadth): CoEval panel vs HUMAN preference on LLMBar.

LLMBar is the purpose-built meta-benchmark for LLM evaluators: each instance has an
instruction and two outputs, with a HUMAN gold label for which output better follows it.
CoEval scores each output ABSOLUTELY with the cross-family panel (no pairwise comparison,
so no position bias) and prefers the higher-scored output; we report preference accuracy
vs the human gold, per subset, for the panel / judge-weighted panel / each single judge.

Usage:  python scripts/e1_preference_llmbar.py [MAX_PER_SUBSET]
"""
from __future__ import annotations
import json
import re
import sys
import urllib.request
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

MAX = int(sys.argv[1]) if len(sys.argv) > 1 else 1000
SUBSETS = {
    "Natural": "Dataset/LLMBar/Natural/dataset.json",
    "Adv-Neighbor": "Dataset/LLMBar/Adversarial/Neighbor/dataset.json",
    "Adv-GPTInst": "Dataset/LLMBar/Adversarial/GPTInst/dataset.json",
    "Adv-GPTOut": "Dataset/LLMBar/Adversarial/GPTOut/dataset.json",
    "Adv-Manual": "Dataset/LLMBar/Adversarial/Manual/dataset.json",
}
RAW = "https://raw.githubusercontent.com/princeton-nlp/LLMBar/main/"
RUBRIC = ("instruction_following: the response correctly and completely follows the instruction\n"
          "quality: the response is helpful, relevant, and high quality")
JUDGES = [
    ModelConfig(name="judge-gpt4o-mini", interface="openai",
                parameters={"model": "gpt-4o-mini"}, roles=["judge"]),
    ModelConfig(name="judge-claude-haiku", interface="openrouter",
                parameters={"model": "anthropic/claude-3.5-haiku"}, roles=["judge"]),
    ModelConfig(name="judge-gemini-flash", interface="gemini",
                parameters={"model": "gemini-2.5-flash"}, roles=["judge"]),
]
NUM = {"high": 1.0, "medium": 0.5, "low": 0.0}
FACTORS = ["instruction_following", "quality"]


def parse_json(text):
    m = re.search(r"\{.*\}", text or "", re.DOTALL)
    if not m:
        return {}
    try:
        return json.loads(m.group(0))
    except Exception:
        return {}


def main():
    pk = resolve_provider_keys(str(ROOT / "keys.yaml"))
    pool = ModelPool(pk)

    # load subsets
    data = {}
    for name, path in SUBSETS.items():
        try:
            arr = json.load(urllib.request.urlopen(RAW + path, timeout=30))
            data[name] = arr[:MAX]
            print(f"{name}: {len(data[name])} instances")
        except Exception as e:
            print(f"{name}: FETCH FAIL {str(e)[:80]}")

    # tasks: (subset, idx, side, judge)
    tasks = []
    for name, arr in data.items():
        for idx, inst in enumerate(arr):
            for side in (1, 2):
                for j in JUDGES:
                    tasks.append((name, idx, side, j))

    def score(args):
        name, idx, side, jcfg = args
        inst = data[name][idx]
        prompt = get_prompt("evaluate_single", {}, jcfg.parameters["model"], {
            "task_description": "follow the user instruction",
            "output_description": "a response that follows the instruction",
            "input": str(inst["input"])[:2500], "target_attributes": "{}",
            "reference_response": "", "response": str(inst[f"output_{side}"])[:1500],
            "rubric": RUBRIC,
        })
        params = {"model": jcfg.parameters["model"], "temperature": 0.0, "max_tokens": 1024}
        try:
            obj = parse_json(pool.get(jcfg).generate(prompt, params))
        except Exception:
            return (name, idx, side, jcfg.name, None)
        vals = [NUM[str(obj.get(f, "")).strip().lower()] for f in FACTORS
                if str(obj.get(f, "")).strip().lower() in NUM]
        return (name, idx, side, jcfg.name, float(np.mean(vals)) if vals else None)

    cells = {}
    with ThreadPoolExecutor(max_workers=12) as ex:
        for name, idx, side, jn, sc in ex.map(score, tasks):
            cells[(name, idx, side, jn)] = sc

    jnames = [j.name for j in JUDGES]
    # judge-agreement weights (label-free): peer Spearman over all (instance,side) scores
    vecs = {jn: [] for jn in jnames}
    keyset = [(name, idx, side) for name, arr in data.items()
              for idx in range(len(arr)) for side in (1, 2)]
    for k in keyset:
        for jn in jnames:
            vecs[jn].append(cells.get((k[0], k[1], k[2], jn)))
    jw = {}
    for jn in jnames:
        ags = []
        for o in jnames:
            if o == jn:
                continue
            a = np.array([x if x is not None else np.nan for x in vecs[jn]], float)
            b = np.array([x if x is not None else np.nan for x in vecs[o]], float)
            ok = ~np.isnan(a) & ~np.isnan(b)
            if ok.sum() > 3 and np.std(a[ok]) > 0 and np.std(b[ok]) > 0:
                ags.append(spearmanr(a[ok], b[ok]).correlation)
        jw[jn] = max(0.0, float(np.mean(ags))) if ags else 0.0
    tot = sum(jw.values()) or 1.0
    jw = {jn: jw[jn] / tot for jn in jnames}

    def acc(name, scorer):
        # scorer(idx) -> (score1, score2) or None; gold label compare
        hits = tot_n = 0
        for idx, inst in enumerate(data[name]):
            sc = scorer(idx)
            if sc is None:
                continue
            s1, s2 = sc
            gold = int(inst["label"])
            pred = 1 if s1 > s2 else (2 if s2 > s1 else 0)
            tot_n += 1
            hits += 1.0 if pred == gold else (0.5 if pred == 0 else 0.0)
        return round(hits / tot_n, 3) if tot_n else None, tot_n

    def panel_scorer(name, weighted):
        def f(idx):
            out = []
            for side in (1, 2):
                vals = [(jw[jn] if weighted else 1.0, cells.get((name, idx, side, jn)))
                        for jn in jnames]
                vals = [(w, v) for w, v in vals if v is not None]
                if len(vals) < len(jnames):
                    return None
                out.append(sum(w * v for w, v in vals) / (sum(w for w, _ in vals) or 1.0))
            return tuple(out)
        return f

    def single_scorer(name, jn):
        def f(idx):
            a = cells.get((name, idx, 1, jn)); b = cells.get((name, idx, 2, jn))
            return None if a is None or b is None else (a, b)
        return f

    report = {"experiment": "e1_preference_llmbar", "dataset": "princeton-nlp/LLMBar",
              "judges": jnames, "judge_weights": {k: round(v, 3) for k, v in jw.items()},
              "rubric_factors": FACTORS, "per_subset": {}, "overall": {}}
    print("\nsubset        n   PANEL  WEIGHTED  " + "  ".join(j.split('-', 1)[1][:6] for j in jnames))
    agg = {"panel": [0, 0], "weighted": [0, 0], **{jn: [0, 0] for jn in jnames}}
    for name in data:
        row = {}
        pa, n = acc(name, panel_scorer(name, False)); row["panel"] = pa
        wa, _ = acc(name, panel_scorer(name, True)); row["weighted"] = wa
        sj = {}
        for jn in jnames:
            sa, _ = acc(name, single_scorer(name, jn)); sj[jn] = sa
        row["per_judge"] = sj
        row["n"] = n
        report["per_subset"][name] = row
        # weighted overall accumulation (by n)
        for key, val in [("panel", pa), ("weighted", wa)] + [(jn, sj[jn]) for jn in jnames]:
            if val is not None:
                agg[key][0] += val * n; agg[key][1] += n
        print(f"{name:13s} {n:3d}  {pa:.3f}  {wa:.3f}    " +
              "  ".join(f"{sj[jn]:.3f}" for jn in jnames))
    for key in agg:
        report["overall"][key] = round(agg[key][0] / agg[key][1], 3) if agg[key][1] else None
    ov = report["overall"]
    print(f"{'OVERALL':13s} {agg['panel'][1]:3d}  {ov['panel']:.3f}  {ov['weighted']:.3f}    " +
          "  ".join(f"{ov[jn]:.3f}" for jn in jnames))

    out = ROOT / "Runs" / "E1-llmbar-human" / "reports" / "e1_preference_llmbar.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    (out.parent / "e1_llmbar_raw_cells.json").write_text(
        json.dumps({f"{k[0]}|{k[1]}|{k[2]}|{k[3]}": v for k, v in cells.items()}))
    out.write_text(json.dumps(report, indent=2))
    print(f"\nsaved {out.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
