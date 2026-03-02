# Documentation

[← Repository](12-repository.md) · [Back to README →](../../README.md)

---

## Section-by-Section Guide

This folder (`docs/README/`) splits the project README into 13 focused, standalone documents.

| # | File | Contents |
|---|------|----------|
| 01 | [Overview](01-overview.md) | Problem space, solution approach, target audience, feature catalogue |
| 02 | [Installation](02-installation.md) | Requirements, pip install, optional extras, provider SDKs |
| 03 | [Quick Start](03-quick-start.md) | Three paths to first run (cloud, benchmark, local GPU), typical workflow |
| 04 | [Configuration](04-configuration.md) | Models, tasks, sampling, rubric, experiment settings, prompts, multi-role params |
| 05 | [Providers & Pricing](05-providers.md) | All 15 interfaces with auth, batch support, code examples, pricing tables |
| 06 | [Running Experiments](06-running.md) | Phase modes, quotas, batch processing, cost estimation, resuming, use-case examples |
| 07 | [Benchmark Datasets](07-benchmarks.md) | Pre-ingested datasets, coeval ingest, benchmark teachers, reproducing results |
| 08 | [Analytics & Reports](08-reports.md) | All 11 report types, metrics, data model, programmatic API, paper tables |
| 09 | [Resume & Recovery](09-recovery.md) | Checkpointing, --continue, --resume, repair workflow, decision tree |
| 10 | [Architecture](10-architecture.md) | Five-phase pipeline, phase details, role assignment, storage layout |
| 11 | [Testing](11-testing.md) | Running tests, coverage areas, CI setup |
| 12 | [Repository Layout](12-repository.md) | Annotated directory tree, key file index |
| 13 | [Documentation](13-documentation.md) | This index |

---

## Full Documentation (`docs/`)

| Document | Contents |
|----------|----------|
| [docs/cli_reference.md](../cli_reference.md) | Complete flag reference for all 11 subcommands with examples |
| [docs/tutorial.md](../tutorial.md) | Step-by-step walkthrough from install to first published report |
| [docs/developer_guide.md](../developer_guide.md) | Adding new interfaces, phases, and report types; contributing guide |

---

## Example Configurations

| File | Description |
|------|-------------|
| [examples/local_smoke_test.yaml](../../examples/local_smoke_test.yaml) | Minimal runnable config: 5 HuggingFace models, 2 tasks, no cloud APIs required |
| [benchmark/mixed.yaml](../../benchmark/mixed.yaml) | Real benchmark data + OpenAI models; full evaluation for ~$0.03 |
| [benchmark/education.yaml](../../benchmark/education.yaml) | Education benchmark: 3 real-dataset tasks + 10 synthetic tasks, 6 models |
| [benchmark/medium_benchmark.yaml](../../benchmark/medium_benchmark.yaml) | Medium-scale benchmark: 5 models, 4 tasks, 20 items/task |
| [benchmark/paper_benchmarks.yaml](../../benchmark/paper_benchmarks.yaml) | Paper evaluation config: 8 students, 3 judges, all 4 benchmark tasks |
| [benchmark/paper_dual_track.yaml](../../benchmark/paper_dual_track.yaml) | Dual-track paper config: benchmark + generative teacher ablation |

---

## HTML Examples

All examples are self-contained HTML files — click to view rendered in browser.

> **Generate your own planning view:**
> ```bash
> coeval describe --config my_experiment.yaml --out my_experiment_plan.html
> ```

### Experiment Planning Views

| Example | Description |
|---------|-------------|
| [Education Benchmark Plan](https://htmlpreview.github.io/?https://raw.githubusercontent.com/ApartsinProjects/CoEval/master/benchmark/education_description.html) | Full experiment plan: 3 real-dataset tasks + 10 synthetic tasks, 6 models, per-phase call budget, cost table |
| [Mixed Benchmark Plan](https://htmlpreview.github.io/?https://raw.githubusercontent.com/ApartsinProjects/CoEval/master/benchmark/mixed_description.html) | Mixed benchmark plan: real benchmark datasets + OpenAI models |
| [Paper Dual-Track Plan](https://htmlpreview.github.io/?https://raw.githubusercontent.com/ApartsinProjects/CoEval/master/benchmark/paper_dual_track_description.html) | Paper evaluation: dual-track design with benchmark + generative teachers |

> **Generate all reports from a completed run:**
> ```bash
> coeval analyze all --run ./eval_runs/my-experiment-v1 --out ./reports
> ```

### Analysis Reports — coeval-demo-v2

| Report | Description |
|--------|-------------|
| [Student Report](https://htmlpreview.github.io/?https://raw.githubusercontent.com/ApartsinProjects/CoEval/master/samples/analysis/coeval-demo-v2/coeval-demo-v2_student_report.html) | Per-student score breakdowns, task rankings, rubric factor heatmaps |
| [Judge Consistency](https://htmlpreview.github.io/?https://raw.githubusercontent.com/ApartsinProjects/CoEval/master/samples/analysis/coeval-demo-v2/coeval-demo-v2_judge_consistency.html) | Inter-judge ICC agreement, calibration drift, flagged uncertain items |
| [Robust Summary](https://htmlpreview.github.io/?https://raw.githubusercontent.com/ApartsinProjects/CoEval/master/samples/analysis/coeval-demo-v2/coeval-demo-v2_robust_summary.html) | Final model rankings with confidence intervals and robust ensemble weights |
| [Score Distribution](https://htmlpreview.github.io/?https://raw.githubusercontent.com/ApartsinProjects/CoEval/master/samples/analysis/coeval-demo-v2/coeval-demo-v2_score_distribution.html) | High / Medium / Low histograms filterable by task, teacher, student, and judge |
| [Teacher Report](https://htmlpreview.github.io/?https://raw.githubusercontent.com/ApartsinProjects/CoEval/master/samples/analysis/coeval-demo-v2/coeval-demo-v2_teacher_report.html) | Per-teacher source quality, attribute stratum coverage, data consistency |
| [Interaction Matrix](https://htmlpreview.github.io/?https://raw.githubusercontent.com/ApartsinProjects/CoEval/master/samples/analysis/coeval-demo-v2/coeval-demo-v2_interaction_matrix.html) | Teacher × Student pair quality heatmap |
| [Coverage Summary](https://htmlpreview.github.io/?https://raw.githubusercontent.com/ApartsinProjects/CoEval/master/samples/analysis/coeval-demo-v2/coeval-demo-v2_coverage_summary.html) | Attribute Coverage Ratio (ACR) and rare-attribute recall per task |
| [Judge Report](https://htmlpreview.github.io/?https://raw.githubusercontent.com/ApartsinProjects/CoEval/master/samples/analysis/coeval-demo-v2/coeval-demo-v2_judge_report.html) | Judge-level bias rates, score calibration, inter-rater reliability |

### Analysis Reports — coeval-demo-v1

| Report | Description |
|--------|-------------|
| [Student Report](https://htmlpreview.github.io/?https://raw.githubusercontent.com/ApartsinProjects/CoEval/master/samples/analysis/coeval-demo-v1/coeval-demo-v1_student_report.html) | Per-student score breakdowns, task rankings, rubric factor heatmaps |
| [Judge Consistency](https://htmlpreview.github.io/?https://raw.githubusercontent.com/ApartsinProjects/CoEval/master/samples/analysis/coeval-demo-v1/coeval-demo-v1_judge_consistency.html) | Inter-judge ICC agreement, calibration drift, flagged uncertain items |
| [Robust Summary](https://htmlpreview.github.io/?https://raw.githubusercontent.com/ApartsinProjects/CoEval/master/samples/analysis/coeval-demo-v1/coeval-demo-v1_robust_summary.html) | Final model rankings with confidence intervals |
| [Score Distribution](https://htmlpreview.github.io/?https://raw.githubusercontent.com/ApartsinProjects/CoEval/master/samples/analysis/coeval-demo-v1/coeval-demo-v1_score_distribution.html) | Score histograms filterable by task, teacher, student, and judge |
| [Teacher Report](https://htmlpreview.github.io/?https://raw.githubusercontent.com/ApartsinProjects/CoEval/master/samples/analysis/coeval-demo-v1/coeval-demo-v1_teacher_report.html) | Per-teacher source quality and attribute stratum coverage |
| [Interaction Matrix](https://htmlpreview.github.io/?https://raw.githubusercontent.com/ApartsinProjects/CoEval/master/samples/analysis/coeval-demo-v1/coeval-demo-v1_interaction_matrix.html) | Teacher × Student pair quality heatmap |
| [Coverage Summary](https://htmlpreview.github.io/?https://raw.githubusercontent.com/ApartsinProjects/CoEval/master/samples/analysis/coeval-demo-v1/coeval-demo-v1_coverage_summary.html) | Attribute Coverage Ratio (ACR) and rare-attribute recall |
| [Judge Report](https://htmlpreview.github.io/?https://raw.githubusercontent.com/ApartsinProjects/CoEval/master/samples/analysis/coeval-demo-v1/coeval-demo-v1_judge_report.html) | Judge-level bias rates, score calibration, inter-rater reliability |

---

[← Repository](12-repository.md) · [Back to README →](../../README.md)
