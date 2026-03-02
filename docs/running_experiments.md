# CoEval — Operational Guide: Running, Monitoring, and Recovering Experiments

**CoEval** is a self-evaluating LLM ensemble benchmarking system. A fleet of language
models plays three roles: **teachers** generate evaluation datasets, **students** answer
the test prompts, and **judges** score each student response. All three roles may be
filled by the same model or by completely different ones. CoEval supports 15 provider
interfaces; credentials are resolved from a key file or environment variables.

| Role    | Responsibility |
|---------|----------------|
| teacher | Generates benchmark datapoints (Phase 3) and maps attributes/rubrics (Phases 1–2) |
| student | Responds to the prompt from each datapoint (Phase 4) |
| judge   | Evaluates student responses against the rubric (Phase 5) |

**Attribute system:** *target_attributes* are axes that affect the expected output (e.g.
`tone`, `urgency`); *nuanced_attributes* vary the input surface without changing the
correct answer (e.g. domain, register). Both can be static or auto-generated at runtime.

> Installation guide: [docs/README/04-installation.md](README/04-installation.md)

---

## Table of Contents

1. [Quick Start](#1-quick-start)
2. [Phase Modes](#2-phase-modes)
3. [Quota Control](#3-quota-control)
4. [Batch Processing](#4-batch-processing)
5. [Model Probe](#5-model-probe)
6. [Cost and Time Estimation](#6-cost-and-time-estimation)
7. [Use-Case Examples](#7-use-case-examples)
8. [Further Reading](#8-further-reading)

---

## 1. Quick Start

```bash
coeval run --config examples/local_smoke_test.yaml --dry-run   # validate only, no LLM calls
coeval run --config examples/local_smoke_test.yaml             # full run
```

Subcommands: `run`, `probe`, `plan`, `status`, `generate`, `models`, `analyze`, `describe`.

---

## 2. Phase Modes

CoEval runs a 5-phase pipeline: `attribute_mapping` → `rubric_mapping` →
`data_generation` → `response_collection` → `evaluation`. Each phase can run in one of
four modes set under `experiment.phases` or inherited via `resume_from`.

| Mode | Behaviour |
|------|-----------|
| **New** | Discard any existing artifact and regenerate from scratch |
| **Keep** | Skip this phase entirely if the artifact already exists |
| **Extend** | Generate only *missing* items up to `sampling.total`; never re-generates stored items |
| **Model** | Skip a (task, model) pair if its JSONL already exists; regenerate only absent pairs |

`Model` mode is not allowed for Phases 1–2. `rubric: extend` requires `resume_from`.

Typical resume configuration:

```yaml
experiment:
  id: summarise-v2
  storage_folder: ./eval_runs
  resume_from: summarise-v1      # copies Phase 1–2 artifacts from a prior run

  phases:
    attribute_mapping:   Keep
    rubric_mapping:      Keep
    data_generation:     Keep
    response_collection: Extend  # generates only missing responses
    evaluation:          Extend  # evaluates only missing responses
```

---

## 3. Quota Control

Add a `quota` block under `experiment` to cap the total LLM calls any model may make:

```yaml
experiment:
  quota:
    expensive-gpt4:
      max_calls: 50
    local-model:
      max_calls: 200
```

When a quota is exhausted, CoEval skips that model's remaining work and logs a warning;
other models continue unaffected. Models not listed in `quota` have no limit.

---

## 4. Batch Processing

For large experiments, CoEval can submit LLM requests as batch jobs rather than
individual real-time calls. Batch APIs offer up to 50% cost savings but have higher
latency (results returned within 24 hours, typically 1–4 hours). CoEval polls
automatically and resumes the pipeline when results are available.

| Interface      | Batch mechanism                           | Pricing discount |
|----------------|-------------------------------------------|-----------------|
| `openai`       | OpenAI Batch API                          | 50% per-token   |
| `anthropic`    | Anthropic Message Batches API             | 50% per-token   |
| `azure_openai` | Azure OpenAI Batch API                    | 50% per-token   |
| `gemini`       | Pseudo-batch (paced real-time calls)      | No discount     |
| `huggingface`  | Not supported                             | —               |

Enable batch processing per phase in the config:

```yaml
experiment:
  batch:
    phases: [3, 4, 5]    # which phases to run in batch mode (default: none)
```

Or set `batch_enabled: true` / `batch_enabled: false` on individual model entries to mix
batch and real-time models in the same experiment.

---

## 5. Model Probe

Before the pipeline starts, CoEval tests every model for availability using lightweight
API calls that do not consume generation tokens. Configure via `experiment.probe_mode`
or the `--probe` CLI flag.

```yaml
experiment:
  probe_mode: resume     # full | resume | disable
  probe_on_fail: warn    # abort (default) | warn
```

| Mode      | Behaviour                                                                      |
|-----------|--------------------------------------------------------------------------------|
| `full`    | Probe every model in the config (default)                                      |
| `resume`  | Probe only models needed for phases that have not yet completed                |
| `disable` | Skip the probe entirely                                                        |

`abort` (default) halts the pipeline if any model is unreachable; `warn` logs and
continues. On completion, `probe_results.json` is written to the experiment folder.

```bash
coeval run   --config my.yaml --probe resume --probe-on-fail warn  # embedded in a run
coeval run   --config my.yaml --probe disable
coeval probe --config my.yaml                     # standalone — no pipeline phases started
coeval probe --config my.yaml --probe resume
coeval probe --config my.yaml --probe-on-fail warn
```

---

## 6. Cost and Time Estimation

The cost estimator runs sample API calls per model, measures latency and token
throughput, and extrapolates to the full experiment size. Batch discounts (50% for
`openai`, `anthropic`, and `azure_openai`) are reflected automatically.

Mental formula for LLM call counts:
- Phase 3: `n_teachers × sampling.total` per task
- Phase 4: `n_teachers × n_students × sampling.total` per task
- Phase 5 (`single`): `n_teachers × n_judges × n_students × sampling.total` per task
- Phase 5 (`per_factor`): Phase 5 (single) × number of rubric factors

```bash
# Standalone planning (no experiment folder needed):
coeval plan --config my.yaml --estimate-samples 0   # heuristics only, no LLM calls
coeval plan --config my.yaml --estimate-samples 3   # 3 sample calls per model
coeval plan --config my.yaml --continue             # estimate remaining work only

# Inline — prints table + writes cost_estimate.json, then exits:
coeval run --config my.yaml --estimate-only --estimate-samples 0
coeval run --config my.yaml --estimate-only --continue
```

---

## 7. Use-Case Examples

### 7.1 First run — everything from scratch

All phases run in `New` mode by default (no `resume_from`, no `phases` overrides needed).

```yaml
models:
  - name: gpt4o
    interface: openai
    parameters:
      model: gpt-4o
    roles: [teacher, student, judge]

tasks:
  - name: summarise
    description: >
      Summarise a news article in 2-3 sentences.
    output_description: >
      A 2-3 sentence summary that preserves the key facts.
    target_attributes:
      length:    [short, medium]
      formality: [neutral, formal]
    nuanced_attributes:
      domain: [politics, technology, sports]
    sampling:
      target: [1, 2]
      nuance: [1, 1]
      total: 10
    rubric:
      accuracy:   "Summary accurately reflects the article's main facts."
      brevity:    "Summary uses no more words than necessary."
    evaluation_mode: single

experiment:
  id: summarise-v1
  storage_folder: ./eval_runs
  log_level: INFO
```

```bash
coeval run --config summarise-v1.yaml
```

---

### 7.2 Resume an interrupted run

Use `--continue` to restart an interrupted run in-place without changing the experiment ID:

```bash
coeval run --config my.yaml --continue
```

CoEval reads `phases_completed` from `meta.json`, applies `Keep` to Phases 1–2 and
`Extend` to Phases 3–5. To use a new experiment ID instead:

```yaml
experiment:
  id: summarise-v2
  storage_folder: ./eval_runs
  resume_from: summarise-v1

  phases:
    attribute_mapping:   Keep
    rubric_mapping:      Keep
    data_generation:     Keep
    response_collection: Extend
    evaluation:          Extend
```

```bash
coeval run --config summarise-v2.yaml
```

---

### 7.3 Add a new student model to a finished experiment

Run only Phases 4–5 for a new student without regenerating anything else. `Model` mode
creates JSONL only for model/task pairs that do not yet exist:

```yaml
models:
  - name: gpt4o
    interface: openai
    parameters: {model: gpt-4o}
    roles: [teacher, judge]     # no longer a student

  - name: llama3-8b
    interface: openai
    parameters: {model: meta-llama/llama-3-8b-instruct}
    roles: [student]            # the new student

experiment:
  id: summarise-v5
  storage_folder: ./eval_runs
  resume_from: summarise-v1

  phases:
    attribute_mapping:   Keep
    rubric_mapping:      Keep
    data_generation:     Keep
    response_collection: Model  # skips pairs whose JSONL already exists; runs llama3-8b
    evaluation:          Model
```

---

### 7.4 Dry-run / config check

Validate the config and print the execution plan without making any LLM calls:

```bash
coeval run --config my-experiment.yaml --dry-run
```

Output: model list with roles/interfaces, task sampling settings, per-phase mode, and
estimated LLM call counts per task and in total.

---

## 8. Further Reading

| Topic | Document |
|-------|----------|
| Full YAML config schema | [docs/README/06-configuration.md](README/06-configuration.md) |
| All CLI flags and exit codes | [docs/cli_reference.md](cli_reference.md) |
| Resume, recovery & repair in depth | [docs/README/10-resume-recovery.md](README/10-resume-recovery.md) |
| Benchmark datasets as teacher source | [manuals/02_benchmark_experiments.md](../manuals/02_benchmark_experiments.md) |
| Analysis reports | [docs/README/11-analytics-reports.md](README/11-analytics-reports.md) |
| Installation guide | [docs/README/04-installation.md](README/04-installation.md) |

**Experiment planning HTML example:** [`benchmark/education_description.html`](../benchmark/education_description.html) — open locally to see a real planning view.

**Analysis report examples:** [`samples/analysis/coeval-demo-v2/`](../samples/analysis/coeval-demo-v2/) — 8 self-contained interactive HTML reports.

---
