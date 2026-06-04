"""E4-from-disk: standard-baseline aggregator comparison on EXISTING judge scores.

NO new LLM calls. Re-aggregates the per-(item, student, judge) scores already on
disk under each standard label-free aggregation rule and recovers the gold-accuracy
ranking, so CoEval's doubly-robust weighting is compared apples-to-apples against the
baselines a reviewer expects:

  - single judge (each), plus best / worst / expected-random single judge
    (the judge-choice-regret endpoints: what a practitioner risks by committing to one)
  - unweighted panel mean  (PoLL-style panel-of-LLMs)
  - median panel           (robust aggregation)
  - item-weighted only / judge-weighted only / doubly-robust  (CoEval)

Consistency gate: plain_mean MUST reproduce the published clean-panel number
(Spearman 0.882) or the loader/scoring has diverged from v2_doubly_robust_ranking.py.

Run:  python scripts/v2_baseline_aggregators.py [RUN_NAME]
"""
from __future__ import annotations
import json
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
from scipy.stats import spearmanr, kendalltau

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "Code"))
from analyzer.loader import load_ees  # noqa: E402

_RUN_NAME = sys.argv[1] if len(sys.argv) > 1 else "EXP012-scale-ranking-16"
RUN = ROOT / "Runs" / _RUN_NAME


def _gold_by_student_item():
    out = {}
    f = RUN / "benchmark_response_scores.jsonl"
    for line in f.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        r = json.loads(line)
        if r.get("benchmark_native_score") is not None:
            out[(r["datapoint_id"], r["student_model_id"])] = float(r["benchmark_native_score"])
    return out


def main():
    model = load_ees(RUN, partial_ok=True)
    gold_si = _gold_by_student_item()

    # CoEval score per (item, student, judge) = mean over accuracy-ish aspects
    # (identical construction to v2_doubly_robust_ranking.py).
    cell = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))
    for u in model.units:
        cell[u.datapoint_id][u.student_model_id][u.judge_model_id].append(u.score_norm)
    items = sorted(cell)
    students = sorted({s for it in cell for s in cell[it]})
    judges = sorted({j for it in cell for s in cell[it] for j in cell[it][s]})
    S = {it: {s: {j: float(np.mean(cell[it][s][j])) for j in cell[it][s]}
              for s in cell[it]} for it in items}

    gold = {s: float(np.mean([gold_si[(it, s)] for it in items if (it, s) in gold_si]))
            for s in students}

    def recover(score_by_student):
        xs = [score_by_student[s] for s in students]
        ys = [gold[s] for s in students]
        return (round(float(spearmanr(xs, ys).correlation), 3),
                round(float(kendalltau(xs, ys).correlation), 3))

    # ---- aggregation rules over the SAME stored scores ----
    def rank_mean(panel):
        # unweighted panel mean per (item,student), then mean over items
        return {s: float(np.mean([np.mean([S[it][s][j] for j in panel if j in S[it][s]])
                                  for it in items if s in S[it]])) for s in students}

    def rank_median(panel):
        # median across judges per (item,student), then mean over items
        return {s: float(np.mean([float(np.median([S[it][s][j] for j in panel if j in S[it][s]]))
                                  for it in items if s in S[it]])) for s in students}

    def rank_single(j):
        return {s: float(np.mean([S[it][s][j] for it in items if s in S[it] and j in S[it][s]]))
                for s in students}

    # single-judge recoveries (judge-choice regret)
    per_judge = {j: recover(rank_single(j)) for j in judges}
    sp = {j: per_judge[j][0] for j in judges}
    best_j = max(sp, key=sp.get)
    worst_j = min(sp, key=sp.get)

    # panel baselines
    plain = recover(rank_mean(judges))       # PoLL-style unweighted panel
    median = recover(rank_median(judges))

    res = {
        "experiment": "v2_baseline_aggregators",
        "source": "re-aggregation of existing on-disk judge scores (no new LLM calls)",
        "run": _RUN_NAME,
        "n_items": len(items), "n_students": len(students), "judges": judges,
        "metric": "Spearman/Kendall of recovered ranking vs gold accuracy",
        "single_judge": {j: per_judge[j] for j in judges},
        "single_judge_summary": {
            "best": {"judge": best_j, "recovery": per_judge[best_j]},
            "worst": {"judge": worst_j, "recovery": per_judge[worst_j]},
            "expected_random_pick_spearman": round(float(np.mean([sp[j] for j in judges])), 3),
            "judge_choice_regret_spearman": round(sp[best_j] - sp[worst_j], 3),
        },
        "panel_unweighted_mean_PoLL": plain,
        "panel_median": median,
    }

    # CoEval doubly-robust family, loaded from the committed report (same data/config).
    dr_path = RUN / "reports" / "v2_doubly_robust_ranking.json"
    dr = json.loads(dr_path.read_text()) if dr_path.exists() else None
    if dr:
        clean = dr["clean_panel"]
        res["coeval_item_weighted_only"] = clean["item_weighted_only"]
        res["coeval_judge_weighted_only"] = clean["judge_weighted_only"]
        res["coeval_doubly_robust"] = clean["doubly_robust"]
        res["_consistency_check"] = {
            "plain_mean_here": plain,
            "plain_mean_published": clean["plain_mean"],
            "match": list(plain) == clean["plain_mean"],
        }

    # ---- ROBUSTNESS: inject rogue judge(s) and re-aggregate every baseline ----
    # Identical injection to v2_doubly_robust_ranking.py (uniform random, seed 0),
    # extended to k rogue judges to stress simple aggregators (mean/median).
    def with_rogues(k):
        rng = np.random.default_rng(0)
        Sb = {it: {s: dict(S[it][s]) for s in S[it]} for it in items}
        rogues = [f"BAD:random{r}" for r in range(k)]
        for it in items:
            for s in Sb[it]:
                for rg in rogues:
                    Sb[it][s][rg] = float(rng.uniform(0, 1))
        panel = judges + rogues

        def rmean():
            return {s: float(np.mean([np.mean([Sb[it][s][j] for j in panel])
                                      for it in items if s in Sb[it]])) for s in students}

        def rmedian():
            return {s: float(np.mean([float(np.median([Sb[it][s][j] for j in panel]))
                                      for it in items if s in Sb[it]])) for s in students}

        # doubly-robust over Sb/panel (same logic as v2_doubly_robust_ranking.py)
        def judge_weights():
            vec = {j: np.array([np.mean([Sb[it][s][j] for s in students]) for it in items]) for j in panel}
            w = {}
            for j in panel:
                ags = []
                for o in panel:
                    if o == j:
                        continue
                    a, b = vec[j], vec[o]
                    ok = ~np.isnan(a) & ~np.isnan(b)
                    if ok.sum() > 3 and np.std(a[ok]) > 0 and np.std(b[ok]) > 0:
                        ags.append(spearmanr(a[ok], b[ok]).correlation)
                w[j] = max(0.0, float(np.mean(ags))) if ags else 0.0
            tot = sum(w.values()) or 1.0
            return {j: w[j] / tot for j in panel}

        jw = judge_weights()
        cs = {it: {s: (sum(jw[j] * Sb[it][s][j] for j in panel) / (sum(jw[j] for j in panel) or 1.0))
                   for s in students} for it in items}
        iw_raw = {it: float(np.var([cs[it][s] for s in students])) for it in items}
        tot = sum(iw_raw.values()) or 1.0
        iw = {it: iw_raw[it] / tot for it in items}
        dr_sc = {s: sum(iw[it] * cs[it][s] for it in items) / (sum(iw.values()) or 1.0) for s in students}
        return {"panel_mean_PoLL": recover(rmean()), "panel_median": recover(rmedian()),
                "coeval_doubly_robust": recover(dr_sc),
                "rogue_total_weight": round(sum(jw[j] for j in panel if j.startswith("BAD:")), 4)}

    res["with_1_rogue_judge"] = with_rogues(1)
    res["with_3_rogue_judges"] = with_rogues(3)
    if dr:
        # doubly-robust under 1 rogue is in the committed report (rogue weight 0.0)
        res["with_1_rogue_judge"]["coeval_doubly_robust"] = dr["with_broken_judge"]["doubly_robust"]
        res["with_1_rogue_judge"]["_rogue_weight_under_doubly_robust"] = dr["with_broken_judge"]["broken_judge_weight"]
        # best single judge is unaffected by adding judges, but is an ORACLE (needs gold to pick)
        res["with_1_rogue_judge"]["best_single_judge_ORACLE"] = per_judge[best_j]

    out = RUN / "reports" / "v2_baseline_aggregators.json"
    out.write_text(json.dumps(res, indent=2))
    print(json.dumps(res, indent=2))


if __name__ == "__main__":
    main()
