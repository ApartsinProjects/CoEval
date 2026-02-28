# CoEval — Running Experiments

**CoEval** is a self-evaluating LLM ensemble benchmarking system.
A fleet of small language models plays three roles simultaneously:
**teachers** generate evaluation datasets, **students** answer the test prompts, and
**judges** score each student response.  All three roles may be filled by the same
model or by completely different ones.

---

## Table of Contents

1. [Concept of Operation](#1-concept-of-operation)
2. [Installation](#2-installation)
3. [Quick Start](#3-quick-start)
4. [Configuration Reference](#4-configuration-reference)
   - 4.1 [Top-level keys](#41-top-level-keys)
   - 4.2 [`models`](#42-models)
   - 4.3 [`tasks`](#43-tasks)
   - 4.4 [`experiment`](#44-experiment)
5. [Phase Modes](#5-phase-modes)
6. [Storage Folder Format](#6-storage-folder-format)
7. [Prompt Library Customisation](#7-prompt-library-customisation)
8. [Quota Control](#8-quota-control)
9. [Batch Processing](#9-batch-processing)
10. [Model Probe](#10-model-probe)
11. [Cost and Time Estimation](#11-cost-and-time-estimation)
12. [Label Accuracy for Classification Tasks](#12-label-accuracy-for-classification-tasks)
13. [Use-Case Examples](#13-use-case-examples)
    - 13.1 [First run — everything from scratch](#131-first-run--everything-from-scratch)
    - 13.2 [Resume an interrupted run](#132-resume-an-interrupted-run)
    - 13.3 [Extend an existing dataset](#133-extend-an-existing-dataset)
    - 13.4 [Re-use attributes and rubric; regenerate data only](#134-re-use-attributes-and-rubric-regenerate-data-only)
    - 13.5 [Add a new student model to a finished experiment](#135-add-a-new-student-model-to-a-finished-experiment)
    - 13.6 [Dry-run / config check](#136-dry-run--config-check)
    - 13.7 [Full OpenAI-backend experiment](#137-full-openai-backend-experiment)
    - 13.8 [Estimate cost before running](#138-estimate-cost-before-running)
    - 13.9 [Run with probing in resume mode](#139-run-with-probing-in-resume-mode)
    - 13.10 [Sentiment classification with label accuracy](#1310-sentiment-classification-with-label-accuracy)
    - 13.11 [Probe models, inspect progress, apply batch results](#1311-probe-models-inspect-progress-apply-batch-results)
14. [Validation Rules](#14-validation-rules)
15. [CLI Reference](#15-cli-reference)
16. [Frequently Asked Questions](#16-frequently-asked-questions)

---

## 1. Concept of Operation

CoEval runs a **5-phase pipeline** for each experiment:

```
Phase 1  attribute_mapping    Build or load attribute catalogues for each task
Phase 2  rubric_mapping       Build or load evaluation rubrics for each task
Phase 3  data_generation      Teachers generate (prompt, reference_response) datapoints
Phase 4  response_collection  Students answer each datapoint prompt
Phase 5  evaluation           Judges score each student response against the reference
```

### Roles

| Role    | Responsibility                                           |
|---------|----------------------------------------------------------|
| teacher | Generates synthetic benchmark datapoints (Phase 3) and can map attributes/rubrics (Phases 1–2) |
| student | Responds to the prompt from each datapoint (Phase 4)     |
| judge   | Evaluates student responses against the rubric (Phase 5) |

A single model may hold **all three roles** or any subset.  Tiny models (< 500 M params) that cannot reliably produce structured JSON output should be restricted to the **student** role only.

### Attribute system

Every task has two orthogonal attribute spaces:

- **target_attributes** — axes that directly affect the expected output (e.g. `tone`, `urgency`).  Teachers sample one value per axis when generating a datapoint, creating a controlled spread of difficulty.
- **nuanced_attributes** — axes that vary the *input surface* without changing the correct answer (e.g. writing style, domain, register).  They make datapoints more realistic without biasing the rubric.

Attributes can be **static** (hardcoded in the YAML) or **auto-generated** by teachers at runtime.

---

## 2. Installation

```bash
pip install -e .
# HuggingFace models also need:
pip install accelerate>=0.26
```

Verify:

```bash
coeval --help
```

---

## 3. Quick Start

```bash
coeval run --config examples/local_smoke_test.yaml --dry-run   # check config
coeval run --config examples/local_smoke_test.yaml             # full run
```

> **Available subcommands:** `coeval run`, `coeval probe`, `coeval plan`, `coeval status`, `coeval generate`, `coeval models`, `coeval analyze`.
> See the [CLI Reference](cli_reference.md) for the full option listing for every subcommand.

---

## 4. Configuration Reference

A CoEval config file is a YAML document with three mandatory top-level keys:
`models`, `tasks`, and `experiment`.

### 4.1 Top-level keys

```yaml
models:   [ ... ]   # list of model definitions
tasks:    [ ... ]   # list of task definitions
experiment:         # experiment metadata and control
  id: ...
```

---

### 4.2 `models`

Each entry in the `models` list defines one model.

```yaml
models:
  - name: my-model              # required; [A-Za-z0-9._-], no double underscores
    interface: huggingface      # openai | anthropic | gemini | huggingface | azure_openai | bedrock | vertex
    parameters:                 # passed to the interface on every call
      model: Qwen/Qwen2.5-1.5B-Instruct
      temperature: 0.7
      max_new_tokens: 512
      device: auto              # HuggingFace only; "auto" uses GPU if available
    roles: [teacher, student, judge]   # one or more of: teacher, student, judge
    access_key: sk-...          # optional; OpenAI API key (or set OPENAI_API_KEY env var)

    # Optional per-role parameter overrides (merged on top of `parameters`)
    role_parameters:
      teacher:
        temperature: 0.8
        max_new_tokens: 512
      student:
        temperature: 0.5
        max_new_tokens: 64
      judge:
        temperature: 0.0
        max_new_tokens: 128
```

**Key points:**
- `name` must be unique across all models.
- `name` and task names are combined with `__` (double underscore) as separator to form artifact IDs — so `__` is **reserved** and must not appear in names.
- `role_parameters` values are *merged on top of* the base `parameters` for that role's calls.  Any key present in `role_parameters[role]` overrides the base value; all other keys are inherited unchanged.

---

### 4.3 `tasks`

Each entry defines one evaluation task.

```yaml
tasks:
  - name: email_subject             # required; [A-Za-z0-9_-]
    description: >
      Write a concise email subject line for a given email body.
    output_description: >
      A single subject line of 5 to 12 words that captures the main point.

    # Attribute spaces -------------------------------------------------------
    # Static map (provide the values yourself):
    target_attributes:
      tone:    [formal, casual]
      urgency: [routine, urgent]

    # OR let teachers generate them at runtime:
    # target_attributes: auto      # each teacher generates independently; results merged
    # target_attributes: complete  # teachers augment a seed map (requires target_attributes_seed)

    nuanced_attributes:
      sender_role:   [peer, manager]
      writing_style: [terse, verbose]

    # Seed for "complete" mode:
    target_attributes_seed:
      tone: [formal]              # these values are always kept; teachers add more

    # Whether to store sampled nuanced attributes in each datapoint record:
    store_nuanced: false          # default

    # Sampling ---------------------------------------------------------------
    sampling:
      target: [1, 1]   # [min, max] attributes to sample per datapoint
                       # or "all" to always use every attribute
      nuance: [1, 2]   # [min, max] nuanced attributes per datapoint
      total: 5         # total datapoints to generate per (task, teacher) pair

    # Rubric -----------------------------------------------------------------
    # Static map:
    rubric:
      relevance:   "Subject line accurately reflects the main point."
      conciseness: "Subject line is brief and free of filler words."

    # OR auto-generated:
    # rubric: auto       # teachers generate fresh rubrics; results merged
    # rubric: extend     # copy rubric from resume_from source, teachers may add factors

    evaluation_mode: single     # "single" (one call per response) or "per_factor"

    # Optional prompt overrides (see §7):
    prompt_library: {}
```

#### `target_attributes` / `nuanced_attributes` values

| Value | Meaning |
|-------|---------|
| `{key: [v1, v2, ...]}` | Static map — no LLM calls in Phase 1 for this task |
| `"auto"` | Each teacher generates an independent map; all results are merged |
| `"complete"` | Teachers generate a map that is merged with `*_attributes_seed` |

#### `sampling.target`

| Value | Meaning |
|-------|---------|
| `[min, max]` | Randomly sample between *min* and *max* attributes per datapoint |
| `"all"` | Always include every attribute in every datapoint |

#### `evaluation_mode`

| Value | Phase 5 behaviour |
|-------|-------------------|
| `single` | One LLM call per response; judge scores all rubric factors at once (JSON object) |
| `per_factor` | One LLM call per rubric factor per response; judge returns a single word |

---

### 4.4 `experiment`

```yaml
experiment:
  id: my-experiment-v1          # required; [A-Za-z0-9._-]; must be unique in storage_folder

  storage_folder: ./eval_runs   # root directory for all experiment outputs

  # Resume control ---------------------------------------------------------
  resume_from: my-experiment-v1  # (optional) copy Phase 1–2 artifacts from this prior run

  # Per-phase mode overrides (see §5) --------------------------------------
  phases:
    attribute_mapping: New       # default: New (fresh run) or Keep (resume)
    rubric_mapping:    New
    data_generation:   Extend
    response_collection: New
    evaluation:        New

  log_level: INFO   # DEBUG | INFO | WARNING | ERROR

  # Per-model call quotas (optional) ----------------------------------------
  quota:
    my-model:
      max_calls: 100
```

---

## 5. Phase Modes

Each of the five phases can be run in one of four modes.  The default mode for a fresh
experiment is `New`; when `resume_from` is set, all phases default to `Keep`.

| Mode | Behaviour |
|------|-----------|
| **New** | Discard any existing artifact and regenerate from scratch |
| **Keep** | Skip this phase entirely if the artifact already exists; do nothing otherwise |
| **Extend** | For phases 3–5: generate only the *missing* items up to `sampling.total`; never regenerates already-stored items |
| **Model** | For phases 3–5 only: skip a (task, model) pair if its JSONL file already exists; regenerate only pairs that are absent |

> **Note:** `Model` mode is **not allowed** for Phase 1 (`attribute_mapping`) or Phase 2 (`rubric_mapping`).

> **Note:** `rubric: extend` in a task requires `resume_from` to be set (validation rule V-09).

---

## 6. Storage Folder Format

CoEval writes all outputs under `{storage_folder}/{experiment_id}/`:

```
eval_runs/
└── my-experiment-v1/
    ├── config.yaml                      # snapshot of the config used for this run
    ├── meta.json                        # run status and progress tracker
    ├── run.log                          # timestamped log of all phases
    │
    ├── phase1_attributes/
    │   ├── {task_id}.target_attrs.json  # {"tone": ["formal","casual"], ...}
    │   └── {task_id}.nuanced_attrs.json
    │
    ├── phase2_rubric/
    │   └── {task_id}.rubric.json        # {"relevance": "...", "conciseness": "..."}
    │
    ├── phase3_datapoints/
    │   └── {task_id}.{teacher_id}.datapoints.jsonl
    │
    ├── phase4_responses/
    │   └── {task_id}.{teacher_id}.{student_id}.responses.jsonl
    │
    └── phase5_evaluations/
        └── {task_id}.{teacher_id}.{judge_id}.evaluations.jsonl
```

### `meta.json` schema

```json
{
  "experiment_id": "my-experiment-v1",
  "status": "completed",           // "in_progress" | "completed" | "failed"
  "created_at": "2025-01-01T00:00:00Z",
  "updated_at": "2025-01-01T01:30:00Z",
  "phases_completed": ["attribute_mapping", "rubric_mapping", "data_generation",
                        "response_collection", "evaluation"],
  "phases_in_progress": [],
  "resume_from": null              // or "prior-experiment-id"
}
```

### JSONL record schemas

**Datapoint** (`phase3_datapoints/*.jsonl`):
```json
{
  "id": "email_subject__my-teacher__00001",
  "task_id": "email_subject",
  "teacher_model_id": "my-teacher",
  "sampled_target_attributes": {"tone": "formal", "urgency": "routine"},
  "prompt": "The Q3 results are ready. Please review and share your feedback by Wednesday.",
  "reference_response": "Q3 Results Ready — Feedback Needed by Wednesday",
  "generated_at": "2025-01-01T00:05:00Z"
}
```

**Response** (`phase4_responses/*.jsonl`):
```json
{
  "id": "email_subject__my-teacher__00001__my-student",
  "datapoint_id": "email_subject__my-teacher__00001",
  "task_id": "email_subject",
  "teacher_model_id": "my-teacher",
  "student_model_id": "my-student",
  "prompt": "...",
  "response": "Q3 Feedback Deadline: Wednesday",
  "responded_at": "2025-01-01T00:10:00Z"
}
```

**Evaluation** (`phase5_evaluations/*.jsonl`):
```json
{
  "id": "email_subject__my-teacher__00001__my-student__my-judge",
  "response_id": "email_subject__my-teacher__00001__my-student",
  "task_id": "email_subject",
  "judge_model_id": "my-judge",
  "scores": {"relevance": "High", "conciseness": "Medium"},
  "evaluated_at": "2025-01-01T00:15:00Z"
}
```

### ID naming convention

IDs use `__` (double underscore) as a structured separator:

```
Datapoint:   {task_id}__{teacher_id}__{seq:05d}
Response:    {datapoint_id}__{student_id}
Evaluation:  {response_id}__{judge_id}
```

Because `__` is reserved, **model names and task names must not contain `__`**.

---

## 7. Prompt Library Customisation

CoEval ships six **canonical prompt templates** (in `experiments/prompts.py`):

| Prompt ID | Used in | Purpose |
|-----------|---------|---------|
| `map_target_attrs` | Phase 1 | Ask teacher to generate target attribute map |
| `map_nuanced_attrs` | Phase 1 | Ask teacher to generate nuanced attribute map |
| `autorubric` | Phase 2 | Ask teacher to generate rubric |
| `sample` | Phase 3 | Ask teacher to generate a (prompt, response) datapoint |
| `test` | Phase 4 | Ask student to respond to a prompt |
| `evaluate_single` | Phase 5 | Ask judge to score all rubric factors at once |
| `evaluate_per_factor` | Phase 5 | Ask judge to score one rubric factor |

### Override resolution order

For any prompt call, CoEval resolves the template as follows:

1. `{prompt_id}.{model_name}` in the task's `prompt_library` — **model-specific override**
2. `{prompt_id}` in the task's `prompt_library` — **task-level override**
3. Canonical template from `coeval/prompts.py`

### Template variables

All templates use Python `str.format()` with named placeholders:

| Variable | Available in |
|----------|-------------|
| `{task_description}` | Phases 1, 2, 3, 4, 5 |
| `{output_description}` | Phases 2, 3, 4, 5 |
| `{target_attributes}` | Phases 1, 3, 5 |
| `{nuanced_attributes}` | Phases 1, 3 |
| `{input}` | Phases 4, 5 |
| `{reference_response}` | Phase 5 |
| `{response}` | Phase 5 |
| `{rubric}` | Phase 5 (single mode) |
| `{rubric_factor_name}` / `{rubric_factor_description}` | Phase 5 (per_factor mode) |

> **Escaping braces in YAML:** If your template contains literal `{` or `}` characters
> (e.g. a JSON example), double them: `{{` and `}}`.  Python's `str.format()` will
> convert `{{` → `{` and `}}` → `}`.

### Example — few-shot override for all models

```yaml
tasks:
  - name: email_subject
    ...
    prompt_library:
      sample: |
        Generate a benchmark data point for: {task_description}
        Response format: {output_description}
        Required attributes: {target_attributes}. Nuance: {nuanced_attributes}.

        Follow this example format exactly:
        {{"prompt": "The Q3 results are ready. Please review by Wednesday.",
          "response": "Q3 Results Ready -- Feedback Needed by Wednesday"}}

        Now generate a NEW, different data point.
        Return only a JSON object with keys "prompt" and "response". No explanation.
```

### Example — per-model override

```yaml
    prompt_library:
      sample: |        # default for most models (few_shot)
        ...
      sample.my-small-model: >   # override for one specific model only
        Generate a natural benchmark data point for the task {task_description} ...
        Return as JSON with exactly two keys: "prompt" and "response".
```

---

## 8. Quota Control

To limit how many LLM calls any individual model can make across the entire experiment:

```yaml
experiment:
  quota:
    expensive-gpt4:
      max_calls: 50
    local-model:
      max_calls: 200
```

When a model's quota reaches zero, CoEval skips that model's remaining work and logs a
warning.  Other models continue unaffected.  Models **not** listed in `quota` have no limit.

---

## 9. Batch Processing

For large experiments, CoEval can submit LLM requests as **batch jobs** rather than
individual real-time calls.  Batch APIs offer significant cost savings but have higher
latency (results returned within 24 hours, typically 1–4 hours).

| Interface | Batch mechanism | Pricing discount |
|-----------|----------------|-----------------|
| `openai` | OpenAI Batch API | 50% per-token discount |
| `anthropic` | Anthropic Message Batches API | 50% per-token discount |
| `gemini` | Pseudo-batch (paced real-time calls) | No discount |
| `huggingface` | Not supported | — |

### Enabling batch per phase

```yaml
experiment:
  batch:
    phases: [3, 4, 5]    # which phases to run in batch mode (default: none)
```

Or configure per-model:

```yaml
models:
  - name: gpt4o-teacher
    interface: openai
    parameters:
      model: gpt-4o
    roles: [teacher]
    batch_enabled: true    # this model always uses batch
```

CoEval polls automatically and resumes the pipeline once batch results are available.
To mix batch and real-time models in the same experiment, set `batch_enabled: false`
on individual models.

---

## 9b. Additional Provider Interfaces

CoEval supports seven model interfaces.  All accept the same `generate()` contract;
credentials are resolved automatically from the provider key file or environment variables.

| `interface` value | Provider | Install | Auth |
|-------------------|----------|---------|------|
| `openai` | OpenAI | `pip install openai` | `OPENAI_API_KEY` |
| `anthropic` | Anthropic | `pip install anthropic` | `ANTHROPIC_API_KEY` |
| `gemini` | Google AI Studio | `pip install google-generativeai` | `GEMINI_API_KEY` or `GOOGLE_API_KEY` |
| `huggingface` | HuggingFace Hub (local GPU) | `pip install 'coeval[huggingface]'` | `HF_TOKEN` |
| `azure_openai` | Azure OpenAI Service | `pip install openai` | `AZURE_OPENAI_API_KEY` + `AZURE_OPENAI_ENDPOINT` |
| `bedrock` | AWS Bedrock | `pip install boto3` | `AWS_ACCESS_KEY_ID` + `AWS_SECRET_ACCESS_KEY` + `AWS_DEFAULT_REGION` |
| `vertex` | Google Vertex AI (Gemini) | `pip install google-cloud-aiplatform` | `GOOGLE_CLOUD_PROJECT` + ADC |

### Azure OpenAI

```yaml
models:
  - name: azure-gpt4o
    interface: azure_openai
    parameters:
      model: gpt-4o                              # deployment name in Azure
      azure_endpoint: https://my-res.openai.azure.com/
      api_version: 2024-08-01-preview
      temperature: 0.7
      max_tokens: 512
    roles: [teacher, student, judge]
```

### AWS Bedrock

```yaml
models:
  - name: claude-bedrock
    interface: bedrock
    parameters:
      model: anthropic.claude-3-5-sonnet-20241022-v2:0
      region: us-east-1
      temperature: 0.7
      max_tokens: 512
    roles: [teacher, student, judge]
```

AWS credentials are resolved in order: `parameters` → provider key file → environment variables → IAM instance role.

### Google Vertex AI

```yaml
models:
  - name: gemini-vertex
    interface: vertex
    parameters:
      model: gemini-1.5-pro
      project: my-gcp-project
      location: us-central1
      temperature: 0.7
      max_tokens: 512
    roles: [teacher, student, judge]
```

Authentication uses [Application Default Credentials](https://cloud.google.com/docs/authentication/application-default-credentials) (`gcloud auth application-default login`) unless a `service_account_key` path is provided in the provider key file.

### Provider key file

Store API keys in one place instead of per-experiment:

```yaml
# ~/.coeval/keys.yaml  (or set COEVAL_KEYS_FILE env var, or pass --keys PATH)
providers:
  openai: sk-...
  anthropic: sk-ant-...
  gemini: AIza...
  huggingface: hf_...
  azure_openai:
    api_key: ...
    endpoint: https://my-resource.openai.azure.com/
    api_version: 2024-08-01-preview
  bedrock:
    access_key_id: AKIA...
    secret_access_key: ...
    region: us-east-1
  vertex:
    project: my-gcp-project
    location: us-central1
```

Pass a custom file with `--keys PATH`.  Keys in the file act as fallbacks after
model-level `access_key` values in the YAML.

```bash
coeval run   --config my.yaml --keys ~/.coeval/prod-keys.yaml
coeval probe --config my.yaml --keys ~/.coeval/prod-keys.yaml
coeval models              # list all accessible models
coeval models --providers openai,anthropic
```

---

## 10. Model Probe

Before the pipeline starts, CoEval tests every model for availability using lightweight
API calls that **do not consume generation tokens** (model listing endpoint or
Hub metadata API).

### Probe modes

Configure via `experiment.probe_mode` in the YAML or the `--probe` CLI flag:

| Mode | Behaviour |
|------|-----------|
| `full` | Probe every model in the config (default) |
| `resume` | Probe only models needed for phases that haven't yet completed |
| `disable` | Skip the probe entirely |

```yaml
experiment:
  probe_mode: resume     # full | resume | disable
  probe_on_fail: warn    # abort | warn  (default: abort)
```

`abort` (default): halt the pipeline if any model is unreachable.
`warn`: log a warning and continue; affected phases may fail or produce partial results.

On completion, a `probe_results.json` file is written to the experiment folder.

### CLI flags

```bash
# Probe embedded in a run:
coeval run --config my.yaml --probe resume --probe-on-fail warn
coeval run --config my.yaml --probe disable   # skip probe entirely

# Standalone probe — test models without starting any pipeline phases:
coeval probe --config my.yaml                        # test all models
coeval probe --config my.yaml --probe resume         # test only models needed for remaining phases
coeval probe --config my.yaml --probe-on-fail warn   # always exits 0
```

`coeval probe` runs the same pre-flight check that `coeval run` executes, then exits
immediately after printing results.  Useful for verifying API keys before committing to
a full run.  It suppresses folder-existence validation, so it works on any config
regardless of whether the experiment folder already exists.

---

## 11. Cost and Time Estimation

The cost estimator runs a small number of sample API/inference calls per model,
measures latency and token throughput, then extrapolates to the full experiment size.

### `coeval plan` — dedicated planning command

```bash
# Heuristic only (no real LLM calls, no experiment folder required):
coeval plan --config my.yaml --estimate-samples 0

# 3 sample calls per model for a more accurate estimate:
coeval plan --config my.yaml --estimate-samples 3

# Estimate remaining work for an already-started experiment:
coeval plan --config my.yaml --continue --estimate-samples 0
```

`coeval plan` does not require the experiment folder to already exist (unless `--continue`
is given), so it can be run against a brand-new config before anything has been created.

### Alternative: estimate via `coeval run`

```bash
# Run the estimator inline before starting the pipeline, then exit:
coeval run --config my.yaml --estimate-only --estimate-samples 0
coeval run --config my.yaml --estimate-only --estimate-samples 3

# Estimate only the remaining work for a partial run:
coeval run --config my.yaml --estimate-only --continue
```

### Estimate and then continue with the pipeline

```yaml
experiment:
  estimate_cost: true      # run estimator before the pipeline (default: false)
  estimate_samples: 2      # sample calls per model (default: 2)
```

### Output

The estimator prints a table like:

```
Phase               | Calls  | Cost (USD) | Time (min)
--------------------|--------|------------|----------
attribute_mapping   |     16 |      $0.03 |        0.7
rubric_mapping      |     16 |      $0.03 |        0.7
data_generation     |    200 |      $1.40 |        8.0
response_collection |    600 |      $0.90 |       15.0
evaluation          |    600 |      $1.20 |       18.0
--------------------|--------|------------|----------
TOTAL               |   1432 |      $3.56 |       42.4
```

A `cost_estimate.json` file is also written to the experiment folder.
Batch pricing discounts (50% for `openai` and `anthropic`) are reflected automatically
in the `Cost (USD)` column when batch mode is enabled.

---

## 12. Label Accuracy for Classification Tasks

For tasks where the correct answer is a **discrete class label** (e.g. sentiment
analysis, intent classification, named-entity type recognition), CoEval can evaluate
student responses by **exact label match** instead of calling an LLM judge.

### Config

Add `label_attributes` to the task definition:

```yaml
tasks:
  - name: sentiment_analysis
    description: Classify the sentiment of a product review.
    output_description: A single word — positive, negative, or neutral.
    target_attributes:
      sentiment: [positive, negative, neutral]
    label_attributes: [sentiment]   # exact-match evaluation; no judge model required
    sampling:
      target: [1, 1]
      total: 30
    rubric:
      correctness: "The sentiment label matches the ground-truth label."
    evaluation_mode: single
```

**Validation rule V-17** enforces that every key in `label_attributes` must also
appear as a key in `target_attributes`.

### Student response format

The student may respond in either of two ways:

1. **JSON object:** `{"sentiment": "positive"}`
2. **Short free text:** `positive` (≤ 60 characters, single line)

If the response cannot be parsed, the score is counted as **skipped** (not incorrect).

### Python API

```python
from experiments.label_eval import LabelEvaluator

ev = LabelEvaluator(label_attributes=["sentiment"])
report = ev.evaluate(datapoints, responses)
# report → {"sentiment": {"accuracy": 0.87, "n_total": 50, "n_matched": 44,
#            "n_skipped": 3, "per_label": {"positive": {"precision": ..., ...}, ...}}}
```

---

## 13. Use-Case Examples

### 13.1 First run — everything from scratch

All phases run in `New` mode by default (no `resume_from`, no `phases` overrides).

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

### 13.2 Resume an interrupted run

If a run fails (e.g. network error in Phase 4), all already-written artifacts are
preserved.  Create a new experiment that inherits the completed phases:

```yaml
experiment:
  id: summarise-v2                 # new ID — a fresh folder is created
  storage_folder: ./eval_runs
  resume_from: summarise-v1        # copies Phase 1–2 artifacts into summarise-v2

  phases:
    attribute_mapping:  Keep       # reuse Phase 1 artifacts copied from v1
    rubric_mapping:     Keep       # reuse Phase 2 artifacts copied from v1
    data_generation:    Keep       # datapoints copied from v1 already complete
    response_collection: Extend    # generates only missing responses
    evaluation:         Extend     # evaluates only missing responses
```

```bash
coeval run --config summarise-v2.yaml
# or override resume_from from the command line:
coeval run --config summarise-v2.yaml --resume summarise-v1
```

---

### 13.3 Extend an existing dataset

Double the number of datapoints per task without discarding the ones already generated:

```yaml
tasks:
  - name: summarise
    ...
    sampling:
      total: 20              # was 10 previously

experiment:
  id: summarise-v3
  storage_folder: ./eval_runs
  resume_from: summarise-v1

  phases:
    attribute_mapping:   Keep
    rubric_mapping:      Keep
    data_generation:     Extend    # generates 10 more to reach total=20
    response_collection: Extend
    evaluation:          Extend
```

---

### 13.4 Re-use attributes and rubric; regenerate data only

Use stable, trusted attributes from a previous run but generate entirely fresh datapoints:

```yaml
experiment:
  id: summarise-v4
  storage_folder: ./eval_runs
  resume_from: summarise-v1

  phases:
    attribute_mapping:   Keep    # reuse Phase 1
    rubric_mapping:      Keep    # reuse Phase 2
    data_generation:     New     # discard old datapoints; generate fresh ones
    response_collection: New
    evaluation:          New
```

---

### 13.5 Add a new student model to a finished experiment

Run only Phase 4 (and 5) for a new student, without regenerating anything else:

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
    data_generation:     Keep   # reuse existing datapoints
    response_collection: Model  # skips pairs whose JSONL already exists; runs llama3-8b
    evaluation:          Model
```

---

### 13.6 Dry-run / config check

Validate the config and print the execution plan without making any LLM calls:

```bash
coeval run --config my-experiment.yaml --dry-run
```

Output includes:
- Model list with roles and interfaces
- Task list with sampling settings
- Per-phase mode
- Estimated LLM call counts per task and total

---

### 13.7 Full OpenAI-backend experiment

```yaml
models:
  - name: gpt4o-teacher
    interface: openai
    parameters:
      model: gpt-4o
      temperature: 0.8
      max_tokens: 512
    roles: [teacher]
    access_key: sk-...   # or set OPENAI_API_KEY in your environment

  - name: gpt4o-mini-student
    interface: openai
    parameters:
      model: gpt-4o-mini
      temperature: 0.5
      max_tokens: 256
    roles: [student]

  - name: gpt4o-judge
    interface: openai
    parameters:
      model: gpt-4o
      temperature: 0.0
      max_tokens: 256
    roles: [judge]

tasks:
  - name: qa_task
    description: >
      Answer a factual question with a single sentence.
    output_description: >
      A single sentence that directly answers the question.
    target_attributes:
      difficulty: [easy, hard]
      domain:     [science, history]
    nuanced_attributes:
      phrasing: [direct, indirect]
    sampling:
      target: [1, 2]
      nuance: [1, 1]
      total: 20
    rubric: auto   # let gpt4o-teacher generate the rubric
    evaluation_mode: single

experiment:
  id: qa-benchmark-v1
  storage_folder: ./eval_runs
  log_level: INFO
  quota:
    gpt4o-teacher:
      max_calls: 100
    gpt4o-judge:
      max_calls: 500
```

---

### 13.8 Estimate cost before running

```bash
# Heuristic only — no LLM calls, instant:
coeval run --config my.yaml --estimate-only --estimate-samples 0

# 3 sample calls per model for a more accurate estimate:
coeval run --config my.yaml --estimate-only --estimate-samples 3
```

---

### 13.9 Continue a failed experiment in-place

When a run is interrupted, restart it without changing the experiment ID:

```bash
coeval run --config my.yaml --continue
```

CoEval reads `phases_completed` from `meta.json` and skips completed phases automatically.
Phases 1–2 use `Keep` mode; Phases 3–5 use `Extend` mode (per-record resumption).

---

### 13.10 Sentiment classification with label accuracy

```yaml
models:
  - name: gpt4o-teacher
    interface: openai
    parameters:
      model: gpt-4o
      temperature: 0.7
      max_tokens: 512
    roles: [teacher]

  - name: gpt4o-mini-student
    interface: openai
    parameters:
      model: gpt-4o-mini
      temperature: 0.3
      max_tokens: 32
    roles: [student]

tasks:
  - name: sentiment_analysis
    description: Classify the sentiment of a product review.
    output_description: A single word — positive, negative, or neutral.
    target_attributes:
      sentiment: [positive, negative, neutral]
    label_attributes: [sentiment]   # judge-free exact-match evaluation
    sampling:
      target: [1, 1]
      total: 30
    rubric:
      correctness: "The predicted sentiment matches the ground-truth label."
    evaluation_mode: single

experiment:
  id: sentiment-v1
  storage_folder: ./eval_runs
```

No judge model is required — Phase 5 uses exact label matching instead of LLM calls.

---

### 13.11 Two-step workflow: generate design, then run

Separate the attribute/rubric generation step from the execution step so you can
review and edit the generated values before running the full pipeline.

```bash
# Step 1 — write a draft config with target_attributes: auto and rubric: auto
# Step 2 — generate the design file (runs phases 1-2 in a temp directory)
coeval generate --config draft.yaml --out design.yaml

# Step 3 — review design.yaml; attributes and rubric are now static lists
# Step 4 — run the full pipeline from the materialized design
coeval run --config design.yaml
```

**Draft config snippet** (`draft.yaml`):
```yaml
tasks:
  - name: qa_task
    description: Answer a factual question with a single sentence.
    output_description: A single sentence that directly answers the question.
    target_attributes: auto   # teacher generates the attribute map
    rubric: auto              # teacher generates the rubric
    sampling: {target: [1,2], nuance: [0,0], total: 10}
```

**After `coeval generate`**, the materialized `design.yaml` has:
```yaml
tasks:
  - name: qa_task
    target_attributes:
      difficulty: [easy, hard]
      domain: [science, history]
    rubric:
      accuracy: >
        The answer correctly states the fact asked about.
      completeness: >
        The answer addresses all parts of the question.
    ...
```

---

### 13.12 Probe models, inspect progress, apply batch results

**Before a run — verify API keys and model access:**

```bash
coeval probe --config my-experiment.yaml
```

**During or after a run — inspect progress:**

```bash
# Show metadata, phase artifact counts, pending batch jobs, and recent errors:
coeval status --run eval_runs/my-experiment-v1

# Poll batch APIs; for completed jobs, download and apply results to storage:
coeval status --run eval_runs/my-experiment-v1 --fetch-batches

# Then resume to finish any remaining work:
coeval run   --config my-experiment.yaml --continue
```

`coeval status` reads the experiment folder directly — no config file needed.
Phase 4 and Phase 5 batch results are applied automatically by `--fetch-batches`.
Phase 3 (data generation) batch results require a subsequent `--continue` run.

---

## 14. Validation Rules

CoEval validates the configuration before any LLM call is made.
All errors are reported at once; the experiment does not start if any rule is violated.

| Rule | Description |
|------|-------------|
| V-01 | `models` and `tasks` must be present and non-empty |
| V-02 | Model names must be unique |
| V-03 | Task names must be unique |
| V-04 | Model names match `[A-Za-z0-9._-]` and must not contain `__`; task names match `[A-Za-z0-9_-]`; experiment ID matches `[A-Za-z0-9._-]` |
| V-05 | Every model must have at least one valid role (`teacher`, `student`, `judge`) |
| V-06 | Every model's `interface` must be one of: `openai`, `anthropic`, `gemini`, `huggingface`, `azure_openai`, `bedrock`, `vertex` |
| V-07 | At least one model must be a `student`; at least one must be a `judge` (unless all tasks use `label_attributes`); if any task uses `auto`/`complete` attributes or `auto`/`extend` rubric, at least one model must be a `teacher` |
| V-08 | `Model` mode is not permitted for Phase 1 (`attribute_mapping`) or Phase 2 (`rubric_mapping`) |
| V-09 | `rubric: extend` requires `experiment.resume_from` to be set |
| V-10 | If `resume_from` is set, the source experiment folder must exist in `storage_folder` |
| V-11 | For a new experiment (no `resume_from`), the target folder must not already exist — use a different ID or `--continue` to restart an interrupted run |
| V-12 | `generation_retries` must be >= 0 if specified |
| V-13 | `experiment.batch.phases` must be a subset of `[3, 4, 5]` |
| V-14 | `--continue` requires an existing `meta.json` in the experiment folder |
| V-15 | `experiment.probe_mode` must be `disable`, `full`, or `resume` |
| V-16 | `experiment.probe_on_fail` must be `abort` or `warn` |
| V-17 | Every key in `label_attributes` must also be present as a key in `target_attributes` |

---

## 15. CLI Reference

> **Full option listing:** see [`docs/cli_reference.md`](cli_reference.md) for tables of
> every option, exit code, and example for every subcommand.

### Subcommand summary

| Subcommand | Purpose |
|------------|---------|
| `coeval run` | Execute an evaluation experiment (all five pipeline phases) |
| `coeval probe` | Test model availability without starting any experiment phases |
| `coeval plan` | Estimate cost and runtime without starting any experiment phases |
| `coeval status` | Show experiment progress and pending batch job status |
| `coeval generate` | Run phases 1–2 and write a materialized YAML ready for `coeval run` |
| `coeval models` | List available text-generation models from each configured provider |
| `coeval analyze` | Analyze an experiment folder and generate reports |

### `coeval run` — key options

```
coeval run --config PATH [options]

  --config PATH          Required; path to the YAML configuration file
  --resume ID            Override experiment.resume_from from the command line
  --continue             Resume a failed/interrupted run in-place (requires meta.json)
  --only-models IDS      Comma-separated model IDs to activate; all others skipped
  --dry-run              Validate config and print plan; make no LLM calls
  --probe MODE           Probe scope: full (default) | resume | disable
  --probe-on-fail MODE   On unavailable model: abort (default) | warn
  --estimate-only        Run estimator, print table, write cost_estimate.json, then exit
  --estimate-samples N   Sample calls per model (default 2; 0 = heuristics only)
  --log-level LEVEL      DEBUG | INFO | WARNING | ERROR
```

The execution plan is always printed before the run starts.
Log output is written to both stdout and `{storage_folder}/{experiment_id}/run.log`.

**CLI flag precedence:** CLI flags always override their YAML config equivalents
(`--probe` overrides `experiment.probe_mode`, `--estimate-samples` overrides
`experiment.estimate_samples`, `--log-level` overrides `experiment.log_level`).

### `coeval probe` — standalone model check

```
coeval probe --config PATH [--probe MODE] [--probe-on-fail MODE] [--log-level LEVEL]
```

Exit codes: 0 = all models available, 1 = config error, 2 = model unavailable + `abort`.

### `coeval plan` — standalone cost estimation

```
coeval plan --config PATH [--continue] [--estimate-samples N] [--log-level LEVEL]
```

Does not require the experiment folder to exist (unless `--continue` is given).

### `coeval status` — experiment dashboard

```
coeval status --run PATH [--fetch-batches]
```

Takes the experiment **folder path** (not a config file). `--fetch-batches` polls
provider APIs and applies completed Phase 4/5 batch results automatically.

### `coeval generate` — design then run

```
coeval generate --config PATH --out PATH [--probe MODE] [--probe-on-fail MODE]
                [--log-level LEVEL] [--keys PATH]
```

Runs phases 1–2 in a temporary directory; writes a materialized YAML where all
`auto`/`complete`/`extend` values are replaced by generated static data.
Review and edit `--out`, then pass it to `coeval run`.

### `coeval models` — list accessible models

```
coeval models [--providers LIST] [--verbose] [--keys PATH]
```

Queries each provider's model-listing endpoint and prints accessible models.
Credentials are resolved from the provider key file or environment variables.

### Provider key file (`--keys PATH`)

All config-consuming subcommands accept `--keys PATH` to point at a YAML file
storing provider credentials (default: `~/.coeval/keys.yaml`).  Credentials in
the file act as fallbacks after model-level `access_key` values in the YAML.

---

## 16. Frequently Asked Questions

### New Subcommands (probe / plan / status)

**Q: When should I use `coeval probe` instead of just running with `--probe`?**
> Use `coeval probe` to verify API keys and model access *before* you commit to a full
> run — especially if the experiment would take hours or incur significant cost.  It runs
> the same lightweight availability check but exits immediately after printing results,
> without creating any experiment folder or consuming any pipeline quota.

**Q: What is the difference between `coeval plan` and `coeval run --estimate-only`?**
> Both call the same cost estimator and print the same table.  `coeval plan` is the
> preferred standalone command: it suppresses folder-existence validation, so you can
> use it against a new config before the experiment folder exists.  `coeval run
> --estimate-only` is the inline version — useful when you want to check cost and then
> immediately start the run.

**Q: What does `coeval status` show?**
> It reads the experiment folder directly (no config file needed) and prints:
> (1) experiment metadata (ID, status, creation time, completed and in-progress phases),
> (2) file and JSONL record counts per phase,
> (3) pending batch jobs (IDs, phase, request count, last-known status), and
> (4) the last 10 entries from `run_errors.jsonl`.

**Q: My batch job finished but the results aren't in the experiment folder.  How do I apply them?**
> Run `coeval status --run <path> --fetch-batches`.  This polls the OpenAI/Anthropic
> APIs for all tracked batch jobs, downloads results for completed jobs, and writes them
> into the Phase 4 or Phase 5 JSONL files automatically.  Phase 3 batch results cannot
> be reconstructed automatically — the command will notify you to re-run with `--continue`.

---

### Setup and Installation

**Q: I get `ImportError: No module named 'accelerate'` when running a HuggingFace model.**
> Install the optional dependency: `pip install 'coeval[huggingface]'` or `pip install accelerate>=0.26`.

**Q: Do I need a GPU to run CoEval with HuggingFace models?**
> No.  Setting `device: auto` lets the Transformers library choose CPU if no GPU is
> available.  Inference will be slower, but the pipeline works correctly.  Explicitly
> set `device: cpu` to force CPU and suppress device-selection warnings.

**Q: Where do I put my OpenAI API key?**
> Either set the `OPENAI_API_KEY` environment variable, or add `access_key: sk-...` to
> the model entry in your YAML config.  Environment variable is recommended to avoid
> committing credentials to version control.

---

### Running Experiments

**Q: The experiment fails with "Experiment folder already exists".**
> This is validation rule V-11.  Either (a) choose a new `experiment.id`, (b) set
> `resume_from: <your-existing-id>` to inherit Phase 1–2 artifacts from a prior run,
> or (c) use `--continue` to restart the same experiment in-place.

**Q: Can I run the same config twice?**
> Not with the same `experiment.id` unless you use `--continue`.  Change the ID for
> each fresh run, or use `--continue` to resume an interrupted one.

**Q: The run stopped halfway through Phase 4.  How do I continue from where it left off?**
> Option A (recommended for interrupted runs): use `--continue`:
> ```bash
> coeval run --config my.yaml --continue
> ```
> Option B (new experiment ID): create a new config with `resume_from` pointing to the
> old experiment and set phase modes manually:
> ```yaml
> phases:
>   attribute_mapping:   Keep
>   rubric_mapping:      Keep
>   data_generation:     Keep
>   response_collection: Extend   # generates only missing responses
>   evaluation:          Extend
> ```

**Q: How do I get a cost estimate in USD before running?**
> Use `--estimate-only`:
> ```bash
> coeval run --config my.yaml --estimate-only
> ```
> This prints a cost table per phase and writes `cost_estimate.json`, then exits.
> Add `--estimate-samples 0` to use heuristics only (no real LLM calls).

**Q: The model probe fails for one of my models.  Can I skip just that model?**
> Run with `--probe-on-fail warn`.  CoEval will log the failure and continue with
> the remaining models:
> ```bash
> coeval run --config my.yaml --probe-on-fail warn
> ```

**Q: What is `--dry-run` useful for?**
> Use it to validate your YAML config and see the estimated LLM call budget before
> spending any credits or GPU time.  It prints the full execution plan and exits without
> making a single LLM call.

**Q: How do I estimate how many LLM calls my experiment will make?**
> Run `coeval run --config my.yaml --dry-run`.  The "Estimated LLM calls" section in
> the output breaks down calls per task and per phase.  The formula is:
> - Phase 3: `n_teachers × sampling.total` per task
> - Phase 4: `n_teachers × n_students × sampling.total` per task
> - Phase 5 (single): `n_teachers × n_judges × n_students × sampling.total` per task
> - Phase 5 (per_factor): multiply Phase 5 (single) by the number of rubric factors

---

### Configuration

**Q: What is the difference between `auto` and `complete` for `target_attributes`?**
> Both call teachers to generate attributes.  With `auto`, the teacher output is the
> only source.  With `complete`, you also provide a `target_attributes_seed` dict whose
> values are always preserved and merged with whatever teachers generate.  Use
> `complete` when you want to guarantee certain values appear while still expanding the
> space with LLM creativity.

**Q: Can one model be both a teacher and a student?**
> Yes.  Set `roles: [teacher, student, judge]` (or any subset).  The model will receive
> different prompt templates and different role-specific parameters (temperature, token
> limit) depending on which role it is acting in.

**Q: When should I restrict a model to `roles: [student]` only?**
> Tiny models (≤ 360 M parameters) typically cannot produce reliably structured JSON
> output needed for Phases 1–3.  Limit them to the student role so they are only asked
> for free-form text responses in Phase 4.

**Q: How does `sampling.target: [1, 1]` differ from `sampling.target: "all"`?**
> `[1, 1]` picks exactly one attribute key (and one value) per datapoint, giving you
> focused, targeted test cases.  `"all"` includes every attribute in every datapoint,
> useful when you have very few attributes and want complete coverage per item.

**Q: My YAML has `{` and `}` in a prompt template but they get swallowed or cause an error.**
> Python's `str.format()` treats `{` and `}` as placeholder delimiters.  Escape literal
> braces by doubling them: write `{{` to produce `{` and `}}` to produce `}` in the
> final prompt.  This applies both to prompt_library overrides in YAML and to JSON
> examples embedded in templates.

---

### Models and Evaluation

**Q: What does `evaluation_mode: per_factor` buy me over `single`?**
> With `single`, the judge scores all rubric factors in one call — faster but the model
> may be less reliable when scoring many factors at once.  With `per_factor`, each
> factor gets its own dedicated call, which tends to produce more consistent scores at
> the cost of `n_factors × n_responses × n_judges` additional LLM calls.

**Q: What are valid score values?**
> `High`, `Medium`, or `Low`.  In `single` mode, any value outside this set is silently
> coerced to `Low`.  In `per_factor` mode, the model is retried up to 3 times; if it
> still returns an invalid word, a `ValueError` is raised.

**Q: Can I add more score levels (e.g., 1-5 scale)?**
> Not without code changes.  The score vocabulary is hardcoded in `call_llm_word()` and
> the `_score_response()` validation logic in Phase 5.  See the Developer Guide §7 for
> how to extend the system.

**Q: My judge model keeps returning `Low` for every factor.  What's wrong?**
> This usually means the model is not following the JSON output format (`single` mode)
> or the one-word instruction (`per_factor` mode).  Try a larger judge model, add a
> model-specific `prompt_library` override for `evaluate_single` or `evaluate_per_factor`,
> switch to `per_factor` mode (simpler output format), or ensure `max_new_tokens` /
> `max_tokens` is at least 256 for `single` mode judge calls.

**Q: When should I use `label_attributes` instead of an LLM judge?**
> Use `label_attributes` for tasks with a finite, known set of correct answers
> (classification, tagging, intent detection).  Label evaluation is deterministic,
> costs nothing, and is much faster than judge calls.  For open-ended generation
> tasks (summarisation, translation, code generation), use an LLM judge.

**Q: Does `label_attributes` require a judge model?**
> No.  When all rubric factors for a task are covered by `label_attributes`, no judge
> model is invoked for that task.  You can omit the `judge` role from the model list
> entirely if every task in the experiment uses label-based evaluation.

---

### Batch Processing

**Q: How much cheaper is batch processing?**
> For `openai` and `anthropic` models, the Batch API offers a **50% per-token
> discount**.  The `gemini` pseudo-batch interface provides no discount — it simply
> paces requests to avoid rate limits.  HuggingFace models do not support batching.

**Q: How long does a batch job take?**
> OpenAI and Anthropic guarantee results within 24 hours, but typical turnaround is
> 1–4 hours.  CoEval polls automatically and resumes the pipeline when results arrive.

---

### Storage and Results

**Q: Where are my results?**
> All outputs are in `{storage_folder}/{experiment_id}/`.  Phase 5 evaluations
> (`phase5_evaluations/*.jsonl`) are the primary result files.  Each line is a JSON
> object with an `id`, `scores` dict (`{"factor": "High/Medium/Low"}`), and metadata.

**Q: How do I load results in Python?**
> ```python
> import json, pathlib
>
> eval_dir = pathlib.Path('./eval_runs/my-experiment/phase5_evaluations')
> evaluations = []
> for path in eval_dir.glob('*.jsonl'):
>     for line in path.read_text().splitlines():
>         if line.strip():
>             evaluations.append(json.loads(line))
> ```

**Q: Can I delete the experiment folder and start over?**
> Yes.  Deleting the folder removes all artifacts.  Then run with the same `id` again
> (no `resume_from`) and CoEval will create it fresh.

**Q: The `run.log` file is very large.  How do I reduce it?**
> Set `log_level: WARNING` in the `experiment` block to suppress `INFO` and `DEBUG`
> messages.  Or use `--log-level WARNING` on the CLI.
