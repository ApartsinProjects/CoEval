# CoEval — Developer Guide

This guide explains the codebase architecture, every module, every major class and
function, and the interfaces between them.  Read it to understand the system well
enough to fix bugs, add new phases, or add a new model backend.

---

## Table of Contents

1. [Repository Layout](#1-repository-layout)
2. [Architecture Overview](#2-architecture-overview)
3. [Module Reference](#3-module-reference)
   - 3.1 [`experiments/config.py`](#31-experimentsconfigpy)
   - 3.2 [`experiments/storage.py`](#32-experimentsstoragepy)
   - 3.3 [`experiments/prompts.py`](#33-experimentspromptspy)
   - 3.4 [`experiments/logger.py`](#34-experimentsloggerpy)
   - 3.5 [`experiments/runner.py`](#35-experimentsrunnerpy)
   - 3.6 [`experiments/cli.py`](#36-experimentsclipy)
   - 3.7 [`experiments/commands/`](#37-experimentscommands)
   - 3.8 [`experiments/label_eval.py`](#38-experimentslabel_evalpy)
   - 3.9 [`experiments/interfaces/base.py`](#39-experimentsinterfacesbasepy)
   - 3.10 [`experiments/interfaces/openai_iface.py`](#310-experimentsinterfacesopenai_ifacepy)
   - 3.11 [`experiments/interfaces/anthropic_iface.py`](#311-experimentsinterfacesanthropic_ifacepy)
   - 3.12 [`experiments/interfaces/gemini_iface.py`](#312-experimentsinterfacesgemini_ifacepy)
   - 3.13 [`experiments/interfaces/huggingface_iface.py`](#313-experimentsinterfaceshuggingface_ifacepy)
   - 3.14 [`experiments/interfaces/openai_batch.py`](#314-experimentsinterfacesopenai_batchpy)
   - 3.15 [`experiments/interfaces/anthropic_batch.py`](#315-experimentsinterfacesanthropic_batchpy)
   - 3.16 [`experiments/interfaces/probe.py`](#316-experimentsinterfacesprobepy)
   - 3.17 [`experiments/interfaces/cost_estimator.py`](#317-experimentsinterfacescost_estimatorpy)
   - 3.18 [`experiments/interfaces/pool.py`](#318-experimentsinterfacespoolpy)
   - 3.19 [`experiments/phases/utils.py`](#319-experimentsphasesutispy)
   - 3.20–3.24 `experiments/phases/phase{1–5}.py`
4. [Data Flow Walkthrough](#4-data-flow-walkthrough)
5. [ID Naming Convention](#5-id-naming-convention)
6. [Error Handling Strategy](#6-error-handling-strategy)
7. [Adding a New Model Backend](#7-adding-a-new-model-backend)
8. [Adding a New Phase](#8-adding-a-new-phase)
9. [Testing](#9-testing)
10. [Frequently Asked Questions](#10-frequently-asked-questions)
11. [Benchmark Loaders](#11-benchmark-loaders)

---

## 1. Repository Layout

```
experiments/                     ← main pipeline package (experiments.* namespace)
├── __init__.py
├── cli.py                       # CLI entry point (coeval run/probe/plan/status/analyze)
├── config.py                    # Config dataclasses, YAML loading, validation V-01..V-17
├── logger.py                    # RunLogger: timestamped log to file + console
├── prompts.py                   # Canonical prompt templates + resolution logic
├── runner.py                    # Orchestrator: iterates phases, manages storage/logger/pool
├── storage.py                   # ExperimentStorage: all filesystem I/O
├── label_eval.py                # LabelEvaluator: exact-match evaluation for classification tasks
│
├── commands/                    # Standalone CLI command implementations
│   ├── __init__.py
│   ├── probe_cmd.py             # coeval probe — standalone model availability probe
│   ├── plan_cmd.py              # coeval plan — standalone cost/time estimation
│   └── status_cmd.py           # coeval status — experiment dashboard + batch fetching
│
├── interfaces/
│   ├── __init__.py              # Re-exports ModelInterface and ModelPool
│   ├── base.py                  # Abstract ModelInterface
│   ├── openai_iface.py          # OpenAI Chat Completions backend
│   ├── anthropic_iface.py       # Anthropic Messages backend
│   ├── gemini_iface.py          # Google Gemini backend
│   ├── huggingface_iface.py     # HuggingFace transformers.pipeline backend
│   ├── openai_batch.py          # OpenAI Batch API submit + poll + apply helpers
│   ├── anthropic_batch.py       # Anthropic Message Batches submit + poll + apply helpers
│   ├── probe.py                 # run_probe(): lightweight model availability check
│   ├── cost_estimator.py        # estimate_experiment_cost(), PRICE_TABLE
│   └── pool.py                  # ModelPool: lazy-load + cache interfaces
│
├── phases/
│   ├── __init__.py
│   ├── utils.py                 # Shared helpers: _extract_json, call_llm_json/word, mergers, QuotaTracker
│   ├── phase1.py                # Attribute mapping
│   ├── phase2.py                # Rubric mapping
│   ├── phase3.py                # Data generation
│   ├── phase4.py                # Response collection
│   └── phase5.py                # Evaluation
│
└── tests/                       # Unit tests (pytest, no network/GPU required)
    ├── test_config.py
    ├── test_storage.py
    ├── test_prompts.py
    ├── test_utils.py
    ├── test_phase4_phase5.py
    ├── test_label_eval.py
    ├── test_probe_and_estimator.py
    └── test_commands.py

analysis/                        ← analysis & reporting package (analysis.* namespace)
├── main.py                      # run_analyze() entry point for coeval analyze
├── reports/                     # HTML report generators
├── paper_tables.py              # LaTeX/CSV table generators for paper
└── tests/                       # Analysis unit tests

benchmark/                       ← benchmark configs, loaders, and runs
├── loaders/                     # XSum, CodeSearchNet, AESLC, WikiTableQuestions
├── emit_datapoints.py           # CLI: emit Phase 3 JSONL from datasets
├── compute_scores.py            # Populates benchmark_native_score in Phase 3 JSONL
├── configs/                     # attribute_map YAMLs per benchmark
├── paper_benchmarks.yaml        # Full paper validation config
└── medium_benchmark.yaml        # Medium experiment config

docs/
├── cli_reference.md             # Complete CLI option reference (all subcommands)
├── tutorial.md                  # End-to-end tutorial
├── developer_guide.md           # This file
└── README/                      # 13-section guide (01-overview through 13-documentation)

examples/
└── local_smoke_test.yaml        # Reference config for local HuggingFace models
```

---

## 2. Architecture Overview

```
CLI (cli.py)
  ├─► coeval run   → load_config() → validate_config() → run_experiment()
  ├─► coeval probe → commands/probe_cmd.py → run_probe()
  ├─► coeval plan  → commands/plan_cmd.py  → estimate_experiment_cost()
  ├─► coeval status→ commands/status_cmd.py → reads experiment folder directly
  └─► coeval analyze → analysis/main.py → run_analyze()

run_experiment() [runner.py]
  │
  ├─ ExperimentStorage.initialize()  [storage.py]
  ├─ RunLogger()                     [logger.py]
  ├─ ModelPool()                     [interfaces/pool.py]
  ├─ QuotaTracker()                  [phases/utils.py]
  ├─ run_probe()                     [interfaces/probe.py]      (pre-flight check)
  ├─ estimate_experiment_cost()      [interfaces/cost_estimator.py]  (optional)
  │
  └─ for phase_id in PHASE_IDS:
        runner(cfg, storage, logger, pool, quota, mode)
          │
          ├─ Phase 1: run_phase1()   reads cfg, writes phase1_attributes/
          ├─ Phase 2: run_phase2()   reads cfg, writes phase2_rubric/
          ├─ Phase 3: run_phase3()   reads phase1 artifacts, writes phase3_datapoints/
          │             batch path: openai_batch.py / anthropic_batch.py
          ├─ Phase 4: run_phase4()   reads phase3 artifacts, writes phase4_responses/
          │             batch path: openai_batch.py / anthropic_batch.py
          └─ Phase 5: run_phase5()   reads phase2/3/4 artifacts, writes phase5_evaluations/
                        batch path: openai_batch.py / anthropic_batch.py
```

Every phase function has the same signature:

```python
def run_phaseN(
    cfg: CoEvalConfig,
    storage: ExperimentStorage,
    logger: RunLogger,
    pool: ModelPool,
    quota: QuotaTracker,
    phase_mode: str,
) -> None: ...
```

This uniformity allows the runner to iterate over them with a single loop and to add
new phases without changing the orchestrator.

---

## 3. Module Reference

### 3.1 `experiments/config.py`

**Purpose:** Parse the YAML config into typed dataclasses and enforce all 17 validation rules.

#### Dataclasses

```
CoEvalConfig
├── models: list[ModelConfig]
├── tasks:  list[TaskConfig]
└── experiment: ExperimentConfig
    └── _raw: dict  (raw YAML, passed to storage.initialize for config snapshot)
```

| Class | Key fields |
|-------|-----------|
| `ModelConfig` | `name`, `interface`, `parameters`, `roles`, `access_key`, `role_parameters`, `batch_enabled` |
| `TaskConfig` | `name`, `description`, `output_description`, `target_attributes`, `nuanced_attributes`, `sampling`, `rubric`, `evaluation_mode`, `prompt_library`, `label_attributes` |
| `SamplingConfig` | `target` ([min,max] or "all"), `nuance` ([min,max]), `total` |
| `ExperimentConfig` | `id`, `storage_folder`, `resume_from`, `phases`, `log_level`, `quota`, `probe_mode`, `probe_on_fail`, `estimate_cost`, `estimate_samples` |

#### Key functions

**`load_config(path: str) -> CoEvalConfig`**
Opens the YAML file, calls `_parse_config()`, stores the raw dict in `cfg._raw`, returns the config.

**`validate_config(cfg, continue_in_place=False, _skip_folder_validation=False) -> list[str]`**
Applies rules V-01 through V-17.  Returns a list of error strings (empty = valid).
Does **not** raise; the caller (CLI or tests) decides what to do with errors.

- `continue_in_place=True`: suppresses V-11 (folder must not exist); activates V-14
  (folder must already have `meta.json`).
- `_skip_folder_validation=True`: suppresses both V-11 and V-14; used by standalone
  commands (`coeval probe`, `coeval plan` without `--continue`) that are
  folder-state-agnostic.

**`CoEvalConfig.get_models_by_role(role: str) -> list[ModelConfig]`**
Returns all models that have the given role.  Used by every phase.

**`CoEvalConfig.get_phase_mode(phase_id: str) -> str`**
Returns the configured mode for a phase, defaulting to `'New'` for fresh experiments
or `'Keep'` when `resume_from` is set.

**`ModelConfig.get_parameters_for_role(role: str) -> dict`**
Returns base `parameters` merged with `role_parameters[role]`.

#### Constants

```python
VALID_ROLES            = {'student', 'teacher', 'judge'}
VALID_INTERFACES       = {'openai', 'anthropic', 'gemini', 'huggingface'}
VALID_PHASE_MODES      = {'New', 'Keep', 'Extend', 'Model'}
VALID_PROBE_MODES      = {'disable', 'full', 'resume'}
VALID_PROBE_FAIL_MODES = {'abort', 'warn'}
PHASE_IDS = ['attribute_mapping', 'rubric_mapping', 'data_generation',
             'response_collection', 'evaluation']
```

---

### 3.2 `experiments/storage.py`

**Purpose:** All filesystem I/O for one experiment.  Phases never touch the disk directly;
they call `ExperimentStorage` methods.

#### Class `ExperimentStorage`

Constructor: `ExperimentStorage(storage_folder: str, experiment_id: str)`
Sets `self.root = self.run_path = Path(storage_folder) / experiment_id` and computes
all sub-paths (`phase1`, `phase2`, …, `phase5`).

**`initialize(config_raw, resume_from_id=None, source_storage_folder=None, continue_in_place=False)`**
Creates the full folder tree (`phase1_attributes/` … `phase5_evaluations/`), writes
`config.yaml` (snapshot) and `meta.json` with status `in_progress`.

- If `resume_from_id` is given, copies Phase 1 and Phase 2 artifact files from the
  source experiment into the new experiment's folders.
- If `continue_in_place=True`, uses `exist_ok=True` for all `mkdir` calls and **skips**
  overwriting `config.yaml` and `meta.json` — existing data is preserved intact.
- Raises `FileExistsError` if the target root already exists **and** `continue_in_place=False`.

**Phase 1 methods**
| Method | Description |
|--------|-------------|
| `write_target_attrs(task_id, attrs)` | Write `{task_id}.target_attrs.json` |
| `read_target_attrs(task_id)` | Read back the JSON dict |
| `target_attrs_exist(task_id)` | Check file presence |
| Same trio for `nuanced_attrs` | |

**Phase 2 methods**
| Method | Description |
|--------|-------------|
| `write_rubric(task_id, rubric)` | Write `{task_id}.rubric.json` |
| `read_rubric(task_id)` | Read back the JSON dict |
| `rubric_exists(task_id)` | Check file presence |

**Phase 3 methods (JSONL)**
| Method | Description |
|--------|-------------|
| `append_datapoint(task_id, teacher_id, record)` | Append one record to the JSONL file |
| `read_datapoints(task_id, teacher_id)` | Read all records |
| `count_datapoints(task_id, teacher_id)` | Count non-empty lines |
| `index_datapoints(task_id, teacher_id)` | Return `{id: record}` dict for fast lookup |

**Phase 4 methods (JSONL)**
| Method | Description |
|--------|-------------|
| `append_response(task_id, teacher_id, student_id, record)` | Append |
| `read_responses(...)` | Read all |
| `iter_response_files(task_id, teacher_id)` | Yield all JSONL paths for a (task, teacher) pair |
| `response_file_exists(task_id, teacher_id, student_id)` | Path existence check |
| `get_responded_datapoint_ids(...)` | `set[str]` of `datapoint_id` values already in the file |

**Phase 5 methods (JSONL)**
| Method | Description |
|--------|-------------|
| `append_evaluation(task_id, teacher_id, judge_id, record)` | Append |
| `read_evaluations(...)` | Read all |
| `evaluation_file_exists(...)` | Path existence check |
| `get_evaluated_response_ids(...)` | `set[str]` of `response_id` values already evaluated |

**`update_meta(phase_started=None, phase_completed=None, status=None)`**
Reads, mutates, and rewrites `meta.json`.  Keeps `phases_in_progress` and
`phases_completed` lists accurate throughout the run.

**`read_meta() -> dict`**
Reads and returns the full `meta.json` dict.  Used by `--continue` mode and
`coeval status` to determine which phases are already done.

**Batch tracking methods**
| Method | Description |
|--------|-------------|
| `write_pending_batch(batch_id, record)` | Append/update entry in `pending_batches.json` |
| `read_pending_batches() -> dict` | Read all tracked batch jobs |
| `remove_pending_batch(batch_id)` | Remove a completed batch from the tracking file |
| `write_run_error(record)` | Append one entry to `run_errors.jsonl` |
| `read_run_errors(limit=10) -> list` | Read the last N error entries |

**Low-level helpers** (private, used by all public methods):
- `_write_json(path, data)` — `json.dump` with `ensure_ascii=False`
- `_read_json(path)` — `json.load`
- `_append_jsonl(path, record)` — open in append mode, write one JSON line
- `_read_jsonl(path)` — read all non-empty lines, return list of dicts

---

### 3.3 `experiments/prompts.py`

**Purpose:** Define canonical prompt templates and resolve the correct template for
any (prompt_id, model_name, task) combination.

#### `TEMPLATES: dict[str, str]`

Seven entries — one per prompt ID.  All use Python `str.format()` placeholders.

| ID | Used in | Variables |
|----|---------|-----------|
| `map_target_attrs` | Phase 1 | `{task_description}` |
| `map_nuanced_attrs` | Phase 1 | `{task_description}` |
| `autorubric` | Phase 2 | `{task_description}`, `{output_description}` |
| `sample` | Phase 3 | `{task_description}`, `{output_description}`, `{target_attributes}`, `{nuanced_attributes}` |
| `test` | Phase 4 | `{input}`, `{task_description}`, `{output_description}` |
| `evaluate_single` | Phase 5 | `{task_description}`, `{output_description}`, `{input}`, `{target_attributes}`, `{reference_response}`, `{response}`, `{rubric}` |
| `evaluate_per_factor` | Phase 5 | same as above minus `{rubric}`, plus `{rubric_factor_name}`, `{rubric_factor_description}` |

#### `get_prompt(prompt_id, task_prompt_library, model_name, variables) -> str`

Resolution order:
1. `task_prompt_library[f"{prompt_id}.{model_name}"]` — model-specific override
2. `task_prompt_library[prompt_id]` — task-level override
3. `TEMPLATES[prompt_id]` — canonical fallback

After template selection, `template.format(**variables)` is called.  Any missing
variable raises `KeyError` immediately.

**Important:** Literal `{` / `}` characters in YAML overrides must be written as `{{` / `}}` to survive `str.format()`.

---

### 3.4 `experiments/logger.py`

**Purpose:** Simple timestamped logger that writes to `run.log` and optionally to
the console.

#### Class `RunLogger`

Constructor: `RunLogger(log_path, min_level='INFO', console=True)`

Pass `os.devnull` as `log_path` for standalone commands (`probe`, `plan`, `status`)
that do not have a run folder.

| Method | Level value |
|--------|------------|
| `debug(msg)` | 0 |
| `info(msg)` | 1 |
| `warning(msg)` | 2 |
| `error(msg)` | 3 |

Lines are formatted as `{ISO-timestamp} [{LEVEL}] {message}`.
`WARNING` and `ERROR` go to `sys.stderr`; others to `sys.stdout`.
Messages below `min_level` are silently discarded (not written to disk or console).

On Windows, `UnicodeEncodeError` on console output is caught and the message is
re-emitted with `errors='replace'` to prevent crashes from non-ASCII characters.

---

### 3.5 `experiments/runner.py`

**Purpose:** Top-level experiment orchestrator.

#### `run_experiment(cfg, dry_run=False, continue_in_place=False, only_models=None, skip_probe=False, probe_mode=None, probe_on_fail=None, estimate_only=False, estimate_samples=None) -> int`

1. Creates `ExperimentStorage` and calls `initialize(continue_in_place=continue_in_place)`.
2. Creates `RunLogger`, `ModelPool`, `QuotaTracker`.
3. Runs the pre-flight probe (unless `probe_mode='disable'` or `skip_probe=True`).
4. If `estimate_only=True`: runs estimator, prints table, writes `cost_estimate.json`, returns 0.
5. If `continue_in_place=True`: reads `phases_completed` from `meta.json`; skips
   already-completed phases; forces `Keep` mode for phases 1–2 and `Extend` mode for
   phases 3–5 (regardless of YAML config).
6. If `only_models` is set: activates only those models for phases 3–5; does **not**
   write phase-completion markers to `meta.json` so the main process is unaffected.
7. Loops over `PHASE_IDS`, calling the corresponding runner function.
8. On any phase exception: logs error, marks storage as `failed`, breaks.
9. Returns exit code 0 (success) or 1 (failure).

**Partial-success guarantee:** All JSONL files written before the failure are preserved
on disk.  Use `--continue` to resume from the last written item.

#### `print_execution_plan(cfg) -> None`

Prints to stdout: model list, task list, per-phase modes, estimated LLM call counts.
Called before every run (dry-run or real).

---

### 3.6 `experiments/cli.py`

**Purpose:** Argparse-based entry point for the `coeval` command.  Defines all
subcommand parsers and dispatches to the appropriate handler.

#### `main(argv=None) -> None`

Dispatches to `_cmd_run`, `cmd_probe`, `cmd_plan`, `cmd_status`, or `_cmd_analyze`
based on `args.command`.

#### `_cmd_run(args) -> None`

1. `load_config(args.config)` — raises + exits 1 on parse error.
2. Apply CLI overrides (`--resume`, `--log-level`).
3. `validate_config(cfg, continue_in_place=args.continue_in_place)` — prints all errors; exits 1 if any.
4. `print_execution_plan(cfg)` — always.
5. If `--dry-run`: print "config valid" and exit 0.
6. Otherwise: `run_experiment(cfg, ...)` and `sys.exit(exit_code)`.

#### CLI subcommands and flags

| Subcommand | Handler | Key options |
|------------|---------|-------------|
| `run` | `_cmd_run` | `--config`, `--resume`, `--continue`, `--only-models`, `--dry-run`, `--probe`, `--probe-on-fail`, `--skip-probe` (deprecated), `--estimate-only`, `--estimate-samples`, `--log-level` |
| `probe` | `cmd_probe` (commands/) | `--config`, `--probe`, `--probe-on-fail`, `--log-level` |
| `plan` | `cmd_plan` (commands/) | `--config`, `--continue`, `--estimate-samples`, `--log-level` |
| `status` | `cmd_status` (commands/) | `--run`, `--fetch-batches` |
| `analyze` | `_cmd_analyze` | `--run`, `--out`, `--partial-ok`, robust filtering flags, `--benchmark-format` |

---

### 3.7 `experiments/commands/`

Standalone CLI command implementations.  Each file exports a single `cmd_*` function
that is imported lazily by `cli.main()`.  All three commands use a
`RunLogger(os.devnull, ...)` (console-only, no log file) because they do not own an
experiment run folder.

#### `commands/probe_cmd.py` — `cmd_probe(args)`

1. Loads config; applies `--probe`/`--probe-on-fail` overrides to `cfg.experiment`.
2. Validates with `_skip_folder_validation=True` (probe is folder-state-agnostic).
3. Calls `run_probe(cfg, logger, mode=..., on_fail=...)`.
4. Prints a tabular result summary.
5. Exits 0 on success, 1 on config error, 2 when a model is unavailable and `on_fail='abort'`.

#### `commands/plan_cmd.py` — `cmd_plan(args)`

1. Loads config; applies `--estimate-samples` override.
2. Validates with `_skip_folder_validation=not continue_in_place` (folder need not exist
   for a fresh estimate).
3. Creates `ExperimentStorage` without calling `initialize()` (just points at the path).
4. If `--continue`: reads `phases_completed` from `meta.json`.
5. Calls `estimate_experiment_cost(cfg, storage, logger, ...)`.

#### `commands/status_cmd.py` — `cmd_status(args)`

Reads the experiment folder directly (no config file needed).  Key internal helpers:

| Helper | Description |
|--------|-------------|
| `_print_meta(storage, run_path)` | Experiment ID, status, timestamps, phase lists |
| `_print_phase_progress(storage, run_path)` | File counts + JSONL record counts per phase |
| `_print_pending_batches(batches)` | Table from `pending_batches.json` |
| `_print_recent_errors(storage)` | Last 10 entries from `run_errors.jsonl` |
| `_fetch_batch_results(storage, batches)` | Polls APIs; applies Phase 4/5 results |
| `_poll_openai_batch(batch_id)` | Returns `(done: bool, results: dict \| None)` |
| `_poll_anthropic_batch(batch_id)` | Returns `(done: bool, results: dict \| None)` |
| `_apply_phase4_results(key_to_text, storage)` | Writes response records; returns count |
| `_apply_phase5_results(key_to_text, storage)` | Writes evaluation records; returns count |

Batch key format (used internally):
- Phase 3: `task\x00teacher\x00seq`
- Phase 4: `task\x00teacher\x00student\x00dp_id`
- Phase 5 single: `task\x00teacher\x00judge\x00response_id\x01`
- Phase 5 per_factor: `task\x00teacher\x00judge\x00response_id\x00factor`

Phase 3 results **cannot** be auto-applied (the in-memory `pending` dicts with sampled
attributes were never serialised).  `_fetch_batch_results` detects `phase='data_generation'`
and prints an advisory message directing the user to re-run with `--continue`.

---

### 3.8 `experiments/label_eval.py`

**Purpose:** Label-accuracy metrics for classification and information-extraction tasks,
computed directly from Phase 3 datapoints and Phase 4 student responses — **no LLM
judge required**.

#### `extract_label(response_text, attr_key) -> str | None`

Three-strategy extraction:
1. Parse as JSON; return value at `attr_key` (exact key match, then alias keys: `label`, `prediction`, `class`, `answer`, …).
2. If JSON fails: return the text directly if it is ≤ 60 chars and single-line.
3. Return `None` (extraction failed; response counted as *skipped*).

#### `extract_multilabel(response_text, attr_keys) -> dict[str, str | None]`

Batch variant for tasks with multiple label attributes.  Tries JSON first (all keys in
one pass), then falls back to short free-text (same value replicated for every key).

#### `class LabelEvaluator(label_attributes, match_fn=None)`

- `label_attributes`: list of `target_attributes` keys whose sampled values are ground truth.
- `match_fn`: optional `(predicted, ground_truth) -> bool` comparator (default: case-insensitive exact match after strip).
- `.evaluate(datapoints, responses) -> dict[str, dict]` — returns per-attribute `accuracy`, `n_total`, `n_matched`, `n_skipped`, `per_label` (precision/recall/F1 per class).
- `.evaluate_multilabel(datapoints, responses) -> dict` — returns `hamming_accuracy` (macro-averaged) and `per_attribute`.

---

### 3.9 `experiments/interfaces/base.py`

**Purpose:** Abstract base class that all model backends must implement.

```python
class ModelInterface(ABC):
    @abstractmethod
    def generate(self, prompt: str, parameters: dict) -> str: ...
```

`parameters` is the fully-merged dict (base + role-specific overrides) produced by
`ModelConfig.get_parameters_for_role()` before the call.

---

### 3.10 `experiments/interfaces/openai_iface.py`

**Purpose:** OpenAI Chat Completions backend with exponential-backoff retry.

#### `OpenAIInterface`

Constructor: `__init__(access_key=None)` — uses `access_key` or `OPENAI_API_KEY` env var.

**`generate(prompt, parameters) -> str`**

Pops the following keys from `parameters` before passing the rest to the API:
- `model` (required)
- `system_prompt` (optional; prepended as a system message if present)
- `temperature` (default 0.7)
- `max_tokens` (optional)

Retries up to 3 times with doubling delay (1 s → 2 s) on transient errors
(`rate limit`, `timeout`, `connection`, 5xx codes).  Raises immediately on fatal errors
(`invalid api key`, `authentication`, `model not found`).

---

### 3.11 `experiments/interfaces/anthropic_iface.py`

**Purpose:** Anthropic Messages API backend.

#### `AnthropicInterface`

Constructor: `__init__(access_key=None)` — uses `access_key` or `ANTHROPIC_API_KEY` env var.

**`generate(prompt, parameters) -> str`**

Pops `model`, `system_prompt`, `temperature`, `max_tokens`.
Calls `anthropic.Anthropic.messages.create()` with exponential-backoff retry.

---

### 3.12 `experiments/interfaces/gemini_iface.py`

**Purpose:** Google Gemini backend.

#### `GeminiInterface`

Constructor: `__init__(access_key=None)` — uses `access_key` or `GEMINI_API_KEY` / `GOOGLE_API_KEY` env var.

**`generate(prompt, parameters) -> str`**

Calls `google.generativeai.GenerativeModel.generate_content()`.
Supports pseudo-batch via `GeminiBatchInterface` (paced real-time calls to avoid rate limits).

---

### 3.13 `experiments/interfaces/huggingface_iface.py`

**Purpose:** Local-inference backend using `transformers.pipeline`.

#### `HuggingFaceInterface`

Constructor: `__init__(model_id, access_key=None, device='auto')`
- Loads the model weights once via `pipeline('text-generation', ...)`.
- `device='auto'` → `device_map='auto'` (lets Accelerate choose GPU/CPU automatically).
  Falls back to CPU if no CUDA-capable GPU is detected.
- `device='cpu'` or `device='cuda'` → passed directly as `device=`.
- `access_key` or `HF_TOKEN` env var is used for gated models.

**`generate(prompt, parameters) -> str`**

Pops `model` and `device` (already handled at init), `temperature`, and `max_new_tokens`.
Calls `pipeline(messages, temperature=..., max_new_tokens=..., do_sample=temperature>0)`.

The pipeline uses the chat template format (list of `{'role': ..., 'content': ...}`
dicts).  The method scans the output list in reverse to find the last `assistant` turn
and returns its `content`.

**Important:** Model weights are loaded at first `pool.get()` and never freed.
For experiments with many HuggingFace models, GPU memory grows.  Free memory manually
between experiments by calling `del pool` and `torch.cuda.empty_cache()`.

---

### 3.14 `experiments/interfaces/openai_batch.py`

**Purpose:** OpenAI Batch API helpers for phases 3–5.

Key functions used by phase batch runners:

| Function | Description |
|----------|-------------|
| `submit_openai_batch(requests, storage, phase, description)` | Uploads a JSONL file, creates a batch job, writes `pending_batches.json`, returns `batch_id` |
| `poll_openai_batch(batch_id, storage, logger)` | Polls the API until done; downloads output; applies results via storage methods; removes from `pending_batches.json` |

The batch runner (`AsyncBatchRunner` or equivalent) receives `storage=storage, phase='data_generation'`
(etc.) so it can write tracking records before any polling begins — ensuring the
`batch_id` is never lost even if the process is killed while waiting.

---

### 3.15 `experiments/interfaces/anthropic_batch.py`

**Purpose:** Anthropic Message Batches API helpers for phases 3–5.

Mirrors `openai_batch.py` in structure:

| Function | Description |
|----------|-------------|
| `submit_anthropic_batch(requests, storage, phase, description)` | Creates a Message Batch, writes `pending_batches.json`, returns `batch_id` |
| `poll_anthropic_batch(batch_id, storage, logger)` | Polls until `ended`; downloads results; applies via storage; removes from tracking |

---

### 3.16 `experiments/interfaces/probe.py`

**Purpose:** Model availability probe — tests each model with a lightweight API call
before the pipeline starts.

#### `run_probe(cfg, logger, mode, on_fail, phases_completed=None, only_models=None, probe_results_path=None) -> (results, needed_names)`

- `mode='full'` — probe all models; `mode='resume'` — probe only models needed for
  remaining phases; `mode='disable'` — skip.
- `on_fail='abort'` — calls `logger.error`; `on_fail='warn'` — calls `logger.warning`.
- Writes `probe_results.json` to `probe_results_path` if provided.
- Returns `(results dict {model_name: 'ok' | error_str}, set of probed model names)`.

**Phase → role mapping** (used in `resume` mode):

| Phase | Role probed |
|-------|-------------|
| `attribute_mapping`, `rubric_mapping`, `data_generation` | `teacher` |
| `response_collection` | `student` |
| `evaluation` | `judge` |

#### Per-interface probe methods

| Interface | Method | Mechanism |
|-----------|--------|-----------|
| `openai` | `_probe_openai` | `client.models.list()` — no tokens consumed |
| `anthropic` | `_probe_anthropic` | `client.models.list()` — no tokens consumed |
| `gemini` | `_probe_gemini` | `genai.list_models()` — no tokens consumed |
| `huggingface` | `_probe_huggingface` | `huggingface_hub.model_info()` — metadata only |

---

### 3.17 `experiments/interfaces/cost_estimator.py`

**Purpose:** Pre-run cost and time estimation.

#### Key functions

- **`get_prices(model_cfg) -> (input_price, output_price)`** — looks up `PRICE_TABLE` (17+ known models); falls back to defaults (`$1.00/$3.00 per 1M tokens`).
- **`count_tokens_approx(text) -> int`** — `max(1, len(text) // 4)` character heuristic.
- **`estimate_experiment_cost(cfg, storage, logger, n_samples, run_sample_calls, continue_in_place=False, completed_phases=None) -> dict`**
  - Runs `n_samples` real calls per model (or uses heuristics when `n_samples=0`).
  - Computes per-phase token counts and costs.
  - Applies batch discount: 50% for `openai`/`anthropic`, 0% for `gemini`.
  - When `continue_in_place=True` and `completed_phases` is provided, reads existing
    storage artifacts and subtracts already-completed work from the budget.
  - Writes `cost_estimate.json` to `storage.run_path`.
  - Returns a dict with `total_cost_usd`, `total_time_min`, and per-phase breakdown.

#### `PRICE_TABLE`

Covers GPT-4o, GPT-4o-mini, GPT-3.5-turbo, Claude 3 (Haiku/Sonnet/Opus), Claude 3.5
(Haiku/Sonnet), Claude 3.7 Sonnet, Gemini 1.5 (Flash/Pro), Gemini 2.0 Flash, and
HuggingFace (free / compute cost only).

---

### 3.18 `experiments/interfaces/pool.py`

**Purpose:** Lazy-load factory + cache for `ModelInterface` instances.

#### `ModelPool`

**`get(model_cfg: ModelConfig) -> ModelInterface`**

Returns a cached interface, or creates it on the first call for that model name.
This ensures HuggingFace weights are loaded exactly once per experiment run.
The cache key is `model_cfg.name`.

---

### 3.19 `experiments/phases/utils.py`

**Purpose:** Shared utilities used by all five phase modules.

#### `_extract_json(text: str) -> Any`

Three-strategy JSON extraction:
1. **Direct** — `json.loads(text)`.
2. **Strip prose** — find first `{` or `[`, parse from there to end.
3. **Bracket window** — find first `{` and last `}` (or `[` / `]`), parse that substring.

After a successful parse, single-element lists `[{...}]` are unwrapped to `{...}`.
Raises `json.JSONDecodeError` only if all three strategies fail.

#### `call_llm_json(iface, prompt, parameters, max_retries=3) -> Any`

Calls `iface.generate()`, strips markdown code fences (` ```json ` / ` ``` `),
then calls `_extract_json()`.  Retries up to `max_retries` times with doubling delay
on `JSONDecodeError`.  Non-JSON errors (network, auth) are re-raised immediately.

#### `call_llm_word(iface, prompt, parameters, valid_words, max_retries=3) -> str`

Expects the model to return a single word from `valid_words` (default: `{'High', 'Medium', 'Low'}`).
Strips whitespace and trailing punctuation.  Retries on invalid responses.
Used by Phase 5 `per_factor` evaluation mode.

#### `extract_prompt_response(data: Any) -> tuple[str, str]`

Normalises the dict returned by a teacher model.  Accepts a wide range of key names:

- Prompt keys tried in order: `prompt`, `input`, `question`, `task`, `context`, `user_input`, `text`, `scenario`
- Response keys tried in order: `response`, `output`, `answer`, `completion`, `result`, `reference`, `label`

Also unwraps single-element lists `[{...}]`.  Raises `KeyError` with a descriptive
message if either field cannot be found.

#### `merge_attr_maps(*maps: dict) -> dict[str, list]`

Union of multiple attribute maps.  For each attribute key, appends values that are
not already present (preserving insertion order, no duplicates).  Non-dict entries
and non-list values are silently skipped.

#### `merge_rubrics(*rubrics: dict) -> dict[str, str]`

Union of multiple rubric dicts.  First occurrence of a factor name wins (later
rubrics can only add new factors, not override existing ones).

#### `class QuotaTracker`

**`__init__(quota_config: dict[str, dict[str, int]])`**
Initialises `_remaining[model_name] = spec['max_calls']`.
Models not in `quota_config` have `float('inf')` remaining.

**`is_exhausted(model_name: str) -> bool`**
Returns `True` if remaining ≤ 0.

**`consume(model_name: str) -> None`**
Decrements the counter by 1.  No-op for unlisted models.

---

### 3.20 `experiments/phases/phase1.py`

**Purpose:** Attribute Mapping — produce `target_attrs.json` and `nuanced_attrs.json` for each task.

#### `run_phase1(cfg, storage, logger, pool, quota, phase_mode) -> None`

For each task, calls `_resolve_attrs()` twice — once for `'target'` and once for `'nuanced'`.
Collects per-task errors; raises `RuntimeError` at the end if any occurred.

#### `_resolve_attrs(task, kind, teachers, storage, logger, pool, quota, phase_mode)`

Decision tree:
1. `phase_mode == 'Keep'` and artifact exists → skip.
2. `attr_value` is a `dict` → write directly (no LLM calls).
3. `attr_value == 'auto'` or `'complete'` → call all teachers with `call_llm_json`, merge results with `merge_attr_maps`.  For `'complete'` mode, `*_attributes_seed` values are prepended to the merge (they always survive).

Uses prompt ID `map_target_attrs` or `map_nuanced_attrs` from `get_prompt()`.

---

### 3.21 `experiments/phases/phase2.py`

**Purpose:** Rubric Mapping — produce `{task_id}.rubric.json` for each task.

#### `run_phase2(cfg, storage, logger, pool, quota, phase_mode) -> None`

For each task, calls `_resolve_rubric()`.  Raises on any error.

#### `_resolve_rubric(task, teachers, storage, logger, pool, quota, phase_mode)`

Decision tree:
1. `phase_mode == 'Keep'` and rubric exists → skip.
2. `task.rubric` is a `dict` → write directly.
3. `task.rubric == 'auto'` or `'extend'` → call teachers, merge.  For `'extend'`, the existing rubric from storage is prepended (its factors take priority over new teacher output).

Uses prompt ID `autorubric` from `get_prompt()`.

---

### 3.22 `experiments/phases/phase3.py`

**Purpose:** Data Generation — produce `{task_id}.{teacher_id}.datapoints.jsonl`.

#### `run_phase3(cfg, storage, logger, pool, quota, phase_mode) -> None`

For each `(task, teacher)` pair, calls `_generate_datapoints()` (real-time) or
`_generate_batch_datapoints()` (batch).  Partial failures are tolerated — individual
teacher failures are logged but the phase continues.  Raises only if a task ends up
with **zero** datapoints across all teachers.

#### `_generate_datapoints(task, teacher, storage, logger, pool, quota, phase_mode)`

Phase mode logic:
- `Keep` → skip.
- `Model` → skip if the JSONL file already exists.
- `Extend` → compute `to_generate = total - existing_count`; skip if already at target.
- `New` → generate all `total` items from scratch.

For each datapoint:
1. Sample `target_attrs` and `nuanced_attrs` using `_sample_attrs()`.
2. Build prompt with `get_prompt('sample', ...)`.
3. Call `call_llm_json()`.
4. Normalise with `extract_prompt_response()`.
5. Build record with structured ID `{task_id}__{teacher_id}__{seq:05d}`.
6. Append to JSONL via `storage.append_datapoint()`.

#### `_sample_attrs(attr_map, target_spec) -> dict[str, str]`

If `target_spec == 'all'`: include all attributes.
Otherwise `target_spec = [lo, hi]`: randomly sample `n = randint(lo, min(hi, len(attr_map)))` keys, then pick one random value per key.

---

### 3.23 `experiments/phases/phase4.py`

**Purpose:** Response Collection — produce `{task_id}.{teacher_id}.{student_id}.responses.jsonl`.

#### `run_phase4(cfg, storage, logger, pool, quota, phase_mode) -> None`

For each `(task, teacher, student)` triple, calls `_collect_responses()`.
Collects errors; raises `RuntimeError` if any occurred.

#### `_collect_responses(task, teacher, student, storage, logger, pool, quota, phase_mode)`

Phase mode logic:
- `Keep` → skip.
- `Model` → skip if the responses file already exists.
- `Extend` → load already-responded IDs, skip those datapoints.

For each datapoint: calls `iface.generate()` directly (no JSON parsing needed — student output is free-form text).  Response record ID is `{datapoint_id}__{student_id}`.

---

### 3.24 `experiments/phases/phase5.py`

**Purpose:** Evaluation — produce `{task_id}.{teacher_id}.{judge_id}.evaluations.jsonl`.

#### `run_phase5(cfg, storage, logger, pool, quota, phase_mode) -> None`

For each `(task, teacher, judge)` triple, calls `_evaluate()`.
Tolerates partial failures.  Raises only if the total evaluation count across all
combinations is zero.

#### `_evaluate(task, teacher, judge, storage, logger, pool, quota, phase_mode)`

Phase mode logic:
- `Keep` → skip.
- `Model` → skip if evaluation file exists.
- `Extend` → determine which rubric factors are new (not yet in stored evaluations);
  evaluate only those for responses that haven't been scored yet.

Reads all responses from **all** student files for this `(task, teacher)` pair via
`storage.iter_response_files()`, then scores each against the rubric.

#### `_score_response(task, rubric, response, reference_response, ...) -> dict[str, str]`

Dispatches on `task.evaluation_mode`:

- **`single`** — one `call_llm_json()` call; model returns a JSON object mapping
  factor names to `"High"` / `"Medium"` / `"Low"`.  Invalid values are silently
  replaced with `"Low"`.
- **`per_factor`** — one `call_llm_word()` call per rubric factor.

---

## 4. Data Flow Walkthrough

```
YAML file
  │
  ▼ load_config() → CoEvalConfig
  │
  ▼ Phase 1: For each task
  │   If static attrs → write directly
  │   If auto/complete → teacher LLM call → merge_attr_maps() → write JSON
  │
  ▼ Phase 2: For each task
  │   If static rubric → write directly
  │   If auto/extend → teacher LLM call → merge_rubrics() → write JSON
  │
  ▼ Phase 3: For each (task, teacher)
  │   Read Phase 1 artifacts
  │   For N items: _sample_attrs() → get_prompt('sample') → teacher LLM call
  │                → extract_prompt_response() → append JSONL
  │   [batch path: submit to OpenAI/Anthropic Batch API; poll; apply results]
  │
  ▼ Phase 4: For each (task, teacher, student)
  │   Read Phase 3 JSONL
  │   For each datapoint: get_prompt('test') → student LLM call → append JSONL
  │   [batch path: same as Phase 3]
  │
  ▼ Phase 5: For each (task, teacher, judge)
      Read Phase 2 rubric
      Read Phase 3 datapoints index
      Read Phase 4 responses (all students)
      For each response: _score_response() using judge LLM → append JSONL
      [batch path: same as Phase 3]
```

---

## 5. ID Naming Convention

Double underscore `__` is the structured separator used throughout the ID system.
It is **reserved**: model names and task names must not contain `__`.

```
Datapoint:   {task_id}__{teacher_id}__{seq:05d}
Response:    {datapoint_id}__{student_id}
             = {task_id}__{teacher_id}__{seq:05d}__{student_id}
Evaluation:  {response_id}__{judge_id}
             = {task_id}__{teacher_id}__{seq:05d}__{student_id}__{judge_id}
```

The sequence number is zero-padded to 5 digits (`00001`..`99999`) to allow correct
lexicographic sorting.

---

## 6. Error Handling Strategy

| Phase | On partial failure | On total failure |
|-------|--------------------|-----------------|
| Phase 1 | Accumulate errors, raise RuntimeError after all tasks | Same |
| Phase 2 | Same | Same |
| Phase 3 | Log error, continue other teachers; **raise if a task has zero datapoints** | Raise |
| Phase 4 | Accumulate errors, raise RuntimeError at end | Same |
| Phase 5 | Log error, continue; **raise only if zero evaluations total** | Raise |

The runner catches any phase exception, marks the experiment as `failed`, and stops
the pipeline.  All JSONL and JSON files written before the failure are preserved for
resume.

Non-JSON errors from `iface.generate()` (network, auth) are re-raised immediately
by `call_llm_json()`; they count as fatal errors that stop the current (task, model)
combination.

---

## 7. Adding a New Model Backend

1. Create `experiments/interfaces/my_backend_iface.py` implementing `ModelInterface`:

```python
from .base import ModelInterface

class MyBackendInterface(ModelInterface):
    def __init__(self, **kwargs):
        ...  # load or connect

    def generate(self, prompt: str, parameters: dict) -> str:
        ...  # call your backend, return the text response
```

2. Register the new interface name in `ModelPool.get()` (`experiments/interfaces/pool.py`):

```python
elif model_cfg.interface == 'my_backend':
    self._cache[model_cfg.name] = MyBackendInterface(...)
```

3. Add `'my_backend'` to `VALID_INTERFACES` in `experiments/config.py`.

4. Add a probe method to `experiments/interfaces/probe.py` for the new interface.

5. Write tests for the new class (mock the underlying client).

---

## 8. Adding a New Phase

1. Create `experiments/phases/phaseN.py` with the standard signature:

```python
def run_phaseN(cfg, storage, logger, pool, quota, phase_mode):
    ...
```

2. Add `'new_phase_id'` to `PHASE_IDS` in `experiments/config.py` (in the correct
   execution order).

3. Add the corresponding storage methods to `ExperimentStorage` if the phase
   needs new file types.

4. Register the runner in `_PHASE_RUNNERS` in `experiments/runner.py`:

```python
_PHASE_RUNNERS = {
    ...
    'new_phase_id': run_phaseN,
}
```

5. Update `validate_config()` if the new phase has mode restrictions (like V-08).

---

## 9. Testing

Tests live in `experiments/tests/` and `analysis/tests/`.  All tests require only
`pytest` — no network, no LLM calls, no GPU.

```bash
pip install pytest
python -m pytest experiments/tests/ analysis/tests/ -v
```

Run from the project root (`E:\Projects\CoEval\main\`).

| File | Coverage |
|------|----------|
| `test_config.py` | V-01..V-17 validation, role-parameter merge, `get_phase_mode` defaults, `_skip_folder_validation`, duplicate names, reserved separator |
| `test_storage.py` | `initialize()` folder creation and `FileExistsError`, `continue_in_place` re-open, `resume_from` copy, `meta.json` lifecycle, Phase 1–5 JSONL round-trips |
| `test_prompts.py` | Resolution order (model > task > canonical), all 7 template IDs present and non-empty, variable substitution, `{{` escaping |
| `test_utils.py` | `_extract_json` three strategies + edge cases, `extract_prompt_response` all accepted key names + error cases, `merge_attr_maps` deduplication, `merge_rubrics` first-wins, `QuotaTracker` full lifecycle |
| `test_phase4_phase5.py` | Phase 4/5 in all modes, batch path disabled, `evaluated_resp_ids` skip logic |
| `test_label_eval.py` | `extract_label` all strategies, `extract_multilabel`, `LabelEvaluator` accuracy/P/R/F1/Hamming |
| `test_probe_and_estimator.py` | `run_probe` all modes, `probe_results.json`, `on_fail` dispatch, `get_prices`, `estimate_experiment_cost` (full + remaining-work mode) |
| `test_commands.py` | `_skip_folder_validation` (5 tests), `cmd_probe` (7), `cmd_plan` (6), status helpers (11), `cmd_status` (9), CLI dispatch (3) |

**Current test count:** 698 tests across 8 test modules (experiments) + analysis test modules.
All tests run without network, GPU, or real LLM calls.

**Mocking pattern for interface tests:**

```python
from unittest.mock import MagicMock
from experiments.interfaces.base import ModelInterface

class FakeInterface(ModelInterface):
    def __init__(self, responses):
        self._responses = iter(responses)
    def generate(self, prompt, parameters):
        return next(self._responses)
```

Pass a `FakeInterface` wherever `iface` is expected to test phase logic
deterministically without any model.  Pre-populate a `ModelPool` with fake entries:

```python
pool = ModelPool()
pool._cache['my-model'] = FakeInterface(['{"prompt": "p", "response": "r"}'])
```

---

## 10. Frequently Asked Questions

### Architecture and Design

**Q: Why are all five phase functions given the same signature instead of taking only what they need?**
> Uniformity lets the runner iterate `_PHASE_RUNNERS` with a single generic call.
> Adding a new phase requires zero changes to the runner — just add an entry to the
> dict.  It also makes it easy to unit-test each phase in isolation with the same
> fixture setup.

**Q: Why does `ExperimentStorage` exist instead of just using direct file I/O in each phase?**
> Centralising all path construction and serialisation in one class means:
> (1) path-naming conventions are enforced in a single place,
> (2) phases never hard-code paths,
> (3) swapping the storage backend (e.g., S3 instead of local disk) only requires
> reimplementing `ExperimentStorage`, not touching any phase code.

**Q: Why are JSONL files used instead of a database or single JSON files?**
> JSONL files are append-only, require no lock management, and survive a crash without
> data loss.  They also allow incremental `Extend`-mode resumption — unwritten items are
> simply missing lines, and the code counts lines to determine what is still needed.
> A database would add a dependency and a write-ahead log for the same benefit.

**Q: Why is `_extract_json` needed?  Can't we just call `json.loads()`?**
> Small models often wrap their JSON in prose, markdown fences (` ```json `), or return
> a single-element list.  The three-strategy extraction handles all observed failure
> modes from models as small as 135 M parameters.  Without it, even correctly-generated
> JSON from small models would be discarded as a parse failure.

**Q: Why does `merge_attr_maps` deduplicate values but not keys?**
> Attribute *keys* represent independent semantic axes (e.g., `tone`, `urgency`).  If
> two teachers both produce a `tone` axis, we want to *union* their values, not replace
> one with the other.  Deduplication of values (not keys) is the correct merge
> semantics for expanding an attribute catalogue.

---

### Config and Validation

**Q: Why does `validate_config` return a list instead of raising on the first error?**
> It is more user-friendly to show all configuration errors at once so the operator can
> fix them all in one edit, rather than discovering problems one at a time.

**Q: Why is `__` (double underscore) reserved in names?**
> IDs are constructed by joining components with `__` as the separator
> (`task__teacher__00001__student__judge`).  If any component itself contained `__`,
> splitting the ID back into its parts would be ambiguous.

**Q: `V-11` prevents running the same config twice.  Is there a way to bypass it?**
> Use `--continue` to restart an interrupted run in-place.  For a completely fresh run
> with the same config, increment the `experiment.id`.  `resume_from` creates a new
> experiment that inherits Phase 1–2 artifacts.

**Q: What does `_skip_folder_validation` do?**
> It suppresses both V-11 (folder must not exist) and V-14 (folder must exist with
> `meta.json`).  Used by `coeval probe` and `coeval plan` (without `--continue`) to
> allow them to run against any config regardless of whether the experiment folder
> already exists.

---

### Phases and LLM Calls

**Q: Phase 3 tolerates individual teacher failures, but Phases 1, 2, and 4 do not.  Why?**
> Phase 3 has a redundancy safety net: if one teacher fails, the other teachers have
> likely already written some datapoints, so the pipeline can continue with partial
> data.  Phases 1 and 2 produce singleton artifacts (one file per task) so any failure
> leaves the artifact in an unknown state.  Phase 4 failures are collected and reported
> together because each (task, teacher, student) triple is independent and the pipeline
> has enough information to report all failures at once.

**Q: What happens if a model's quota runs out mid-phase?**
> The current item is skipped and a `WARNING` is logged.  Work done before quota
> exhaustion is preserved in JSONL.  Other models' work continues unaffected.  The
> experiment can be resumed with `Extend` mode to fill in the missing items with a
> higher quota or a different model.

**Q: `call_llm_json` retries on `JSONDecodeError`.  Doesn't this waste LLM calls?**
> Yes, but it is the correct trade-off for small models.  A structured-output failure
> from a tiny model is frequently stochastic — a second attempt at a slightly different
> random seed often succeeds.  The retry count is bounded at 3 by default and is
> configurable via `max_retries`.

**Q: Why does Phase 4 use `iface.generate()` directly instead of `call_llm_json()`?**
> Student responses are free-form text — the task explicitly asks for natural language
> (e.g., a subject line, a sentiment label, a summary), not JSON.  Parsing the student
> output as JSON would be wrong; the raw text is stored as-is.

**Q: Why does Phase 5 `single` mode silently coerce invalid scores to `Low`, while `per_factor` mode raises?**
> In `single` mode the judge returns a JSON object with potentially many factors at
> once; a partially invalid response still contains useful data, so a graceful fallback
> avoids discarding the entire evaluation.  In `per_factor` mode each call returns
> exactly one word — there is no partial result to salvage, so raising and retrying
> (up to 3 times) is the right strategy.

---

### Extending CoEval

**Q: How do I add support for a new model provider?**
> See §7.  In summary: subclass `ModelInterface`, implement `generate()`, register the
> new interface name in `ModelPool.get()`, add the name to `VALID_INTERFACES` in
> `config.py`, add a probe method in `probe.py`, and write tests.  No phase code needs
> to change.

**Q: How do I add a custom attribute-sampling strategy beyond `[min, max]` and `"all"`?**
> The `_sample_attrs()` function in `phase3.py` checks for `target_spec == 'all'` and
> otherwise interprets it as `[lo, hi]`.  Add a new branch for your custom strategy
> value (e.g., `"weighted"`) and handle it there.  Also update the `SamplingConfig`
> dataclass and the config documentation accordingly.

**Q: Can I add a Phase 6 that post-processes evaluations?**
> Yes.  See §8.  Add a `'post_processing'` entry to `PHASE_IDS`, implement `run_phase6`,
> add any new storage methods to `ExperimentStorage`, and register the runner in
> `_PHASE_RUNNERS`.  The runner loop picks it up automatically.

---

### Testing

**Q: The tests run in under a second.  How is that possible without mocking LLM calls?**
> No test touches a real model.  Config tests work entirely on in-memory dicts.  Storage
> tests use `tmp_path` (a `pathlib.Path` to a real but temporary directory).  Prompt
> tests check string manipulation.  Utils tests exercise pure functions.  The only
> external side-effect is creating and deleting temporary directories, which `pytest`
> cleans up automatically.

**Q: How do I write a test that exercises a phase without a real LLM?**
> Create a `FakeInterface` (see the pattern in §9), pre-load the storage fixture with
> the required input artifacts, and pass the fake interface where the phase would
> normally call `pool.get()`.  Because `ModelPool` is just a factory/cache, you can
> also pass a pre-populated `ModelPool` with fake entries:
> ```python
> pool = ModelPool()
> pool._cache['my-model'] = FakeInterface(['{"prompt": "p", "response": "r"}'])
> ```

**Q: Why are there no integration tests that run the full pipeline?**
> The full pipeline requires downloading model weights (several GB) and significant
> compute time.  The `examples/local_smoke_test.yaml` config serves as the integration
> test — it is run manually or in a CI job that has GPU access.  The unit tests cover
> all logic paths without network or GPU dependencies.

---

## 11. Benchmark Loaders

The `benchmark/` package contains loaders that convert public NLP datasets into CoEval
Phase 3 JSONL datapoints.  Each loader extends `BenchmarkLoader` (in `benchmark/loaders/base.py`)
and implements two methods:

| Method | Purpose |
|--------|---------|
| `_load_dataset()` | Download / parse the dataset; return a list of internal dicts. |
| `_to_record(item, seq)` | Convert one internal dict to a Phase 3 JSONL record. |

### Supported datasets

| Dataset | Task | Loader class | Default split | Notes |
|---------|------|-------------|---------------|-------|
| `xsum` | `text_summarization` | `XSumLoader` | `validation` | BBC article → summary pairs; BERTScore reference metric. |
| `codesearchnet` | `code_explanation` | `CodeSearchNetLoader` | `test` | Python function → docstring; `language="python"` kwarg. |
| `aeslc` | `email_composition` | `AESLCLoader` | `train` | Email body → subject line; uses **train** split (14 k items) because validation only has ~2 k items — too few for stratified 620-item sampling. |
| `wikitablequestions` | `data_interpretation` | `WikiTableQuestionsLoader` | `validation` | Wikipedia table + question → answer. |

### WikiTableQuestions — loading strategy

The original `wikitablequestions` HuggingFace dataset relies on a deprecated custom
loading script (removed from `datasets ≥ 3.x`), and no Parquet conversion exists on
the Hub.  `_hf_load_wtq()` tries four strategies in order:

1. **`load_dataset("wikitablequestions")`** — works on `datasets < 3.x`.
2. **Direct Parquet URL** from the HF Hub `refs/convert/parquet` revision.
3. **HF datasets-server REST API** (`/parquet?dataset=wikitablequestions`) — returns live
   Parquet file URLs if available.
4. **GitHub archive download** — downloads
   `ppasupat/WikiTableQuestions/archive/refs/heads/master.zip` (~4 MB compressed),
   reads the split's `.tsv` file and all referenced table `.csv` files entirely in memory,
   and returns a plain `list[dict]`.  This is the strategy actually invoked with current
   library versions.

### Emitting datapoints

```bash
# Emit all four datasets (sample 620 items each) into a run folder
python -m benchmark.emit_datapoints --run-id paper-eval-v1 --sample-size 620

# Emit a single dataset to a custom output directory
python -m benchmark.emit_datapoints \
    --dataset wikitablequestions \
    --out-dir ./my-run/phase3_datapoints \
    --sample-size 300
```

Output files follow the Phase 3 naming convention and can be placed directly into
an experiment's `phase3_datapoints/` folder (or ingested via `coeval ingest`).

### Stratified sampling

`BenchmarkLoader.sample()` performs stratified sampling on the `insight_depth`
attribute (or whichever attribute is listed in `_stratify_on`) to ensure each
depth level (`surface_observation`, `analytical_interpretation`, `predictive_inference`)
is proportionally represented in the output.  The random seed is controllable via
`--seed` (default 42).
