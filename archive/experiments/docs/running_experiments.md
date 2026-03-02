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
9. [Use-Case Examples](#9-use-case-examples)
   - 9.1 [First run — everything from scratch](#91-first-run--everything-from-scratch)
   - 9.2 [Resume an interrupted run](#92-resume-an-interrupted-run)
   - 9.3 [Extend an existing dataset](#93-extend-an-existing-dataset)
   - 9.4 [Re-use attributes and rubric; regenerate data only](#94-re-use-attributes-and-rubric-regenerate-data-only)
   - 9.5 [Add a new student model to a finished experiment](#95-add-a-new-student-model-to-a-finished-experiment)
   - 9.6 [Dry-run / config check](#96-dry-run--config-check)
   - 9.7 [Full OpenAI-backend experiment](#97-full-openai-backend-experiment)
10. [Validation Rules](#10-validation-rules)
11. [CLI Reference](#11-cli-reference)
12. [Frequently Asked Questions](#12-frequently-asked-questions)

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
coeval run --config experiments/configs/local_smoke_test.yaml --dry-run   # check config
coeval run --config experiments/configs/local_smoke_test.yaml             # full run
```

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
    interface: huggingface      # "huggingface" or "openai"
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
3. Canonical template from `experiments/prompts.py`

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

## 9. Use-Case Examples

### 9.1 First run — everything from scratch

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

### 9.2 Resume an interrupted run

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

### 9.3 Extend an existing dataset

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

### 9.4 Re-use attributes and rubric; regenerate data only

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

### 9.5 Add a new student model to a finished experiment

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

### 9.6 Dry-run / config check

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

### 9.7 Full OpenAI-backend experiment

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

## 10. Validation Rules

CoEval validates the configuration before any LLM call is made.
All errors are reported at once; the experiment does not start if any rule is violated.

| Rule | Description |
|------|-------------|
| V-01 | `models` and `tasks` must be present and non-empty |
| V-02 | Model names must be unique |
| V-03 | Task names must be unique |
| V-04 | Model names match `[A-Za-z0-9._-]` and must not contain `__`; task names match `[A-Za-z0-9_-]`; experiment ID matches `[A-Za-z0-9._-]` |
| V-05 | Every model must have at least one valid role (`teacher`, `student`, `judge`) |
| V-06 | Every model's `interface` must be `openai` or `huggingface` |
| V-07 | At least one model must be a `student`; at least one must be a `judge`; if any task uses `auto`/`complete` attributes or `auto`/`extend` rubric, at least one model must be a `teacher` |
| V-08 | `Model` mode is not permitted for Phase 1 (`attribute_mapping`) or Phase 2 (`rubric_mapping`) |
| V-09 | `rubric: extend` requires `experiment.resume_from` to be set |
| V-10 | If `resume_from` is set, the source experiment folder must exist in `storage_folder` |
| V-11 | For a new experiment (no `resume_from`), the target folder must not already exist — use a different ID or set `resume_from` to continue an existing run |

---

## 11. CLI Reference

```
coeval run --config PATH [options]

Options:
  --config PATH          Path to the YAML configuration file (required)
  --resume EXPERIMENT_ID Override experiment.resume_from from the command line
  --dry-run              Validate config and print the execution plan; make no LLM calls
  --log-level LEVEL      Override the log level (DEBUG | INFO | WARNING | ERROR)
```

The execution plan is always printed before the run starts (even without `--dry-run`).
Log output is written to both stdout and `{storage_folder}/{experiment_id}/run.log`.

---

## 12. Frequently Asked Questions

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
> This is validation rule V-11.  Either (a) choose a new `experiment.id`, or (b) set
> `resume_from: <your-existing-id>` to continue the interrupted run.

**Q: Can I run the same config twice?**
> Not with the same `experiment.id`.  Change the ID for each fresh run, or use
> `resume_from` to continue an existing one.

**Q: The run stopped halfway through Phase 4.  How do I continue from where it left off?**
> Create a new config with a new `experiment.id`, set `resume_from` to the failed
> experiment's ID, and set the appropriate phase modes:
> ```yaml
> phases:
>   attribute_mapping:   Keep
>   rubric_mapping:      Keep
>   data_generation:     Keep
>   response_collection: Extend   # generates only missing responses
>   evaluation:          Extend
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
> or switch to `per_factor` mode which has a simpler output format.

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
