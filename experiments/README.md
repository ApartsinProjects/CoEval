# experiments/ — Evaluation Experiment Runner (EER)

This package implements the **EER pipeline** (`coeval run`): it reads a YAML config,
orchestrates the 5-phase evaluation pipeline, and writes results to an
**Experiment Storage Set (EES)** on disk.

---

## Package Contents

```
experiments/
├── cli.py              ← `coeval run` + `coeval analyze` CLI entry point
├── config.py           ← YAML loading, ExperimentConfig dataclasses, validation V-01..V-17
├── label_eval.py       ← LabelEvaluator: classification/IE accuracy without LLM judge
├── logger.py           ← RunLogger: timestamped output to file and console
├── prompts.py          ← Canonical prompt templates and resolution logic
├── runner.py           ← Pipeline orchestrator: iterates phases, manages pool/storage/logger
├── storage.py          ← ExperimentStorage: all filesystem I/O for the EES
│
├── interfaces/         ← Model backends
│   ├── base.py             ← Abstract ModelInterface (generate method contract)
│   ├── openai_iface.py     ← OpenAI Chat Completions (retry, quota, role overrides)
│   ├── anthropic_iface.py  ← Anthropic Messages API backend
│   ├── anthropic_batch.py  ← Anthropic Message Batches API runner (50cheaper)
│   ├── gemini_iface.py     ← Google Gemini backend
│   ├── gemini_batch.py     ← Gemini concurrent pseudo-batch runner
│   ├── huggingface_iface.py  ← HuggingFace transformers.pipeline backend
│   ├── pool.py             ← ModelPool: lazy-loads and caches one interface per (model, role)
│   ├── probe.py            ← Model availability probe (full/resume/disable modes)
│   └── cost_estimator.py   ← Cost & time estimator with per-model pricing tables
│
├── phases/             ← 5-phase pipeline implementations
│   ├── utils.py        ← Shared helpers: JSON extraction, LLM call wrappers, QuotaTracker
│   ├── phase1.py       ← Attribute mapping (static or LLM-generated)
│   ├── phase2.py       ← Rubric mapping (static, auto, or extend)
│   ├── phase3.py       ← Data generation — teachers produce (prompt, response) pairs
│   ├── phase4.py       ← Response collection — students answer each prompt
│   └── phase5.py       ← Evaluation — judges score student responses
│
├── configs/            ← Example YAML experiment configurations
├── scripts/            ← Research and utility scripts
├── tests/              ← Unit tests (run with: python -m pytest experiments/tests/)
│   ├── test_label_eval.py          ← Label eval tests (multiclass, multilabel, IE)
│   ├── test_probe_and_estimator.py ← Probe and cost estimator tests
│   ├── test_phase4_phase5.py       ← Phase 4 & 5 unit tests
│   └── test_storage_extended.py    ← Extended storage tests
└── docs/               ← User manual + COEVAL-SPEC-001
```

---

## The 5-Phase Pipeline

```
Phase 1  attribute_mapping    ← attributes/  (per-task attribute catalogues)
Phase 2  rubric_mapping       ← rubric/      (per-task evaluation rubrics)
Phase 3  data_generation      ← datapoints/  (teacher-generated prompt+response pairs)
Phase 4  response_collection  ← responses/   (student answers to each prompt)
Phase 5  evaluation           ← evaluations/ (judge scores per student response)
```

Each phase appends to its folder in the EES. Interrupted runs can be resumed;
completed phases can be kept or extended.

---

## Key Classes

| Class | Module | Role |
|-------|--------|------|
| `ExperimentConfig` | `config.py` | Top-level config dataclass (models, tasks, experiment) |
| `ModelConfig` | `config.py` | Per-model config: interface, parameters, roles, role_parameters |
| `TaskConfig` | `config.py` | Per-task config: attributes, rubric, sampling, prompt_library |
| `ExperimentStorage` | `storage.py` | All EES read/write: datapoints, responses, evaluations, metadata |
| `RunLogger` | `logger.py` | Timestamped log to `experiment.log` + console |
| `ModelPool` | `interfaces/pool.py` | Lazy-loads and caches interfaces; applies role_parameters |
| `ModelInterface` | `interfaces/base.py` | Abstract base: `generate(prompt) -> str` |
| `QuotaTracker` | `phases/utils.py` | Enforces per-model `max_calls` quotas |
| `LabelEvaluator` | `label_eval.py` | Score classification/IE tasks via label matching (no LLM) |
| `ModelProbe` | `interfaces/probe.py` | Sends a canary call to each model before the run starts |
| `CostEstimator` | `interfaces/cost_estimator.py` | Estimates token cost and wall-clock time before a run |

---

## Supported Model Backends

| Interface name | Class | When to use |
|----------------|-------|-------------|
| `openai` | `OpenAIInterface` | GPT-4o-mini, GPT-3.5-turbo, fine-tuned models |
| `anthropic` | `AnthropicInterface` | Claude 3/3.5/4 family via Messages API |
| `anthropic_batch` | `AnthropicBatchRunner` | Same Claude models at 50% cost via Message Batches API |
| `gemini` | `GeminiInterface` | Google Gemini models via the Gemini API |
| `gemini_batch` | `GeminiBatchRunner` | Gemini models with concurrent pseudo-batching |
| `huggingface` | `HuggingFaceInterface` | Any model on the HF Hub via `transformers.pipeline` |

---

## Label Evaluation (No LLM Judge)

For classification and information-extraction tasks where ground-truth labels are
available, `label_eval.py` provides `LabelEvaluator` — a zero-cost alternative
to an LLM judge.

**Supported task types**

| Mode | Use case | Score |
|------|----------|-------|
| Multiclass | Single predicted label vs. single ground-truth label | 0 or 1 (exact match) |
| Multilabel | Predicted set vs. ground-truth set | F1 (token-level) |
| Information extraction (IE) | Predicted spans/entities vs. ground-truth spans | Span-level F1 |

**Config wiring**

Add `label_attributes` to any task block to activate label evaluation for that task.
The list names the keys in each datapoint whose values are the ground-truth labels:

```yaml
tasks:
  - name: intent_classification
    label_attributes:
      - intent          # ground-truth key in the datapoint
```

When `label_attributes` is non-empty, Phase 5 skips the LLM judge for that task
and routes scoring through `LabelEvaluator` instead.

---

## Model Probe

`interfaces/probe.py` contains `ModelProbe`, which sends a short canary generation
to every model that will be used in a run before any phase work begins.
This surfaces authentication errors, missing model IDs, and quota problems early
rather than mid-run.

**Probe modes**

| Mode | Behaviour |
|------|-----------|
| `full` | Probe every model in the config |
| `resume` | Probe only models not yet seen in completed phases |
| `disable` | Skip probing entirely |

**On-failure actions**

| Setting | Behaviour |
|---------|-----------|
| `abort` | Raise an error and stop the run (default) |
| `warn` | Print a warning and continue |

**Config keys**

```yaml
experiment:
  probe_mode: full          # full | resume | disable
  probe_on_fail: abort      # abort | warn
```

**CLI flags**

```bash
--probe {disable,full,resume}   # set probe mode
--probe-on-fail {abort,warn}    # set on-failure action
--skip-probe                    # deprecated alias for --probe disable
```

---

## Cost Estimator

`interfaces/cost_estimator.py` contains `CostEstimator`, which samples a small
number of prompts from each model/phase combination, measures token usage, and
projects the total cost and wall-clock time for the full run before any real
work is done.

**Config keys**

```yaml
experiment:
  estimate_cost: true       # run cost estimation before the pipeline
  estimate_samples: 3       # number of sample calls per model for calibration
```

**CLI flags**

```bash
--estimate-only             # print the cost estimate and exit (no pipeline run)
--estimate-samples N        # override estimate_samples from config
```

The estimator uses a built-in pricing table that covers OpenAI, Anthropic, and
Gemini models. Unknown models fall back to a configurable default rate.

---

## Batch Interfaces

Two interface back-ends support batch submission for reduced cost and higher
throughput.

### Anthropic Message Batches (`anthropic_batch`)

Wraps the [Anthropic Message Batches API](https://docs.anthropic.com/en/docs/message-batches).
Requests are submitted as a single batch and polled until complete; the result is
returned in the same format as the standard `anthropic` interface.
Cost is 50% of the per-request price for supported models.

### Gemini Concurrent Pseudo-Batch (`gemini_batch`)

The Gemini API does not have a native batch endpoint. `GeminiBatchRunner` submits
requests concurrently with a configurable concurrency cap and aggregates results,
providing batch-like throughput while staying within rate limits.

**Enabling batch interfaces per phase**

```yaml
experiment:
  batch:
    anthropic:
      phase3: true    # use anthropic_batch for Phase 3 (data generation)
      phase5: true    # use anthropic_batch for Phase 5 (evaluation)
    gemini:
      phase4: true    # use gemini_batch for Phase 4 (response collection)
```

---

## Config Validation (V-01 through V-17)

`config.py` runs a suite of named validation checks when loading a YAML config.
The full set of rules is:

| Rule | What it checks |
|------|---------------|
| V-01 | `models` list is non-empty |
| V-02 | `tasks` list is non-empty |
| V-03 | Every model has a unique `name` |
| V-04 | Every task has a unique `name` |
| V-05 | Every model `interface` resolves to a known backend |
| V-06 | Each model has at least one role (`teacher`, `student`, or `judge`) |
| V-07 | At least one model carries the `teacher` role |
| V-08 | At least one model carries the `student` role |
| V-09 | At least one model carries the `judge` role, unless all tasks use `label_attributes` |
| V-10 | `max_items` is a positive integer when present |
| V-11 | Run directory does not already exist (suppressed in `--continue` mode) |
| V-12 | `meta.json` exists and is readable when `--continue` is used |
| V-13 | `probe_mode` is one of `disable`, `full`, `resume` |
| V-14 | `probe_on_fail` is one of `abort`, `warn` |
| V-15 | `estimate_samples` is a positive integer when `estimate_cost` is true |
| V-16 | `label_attributes` values are strings when present on a task |
| V-17 | Batch flags reference known interface names |

---

## Quick Commands

```bash
# Validate config (no LLM calls)
coeval run --config experiments/configs/local_smoke_test.yaml --dry-run

# Full run
coeval run --config experiments/configs/local_smoke_test.yaml

# Resume an interrupted run
coeval run --config experiments/configs/local_smoke_test.yaml --resume local-smoke-test-v2

# Probe all models, then run
coeval run --config experiments/configs/local_smoke_test.yaml --probe full

# Print cost estimate and exit without running
coeval run --config experiments/configs/local_smoke_test.yaml --estimate-only

# Print cost estimate calibrated with 5 sample calls
coeval run --config experiments/configs/local_smoke_test.yaml --estimate-only --estimate-samples 5

# Run tests
python -m pytest experiments/tests/ -v
```

---

## Documentation

| Document | Description |
|----------|-------------|
| `docs/running_experiments.md` | **User manual** — config reference, phase modes, use-case examples, FAQ |
| `docs/spec_claude.md` | **COEVAL-SPEC-001** — formal EER specification |
| `configs/` | Example YAML configurations with inline comments |
| `../../docs/developer_guide.md` | Full developer guide covering both EER and EEA |
