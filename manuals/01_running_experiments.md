# Running CoEval Experiments

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

## New Providers (Groq, DeepSeek, Mistral, DeepInfra, Cerebras)

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

**Key file format** (`~/.coeval/keys.yaml` or project root `keys.yaml`):

```yaml
providers:
  groq:      gsk-...
  deepseek:  sk-...
  mistral:   ...
  deepinfra: di-...
  cerebras:  csk-...
```

**Notes:**
- None of these providers offer a batch discount — all run real-time only.
- `interface: auto` routing prefers the cheapest provider that has credentials configured; DeepSeek direct is cheaper than OpenRouter for DeepSeek-V3.
- See [`manuals/04_provider_pricing.md`](04_provider_pricing.md) §1 and §4.2 for full pricing details and recommended use cases.

---

## 1. Writing a Config File

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

## 2. Running an Experiment

```bash
# From the repo root
python -m experiments.cli run --config benchmark/medium_benchmark.yaml
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

---

## 3. Phases Explained

| Phase | Name | What it does | LLM calls |
|-------|------|-------------|-----------|
| 1 | Attribute Mapping | Teachers propose target & nuanced attributes from the task description | `n_teachers × n_tasks` |
| 2 | Rubric Construction | Teachers propose or refine a scoring rubric | `n_teachers × n_tasks` |
| 3 | Data Generation | Teachers generate (prompt, reference-response) pairs | `n_teachers × n_tasks × datapoints` |
| 4 | Response Collection | Students respond to each teacher-generated prompt | `n_students × total_datapoints` |
| 5 | Ensemble Scoring | Judges score each student response against the rubric | `n_judges × n_students × total_datapoints` |

**Static mode (phases 1–2):** If you supply rubric and attribute definitions directly in the YAML, set phases 1–2 to `Keep` (zero LLM calls for those phases).

---

## 4. Phase Modes

Each phase can be set independently in `experiment.phases`:

| Mode | Behaviour |
|------|-----------|
| `New` | Overwrite any existing output and regenerate from scratch |
| `Keep` | Skip the phase entirely; use whatever output already exists |
| `Extend` | Generate only the missing items (fill gaps); skip what exists |
| `Model` | Skip if the output file for this model already exists |

---

## 5. API Quotas

To prevent overrunning API budgets, set per-model call limits:

```yaml
experiment:
  quota:
    gpt-4o-mini:
      max_calls: 2600
    gpt-3.5-turbo:
      max_calls: 2600
```

When the quota is exhausted, the model is skipped for the remainder of the phase (other models continue).

---

## 6. Multi-Role Model Configuration

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

---

## 7. Local HuggingFace Models

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

## 8. Checking Experiment Status

```bash
python -c "
import json
from pathlib import Path
meta = json.loads(Path('benchmark/runs/my-experiment-v1/meta.json').read_text())
print('Status:', meta['status'])
print('Completed:', meta['phases_completed'])
print('In progress:', meta.get('phases_in_progress', []))
"
```

---

## 9. Fault Tolerance

The pipeline writes each item immediately to disk. If a run crashes mid-phase, restart with `--continue` to pick up from exactly where it left off (see [Resuming Interrupted Runs](01_running_experiments.md#10-resuming-interrupted-runs)).

---

## 10. Resuming Interrupted Runs

```bash
python -m experiments.cli run --config benchmark/medium_benchmark.yaml --continue
```

`--continue` applies:
- **Phase-level skip** — any phase in `phases_completed` is skipped entirely.
- **Item-level skip (Extend mode)** — within active phases, already-written JSONL records are read and only missing items are processed.

This means a crash after 847 of 1,000 items wastes at most one in-flight batch, not the full 847.

**Validation checks on `--continue`:**
- Config ID must match the existing `meta.json` experiment ID.
- A `meta.json` must already exist (ensures you are continuing, not starting fresh).

---

## 11. Cost Estimation

Before running, estimate costs:

```
Phase 3 calls = n_teachers × n_tasks × datapoints_per_task
Phase 4 calls = n_students × (n_teachers × n_tasks × datapoints_per_task)
Phase 5 calls = n_judges   × Phase_4_calls
Total calls   = Phase3 + Phase4 + Phase5
```

For `medium_benchmark.yaml` (5 models all roles, 4 tasks, 20 datapoints):
```
Phase 3:   5 × 4 × 20         =   400  calls
Phase 4:   5 × 400            = 2,000  calls
Phase 5:   5 × 2,000          = 10,000 calls
Total:                        = 12,400 calls
```

At `gpt-4o-mini` rates (~$0.15/1M input tokens, ~$0.60/1M output), a full medium run costs approximately **$1.80–$2.50**.
