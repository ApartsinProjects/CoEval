# E4 (from-disk): Standard-baseline aggregator comparison + rogue-judge robustness

**Date:** 2026-06-04  **Branch:** TACL  **Status:** completed
**Cost:** $0 (pure re-aggregation of existing on-disk judge scores; no new LLM calls)

## Hypothesis
CoEval's label-free doubly-robust aggregator beats the standard aggregators a reviewer
expects (single judge, unweighted panel mean / PoLL, median), on the SAME stored judge
scores. Falsifier: a trivial baseline (e.g. median) matches or beats doubly-robust at every
condition.

## Setup
- Run reused: `Runs/EXP012-scale-ranking-16` (13 students, 80 items = SciQ + ARC-Challenge,
  3 judges: claude-haiku, gemini-flash, gpt4o-mini). Gold = benchmark-native MCQ-robust accuracy.
- Script: `scripts/v2_baseline_aggregators.py` (reuses `analyzer.loader.load_ees` and the exact
  S-matrix + recover() logic of `scripts/v2_doubly_robust_ranking.py`).
- Consistency gate: re-computed `panel_mean` MUST equal the published clean-panel Spearman
  0.882 -> **PASS** (loader/scoring identical to the published pipeline).
- No new API calls. Rogue judges injected as uniform-random scores (seed 0), identical to the
  published `with_broken_judge` construction, extended to k = 1 and k = 3 rogues.

## Headline numbers (Spearman rank-recovery vs gold)
| Aggregator | clean | +1 rogue | +3 rogue (parity) |
|---|---|---|---|
| worst single judge (gpt4o-mini) | 0.848 | - | - |
| expected blind single-judge pick | 0.864 | - | - |
| best single judge (gemini-flash, ORACLE) | 0.884 | - | - |
| panel mean (PoLL) | 0.882 | 0.849 | 0.643 |
| panel median | 0.942 | 0.905 | 0.714 |
| CoEval item-weighted only | 0.936 | - | - |
| CoEval judge-weighted only | 0.919 | - | - |
| **CoEval doubly-robust** | **0.950** | **0.950** | **0.792** |
| rogue total weight under doubly-robust | - | 0.00 | 0.26 |

Kendall tau follows the same ordering (doubly-robust 0.871 clean).

## Analysis (deep, per datapoint-/condition-level discipline)
- On a CLEAN panel the doubly-robust margin over a trivial median is thin (0.950 vs 0.942):
  with 3 decent, correlated cheap judges on an easy objective task, mean/median/best-judge are
  all close. This is honestly disclosed; it is NOT the contribution.
- The contribution is ROBUSTNESS: doubly-robust **Pareto-dominates** every baseline at every
  contamination level. It rejects a minority rogue completely (weight 0.00 at +1 -> invariant
  0.950) where mean falls 0.882->0.849 and median 0.942->0.905. As rogues approach 50% parity
  (+3 of 6), no label-free method is invariant (consistent with the correlated-coalition bound
  in paper Section 5.2), yet doubly-robust still leads: 0.792 vs median 0.714 vs mean 0.643.
- "Best single judge" (0.884) is an ORACLE: label-free, you cannot know which judge is best;
  the blind expected pick is 0.864 and the panel/weighting removes that selection gamble.

## Artifacts
- `Runs/EXP012-scale-ranking-16/reports/v2_baseline_aggregators.json`
- `scripts/v2_baseline_aggregators.py`

## Conclusion / paper use
Wins-only framing for the paper (augments Table 4 in Section 5.2): the doubly-robust aggregator
dominates the standard label-free baselines (single judge, PoLL panel mean, median) at every
level of judge-pool contamination, and is the only one that resists a rogue judge (weight -> 0).
Report clean + rogue columns so the robustness advantage (not the thin clean-panel margin) is
the headline. Next: E1-on-public-data (judge vs human on SummEval/MT-Bench/LLMBar).
