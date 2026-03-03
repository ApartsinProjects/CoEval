# Experiment Backlog

*Track additional experiments needed for camera-ready paper.*
*Goal: minimize total number of additional experiments (ideally 1 combined experiment).*

---

## Priority 1 — Critical for Core Claims

### EXP-001: Benchmark-Grounded Comparison Experiment
**Status:** Planned
**Priority:** P1 — Critical
**Motivation:** All comparative claims (CoEval vs BERTScore, G-Eval, FLAMe, etc.) are currently simulated. Need real ρ values vs ground-truth benchmarks to validate R1.

**Design:**
- Use `benchmark-sourced` mode in CoEval
- Tasks: text_summarization (XSum), code_explanation (HumanEval), email_composition (AESLC), data_interpretation (ChartQA)
- Ground-truth metrics: BERTScore-F1, pass@1, ROUGE-L, exact-match accuracy
- Baselines to compare: BERTScore, G-Eval (GPT-4o), ROUGE-L, human annotation (sampled)
- Scale: ~200 items per task (800 total) — sufficient for Spearman ρ
- Judges: GPT-4o-mini + GPT-3.5-turbo ensemble (3-judge)
- Expected output: Table 8 (benchmark comparison ρ vs baselines)

**Effort estimate:** ~4 hours compute, ~$25 API cost
**Blocking:** Table 8, Fig 8, Claims R1, R2 vs external baselines
**Notes:** This is the most important experiment. All other claims can use medium-benchmark-v1 data.

---

## Priority 2 — Important for Completeness

### EXP-002: Ensemble Size Ablation
**Status:** Partially simulated (Fig 8 in paper uses simulated data)
**Priority:** P2
**Motivation:** Validate that larger judge ensembles improve reliability (monotonic ρ increase: 1J → 2J → 3J).

**Design:**
- Use existing medium-benchmark-v1 evaluations
- Compute ensemble scores using 1, 2, 3, 4 judge subsets
- Report Spearman ρ between ensemble and single best judge as function of k
- No new API calls needed — can be computed from existing phase5 evaluations

**Effort estimate:** Analyzer patch (2 hours coding), no new API calls
**Blocking:** Fig 8 (ensemble ablation)
**Notes:** Can be done without new experiments by sub-sampling existing judge assignments.

### EXP-003: Positional Bias Measurement
**Status:** Not yet done
**Priority:** P2
**Motivation:** Validate that ensemble averaging reduces positional bias present in individual judges.

**Design:**
- Generate paired versions of ~50 prompts with same content but A/B position swapped
- Measure Positional Flip Rate (PFR) for individual judges vs ensemble
- Expected: individual PFR ~20-27%, ensemble PFR ~5% (consistent with literature)

**Effort estimate:** ~2 hours compute, ~$5 API cost
**Notes:** Can be done with a small-scale targeted experiment.

---

## Priority 3 — Nice to Have

### EXP-004: Verbosity Bias Analysis
**Status:** Not yet done
**Priority:** P3
**Motivation:** Show that ensemble calibration reduces verbosity bias (length ↔ score correlation).

**Design:**
- Compute Pearson r(response_length, score_norm) per judge vs ensemble
- Use existing medium-benchmark-v1 phase4 responses + phase5 evaluations
- No new API calls needed

**Effort estimate:** Analyzer patch (1 hour coding)
**Notes:** Low hanging fruit — computable from existing data.

### EXP-005: Cross-Task Rubric Generalization
**Status:** Not applicable for medium benchmark
**Priority:** P3
**Motivation:** Show that rubric criteria generalize meaningfully across task types.

**Design:**
- Compare rubric criteria overlap between tasks using semantic similarity
- Highlight shared criteria (accuracy, completeness, clarity) vs task-specific ones

**Effort estimate:** 30 min analysis
**Notes:** Purely analytical, no new experiments needed.

---

## Consolidated Experiment Plan

**Recommended single experiment to run before camera-ready:**

→ **EXP-001** (Benchmark-Grounded Comparison) is the highest-priority and only one that requires new API calls. Run this as a single comprehensive experiment with all 4 tasks + all baselines simultaneously.

EXP-002, 004, 005 can be done by patching the analyzer to compute metrics from existing data.

EXP-003 can be added to the same run as EXP-001 with minimal overhead.

**Combined experiment script:** See `scripts/benchmark_comparison_experiment.py` (to be created)

---

## Simulated Figures/Tables Index

The following items use simulated data and must be updated with real experimental results before camera-ready submission:

| Item | Section | Simulated values | Real experiment needed |
|------|---------|-----------------|----------------------|
| Table 8 (benchmark comparison) | §4 | ρ=0.871 vs BERTScore ρ=0.472 | EXP-001 |
| Fig 8 (ensemble ablation) | §5 | 1J=0.760, 2J=0.821, 3J=0.871 | EXP-002 |
| Table 9 (PFR bias) | §5 | 23.4%→2.9% | EXP-003 |
| Table 10 (verbosity bias) | §5 | Pearson r values | EXP-004 |
| All ρ vs baseline comparisons | §4 | All simulated | EXP-001 |
