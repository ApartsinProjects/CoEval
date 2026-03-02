# Analytics & Reports

[← Benchmarks](07-benchmarks.md) · [Resume & Recovery →](09-recovery.md)

---

After a run completes, CoEval's analysis package transforms raw JSONL evaluation data into eight interactive HTML reports and an Excel workbook. All reports are fully self-contained — no external CDN dependencies, no server required.

---

## Generating Reports

```bash
# Generate all eight reports at once
coeval analyze all \
    --run ./eval_runs/my-experiment-v1 \
    --out ./eval_runs/my-experiment-v1/reports

# Generate a single report
coeval analyze student-report \
    --run ./eval_runs/my-experiment-v1 \
    --out ./reports

# Generate the full Excel workbook
coeval analyze complete-report \
    --run ./eval_runs/my-experiment-v1 \
    --out ./reports
```

Using the `analyzer.main` module directly:

```bash
# Generate all HTML reports
python -m analyzer.main \
    --run-path benchmark/runs/medium-benchmark-v1 \
    --out-dir  benchmark/runs/medium-benchmark-v1/html_reports

# Generate a single report type
python -m analyzer.main \
    --run-path benchmark/runs/medium-benchmark-v1 \
    --report   student_report

# Generate paper tables (requires benchmark-native scores)
python -m analyzer.paper_tables --run-id paper-eval-v1 --out-dir paper/tables
```

---

## Report Catalogue

### `complete-report`
Full Excel workbook with all evaluation data across every (task, teacher, student, judge) combination. Includes raw scores, aggregated rankings, and metadata. Designed for stakeholder review and downstream statistical analysis.

Sheets included:
- `Summary` — overall model rankings + composite scores
- `StudentScores` — full per-(student, task, rubric_factor) score table
- `TeacherCoverage` — attribute coverage metrics per teacher
- `JudgeAgreement` — pairwise ICC between all judge pairs
- `FailedRecords` — records with validation errors (MISSING_RESPONSE, etc.)

### `score-distribution`
Interactive HTML histogram of judge score distributions. Filterable by task, teacher, student, and judge. Shows score spread, mean, median, and outlier bands. Reveals systematic over/under-scoring at a glance.

### `teacher-report`
Analysis of teacher model performance:
- Attribute coverage heatmap (which dimensions were sampled how often)
- Diversity score across nuanced attribute dimensions
- Item quality metrics (judge score distributions per teacher)
- Comparison of synthetic vs. benchmark teacher outputs

### `judge-report`
Analysis of judge model behavior:
- Judge score distributions and variance
- Positional bias detection (does response order affect scores?)
- Agreement with ground-truth benchmark scores (Spearman ρ)
- Calibration curves (judge score vs. BERTScore / BLEU)

### `student-report`
Analysis of student model performance:
- Per-task score breakdowns and percentile bands
- Cross-task ranking with confidence intervals
- Performance by attribute dimension (which input types challenge each model)
- Head-to-head comparisons between student pairs

### `interaction-matrix`
Color-coded heatmap of average scores across every (teacher × student × judge) triplet. Reveals interaction effects — e.g., which teacher-student combinations score unexpectedly high or low regardless of judge.

- **Heatmap** — mean composite score for each (teacher, student) cell
- **Row effects** — teacher contribution to scores (should be small)
- **Column effects** — student contribution (should be large)
- **Self-teaching cells** — highlighted where teacher == student

### `judge-consistency`
Inter-judge agreement analysis across all judge pairs:
- Spearman ρ rank correlation matrix
- Kendall τ agreement matrix
- ACR (Agreement Consistency Rate) per pair
- ICC matrix — pairwise intraclass correlation between judges per task
- Drift chart — ICC over sliding window of 20 items (detects rubric drift)
- Calibration parameters — α and β per judge per task
- High-uncertainty items — responses where inter-judge σ > 1.5 on any factor
- Identifies judges that are outliers or systematically miscalibrated

### `coverage-summary`
Attribute dimension coverage across the full benchmark:
- ACR gauge — overall and per-task attribute coverage ratio
- Stratum heatmap — grid of all target-attribute value combinations, coloured by datapoint count
- Rare-attribute recall — proportion of underrepresented strata covered
- Surface bias — mean pairwise BLEU across prompts
- Gaps in coverage (attribute values with fewer items than expected)
- Nuanced attribute distribution across tasks and teachers

### `summary-report`
High-level experiment summary for executive review:
- Top-line student rankings across all tasks
- Judge ensemble confidence
- Cost summary (actual calls × price)
- Key quality metrics in a single-page view

### `robust-summary`
Outlier-robust score aggregation:
- Trimmed mean and median scores per student
- Sensitivity analysis: how does ranking change when one judge is removed?
- Ensemble stability score (how consistent are rankings across judge subsets)
- Final model rankings with confidence intervals and robust ensemble weights

### `export-benchmark`
Exports data in a structured format compatible with external benchmark evaluation tools and leaderboards.

---

## HTML Report Features

All HTML reports include:
- **Interactive charts** (Plotly) — hover for exact values, click to filter
- **Filterable data tables** with CSV export
- **Sortable model rankings** by any metric column
- **Color-coded matrices** for quick pattern identification
- **Fully self-contained** — single HTML file, no internet connection required

---

## Key Metrics

| Metric | Symbol | Description |
|--------|--------|-------------|
| Spearman rank correlation | ρ | Monotone agreement between judge scores and ground-truth rankings |
| Kendall rank correlation | τ | Pairwise concordance between judge and ground-truth orderings |
| Agreement Consistency Rate | ACR | Judge-to-judge pairwise score agreement rate |
| Position Flip Rate | PFR | How often response order reversal changes judge's relative scores (positional bias) |
| Differentiation Score | — | Variance of scores across student models; higher = judges discriminate better |
| Calibration intercept | α | Additive correction from judge score to benchmark scale |
| Calibration slope | β | Multiplicative correction from judge score to benchmark scale |

---

## Metric Formulas

### Composite Score

```
Q(student) = mean over all valid (response, factor) units of score_norm
```

where `score_norm ∈ {0.0, 0.5, 1.0}` (Low / Medium / High).

Rubric-weighted composite:
```
Q_weighted = Σ_l  w_l × mean(scores on factor l)
```

### Attribute Coverage Ratio (ACR)

```
ACR = |{ω ∈ Ω : count(ω) ≥ 1}| / |Ω|
```

where Ω is the full attribute stratum space (Cartesian product of all `target_attributes` values). Perfect coverage: ACR = 1.0.

### Rare-Attribute Recall (RAR)

```
RAR = |{ω ∈ Ω_rare : count(ω) ≥ 1}| / |Ω_rare|
```

where Ω_rare contains strata with fewer than 3 natural occurrences in the benchmark. Measures coverage of underrepresented scenarios.

### Surface Bias

```
Surface Bias = mean pairwise BLEU between all prompt pairs
              (lower = more diverse prompts)
```

### Positional Flip Rate (PFR)

```
PFR = |comparisons where judge ranking changes on order swap| / |total comparisons|
```

Measured before and after swap-and-average mitigation.

### Spearman ρ (benchmark validation runs only)

```
ρ = Spearman rank correlation between:
    - CoEval composite score Q for each student response
    - benchmark_native_score for the same datapoint
```

Computed at the response level across all 620 × 4 = 2,480 datapoints. Requires benchmark-native scores to be populated (see Benchmark Datasets).

---

## Data Model

All reports are built on top of the unified `EESDataModel` (loaded by `analysis.loader.load_ees`). The key analytical unit is:

```
(response_id, rubric_factor) → score ∈ {High, Medium, Low}
```

Normalised to floats: `High=1.0`, `Medium=0.5`, `Low=0.0`.

**Validity classification.** A Phase 5 record is valid if:
- The referenced Phase 4 response exists (not `MISSING_RESPONSE`)
- The referenced Phase 3 datapoint exists (not `MISSING_DATAPOINT`)
- All rubric factors are present in the scores (not `INCOMPLETE_SCORES`)
- All score values are `High`, `Medium`, or `Low` (not `INVALID_SCORE_VALUE`)

Invalid records appear in the Excel `FailedRecords` sheet but are excluded from all aggregate statistics.

**Self-judging / self-teaching flags.** Records where `judge_model_id == student_model_id` are flagged `is_self_judging=True`; records where `teacher_model_id == student_model_id` are flagged `is_self_teaching=True`. Reports can be filtered to exclude these.

---

## Programmatic API

```python
from analyzer.loader import load_ees
from analyzer.metrics import (
    composite_score_by_student,
    coverage_ratio,
    judge_consistency,
)

model = load_ees("benchmark/runs/medium-benchmark-v1", partial_ok=True)

# Print any load warnings
for w in model.load_warnings:
    print("WARN:", w)

# Student composite scores (mean normalised score across all valid units)
scores = composite_score_by_student(model)
for student, score in sorted(scores.items(), key=lambda x: -x[1]):
    print(f"  {student}: {score:.3f}")

# Attribute coverage ratio
acr = coverage_ratio(model, task_id="text_summarization")
print(f"ACR (text_summarization): {acr:.3f}")

# Judge consistency (ICC per task)
icc = judge_consistency(model)
for task, val in icc.items():
    print(f"  ICC({task}): {val:.3f}")
```

Excel export:

```bash
python -m analyzer.main \
    --run-path benchmark/runs/medium-benchmark-v1 \
    --format excel \
    --out-file benchmark/runs/medium-benchmark-v1/analysis.xlsx
```

---

## Calibration API

```python
from analyzer.calibration import fit_calibration, apply_calibration, load_or_fit_calibration
from analyzer.loader import load_ees
from pathlib import Path

model = load_ees("benchmark/runs/paper-eval-v1")

# Fit overall calibration
params = load_or_fit_calibration(model, out_dir=Path("paper/tables"), holdout_n=200)
# params["gpt-4o"]["text_summarization"] → {alpha, beta, rho_raw, rho_calibrated, mae_raw, mae_calibrated}
# params["_overall"] → aggregated across all judges/tasks

# Apply to a list of raw scores
calibrated = apply_calibration(raw_scores, params["_overall"]["alpha"], params["_overall"]["beta"])
```

The result is cached in `paper/tables/calibration_params.json`.

---

## Paper Tables

The `analysis/paper_tables.py` module generates publication-ready tables:

```bash
python -m analyzer.paper_tables \
    --run benchmark/runs/paper-eval-v1 \
    --out paper/tables
```

This generates all 7 tables (`.tex` + `.csv`):

| File | Paper Table | Contents | Requires benchmark scores? |
|------|-------------|----------|---------------------------|
| `table3_spearman.tex/.csv` | Table 3 | Spearman ρ: CoEval ensemble + per-judge vs. benchmark ground truth | Yes |
| `table4_coverage.tex/.csv` | Table 4 | ACR, RAR, Surface Bias, fill rates by task | No |
| `table5_student_scores.tex/.csv` | Table 5 | Student composite scores, Kendall τ ranking | No |
| `table6_ensemble_ablation.tex/.csv` | Table 6 | ρ by ensemble size (1→all judges) | Yes |
| `table7_sampling_ablation.tex/.csv` | Table 7 | Random vs. freq-weighted vs. stratified sampling | No (ACR/RAR from EES) |
| `table8_calibration.tex/.csv` | Table 8 | OLS calibration effect (ρ + MAE before/after) | Yes |
| `table9_positional_bias.tex/.csv` | Table 9 | Positional flip rates (needs swap pairs) | No |
| `SUMMARY.md` | — | Data availability checklist + next steps | — |

**Automatically computed metrics:**
- **RAR** (Rare-Attribute Recall) — fraction of rare strata (freq < 3) covered; Table 4 + Table 7.
- **Surface Bias** — mean pairwise sentence-BLEU across Phase 3 prompts; Table 4. Requires `pip install nltk`.
- **OLS Calibration** — α, β fit on 200-item holdout; Table 8 + `calibration_params_overall.json`.

---

## Baseline Comparison

For Table 3 baseline columns, run the baseline comparison script:

```bash
python -m benchmark.run_baselines \
    --run  benchmark/runs/paper-eval-v1 \
    --out  paper/tables \
    --methods bertscore geval-gpt4o geval-claude \
    --max-pairs 200
```

Outputs `paper/tables/baselines.csv` with Spearman ρ for each method × task. Requires `pip install bert-score scipy` (BERTScore) and `OPENAI_API_KEY` / `ANTHROPIC_API_KEY` (G-Eval).

| Flag | Description | Default |
|------|-------------|---------|
| `--methods` | Which baselines: `bertscore`, `geval-gpt4o`, `geval-claude` | all |
| `--max-pairs N` | Subsample N items per task (cost control) | all |
| `--geval-gpt4o-model` | OpenAI model for G-Eval | `gpt-4o` |
| `--geval-claude-model` | Anthropic model for G-Eval | `claude-3-5-sonnet-20241022` |
| `--bertscore-model` | BERTScore backbone | `distilbert-base-uncased` |
| `--dry-run` | Print plan without making API calls | — |

---

## Comparing Multiple Runs

```bash
python -m analyzer.compare \
    --run-a benchmark/runs/medium-benchmark-v1 \
    --run-b benchmark/runs/paper-eval-v1 \
    --out-dir paper/comparison
```

Generates a comparison report showing ranking differences, score delta per student, and coverage improvement between runs.

---

## Partial / In-Progress Runs

All analysis commands accept `--partial-ok` to run on an experiment that is still in progress:

```bash
python -m analyzer.main \
    --run-path benchmark/runs/medium-benchmark-v1 \
    --partial-ok
```

A warning banner is shown at the top of every report indicating the run is incomplete, and any statistics are clearly marked as preliminary.

---

## CLI Reference

```
python -m analyzer.main
  --run-path PATH       Experiment folder (required)
  --out-dir  PATH       Output directory (default: {run-path}/html_reports)
  --report   TYPE       One of: student_report, teacher_report, judge_report,
                        score_dist, coverage, interaction, consistency,
                        robust_summary, all  (default: all)
  --format   FMT        html | excel | csv  (default: html)
  --partial-ok          Allow analysis of incomplete runs
  --exclude-self-judge  Exclude self-judging records from all statistics
  --exclude-self-teach  Exclude self-teaching records from all statistics

python -m analyzer.paper_tables
  --run-id   ID         Experiment ID (resolved under benchmark/runs/)
  --out-dir  PATH       Directory for CSV table files
  --tasks    LIST       Comma-separated task IDs (default: all)

python -m benchmark.emit_datapoints
  --dataset  NAME       xsum | codesearchnet | aeslc | wikitablequestions | all
  --run-id   ID         Create phase3_datapoints/ under benchmark/runs/{ID}/
  --out-dir  PATH       Override output directory
  --sample-size N       Items per dataset (default: 620)
  --split    NAME       Dataset split (default: loader default)
  --seed     INT        Sampling seed (default: 42)
```

---

## Sample Reports

All sample reports are self-contained HTML files — click to view rendered in browser.

### Experiment Planning Views

| Example | Description |
|---------|-------------|
| [Education Experiment Plan](https://htmlpreview.github.io/?https://raw.githubusercontent.com/ApartsinProjects/CoEval/master/Runs/education/education_description.html) | Full experiment plan: 3 real-dataset tasks + 10 synthetic tasks, 6 models, per-phase call budget, cost table |
| [Mixed Benchmark Plan](https://htmlpreview.github.io/?https://raw.githubusercontent.com/ApartsinProjects/CoEval/master/Runs/mixed/mixed_description.html) | Mixed benchmark plan: real benchmark datasets + OpenAI models |
| [Paper Dual-Track Plan](https://htmlpreview.github.io/?https://raw.githubusercontent.com/ApartsinProjects/CoEval/master/Runs/paper/paper_dual_track_description.html) | Paper evaluation: dual-track design with benchmark + generative teachers |

> **Generate your own planning view:**
> ```bash
> coeval describe --config my_experiment.yaml --out my_experiment_plan.html
> ```

> **Generate all reports from a completed run:**
> ```bash
> coeval analyze all --run ./Runs/my-experiment-v1 --out ./reports
> ```

### Analysis Reports — medium-benchmark

| Report | Description |
|--------|-------------|
| [Dashboard](https://htmlpreview.github.io/?https://raw.githubusercontent.com/ApartsinProjects/CoEval/master/Runs/medium-benchmark/reports/index.html) | Overview dashboard — all reports in one place with top-line rankings and navigation |
| [Student Report](https://htmlpreview.github.io/?https://raw.githubusercontent.com/ApartsinProjects/CoEval/master/Runs/medium-benchmark/reports/student_report/index.html) | Per-student score breakdowns, task rankings, rubric factor heatmaps |
| [Judge Consistency](https://htmlpreview.github.io/?https://raw.githubusercontent.com/ApartsinProjects/CoEval/master/Runs/medium-benchmark/reports/judge_consistency/index.html) | Inter-judge ICC agreement, calibration drift, flagged uncertain items |
| [Robust Summary](https://htmlpreview.github.io/?https://raw.githubusercontent.com/ApartsinProjects/CoEval/master/Runs/medium-benchmark/reports/summary/index.html) | Final model rankings with confidence intervals and robust ensemble weights |
| [Score Distribution](https://htmlpreview.github.io/?https://raw.githubusercontent.com/ApartsinProjects/CoEval/master/Runs/medium-benchmark/reports/score_distribution/index.html) | High / Medium / Low histograms filterable by task, teacher, student, and judge |
| [Teacher Report](https://htmlpreview.github.io/?https://raw.githubusercontent.com/ApartsinProjects/CoEval/master/Runs/medium-benchmark/reports/teacher_report/index.html) | Per-teacher source quality, attribute stratum coverage, data consistency |
| [Interaction Matrix](https://htmlpreview.github.io/?https://raw.githubusercontent.com/ApartsinProjects/CoEval/master/Runs/medium-benchmark/reports/interaction_matrix/index.html) | Teacher × Student pair quality heatmap |
| [Coverage Summary](https://htmlpreview.github.io/?https://raw.githubusercontent.com/ApartsinProjects/CoEval/master/Runs/medium-benchmark/reports/coverage_summary/index.html) | Attribute Coverage Ratio (ACR) and rare-attribute recall per task |
| [Judge Report](https://htmlpreview.github.io/?https://raw.githubusercontent.com/ApartsinProjects/CoEval/master/Runs/medium-benchmark/reports/judge_report/index.html) | Judge-level bias rates, score calibration, inter-rater reliability |

---

## Frequently Asked Questions

**Q: How do I generate all reports at once after a run completes?**
A: Run `coeval analyze all --run ./eval_runs/my-experiment-v1 --out ./reports`. This generates all eight HTML reports plus the Excel workbook in the specified output directory. You can also call individual report types by replacing `all` with the report name (e.g., `student-report`, `judge-report`).

**Q: What reports does CoEval generate and what is each one for?**
A: CoEval generates eight HTML reports: `score-distribution` (judge score histograms), `teacher-report` (attribute coverage and data quality), `judge-report` (bias detection and calibration), `student-report` (per-model performance and rankings), `interaction-matrix` (teacher × student score heatmap), `judge-consistency` (inter-judge agreement and ICC), `coverage-summary` (attribute stratum coverage and surface bias), and `robust-summary` (outlier-robust rankings with confidence intervals). A `complete-report` Excel workbook is also available.

**Q: Is there a programmatic API to access metrics without generating HTML?**
A: Yes. Import `load_ees` from `analyzer.loader` and the metric functions from `analyzer.metrics` to work with the data directly in Python. For example, `composite_score_by_student(model)` returns a dict of mean normalized scores per student, and `judge_consistency(model)` returns ICC values per task. See the Programmatic API section above for a complete example.

**Q: Can I generate reports on a run that is still in progress?**
A: Yes. Pass `--partial-ok` to any `coeval analyze` or `python -m analyzer.main` command. All reports will render with a warning banner indicating the run is incomplete, and statistics are marked as preliminary.

**Q: What is the difference between Spearman rho and Kendall tau in the reports?**
A: Both are rank correlation metrics, but they measure slightly different things. Spearman rho measures the monotone agreement between two ranked lists (used to validate judge scores against benchmark ground-truth). Kendall tau measures pairwise concordance — the fraction of all pairs where two rankings agree on relative order. CoEval uses tau for student ranking comparisons and rho for benchmark validation.

**Q: How do I export results to Excel for stakeholder review?**
A: Run `coeval analyze complete-report --run ./eval_runs/my-experiment-v1 --out ./reports` or use `python -m analyzer.main --run-path <path> --format excel --out-file analysis.xlsx`. The workbook includes Summary, StudentScores, TeacherCoverage, JudgeAgreement, and FailedRecords sheets.

---

[← Benchmarks](07-benchmarks.md) · [Resume & Recovery →](09-recovery.md)
