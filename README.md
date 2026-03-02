# CoEval: A fine-grained LLM benchmarking and ranking framework powered by self-evaluating ensembles.

[![Python ≥3.10](https://img.shields.io/badge/python-%E2%89%A53.10-blue?logo=python&logoColor=white)](https://www.python.org/)
[![Version 0.3.0](https://img.shields.io/badge/version-0.3.0-informational)](CHANGELOG.md)
[![Tests 557 passing](https://img.shields.io/badge/tests-557%20passing-brightgreen)](docs/README/11-testing.md)
[![Interfaces 16+](https://img.shields.io/badge/interfaces-16%2B-orange)](docs/README/05-providers.md)
[![License MIT](https://img.shields.io/badge/license-MIT-lightgrey)](LICENSE)

<p align="center">
  <img src="docs/coeval_banner.jpg" alt="CoEval — Teacher · Student · Judge evaluation ensemble" width="860"/>
</p>

---

## Introduction

The need: Comparing off-the-shelf and fine-tuned models is hard. Public benchmarks rarely match a specific use case in data or metrics, and building a dedicated benchmark is often too costly. Running evaluations across many variants is also operationally heavy, and results can be skewed by benchmark leakage when test data (or near-duplicates) leaks into training or fine-tuning.

CoEval is a framework for self-evaluation of LLMs using model ensembles. In each run, state-of-the-art models jointly serve as teachers (generating questions and reference answers), students (the candidate models being compared), and judges (scoring student outputs against the reference).

Teachers use attribute-driven prompt generation to produce realistic, diverse test items from a user-defined or auto-generated space of targets and nuanced attributes. Judges apply rich scoring rubrics (user-specified, auto-generated, or mixed) to evaluate answers and produce comparable rankings across models.

Ranking reliability is improved by automatically weighting (or selecting) a robust subset of teachers that best differentiates students and a robust subset of judges that most consistently agree with the ensemble majority.

CoEval supports both local and remote models, with connectors for OpenAI, Hugging Face, Azure, AWS Bedrock, Anthropic, Ollama, and others, plus cost-aware experiment planning and batch inference where providers support it. Results and run plans are delivered as rich HTML reports for efficient control over definitions, costs, and outcomes, and the system includes documentation for both users and developers.

---

## Quick Start

```bash
# 1. Install
pip install coeval

# 2. Add your API keys  (see: docs/tutorial.md § 2)
cp keys.yaml.template keys.yaml   # then fill in your provider keys

# 3. Probe all models — no tokens consumed
coeval probe --config benchmark/mixed.yaml

# 4. Estimate cost before spending anything
coeval plan --config benchmark/mixed.yaml

# 5. Run the experiment
coeval run --config benchmark/mixed.yaml --continue

# 6. Generate analysis reports
coeval analyze all --run ./eval_runs/mixed-benchmark --out ./reports
```

### Minimal experiment config

```yaml
models:
  - name: gpt-4o-mini
    interface: openai
    parameters: { model: gpt-4o-mini, temperature: 0.7, max_tokens: 512 }
    roles: [teacher, student, judge]

tasks:
  - name: text_sentiment
    description: Classify the sentiment of a short customer review.
    output_description: A single word — either Positive or Negative.
    target_attributes:
      sentiment: [positive, negative]
      intensity:  [mild, strong]
    sampling: { target: [1,1], nuance: [0,1], total: 20 }
    rubric:
      accuracy: "The label matches the actual sentiment of the review."
    evaluation_mode: single

experiment:
  id: sentiment-v1
  storage_folder: ./eval_runs
```

---

## Examples

Interactive HTML examples — click to open rendered in browser:

### Experiment Planning

| Example | Description |
|---------|-------------|
| [Education Benchmark — Planning View](https://htmlpreview.github.io/?https://raw.githubusercontent.com/ApartsinProjects/CoEval/master/benchmark/education_description.html) | Full experiment plan: 3 real-dataset tasks + 10 synthetic tasks, 6 models, per-phase call budget, cost table, and attribute maps |
| [Mixed Benchmark — Planning View](https://htmlpreview.github.io/?https://raw.githubusercontent.com/ApartsinProjects/CoEval/master/benchmark/mixed_description.html) | Mixed benchmark plan: real benchmark datasets + OpenAI models |
| [Paper Dual-Track — Planning View](https://htmlpreview.github.io/?https://raw.githubusercontent.com/ApartsinProjects/CoEval/master/benchmark/paper_dual_track_description.html) | Paper evaluation: dual-track design with benchmark + generative teachers |

> **Generate your own planning view:**
> ```bash
> coeval describe --config my_experiment.yaml --out my_experiment_plan.html
> ```

### Analysis Reports

| Report | Description |
|--------|-------------|
| [Student Performance Report](https://htmlpreview.github.io/?https://raw.githubusercontent.com/ApartsinProjects/CoEval/master/samples/analysis/coeval-demo-v2/coeval-demo-v2_student_report.html) | Per-student score breakdowns, task rankings, rubric factor heatmaps |
| [Judge Consistency Report](https://htmlpreview.github.io/?https://raw.githubusercontent.com/ApartsinProjects/CoEval/master/samples/analysis/coeval-demo-v2/coeval-demo-v2_judge_consistency.html) | Inter-judge ICC agreement, calibration drift, flagged uncertain items |
| [Robust Summary Report](https://htmlpreview.github.io/?https://raw.githubusercontent.com/ApartsinProjects/CoEval/master/samples/analysis/coeval-demo-v2/coeval-demo-v2_robust_summary.html) | Final model rankings with confidence intervals and robust ensemble weights |
| [Score Distribution Report](https://htmlpreview.github.io/?https://raw.githubusercontent.com/ApartsinProjects/CoEval/master/samples/analysis/coeval-demo-v2/coeval-demo-v2_score_distribution.html) | High / Medium / Low histograms filterable by task, teacher, student, and judge |
| [Teacher Report](https://htmlpreview.github.io/?https://raw.githubusercontent.com/ApartsinProjects/CoEval/master/samples/analysis/coeval-demo-v2/coeval-demo-v2_teacher_report.html) | Per-teacher source quality, attribute stratum coverage, data consistency |
| [Interaction Matrix](https://htmlpreview.github.io/?https://raw.githubusercontent.com/ApartsinProjects/CoEval/master/samples/analysis/coeval-demo-v2/coeval-demo-v2_interaction_matrix.html) | Teacher × Student pair quality heatmap — spot which combinations succeed or fail |
| [Coverage Summary](https://htmlpreview.github.io/?https://raw.githubusercontent.com/ApartsinProjects/CoEval/master/samples/analysis/coeval-demo-v2/coeval-demo-v2_coverage_summary.html) | Attribute Coverage Ratio (ACR) and rare-attribute recall per task |
| [Judge Report](https://htmlpreview.github.io/?https://raw.githubusercontent.com/ApartsinProjects/CoEval/master/samples/analysis/coeval-demo-v2/coeval-demo-v2_judge_report.html) | Judge-level bias rates, score calibration, inter-rater reliability |

> **Generate all reports from a completed run:**
> ```bash
> coeval analyze all --run ./eval_runs/my-experiment-v1 --out ./reports
> ```

---

## Related documents

| Guide | What it covers |
|-------|----------------|
| [Evaluation Experiment Planning and Preparation Guide](docs/tutorial.md) | End-to-end walkthrough: installation, config design, probing, running, analysis, and benchmark export |
| [Command Line Option Reference](docs/cli_reference.md) | Every `coeval` subcommand, flag, and exit code — `run`, `probe`, `plan`, `generate`, `status`, `models`, `analyze`, `describe`, `wizard`, `ingest`, `repair` |
| [Running Experiments](docs/README/06-running.md) | Phase modes, `--continue`, batch API, quota control, cost estimation, fault recovery, use-case examples |
| [Providers & Pricing](docs/README/05-providers.md) | All 15 interfaces with auth, batch support, code examples, and pricing tables |
| [Analytics & Reports](docs/README/08-reports.md) | 11 interactive HTML dashboards, paper-quality result tables, programmatic API, Excel workbook export |
| [Configuration Guide](docs/README/04-configuration.md) | YAML config schema: models, tasks, attributes, rubric, sampling, prompt overrides, experiment settings |
| [Benchmark Datasets](docs/README/07-benchmarks.md) | Pre-ingested datasets, `coeval ingest`, `interface: benchmark` virtual teacher, reproducing published results |

---

## Pipeline at a Glance

```
YAML Config  →  Phase 1: Attribute Mapping   (teachers infer task dimensions)
             →  Phase 2: Rubric Mapping       (teachers build evaluation criteria)
             →  Phase 3: Data Generation      (teachers produce benchmark items)
             →  Phase 4: Response Collection  (students answer benchmark prompts)
             →  Phase 5: Evaluation           (judges score student responses)
             →  coeval analyze all            (8 HTML reports + Excel workbook)
```

### 16 Model Interfaces

| Cloud — Async Batch ✅ | Cloud — Real-time | OpenAI-Compatible | Local / Virtual |
|:---:|:---:|:---:|:---:|
| `openai` | `azure_openai`¹ | `groq` | `huggingface` |
| `anthropic` | `azure_ai` | `deepseek` | `ollama` |
| `gemini`² | `bedrock` | `mistral` | `benchmark` |
| | `vertex` | `deepinfra` | |
| | `openrouter` | `cerebras` | |

> ¹ `azure_openai` supports Azure Global Batch API (50% discount) — enable via `batch: azure_openai:` in config.
> ² `gemini` uses concurrent requests (pseudo-batch) — no async discount.

### Key Capabilities

| Capability | Detail |
|-----------|--------|
| **Cost estimation** | Itemised call budget and cost table before any phases run; Batch API discounts modelled |
| **Batch API** | 50% async discount for OpenAI, Anthropic, and Azure OpenAI; Gemini uses concurrent mode (no discount) |
| **Resume** | `--continue` resumes at exact JSONL record; no duplicate API calls |
| **Auto attributes** | Teachers infer task dimensions from a description; no hand-labelling required |
| **Auto rubric** | Teachers propose rubric factors; merge-and-deduplicate across N teachers |
| **Multi-judge ensemble** | N judges → bias-resistant aggregate scores; outlier judges down-weighted |
| **8 HTML reports** | Interactive charts, filterable tables, CSV export, fully self-contained (no CDN) |
| **Model probe** | Verify all 16 interfaces are reachable before spending a dollar |
| **Virtual teachers** | Pre-ingested public datasets supply zero-cost Phase 3 ground truth |
| **Label accuracy** | Judge-free exact-match for classification tasks (`label_attributes`) |

---

<div align="center">

**CoEval** · Multi-Model LLM Evaluation Framework · MIT License

*Built for LLM developers, integrators, and evaluation practitioners who demand reproducibility, cost predictability, and model-agnostic rigor.*

</div>
