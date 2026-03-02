# analysis/ — Evaluation Experiment Analyzer (EEA)

This package implements the **EEA pipeline** (`coeval analyze`): it reads a completed
(or in-progress) **Experiment Storage Set (EES)** produced by `coeval run` and generates
reports — Excel workbooks, interactive HTML pages, and filtered JSONL/Parquet exports.

---

## Package Contents

```
analysis/
├── loader.py           ← EES data loader: reads all 5 phase folders into EESDataModel
├── metrics.py          ← Computation engine: SPA/WPA/kappa agreement, teacher/student scores,
│                          robust filter (J*, T*, consistency threshold)
├── main.py             ← EEA dispatch: load once, route subcommand to report generator
│
├── reports/            ← One module per report type
│   ├── html_base.py    ← Shared HTML scaffold (Plotly, CSS, navigation)
│   ├── excel.py        ← complete-report (Excel workbook)
│   ├── coverage.py     ← coverage-summary (HTML)
│   ├── score_dist.py   ← score-distribution (HTML)
│   ├── teacher_report.py   ← teacher-report (HTML)
│   ├── judge_report.py     ← judge-report (HTML)
│   ├── student_report.py   ← student-report (HTML)
│   ├── interaction.py      ← interaction-matrix (HTML)
│   ├── consistency.py      ← judge-consistency (HTML)
│   ├── robust.py           ← robust-summary (HTML)
│   └── export_benchmark.py ← export-benchmark (JSONL / Parquet)
│
├── tests/              ← Unit tests (run with: python -m pytest analysis/tests/)
├── samples/            ← Sample EES fixtures for offline testing
└── docs/               ← Analysis user manual + COEVAL-SPEC-002
```

---

## Available Reports

| Subcommand | Output | What it shows |
|------------|--------|---------------|
| `complete-report` | Excel | All raw scores, attributes, model names — full audit trail |
| `coverage-summary` | HTML | Phase coverage per task/model, invalid record breakdown |
| `score-distribution` | HTML | Score histograms by rubric aspect, model, and attribute |
| `teacher-report` | HTML | Teacher differentiation scores — how varied each teacher's prompts are |
| `judge-report` | HTML | Judge agreement (SPA/WPA/kappa) and reliability across models |
| `student-report` | HTML | Student performance ranking across tasks and aspects |
| `interaction-matrix` | HTML | Heatmap: student scores cross-tabulated by teacher and student model |
| `judge-consistency` | HTML | Within-judge consistency: same prompt scored twice |
| `robust-summary` | HTML | Student ranking after robust filter (top-half judges + consistency threshold) |
| `export-benchmark` | JSONL/Parquet | High-quality datapoints that passed all robust filters |
| `all` | all above | All HTML reports + Excel + robust summary in one call |

---

## Key Classes

| Class | Module | Role |
|-------|--------|------|
| `EESDataModel` | `loader.py` | In-memory representation of one EES (phases 1–5 data, validity flags) |
| `RobustFilterResult` | `metrics.py` | Output of the robust filter: J*, T*, consistency-passing datapoints |
| `run_analyze` | `main.py` | Top-level dispatch: load EES, call the right report function |

---

## Robust Filtering

The robust filter selects a subset of high-confidence datapoints for the benchmark export:

1. **Judge selection (J\*)** — rank judges by agreement metric (SPA / WPA / kappa), keep top-half or all
2. **Teacher selection (T\*)** — rank teachers by differentiation score, keep best
3. **Consistency filter** — keep only datapoints where judges agree above threshold `theta`

```bash
coeval analyze export-benchmark \
    --run eval_runs/my-experiment \
    --out my-benchmark.jsonl \
    --judge-selection top_half \      # or: all
    --agreement-metric spa \          # or: wpa, kappa
    --agreement-threshold 0.8         # fraction of judges that must agree
```

---

## Quick Commands

```bash
# Generate all reports at once
coeval analyze all \
    --run eval_runs/my-experiment \
    --out eval_runs/my-experiment-reports/

# Single reports
coeval analyze student-report  --run eval_runs/my-experiment --out report.html
coeval analyze complete-report --run eval_runs/my-experiment --out report.xlsx

# Export benchmark dataset
coeval analyze export-benchmark \
    --run eval_runs/my-experiment \
    --out my-benchmark.jsonl

# Analyze an in-progress experiment (skip completeness warning)
coeval analyze student-report \
    --run eval_runs/my-experiment \
    --out report.html \
    --partial-ok

# Run tests
python -m pytest analysis/tests/ -v
```

---

## Documentation

| Document | Description |
|----------|-------------|
| `docs/running_analysis.md` | **User manual** — all subcommands, filtering options, output formats, FAQ |
| `docs/spec_phase2_claude.md` | **COEVAL-SPEC-002** — formal EEA specification |
| `samples/` | Sample EES folders for offline testing and report preview |
| `../../docs/developer_guide.md` | Full developer guide covering both EER and EEA |
