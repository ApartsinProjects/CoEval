# CoEval System Improvement Wishlist
## Synthesized from simulated reviewer perspectives (ACL, EMNLP, ICLR, JMLR, NMI)
## Generated: 2026-03-03

This document captures concrete, actionable system and tool improvements that would
strengthen CoEval's experimental results, publication narrative, and generalizability
claims across five target venues. Items are organized into three implementation
dimensions and closed with a priority matrix. All items are grounded in weaknesses
identified in the existing review corpus and in gaps in the current codebase.

Reviewer persona shorthand used in rationale fields:
- ACL = ACL 2026 (NLP evaluation methodology, statistical rigor, reproducibility)
- EMNLP = EMNLP 2026 (empirical NLP, robustness studies, multilingual evaluation)
- ICLR = ICLR 2026 (theoretical grounding, ablation completeness, learning-theoretic
  framing)
- JMLR = JMLR (statistical methodology, formal correctness, long-form reproducibility)
- NMI = Nature Machine Intelligence (broad scientific impact, ethical dimensions,
  real-world applicability, cross-domain generalization)

---

## A. Benchmark and Dataset Coverage

### 1. HumanEval+ and MBPP+ (execution-verified code generation)

Add loaders for `evalplus/humanevalplus` and `evalplus/mbppplus` (HuggingFace paths:
`evalplus/humanevalplus`, `evalplus/mbppplus`). These extend the 164-problem HumanEval
and 374-problem MBPP corpora with additional test cases that catch over-fitted solutions.
The existing `humaneval` adapter in `Code/runner/benchmarks/adapters/humaneval.py` uses
only text-match pass@k; EvalPlus provides execution-based test oracles. Implementation
requires adding a sandboxed Python executor (e.g., subprocess with resource limits) and
a `pass_at_k` metric alongside the existing `bleu` path in `benchmark_native_score`.

Rationale: ACL M3 flags that the current four tasks all require generation-quality
judging; EvalPlus provides discrete correct/incorrect ground truth that anchors the
calibration experiment (EXP-001). ICLR C3 and NMI both want code tasks with verifiable
ground truth to validate the OLS calibration pipeline beyond subjective-quality proxies.

### 2. MMLU-Pro (knowledge-intensive MCQ, 10-way)

Add a loader for `TIGER-Lab/MMLU-Pro` (HuggingFace path: `TIGER-Lab/MMLU-Pro`). The
existing `mmlu` adapter in `Code/runner/benchmarks/adapters/mmlu.py` covers 57-subject
4-way MCQ; MMLU-Pro extends this to 10-way with harder, reasoning-dependent items. The
`exact_match` metric already used for MCQ tasks applies directly.

Rationale: JMLR and ACL both flag that the current task set is limited to NLG
generation; adding a large-vocabulary, knowledge-intensive MCQ benchmark demonstrates
that the rubric-scoring mechanism generalizes to discriminative tasks via the existing
`label_eval.py` classification path. NMI expects broad domain coverage to justify the
"general-purpose framework" claim.

### 3. GSM8K and MATH (multi-step arithmetic and proof-level mathematics)

The runner-side `gsm8k` adapter exists in `Code/runner/benchmarks/adapters/gsm8k.py`
but there is no corresponding Public-side loader in `Public/benchmark/loaders/`. Add
`Public/benchmark/loaders/gsm8k.py` pointing to `openai/gsm8k` (HuggingFace path:
`openai/gsm8k`, `test` split, 1,319 items). The existing `math_dataset` loader covers
MATH Level 1-5 but uses a string-match metric that is brittle for reformatted answers;
add a symbolic equivalence scorer using `sympy.simplify` to reduce false-negative exact
matches for equivalent mathematical expressions.

Rationale: ACL M3 requires at least one structured-prediction or reasoning task to
support the claim of framework generality. The reviewer cited commonsense reasoning
and multi-hop QA; multi-step math provides similarly structured ground truth that is
absent from the four current tasks. ICLR M3 specifically calls out that attribute
adherence has not been measured for any existing task; GSM8K's step-count attribute
is mechanically verifiable and would be the first case where attribute coverage can be
confirmed instrumentally rather than assumed.

### 4. WMT23 / FLORES-200 (multilingual translation quality)

Add a loader for `Helsinki-NLP/flores` (HuggingFace path: `openlanguagedata/flores_plus`
or `gsarti/flores_101`) for the FLORES-200 evaluation benchmark covering 200 languages.
Use chrF++ as the `benchmark_native_score` metric (add `sacrebleu` dependency alongside
the existing `bert_score` dependency). This requires implementing a new metric branch in
`Public/benchmark/compute_scores.py` alongside the existing `bertscore` and `bleu`
branches.

Rationale: EMNLP and NMI are the primary venues requesting this. The paper's Section 6
limitation acknowledges "all findings derive from English-language NLP tasks." EMNLP
reviewers at the empirical NLP track consistently flag monolingual evaluation systems as
having bounded generalizability claims. Adding two non-English tasks (e.g.,
Spanish-English and Chinese-English translation from FLORES) would transform the
limitation into a validated scope boundary.

### 5. HellaSwag and WinoGrande Adversarial Splits

The existing `winogrande` loader (`Public/benchmark/loaders/winogrande.py`) uses the
standard split. The existing `hellaswag` adapter in `Code/runner/benchmarks/adapters/`
lacks a Public-side loader. Add `Public/benchmark/loaders/hellaswag.py` using
`Rowan/hellaswag` (HuggingFace path: `Rowan/hellaswag`, `validation` split, 10,042
items, `exact_match` metric). Additionally, add the WinoGrande adversarial split
(`allenai/winogrande`, `winogrande_debiased` configuration) as a second registered entry
`winogrande_debiased` in `_REGISTRY` in `Public/benchmark/loaders/__init__.py`.

Rationale: EMNLP reviewers prioritize robustness to adversarial perturbation and
debiased evaluation splits. The `winogrande_debiased` configuration removes statistical
artifacts that make the standard split solvable via surface cues. Using adversarial
splits strengthens the claim that CoEval-generated datapoints are genuinely challenging
rather than exploiting the same artifacts.

### 6. BoolQ and CommonsenseQA (binary QA and commonsense reasoning)

Add loaders for `google/boolq` (HuggingFace path: `google/boolq`, `validation` split,
3,270 items, `exact_match` metric after normalizing Yes/No) and
`tau/commonsense_qa` (HuggingFace path: `tau/commonsense_qa`, `validation` split,
1,221 items, `exact_match` metric on MCQ labels). Both use the existing `exact_match`
metric and require no new scoring infrastructure.

Rationale: ACL M3 explicitly names "commonsense reasoning" and "textual entailment" as
absent task types that undercut the paper's generality claim. BoolQ covers polar QA
with passage-grounded reasoning; CommonsenseQA covers knowledge-intensive 5-way MCQ.
Both are standard ACL-track benchmark tasks with stable HuggingFace loaders.

### 7. ChartQA and TabMWP (visual and tabular reasoning)

Add loaders for `HuggingFaceM4/ChartQA` (HuggingFace path: `HuggingFaceM4/ChartQA`,
`test` split) and `lupantech/tabmwp` (HuggingFace path: `lupantech/tabmwp`). ChartQA
requires multimodal input (chart images); for text-only pipeline compatibility, use
only the `human` split which includes textual chart descriptions alongside questions.
TabMWP provides 38,431 grade-school math word problems grounded in tabular data.

Rationale: The experiment_backlog.md (EXP-001) already lists "data_interpretation
(ChartQA)" as the target benchmark for validating the `data_interpretation` task. Adding
the loader enables the planned EXP-001 ground-truth comparison experiment without
requiring a bespoke ingestion script. NMI reviewers value demonstrated applicability to
emerging modalities (tabular, semi-structured data).

### 8. MT-Bench and AlpacaEval 2 (instruction-following open-ended QA)

Add loaders for the MT-Bench question corpus (`lmsys/mt_bench_human_judgments`,
HuggingFace path: `lmsys/mt_bench_human_judgments`) and AlpacaEval 2
(`tatsu-lab/alpaca_eval`, HuggingFace path: `tatsu-lab/alpaca_eval`). These do not have
discrete ground-truth scores, so `benchmark_native_score` should use the average human
preference score included in the dataset metadata. This extends the calibration pipeline
to human-preference-grounded benchmarks rather than automated metric proxies.

Rationale: ICLR C2 flags that the OLS calibration is circular (calibrated against
consensus from the same judges being calibrated). MT-Bench and AlpacaEval 2 provide
external human preference labels that break the circularity, enabling the first genuine
external-validity test of the calibration pipeline. This directly addresses EXP-001 and
resolves ICLR C2 for the camera-ready version.

### 9. TruthfulQA (truthfulness and hallucination)

Add a loader for `truthful_qa` (HuggingFace path: `truthful_qa`, `generation` and
`multiple_choice` configurations). The existing adapter in
`Code/runner/benchmarks/adapters/truthfulqa.py` covers the runner side; add the
corresponding `Public/benchmark/loaders/truthfulqa.py` loader. For the `generation`
configuration, `benchmark_native_score` should use BLEURT-20 (add `evaluate` package
dependency; `evaluate.load("bleurt", "BLEURT-20")`). For the `multiple_choice`
configuration, use `exact_match`.

Rationale: NMI and ACL both stress ethical dimensions of LLM evaluation. TruthfulQA
directly measures a safety-adjacent property (hallucination tendency) and its inclusion
in the benchmark suite signals that CoEval can serve as an evaluation framework for
alignment-relevant properties, not just task-performance metrics.

### 10. MedQA-USMLE and LegalBench (domain-specific professional competence)

Add loaders for `bigbio/med_qa` (HuggingFace path: `bigbio/med_qa`, USMLE split,
`exact_match` metric) and `hazyresearch/legalbench` (HuggingFace path:
`hazyresearch/legalbench`, multiple subtask configurations, `exact_match`). These cover
professional knowledge domains absent from the current 28 loaders.

Rationale: NMI expects demonstration of real-world applicability beyond academic NLP
tasks. JMLR reviewers scrutinize generalizability claims; professional-domain benchmarks
with distinct vocabulary, reasoning patterns, and rubric requirements stress-test the
claim that attribute-controlled evaluation transfers across domains without manual rubric
tuning. The `label_eval.py` classification path already handles MCQ tasks without judge
LLMs, so no new evaluation infrastructure is required.

---

## B. System Features

### 1. `coeval compare` CLI subcommand (multi-run comparison)

Add a new CLI subcommand `coeval compare --runs RUN_A RUN_B [--metric wpa|kappa|spa]
[--output compare_report/]` that ingests two or more completed experiment folders and
produces a differential analysis: student ranking stability (Kendall tau between run
rankings), judge agreement drift, attribute coverage overlap, and cost delta. The
command should write both a JSON summary and an HTML report (reusing the existing
`html_base.py` infrastructure).

Implementation location: `Code/runner/commands/compare_cmd.py` (new file), registered
in `Code/runner/cli.py` alongside existing subcommands.

Rationale: ACL reproducibility requirements include demonstrating that results are
stable across re-runs with different random seeds. JMLR requires reporting run-to-run
variance explicitly. The `compare` command operationalizes this without requiring users
to write custom scripts, and it enables the paper to report stability metrics from
repeated medium-benchmark runs as a table in Section 4 or the appendix.

### 2. `--positional-swap` flag for Phase 4 (positional bias measurement)

Add a config option `experiment.positional_swap: true` (or CLI flag
`coeval run --positional-swap`) that, for each (datapoint, student) pair in Phase 4,
generates a second response where the input prompt has its A/B option order reversed
(for MCQ tasks) or where a secondary instruction ordering is applied (for generation
tasks). Phase 5 then scores both orderings and the Positional Flip Rate (PFR) is
computed as the fraction of pairs where the judge's score changes.

The PFR metric should be reported in a new `positional_bias` section of the
`run_summary.json` output and in a dedicated HTML panel added to the existing
`summary_report.py` report.

Implementation location: new flag in `Code/runner/config.py` (config validation V-18),
new logic in `Code/runner/phases/phase4.py` to emit paired response records with a
`positional_variant: true` field, and new metric computation in
`Code/analyzer/reports/summary_report.py`.

Rationale: EXP-003 in experiment_backlog.md specifies PFR measurement as P2 priority.
ICLR C2 and ACL M2 both require experimental evidence that ensemble averaging reduces
known judge biases. PFR is the most direct measurable proxy for positional bias and
requires no external annotations.

### 3. `--verbosity-bias` analysis flag for Phase 5 output

Add a config option `experiment.compute_verbosity_bias: true` that triggers a post-Phase
5 analysis computing Pearson r(response_length_tokens, score_norm) per judge, per task,
and for the ensemble. The analysis should use the `token_count` field already present in
Phase 4 response records and the `score_norm` values in Phase 5 evaluation records. The
result should be added to `run_summary.json` under a `verbosity_bias` key and rendered
as a bar chart in the summary HTML report.

Rationale: EXP-004 in experiment_backlog.md specifies verbosity bias measurement as P3
priority requiring only an analyzer patch. ACL and EMNLP reviewers frequently require
evidence that LLM-judge scores are not length-confounded. The computation requires no
new LLM calls and can be done entirely from existing Phase 4 and Phase 5 JSONL data.

### 4. Bootstrap CI computation for teacher discrimination metrics (V1, S2, R3)

Add a `--bootstrap-teacher-ci` flag to `coeval analyze` (or activate it by default) that
computes B=1000 bootstrap resamples of V1, S2, and R3 for each teacher by resampling
datapoints with replacement. Report 2.5th and 97.5th percentile bounds alongside the
point estimates. Store results in `calibration_params.json` under a
`teacher_discrimination_ci` key and render them as error bars in the teacher report
HTML.

Implementation location: new function `bootstrap_teacher_ci(units, teachers, B=1000,
seed=0)` in `Code/analyzer/` (new file `metrics_bootstrap.py`), called from
`Code/analyzer/reports/teacher_report.py`.

Rationale: ACL C3 states explicitly that the V1 difference between SmolLM2-1.7B
(V1=0.0046) and GPT-4o-mini (V1=0.0039) requires bootstrap CIs before the ranking
claim can be published. This is the highest-priority statistical gap identified by ACL
round-2 review. JMLR always requires interval estimates for small-sample comparisons.

### 5. Self-evaluation confound sensitivity analysis

Add a `coeval analyze --self-eval-sensitivity` flag that partitions evaluation units
into within-role triples (student_model == teacher_model or student_model == judge_model
or teacher_model == judge_model) and cross-role triples (all three roles held by
different models). The command computes mean score_norm for both partitions per student
model and reports the delta. Results are added to the robust summary report as a
dedicated "Self-Evaluation Sensitivity" section.

Implementation location: new analysis function in `Code/analyzer/loader.py` that
annotates `EESDataUnit` instances with a `self_eval_triple` boolean flag, and a new
rendering block in `Code/analyzer/reports/robust.py`.

Rationale: ACL M2 and ICLR C4 both identify the self-evaluation confound as an
uncontrolled variable that makes the student capability ranking uninterpretable. The ACL
reviewer explicitly states that the paper must report either the sensitivity analysis or
the count of within-model triples as a fraction of all triples, with a lower bound on
potential bias magnitude. This feature implements the sensitivity analysis path.

### 6. Percentile bootstrap and BCa CI for Cohen's kappa (replace normal approximation)

Replace the current normal-approximation kappa CI in `Code/analyzer/` with a percentile
bootstrap or bias-corrected accelerated (BCa) interval. The current implementation uses
`kappa_hat +/- 1.96 * se_boot`, which produces negative lower bounds when kappa is near
zero (e.g., kappa = 0.003 for SmolLM2-1.7B). Implement using `scipy.stats.bootstrap`
with `method='BCa'` and B=2000 resamples. The BCa interval remains within [0, 1] for
near-zero kappa values and is appropriate for bounded statistics.

Implementation location: `Code/analyzer/` — search for the kappa CI computation and
replace the point-estimate-plus-1.96-se formula.

Rationale: ICLR M2 flags the normal approximation as formally incorrect for kappa near
zero. JMLR expects BCa intervals by default for bounded statistics. This is a
correctness fix, not a new feature, and it changes only the reported CI bounds, not the
point estimates.

### 7. Attribute adherence verification module (`coeval verify-attributes`)

Add a new CLI subcommand `coeval verify-attributes --run RUN_DIR [--sample N] [--judge
JUDGE_MODEL]` that takes a random sample of N Phase 3 datapoints and uses a specified
judge model to verify whether the generated prompt text actually exhibits the sampled
target attribute values. The judge is prompted with a binary question: "Does the
following prompt exhibit [attribute=value]? Answer Yes or No." The attribute adherence
rate (fraction of Yes responses) is reported per attribute, per attribute value, and
per teacher.

Implementation location: `Code/runner/commands/` (new file `verify_cmd.py`), registered
in `Code/runner/cli.py`.

Rationale: ICLR M3 states that "the coverage guarantee is purely procedural" because
attribute adherence has not been measured. ACL M3 notes that the paper cannot claim
"attribute-controlled generation" without verifying that generated text actually exhibits
the requested attributes. This command operationalizes the measurement required by both
reviewers and enables the paper to report adherence rates as a validation table.

### 8. Ensemble size ablation CLI flag (`coeval analyze --ensemble-ablation`)

Add a `--ensemble-ablation` flag to `coeval analyze` that computes student rankings and
Spearman rho (against benchmark_native_score) for all subsets of size k=1,2,...,|J| of
the judge pool. Output a JSON table of (k, subset, rho, kendall_tau_vs_full) values and
render as a line plot (ensemble size vs. rho) in a new `ensemble_ablation` HTML report.

Implementation location: new analysis function in `Code/analyzer/` that enumerates
judge subsets (using `itertools.combinations`) and re-computes ensemble scores from raw
Phase 5 JSONL records for each subset.

Rationale: EXP-002 in experiment_backlog.md specifies ensemble size ablation as P2
priority requiring no new API calls. ICLR and JMLR both require ablation evidence that
ensemble size monotonically improves reliability, since this is a core architectural
claim of the paper. The computation requires only existing Phase 5 evaluation data.

### 9. Minimum judge quality threshold with principled default

Add a config option `experiment.judge_min_wpa: float` (default 0.0, meaning no
threshold) and a corresponding `experiment.judge_min_kappa: float` option. During the
`robust_filter` computation in `Code/analyzer/`, exclude from J* any judge whose WPA or
kappa falls below the specified threshold, regardless of whether it falls in the top 50%
by rank. The current top-half selection heuristic is retained as the default when no
explicit threshold is set, but the threshold option enables principled cutoffs (e.g.,
`judge_min_kappa: 0.10` to exclude chance-level judges).

Document the threshold choice in a config option `experiment.judge_selection_rationale:
str` that is written to `meta.json` and displayed in the robust summary report.

Rationale: ICLR C3 identifies the top-50% threshold as having "no principled
justification." The fix does not require changing the default behavior but gives users
and paper reviewers a verifiable mechanism for excluding chance-level judges. The config
option makes the selection criterion auditable from the output metadata.

### 10. `coeval export --format parquet|csv|jsonl-flat` for downstream analysis

Add a `--format parquet` option to the existing export functionality (currently the
analyzer writes Excel via `Code/analyzer/reports/excel.py` and HTML reports) that
exports all Phase 5 evaluation units as a flat Parquet file with columns: `run_id`,
`task_id`, `teacher_model_id`, `student_model_id`, `judge_model_id`, `datapoint_id`,
`rubric_aspect`, `score`, `score_norm`, `benchmark_native_score`, `token_count`,
`evaluated_at`. Requires `pyarrow` as an optional dependency (add to `pyproject.toml`
optional extras: `coeval[parquet]`).

Rationale: JMLR and NMI both require that raw data be depositable in a structured
format alongside the paper. ACL reproducibility guidelines recommend machine-readable
data exports. The Parquet format is smaller than JSONL for the evaluation corpus and
is directly importable into pandas, R, and Julia for independent analysis.

### 11. `pass@k` metric support in Phase 5 for code generation tasks

Add `pass_at_k` as a supported `benchmark_native_score` metric for code generation tasks
(HumanEval, MBPP, EvalPlus). This requires adding a sandboxed Python executor that runs
generated code against test cases. Use the `restricted_python` or `multiprocess` timeout
approach. The `pass_at_k` unbiased estimator from Chen et al. (2021) is:
`pass@k = 1 - C(n-c, k) / C(n, k)` where n is total samples, c is correct samples, k
is the target. Add this formula to `Public/benchmark/compute_scores.py` alongside the
existing metric dispatch.

Rationale: ICLR expects execution-verified evaluation for code tasks as the gold
standard. The existing `bleu`-based code metric is acknowledged in the paper as a proxy;
replacing it with `pass@k` for HumanEval/MBPP tasks directly addresses the "no
verifiable ground truth" gap in the calibration experiment.

### 12. `coeval wizard` multilingual task scaffolding

Extend the existing `wizard` command (`Code/runner/commands/wizard_cmd.py`) with a
`--language` option that prompts the user to select a target language and injects
language-appropriate instructions into the task description, attribute definitions, and
rubric criteria generation prompts. This enables non-English benchmark construction
without requiring manual configuration.

Rationale: EMNLP and NMI reviewers flag the English-only limitation. The wizard is the
primary user-facing configuration tool; making it language-aware is the lowest-effort
path to multilingual capability demonstration. No new pipeline phases are required; only
the prompts in `Code/runner/prompts.py` need language-conditioned variants.

---

## C. Output Reports and Analyses

### 1. Kernel density estimate (KDE) plot of per-item mean student scores by teacher

Add a KDE plot to the teacher report (`Code/analyzer/reports/teacher_report.py`) showing
the distribution of per-item mean calibrated scores for each teacher, one curve per
teacher on a shared x-axis [0, 1]. Use Plotly's `violin` or `histogram` trace with
`histnorm='probability density'` to approximate KDE. Add a bimodality coefficient
statistic (Sarle's b = (skewness^2 + 1) / kurtosis) per teacher, displayed in the
report alongside the V1/S2/R3 metrics.

Rationale: Section 5.2 of the paper (06_analysis_conclusion_v2.md line 31) explicitly
contains a placeholder: "Figure placeholder (Figure X): Score distribution for
SmolLM2-1.7B-generated items (to be inserted in camera-ready version). A histogram of
per-item mean student scores for each of the five teachers is required to support the
bimodality claim." The paper cannot be submitted without this figure. The bimodality
coefficient provides a scalar summary that supports the floor-and-ceiling vs.
prompt-diversity hypothesis distinction.

### 2. Attribute adherence heatmap in the coverage report

Add a new view to `Code/analyzer/reports/coverage.py` that displays a heatmap of
attribute adherence rates (from `coeval verify-attributes` output) with rows = teachers,
columns = target attribute values, and cell color = adherence fraction [0, 1]. Flag
cells below 0.7 in red. This view only renders if the verify-attributes output JSON is
present in the run directory.

Rationale: ICLR M3 requires that attribute adherence be measured and reported, not
assumed. The heatmap provides the visual evidence required for the paper's claim that
"stratified attribute sampling guarantees coverage of quality dimensions." Without it,
the coverage claim is purely procedural.

### 3. Calibration residual diagnostic plot

Add a calibration residual plot to the judge consistency report
(`Code/analyzer/reports/consistency.py`) showing, for each judge, a scatter of
(raw_score_norm, residual = calibrated_score - benchmark_native_score) against
raw_score_norm. A well-calibrated judge should show residuals centered near zero with no
systematic trend. Add a LOWESS smoothed trend line using a pure-Python LOWESS
implementation (no statsmodels dependency required; use a 5-point moving average as a
lightweight approximation) to flag non-linear calibration artifacts.

Rationale: ICLR C2 flags that the OLS calibration is circular and may perpetuate
systematic biases. The residual plot makes systematic bias visible without requiring
additional experiments. JMLR expects diagnostic plots for all regression-based
calibration procedures.

### 4. Wilcoxon signed-rank test results for pairwise kappa comparisons

Add a statistical testing section to the judge report
(`Code/analyzer/reports/judge_report.py`) that, for all pairs of judge model pairs (e.g.,
comparing kappa_pair_AB against kappa_pair_AC), runs a Wilcoxon signed-rank test on the
per-item kappa estimates with Bonferroni correction for the number of comparisons
(m*(m-1)/2 pairs where m is the number of judge models). Report: test statistic, raw
p-value, Bonferroni-corrected p-value, and significance indicator (*, **, ***) at
alpha=0.05, 0.01, 0.001 thresholds. Requires `scipy.stats.wilcoxon`.

Rationale: ACL M1 explicitly requires "a permutation test or Wilcoxon test on the
per-item kappa estimates" for the key pairwise comparison. JMLR expects Bonferroni
correction when multiple comparisons are reported. This is the single most directly
actionable statistical addition requested by the existing review corpus.

### 5. Run-to-run stability report (`coeval compare` output)

The `coeval compare` command (B1 above) should produce a stability report containing:
(a) Kendall tau between student rankings across runs, (b) inter-run Spearman rho for
judge agreement scores, (c) inter-run Cohen's kappa for attribute coverage distributions,
and (d) a side-by-side student ranking table with rank-change annotations. The report
should be rendered as HTML using the existing `html_base.py` infrastructure.

Rationale: ACL reproducibility requirements (and the JMLR editorial standard) require
that claims about model ranking be stable across re-runs. The current codebase has no
mechanism to compare two runs; this report operationalizes the stability claim. Kendall
tau is the standard metric for ranking stability in NLP evaluation papers.

### 6. Cost efficiency breakdown report with batch savings visualization

Extend the existing cost summary in `Code/analyzer/reports/run_summary.py` with a
dedicated cost efficiency page showing: (a) a stacked bar chart of cost by phase and by
model, (b) a "batch savings" bar showing the dollar amount saved vs. sequential
non-batched execution for each provider, (c) a cost-per-evaluation curve as a function
of number of student models (to demonstrate the Extend mode amortization property), and
(d) an annualized cost projection assuming one full evaluation run per week.

The batch savings figure (`batch_savings_usd`) is already computed in
`estimate_cost_static()` in `Code/runner/interfaces/cost_estimator.py` but is not
rendered in any HTML report.

Rationale: ACL M4 flags the "82.7% cost reduction" claim as unsupported. The batch
savings chart provides the derivation in visual form. Section 5.4 of the paper discusses
cost structure but defers the per-evaluation cost curve to a figure that does not yet
exist.

### 7. Sensitivity table: self-evaluation confound quantification

Add a table to the student report (`Code/analyzer/reports/student_report.py`) that
reports for each student model: (a) the number of evaluations where student == teacher
or student == judge or teacher == judge (within-role triples), (b) the number of
cross-role evaluations, (c) the mean score_norm for within-role triples, (d) the mean
score_norm for cross-role triples, and (e) the difference (d) - (c) with a flag if the
difference exceeds 0.05. This table directly implements the sensitivity analysis
required by ACL M2 and ICLR C4.

### 8. Ensemble ablation line plot (ensemble size vs. Spearman rho)

The `--ensemble-ablation` analyzer output (B8 above) should render a line plot with
ensemble size k on the x-axis and Spearman rho (against benchmark_native_score) on the
y-axis. Plot individual subset rho values as semi-transparent dots and the mean rho per
k as a solid line. Add shaded 95% CI bands across subsets of size k. If
benchmark_native_score is absent (no benchmark teacher used), substitute Kendall tau
between the k-judge ensemble ranking and the full-|J|-judge ensemble ranking as the
y-axis metric.

Rationale: This directly produces Figure 8 (ensemble ablation) from the paper, which is
currently simulated (experiment_backlog.md: "Fig 8 uses simulated data"). The figure can
be generated from existing Phase 5 JSONL data without new API calls (EXP-002).

### 9. Verbosity bias scatter plot per judge

For the `--verbosity-bias` analyzer output (B3 above), render a scatter plot with
response_length_tokens on the x-axis and score_norm on the y-axis, one subplot per
judge model, with a LOWESS trend line. Report Pearson r and its p-value (from
`scipy.stats.pearsonr`) in the subplot title. Add an overall-ensemble subplot showing
the same for ensemble-averaged scores to demonstrate bias reduction.

Rationale: EXP-004 in experiment_backlog.md is listed as "low hanging fruit" requiring
only an analyzer patch. ACL and EMNLP reviewers standardly check for length bias in LLM
evaluators. This plot provides the figure required for Table 10 (verbosity bias) which
is currently simulated.

### 10. Spearman rho vs. ground-truth benchmark report

Add a dedicated calibration validation report (new file
`Code/analyzer/reports/calibration_report.py`) that, when `benchmark_native_score`
values are present in Phase 3 JSONL records, computes and renders: (a) Spearman rho
between ensemble score_norm and benchmark_native_score per judge, per task, and
overall; (b) rho for raw scores vs. calibrated scores side by side; (c) rho comparison
against BERTScore-F1 baseline (computed on the same records using `bert_score`
package); (d) a scatter plot of ensemble score vs. benchmark_native_score with the OLS
regression line overlaid. Include MAE alongside rho. The existing `calibration.py`
computes the rho values but they are not rendered in any HTML report.

Rationale: This report is the primary output of EXP-001 (Benchmark-Grounded Comparison
Experiment) which is the highest-priority experiment in experiment_backlog.md. Table 8
in the paper (benchmark comparison rho vs. baselines) is currently simulated; this
report generates the real version once EXP-001 is run.

### 11. Positional Flip Rate (PFR) report

Add a PFR report (new file `Code/analyzer/reports/positional_bias_report.py`) that reads
paired response records (from B2 `--positional-swap` runs) and computes: (a) PFR per
judge = fraction of items where the judge flips its score between the A-ordering and the
B-ordering; (b) PFR for the ensemble = fraction of items where the ensemble score
changes by more than 0.1 between orderings; (c) a side-by-side bar chart comparing
individual PFR vs. ensemble PFR. Include a statistical test (McNemar's chi-squared test
with continuity correction, `scipy.stats.mcnemar`) for whether individual PFR
significantly exceeds ensemble PFR.

Rationale: EXP-003 in experiment_backlog.md specifies PFR measurement. Table 9 in the
paper (PFR bias: 23.4% -> 2.9%) is currently simulated. This report generates the real
version. McNemar's test is the standard paired categorical test for flip-rate
comparisons.

### 12. Judge agreement stability across tasks (cross-task kappa heatmap)

Add a cross-task kappa heatmap to the judge report (`Code/analyzer/reports/judge_report.py`)
showing, for each (judge pair, task) cell, the pairwise Cohen's kappa computed on items
from that task only. This identifies whether inter-judge agreement is task-dependent
(a finding noted in Section 5.3 of the paper: "agreement is highest for code_explanation
and lowest for data_interpretation"). Currently, kappa is reported as a single pooled
value across all tasks.

Compute the per-task kappa using the existing kappa calculation infrastructure, filtered
by `u.task_id`. Render as a Plotly heatmap with judge pairs on one axis and tasks on the
other.

Rationale: Section 5.3 of the paper makes a task-difficulty claim based on aggregated
agreement; breaking it down by task provides the supporting evidence at the required
granularity. EMNLP reviewers routinely check whether aggregate metrics mask task-level
variation. This is purely a re-slicing of existing data with no new computation.

### 13. Rubric criterion difficulty ranking with inter-rater agreement

Add a view to the judge consistency report showing, for each rubric criterion (aspect),
the pairwise SPA and WPA averaged across all judge pairs, ranked from easiest to hardest
for judges to agree on. Flag criteria with mean SPA below 0.5 as "low-agreement
criteria" requiring rubric refinement. Currently, criterion-level agreement is partially
computed in `_build_data()` in `consistency.py` (the View 3 calibration table) but is
not ranked or visualized comparatively.

Rationale: Section 4.2 of the paper reports criterion-level agreement as a point
finding (technical_accuracy SPA=0.843, professionalism SPA=0.294) but provides no
systematic ranking. The ACL reviewer and EMNLP reviewer both want evidence that rubric
design choices affect evaluation reliability in a predictable, generalizable way. A
ranked criterion difficulty table provides this evidence systematically.

---

## Priority Matrix

| # | Item | Dimension | Venues | Effort | Publication Impact |
|---|------|-----------|--------|--------|--------------------|
| B4 | Bootstrap CI for V1/S2/R3 | System Feature | ACL, JMLR | Low | High |
| C4 | Wilcoxon signed-rank for kappa pairs | Report | ACL, JMLR | Low | High |
| C10 | Spearman rho vs. ground-truth report | Report | ICLR, ACL, JMLR | Low | High |
| B5 | Self-eval sensitivity analysis | System Feature | ACL, ICLR | Low | High |
| C7 | Self-eval confound table | Report | ACL, ICLR | Low | High |
| B6 | BCa CI for kappa (replace normal approx) | System Feature | ICLR, JMLR | Low | High |
| C1 | KDE/histogram of per-item scores by teacher | Report | ACL, EMNLP | Low | High |
| C8 | Ensemble ablation line plot | Report | ICLR, ACL | Med | High |
| B8 | Ensemble ablation CLI flag | System Feature | ICLR, ACL | Med | High |
| C9 | Verbosity bias scatter plot | Report | EMNLP, ACL | Low | Med |
| B3 | `--verbosity-bias` analyzer flag | System Feature | EMNLP, ACL | Low | Med |
| C6 | Cost efficiency + batch savings chart | Report | ACL, NMI | Low | Med |
| B2 | `--positional-swap` Phase 4 flag | System Feature | ICLR, ACL | Med | Med |
| C11 | Positional Flip Rate report | Report | ACL, EMNLP | Med | Med |
| B7 | `coeval verify-attributes` command | System Feature | ICLR, ACL | Med | Med |
| C2 | Attribute adherence heatmap | Report | ICLR, ACL | Med | Med |
| C3 | Calibration residual diagnostic plot | Report | ICLR, JMLR | Low | Med |
| B1 | `coeval compare` subcommand | System Feature | ACL, JMLR | Med | Med |
| C5 | Run-to-run stability report | Report | ACL, JMLR | Med | Med |
| A8 | MT-Bench / AlpacaEval 2 loaders | Benchmark | ICLR, ACL | Med | High |
| A3 | GSM8K public loader + sympy scorer | Benchmark | ACL, ICLR | Low | Med |
| A6 | BoolQ and CommonsenseQA loaders | Benchmark | ACL, EMNLP | Low | Med |
| A2 | MMLU-Pro loader | Benchmark | JMLR, NMI | Low | Med |
| A9 | TruthfulQA loader with BLEURT | Benchmark | NMI, ACL | Med | Med |
| A1 | HumanEval+ / MBPP+ loaders | Benchmark | ICLR, ACL | Med | Med |
| B11 | `pass@k` metric for code tasks | System Feature | ICLR | Med | Med |
| A5 | HellaSwag and WinoGrande-debiased loaders | Benchmark | EMNLP | Low | Med |
| A7 | ChartQA and TabMWP loaders | Benchmark | NMI, ACL | Med | Med |
| C12 | Cross-task kappa heatmap | Report | EMNLP | Low | Med |
| C13 | Rubric criterion difficulty ranking | Report | ACL, EMNLP | Low | Med |
| B9 | Principled judge quality threshold config | System Feature | ICLR | Low | Med |
| B10 | `coeval export --format parquet` | System Feature | JMLR, NMI | Low | Med |
| A4 | FLORES-200 multilingual loader + chrF++ | Benchmark | EMNLP, NMI | High | Med |
| A10 | MedQA + LegalBench loaders | Benchmark | NMI | Med | Low |
| B12 | `coeval wizard` multilingual scaffolding | System Feature | EMNLP, NMI | High | Low |

---

## Implementation Sequence Recommendation

The following ordering minimizes sequential dependencies and maximizes early publication
impact:

**Sprint 1 — Statistical corrections (no new experiments, ~1 day coding):**
- B4: Bootstrap CI for V1/S2/R3
- B6: BCa CI for kappa
- C4: Wilcoxon signed-rank tests
- C3: Calibration residual plot
- C7: Self-eval confound table
- C13: Rubric criterion difficulty ranking

**Sprint 2 — From existing data, no new API calls (~2 days coding):**
- B3 + C9: Verbosity bias flag and scatter plot (uses existing Phase 4/5 data)
- B8 + C8: Ensemble ablation flag and line plot (uses existing Phase 5 data)
- C6: Cost efficiency chart (data already in cost_estimate.json and cost_estimator.py)
- C12: Cross-task kappa heatmap (re-slicing existing kappa data)
- C1: KDE plot of per-item scores by teacher (uses existing Phase 5 data)

**Sprint 3 — New experiments required (~4 hours compute, ~$30 API cost):**
- EXP-001 (Benchmark-Grounded Comparison): run with A8 loaders (MT-Bench/AlpacaEval)
  and output to C10 (Spearman rho report)
- EXP-003 (Positional Bias): run with B2 flag and output to C11 (PFR report)
- B5 + C5: Self-eval sensitivity and stability reports (use EXP-001 data)

**Sprint 4 — Benchmark coverage expansion (incremental, low risk):**
- A3, A5, A6, A2: Low-effort loaders using existing metric infrastructure
- A1, A7, A9: Medium-effort loaders requiring new metric components

**Sprint 5 — Major features (multilingual, domain-specific):**
- A4: FLORES-200 + chrF++ (new metric dependency)
- A10, B12: Domain loaders and wizard multilingual support

---

*End of system_todo.md*
