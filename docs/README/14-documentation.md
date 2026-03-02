# Documentation

[← Testing](13-testing.md) · [Back to README →](../../README.md)

---

## Section-by-Section README

This folder (`docs/README/`) splits the project README into focused, standalone documents. Each section can be read independently.

| # | File | Contents |
|---|------|----------|
| 01 | [Why CoEval](01-why-coeval.md) | Problem space, solution table, target audience |
| 02 | [Features](02-features.md) | Complete feature catalogue across all five capability clusters |
| 03 | [Architecture](03-architecture.md) | Five-phase pipeline diagram, phase details, role assignment, storage layout |
| 04 | [Installation](04-installation.md) | Requirements, pip install, optional extras, provider SDKs |
| 05 | [Quick Start](05-quick-start.md) | Three paths to first run (cloud, benchmark, local GPU), typical workflow |
| 06 | [Configuration Guide](06-configuration.md) | Models, tasks, sampling, rubric, experiment settings, prompts, key file |
| 07 | [Supported Interfaces](07-interfaces.md) | All 15 interfaces with auth, batch support, and code examples |
| 08 | [CLI Reference](08-cli-reference.md) | All 11 subcommands with flag tables and exit codes |
| 09 | [Cost Planning](09-cost-control.md) | Pre-run estimation, Batch API, quotas, price table, reduction strategies |
| 10 | [Resume & Recovery](10-resume-recovery.md) | Checkpointing, `--continue`, `--resume`, repair workflow, decision tree |
| 11 | [Analytics & Reports](11-analytics-reports.md) | All 8 report types, key metrics, paper tables |
| 12 | [Repository Layout](12-repository-layout.md) | Annotated directory tree, key file index |
| 13 | [Testing](13-testing.md) | Running tests, coverage areas, CI setup |
| 14 | [Documentation](14-documentation.md) | This index |

---

## Full Documentation (`docs/`)

| Document | Contents |
|----------|----------|
| [docs/cli_reference.md](../cli_reference.md) | Complete flag reference for all 11 subcommands with examples |
| [docs/tutorial.md](../tutorial.md) | Step-by-step walkthrough from install to first published report |
| [docs/running_experiments.md](../running_experiments.md) | Production experiment workflow, batching strategies, cost tuning |
| [docs/extracting_benchmarks.md](../extracting_benchmarks.md) | Export Phase 3 data as a shareable benchmark; `coeval ingest`; reproducing published results |
| [docs/developer_guide.md](../developer_guide.md) | Adding new interfaces, phases, and report types; contributing guide |

---

## In-Depth Manuals (`manuals/`)

| Document | Contents |
|----------|----------|
| [manuals/01_running_experiments.md](../../manuals/01_running_experiments.md) | Quick reference: provider setup, phase modes, config patterns, cost estimation |
| [manuals/02_benchmark_experiments.md](../../manuals/02_benchmark_experiments.md) | Ingesting public datasets (XSum, CodeSearchNet, AESLC, WikiTableQuestions) as virtual teachers |
| [manuals/03_analysis_and_reporting.md](../../manuals/03_analysis_and_reporting.md) | Analysis pipeline, HTML reports, paper-quality result tables, Excel export |
| [manuals/04_provider_pricing.md](../../manuals/04_provider_pricing.md) | Pricing tables, batch discounts, `interface: auto` routing, provider comparison |

---

## Example Configurations

| File | Description |
|------|-------------|
| [examples/local_smoke_test.yaml](../../examples/local_smoke_test.yaml) | Minimal runnable config: 5 HuggingFace models, 2 tasks, no cloud APIs required |
| [benchmark/mixed.yaml](../../benchmark/mixed.yaml) | Real benchmark data + OpenAI models; full evaluation for ~$0.02 |
| [benchmark/education.yaml](../../benchmark/education.yaml) | Education benchmark: 3 real-dataset tasks + 10 synthetic tasks, 6 models |

---

## HTML Examples

All examples are self-contained HTML files — open locally in any browser (no server or internet required).

### Experiment Planning

| Example | Description |
|---------|-------------|
| [benchmark/education_description.html](../../benchmark/education_description.html) | Full experiment plan: 3 real-dataset tasks + 10 synthetic tasks, 6 models, per-phase call budget, cost table, and attribute maps |

> **Generate your own planning view:**
> ```bash
> coeval describe --config my_experiment.yaml --out my_experiment_plan.html
> ```

### Analysis Reports

| Report | Description |
|--------|-------------|
| [Student Performance Report](../../samples/analysis/coeval-demo-v2/coeval-demo-v2_student_report.html) | Per-student score breakdowns, task rankings, rubric factor heatmaps |
| [Judge Consistency Report](../../samples/analysis/coeval-demo-v2/coeval-demo-v2_judge_consistency.html) | Inter-judge ICC agreement, calibration drift, flagged uncertain items |
| [Robust Summary Report](../../samples/analysis/coeval-demo-v2/coeval-demo-v2_robust_summary.html) | Final model rankings with confidence intervals and robust ensemble weights |
| [Score Distribution Report](../../samples/analysis/coeval-demo-v2/coeval-demo-v2_score_distribution.html) | High / Medium / Low histograms filterable by task, teacher, student, and judge |
| [Teacher Report](../../samples/analysis/coeval-demo-v2/coeval-demo-v2_teacher_report.html) | Per-teacher source quality, attribute stratum coverage, data consistency |
| [Interaction Matrix](../../samples/analysis/coeval-demo-v2/coeval-demo-v2_interaction_matrix.html) | Teacher × Student pair quality heatmap — spot which combinations succeed or fail |
| [Coverage Summary](../../samples/analysis/coeval-demo-v2/coeval-demo-v2_coverage_summary.html) | Attribute Coverage Ratio (ACR) and rare-attribute recall per task |
| [Judge Report](../../samples/analysis/coeval-demo-v2/coeval-demo-v2_judge_report.html) | Judge-level bias rates, score calibration, inter-rater reliability |

> **Generate all reports from a completed run:**
> ```bash
> coeval analyze all --run ./eval_runs/my-experiment-v1 --out ./reports
> ```

---

## Analysis Package

| File | Contents |
|------|----------|
| [analysis/README.md](../../analysis/README.md) | Analysis package API reference and report gallery |

---

[← Testing](13-testing.md) · [Back to README →](../../README.md)
