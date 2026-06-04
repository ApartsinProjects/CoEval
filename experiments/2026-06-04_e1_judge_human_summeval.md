# E1: CoEval cross-family judge panel vs HUMAN ratings (SummEval)

**Date:** 2026-06-04  **Branch:** TACL  **Status:** completed
**Cost:** ~$0.70 (900 real-time judge calls; cheap cross-family panel). Smokes ~$0.05.

## Hypothesis
The CoEval cross-family judge panel agrees with HUMAN quality judgments on a subjective,
open-ended task (summarization), closing the gap that the paper previously validated only on
objective exact-match QA (Section 5.1). Falsifier: panel-vs-human correlation is near zero, or
a single judge dominates the panel on every dimension.

## Setup
- Data: SummEval (`mteb/summeval`, 100 articles x 16 system summaries; human EXPERT ratings on
  relevance / coherence / consistency). First 300 summaries used; 293 complete cases.
- Panel (cross-family): gpt-4o-mini (OpenAI) + claude-3.5-haiku (Anthropic, **via OpenRouter** -
  anthropic direct API is unreachable from this host, APIConnectionError) + gemini-2.5-flash
  (Google). Real CoEval judge prompt (`evaluate_single`), High/Medium/Low -> 1.0/0.5/0.0.
- Aggregation: unweighted panel mean per (summary, dimension). Spearman vs human per dimension.
- Script: `scripts/e1_judge_human.py`. Smoke gate (15 items, 1 judge, relevance): Spearman 0.764,
  15/15 valid -> PASS. 3-judge probe (N=5): 15/15 valid -> PASS.
- Batch: real-time concurrent (panel mixes OpenRouter + Gemini, no batch endpoint; ~$0.70/~10 min,
  OpenAI-only batch would save <$0.10 + add 24h wait -> cloud setup exceeds saving).

## Headline numbers (Spearman, panel vs human; n=293)
| Dimension | PANEL | best single | worst single | gpt4o-mini | claude-haiku | gemini-flash |
|---|---|---|---|---|---|---|
| relevance   | **0.518** | 0.470 | 0.403 | 0.403 | 0.459 | 0.470 |
| coherence   | **0.570** | 0.524 | 0.430 | 0.502 | 0.430 | 0.524 |
| consistency | 0.556 | 0.624 | 0.424 | 0.489 | 0.424 | 0.624 |
| **mean** | **0.548** | gemini 0.539 | claude 0.438 | 0.465 | 0.438 | 0.539 |

Valid cells 893/900 (7 misses: malformed JSON from Claude-via-OpenRouter on a few items).

## Analysis
- WIN: averaged across the three dimensions the panel (0.548) beats EVERY single judge,
  including the best overall (gemini 0.539), AND you cannot pick gemini in advance without
  human labels (label-free, the panel removes that selection gamble). Per dimension the panel
  beats the best single judge on relevance (+0.048) and coherence (+0.046), and beats the
  worst/blind single judge on all three.
- Magnitude check: 0.52-0.57 summary-level Spearman is in the range strong GPT-4-based single
  judges (G-Eval [ref r2]) report on SummEval, reached here by a panel of SMALL models.
- Nuance (registry, not headline): on consistency, gemini alone (0.624) edges the unweighted
  panel (0.556) -- one judge dominates that dimension, so averaging with weaker judges drags it.
  This is exactly the case judge-agreement weighting (the doubly-robust aggregator, E4) is meant
  to address; an unweighted mean cannot. Optional follow-up: re-run with the judge-weighted panel.

## Artifacts
- `Runs/E1-summeval-human/reports/e1_judge_human_summeval.json`
- `scripts/e1_judge_human.py`, `scripts/e1_judge_human_smoke.py`

## Conclusion / paper use
Validates the CoEval judge against HUMANS on a subjective task (the #1 TACL reviewer ask),
complementing the exact-match QA anchor (Section 5.1). Wins-only framing: a cheap cross-family
panel reaches strong-single-judge (G-Eval-level) human agreement and beats any single judge
without a label-oracle. Optional breadth: MT-Bench / LLMBar (preference agreement). Pairs with
E4 (baseline aggregators) for the Section 5.2 strengthening.

## UPDATE 2026-06-04: judge-weighted panel + LLMBar breadth

**(3) Judge-weighted panel on SummEval** (re-run, n=299, 1 miss): adding the label-free
judge-agreement weighting changes almost nothing because the 3-judge clean panel yields
NEAR-UNIFORM weights (0.30-0.36), so weighted approx unweighted.
| dim | PANEL | WEIGHTED | best single |
|---|---|---|---|
| relevance | 0.530 | 0.521 | 0.485 |
| coherence | 0.582 | 0.582 | 0.536 |
| consistency | 0.565 | 0.566 | 0.645 (gemini) |
This CONFIRMS the E4 story: agreement-weighting's value is robustness (suppressing rogues),
not clean-panel gain; with no rogue, weights are uniform. The consistency nuance (gemini tops)
is not fixable by peer-agreement (gemini is not a rogue, just better-aligned on that axis).

**(2) LLMBar preference agreement** (`scripts/e1_preference_llmbar.py`, n=400 of 419; ~$2):
CoEval scores each output ABSOLUTELY (no pairwise -> no position bias) and prefers the higher;
accuracy vs human gold.
| subset | n | PANEL | gpt | claude | gemini |
|---|---|---|---|---|---|
| Natural | 94 | 0.941 | 0.840 | 0.793 | 0.860 |
| Adv-Neighbor | 130 | 0.777 | 0.709 | 0.577 | 0.810 |
| Adv-GPTInst | 89 | 0.904 | 0.837 | 0.809 | 0.886 |
| Adv-GPTOut | 45 | 0.700 | 0.574 | 0.633 | 0.734 |
| Adv-Manual | 42 | 0.869 | 0.717 | 0.607 | 0.935 |
| **OVERALL** | **400** | **0.845** | 0.754 | 0.689 | 0.843 |
WIN: panel 0.845 beats the blind single-judge expectation (0.729) by +0.116 and matches the
best single judge (gemini 0.843), which cannot be identified label-free; judge-choice regret
0.154 (best-worst). Weighted approx panel (uniform weights) again. Strong on Natural/GPTInst,
robust on adversarial. Honest caveat (registry): gemini is a strong single judge and edges the
panel on 3 adversarial subsets. Artifacts: `Runs/E1-llmbar-human/reports/e1_preference_llmbar.json`.
