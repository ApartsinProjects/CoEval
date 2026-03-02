# CoEval — Developer Guide

Architecture, module reference, and step-by-step guides for adding model providers,
analysis reports, benchmark loaders, and new pipeline phases.

---

## Table of Contents

1. [Repository Layout](#1-repository-layout)
2. [Architecture Overview](#2-architecture-overview)
3. [Module Reference](#3-module-reference)
   - 3.1 [`Code/runner/config.py`](#31-coderunnerconfig.py)
   - 3.2 [`Code/runner/storage.py`](#32-coderunnerstorage.py)
   - 3.3 [`Code/runner/prompts.py`](#33-coderunnerprompts.py)
   - 3.4 [`Code/runner/logger.py`](#34-coderunnerlogger.py)
   - 3.5 [`Code/runner/runner.py`](#35-coderunnerrunner.py)
   - 3.6 [`Code/runner/cli.py`](#36-coderunnercli.py)
   - 3.7 [`Code/runner/commands/`](#37-coderunnercommands)
   - 3.8 [`Code/runner/label_eval.py`](#38-coderunnerlabel_eval.py)
   - 3.9 [`Code/runner/interfaces/base.py`](#39-coderunnerinterfacesbase.py)
   - 3.10 [Real-time interfaces](#310-real-time-interfaces)
   - 3.11 [Batch runners](#311-batch-runners)
   - 3.12 [`Code/runner/interfaces/probe.py`](#312-coderunnerinterfacesprobe.py)
   - 3.13 [`Code/runner/interfaces/cost_estimator.py`](#313-coderunnerinterfacescost_estimator.py)
   - 3.14 [`Code/runner/interfaces/pool.py`](#314-coderunnerinterfacespool.py)
   - 3.15 [`Code/runner/interfaces/registry.py`](#315-coderunnerinterfacesregistry.py)
   - 3.16 [`Code/runner/phases/utils.py`](#316-coderunnerphaseutils.py)
   - 3.17 [`Code/runner/phases/phase{1–5}.py`](#317-coderunnerphases-phase15)
   - 3.18 [`Code/analyzer/main.py`](#318-codeanalyzermain.py)
   - 3.19 [`Code/analyzer/loader.py`](#319-codeanalyzerloader.py)
   - 3.20 [`Code/analyzer/reports/`](#320-codeanalyzerreports)
4. [Data Flow Walkthrough](#4-data-flow-walkthrough)
5. [ID and File Naming Conventions](#5-id-and-file-naming-conventions)
6. [Error Handling Strategy](#6-error-handling-strategy)
7. [How To: Add a Real-Time Model Provider](#7-how-to-add-a-real-time-model-provider)
8. [How To: Add a Batch Runner](#8-how-to-add-a-batch-runner)
9. [How To: Add an Analysis Report](#9-how-to-add-an-analysis-report)
10. [How To: Add a Benchmark Loader](#10-how-to-add-a-benchmark-loader)
11. [How To: Add a Pipeline Phase](#11-how-to-add-a-pipeline-phase)
12. [Testing](#12-testing)
13. [Frequently Asked Questions](#13-frequently-asked-questions)

---

## 1. Repository Layout

```
Code/runner/                         ← pipeline package  (runner.* namespace)
├── __init__.py
├── cli.py                           # CLI entry point — all coeval subcommands
├── config.py                        # Config dataclasses, YAML load, V-01..V-17 validation
├── logger.py                        # RunLogger: timestamped log to file + console
├── prompts.py                       # Canonical prompt templates + resolution logic
├── runner.py                        # Orchestrator: iterates phases, wires storage/logger/pool
├── storage.py                       # ExperimentStorage: all filesystem I/O
├── label_eval.py                    # LabelEvaluator: exact-match metrics for classification tasks
│
├── commands/                        # Standalone CLI command implementations
│   ├── describe_cmd.py              # coeval describe  — HTML planning view
│   ├── generate_cmd.py              # coeval generate  — single-model generation
│   ├── ingest_cmd.py                # coeval ingest    — benchmark JSONL ingest
│   ├── models_cmd.py                # coeval models    — list provider models
│   ├── plan_cmd.py                  # coeval plan      — cost/phase dry run
│   ├── probe_cmd.py                 # coeval probe     — standalone availability probe
│   ├── repair_cmd.py                # coeval repair    — fix corrupted artifacts
│   ├── status_cmd.py                # coeval status    — experiment dashboard + batch fetching
│   └── wizard_cmd.py                # coeval wizard    — interactive config setup
│
├── interfaces/
│   ├── __init__.py                  # Re-exports + create_batch_runner() factory
│   ├── base.py                      # Abstract ModelInterface (generate method)
│   ├── openai_iface.py              # OpenAI Chat Completions
│   ├── anthropic_iface.py           # Anthropic Messages API
│   ├── gemini_iface.py              # Google Gemini (generativeai)
│   ├── huggingface_iface.py         # Local HuggingFace transformers.pipeline (GPU)
│   ├── openai_compat_iface.py       # OpenAI-compatible: groq, deepseek, cohere, etc.
│   ├── azure_openai_iface.py        # Azure OpenAI
│   ├── azure_ai_iface.py            # Azure AI Inference (models.ai.azure.com)
│   ├── bedrock_iface.py             # AWS Bedrock real-time (native API key)
│   ├── vertex_iface.py              # Google Vertex AI real-time
│   ├── openai_batch.py              # OpenAI Batch API runner
│   ├── anthropic_batch.py           # Anthropic Message Batches runner
│   ├── gemini_batch.py              # Gemini concurrent pseudo-batch runner
│   ├── azure_batch.py               # Azure OpenAI Batch API runner
│   ├── bedrock_batch.py             # AWS Bedrock Model Invocation Jobs runner
│   ├── vertex_batch.py              # Google Vertex AI Batch Prediction runner
│   ├── mistral_batch.py             # Mistral Batch API runner
│   ├── probe.py                     # run_probe(): lightweight availability check
│   ├── cost_estimator.py            # estimate_experiment_cost(), PRICE_TABLE
│   ├── pool.py                      # ModelPool: lazy-load + cache interface instances
│   └── registry.py                  # Credential resolution, auto-routing, model listing
│
├── phases/
│   ├── __init__.py
│   ├── utils.py                     # _extract_json, call_llm_json/word, mergers, QuotaTracker
│   ├── phase1.py                    # Attribute Mapping
│   ├── phase2.py                    # Rubric Mapping
│   ├── phase3.py                    # Data Generation
│   ├── phase4.py                    # Response Collection
│   └── phase5.py                    # Evaluation
│
└── benchmarks/                      # Benchmark adapter helpers (not benchmark loaders)

Code/analyzer/                       ← analysis & reporting package  (analyzer.* namespace)
├── __init__.py
├── main.py                          # run_analyze() entry point for coeval analyze
├── loader.py                        # load_ees(): read phase 5 JSONL → EESDataModel
├── metrics.py                       # ICC, kappa, score normalisation
├── calibration.py                   # Judge calibration and drift analysis
├── paper_tables.py                  # LaTeX / CSV paper table generators
└── reports/
    ├── html_base.py                 # Shared Plotly HTML utilities, get_plotly_js()
    ├── index_page.py                # Main dashboard HTML (links to all sub-reports)
    ├── summary_report.py            # Run metadata summary
    ├── coverage.py                  # Attribute coverage stacked-bar charts
    ├── student_report.py            # Per-student score breakdowns and heatmaps
    ├── teacher_report.py            # Per-teacher source quality and coverage
    ├── judge_report.py              # Judge bias, calibration, inter-rater reliability
    ├── consistency.py               # Inter-judge ICC agreement and drift
    ├── robust.py                    # Robust summary: rankings + confidence bounds
    ├── score_dist.py                # Score distribution histograms
    ├── interaction.py               # Teacher × Student pair quality heatmap
    └── excel.py                     # Complete Excel workbook export

Public/benchmark/                    ← benchmark Python package  (benchmark.* namespace)
├── __init__.py
├── setup_mixed.py                   # One-time setup: ingest all mixed-benchmark datasets
├── setup_education.py               # One-time setup: ingest education datasets
├── loaders/
│   ├── __init__.py                  # Loader registry + load_benchmark() dispatcher
│   ├── base.py                      # BenchmarkLoader abstract base
│   ├── xsum.py                      # XSum summarisation (EdinburghNLP/xsum)
│   ├── aeslc.py                     # Email subject line (aeslc)
│   ├── arc_challenge.py             # ARC Challenge QA
│   ├── race.py                      # RACE reading comprehension
│   ├── sciq.py                      # SciQ science QA
│   ├── codesearchnet.py             # CodeSearchNet code search
│   └── wikitablequestions.py        # WikiTableQuestions table QA
└── compute_scores.py                # Populate benchmark_native_score in Phase 3 JSONL

Config/
└── provider_pricing.yaml            # Pricing tables and auto_routing for all 18 interfaces

Runs/                                # One subfolder per experiment config
├── mixed/mixed.yaml
├── education/education.yaml
├── medium-benchmark/medium_benchmark.yaml
└── ...

Tests/
├── runner/                          # Unit tests for runner.* package
├── benchmark/                       # Unit tests for benchmark.* package
├── analyzer/                        # Unit + Playwright tests for analyzer.* package
└── test_structural_integrity.py     # Layout, imports, path constant verification

docs/
├── concepts.md                      # Concept glossary
├── developer_guide.md               # This file
├── cli_reference.md                 # CLI option reference
├── tutorial.md                      # End-to-end walkthrough
└── README/                          # 13-section user guide (01-overview … 13-documentation)
```

---

## 2. Architecture Overview

```
CLI (cli.py)
  ├─► coeval run      → load_config() → validate_config() → run_experiment()
  ├─► coeval probe    → commands/probe_cmd.py    → run_probe()
  ├─► coeval plan     → commands/plan_cmd.py     → estimate_experiment_cost()
  ├─► coeval status   → commands/status_cmd.py   → reads experiment folder
  ├─► coeval repair   → commands/repair_cmd.py   → validates + patches artifacts
  ├─► coeval describe → commands/describe_cmd.py → HTML planning view
  ├─► coeval wizard   → commands/wizard_cmd.py   → interactive config builder
  └─► coeval analyze  → Code/analyzer/main.py    → run_analyze()

run_experiment() [runner.py]
  │
  ├─ ExperimentStorage.initialize()   [storage.py]
  ├─ RunLogger()                      [logger.py]
  ├─ ModelPool(provider_keys)         [interfaces/pool.py]
  ├─ QuotaTracker()                   [phases/utils.py]
  ├─ run_probe()                      [interfaces/probe.py]           pre-flight
  ├─ estimate_experiment_cost()       [interfaces/cost_estimator.py]  optional
  │
  └─ for phase_id in PHASE_IDS:
        runner_fn(cfg, storage, logger, pool, quota, phase_mode)
              │
              ├─ Phase 1: run_phase1()   → phase1_attributes/{task}.{kind}_attrs.json
              ├─ Phase 2: run_phase2()   → phase2_rubric/{task}.rubric.json
              ├─ Phase 3: run_phase3()   → phase3_datapoints/{task}__{teacher}.datapoints.jsonl
              ├─ Phase 4: run_phase4()   → phase4_responses/{task}__{teacher}__{student}.responses.jsonl
              └─ Phase 5: run_phase5()   → phase5_evaluations/{task}__{teacher}__{judge}.evaluations.jsonl

run_analyze() [Code/analyzer/main.py]
  ├─ load_ees(run_path) → EESDataModel
  └─ report writers (one per subcommand):
       all / dashboard / student-report / teacher-report / judge-report /
       judge-consistency / coverage-summary / score-distribution /
       interaction-matrix / robust-summary / complete-report
```

Every phase function has the **same signature**:

```python
def run_phaseN(
    cfg:        CoEvalConfig,
    storage:    ExperimentStorage,
    logger:     RunLogger,
    pool:       ModelPool,
    quota:      QuotaTracker,
    phase_mode: str,
) -> None: ...
```

This uniformity lets `runner.py` iterate over phases in a loop and makes adding a new phase zero-cost to the orchestrator.

---

## 3. Module Reference

### 3.1 `Code/runner/config.py`

**Purpose:** Parse the YAML experiment config into typed dataclasses and enforce all 17 validation rules.

#### Dataclasses

```
CoEvalConfig
├── models:     list[ModelConfig]
├── tasks:      list[TaskConfig]
└── experiment: ExperimentConfig

ModelConfig
  name, interface, parameters, roles, access_key, role_parameters, batch_enabled

TaskConfig
  name, description, output_description, target_attributes, nuanced_attributes,
  sampling (SamplingConfig), rubric, evaluation_mode, prompt_library, label_attributes

SamplingConfig
  target ([min,max] | "all"), nuance ([min,max]), total (int)

ExperimentConfig
  id, storage_folder, resume_from, phases, log_level, quota,
  probe_mode, probe_on_fail, estimate_cost, estimate_samples, batch
```

#### Key functions

**`load_config(path) → CoEvalConfig`**
Opens the YAML, calls `_parse_config()`, stores the raw dict on `cfg._raw`, returns the config.

**`validate_config(cfg, continue_in_place, _skip_folder_validation) → list[str]`**
Applies V-01 through V-17. Returns error strings; never raises.
- `continue_in_place=True` — suppresses V-11 (folder must not exist), activates V-14 (meta.json must exist).
- `_skip_folder_validation=True` — suppresses V-11 and V-14; used by standalone commands.

**`CoEvalConfig.get_models_by_role(role) → list[ModelConfig]`**
Returns all models carrying the given role. Used by every phase.

**`ModelConfig.get_parameters_for_role(role) → dict`**
Returns base `parameters` deep-merged with `role_parameters[role]`.

#### Key constants

```python
VALID_INTERFACES       # all 18 supported interface names
BATCH_CAPABLE_INTERFACES  # openai, anthropic, gemini, azure_openai, bedrock, vertex, mistral
PHASE_IDS              # ['attribute_mapping', 'rubric_mapping', 'data_generation',
                       #  'response_collection', 'evaluation']
VALID_PHASE_MODES      # New | Keep | Extend | Model
```

---

### 3.2 `Code/runner/storage.py`

**Purpose:** All filesystem I/O for one experiment. Phases never touch the disk directly.

#### `ExperimentStorage(storage_folder, experiment_id)`

Sets `self.run_path = Path(storage_folder) / experiment_id` and pre-computes all sub-paths.

**`initialize(config_raw, resume_from_id, source_storage_folder, continue_in_place)`**
Creates the folder tree (`phase1_attributes/` … `phase5_evaluations/`), writes `config.yaml` and `meta.json`.
- `resume_from_id` — copies Phase 1 and Phase 2 artifacts from a source experiment.
- `continue_in_place=True` — `exist_ok=True` on all `mkdir` calls; skips overwriting existing `config.yaml` / `meta.json`.

| Phase | Write | Read | Exists? |
|-------|-------|------|---------|
| 1 | `write_target_attrs(task, attrs)` | `read_target_attrs(task)` | `target_attrs_exist(task)` |
| 1 | `write_nuanced_attrs(task, attrs)` | `read_nuanced_attrs(task)` | `nuanced_attrs_exist(task)` |
| 2 | `write_rubric(task, rubric)` | `read_rubric(task)` | `rubric_exists(task)` |
| 3 | `append_datapoint(task, teacher, record)` | `read_datapoints(task, teacher)` | `count_datapoints(task, teacher)` |
| 4 | `append_response(task, teacher, student, record)` | `read_responses(...)` | `response_file_exists(...)` |
| 5 | `append_evaluation(task, teacher, judge, record)` | `read_evaluations(...)` | `evaluation_file_exists(...)` |

**`update_meta(phase_started, phase_completed, status)`** — Reads, patches, and rewrites `meta.json`.
**`read_meta() → dict`** — Used by `--continue` and `coeval status`.
**Batch tracking:** `add_pending_batch()`, `read_pending_batches()`, `remove_pending_batch()`, `update_pending_batch_status()`.

---

### 3.3 `Code/runner/prompts.py`

**Purpose:** Canonical prompt templates and resolution logic.

#### `TEMPLATES: dict[str, str]`

| ID | Used in phase | Key slots |
|----|--------------|-----------|
| `map_target_attrs` | 1 | `{task_description}` |
| `map_nuanced_attrs` | 1 | `{task_description}` |
| `autorubric` | 2 | `{task_description}`, `{output_description}` |
| `sample` | 3 | `{task_description}`, `{output_description}`, `{target_attributes}`, `{nuanced_attributes}` |
| `test` | 4 | `{input}`, `{task_description}`, `{output_description}` |
| `evaluate_single` | 5 | `{task_description}`, `{output_description}`, `{input}`, `{target_attributes}`, `{reference_response}`, `{response}`, `{rubric}` |
| `evaluate_per_factor` | 5 | same minus `{rubric}`, plus `{rubric_factor_name}`, `{rubric_factor_description}` |

#### `get_prompt(prompt_id, task_prompt_library, model_name, variables) → str`

Resolution order:
1. `task_prompt_library[f"{prompt_id}.{model_name}"]` — model-specific override
2. `task_prompt_library[prompt_id]` — task-level override
3. `TEMPLATES[prompt_id]` — canonical fallback

Then calls `template.format(**variables)`. Literal `{` / `}` in YAML overrides must be doubled: `{{` / `}}`.

---

### 3.4 `Code/runner/logger.py`

**Purpose:** Timestamped logger writing to `run.log` and optionally to the console.

#### `RunLogger(log_path, min_level='INFO', console=True)`

Pass `os.devnull` as `log_path` for commands that have no run folder.
Lines are formatted as `{ISO-UTC} [{LEVEL}] {message}`.
`WARNING` and `ERROR` go to `sys.stderr`; all others to `sys.stdout`.
On Windows, `UnicodeEncodeError` on console output is caught and re-emitted with `errors='replace'`.

---

### 3.5 `Code/runner/runner.py`

**Purpose:** Top-level experiment orchestrator.

#### `run_experiment(cfg, dry_run, continue_in_place, only_models, skip_probe, probe_mode, probe_on_fail, estimate_only, estimate_samples) → int`

1. Creates `ExperimentStorage` and calls `initialize()`.
2. Creates `RunLogger`, `ModelPool(cfg._provider_keys)`, `QuotaTracker(cfg.experiment.quota)`.
3. Runs the pre-flight probe unless disabled.
4. Optionally runs cost estimation.
5. Iterates `PHASE_IDS`; for each phase calls `_PHASE_RUNNERS[phase_id](cfg, storage, logger, pool, quota, mode)`.
6. Updates `meta.json` phase-by-phase; writes `status: completed` on success.

`_PHASE_RUNNERS` maps each phase ID to its `run_phaseN()` function.
`_CONTINUE_MODE` maps phase IDs to the mode used by `--continue` (`Keep` or `Extend`).

#### `print_execution_plan(cfg)`

Prints a formatted summary of models, tasks, phases, and estimated call counts — used by `coeval plan` before cost estimation.

---

### 3.6 `Code/runner/cli.py`

**Purpose:** `argparse`-based entry point for all `coeval` subcommands.

The `main()` function:
1. Resolves the provider key file path (flag → env var → project root → home dir).
2. Dispatches to the appropriate command handler.

Subcommands and their handlers:

| Subcommand | Handler module |
|-----------|---------------|
| `run` | `runner.py::run_experiment` |
| `probe` | `commands/probe_cmd.py::cmd_probe` |
| `plan` | `commands/plan_cmd.py::cmd_plan` |
| `status` | `commands/status_cmd.py::cmd_status` |
| `repair` | `commands/repair_cmd.py::cmd_repair` |
| `describe` | `commands/describe_cmd.py::cmd_describe` |
| `wizard` | `commands/wizard_cmd.py::cmd_wizard` |
| `generate` | `commands/generate_cmd.py::cmd_generate` |
| `ingest` | `commands/ingest_cmd.py::cmd_ingest` |
| `models` | `commands/models_cmd.py::cmd_models` |
| `analyze` | `Code/analyzer/main.py::run_analyze` |

---

### 3.7 `Code/runner/commands/`

Each file in this directory implements one `cmd_*` function.

| File | Key function | What it does |
|------|-------------|-------------|
| `probe_cmd.py` | `cmd_probe` | Runs `run_probe()` against a config; prints per-model pass/fail |
| `plan_cmd.py` | `cmd_plan` | Runs `estimate_experiment_cost()`; prints phase plan + cost table |
| `status_cmd.py` | `cmd_status` | Reads `meta.json` and JSONL counts; shows a live experiment dashboard |
| `repair_cmd.py` | `cmd_repair` | Scans experiment artifacts; patches truncated JSONL, missing phase dirs |
| `describe_cmd.py` | `cmd_describe` | Generates a standalone HTML planning document from a config |
| `wizard_cmd.py` | `cmd_wizard` | Interactive questionnaire that writes a ready-to-run YAML config |
| `generate_cmd.py` | `cmd_generate` | Single-model generation utility for prompt testing |
| `ingest_cmd.py` | `cmd_ingest` | Converts a benchmark dataset into Phase 3 JSONL format |
| `models_cmd.py` | `cmd_models` | Lists available models for a provider, optionally filtered |

---

### 3.8 `Code/runner/label_eval.py`

**Purpose:** Exact-match evaluation for classification and information-extraction tasks. Used after Phase 5 when the teacher's `sampled_target_attributes` represent ground-truth labels.

#### `LabelEvaluator`

**`evaluate(predictions, ground_truth) → dict`**
Multiclass accuracy, per-label precision/recall/F1. Accepts both string and single-element-list predictions.

**`evaluate_multilabel(predictions, ground_truth) → dict`**
Hamming accuracy plus per-attribute metrics for multi-label tasks.

---

### 3.9 `Code/runner/interfaces/base.py`

```python
class ModelInterface(ABC):
    @abstractmethod
    def generate(self, prompt: str, parameters: dict) -> str:
        """Call the model and return the text response."""
```

This is the only contract that all 18 provider adapters must fulfil. Role-specific parameter overrides are already merged into `parameters` before `generate()` is called — the interface does not need to know about roles.

---

### 3.10 Real-time Interfaces

Each file in `Code/runner/interfaces/` that ends in `_iface.py` is a real-time provider adapter.

| File | Class | Auth | Notes |
|------|-------|------|-------|
| `openai_iface.py` | `OpenAIInterface` | `OPENAI_API_KEY` | Chat Completions; retries on transient errors |
| `anthropic_iface.py` | `AnthropicInterface` | `ANTHROPIC_API_KEY` | Messages API; requires `max_tokens` |
| `gemini_iface.py` | `GeminiInterface` | `GEMINI_API_KEY` | `google-generativeai` SDK |
| `huggingface_iface.py` | `HuggingFaceInterface` | `HF_TOKEN` | `transformers.pipeline`; requires CUDA GPU |
| `openai_compat_iface.py` | `OpenAICompatInterface` | provider-specific | Covers groq, deepseek, mistral, deepinfra, cerebras, cohere, ollama, huggingface_api, openrouter |
| `azure_openai_iface.py` | `AzureOpenAIInterface` | `AZURE_OPENAI_API_KEY` + endpoint | Azure OpenAI resource |
| `azure_ai_iface.py` | `AzureAIInterface` | `AZURE_AI_API_KEY` + endpoint | Azure AI Inference (models.ai.azure.com) |
| `bedrock_iface.py` | `BedrockInterface` | native Bedrock API key OR IAM | Converse API |
| `vertex_iface.py` | `VertexInterface` | ADC / service account | Vertex AI Gemini real-time |

All real-time interfaces implement the same retry pattern:
1. Call the provider API.
2. On transient errors (rate limit, 502/503/504, timeout) — exponential backoff, up to 3 retries.
3. On fatal errors (invalid API key, model not found) — re-raise immediately.

---

### 3.11 Batch Runners

Batch runners handle the asynchronous submit → poll → download cycle for each provider's batch API.

| File | Class | Provider | Discount |
|------|-------|---------|---------|
| `openai_batch.py` | `OpenAIBatchRunner` | OpenAI Batch API | ~50% |
| `anthropic_batch.py` | `AnthropicBatchRunner` | Message Batches API | ~50% |
| `gemini_batch.py` | `GeminiBatchRunner` | Concurrent thread pool | simulated |
| `azure_batch.py` | `AzureBatchRunner` | Azure OpenAI Batch | ~50% |
| `bedrock_batch.py` | `BedrockBatchRunner` | Model Invocation Jobs | ~50% |
| `vertex_batch.py` | `VertexBatchRunner` | Batch Prediction Jobs | ~50% |
| `mistral_batch.py` | `MistralBatchRunner` | Mistral Batch API | ~50% |

All batch runners expose the same interface:

```python
runner.add(key: str, prompt: str, params: dict) → None
runner.run(description, logger, storage, phase) → dict[str, str]
len(runner)       # number of pending requests
runner.clear()    # discard without submitting
```

`run()` returns `{user_key: response_text}`. Failed individual records map to `''`.
The factory `create_batch_runner(interface, access_key, **kwargs)` in `interfaces/__init__.py` returns the correct runner for any batch-capable interface name.

---

### 3.12 `Code/runner/interfaces/probe.py`

**Purpose:** Verify model reachability before committing to a full run.

#### `run_probe(cfg, logger, mode, on_fail, phases_completed, only_models, probe_results_path) → (dict, set)`

- `mode='full'` — probe every model in the config.
- `mode='resume'` — probe only models needed for incomplete phases.
- `mode='disable'` — skip probing entirely.

Returns `(results_dict, set_of_needed_models)`.
`results_dict` maps `model_name` → `{'ok': bool, 'latency_ms': int, 'error': str|None}`.
Written to `{run_path}/probe_results.json`.

For network interfaces, probes are lightweight single-token calls.
For HuggingFace, probes query Hub metadata without loading weights.

---

### 3.13 `Code/runner/interfaces/cost_estimator.py`

**Purpose:** Pre-run cost and time estimation.

#### Path constant

```python
_PRICING_YAML_PATH = Path(__file__).parent.parent.parent.parent / 'Config' / 'provider_pricing.yaml'
```
(4 parent levels: `interfaces/` → `runner/` → `Code/` → project root → `Config/`)

#### Key exports

**`PRICE_TABLE: dict`** — `{fragment: {input_per_1M, output_per_1M}}` built at import time from the YAML.
**`BATCH_DISCOUNT: dict`** — `{interface: discount_factor}` (0.50 = 50% off).
**`get_prices(model_id) → (input_price, output_price)`** — Longest-fragment match in `PRICE_TABLE`.
**`estimate_experiment_cost(cfg, storage, logger) → dict`** — Runs `estimate_samples` live sample calls per model, then extrapolates to the full experiment. Writes result to `cost_estimate.json`.

---

### 3.14 `Code/runner/interfaces/pool.py`

**Purpose:** Lazy-load and cache `ModelInterface` instances.

#### `ModelPool(provider_keys: dict | None)`

**`get(model_cfg: ModelConfig) → ModelInterface`**
Returns the cached instance for `model_cfg.name`, or creates one on the first call.
HuggingFace instances are cached in their own slot so GPU weights are loaded exactly once.

---

### 3.15 `Code/runner/interfaces/registry.py`

**Purpose:** Credential resolution, key file loading, auto-routing, and model listing.

#### Path constant

```python
_PROJECT_KEYS_FILE = Path(__file__).parent.parent.parent.parent / 'keys.yaml'
```

#### Key functions

**`load_keys_file(path=None) → dict`**
Lookup order: explicit path → `COEVAL_KEYS_FILE` env var → project root `keys.yaml` → `~/.coeval/keys.yaml`.

**`resolve_provider_keys(keys_path=None) → dict`**
Merges key file entries with environment variables into a flat `{provider: key}` dict.

**`load_provider_pricing(path=None) → dict`**
Loads `Config/provider_pricing.yaml`; falls back to `{}` on missing file.

**`resolve_auto_interface(model_id, provider_keys) → str | None`**
Scans `auto_routing` in the pricing YAML; returns the first interface whose fragment matches the model ID and whose credentials are present.

---

### 3.16 `Code/runner/phases/utils.py`

**Purpose:** Shared helpers used by all five phases.

#### `_extract_json(text) → Any`

Three-strategy extraction:
1. `json.loads(text)` directly.
2. Strip leading prose — find first `{` or `[`, parse from there.
3. Bracket window — find first `{` and last `}` (or `[`/`]`), parse that substring.

Single-element lists `[{...}]` are unwrapped to `{...}` after a successful parse.

#### `call_llm_json(iface, prompt, parameters, max_retries=3) → Any`

Calls `iface.generate()`, strips markdown code fences, then calls `_extract_json()`.
Retries on `JSONDecodeError` with doubling delay. Re-raises immediately on non-JSON errors.

#### `call_llm_word(iface, prompt, parameters, valid_words, max_retries=3) → str`

Expects a single word from `valid_words` (`{'High', 'Medium', 'Low'}` by default).
Strips whitespace and punctuation. Used by Phase 5 `per_factor` mode.

#### `extract_prompt_response(data) → tuple[str, str]`

Normalises teacher output. Tries multiple key aliases for both the prompt and response fields.
Raises `KeyError` with a descriptive message if either field cannot be resolved.

#### `merge_attr_maps(*maps) → dict[str, list]`

Union of multiple attribute maps. New values per key are appended; existing values are not duplicated.

#### `merge_rubrics(*rubrics) → dict[str, str]`

Union of rubric dicts. First occurrence wins; later rubrics can only add new factors.

#### `QuotaTracker`

Tracks remaining API call budget per model. `is_exhausted(name)` / `consume(name)`.

---

### 3.17 `Code/runner/phases/` — Phase 1–5

#### Phase 1 — `phase1.py`

`run_phase1()` calls `_resolve_attrs()` twice per task (for `'target'` and `'nuanced'` attribute types). Decision: static dict → write directly; `auto` / `complete` → call all teachers via `call_llm_json`, merge with `merge_attr_maps`. Prompt IDs: `map_target_attrs`, `map_nuanced_attrs`.

#### Phase 2 — `phase2.py`

`run_phase2()` calls `_resolve_rubric()` per task. Decision: static dict → write directly; `auto` → call teachers, merge; `extend` → prepend existing rubric before merge (its factors take priority). Prompt ID: `autorubric`.

#### Phase 3 — `phase3.py`

`run_phase3()` processes every `(task, teacher)` pair. For each pair:
- `Keep` → skip if file exists.
- `Model` → skip if file exists.
- `Extend` → generate only the missing items (`total - existing_count`).
- `New` → generate all `total` items.

For each datapoint: `_sample_attrs()` → `get_prompt('sample')` → `call_llm_json()` → `extract_prompt_response()` → `storage.append_datapoint()`.

Benchmark interface teachers are skipped (data is pre-ingested).
`_MAX_WORKERS = 10` for concurrent generation via `ThreadPoolExecutor`.

#### Phase 4 — `phase4.py`

Processes every `(task, teacher, student)` triple. Checks `get_responded_datapoint_ids()` to skip already-written items on resume. Batch-capable interfaces use `create_batch_runner()` when `batch.{interface}.response_collection` is enabled. HuggingFace runs sequentially.

#### Phase 5 — `phase5.py`

Processes every `(task, teacher, judge)` triple. Checks `get_evaluated_response_ids()` to skip on resume. Supports both `evaluation_mode: single` (one call per response, all rubric dimensions at once) and `evaluation_mode: per_factor` (one call per rubric dimension per response). Batch-capable interfaces use `create_batch_runner()` when `batch.{interface}.evaluation` is enabled.

---

### 3.18 `Code/analyzer/main.py`

**Purpose:** Entry point for `coeval analyze`. Orchestrates loading and report generation.

#### `run_analyze(run_path, out_path, subcommand, judge_selection, agreement_metric, agreement_threshold, teacher_score_formula, benchmark_format, partial_ok, log_level) → int`

1. Validates `run_path` has `meta.json` and `phase5_evaluations/`.
2. Calls `load_ees(run_path)` → `EESDataModel`.
3. Dispatches to the appropriate report writer based on `subcommand`.
4. Returns 0 on success, 1 on error.

Subcommands: `all`, `dashboard`, `student-report`, `teacher-report`, `judge-report`, `judge-consistency`, `coverage-summary`, `score-distribution`, `interaction-matrix`, `robust-summary`, `complete-report`.

`all` runs every report writer in sequence.

---

### 3.19 `Code/analyzer/loader.py`

**Purpose:** Read Phase 5 evaluation JSONL files and assemble an in-memory data model.

#### `load_ees(run_path, partial_ok=False) → EESDataModel`

Reads all `*.evaluations.jsonl` files from `phase5_evaluations/`, parses each record into an `EvalRecord`, and produces an `EESDataModel`.

#### Key dataclasses

**`EvalRecord`**
One Phase 5 record: `response_id`, `datapoint_id`, `task_id`, `teacher_model_id`, `student_model_id`, `judge_model_id`, `scores` (dict), `evaluated_at`, `valid`, `error_codes`, `is_self_judging`, `is_self_teaching`.

**`AnalyticalUnit`**
The primary analytical unit: one `(response, rubric_aspect)` pair with its normalised score. All metrics operate on lists of `AnalyticalUnit`.

**`EESDataModel`**
Unified in-memory model: `run_path`, `meta`, `tasks`, `teachers`, `students`, `judges`, `records`, `analytical_units`, plus convenience accessors.

---

### 3.20 `Code/analyzer/reports/`

Each report module exports one top-level function:

```python
write_<report_name>(model: EESDataModel, out_dir: Path, shared_plotly: Path | None) → None
```

`shared_plotly`, if given, copies the Plotly JS file to a shared location instead of embedding it inline (saves disk space when generating multiple reports).

| Module | Function | Output file |
|--------|---------|------------|
| `index_page.py` | `write_index_page` | `index.html` (main dashboard) |
| `summary_report.py` | `write_run_summary` | `summary/index.html` |
| `student_report.py` | `write_student_report` | `student_report/index.html` |
| `teacher_report.py` | `write_teacher_report` | `teacher_report/index.html` |
| `judge_report.py` | `write_judge_report` | `judge_report/index.html` |
| `consistency.py` | `write_judge_consistency` | `judge_consistency/index.html` |
| `coverage.py` | `write_coverage_summary` | `coverage_summary/index.html` |
| `score_dist.py` | `write_score_distribution` | `score_distribution/index.html` |
| `interaction.py` | `write_interaction_matrix` | `interaction_matrix/index.html` |
| `robust.py` | `write_robust_summary` | `robust_summary/index.html` |
| `excel.py` | `write_complete_report` | `complete_report.xlsx` |

Shared HTML utilities live in `html_base.py`:
- `get_plotly_js(cache_dir)` — downloads or caches `plotly.min.js` (no CDN at render time).
- `build_html_page(title, body_html, plotly_js)` — wraps content in a standard HTML shell.

---

## 4. Data Flow Walkthrough

**Single task, two models (teacher + student + judge)**

```
YAML config
  │
  ▼
load_config() ──► CoEvalConfig
  │
  ▼
run_experiment()
  │
  ├── Phase 1: Teacher calls map_target_attrs prompt
  │     └── Writes: phase1_attributes/sentiment.target_attrs.json
  │                  phase1_attributes/sentiment.nuanced_attrs.json
  │
  ├── Phase 2: Teacher calls autorubric prompt
  │     └── Writes: phase2_rubric/sentiment.rubric.json
  │
  ├── Phase 3: Teacher samples attributes → calls sample prompt per item
  │     └── Writes: phase3_datapoints/sentiment__teacher1.datapoints.jsonl
  │                  (50 records, each: {id, prompt, reference_response, sampled_attrs})
  │
  ├── Phase 4: Student receives each prompt → calls test prompt
  │     └── Writes: phase4_responses/sentiment__teacher1__student1.responses.jsonl
  │                  (50 records, each: {response_id, datapoint_id, response, ...})
  │
  └── Phase 5: Judge scores each response against rubric
        └── Writes: phase5_evaluations/sentiment__teacher1__judge1.evaluations.jsonl
                     (50 records × N rubric factors)
                     (each: {response_id, scores: {factor: High|Medium|Low}, ...})

coeval analyze all
  │
  ▼
load_ees() → EESDataModel
  │
  ├── write_index_page()      → reports/index.html
  ├── write_student_report()  → reports/student_report/index.html
  ├── write_teacher_report()  → reports/teacher_report/index.html
  ├── write_judge_report()    → reports/judge_report/index.html
  ├── ...
  └── write_complete_report() → reports/complete_report.xlsx
```

---

## 5. ID and File Naming Conventions

### Model and task IDs
- Alphanumeric, hyphens, underscores; no spaces. Validated by `_MODEL_NAME_RE` / `_TASK_NAME_RE`.
- Used verbatim in file names — keep them short and readable.

### Record IDs
```
Phase 3 datapoint:   {task_id}__{teacher_id}__{seq:05d}    e.g.  sentiment__gpt4o__00042
Phase 4 response:    {datapoint_id}__s__{student_id}        e.g.  sentiment__gpt4o__00042__s__claude
Phase 5 evaluation:  {response_id}__j__{judge_id}           e.g.  sentiment__gpt4o__00042__s__claude__j__gpt4o
```

The double-underscore `__` separator is reserved; single underscores are safe within component names.

### JSONL file names (under run folder)
```
phase3_datapoints/   {task}__{teacher}.datapoints.jsonl
phase4_responses/    {task}__{teacher}__{student}.responses.jsonl
phase5_evaluations/  {task}__{teacher}__{judge}.evaluations.jsonl
```

---

## 6. Error Handling Strategy

| Layer | Strategy |
|-------|----------|
| Validation (config) | Return list of error strings; caller decides |
| LLM calls (transient) | Exponential backoff, up to 3 retries, then re-raise |
| LLM calls (fatal) | Re-raise immediately (invalid key, model not found) |
| JSON parsing | `call_llm_json` retries up to 3 times on `JSONDecodeError` |
| Phase failures | Individual item failures are logged; phase continues; raises `RuntimeError` only if *zero* useful output was produced |
| Filesystem | `ExperimentStorage` raises `FileExistsError` on conflict without `continue_in_place` |
| Batch jobs | `RuntimeError` on non-terminal batch failure state; in-flight batch IDs tracked in `pending_batches.json` for recovery |

Phases never swallow exceptions silently — every error is logged with model name, task, and error text before any retry or skip.

---

## 7. How To: Add a Real-Time Model Provider

### Step 1 — Create the interface file

Create `Code/runner/interfaces/my_provider_iface.py`:

```python
"""MyProvider model interface."""
from __future__ import annotations
import os
from .base import ModelInterface

# Patterns that indicate a transient (retryable) error
_TRANSIENT = ('rate limit', 'timeout', 'connection', '502', '503')
# Patterns that indicate a fatal (non-retryable) error
_FATAL = ('invalid api key', 'authentication', 'model not found')


class MyProviderInterface(ModelInterface):
    def __init__(self, access_key: str | None = None) -> None:
        self._key = access_key or os.environ.get('MY_PROVIDER_API_KEY', '')
        if not self._key:
            raise ValueError("MY_PROVIDER_API_KEY is required")
        # Import the SDK lazily to avoid hard dependency:
        try:
            from myprovider import Client
            self._client = Client(api_key=self._key)
        except ImportError:
            raise ImportError("myprovider SDK is required: pip install myprovider")

    def generate(self, prompt: str, parameters: dict) -> str:
        import time
        model   = parameters.get('model', 'default-model')
        temp    = float(parameters.get('temperature', 0.7))
        max_tok = int(parameters.get('max_tokens', 512))
        sys_p   = parameters.get('system_prompt')

        for attempt in range(3):
            try:
                response = self._client.complete(
                    model=model, prompt=prompt,
                    temperature=temp, max_tokens=max_tok,
                    system=sys_p,
                )
                return response.text
            except Exception as exc:
                msg = str(exc).lower()
                if any(s in msg for s in _FATAL):
                    raise
                if any(s in msg for s in _TRANSIENT) and attempt < 2:
                    time.sleep(2 ** attempt)
                    continue
                raise
        raise RuntimeError("MyProvider: exhausted retries")
```

### Step 2 — Register in `pool.py`

In `Code/runner/interfaces/pool.py`, add a branch to `_create()`:

```python
elif interface == 'my_provider':
    from .my_provider_iface import MyProviderInterface
    return MyProviderInterface(access_key=access_key)
```

### Step 3 — Register in `config.py`

Add `'my_provider'` to `VALID_INTERFACES`:

```python
VALID_INTERFACES = {
    ...,
    'my_provider',
}
```

### Step 4 — Add credentials to `registry.py`

Add the env var lookup in `resolve_provider_keys()`:

```python
if not keys.get('my_provider'):
    v = os.environ.get('MY_PROVIDER_API_KEY')
    if v:
        keys['my_provider'] = v
```

### Step 5 — Add a probe handler in `probe.py`

```python
elif interface == 'my_provider':
    from .my_provider_iface import MyProviderInterface
    iface = MyProviderInterface(access_key=access_key)
    iface.generate("ping", {"model": model_cfg.parameters.get("model", ""), "max_tokens": 1})
```

### Step 6 — Add pricing to `Config/provider_pricing.yaml`

```yaml
providers:
  my_provider:
    interface: my_provider
    batch_discount: 1.0          # 1.0 = no batch discount
    models:
      my-model-v1:
        input:  0.50             # USD per million input tokens
        output: 1.50
```

### Step 7 — Add the package to `pyproject.toml` (optional)

If the provider SDK is optional:

```toml
[project.optional-dependencies]
my_provider = ["myprovider>=1.0"]
```

### Step 8 — Write a test

Create `Tests/runner/test_my_provider.py` following the pattern in `test_new_providers.py`:
mock `sys.modules['myprovider']` with `patch.dict`, verify `generate()` returns a string.

---

## 8. How To: Add a Batch Runner

### Step 1 — Create the batch runner file

Create `Code/runner/interfaces/my_provider_batch.py`. Implement `add()`, `run()`, `__len__()`, `clear()`:

```python
class MyProviderBatchRunner:
    def __init__(self, access_key=None, poll_seconds=60, **kwargs):
        self._key = access_key
        self._poll = poll_seconds
        self._requests: list[dict] = []
        self._id_to_key: dict[str, str] = {}

    def add(self, key: str, prompt: str, params: dict) -> None:
        custom_id = f"r{len(self._requests)}"
        self._id_to_key[custom_id] = key
        self._requests.append({"id": custom_id, "prompt": prompt, **params})

    def run(self, description="", logger=None, storage=None, phase="") -> dict[str, str]:
        if not self._requests:
            return {}
        # 1. Submit batch to provider
        # 2. Poll until terminal status
        # 3. Download and parse results
        # 4. self.clear()
        # 5. Return {user_key: response_text}
        ...

    def __len__(self): return len(self._requests)
    def clear(self):
        self._requests.clear()
        self._id_to_key.clear()
```

### Step 2 — Register in `interfaces/__init__.py`

```python
from .my_provider_batch import MyProviderBatchRunner

def create_batch_runner(interface, access_key=None, **kwargs):
    ...
    elif interface == 'my_provider':
        return MyProviderBatchRunner(access_key=access_key, **kwargs)
```

### Step 3 — Register in `config.py`

Add `'my_provider'` to `BATCH_CAPABLE_INTERFACES`.

### Step 4 — Write tests

Follow the pattern in `Tests/runner/test_batch_runners.py`: mock the provider SDK via `sys.modules`, test `add()` / `run()` / polling / error cases.

---

## 9. How To: Add an Analysis Report

### Step 1 — Create the report module

Create `Code/analyzer/reports/my_report.py`:

```python
"""My Custom Report — REQ-A-X.X."""
from __future__ import annotations
from pathlib import Path
from ..loader import EESDataModel
from .html_base import build_html_page, get_plotly_js


def write_my_report(
    model: EESDataModel,
    out_dir: Path,
    shared_plotly: Path | None = None,
) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)

    # Build your HTML content (use Plotly figures for interactivity)
    import plotly.graph_objects as go
    fig = go.Figure(...)
    plot_html = fig.to_html(full_html=False, include_plotlyjs=False)

    # Get Plotly JS (cached; no network call if already downloaded)
    plotly_js = get_plotly_js(shared_plotly or out_dir.parent)

    body = f"<h1>My Report</h1>\n{plot_html}"
    html = build_html_page(title="My Report", body_html=body, plotly_js=plotly_js)
    (out_dir / 'index.html').write_text(html, encoding='utf-8')
```

### Step 2 — Register in `Code/analyzer/main.py`

```python
from .reports.my_report import write_my_report

# Add to the dispatch table:
'my-report': lambda: write_my_report(data_model, out_dir / 'my_report', shared_plotly),
```

Also add `'my-report'` to the `all` subcommand sequence.

### Step 3 — Register in `Code/runner/cli.py` (analyze subparser)

Add `'my-report'` to the choices list for the `analyze` subcommand.

### Step 4 — Link from the index page

In `Code/analyzer/reports/index_page.py`, add a card linking to `my_report/index.html`.

### Step 5 — Write tests

Add test class to `Tests/analyzer/test_analyze_reports.py` following the existing pattern: create minimal `EESDataModel` in a `tmp_path`, call `write_my_report()`, assert `index.html` was created and contains expected markers.

---

## 10. How To: Add a Benchmark Loader

Benchmark loaders convert a HuggingFace dataset into CoEval Phase 3 JSONL format.

### Step 1 — Create the loader

Create `Public/benchmark/loaders/my_dataset.py`:

```python
"""MyDataset benchmark loader."""
from __future__ import annotations
from pathlib import Path
from .base import BenchmarkLoader


class MyDatasetLoader(BenchmarkLoader):
    """Loads MyDataset for the <task_name> task."""

    DATASET_NAME = "org/my-dataset"    # HuggingFace dataset ID
    DEFAULT_SPLIT = "validation"

    def load(
        self,
        out_path: Path,
        attribute_map_path: Path | None,
        sample_size: int = 500,
        split: str | None = None,
    ) -> int:
        """Download, sample, and write Phase 3 JSONL.

        Returns the number of records written.
        """
        from datasets import load_dataset
        ds = load_dataset(self.DATASET_NAME, split=split or self.DEFAULT_SPLIT)
        if sample_size and len(ds) > sample_size:
            ds = ds.shuffle(seed=42).select(range(sample_size))

        out_path.parent.mkdir(parents=True, exist_ok=True)
        count = 0
        with out_path.open('w', encoding='utf-8') as fh:
            for i, example in enumerate(ds):
                # Build the prompt and reference response from the dataset fields
                prompt = example['input_text']
                reference = example['target_text']

                # Infer attributes from the example
                attrs = self._infer_attributes(example, attribute_map_path)

                record = {
                    "id": f"my_dataset__{i:05d}",
                    "prompt": prompt,
                    "reference_response": reference,
                    "sampled_target_attributes": attrs,
                    "source": "my_dataset",
                    "interface": "benchmark",
                }
                fh.write(__import__('json').dumps(record, ensure_ascii=False) + '\n')
                count += 1
        return count

    def _infer_attributes(self, example, attribute_map_path) -> dict:
        # Map dataset fields to CoEval attribute keys + values
        return {"difficulty": "medium"}
```

### Step 2 — Register in `Public/benchmark/loaders/__init__.py`

```python
from .my_dataset import MyDatasetLoader

_REGISTRY = {
    ...,
    'my_dataset': MyDatasetLoader,
}
```

### Step 3 — Add an attribute map YAML (optional)

Create `Public/benchmark/configs/my_dataset_attribute_map.yaml`:

```yaml
difficulty: [easy, medium, hard]
domain:     [science, history, general]
```

Pass this path as `attribute_map_path` when calling `load_benchmark('my_dataset', ...)`.

### Step 4 — Add to setup script or document standalone use

In `Public/benchmark/setup_mixed.py` (or create a dedicated setup script):

```python
from benchmark.loaders import load_benchmark
load_benchmark('my_dataset', out_path=Path('Runs/my-run/phase3_datapoints/...'), ...)
```

### Step 5 — Write tests

Add tests to `Tests/benchmark/` mocking `datasets.load_dataset` and verifying the JSONL output format.

---

## 11. How To: Add a Pipeline Phase

### Step 1 — Create the phase module

Create `Code/runner/phases/phaseN.py` following the standard signature:

```python
def run_phaseN(cfg, storage, logger, pool, quota, phase_mode) -> None:
    ...
```

Write output via `storage` methods (add new ones to `ExperimentStorage` if needed).

### Step 2 — Add storage methods

In `Code/runner/storage.py`, add read/write/exists methods for the new phase's artifact type.

### Step 3 — Register in `runner.py`

```python
from .phases.phaseN import run_phaseN

_PHASE_RUNNERS = {
    ...,
    'my_new_phase': run_phaseN,
}
```

Add `'my_new_phase'` to `PHASE_IDS` in `config.py`.

### Step 4 — Add to config validation

In `config.py`, add the new phase ID to any validation rules that check phase names.

---

## 12. Testing

### Running tests

```bash
# Full suite (excludes Playwright)
pytest Tests/ -q

# Runner unit tests only
pytest Tests/runner/ -v

# Benchmark tests only
pytest Tests/benchmark/ -v

# Analyzer tests only
pytest Tests/analyzer/ -v

# Structural integrity (layout, imports, path constants)
pytest Tests/test_structural_integrity.py -v

# Memory-capped run (kills if RSS > 3 GB)
python scripts/run_tests_safe.py Tests/runner Tests/benchmark -q

# Playwright visual tests (requires: playwright install chromium)
pytest Tests/analyzer/test_reports_playwright.py -v
```

### Test structure

```
Tests/
├── runner/
│   ├── test_config.py              # Config parsing and validation rules V-01..V-17
│   ├── test_storage.py             # ExperimentStorage filesystem methods
│   ├── test_storage_extended.py    # Batch tracking, meta updates, error records
│   ├── test_prompts.py             # Template resolution and slot filling
│   ├── test_utils.py               # _extract_json, call_llm_json/word, merge helpers
│   ├── test_phase4_phase5.py       # QuotaTracker, response/evaluation accumulation
│   ├── test_label_eval.py          # LabelEvaluator metrics
│   ├── test_probe_and_estimator.py # Probe modes, PRICE_TABLE, cost estimation
│   ├── test_auto_interface_and_pricing.py  # Auto-routing, pricing YAML, dual-track config
│   ├── test_new_providers.py       # All 18 interface adapters (mocked)
│   ├── test_batch_runners.py       # BedrockBatchRunner and VertexBatchRunner
│   ├── test_benchmarks.py          # Benchmark interface adapter
│   ├── test_repair.py              # Repair command logic
│   └── test_commands.py            # CLI subcommand dispatch
├── benchmark/
│   └── test_compute_scores.py      # Benchmark score computation
├── analyzer/
│   ├── test_loader.py              # EESDataModel loading from JSONL
│   ├── test_metrics.py             # ICC, kappa, score normalisation
│   └── test_analyze_reports.py     # All 11 report writers (55 tests)
└── test_structural_integrity.py    # Layout, imports, path constants, CLI smoke test
```

### Key testing patterns

**Mock optional SDKs via `sys.modules`** to run tests without installing provider packages:

```python
from unittest.mock import MagicMock, patch

def test_my_interface():
    mock_sdk = MagicMock()
    with patch.dict(sys.modules, {'myprovider': mock_sdk}):
        from runner.interfaces.my_provider_iface import MyProviderInterface
        iface = MyProviderInterface(access_key='test-key')
        mock_sdk.Client.return_value.complete.return_value.text = "hello"
        result = iface.generate("ping", {"model": "m", "max_tokens": 5})
    assert result == "hello"
```

**Delete MagicMock objects explicitly** after the `with` block to avoid reference cycles:

```python
del mock_sdk
```

**Use `tmp_path` for filesystem tests** — pytest injects a fresh temporary directory per test.

**The root `conftest.py`** runs `gc.collect()` after every test to reclaim mock cycles.

---

## 13. Frequently Asked Questions

**Q: Where is the pricing data for cost estimation?**
`Config/provider_pricing.yaml` at the project root. The path is embedded in `cost_estimator.py` as `Path(__file__).parent.parent.parent.parent / 'Config' / 'provider_pricing.yaml'` (4 parent levels from `Code/runner/interfaces/` to the project root).

**Q: Where are provider credentials looked up?**
In order: `--keys PATH` flag → `COEVAL_KEYS_FILE` env var → `{project_root}/keys.yaml` → `~/.coeval/keys.yaml`. The project root path is `Path(__file__).parent.parent.parent.parent / 'keys.yaml'` in `registry.py`.

**Q: Why do test dirs have no `__init__.py`?**
Presence of `__init__.py` in test directories causes pytest to install them as part of the `runner` package. That triggers MagicMock trees to be scanned on every `import runner`, causing memory explosions on Windows. The `--import-mode=importlib` flag in `pyproject.toml` makes pytest work correctly without `__init__.py`.

**Q: How do I add `interface: auto` routing for a new provider?**
Add entries to the `auto_routing` section of `Config/provider_pricing.yaml`:
```yaml
auto_routing:
  my-model:
    interface: my_provider
    priority: 5
```
Model IDs are matched by substring (longest match wins).

**Q: How does `--continue` avoid duplicate API calls?**
Phase 4 calls `storage.get_responded_datapoint_ids()` before submitting each student. Phase 5 calls `storage.get_evaluated_response_ids()` before each judge. Both return `set[str]` of already-written IDs; the phase simply skips any item whose ID is in the set.

**Q: Can the analyzer be run independently of the runner?**
Yes. `Code/analyzer/main.py::run_analyze(run_path, ...)` needs only a completed run folder with `meta.json` and `phase5_evaluations/`. It has no dependency on the runner package at runtime.

---

*See also: [Concepts Glossary](concepts.md) · [CLI Reference](cli_reference.md) · [Configuration Guide](README/04-configuration.md) · [Architecture](README/10-architecture.md)*
