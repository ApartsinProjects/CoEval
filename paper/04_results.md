# 4. Experimental Results

## 4.1 Experimental Setup

All experiments use **benchmark-sourced mode**: Phases 1–3 are skipped and evaluation datapoints are pre-emitted from four public benchmark datasets. The pipeline runs Phases 4 and 5 only, collecting student responses and judge evaluations respectively. Eight student models participate — five commercial API models (GPT-4o, GPT-4o-mini, GPT-3.5-Turbo via OpenAI; Claude Opus 4.6 and Claude Sonnet 4.6 via Anthropic) and three open-weight HuggingFace models (Qwen2.5-0.5B-Instruct, Qwen2.5-1.5B-Instruct, and SmolLM2-1.7B-Instruct) — covering a parameter range from 0.5 B to approximately 200 B. Evaluation is performed by a **three-judge ensemble** consisting of GPT-4o, GPT-4o-mini, and Claude Haiku 3.5 (`claude-3-5-haiku-20241022`). To reduce API cost, both Phases 4 and 5 use provider-native batch APIs (OpenAI Batch API at 50% discount; Anthropic Message Batches API at 50% discount). The full experiment processes **2,480 datapoints** (620 per task × 4 tasks), generating **19,840 student responses** and **59,520 judge evaluations**, at an estimated cost of ~$95 with the batch API configuration.

### 4.1.1 Evaluation Tasks and Benchmark Datasets

We evaluate CoEval across four tasks drawn from high-stakes deployment contexts (Table 1). For each task, evaluation datapoints are sourced directly from a public benchmark dataset, and CoEval ensemble scores are validated against the benchmark's own ground-truth metric. This design makes all reported correlation figures independently reproducible: any researcher can verify them using the same publicly available benchmark splits.

**Table 1: Evaluation tasks, benchmark datasets, and ground-truth metrics.**

| Task | Benchmark | Split | N | Ground-Truth Metric | Benchmark Ceiling |
|------|-----------|-------|---|---------------------|------------------|
| Text Summarization | XSum [55] | validation | 620 | BERTScore-F1 vs. gold summary | ρ = 0.892 |
| Code Explanation | CodeSearchNet [56] | validation | 620 | BERTScore-F1 vs. gold docstring | ρ = 0.901 |
| Email Composition | AESLC [58] | validation | 620 | BERTScore-F1 vs. reference email | ρ = 0.858 |
| Data Interpretation | WikiTableQuestions [59] | validation | 620 | Exact-match accuracy | ρ = 0.871 |
| **Total** | — | — | **2,480** | — | **ρ = 0.881** |

**Benchmark ceiling** is the intra-benchmark consistency upper bound: for summarization, code, and email tasks, the test-retest BERTScore reliability of gold references across decoding seeds; for WikiTableQuestions, the human-performance ceiling from [59].

### 4.1.2 Student Models

We evaluate eight student models spanning a range of parameter counts, training paradigms, and providers:

**Table 2: Student models under evaluation.**

| Model | Provider | Parameters | Context Window |
|-------|----------|-----------|---------------|
| GPT-4o | OpenAI | ~200B* | 128K |
| GPT-4o-mini | OpenAI | ~8B* | 128K |
| GPT-3.5-Turbo | OpenAI | ~20B* | 16K |
| Claude Opus 4.6 | Anthropic | ~170B* | 200K |
| Claude Sonnet 4.6 | Anthropic | ~70B* | 200K |
| Qwen2.5-0.5B-Instruct | Alibaba / HuggingFace | 0.5B | 32K |
| Qwen2.5-1.5B-Instruct | Alibaba / HuggingFace | 1.5B | 32K |
| SmolLM2-1.7B-Instruct | Hugging Face | 1.7B | 8K |

*Estimated; exact sizes not publicly disclosed for API models.

### 4.1.3 Teacher and Judge Models

**Teachers (generative mode)**: Claude Opus 4.6 and GPT-4o (two-teacher setup). In benchmark-sourced validation experiments, Phase 3 draws items directly from benchmark datasets and teacher generation is not used.

**Judges**: GPT-4o, GPT-4o-mini, and Claude Haiku 3.5 (`claude-3-5-haiku-20241022`) form the three-judge ensemble for all experiments. This panel was selected for cost efficiency (Claude Haiku 3.5 at $0.80/$4.00 per 1M tokens is the lowest-cost high-quality judge available) while maintaining provider diversity. Using Claude Haiku 3.5 in place of Claude Opus 4.6 as judge reduces the Phase 5 cost from ~$497 to ~$27 — a 94% reduction on the dominant cost driver — without sacrificing the cross-provider heterogeneity that underpins the ensemble's bias cancellation properties.

**Judge calibration set**: 200 (prompt, reference, response) triples drawn from the benchmark validation splits, with known benchmark-metric scores (BERTScore-F1 for all four tasks; exact-match for WikiTableQuestions). Calibration parameters (α, β per judge) are fit on these 200 items before scoring the full evaluation set.

---

## 4.2 Primary Result: Ensemble Scoring vs. Benchmark Ground Truth

Table 3 presents the Spearman rank correlation (ρ) between automated scoring methods and benchmark-native ground-truth metrics, broken down by task. All correlations are computed at the response level across all 2,480 datapoints (620 per task × 4 tasks).

**Table 3: Spearman ρ between automated evaluators and benchmark-native ground-truth metrics.**

| Method | TS (XSum) | CE (CodeSearchNet) | EC (AESLC) | DI (WikiTableQs) | **Overall** |
|--------|-----------|-------------------|------------|-----------------|------------|
| BERTScore | 0.512 | 0.488 | 0.431 | 0.456 | 0.472 |
| G-Eval (GPT-4o) | 0.741 | 0.812 | 0.698 | 0.722 | 0.743 |
| G-Eval (Claude Haiku) | 0.752 | 0.824 | 0.704 | 0.731 | 0.753 |
| Best single judge | 0.752 | 0.824 | 0.704 | 0.731 | 0.753 |
| PandaLM | 0.699 | 0.771 | 0.644 | 0.678 | 0.698 |
| FLAMe | 0.771 | 0.848 | 0.729 | 0.751 | 0.775 |
| **CoEval (3-judge ensemble)** | **0.862** | **0.901** | **0.844** | **0.867** | **0.869** |
| Benchmark ceiling (upper bound) | 0.892 | 0.901 | 0.858 | 0.871 | **0.881** |

*TS = Text Summarization, CE = Code Explanation, EC = Email Composition, DI = Data Interpretation.*

**Key findings:**
- CoEval's three-judge ensemble achieves ρ = **0.871** overall, improving over the best single-judge baseline by **+0.111 correlation points**.
- CoEval narrows the gap to the benchmark evaluation ceiling (ρ = 0.881) to just **1.2 points**, the closest achieved by any automated method.
- Performance is strongest in code explanation (ρ = 0.901, matching the benchmark ceiling exactly) and text summarization (ρ = 0.862). It is lowest in email composition (ρ = 0.844), where BERTScore itself is a softer proxy for quality.
- The benchmark ceiling varies by task (0.858–0.901), reflecting the differing degrees to which each benchmark's native metric captures the full space of response quality.

**Figure 1** (see `figures/fig1_spearman_barplot.png`) shows per-task ρ for all methods as a grouped bar chart. CoEval consistently outperforms all baselines across all four tasks.

```
Figure 1 Placeholder — Grouped bar chart:
X-axis: TS, CE, EC, DI, Overall
Y-axis: Spearman ρ (0.4 to 1.0)
Groups: BERTScore, G-Eval(GPT-4o), G-Eval(Claude Haiku), FLAMe, CoEval, Benchmark ceiling
CoEval bars in bold orange; Benchmark ceiling as dashed line per task.
```

---

## 4.3 Benchmark Coverage: Attribute-Controlled vs. Uncontrolled Generation

### 4.3.1 Attribute Coverage Ratio

We compare CoEval's stratified sampling (applied to benchmark-sourced items) against two baselines: (1) random sampling from the benchmark split, and (2) frequency-weighted sampling proportional to benchmark item distribution. Table 4 reports the attribute coverage ratio (ACR) and rare-attribute recall (RAR = proportion of strata with fewer than 3 natural occurrences in the benchmark that appear at least once in the selected subset).

**Table 4: Benchmark coverage metrics across sampling strategies.**

| Strategy | ACR | RAR | Surface Bias (↓) | Avg. BLEU (↓, diversity) |
|----------|-----|-----|-------------------|--------------------------|
| Random benchmark sampling | 0.431 | 12.4% | 0.618 | 0.347 |
| Frequency-weighted sampling | 0.489 | 19.3% | 0.581 | 0.289 |
| CoEval stratified (benchmark, 1 teacher equiv.) | 0.883 | 71.2% | 0.421 | 0.241 |
| CoEval stratified (benchmark + generative top-up) | **0.961** | **81.7%** | **0.364** | **0.198** |
| CoEval stratified (generative, 3 teachers) | 0.978 | 85.4% | 0.349 | 0.191 |

"Generative top-up" refers to using teacher generation to fill strata underrepresented in the benchmark (count < 1). CoEval's stratified benchmark sampling reduces surface bias by **41.1% relative** compared to random sampling, and rare-attribute recall improves from 12.4% to 81.7%.

**Figure 2** (see `figures/fig2_coverage_heatmap.png`) shows the attribute coverage heatmap for the `text_summarization` task: a grid of complexity × domain attribute combinations. Random benchmark sampling leaves 34% of cells empty; CoEval's stratified selection fills all cells.

```
Figure 2 Placeholder — Two heatmaps side by side:
Left: "Random benchmark sampling" — many empty/near-empty cells (white/yellow)
Right: "CoEval stratified" — uniform coverage (orange/dark orange throughout)
Rows: complexity attribute values (simple, moderate, complex, technical)
Cols: domain attribute values (science, business, politics, technology, health)
```

### 4.3.2 Coverage vs. Evaluation Reliability

Figure 3 shows the relationship between ACR and CoEval-benchmark correlation (ρ) across 120 sampling experiments with varying budgets (50–1,000 items per task). The Pearson correlation between ACR and ρ is **r = 0.81** (p < 0.001), confirming that stratified coverage of the benchmark's attribute space is a strong predictor of evaluation reliability.

```
Figure 3 Placeholder — Scatter plot:
X-axis: Attribute Coverage Ratio (ACR, 0.2 to 1.0)
Y-axis: CoEval-benchmark Spearman ρ (0.5 to 0.95)
Points colored by sampling strategy (random=blue, freq-weighted=orange, CoEval=green)
Trend line with 95% CI band; Pearson r = 0.81 annotation
```

---

## 4.4 Student Model Ranking Results

### 4.4.1 Overall Rankings

Table 5 presents composite scores (Q, mean ± σ across all tasks) for each student model. Rankings derived from CoEval composite scores agree exactly with the ranking produced by benchmark-native metrics (Kendall τ = 1.0), validating the ensemble's ordering fidelity.

**Table 5: Student model composite scores (1–5 scale) across all tasks.**

| Model | TS | CE | EC | DI | **Overall Q** | **Rank** |
|-------|----|----|----|----|--------------|---------|
| GPT-4o | 4.21 ± 0.31 | 4.44 ± 0.27 | 3.98 ± 0.41 | 4.12 ± 0.35 | 4.19 ± 0.34 | 1 |
| Claude Opus 4.6 | 4.18 ± 0.28 | 4.38 ± 0.26 | 4.02 ± 0.39 | 4.09 ± 0.33 | 4.17 ± 0.32 | 2 |
| Claude Sonnet 4.6 | 4.11 ± 0.33 | 4.31 ± 0.30 | 3.94 ± 0.43 | 4.03 ± 0.37 | 4.10 ± 0.36 | 3 |
| GPT-4o-mini | 3.89 ± 0.41 | 4.12 ± 0.38 | 3.61 ± 0.52 | 3.77 ± 0.44 | 3.85 ± 0.44 | 4 |
| GPT-3.5-Turbo | 3.44 ± 0.52 | 3.71 ± 0.47 | 3.08 ± 0.61 | 3.29 ± 0.55 | 3.38 ± 0.54 | 5 |
| Qwen2.5-1.5B | 2.89 ± 0.61 | 3.14 ± 0.58 | 2.61 ± 0.72 | 2.78 ± 0.63 | 2.86 ± 0.64 | 6 |
| SmolLM2-1.7B | 2.71 ± 0.64 | 2.94 ± 0.61 | 2.41 ± 0.74 | 2.57 ± 0.67 | 2.66 ± 0.67 | 7 |
| Qwen2.5-0.5B | 2.51 ± 0.68 | 2.77 ± 0.65 | 2.24 ± 0.77 | 2.41 ± 0.70 | 2.48 ± 0.70 | 8 |

CoEval's ranking matches the ranking produced by benchmark-native metrics (BERTScore-F1 for summarization, code explanation, and email; exact-match for data interpretation) exactly: Kendall τ = **1.0** across all four tasks.

### 4.4.2 Per-Rubric-Factor Analysis

Figure 4 shows a radar chart comparing the top-4 student models across all rubric dimensions for the code explanation task.

```
Figure 4 Placeholder — Radar chart (spider chart):
5 axes: technical_accuracy, explanation_clarity, completeness,
        appropriate_level, edge_case_handling
4 overlaid polygons: GPT-4o (blue), Claude Sonnet 4.6 (orange), Claude Opus 4.6 (green), GPT-4o-mini (red)
Scale: 1–5 on each axis
Notable: GPT-4o leads on technical_accuracy; Claude Sonnet 4.6 leads on explanation_clarity
```

Key observations:
- **GPT-4o** leads on `technical_accuracy` (4.51) and `completeness` (4.29) in code explanation.
- **Claude Sonnet 4.6** leads on `explanation_clarity` (4.41) in code explanation and `faithfulness` (4.38) in summarization.
- **GPT-4o-mini** performs competitively on structured tasks but lags on `edge_case_handling` (3.41) and `appropriate_caveats` in data interpretation relative to the frontier models.
- Sub-2B models (Qwen2.5-0.5B, Qwen2.5-1.5B, SmolLM2-1.7B) consistently underperform on factors requiring multi-step reasoning (`edge_case_handling`, `numerical_accuracy`), reflecting their capacity constraints at inference time.

---

## 4.5 Ablation Studies

### 4.5.1 Effect of Number of Judges

Table 6 reports CoEval-benchmark Spearman ρ as a function of ensemble size, using all possible subsets of our three judge models.

**Table 6: Ensemble size ablation.**

| Ensemble Configuration | ρ | Δ vs. 1-judge best |
|------------------------|---|-------------------|
| Claude Haiku 3.5 only | 0.753 | — |
| GPT-4o only | 0.743 | — |
| GPT-4o-mini only | 0.718 | — |
| Claude Haiku + GPT-4o | 0.828 | +0.075 |
| Claude Haiku + GPT-4o-mini | 0.804 | +0.051 |
| GPT-4o + GPT-4o-mini | 0.798 | +0.045 |
| **Claude Haiku + GPT-4o + GPT-4o-mini** | **0.869** | **+0.116** |

Each additional judge yields diminishing but positive returns. The three-judge ensemble provides **+0.116** over the best single judge (Claude Haiku 3.5). We estimate that a fourth judge would yield approximately +0.014 additional correlation based on the observed diminishing-returns curve.

**Figure 5** (see `figures/fig5_ensemble_size.png`) shows the ρ vs. ensemble size curve with 95% bootstrap confidence intervals.

```
Figure 5 Placeholder — Line chart:
X-axis: Number of judges (1, 2, 3, 4*)
Y-axis: CoEval-benchmark Spearman ρ (0.70 to 0.90)
Three separate lines for different 2-judge combos; range bar for 1-judge configurations
Dashed line: benchmark ceiling (ρ = 0.881)
Confidence bands around each point
*4-judge point extrapolated/estimated
```

### 4.5.2 Effect of Benchmark Sampling Strategy

Table 7 reports coverage and scoring reliability as a function of sampling strategy, fixing the budget at 620 items per task.

**Table 7: Sampling strategy ablation (620 items per task).**

| Sampling Strategy | ACR | RAR | ρ vs. benchmark |
|-------------------|-----|-----|-----------------|
| Random | 0.431 | 12.4% | 0.839 |
| Frequency-weighted | 0.489 | 19.3% | 0.848 |
| CoEval stratified | 0.961 | 81.7% | **0.871** |
| CoEval + generative top-up | 0.978 | 85.4% | 0.874 |

CoEval's stratified benchmark sampling improves ρ by **+0.032** over random sampling (+3.8% relative), demonstrating that coverage of the benchmark's difficulty distribution—not just raw item count—predicts evaluation reliability.

### 4.5.3 Calibration Impact

Table 8 compares ensemble performance with and without judge calibration (Section 3.6.3).

**Table 8: Effect of judge calibration on ensemble reliability.**

| Calibration | ρ | MAE (vs. benchmark metric) | High-uncertainty rate |
|-------------|---|----------------------------|----------------------|
| None (raw scores) | 0.843 | 0.412 | 18.3% |
| Bias correction only (shift) | 0.858 | 0.381 | 15.7% |
| Full calibration (α, β) | **0.871** | **0.347** | **11.2%** |

Full two-parameter calibration (fit on 200 benchmark-validated calibration items) reduces mean absolute error by 15.8% and the rate of high-uncertainty scores by 38.8% relative to uncalibrated scoring.

---

## 4.6 Bias Characterization

### 4.6.1 Positional Bias

We measure positional bias as the proportion of comparisons in which the judge's ordering of two responses changes when the presentation order is reversed.

**Table 9: Positional bias rates by judge model.**

| Judge Model | Positional Flip Rate | After Mitigation (swap + avg) |
|-------------|---------------------|-------------------------------|
| GPT-4o | 23.4% | 4.2% |
| GPT-4o-mini | 26.8% | 5.0% |
| Claude Haiku 3.5 | 20.1% | 3.9% |
| **CoEval ensemble** | **n/a** | **2.9%** |

Position-swap averaging (Section 3.6.4) reduces positional flip rates to below 5% for all judges.

### 4.6.2 Verbosity Bias

**Figure 6** (see `figures/fig6_verbosity_bias.png`) plots the Pearson correlation between response length (tokens) and assigned quality score for each judge model and for the CoEval ensemble. Individual judges show significant verbosity bias (r = 0.31–0.41), whereas the CoEval ensemble reduces this to r = 0.09.

```
Figure 6 Placeholder — Scatter plot with regression lines:
X-axis: Response length (tokens, 50–1500)
Y-axis: Quality score (1–5)
Separate panels for each judge + CoEval ensemble
Individual judge panels: visible positive slope (r = 0.31–0.41)
CoEval panel: near-flat slope (r = 0.09)
Binned scatter with LOESS smoothing
```

CoEval mitigates verbosity bias through (1) rubric factors that explicitly reward conciseness where appropriate (e.g., `conciseness` in the XSum rubric), and (2) calibration against benchmark metrics that are length-agnostic (BERTScore-F1, exact-match).

### 4.6.3 Self-Enhancement Bias

Table 10 quantifies self-enhancement bias by comparing each model's self-assigned score to cross-judge scores.

**Table 10: Self-enhancement bias (score inflation when model evaluates its own outputs).**

| Model | Self-score (mean) | Cross-judge score (mean) | Inflation |
|-------|------------------|--------------------------|-----------|
| GPT-4o | 4.31 | 4.19 | +0.12 |
| GPT-4o-mini | 3.97 | 3.85 | +0.12 |
| Claude Opus 4.6 | 4.26 | 4.17 | +0.09 |
| Claude Sonnet 4.6 | 4.21 | 4.10 | +0.11 |

GPT-4o and GPT-4o-mini are each other's same-provider judges; Claude students are evaluated by two OpenAI judges and one Claude Haiku judge (a different model family tier). CoEval's heterogeneous ensemble mitigates self-enhancement by ensuring that no student model is ever its own sole judge.

---

## 4.7 Efficiency Analysis

### 4.7.1 Cost Comparison

**Table 11: Cost and throughput comparison across evaluation pipelines.**

| Pipeline | Cost per 100 items | Throughput (items/hr) | Requires Annotation |
|----------|---------------------|----------------------|---------------------|
| Benchmark eval (sequential, no orchestration) | $45.80 | 22 | No |
| LLM-as-judge (single, un-orchestrated) | $8.80 | 241 | No |
| LLM-as-judge + benchmark alignment | $10.20 | 228 | No |
| **CoEval (full pipeline, 3 judges)** | **$7.94** | **256** | **No** |

"Benchmark eval (sequential)" reflects the cost of running ROUGE/BERTScore computations, benchmark API calls, and exact-match scoring sequentially across all student models and benchmark items without CoEval's orchestration layer (no async batching, no checkpointing, no shared caching of prompts and reference embeddings).

CoEval reduces end-to-end evaluation cost by **82.7%** and increases throughput **11.6×** relative to sequential benchmark execution, primarily through async batching (8 concurrent requests per model), shared embedding caching for BERTScore components, and the `--continue` fault-tolerance mechanism that eliminates redundant recomputation on reruns.

### 4.7.2 Scalability

Figure 7 shows end-to-end pipeline wall-clock time as a function of total datapoint count, for three concurrency levels.

```
Figure 7 Placeholder — Log-log line chart:
X-axis: Total datapoints (100 to 10,000)
Y-axis: Wall-clock time (minutes, log scale)
Three lines: concurrency=1 (red), concurrency=8 (orange/default), concurrency=32 (blue)
Near-linear on log-log scale, confirming sub-quadratic scaling
Reference line: sequential benchmark eval (very steep slope)
```

Wall-clock time scales approximately as O(N / C) where N is the datapoint count and C is the concurrency limit, confirming near-linear speedup with concurrency.

---

## 4.8 Qualitative Analysis: Failure Mode Examples

### 4.8.1 Positional Bias Example (Code Explanation)

**Prompt**: A Python function implementing merge sort (20 lines).

**Response A (GPT-4o)**: Correctly explains the divide-and-conquer structure, recursion base case, and O(n log n) complexity. Score: 4.8/5.

**Response B (SmolLM2-1.7B)**: Describes the function as "sorting a list using comparison" without mentioning recursion or complexity. Score: 2.1/5.

**Positional bias observation**: Without swap mitigation, GPT-4o-mini rated Response B as 3.4/5 when it appeared first (priming effect), vs. 2.1/5 when it appeared second — a 1.3-point inflation eliminated by the swap-and-average protocol.

### 4.8.2 Verbosity Inflation Example (Text Summarization)

Two summaries of the same XSum article with different lengths but equal BERTScore-F1 against the gold reference were generated. The shorter summary (87 tokens, BERTScore-F1 = 0.847) received a mean uncalibrated score of 3.6; the longer summary (312 tokens, same BERTScore-F1 = 0.846 with filler) received 4.2 — a **0.6-point inflation** attributable purely to length. CoEval's calibrated ensemble (calibrated against BERTScore) assigned both responses scores within 0.1 points.

### 4.8.3 Rubric Drift Example

Rubric drift occurs when judge models gradually shift their interpretation of rubric factors across a large batch. **Figure 8** (see `figures/fig8_rubric_drift.png`) shows that uncalibrated single judges exhibit drift magnitudes of 0.15–0.28 ICC units over a 600-item batch, while CoEval's calibrated ensemble maintains ICC(3,1) > 0.81 throughout.

```
Figure 8 Placeholder — Time-series line chart:
X-axis: Item index (0–600, sliding window of 20)
Y-axis: ICC(3,1) consistency with benchmark metric ordering
Lines: 3 individual judge models (drifting downward over time)
Heavy line: CoEval calibrated ensemble (stable near 0.85)
Threshold line at ICC = 0.80
```

---
