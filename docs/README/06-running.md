# Running Experiments

[← Providers](05-providers.md) · [Benchmarks →](07-benchmarks.md)

---

**CoEval** is a self-evaluating LLM ensemble benchmarking system. A fleet of language models plays three roles: **teachers** generate evaluation datasets, **students** answer the test prompts, and **judges** score each student response. All three roles may be filled by the same model or by completely different ones.

| Role    | Responsibility |
|---------|----------------|
| teacher | Generates benchmark datapoints (Phase 3) and maps attributes/rubrics (Phases 1–2) |
| student | Responds to the prompt from each datapoint (Phase 4) |
| judge   | Evaluates student responses against the rubric (Phase 5) |

---

## Prerequisites

```bash
# Install core dependencies
pip install -e ".[openai,anthropic,huggingface]"

# Verify GPU (required for local HuggingFace models)
python -c "import torch; print('CUDA:', torch.cuda.is_available())"

# Set API keys
export OPENAI_API_KEY="sk-..."
export ANTHROPIC_API_KEY="sk-ant-..."   # if using Anthropic models
```

---

## Writing a Config File

Every experiment is described by a single YAML file. The minimal structure is:

```yaml
models:
  - name: gpt-4o-mini
    interface: openai
    parameters:
      model: gpt-4o-mini
      temperature: 0.7
      max_tokens: 512
    roles: [teacher, student, judge]

tasks:
  - name: text_summarization
    description: "Summarise a passage of text concisely and accurately."
    output_description: "A 1–3 sentence summary in plain prose."
    target_attributes:
      complexity:  [simple, moderate, complex]
      tone:        [neutral, formal]
    nuanced_attributes:
      domain:      [science, business, politics]
    sampling:
      target: [1, 2]   # sample 1–2 target attribute values per datapoint
      nuance: [1]       # sample 1 nuanced attribute value per datapoint
      total:  20        # datapoints to generate per (task, teacher) pair
    rubric:
      accuracy:    "The summary correctly captures the main points."
      conciseness: "The summary avoids redundancy and respects the length target."
    evaluation_mode: single
    prompt_library:
      sample: |
        Generate a benchmark datapoint for: {task_description}
        Attributes: {target_attributes}. Nuance: {nuanced_attributes}.
        Return JSON with keys "prompt" and "response".

experiment:
  id: my-experiment-v1
  storage_folder: ./benchmark/runs
  log_level: INFO
  phases:
    attribute_mapping:   New
    rubric_mapping:      New
    data_generation:     New
    response_collection: New
    evaluation:          New
```

See `benchmark/medium_benchmark.yaml` for a complete production example with five models, four tasks, and per-role temperature overrides.

---

## Running an Experiment

```bash
coeval run --config benchmark/medium_benchmark.yaml
```

The CLI prints live progress for each phase. All artifacts are written under:

```
benchmark/runs/{experiment_id}/
  meta.json                             ← run status + phase log
  config.yaml                           ← snapshot of the config used
  phase1_attributes/
    {task_id}_target_attrs.json
    {task_id}_nuanced_attrs.json
  phase2_rubric/
    {task_id}.rubric.json
  phase3_datapoints/
    {task_id}.{teacher_id}.datapoints.jsonl
  phase4_responses/
    {task_id}.{student_id}.responses.jsonl
  phase5_evaluations/
    {task_id}.{teacher_id}.{judge_id}.evaluations.jsonl
```

**Quick start commands:**
```bash
coeval run --config examples/local_smoke_test.yaml --dry-run   # validate only, no LLM calls
coeval run --config examples/local_smoke_test.yaml             # full run
```

Available subcommands: `run`, `probe`, `plan`, `status`, `generate`, `models`, `analyze`, `describe`.

---

## Phases Explained

CoEval runs a 5-phase pipeline: `attribute_mapping` → `rubric_mapping` → `data_generation` → `response_collection` → `evaluation`.

| Phase | Name | What it does | LLM calls |
|-------|------|-------------|-----------|
| 1 | Attribute Mapping | Teachers propose target & nuanced attributes from the task description | `n_teachers × n_tasks` |
| 2 | Rubric Construction | Teachers propose or refine a scoring rubric | `n_teachers × n_tasks` |
| 3 | Data Generation | Teachers generate (prompt, reference-response) pairs | `n_teachers × n_tasks × datapoints` |
| 4 | Response Collection | Students respond to each teacher-generated prompt | `n_students × total_datapoints` |
| 5 | Ensemble Scoring | Judges score each student response against the rubric | `n_judges × n_students × total_datapoints` |

**Static mode (phases 1–2):** If you supply rubric and attribute definitions directly in the YAML, set phases 1–2 to `Keep` (zero LLM calls for those phases).

---

## Phase Modes

Each phase can be set independently in `experiment.phases`. Each phase can run in one of four modes:

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

## Multi-Role Model Configuration

A model can hold any combination of `teacher`, `student`, and `judge` roles. Override generation parameters per role:

```yaml
- name: gpt-4o-mini
  interface: openai
  roles: [teacher, student, judge]
  parameters:
    model: gpt-4o-mini
    temperature: 0.7
    max_tokens: 512
  role_parameters:
    teacher:
      temperature: 0.8   # slightly higher creativity for generation
      max_tokens: 512
    student:
      temperature: 0.7
      max_tokens: 256
    judge:
      temperature: 0.0   # deterministic scoring
      max_tokens: 128
```

`role_parameters` values are merged on top of `parameters` — only the keys you specify are overridden.

---

## Local HuggingFace Models

Local models require a CUDA GPU. The framework will stop with a clear error if no GPU is available.

```yaml
- name: qwen2p5-1b5
  interface: huggingface
  parameters:
    model: Qwen/Qwen2.5-1.5B-Instruct
    temperature: 0.7
    max_new_tokens: 512
    device: auto        # auto-selects GPU; use "cuda:0" to pin to a device
  roles: [teacher, student, judge]
```

First run downloads the model weights via HuggingFace Hub. Set `HF_HOME` to control the cache location.

---

## OpenAI-Compatible Providers

CoEval supports five additional OpenAI-compatible providers via the `openai_compat` interface module. All use the same configuration pattern with a dedicated `interface` identifier.

| Interface | Provider | Env var | Notable strength |
|-----------|----------|---------|-----------------|
| `groq` | Groq | `GROQ_API_KEY` | ~500 tok/s — ideal for large-scale Phase 4 response collection |
| `deepseek` | DeepSeek (direct) | `DEEPSEEK_API_KEY` | ~2× cheaper than OpenRouter for DeepSeek-V3 ($0.07/1M input) |
| `mistral` | Mistral AI (direct) | `MISTRAL_API_KEY` | Same price as OpenRouter but direct SLAs; Codestral available only here |
| `deepinfra` | DeepInfra | `DEEPINFRA_API_KEY` | Competitive pricing on Llama and Qwen models; reliable uptime |
| `cerebras` | Cerebras | `CEREBRAS_API_KEY` | ~1000 tok/s sustained throughput on wafer-scale hardware |

**Configuration example:**

```yaml
models:
  - name: llama-3-8b-groq
    interface: groq
    parameters:
      model: llama-3.1-8b-instant
      temperature: 0.7
      max_tokens: 512
    roles: [student]

  - name: deepseek-v3
    interface: deepseek
    parameters:
      model: deepseek-chat
      temperature: 0.7
      max_tokens: 512
    roles: [student]
```

**Key file format** for these providers:

```yaml
providers:
  groq:      gsk-...
  deepseek:  sk-...
  mistral:   ...
  deepinfra: di-...
  cerebras:  csk-...
```

None of these providers offer a batch discount — all run real-time only. `interface: auto` routing prefers the cheapest provider that has credentials configured; DeepSeek direct is cheaper than OpenRouter for DeepSeek-V3.

---

## Cost Estimation

The cost estimator runs sample API calls per model, measures latency and token throughput, and extrapolates to the full experiment size. Batch discounts (50% for `openai`, `anthropic`, `gemini`, and `azure_openai`) are reflected automatically.

**Mental formula for LLM call counts:**
- Phase 3: `n_teachers × sampling.total` per task
- Phase 4: `n_teachers × n_students × sampling.total` per task
- Phase 5 (`single`): `n_teachers × n_judges × n_students × sampling.total` per task
- Phase 5 (`per_factor`): Phase 5 (single) × number of rubric factors

Or more directly:
```
Phase 3 calls = n_teachers × n_tasks × datapoints_per_task
Phase 4 calls = n_students × (n_teachers × n_tasks × datapoints_per_task)
Phase 5 calls = n_judges   × Phase_4_calls
Total calls   = Phase3 + Phase4 + Phase5
```

**Concrete example — `medium_benchmark.yaml` (5 models all roles, 4 tasks, 20 datapoints):**
```
Phase 3:   5 × 4 × 20         =   400  calls
Phase 4:   5 × 400            = 2,000  calls
Phase 5:   5 × 2,000          = 10,000 calls
Total:                        = 12,400 calls
```

At `gpt-4o-mini` rates (~$0.15/1M input tokens, ~$0.60/1M output), a full medium run costs approximately **$1.80–$2.50**.

**Estimation commands:**

```bash
# Standalone planning (no experiment folder needed):
coeval plan --config my.yaml --estimate-samples 0   # heuristics only, no LLM calls
coeval plan --config my.yaml --estimate-samples 3   # 3 sample calls per model
coeval plan --config my.yaml --continue             # estimate remaining work only

# Inline — prints table + writes cost_estimate.json, then exits:
coeval run --config my.yaml --estimate-only --estimate-samples 0
coeval run --config my.yaml --estimate-only --continue
```

**Cost reduction strategies:**

| Strategy | Saving |
|----------|--------|
| Enable Batch API for OpenAI, Anthropic, Gemini, Azure OpenAI | **50%** off Phases 4 and 5 |
| Use `benchmark` teachers instead of LLM teachers | Eliminate Phase 3 entirely |
| Use smaller judge models (Haiku, GPT-4o-mini) | 5–20× cheaper per call vs. frontier |
| Set `evaluation_mode: single` | Reduces Phase 5 calls to 1× vs. N× per rubric dimension |
| Use `--only-models` to add models incrementally | Pay for new models only, not re-runs |
| Set `sampling.total` conservatively, extend later | Start small, scale up with `--continue` |

---

## API Quotas

To prevent overrunning API budgets, set per-model call limits in the `quota` block:

```yaml
experiment:
  quota:
    gpt-4o-mini:
      max_calls: 2600
    gpt-3.5-turbo:
      max_calls: 2600
    expensive-gpt4:
      max_calls: 50
    local-model:
      max_calls: 200
```

CoEval tracks calls per model across all phases. When a model reaches its ceiling:
- The current phase records a warning in the log
- The model stops making new calls for that phase
- The pipeline continues for other models
- Remaining items for the quota-reached model are left as gaps (fillable with `--continue` after adjusting the quota)

This means experiments never crash due to quota exhaustion — they complete gracefully with partial results for the affected model. Models not listed in `quota` have no limit.

---

## Batch Processing

For large experiments, CoEval can submit LLM requests as batch jobs rather than individual real-time calls. Batch APIs offer up to 50% cost savings but have higher latency (results returned within 24 hours, typically 1–4 hours). CoEval polls automatically and resumes the pipeline when results are available.

| Interface      | Batch mechanism                           | Pricing discount |
|----------------|-------------------------------------------|-----------------|
| `openai`       | OpenAI Batch API                          | 50% per-token   |
| `anthropic`    | Anthropic Message Batches API             | 50% per-token   |
| `azure_openai` | Azure OpenAI Batch API                    | 50% per-token   |
| `gemini`       | Gemini Batch API (async)                  | 50% per-token   |
| `huggingface`  | Not supported                             | —               |

Enable batch processing per phase in the config:

```yaml
experiment:
  batch:
    openai:
      response_collection: true
      evaluation: true
    anthropic:
      response_collection: true
      evaluation: true
    gemini:
      response_collection: true
      evaluation: true
    azure_openai:
      response_collection: true
      evaluation: true
```

Or set `batch_enabled: true` / `batch_enabled: false` on individual model entries to mix batch and real-time models in the same experiment.

Batch mode is transparent to the rest of the pipeline — no changes to output format or downstream analysis. Use `coeval status --fetch-batches` to check completion status manually.

---

## Pre-Run Estimation

### Standalone estimate

```bash
coeval plan --config my-experiment.yaml
```

Samples 2 live API calls per model by default to measure real latency and throughput. Use `--estimate-samples 0` for pure heuristics (no API calls at all).

### Estimate embedded in a run

```bash
# Estimate, print table, write cost_estimate.json, then exit — no phases run
coeval run --config my-experiment.yaml --estimate-only

# Estimate first, then proceed if within budget
coeval run --config my-experiment.yaml
# (estimate_cost: true in config triggers estimation before Phase 1)
```

### Remaining-work estimation

When used with `--continue`, the estimator computes cost for only the remaining work:

```bash
coeval plan --config my-experiment.yaml --continue
# → shows cost for phases/items not yet completed
```

---

## Fault Tolerance

The pipeline writes each item immediately to disk. If a run crashes mid-phase, restart with `--continue` to pick up from exactly where it left off. Each JSONL record is written atomically; a crash mid-phase loses at most one record.

---

## Resuming Interrupted Runs

```bash
coeval run --config benchmark/medium_benchmark.yaml --continue
```

`--continue` applies:
- **Phase-level skip** — any phase in `phases_completed` is skipped entirely.
- **Item-level skip (Extend mode)** — within active phases, already-written JSONL records are read and only missing items are processed.

This means a crash after 847 of 1,000 items wastes at most one in-flight batch, not the full 847.

**Validation checks on `--continue`:**
- Config ID must match the existing `meta.json` experiment ID.
- A `meta.json` must already exist (ensures you are continuing, not starting fresh).

---

## Checking Status

```bash
# Show progress dashboard — phase status, artifact counts, pending batches, recent errors
coeval status --run benchmark/runs/my-experiment-v1

# Fetch and apply completed batch results, then show updated status
coeval status --run benchmark/runs/my-experiment-v1 --fetch-batches
```

---

## Use-Case Examples

### Example 1: First Run — Everything from Scratch

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

### Example 2: Resume an Interrupted Run

Use `--continue` to restart an interrupted run in-place without changing the experiment ID:

```bash
coeval run --config my.yaml --continue
```

CoEval reads `phases_completed` from `meta.json`, applies `Keep` to Phases 1–2 and `Extend` to Phases 3–5. To use a new experiment ID instead:

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

### Example 3: Add a New Student Model to a Finished Experiment

Run only Phases 4–5 for a new student without regenerating anything else. `Model` mode creates JSONL only for model/task pairs that do not yet exist:

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

### Example 4: Dry-Run / Config Check

Validate the config and print the execution plan without making any LLM calls:

```bash
coeval run --config my-experiment.yaml --dry-run
```

Output: model list with roles/interfaces, task sampling settings, per-phase mode, and estimated LLM call counts per task and in total.

---

[← Providers](05-providers.md) · [Benchmarks →](07-benchmarks.md)
