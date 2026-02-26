# CoEval — Running Analysis (EEA)

**CoEval** produces an **Experiment Storage Set (EES)** when you run `coeval run`.
The **Evaluation Experiment Analyzer (EEA)** reads that EES and produces reports:
interactive HTML dashboards, an Excel workbook, and optionally a filtered JSONL/Parquet
benchmark export.

---

## Table of Contents

1. [Concept of Operation](#1-concept-of-operation)
2. [Installation](#2-installation)
3. [Quick Start](#3-quick-start)
4. [CLI Reference](#4-cli-reference)
   - 4.1 [Common flags](#41-common-flags)
   - 4.2 [Subcommand list](#42-subcommand-list)
5. [Report Guide](#5-report-guide)
   - 5.1 [coverage-summary](#51-coverage-summary)
   - 5.2 [complete-report (Excel)](#52-complete-report-excel)
   - 5.3 [score-distribution](#53-score-distribution)
   - 5.4 [teacher-report](#54-teacher-report)
   - 5.5 [judge-report](#55-judge-report)
   - 5.6 [student-report](#56-student-report)
   - 5.7 [interaction-matrix](#57-interaction-matrix)
   - 5.8 [judge-consistency](#58-judge-consistency)
   - 5.9 [robust-summary](#59-robust-summary)
   - 5.10 [export-benchmark](#510-export-benchmark)
   - 5.11 [all](#511-all)
6. [Robust Filtering Options](#6-robust-filtering-options)
7. [Analyzing In-Progress Experiments](#7-analyzing-in-progress-experiments)
8. [Output File Format](#8-output-file-format)
9. [Use-Case Examples](#9-use-case-examples)
10. [Frequently Asked Questions](#10-frequently-asked-questions)

---

## 1. Concept of Operation

After `coeval run` completes (or even while it is in progress), `coeval analyze` reads
the EES folder and computes a set of metrics:

- **Agreement metrics** (SPA, WPA, Cohen's kappa) measure how consistently judges score the same datapoints.
- **Teacher differentiation score** measures how varied each teacher's generated prompts are.
- **Student score** is the mean normalized judge score per (student, task, rubric aspect).
- **Robust filter** selects a high-confidence subset of datapoints by keeping only the best judges (J\*), the best teachers (T\*), and only datapoints where J\* judges agree above a threshold.

All reports are generated from the same in-memory data model, loaded once per invocation.

---

## 2. Installation

```bash
pip install -e .                      # core; required for all reports
pip install -e ".[parquet]"           # required only for --benchmark-format parquet
```

Verify:

```bash
coeval analyze --help
```

---

## 3. Quick Start

```bash
# Generate all reports at once
coeval analyze all \
    --run eval_runs/my-experiment \
    --out eval_runs/my-experiment-reports/

# Open any HTML report in a browser
# (reports are self-contained — no server needed)
open eval_runs/my-experiment-reports/student_report/index.html

# Generate a single report
coeval analyze student-report \
    --run eval_runs/my-experiment \
    --out eval_runs/student-report.html

# Export filtered benchmark dataset
coeval analyze export-benchmark \
    --run eval_runs/my-experiment \
    --out eval_runs/my-benchmark.jsonl
```

---

## 4. CLI Reference

### 4.1 Common flags

All `coeval analyze <subcommand>` invocations accept these flags:

| Flag | Required | Default | Description |
|------|----------|---------|-------------|
| `--run PATH` | yes | — | Path to the EES experiment folder |
| `--out PATH` | yes | — | Output path (file for Excel/JSONL; folder for HTML/`all`) |
| `--partial-ok` | no | false | Suppress the warning when analyzing an in-progress experiment |
| `--log-level LEVEL` | no | `INFO` | `DEBUG`, `INFO`, `WARNING`, `ERROR` |

### 4.2 Subcommand list

| Subcommand | Output type | Description |
|------------|-------------|-------------|
| `coverage-summary` | HTML folder | Phase coverage and error breakdown |
| `complete-report` | `.xlsx` file | Full tabular data (all scores, attributes, models) |
| `score-distribution` | HTML folder | Score distributions by aspect, model, attribute |
| `teacher-report` | HTML folder | Teacher differentiation quality |
| `judge-report` | HTML folder | Judge agreement and reliability |
| `student-report` | HTML folder | Student model performance |
| `interaction-matrix` | HTML folder | Teacher–student score heatmap |
| `judge-consistency` | HTML folder | Within-judge consistency |
| `robust-summary` | HTML folder | Filtered student ranking (uses robust options) |
| `export-benchmark` | `.jsonl` or `.parquet` | Robust datapoint export (uses robust options) |
| `all` | mixed | All of the above in one command |

---

## 5. Report Guide

### 5.1 coverage-summary

Shows what fraction of the expected EES data has been collected:

- Per-task, per-model phase coverage (phases 3–5)
- Breakdown of invalid evaluation records (parse errors, missing fields)
- Useful to run **first** to catch data quality issues before reviewing scores

```bash
coeval analyze coverage-summary \
    --run eval_runs/my-experiment \
    --out eval_runs/coverage.html
```

### 5.2 complete-report (Excel)

Dumps all raw data to a multi-sheet Excel workbook:

- **Evaluations** sheet: every score record (task, teacher, student, judge, rubric factors, attributes)
- **Responses** sheet: every student response
- **Datapoints** sheet: every teacher-generated (prompt, reference_response) pair
- Best viewed in Excel or LibreOffice Calc for filtering and pivot analysis

```bash
coeval analyze complete-report \
    --run eval_runs/my-experiment \
    --out eval_runs/report.xlsx
```

### 5.3 score-distribution

Interactive histogram dashboard showing score distributions sliced by:

- Rubric aspect (e.g. `accuracy`, `conciseness`)
- Student model
- Teacher model
- Attribute value (e.g. `tone=formal`)

```bash
coeval analyze score-distribution \
    --run eval_runs/my-experiment \
    --out eval_runs/score-dist.html
```

### 5.4 teacher-report

Shows **teacher differentiation quality** — how much variety each teacher's generated
prompts introduce across attribute values.  A high differentiation score means the teacher
reliably produces distinct prompts for distinct attribute combinations.

```bash
coeval analyze teacher-report \
    --run eval_runs/my-experiment \
    --out eval_runs/teacher-report.html
```

### 5.5 judge-report

Shows **judge reliability and agreement**:

- Per-judge agreement scores (SPA, WPA, kappa) across all judge pairs
- Inter-judge agreement matrix
- Useful for identifying judges that deviate from consensus

```bash
coeval analyze judge-report \
    --run eval_runs/my-experiment \
    --out eval_runs/judge-report.html
```

### 5.6 student-report

Shows **student model performance** across tasks, rubric aspects, and attribute values:

- Per-student mean score by task and aspect
- Score breakdown by attribute value (e.g. how does each student do on `tone=formal` vs `tone=casual`?)
- Student ranking table

```bash
coeval analyze student-report \
    --run eval_runs/my-experiment \
    --out eval_runs/student-report.html
```

### 5.7 interaction-matrix

Heatmap showing how student score depends on **which teacher generated the prompt**.
A high teacher–student interaction means some teachers systematically advantage or
disadvantage specific students.

```bash
coeval analyze interaction-matrix \
    --run eval_runs/my-experiment \
    --out eval_runs/interaction.html
```

### 5.8 judge-consistency

Measures **within-judge consistency**: how reproducibly a single judge scores the same
(prompt, response) pair when it appears more than once (e.g. across different datapoints
with the same content).

```bash
coeval analyze judge-consistency \
    --run eval_runs/my-experiment \
    --out eval_runs/judge-consistency.html
```

### 5.9 robust-summary

Student ranking computed after the **robust filter** (see §6) has been applied.
Only datapoints from the best judges (J\*) and best teachers (T\*) are included,
and only where those judges agree above the consistency threshold.

```bash
coeval analyze robust-summary \
    --run eval_runs/my-experiment \
    --out eval_runs/robust-summary.html \
    --judge-selection top_half \
    --agreement-metric spa \
    --agreement-threshold 0.8
```

### 5.10 export-benchmark

Exports robust-filtered datapoints as a JSONL or Parquet file for downstream use
(fine-tuning, leaderboard submission, dataset creation).

```bash
# JSONL (default)
coeval analyze export-benchmark \
    --run eval_runs/my-experiment \
    --out my-benchmark.jsonl \
    --judge-selection top_half \
    --agreement-metric spa \
    --agreement-threshold 0.8

# Parquet (requires pip install -e ".[parquet]")
coeval analyze export-benchmark \
    --run eval_runs/my-experiment \
    --out my-benchmark.parquet \
    --benchmark-format parquet
```

Each exported record contains: `task`, `teacher`, `prompt`, `reference_response`,
`student`, `student_response`, aggregated `score`, rubric `aspects`, and `attributes`.

### 5.11 all

Runs every report in one invocation.  The `--out` path must be a folder; each report
is written to a named sub-folder.

```bash
coeval analyze all \
    --run eval_runs/my-experiment \
    --out eval_runs/reports/ \
    --judge-selection top_half \
    --agreement-metric spa \
    --agreement-threshold 0.8
```

Output layout:

```
reports/
├── complete_report.xlsx
├── coverage_summary/index.html
├── score_distribution/index.html
├── teacher_report/index.html
├── judge_report/index.html
├── student_report/index.html
├── interaction_matrix/index.html
├── judge_consistency/index.html
└── robust_summary/index.html
```

---

## 6. Robust Filtering Options

The `robust-summary`, `export-benchmark`, and `all` subcommands accept these options:

| Flag | Default | Choices | Description |
|------|---------|---------|-------------|
| `--judge-selection` | `top_half` | `top_half`, `all` | Keep top-half of judges by agreement score, or keep all |
| `--agreement-metric` | `spa` | `spa`, `wpa`, `kappa` | Agreement metric used to rank judges |
| `--agreement-threshold` | `1.0` | any float 0–1 | Minimum fraction of J\* judges that must agree on a score |
| `--teacher-score-formula` | `v1` | `v1`, `s2`, `r3` | Formula for ranking teacher models |

### Agreement metrics

| Metric | Description |
|--------|-------------|
| `spa` | Simple Pairwise Agreement — fraction of judge pairs with identical scores |
| `wpa` | Weighted Pairwise Agreement — like SPA but weights near-misses |
| `kappa` | Cohen's kappa — corrects SPA for chance agreement |

### When the filter returns 0 datapoints

Lower `--agreement-threshold` (try `0.7` or `0.5`), or use `--judge-selection all`
to include all judges in J\*.  The console output will print diagnostics showing
how many datapoints were lost at each filtering step.

---

## 7. Analyzing In-Progress Experiments

You can analyze an experiment while `coeval run` is still running:

```bash
coeval analyze coverage-summary \
    --run eval_runs/my-experiment \
    --out eval_runs/partial-coverage.html \
    --partial-ok
```

Without `--partial-ok`, a warning is printed if `metadata.json` shows
`status: "in_progress"`.  Reports will reflect only the data that exists at
analysis time.

---

## 8. Output File Format

### HTML reports

Each HTML report is a **self-contained folder** with one `index.html` that embeds:
- All data as inline JSON (no server required)
- Plotly.js charts (cached to `~/.cache/coeval/plotly/` on first run)
- Interactive filters (dropdowns, sliders, model selectors)

Open `index.html` directly in any modern browser.

### Excel workbook

Multi-sheet `.xlsx` file produced by `openpyxl`.  Compatible with Excel 2016+,
LibreOffice Calc, and Google Sheets (upload).

### JSONL export

One JSON object per line.  Each object has these keys:

```json
{
  "task": "text_summary",
  "teacher": "gpt-4o-mini",
  "prompt": "Summarise the following passage...",
  "reference_response": "Neural networks learn by adjusting weights...",
  "attributes": {"tone": "formal", "domain": "technology"},
  "student": "smollm2-360m",
  "student_response": "Neural nets adjust weights to learn.",
  "score": 0.75,
  "aspects": {"accuracy": 0.8, "conciseness": 0.7}
}
```

### Parquet export

Same schema as JSONL, stored in Apache Parquet format.
Requires `pip install -e ".[parquet]"` (pyarrow ≥ 14.0).

---

## 9. Use-Case Examples

### 9.1 First analysis after a completed run

```bash
coeval analyze all \
    --run eval_runs/my-experiment \
    --out eval_runs/reports/
```

### 9.2 Quick student ranking without generating all reports

```bash
coeval analyze student-report \
    --run eval_runs/my-experiment \
    --out eval_runs/student.html
```

### 9.3 Iterating on robust filter settings

```bash
# Try three threshold values, compare robust_summary reports
for T in 0.6 0.8 1.0; do
    coeval analyze robust-summary \
        --run eval_runs/my-experiment \
        --out eval_runs/robust-t${T}/index.html \
        --agreement-threshold $T
done
```

### 9.4 Exporting a clean benchmark in Parquet format

```bash
pip install -e ".[parquet]"

coeval analyze export-benchmark \
    --run eval_runs/my-experiment \
    --out datasets/my-benchmark.parquet \
    --benchmark-format parquet \
    --judge-selection top_half \
    --agreement-metric kappa \
    --agreement-threshold 0.75
```

### 9.5 Monitoring an in-progress run

```bash
# Poll every 60 seconds while the experiment is running
watch -n 60 "coeval analyze coverage-summary \
    --run eval_runs/my-experiment \
    --out /tmp/live-coverage.html \
    --partial-ok && echo 'coverage refreshed'"
```

### 9.6 Using sample data for offline testing

```bash
# Run any report against the bundled sample EES
coeval analyze all \
    --run analysis/samples/run-coeval-demo-v2 \
    --out /tmp/demo-reports/
```

---

## 10. Frequently Asked Questions

**Q: Do I need an internet connection to open HTML reports?**
No. All reports are self-contained. Plotly.js is downloaded once and cached in
`~/.cache/coeval/plotly/`. Subsequent runs use the cached copy.

**Q: Can I analyze an experiment that only partially completed?**
Yes — use `--partial-ok`. Reports will reflect only the data that exists.
`coverage-summary` is the most useful report to run first in this case.

**Q: The robust filter returned 0 datapoints. What should I do?**
Lower `--agreement-threshold` (try 0.8, then 0.6), or use `--judge-selection all`.
Check the console output — it prints step-by-step diagnostics.

**Q: What is the difference between `spa` and `wpa`?**
SPA counts judge pairs that agree exactly. WPA gives partial credit when two judges
differ by only one point (e.g. 3 vs 4 on a 1–5 scale). Use `wpa` when rubric scores
are ordinal and near-agreement matters.

**Q: How do I compare two experiments?**
Cross-experiment comparison is not built into `coeval analyze` (single-experiment
scope per invocation). Use the Excel export from each experiment and combine manually,
or load both JSONL exports into a Jupyter notebook.

**Q: Can I add custom report types?**
Yes — add a new module to `analysis/reports/`, implement a `write_<report>()` function
with the same signature as the existing reports, register it in `analysis/main.py`
and the CLI in `experiments/cli.py`.  See `docs/developer_guide.md §8` for the
pattern.

**Q: Where is the Plotly.js cache stored?**
`~/.cache/coeval/plotly/plotly.min.js`.  Delete it to force a fresh download.

**Q: My report looks empty. Why?**
Run `coverage-summary` first — it will show which phase files are present and which
evaluation records are invalid.  If Phase 5 has 0 valid records, no report will have
meaningful data.
