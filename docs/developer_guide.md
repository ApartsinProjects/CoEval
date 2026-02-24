# CoEval — Developer Guide

This guide explains the codebase architecture, every module, every major class and
function, and the interfaces between them.  Read it to understand the system well
enough to fix bugs, add new phases, or add a new model backend.

---

## Table of Contents

1. [Repository Layout](#1-repository-layout)
2. [Architecture Overview](#2-architecture-overview)
3. [Module Reference](#3-module-reference)
   - 3.1 [`coeval/config.py`](#31-coevalconfigpy)
   - 3.2 [`coeval/storage.py`](#32-coevalstorepy)
   - 3.3 [`coeval/prompts.py`](#33-coevalpromptsspy)
   - 3.4 [`coeval/logger.py`](#34-coevalloggerpy)
   - 3.5 [`coeval/runner.py`](#35-coevalrunnerpy)
   - 3.6 [`coeval/cli.py`](#36-coevalclipy)
   - 3.7 [`coeval/interfaces/base.py`](#37-coevalinterfacesbasepy)
   - 3.8 [`coeval/interfaces/openai_iface.py`](#38-coevalinterfacesopenai_ifacepy)
   - 3.9 [`coeval/interfaces/huggingface_iface.py`](#39-coevalinterfaceshuggingface_ifacepy)
   - 3.10 [`coeval/interfaces/pool.py`](#310-coevalinterfacespoolpy)
   - 3.11 [`coeval/phases/utils.py`](#311-coevalphasesutispy)
   - 3.12 [`coeval/phases/phase1.py`](#312-coevalphases_phase1py)
   - 3.13 [`coeval/phases/phase2.py`](#313-coevalphases_phase2py)
   - 3.14 [`coeval/phases/phase3.py`](#314-coevalphases_phase3py)
   - 3.15 [`coeval/phases/phase4.py`](#315-coevalphases_phase4py)
   - 3.16 [`coeval/phases/phase5.py`](#316-coevalphases_phase5py)
4. [Data Flow Walkthrough](#4-data-flow-walkthrough)
5. [ID Naming Convention](#5-id-naming-convention)
6. [Error Handling Strategy](#6-error-handling-strategy)
7. [Adding a New Model Backend](#7-adding-a-new-model-backend)
8. [Adding a New Phase](#8-adding-a-new-phase)
9. [Testing](#9-testing)
10. [Frequently Asked Questions](#10-frequently-asked-questions)
   - 3.8 [`coeval/interfaces/openai_iface.py`](#38-coevalinterfacesopenai_ifacepy)
   - 3.9 [`coeval/interfaces/huggingface_iface.py`](#39-coevalinterfaceshuggingface_ifacepy)
   - 3.10 [`coeval/interfaces/pool.py`](#310-coevalinterfacespoolpy)
   - 3.11 [`coeval/phases/utils.py`](#311-coevalphasesutispy)
   - 3.12 [`coeval/phases/phase1.py`](#312-coevalphases_phase1py)
   - 3.13 [`coeval/phases/phase2.py`](#313-coevalphases_phase2py)
   - 3.14 [`coeval/phases/phase3.py`](#314-coevalphases_phase3py)
   - 3.15 [`coeval/phases/phase4.py`](#315-coevalphases_phase4py)
   - 3.16 [`coeval/phases/phase5.py`](#316-coevalphases_phase5py)
4. [Data Flow Walkthrough](#4-data-flow-walkthrough)
5. [ID Naming Convention](#5-id-naming-convention)
6. [Error Handling Strategy](#6-error-handling-strategy)
7. [Adding a New Model Backend](#7-adding-a-new-model-backend)
8. [Adding a New Phase](#8-adding-a-new-phase)
9. [Testing](#9-testing)

---

## 1. Repository Layout

```
coeval/
├── __init__.py
├── cli.py                   # CLI entry point (coeval run ...)
├── config.py                # Config dataclasses, YAML loading, validation V-01..V-11
├── logger.py                # RunLogger: timestamped log to file + console
├── prompts.py               # Canonical prompt templates + resolution logic
├── runner.py                # Orchestrator: iterates phases, manages storage/logger/pool
├── storage.py               # ExperimentStorage: all filesystem I/O
│
├── interfaces/
│   ├── __init__.py          # Re-exports ModelInterface and ModelPool
│   ├── base.py              # Abstract ModelInterface
│   ├── openai_iface.py      # OpenAI Chat Completions backend
│   ├── huggingface_iface.py # HuggingFace transformers.pipeline backend
│   └── pool.py              # ModelPool: lazy-load + cache interfaces
│
└── phases/
    ├── __init__.py
    ├── utils.py             # Shared helpers: _extract_json, call_llm_json/word, mergers, QuotaTracker
    ├── phase1.py            # Attribute mapping
    ├── phase2.py            # Rubric mapping
    ├── phase3.py            # Data generation
    ├── phase4.py            # Response collection
    └── phase5.py            # Evaluation

experiments/
├── prompt_format_test.py    # Standalone experiment: tests 7 prompt strategies × 5 models
└── results.json             # Output of the prompt format experiment

examples/
└── local_smoke_test.yaml    # Reference config for 5 local HuggingFace models

tests/
├── test_config.py           # V-01..V-11 validation, role-parameter merge, phase mode defaults
├── test_storage.py          # ExperimentStorage round-trips, meta lifecycle, resume copy
├── test_prompts.py          # Prompt resolution order, all 6 template IDs, variable substitution
└── test_utils.py            # JSON extraction, extract_prompt_response, merge helpers, QuotaTracker

docs/
├── running_experiments.md   # User/operator manual
└── developer_guide.md       # This file
```

---

## 2. Architecture Overview

```
CLI (cli.py)
  └─► load_config()  ─►  validate_config()
         │
         ▼
    CoEvalConfig  ──────────────────────────────────────────────────┐
         │                                                           │
         ▼                                                           │
   run_experiment() [runner.py]                                      │
         │                                                           │
         ├─ ExperimentStorage.initialize()  [storage.py]            │
         ├─ RunLogger()                     [logger.py]             │
         ├─ ModelPool()                     [interfaces/pool.py]    │
         ├─ QuotaTracker()                  [phases/utils.py]       │
         │                                                           │
         └─ for phase_id in PHASE_IDS:                              │
               runner(cfg, storage, logger, pool, quota, mode)  ────┘
                 │
                 ├─ Phase 1: run_phase1()   reads cfg, writes phase1_attributes/
                 ├─ Phase 2: run_phase2()   reads cfg, writes phase2_rubric/
                 ├─ Phase 3: run_phase3()   reads phase1 artifacts, writes phase3_datapoints/
                 ├─ Phase 4: run_phase4()   reads phase3 artifacts, writes phase4_responses/
                 └─ Phase 5: run_phase5()   reads phase2/3/4 artifacts, writes phase5_evaluations/
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

### 3.1 `coeval/config.py`

**Purpose:** Parse the YAML config into typed dataclasses and enforce all 11 validation rules.

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
| `ModelConfig` | `name`, `interface`, `parameters`, `roles`, `access_key`, `role_parameters` |
| `TaskConfig` | `name`, `description`, `output_description`, `target_attributes`, `nuanced_attributes`, `sampling`, `rubric`, `evaluation_mode`, `prompt_library` |
| `SamplingConfig` | `target` ([min,max] or "all"), `nuance` ([min,max]), `total` |
| `ExperimentConfig` | `id`, `storage_folder`, `resume_from`, `phases`, `log_level`, `quota` |

#### Key functions

**`load_config(path: str) -> CoEvalConfig`**
Opens the YAML file, calls `_parse_config()`, stores the raw dict in `cfg._raw`, returns the config.

**`validate_config(cfg: CoEvalConfig) -> list[str]`**
Applies rules V-01 through V-11.  Returns a list of error strings (empty = valid).
Does **not** raise; the caller (CLI or tests) decides what to do with errors.

**`CoEvalConfig.get_models_by_role(role: str) -> list[ModelConfig]`**
Returns all models that have the given role.  Used by every phase to find teachers/students/judges.

**`CoEvalConfig.get_phase_mode(phase_id: str) -> str`**
Returns the mode for a phase, defaulting to `'New'` for fresh experiments or `'Keep'` when `resume_from` is set.

**`ModelConfig.get_parameters_for_role(role: str) -> dict`**
Returns base `parameters` merged with `role_parameters[role]`.
Called just before every LLM call so each role gets its own temperature, token limit, etc.

#### Constants

```python
VALID_ROLES      = {'student', 'teacher', 'judge'}
VALID_INTERFACES = {'openai', 'huggingface'}
VALID_PHASE_MODES = {'New', 'Keep', 'Extend', 'Model'}
PHASE_IDS = ['attribute_mapping', 'rubric_mapping', 'data_generation',
             'response_collection', 'evaluation']
```

---

### 3.2 `coeval/storage.py`

**Purpose:** All filesystem I/O for one experiment.  Phases never touch the disk directly;
they call `ExperimentStorage` methods.

#### Class `ExperimentStorage`

Constructor: `ExperimentStorage(storage_folder: str, experiment_id: str)`
Sets `self.root = Path(storage_folder) / experiment_id` and computes all sub-paths.

**`initialize(config_raw, resume_from_id=None, source_storage_folder=None)`**
Creates the full folder tree (`phase1_attributes/` … `phase5_evaluations/`), writes
`config.yaml` (snapshot), writes `meta.json` with status `in_progress`.
If `resume_from_id` is given, copies Phase 1 and Phase 2 artifact files from the
source experiment into the new experiment's folders.
Raises `FileExistsError` if the target root already exists.

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
| `iter_response_files(task_id, teacher_id)` | Yield all JSONL paths for a (task, teacher) pair (one per student) |
| `response_file_exists(task_id, teacher_id, student_id)` | Path existence check |
| `get_responded_datapoint_ids(...)` | `set[str]` of `datapoint_id` values already in the file |

**Phase 5 methods (JSONL)**
| Method | Description |
|--------|-------------|
| `append_evaluation(task_id, teacher_id, judge_id, record)` | Append |
| `read_evaluations(...)` | Read all |
| `evaluation_file_exists(...)` | Path existence check |
| `get_evaluated_response_ids(...)` | `set[str]` of `response_id` values already evaluated |

**`update_meta(phase_started, phase_completed, status)`**
Reads, mutates, and rewrites `meta.json`.  Keeps `phases_in_progress` and
`phases_completed` lists accurate throughout the run.

**Low-level helpers** (private, used by all public methods):
- `_write_json(path, data)` — `json.dump` with `ensure_ascii=False`
- `_read_json(path)` — `json.load`
- `_append_jsonl(path, record)` — open in append mode, write one JSON line
- `_read_jsonl(path)` — read all non-empty lines, return list of dicts

---

### 3.3 `coeval/prompts.py`

**Purpose:** Define canonical prompt templates and resolve the correct template for
any (prompt_id, model_name, task) combination.

#### `TEMPLATES: dict[str, str]`

Six entries — one per prompt ID.  All use Python `str.format()` placeholders.

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

### 3.4 `coeval/logger.py`

**Purpose:** Simple timestamped logger that writes to `run.log` and optionally to
the console.

#### Class `RunLogger`

Constructor: `RunLogger(log_path, min_level='INFO', console=True)`

| Method | Level value |
|--------|------------|
| `debug(msg)` | 0 |
| `info(msg)` | 1 |
| `warning(msg)` | 2 |
| `error(msg)` | 3 |

Lines are formatted as `{ISO-timestamp} [{LEVEL}] {message}`.
`WARNING` and `ERROR` go to `sys.stderr`; others to `sys.stdout`.
Messages below `min_level` are silently discarded (not written to disk or console).

---

### 3.5 `coeval/runner.py`

**Purpose:** Top-level experiment orchestrator.

#### `run_experiment(cfg, dry_run=False) -> int`

1. Creates `ExperimentStorage` and calls `initialize()`.
2. Creates `RunLogger`, `ModelPool`, `QuotaTracker`.
3. Loops over `PHASE_IDS`, calls the corresponding runner function.
4. On any phase exception: logs error, marks storage as `failed`, breaks.
5. Returns exit code 0 (success) or 1 (failure).

**Partial-success guarantee:** All JSONL files written before the failure are preserved
on disk.  The experiment can be resumed with `resume_from`.

#### `print_execution_plan(cfg) -> None`

Prints to stdout: model list, task list, per-phase modes, estimated LLM call counts.
Called before every run (dry-run or real).

---

### 3.6 `coeval/cli.py`

**Purpose:** Argparse-based entry point for the `coeval` command.

#### `main(argv=None) -> None`

Dispatches to `_cmd_run(args)`.

#### `_cmd_run(args) -> None`

1. `load_config(args.config)` — raises + exits 1 on parse error.
2. Apply CLI overrides (`--resume`, `--log-level`).
3. `validate_config(cfg)` — prints all errors and exits 1 if any.
4. `print_execution_plan(cfg)` — always.
5. If `--dry-run`: print "config valid" and exit 0.
6. Otherwise: `run_experiment(cfg)` and `sys.exit(exit_code)`.

CLI flags:

| Flag | Purpose |
|------|---------|
| `--config PATH` | Required; path to YAML |
| `--resume ID` | Override `experiment.resume_from` |
| `--dry-run` | Validate and plan only, no LLM calls |
| `--log-level LEVEL` | Override log level from config |

---

### 3.7 `coeval/interfaces/base.py`

**Purpose:** Abstract base class that all model backends must implement.

```python
class ModelInterface(ABC):
    @abstractmethod
    def generate(self, prompt: str, parameters: dict) -> str: ...
```

`parameters` is the fully-merged dict (base + role-specific overrides) produced by
`ModelConfig.get_parameters_for_role()` before the call.

---

### 3.8 `coeval/interfaces/openai_iface.py`

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

### 3.9 `coeval/interfaces/huggingface_iface.py`

**Purpose:** Local-inference backend using `transformers.pipeline`.

#### `HuggingFaceInterface`

Constructor: `__init__(model_id, access_key=None, device='auto')`
- Loads the model weights once via `pipeline('text-generation', ...)`.
- `device='auto'` → `device_map='auto'` (lets Accelerate choose GPU/CPU automatically).
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

### 3.10 `coeval/interfaces/pool.py`

**Purpose:** Lazy-load factory + cache for `ModelInterface` instances.

#### `ModelPool`

**`get(model_cfg: ModelConfig) -> ModelInterface`**

Returns a cached interface, or creates it on the first call for that model name.
This ensures HuggingFace weights are loaded exactly once per experiment run.
The cache key is `model_cfg.name`.

---

### 3.11 `coeval/phases/utils.py`

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

### 3.12 `coeval/phases/phase1.py`

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

### 3.13 `coeval/phases/phase2.py`

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

### 3.14 `coeval/phases/phase3.py`

**Purpose:** Data Generation — produce `{task_id}.{teacher_id}.datapoints.jsonl`.

#### `run_phase3(cfg, storage, logger, pool, quota, phase_mode) -> None`

For each `(task, teacher)` pair, calls `_generate_datapoints()`.
Partial failures are tolerated — individual teacher failures are logged but the phase
continues.  Raises only if a task ends up with **zero** datapoints across all teachers.

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

### 3.15 `coeval/phases/phase4.py`

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

### 3.16 `coeval/phases/phase5.py`

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
  │
  ▼ Phase 4: For each (task, teacher, student)
  │   Read Phase 3 JSONL
  │   For each datapoint: get_prompt('test') → student LLM call → append JSONL
  │
  ▼ Phase 5: For each (task, teacher, judge)
      Read Phase 2 rubric
      Read Phase 3 datapoints index
      Read Phase 4 responses (all students)
      For each response: _score_response() using judge LLM → append JSONL
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

1. Create `coeval/interfaces/my_backend_iface.py` implementing `ModelInterface`:

```python
from .base import ModelInterface

class MyBackendInterface(ModelInterface):
    def __init__(self, **kwargs):
        ...  # load or connect

    def generate(self, prompt: str, parameters: dict) -> str:
        ...  # call your backend, return the text response
```

2. Register the new interface name in `ModelPool.get()` (`coeval/interfaces/pool.py`):

```python
elif model_cfg.interface == 'my_backend':
    self._cache[model_cfg.name] = MyBackendInterface(...)
```

3. Add `'my_backend'` to `VALID_INTERFACES` in `coeval/config.py`.

4. Write tests for the new class (mock the underlying client).

---

## 8. Adding a New Phase

1. Create `coeval/phases/phaseN.py` with the standard signature:

```python
def run_phaseN(cfg, storage, logger, pool, quota, phase_mode):
    ...
```

2. Add `'new_phase_id'` to `PHASE_IDS` in `coeval/config.py` (in the correct
   execution order).

3. Add the corresponding storage methods to `ExperimentStorage` if the phase
   needs new file types.

4. Register the runner in `_PHASE_RUNNERS` in `coeval/runner.py`:

```python
_PHASE_RUNNERS = {
    ...
    'new_phase_id': run_phaseN,
}
```

5. Update `validate_config()` if the new phase has mode restrictions (like V-08).

---

## 9. Testing

Tests live in `tests/` and require only `pytest` (no network, no LLM calls, no GPU).

```bash
pip install pytest
python -m pytest tests/ -v
```

| File | Coverage |
|------|----------|
| `test_config.py` | V-01..V-11 validation, role-parameter merge, `get_phase_mode` defaults, duplicate names, reserved separator, character-set rules |
| `test_storage.py` | `initialize()` folder creation and `FileExistsError`, `resume_from` copy, `meta.json` lifecycle, Phase 1–5 JSONL round-trips, `iter_response_files`, `get_responded_datapoint_ids` |
| `test_prompts.py` | Resolution order (model > task > canonical), all 6 template IDs present and non-empty, variable substitution for each template, `{{` escaping |
| `test_utils.py` | `_extract_json` three strategies + edge cases, `extract_prompt_response` all accepted key names + error cases, `merge_attr_maps` deduplication, `merge_rubrics` first-wins, `QuotaTracker` full lifecycle |

**Mocking pattern for interface tests** (not yet in the test suite but straightforward):

```python
from unittest.mock import MagicMock
from coeval.interfaces.base import ModelInterface

class FakeInterface(ModelInterface):
    def __init__(self, responses):
        self._responses = iter(responses)
    def generate(self, prompt, parameters):
        return next(self._responses)
```

Pass a `FakeInterface` wherever `iface` is expected to test phase logic
deterministically without any model.

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
> No bypass exists by design — overwriting an existing experiment silently would lose
> all its data.  Instead, increment the `experiment.id` for a fresh run, or set
> `resume_from` to continue the existing one.

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

**Q: How do I add support for a new model provider (e.g., Anthropic, Gemini)?**
> See §7.  In summary: subclass `ModelInterface`, implement `generate()`, register the
> new interface name in `ModelPool.get()`, add the name to `VALID_INTERFACES` in
> `config.py`, and write tests.  No phase code needs to change.

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

**Q: The tests run in 0.5 seconds.  How is that possible without mocking LLM calls?**
> No test touches a real model.  Config tests work entirely on in-memory dicts.  Storage
> tests use `tmp_path` (a `pathlib.Path` to a real but temporary directory).  Prompt
> tests check string manipulation.  Utils tests exercise pure functions.  The only
> external side-effect is creating and deleting temporary directories, which `pytest`
> cleans up automatically.

**Q: How do I write a test that exercises a phase without a real LLM?**
> Create a `FakeInterface` (see the pattern at the end of §9), pre-load the storage
> fixture with the required input artifacts, and pass the fake interface where the phase
> would normally call `pool.get()`.  Because `ModelPool` is just a factory/cache, you
> can also pass a pre-populated `ModelPool` with fake entries:
> ```python
> pool = ModelPool()
> pool._cache['my-model'] = FakeInterface(['{"prompt": "p", "response": "r"}'])
> ```

**Q: Why are there no integration tests that run the full pipeline?**
> The full pipeline requires downloading model weights (several GB) and significant
> compute time.  The `examples/local_smoke_test.yaml` config serves as the integration
> test — it is run manually or in a CI job that has GPU access.  The unit tests cover
> all logic paths without network or GPU dependencies.
