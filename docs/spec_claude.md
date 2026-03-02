# CoEval: Software Specification

**Document ID:** COEVAL-SPEC-001 **Version:** 0.1-draft **Date:** 2026-02-22 **Status:** Draft **Sources:** CoEval_PRD · CoEval_CFG

---

## Table of Contents

0. [Motivation](https://claude.ai/local_sessions/local_d3c6fc54-c635-4117-9825-fd4a6c8733a0#0-motivation)
1. [Overview](https://claude.ai/local_sessions/local_d3c6fc54-c635-4117-9825-fd4a6c8733a0#1-overview)
2. [Architecture](https://claude.ai/local_sessions/local_d3c6fc54-c635-4117-9825-fd4a6c8733a0#2-architecture)
3. [Core Concepts](https://claude.ai/local_sessions/local_d3c6fc54-c635-4117-9825-fd4a6c8733a0#3-core-concepts)
4. [Concept of Operations](https://claude.ai/local_sessions/local_d3c6fc54-c635-4117-9825-fd4a6c8733a0#4-concept-of-operations)
   - 4.1 [New Experiment Flow](https://claude.ai/local_sessions/local_d3c6fc54-c635-4117-9825-fd4a6c8733a0#41-new-experiment-flow)
   - 4.2 [Step-by-Step Walk-Through](https://claude.ai/local_sessions/local_d3c6fc54-c635-4117-9825-fd4a6c8733a0#42-step-by-step-walk-through)
   - 4.3 [Resume Flow](https://claude.ai/local_sessions/local_d3c6fc54-c635-4117-9825-fd4a6c8733a0#43-resume-flow)
   - 4.4 [Data Flow Summary](https://claude.ai/local_sessions/local_d3c6fc54-c635-4117-9825-fd4a6c8733a0#44-data-flow-summary)
5. [Configuration Format (YAML)](https://claude.ai/local_sessions/local_d3c6fc54-c635-4117-9825-fd4a6c8733a0#5-configuration-format-yaml)
   - 5.1 [Top-Level Structure](https://claude.ai/local_sessions/local_d3c6fc54-c635-4117-9825-fd4a6c8733a0#51-top-level-structure)
   - 5.2 [Models Section](https://claude.ai/local_sessions/local_d3c6fc54-c635-4117-9825-fd4a6c8733a0#52-models-section)
   - 5.3 [Tasks Section](https://claude.ai/local_sessions/local_d3c6fc54-c635-4117-9825-fd4a6c8733a0#53-tasks-section)
   - 5.4 [Experiment Section](https://claude.ai/local_sessions/local_d3c6fc54-c635-4117-9825-fd4a6c8733a0#54-experiment-section)
6. [Evaluation Experiment Storage (EES)](https://claude.ai/local_sessions/local_d3c6fc54-c635-4117-9825-fd4a6c8733a0#6-evaluation-experiment-storage-ees)
   - 6.1 [Folder Structure](https://claude.ai/local_sessions/local_d3c6fc54-c635-4117-9825-fd4a6c8733a0#61-folder-structure)
   - 6.2 [Artifact Formats](https://claude.ai/local_sessions/local_d3c6fc54-c635-4117-9825-fd4a6c8733a0#62-artifact-formats)
7. [Pipeline Phases](https://claude.ai/local_sessions/local_d3c6fc54-c635-4117-9825-fd4a6c8733a0#7-pipeline-phases)
8. [CLI Interface](https://claude.ai/local_sessions/local_d3c6fc54-c635-4117-9825-fd4a6c8733a0#8-cli-interface)
9. [Prompt System](https://claude.ai/local_sessions/local_d3c6fc54-c635-4117-9825-fd4a6c8733a0#9-prompt-system)
10. [Model Interfaces](https://claude.ai/local_sessions/local_d3c6fc54-c635-4117-9825-fd4a6c8733a0#10-model-interfaces)
11. [Examples](https://claude.ai/local_sessions/local_d3c6fc54-c635-4117-9825-fd4a6c8733a0#11-examples)
12. [MVP Scope & Limitations](https://claude.ai/local_sessions/local_d3c6fc54-c635-4117-9825-fd4a6c8733a0#12-mvp-scope--limitations)

---

## 0. Motivation

### 0.1 The Evaluation Problem

As large language models (LLMs) become embedded in production workflows, the need to evaluate them rigorously — and continuously — has grown into a first-class engineering concern. Two distinct evaluation pressures coexist. The first is comparative: when a foundation model provider releases a new version (e.g., a new GPT or Claude generation), organizations must decide whether to adopt it, roll back, or hold, and that decision requires evidence of performance on the tasks that actually matter to them. The second is developmental: teams that fine-tune or post-train models on proprietary data need a way to measure whether the fine-tuned model outperforms its base on the target task — and by how much, and on which dimensions.

Both pressures demand evaluation that is task-specific, repeatable, and grounded in the actual distribution of inputs the model will encounter in production. Standard evaluation practice, however, is poorly equipped to meet either demand.

### 0.2 Gaps in Conventional Evaluation

**Benchmark unavailability and creation cost.** High-quality evaluation datasets require domain expertise, careful annotation, and quality control. For many specialized tasks — such as clinical documentation, legal contract review, and domain-specific data extraction — no suitable public benchmark exists. Creating one from scratch demands significant time and expert labor, often making rigorous evaluation economically infeasible for teams without dedicated ML infrastructure.

**Benchmark genericity.** Even when a benchmark exists in a related area, it is rarely a precise fit. Public benchmarks are designed for breadth: they capture average-case behavior across a wide range of inputs and phrasings, not the narrow, high-stakes slice of inputs that characterize a particular deployment. A model can score well on a general-domain reading-comprehension benchmark while systematically failing on the specific document types, terminology, and output formats it will face in production. Generic benchmarks measure a proxy, not the target.

**Benchmark contamination.** As foundation models are trained on increasingly large and diverse web corpora, the boundary between training data and evaluation data has become unreliable. Public benchmarks — including those released after a model's nominal training cutoff — are regularly found to have leaked into model training sets, either directly (the benchmark text itself) or indirectly (near-duplicate examples, derived datasets, or forum discussions that reproduce benchmark items). Contamination inflates benchmark scores and undermines the validity of comparisons between models trained at different times or by different organizations.

### 0.3 Illustrative Example

Consider a health system that has fine-tuned GPT-4o on de-identified clinical notes to generate structured follow-up reminders (e.g., "Schedule a blood test in one week"). In early 2026, OpenAI releases a new model version. The team wants to know: should they switch? Is the new base model already better than their fine-tuned predecessor, or does fine-tuning still add value for this specific output type?

No public benchmark covers this task at the required specificity — the combination of clinical note style, follow-up test types, urgency levels, and reminder phrasing expectations is entirely organization-specific. Commissioning a hand-annotated test set would require clinical reviewers and several weeks of effort. And any existing clinical NLP benchmark they might borrow (e.g., a discharge-summary dataset) is likely represented somewhere in both models' training data, making it an unreliable discriminator.

The team has no principled evaluation path. They either deploy on intuition, run informal spot-checks, or absorb the cost of a custom benchmark — none of which is satisfactory at the pace at which model versions are now released.

### 0.4 The CoEval Approach

CoEval addresses these gaps by generating evaluation data synthetically, on demand, from the task definition itself. Rather than requiring a pre-existing labeled dataset, CoEval uses a capable LLM in the Teacher role to construct benchmark items that reflect a user-specified attribute space — the range of output types, input conditions, and phrasing variations that characterize the target task. A separate model in the Judge role then scores responses against the Teacher's reference answers using a structured rubric, also generated or specified by the user.

This approach eliminates the need for hand-annotated datasets, produces benchmarks that are precisely scoped to the deployment context, and avoids contamination by generating fresh evaluation items at run time. The tradeoff — that Teacher-generated benchmarks carry the Teacher model's own biases and limitations — is a known constraint documented in §12.

---

## 1. Overview

**REQ-1.1** CoEval is a self-evaluating LLM ensemble system for benchmarking LLM performance on specific tasks without requiring pre-existing benchmark datasets.

**REQ-1.2** The system constructs a structured evaluation pipeline using three model roles:

| Role    | Responsibility                                                        |
| ------- | --------------------------------------------------------------------- |
| Teacher | Generates synthetic evaluation tasks and reference (expected) answers |
| Student | Generates responses to teacher-produced tasks                         |
| Judge   | Score student responses against the rubric using reference answers    |

**REQ-1.3** The system produces per-model, per-task, and per-rubric performance statistics, enabling model ranking and selection.

**REQ-1.4** A single model may be eligible for multiple roles. Role assignment is controlled by the `roles` field in the model config (→ REQ-5.2.1).

---

## 2. Architecture

**REQ-2.1** CoEval consists of three components sharing a common file-based storage layer:

```
┌──────────────┐     ┌──────────────┐     ┌──────────────────────┐
│  Config YAML │────▶│     EER      │────▶│  EES (Storage Layer) │
└──────────────┘     │  (CLI Tool)  │     │  File/Folder Based   │
                     └──────────────┘     └──────────┬───────────┘
                                                      │
                     ┌──────────────┐                 │
                     │     EEA      │◀────────────────┘
                     │  (CLI Tool)  │
                     └──────────────┘
```

- **EER (Evaluation Experiment Runner):** CLI tool that executes experiments and writes all artifacts to EES.
- **EEA (Evaluation Experiment Analyzer):** CLI tool that reads EES and generates HTML reports. *(Post-MVP — see §12)*
- **EES (Evaluation Experiment Storage):** Shared folder-based storage for all artifacts (→ §6).

**REQ-2.2** EER and EEA communicate exclusively through EES. No direct inter-process communication is used.

**REQ-2.3** EES is designed for incremental writes: existing artifact files are never overwritten or deleted; new content is always written to new files or appended to JSONL files (→ REQ-6.1.2).

---

## 3. Core Concepts

**REQ-3.1 Target Attributes** — A structured attribute space defining properties of the *intended output* (labels). Each attribute maps to a list of allowed values. Used to control and tag benchmark item generation (→ Phase 3, §7).

> Example: `{"test_type": ["blood test", "X-ray"], "timing": ["in 1 week", "in 1 month"]}`

**REQ-3.2 Nuanced Attributes** — Attributes that control variability in the *input* (phrasing, structure, noise, document style) without changing the target output label. Not stored in datapoint tags.

> Example: `{"note_style": ["SOAP", "narrative_paragraph"], "section": ["assessment_plan", "orders"]}`

**REQ-3.3 Benchmark Item (Datapoint)** — A `(prompt, reference_response)` pair generated by a Teacher model, with sampled target attribute values attached as metadata. Nuance attributes are used only during generation and are not persisted.

**REQ-3.4 Evaluation Rubric** — A JSON object mapping quality factor names to natural-language descriptions, used by Judge models to score each student response.

> Example: `{"test_identity_grounding": "Correctly identifies the follow-up test without introducing extra tests."}`

**REQ-3.5 Experiment ID** — A unique string identifier for each experiment run, used as the root folder name in EES and as a prefix in artifact IDs.

**REQ-3.6 Phase Resume Mode** — A per-phase directive that controls whether a phase reruns, is skipped, or is extended when resuming an experiment (→ §7).

---

## 4. Concept of Operations

This chapter describes how the system is used end-to-end, tracing the flow of control and data from a user's initial configuration through to final evaluation scores.

### 4.1 New Experiment Flow

The diagram below shows the complete sequence of steps for a fresh experiment run.

```
User
 │
 ├─[1] Author config.yaml
 │       (models, tasks, experiment)
 │
 ├─[2] coeval run --config config.yaml
 │
 └──► EER
       │
       ├─[3] Validate config
       │       • Check required fields, unique names, and valid interfaces
       │       • Exit with code 1 on error (no LLM calls made)
       │
       ├─[4] Initialize EES
       │       • Create {storage_folder}/{experiment_id}/ folder
       │       • Write config.yaml snapshot
       │       • Write meta.json (status: in_progress)
       │
       ├─[5] Phase 1 — Attribute Mapping
       │       For each task:
       │         • If target_attributes is a static map → write to EES directly
       │         • If "auto" or "complete" → call ALL Teacher models (map_target_attrs prompt)
       │         •   ↳ Parse JSON response per teacher; retry up to 3× on failure
       │         •   ↳ Merge results: union of attribute values across all teachers
       │         • Write merged {task_id}.target_attrs.json to phase1_attributes/
       │         • Repeat for nuanced_attributes → {task_id}.nuanced_attrs.json
       │       • Update meta.json
       │
       ├─[6] Phase 2 — Rubric Mapping
       │       For each task:
       │         • If the rubric is a static map → write to EES directly
       │         • If "auto" → call ALL Teacher models (autorubric prompt)
       │         •   ↳ Parse JSON response per teacher; retry up to 3× on failure
       │         •   ↳ Merge results: union of rubric factors across all teachers
       │         • Write merged {task_id}.rubric.json to phase2_rubric/
       │       • Update meta.json
       │
       ├─[7] Phase 3 — Data Generation
       │       For each task × each Teacher model:
       │         • Load target_attrs.json and nuanced_attrs.json from EES
       │         • Sample target attribute values (per sampling.target)
       │         • Sample nuanced attribute values (per sampling. nuance range)
       │         • Call Teacher with sample prompt; repeat until sampling. total items
       │         •   ↳ Parse JSON {"prompt", "response"}; retry up to 3× on failure
       │         • Append each datapoint as one line to
       │             phase3_datapoints/{task_id}.{teacher_model_id}.datapoints.jsonl
       │       • Update meta.json
       │
       ├─[8] Phase 4 — Response Collection
       │       For each task × each Teacher model × each Student model:
       │         • Load datapoints from phase3_datapoints/{task_id}.{teacher_model_id}.datapoints.jsonl
       │         • For each datapoint:
       │           - Call Student with test prompt (input = datapoint.prompt)
       │           - Append response record to
       │               phase4_responses/{task_id}.{teacher_model_id}.{student_model_id}.responses.jsonl
       │       • Update meta.json
       │
       ├─[9] Phase 5 — Evaluation
       │       For each task × each Teacher model × each Judge model:
       │         • Load rubric from phase2_rubric/
       │         • Load datapoints from phase3_datapoints/{task_id}.{teacher_model_id}.datapoints.jsonl
       │         •   ↳ Index by datapoint_id to retrieve reference_response for each response
       │         • Load responses from phase4_responses/{task_id}.{teacher_model_id}.*.responses.jsonl
       │         • For each response:
       │           - Resolve reference_response via datapoint_id → datapoints index
       │           - single mode (default): one call with full rubric → parse JSON scores
       │           - per_factor mode: one call per rubric factor → collect High|Medium|Low
       │         •   ↳ Retry up to 3× on failure (JSON parse error or transient API error)
       │         • Append evaluation record (all factor scores) to
       │             phase5_evaluations/{task_id}.{teacher_model_id}.{judge_model_id}.evaluations.jsonl
       │       • Update meta.json (status: completed)
       │
       └─[10] Done — EES contains all artifacts
               User reads JSONL files or runs coeval analyze (post-MVP)
```

### 4.2 Step-by-Step Walk-Through

**Step 1 — Author the configuration.** The user writes a YAML file declaring which models to use (and their roles), what tasks to evaluate, and experiment-level settings such as the experiment ID and storage folder. This file is the sole input to the system.

**Step 2 — Launch EER.** The user invokes `coeval run --config <path>`. Optionally, `--dry-run` can be passed to validate the config and print the execution plan without making any LLM calls.

**Step 3 — Config validation.** EER parses the YAML and checks all required fields, uniqueness constraints, valid role assignments, and supported interface types. Any error causes an immediate exit with code 1 before any LLM or filesystem operation occurs.

**Step 4 — EES initialization.** EER creates the experiment root folder under `storage_folder`, writes a snapshot of the resolved configuration as `config.yaml`, and initializes `meta.json` recording the experiment ID, creation timestamp, and phase status.

**Step 5 — Phase 1: Attribute Mapping.** For each task, EER resolves the target and nuanced attribute maps. Static maps are written directly to EES. For `auto` or `complete` modes, EER calls **all** Teacher models using the `map_target_attrs` or `map_nuanced_attrs` prompt, parses each JSON response (retrying up to three times per model on parse or transient API failures), and merges the results by taking the union of attribute values across all teachers. The merged map is written as a single task-level file.

**Step 6 — Phase 2: Rubric Mapping.** For each task, EER resolves the evaluation rubric by the same mechanism: static maps are written as-is, while `auto` mode calls **all** Teacher models with the `autorubric` prompt, merges the resulting rubric factors by union, and writes a single task-level rubric file.

**Step 7 — Phase 3: Data Generation.** For each (task, Teacher model) pair, EER samples combinations of target and nuanced attribute values and calls the Teacher model with the `sample` prompt once per benchmark item, repeating until `sampling.total` items are produced. Each item — a `(prompt, reference_response)` pair with attribute metadata — is appended as one JSONL line to the datapoints file for that (task, teacher) pair.

**Step 8 — Phase 4: Response Collection.** For each (task, Teacher model, Student model) triple, EER loads the datapoints file for that (task, teacher) pair and calls the Student model with each datapoint's prompt using the `test` prompt. Each student response is appended as one JSONL line to a separate file per (task, teacher, student) triple. Student models run independently across all triples; their output files are separate.

**Step 9 — Phase 5: Evaluation.** For each (task, Teacher model, Judge model) triple, EER loads three inputs: the rubric from Phase 2, the datapoints file from Phase 3 (indexed by `datapoint_id` to look up `reference_response`), and all response files for that (task, teacher) pair from Phase 4. For every response, EER resolves the corresponding `reference_response` via `datapoint_id`, then calls the Judge using the `evaluate` prompt in the mode specified by the task's `evaluation_mode` field. In `single` mode (default), one call is made with the full rubric, the student response, and the reference answer; the result is parsed as a JSON object of factor scores. In `per_factor` mode, one call is made per rubric factor, each returning a single word (`High`, `Medium`, or `Low`). All factor scores are collected into one evaluation record, appended as one JSONL line to a file per (task, teacher, judge) triple. The `meta.json` is updated to reflect completion.

**Step 10 — Results available.** All artifacts are now in EES. The user can inspect the JSONL files directly with Python or other tooling. Post-MVP, `coeval analyze` will read EES and produce an HTML report.

### 4.3 Resume Flow

When `resume_from` is set (or `--resume` is passed on the CLI), the flow differs at initialization:

```
User
 │
 ├─[1] Author new config.yaml with resume_from: "<prior_experiment_id>"
 │
 ├─[2] coeval run --config config.yaml
 │       (or: coeval run --config config.yaml --resume <prior_experiment_id>)
 │
 └──► EER
       │
       ├─[3] Validate config (same as new experiment)
       │
       ├─[4] Initialize new EES folder
       │       • Copy phase1_attributes/ and phase2_rubric/ artifacts
       │         from the source experiment into the new experiment folder
       │       • Write config snapshot and meta.json
       │
       ├─[5] Phase 1 — mode driven by phases.attribute_mapping
       │       • Keep  → skip; reuse copied artifacts
       │       • New   → regenerate from scratch
       │       • Extend → generate only missing attribute values
       │
       ├─[6] Phase 2 — mode driven by phases.rubric_mapping
       │       • Keep  → skip; reuse copied rubric
       │       • Extend → append new rubric factors via LLM
       │
       ├─[7] Phase 3 — mode driven by phases.data_generation
       │       • Keep  → skip; reuse existing datapoints
       │       • Extend → generate only items not yet in JSONL
       │       • Model  → generate only for model IDs not yet present
       │
       ├─[8] Phase 4 — mode driven by phases.response_collection
       │       • Keep  → skip
       │       • Extend → collect responses for datapoints not yet responded to
       │       • Model  → run only for student models not yet in outputs
       │
       ├─[9] Phase 5 — mode driven by phases.evaluation
       │       • Keep   → skip
       │       • Extend → evaluate only new rubric factors on existing responses
       │       • Model  → run only for judge models not yet in outputs
       │
       └─[10] Done
```

Phases 3–5 default to `Keep` mode when `resume_from` is set and no explicit override is provided. This allows incremental workflows such as adding a new student model (set phases 4–5 to `Model`) or extending the rubric (set phase 5 to `Extend`).

### 4.4 Data Flow Summary

The table below shows which artifact is produced by each phase and consumed by the next.

| Phase                   | Produces                     | Consumed By                                       |
| ----------------------- | ---------------------------- | ------------------------------------------------- |
| 1 — Attribute Mapping   | `phase1_attributes/*.json`   | Phase 3 (sample prompt inputs)                    |
| 2 — Rubric Mapping      | `phase2_rubric/*.json`       | Phase 5 (evaluate prompt inputs)                  |
| 3 — Data Generation     | `phase3_datapoints/{task}.{teacher}.datapoints.jsonl`         | Phase 4 (student inputs), Phase 5 (reference answers) |
| 4 — Response Collection | `phase4_responses/{task}.{teacher}.{student}.responses.jsonl` | Phase 5 (judge inputs)                                |
| 5 — Evaluation          | `phase5_evaluations/{task}.{teacher}.{judge}.evaluations.jsonl` | User / EEA (post-MVP)                               |

All artifacts are written to EES exclusively. No phase communicates with another directly — the file system is the sole integration point between phases, and between EER and EEA.

---

## 5. Configuration Format (YAML)

### 5.1 Top-Level Structure

**REQ-5.1.1** The configuration file MUST be valid YAML with exactly three top-level keys:

```yaml
models:      # list — model configurations (→ §5.2)
  - ...

tasks:       # list — task definitions (→ §5.3)
  - ...

experiment:  # map — experiment-level settings (→ §5.4)
  ...
```

**REQ-5.1.2** All three top-level keys are required. `models` and `tasks` must each contain at least one entry.

---

### 5.2 Models Section

**REQ-5.2.1** Each entry in `models` defines a single LLM configuration.

| Field             | Type       | Required | Description                                                                         |
| ----------------- | ---------- | -------- | ----------------------------------------------------------------------------------- |
| `name`            | string     | ✅        | Unique model ID. Used in EES file paths and artifact IDs. Allowed: `[A-Za-z0-9._-]`; the sequence `__` is forbidden (reserved as artifact ID separator). |
| `interface`       | enum       | ✅        | Connector type: `openai` \| `huggingface` (→ §10)                                   |
| `parameters`      | map        | ✅        | Interface-dependent inference parameters (→ §10)                                    |
| `roles`           | list[enum] | ✅        | One or more of: `student` \| `teacher` \| `judge`                                   |
| `access_key`      | string     | ❌        | API key or token. Overrides environment variable.                                   |
| `role_parameters` | map        | ❌        | Per-role parameter overrides. Merged over `parameters` at call time. (→ REQ-5.2.3)  |

**REQ-5.2.2** `name` must be unique across all model entries in the configuration.

**REQ-5.2.3** `role_parameters` keys are role names (`student`, `teacher`, `judge`). Values are partial parameter maps merged over `parameters` when the model executes in that role.

> Use case: set `temperature: 0.0` for judge role while keeping a higher temperature for teacher.

**REQ-5.2.4** A model with no `roles` entry is a validation error.

**Example:**

```yaml
models:
  - name: gpt-4o-teacher
    interface: openai
    parameters:
      model: gpt-4o
      temperature: 0.8
      max_tokens: 2048
    roles: [teacher]

  - name: ft-reminder-v2
    interface: openai
    parameters:
      model: ft:gpt-3.5-turbo:org:reminder:abc123
      temperature: 0.3
      max_tokens: 512
    roles: [student]

  - name: gpt-4o-judge
    interface: openai
    parameters:
      model: gpt-4o
      temperature: 0.0
    roles: [judge]
    role_parameters:
      teacher:
        temperature: 0.7   # if also used as a teacher in another experiment
```

---

### 5.3 Tasks Section

**REQ-5.3.1** Each entry in `tasks` defines a single evaluation task.

| Field                | Type                        | Required | Description                                                 |
| -------------------- | --------------------------- | -------- | ----------------------------------------------------------- |
| `name`               | string                      | ✅        | Unique task ID. Used in EES paths. Allowed: `[A-Za-z0-9_-]`; the sequence `__` is forbidden (reserved as artifact ID separator). |
| `description`        | string                      | ✅        | Instructions for the LLM: what to do with the input         |
| `output_description` | string                      | ✅        | Description of the expected output format or type           |
| `target_attributes`       | map \| `auto` \| `complete` | ✅        | Attribute space for output targets (→ REQ-5.3.2)            |
| `target_attributes_seed`  | map                         | ❌        | Required when `target_attributes: complete`. Partial map merged with LLM-generated extensions. |
| `nuanced_attributes`      | map \| `auto` \| `complete` | ✅        | Variability attribute space (→ REQ-5.3.3)                   |
| `nuanced_attributes_seed` | map                         | ❌        | Required when `nuanced_attributes: complete`. Partial map merged with LLM-generated extensions. |
| `sampling`                | map                         | ✅        | Benchmark item sampling strategy (→ REQ-5.3.4)              |
| `rubric`                  | map \| `auto` \| `extend`   | ✅        | Evaluation rubric definition (→ REQ-5.3.5)                  |
| `store_nuanced`           | bool                        | ❌        | If `true`, persist sampled nuanced attributes in each datapoint record. Default: `false`. |
| `evaluation_mode`         | enum                        | ❌        | Judge call granularity: `single` \| `per_factor`. Default: `single`. See §9. |
| `prompt_library`          | map                         | ❌        | Task-level prompt template overrides (→ §9)                 |

**REQ-5.3.2 `target_attributes`** accepts three forms:

- **Static map:** `{attr_name: [value1, value2, ...]}` — used as-is; Phase 1 writes to EES without calling any LLM.
- **`"auto"`** — Phase 1 calls **all** Teacher models with the `map_target_attrs` prompt; each response is parsed as JSON and the results are merged by taking the union of values per attribute. The merged map is written to EES.
- **`"complete"`** — Set `target_attributes: complete` and supply a partial map in the sibling key `target_attributes_seed`. Phase 1 calls all Teacher models to extend the seed and merges the LLM-generated values with the seed before writing to EES. Example:

```yaml
target_attributes: complete
target_attributes_seed:
  test_type: ["blood test", "X-ray"]
```

**REQ-5.3.3 `nuanced_attributes`** follows the same three modes as `target_attributes`. When using `complete` mode, supply the seed in the sibling key `nuanced_attributes_seed`:

```yaml
nuanced_attributes: complete
nuanced_attributes_seed:
  note_style: ["SOAP"]
```

**REQ-5.3.4 `sampling`** controls how benchmark items are constructed in Phase 3:

| Field    | Type                    | Required | Description                                                                          |
| -------- | ----------------------- | -------- | ------------------------------------------------------------------------------------ |
| `target` | [int, int] \| `"all"`  | ✅        | `[min, max]` range for the number of target attributes to sample per item; `"all"` includes every attribute (→ REQ-5.3.4) |
| `nuance` | [int, int]              | ✅        | `[min, max]` range for the number of nuanced attributes to sample per item           |
| `total`  | int                     | ✅        | Total number of benchmark items to generate per teacher model                        |

For each benchmark item, the following sampling algorithm is applied independently for both target and nuanced attributes:

**When `target` (or `nuance`) is `[min, max]`:**

1. **Sample count** — Draw N uniformly at random from `[min, max]`.
2. **Sample attribute names** — Select N attribute names without replacement, drawn uniformly from the full attribute map.
3. **Sample values** — For each selected attribute name, draw one value uniformly at random from that attribute's list of allowed values.

**When `target` is `"all"`** (not applicable to `nuance`):

Skip steps 1 and 2. Include every attribute name in the map. Proceed directly to step 3: for each attribute name, draw one value uniformly at random from that attribute's list of allowed values. Every datapoint will contain all target attributes, each with one sampled value.

The resulting set of (attribute name, value) pairs forms the `sampled_target_attributes` stored in the datapoint. Nuanced attribute pairs are passed to the Teacher prompt but are not persisted (→ REQ-3.3).

Sampling is performed **with replacement**: the same attribute combination may be drawn more than once across the `total` items for a given (task, teacher) pair. This is intentional — because generation is non-deterministic (e.g., temperature > 0), the same attribute combination submitted to the Teacher in separate calls will produce meaningfully different prompts and reference responses, ensuring diversity even when the attribute space is small relative to `total`.

> **Analysis note — partial attribute coverage.** When `target` is `[min, max]` with `min < total_attributes`, each datapoint will contain only a subset of the defined target attributes. For example, with `target: [1, 1]` and attributes `{test_type, urgency}`, a given datapoint tags only one of the two attributes. Downstream analysis that compares model performance by attribute value can only use datapoints that were tagged with the attribute of interest. Users should set `total` large enough to ensure adequate coverage of each attribute value, or use `target: "all"` if full attribute coverage per datapoint is required.

**REQ-5.3.5 `rubric`** accepts three forms:

- **Static map:** `{factor_name: "description"}` — used as-is; Phase 2 writes directly to EES.
- **`"auto"`** — Phase 2 calls **all** Teacher models with the `autorubric` prompt; rubric factors are merged by union across all responses. The merged rubric is written to EES.
- **`"extend"`** — An existing rubric is loaded from EES, all Teacher models are called to generate additional factors, and the new factors are merged with the existing rubric before writing to EES.

**Example:**

```yaml
tasks:
  - name: followup_reminder
    description: "Extract follow-up test from the medical visit summary."
    output_description: "A polite reminder message to the patient to follow the instructions."
    target_attributes:
      test_type: ["blood test", "X-ray", "EKG", "MRI"]
      timing: ["in 1 week", "in 1 month", "in 3 months"]
      urgency: ["routine", "urgent"]
    nuanced_attributes: auto
    sampling:
      target: [1, 1]
      nuance: [1, 3]
      total: 50
    rubric:
      test_identity_grounding: "Correctly identifies the follow-up test. Does not introduce extra tests."
      timing_grounding: "States timing exactly as written. No modification or shift."
      instruction_fidelity: "Reflects only instructions in the note. No hallucinated medical advice."
      specificity_without_hallucination: "Adds helpful non-speculative specificity; avoids invented details."
```

---

### 5.4 Experiment Section

**REQ-5.4.1** The `experiment` section controls run identity, storage, and phase behavior.

| Field            | Type   | Required | Description                                                                         |
| ---------------- | ------ | -------- | ----------------------------------------------------------------------------------- |
| `id`             | string | ✅        | Unique experiment ID. Root folder name in EES. Allowed: `[A-Za-z0-9._-]`            |
| `storage_folder` | string | ✅        | Absolute or relative path to the EES root directory                                 |
| `resume_from`    | string | ❌        | Experiment ID to resume or extend. The source experiment's EES folder must exist.   |
| `phases`         | map    | ❌        | Per-phase mode overrides. Keys are phase IDs (→ §7). Default: `New` for all phases. |
| `log_level`      | enum   | ❌        | `DEBUG` \| `INFO` \| `WARNING` \| `ERROR`. Default: `INFO`                          |
| `quota`          | map    | ❌        | Optional per-model call limits: `{model_name: {max_calls: int}}`. When a model's limit is reached, EER stops calling that model for the remainder of the current phase, writes a `WARNING`-level entry to the log file, and continues processing with any remaining models. Phases that require the quota-exhausted model and have no substitute will produce incomplete output for that model. |

**Example:**

```yaml
experiment:
  id: "followup-v1"
  storage_folder: "./eval_runs"
  log_level: INFO
  phases:
    attribute_mapping: New
    rubric_mapping: New
    data_generation: New
    response_collection: New
    evaluation: New
```

---

### 5.5 Configuration Validation

EER validates the configuration file before any LLM call or filesystem operation is performed. All validation errors are reported together in a single pass with descriptive messages identifying the offending field, its value, and the rule it violated. EER exits with code 1 if any validation error is found (→ REQ-8.1.5).

The following validations are applied, in order:

| # | Rule | Error Example |
|---|------|---------------|
| V-01 | All three top-level keys (`models`, `tasks`, `experiment`) are present and non-empty | `Missing required top-level key: 'tasks'` |
| V-02 | All model `name` values are unique within the config | `Duplicate model name: 'gpt-4o'` |
| V-03 | All task `name` values are unique within the config | `Duplicate task name: 'followup_reminder'` |
| V-04 | Model and task `name` values match their allowed character sets; `name` must not contain `__` | `Invalid model name 'my__model': contains reserved separator '__'` |
| V-05 | Each model has at least one `role`; all role values are from `{student, teacher, judge}` | `Unknown role 'reviewer' in model 'gpt-4o'` |
| V-06 | Each model's `interface` is a recognized value (`openai` \| `huggingface`) | `Unknown interface 'anthropic' in model 'claude'` |
| V-07 | At least one model is assigned each role required by the experiment: `teacher` (phases 1–3 when not using static maps), `student` (phase 4), `judge` (phase 5) | `No model assigned role 'judge'; required for phase 5` |
| V-08 | `Model` resume mode is not set for phases 1 or 2 | `Phase 'attribute_mapping' does not support mode 'Model'` |
| V-09 | `rubric: extend` is only used when `experiment.resume_from` is set | `rubric: extend requires resume_from to be set in experiment` |
| V-10 | `resume_from` experiment folder exists under `storage_folder` when specified | `Source experiment 'followup-v1' not found in ./runs` |
| V-11 | For new experiments (no `resume_from`), the target experiment folder must not already exist under `storage_folder` | `Experiment folder 'followup-v1' already exists in './runs'. Use resume_from to continue it, or choose a different experiment ID.` |

---

## 6. Evaluation Experiment Storage (EES)

### 6.1 Folder Structure

**REQ-6.1.1** EES uses a two-level hierarchy: experiment root → phase subfolder → artifact files.

**REQ-6.1.2** EES lifecycle management is out of scope for MVP. Experiment folders are user-managed; EER does not delete or prune any EES content automatically.

```
{storage_folder}/
└── {experiment_id}/
    ├── meta.json                                           # Experiment metadata (→ REQ-6.2.1)
    ├── config.yaml                                         # Snapshot of resolved input config
    ├── run.log                                             # Execution log (→ REQ-6.1.5)
    │
    ├── phase1_attributes/
    │   ├── {task_id}.target_attrs.json                     # Target attribute map (→ REQ-6.2.2)
    │   └── {task_id}.nuanced_attrs.json                    # Nuanced attribute map (→ REQ-6.2.2)
    │
    ├── phase2_rubric/
    │   └── {task_id}.rubric.json                           # Evaluation rubric (→ REQ-6.2.3)
    │
    ├── phase3_datapoints/
    │   └── {task_id}.{teacher_model_id}.datapoints.jsonl  # Benchmark items (→ REQ-6.2.4)
    │
    ├── phase4_responses/
    │   └── {task_id}.{teacher_model_id}.{student_model_id}.responses.jsonl   # Student responses (→ REQ-6.2.5)
    │
    └── phase5_evaluations/
        └── {task_id}.{teacher_model_id}.{judge_model_id}.evaluations.jsonl   # Judge scores (→ REQ-6.2.6)
```

**REQ-6.1.2** Files are **append-only**. Existing files MUST NOT be overwritten or deleted. Resuming a phase appends records to existing JSONL files or creates new per-model files for `Model` mode.

**REQ-6.1.3** Each JSONL file contains one JSON object per line with no blank lines. UTF-8 encoding. No trailing whitespace.

**REQ-6.1.4** New experiments initialized from `resume_from` inherit phases 1–2 artifact files by copying (not symlinking) them into the new experiment folder before EER begins execution.

**REQ-6.1.5** EER writes a log file at `{experiment_id}/run.log`. One entry per line. Each line follows the format:

```
{ISO8601_UTC_timestamp} [{LEVEL}] {message}
```

Example:
```
2026-02-22T10:00:00Z [INFO] Experiment followup-v1 started
2026-02-22T10:01:30Z [WARNING] Quota exhausted for model gpt-4o-teacher after 100 calls in phase data_generation
2026-02-22T10:05:00Z [ERROR] Phase response_collection failed for (followup_reminder, ft-reminder-v2): API timeout after 3 retries
```

The log file is opened in append mode so that resumed runs extend the same file. Log level filtering is controlled by `experiment.log_level` (→ §5.4); entries below the configured level are not written.

---

### 6.2 Artifact Formats

#### REQ-6.2.1 Experiment Metadata — `meta.json.`

| Field               | Type             | Description                                                                                          |
| ------------------- | ---------------- | ---------------------------------------------------------------------------------------------------- |
| `experiment_id`     | string           | Matches `experiment.id` in config                                                                    |
| `status`            | enum             | `"in_progress"` \| `"completed"` \| `"failed"`. Set to `in_progress` at initialization; updated to `completed` when all phases finish successfully, or `failed` if EER exits with errors. |
| `created_at`        | string           | ISO 8601 UTC timestamp of experiment initialization                                                  |
| `updated_at`        | string           | ISO 8601 UTC timestamp of last update                                                                |
| `phases_completed`  | list[string]     | Phase IDs that have finished successfully, in order                                                  |
| `phases_in_progress`| list[string]     | Phase IDs currently executing (at most one in the sequential MVP pipeline)                           |
| `resume_from`       | string \| null   | Source experiment ID if this experiment was resumed; `null` otherwise                                |

```json
{
  "experiment_id": "followup-v1",
  "status": "in_progress",
  "created_at": "2026-02-22T10:00:00Z",
  "updated_at": "2026-02-22T12:30:00Z",
  "phases_completed": ["attribute_mapping", "rubric_mapping", "data_generation"],
  "phases_in_progress": ["response_collection"],
  "resume_from": null
}
```

EER writes `meta.json` at initialization (status: `in_progress`) and updates it after each phase completes. On successful completion of all phases, `status` is set to `completed`. If EER exits with errors after the fail-after-all-pairs pass, `status` is set to `failed`.

---

#### REQ-6.2.2 Attribute Maps — `{task_id}.target_attrs.json` / `{task_id}.nuanced_attrs.json`

Plain JSON object. No wrapper envelope. Written once per task in Phase 1.

```json
{
  "test_type": ["blood test", "X-ray", "EKG", "MRI"],
  "timing": ["in 1 week", "in 1 month", "in 3 months"],
  "urgency": ["routine", "urgent"]
}
```

---

#### REQ-6.2.3 Rubric — `{task_id}.rubric.json`

Plain JSON object. No wrapper envelope. Written once per task in Phase 2.

```json
{
  "test_identity_grounding": "Correctly identifies the follow-up test. Does not introduce extra tests.",
  "timing_grounding": "States timing exactly as written. No modification or shift.",
  "instruction_fidelity": "Reflects only instructions in the note. No hallucinated medical advice.",
  "specificity_without_hallucination": "Adds helpful non-speculative specificity; avoids invented details."
}
```

---

#### REQ-6.2.4 Datapoints — `{task_id}.{teacher_model_id}.datapoints.jsonl`

One JSON object per line. One file per (task, teacher model) pair.

| Field                        | Type   | Required | Description                                                                                         |
| ---------------------------- | ------ | -------- | --------------------------------------------------------------------------------------------------- |
| `id`                         | string | ✅        | `{task_id}__{teacher_model_id}__{seq:05d}` — globally unique                                        |
| `task_id`                    | string | ✅        | Cross-ref to task name in config                                                                    |
| `teacher_model_id`           | string | ✅        | Cross-ref to model name in config                                                                   |
| `sampled_target_attributes`  | map    | ✅        | Attribute key-value pairs used to generate this item                                                |
| `sampled_nuanced_attributes` | map    | ❌        | Nuanced attribute key-value pairs used during generation. Present only if `store_nuanced: true` is set in the task config (default: omitted). |
| `prompt`                     | string | ✅        | Input to the student model                                                                          |
| `reference_response`         | string | ✅        | Teacher's ideal answer                                                                              |
| `generated_at`               | string | ✅        | ISO 8601 UTC timestamp                                                                              |

**Example line (single-line JSONL):**

```json
{"id": "followup_reminder__gpt-4o-teacher__00001", "task_id": "followup_reminder", "teacher_model_id": "gpt-4o-teacher", "sampled_target_attributes": {"test_type": "blood test", "timing": "in 1 week"}, "prompt": "SUBJECTIVE:\nPatient reports ongoing fatigue and occasional dizziness over the past 2 weeks.\n\nPLAN:\n1) Repeat blood work in 1 week.", "reference_response": "Hello, this is a friendly reminder to please complete your blood test in 1 week as listed in your visit plan.", "generated_at": "2026-02-22T10:15:00Z"}
```

---

#### REQ-6.2.5 Responses — `{task_id}.{teacher_model_id}.{student_model_id}.responses.jsonl`

One JSON object per line. One file per (task, teacher model, student model) triple.

| Field              | Type   | Description                                                |
| ------------------ | ------ | ---------------------------------------------------------- |
| `id`               | string | `{datapoint_id}__{student_model_id}` — globally unique     |
| `datapoint_id`     | string | Cross-ref to source datapoint (→ REQ-6.2.4)                |
| `task_id`          | string | Cross-ref to task name in config                           |
| `teacher_model_id` | string | Cross-ref to teacher model that generated the datapoint    |
| `student_model_id` | string | Cross-ref to model name in config                          |
| `input`            | string | Full prompt sent to student (copied from datapoint.prompt) |
| `response`         | string | Student model output                                       |
| `generated_at`     | string | ISO 8601 UTC timestamp                                     |

**Example line:**

```json
{"id": "followup_reminder__gpt-4o-teacher__00001__ft-reminder-v2", "datapoint_id": "followup_reminder__gpt-4o-teacher__00001", "task_id": "followup_reminder", "teacher_model_id": "gpt-4o-teacher", "student_model_id": "ft-reminder-v2", "input": "SUBJECTIVE:\nPatient reports ongoing fatigue...\n\nPLAN:\n1) Repeat blood work in 1 week.", "response": "Hello—this is a friendly reminder to complete your follow-up blood work in 1 week as outlined in your visit plan.", "generated_at": "2026-02-22T10:30:00Z"}
```

---

#### REQ-6.2.6 Evaluations — `{task_id}.{teacher_model_id}.{judge_model_id}.evaluations.jsonl`

One JSON object per line. One file per (task, teacher model, judge model) triple.

| Field              | Type   | Description                                                                       |
| ------------------ | ------ | --------------------------------------------------------------------------------- |
| `id`               | string | `{response_id}__{judge_model_id}` — globally unique                               |
| `response_id`      | string | Cross-ref to source response (→ REQ-6.2.5)                                        |
| `datapoint_id`     | string | Cross-ref to source datapoint (→ REQ-6.2.4)                                       |
| `task_id`          | string | Cross-ref to task name in config                                                  |
| `teacher_model_id` | string | Cross-ref to teacher model that generated the datapoint                           |
| `judge_model_id`   | string | Cross-ref to model name in config                                                 |
| `scores`           | map    | `{rubric_factor_name: "High" \| "Medium" \| "Low"}` — one entry per rubric factor |
| `evaluated_at`     | string | ISO 8601 UTC timestamp                                                            |

**Example line:**

```json
{"id": "followup_reminder__gpt-4o-teacher__00001__ft-reminder-v2__gpt-4o-judge", "response_id": "followup_reminder__gpt-4o-teacher__00001__ft-reminder-v2", "datapoint_id": "followup_reminder__gpt-4o-teacher__00001", "task_id": "followup_reminder", "teacher_model_id": "gpt-4o-teacher", "judge_model_id": "gpt-4o-judge", "scores": {"test_identity_grounding": "High", "timing_grounding": "High", "instruction_fidelity": "Medium", "specificity_without_hallucination": "High"}, "evaluated_at": "2026-02-22T10:45:00Z"}
```

---

## 7. Pipeline Phases

**REQ-7.1** EER executes experiments as a sequential 5-phase pipeline. Phases run in order 1–5.

| #   | Phase ID              | Description                                                    | Output Files                 |
| --- | --------------------- | -------------------------------------------------------------- | ---------------------------- |
| 1   | `attribute_mapping`   | Generate or load target and nuanced attribute maps per task    | `phase1_attributes/*.json`   |
| 2   | `rubric_mapping`      | Generate or load the evaluation rubric per task                | `phase2_rubric/*.json`       |
| 3   | `data_generation`     | The teacher model generates benchmark datapoints               | `phase3_datapoints/*.jsonl`  |
| 4   | `response_collection` | Student models generate responses per (task, teacher, student) triple | `phase4_responses/*.jsonl`   |
| 5   | `evaluation`          | Judge models score each response per (task, teacher, judge) triple; call granularity controlled by `evaluation_mode` (→ REQ-5.3.1) | `phase5_evaluations/*.jsonl` |

**REQ-7.2 Phase Resume Modes**

| Mode     | Behavior                                        | Valid Phases | Modifies Existing Files  |
| -------- | ----------------------------------------------- | ------------ | ------------------------ |
| `New`    | Fully regenerate from scratch                   | 1–5          | No                       |
| `Keep`   | Skip phase; reuse existing outputs as-is        | 1–5          | No                       |
| `Extend` | Process only items not yet present in outputs   | 1–5          | No (appends JSONL)       |
| `Model`  | Run phase only for model IDs not yet in outputs | 3–5          | No (new per-model files) |

**REQ-7.3** `Model` mode is only valid for phases 3, 4, and 5. Using it for phases 1 or 2 is a validation error.

**REQ-7.4** In `Extend` mode for Phase 3, EER counts the number of lines already present in the JSONL file for each (task, teacher) pair and generates `sampling.total − existing_count` additional items, appending them to the existing file. If `existing_count ≥ sampling.total`, the phase is skipped for that pair with an informational log entry.

**REQ-7.5** Phase 5 requires three inputs for each (task, teacher, judge) triple: (1) the rubric from `phase2_rubric/`, (2) the datapoints file from `phase3_datapoints/` — loaded and indexed by `datapoint_id` in memory to resolve `reference_response` for each response — and (3) all response files matching `phase4_responses/{task_id}.{teacher_model_id}.*.responses.jsonl`. EER MUST NOT call the Judge without a resolved `reference_response`; if a `datapoint_id` referenced by a response record is missing from the datapoints file, EER logs an ERROR and skips that response.

**REQ-7.6** In `Extend` mode for Phase 5, EER loads the rubric from EES, diffs it against the config rubric, and evaluates only the new rubric factors for all existing response records.

**REQ-7.7** Default mode for all phases in a new experiment (no `resume_from`) is `New`.

**REQ-7.8** When `resume_from` is set, EES artifacts from the source experiment's phases 1 and 2 are copied into the new experiment folder. Phases 3–5 inherit `Keep` by default unless overridden in `phases`.

---

## 8. CLI Interface

### 8.1 EER — `coeval run.`

**REQ-8.1.1** Command signature:

```
coeval run --config <path> [--resume <experiment_id>] [--dry-run] [--log-level <level>]
```

| Flag                  | Required | Description                                                             |
| --------------------- | -------- | ----------------------------------------------------------------------- |
| `--config <path>`     | ✅        | Path to YAML configuration file                                         |
| `--resume <id>`       | ❌        | Experiment ID to resume. Overrides `experiment.resume_from` in config.  |
| `--dry-run`           | ❌        | Validate config, print execution plan, exit without calling any LLM API |
| `--log-level <level>` | ❌        | Override config `log_level.`                                            |

**REQ-8.1.2** On startup, EER prints an execution plan to stdout:

- Experiment ID and storage path
- For each phase: mode, which tasks and models will be processed
- Estimated LLM call counts per model (for dry-run: exact counts)

**REQ-8.1.3** EER writes `config.yaml` (resolved config snapshot) and initializes `meta.json` before Phase 1 begins. `meta.json` is updated after each phase completes.

**REQ-8.1.4** If one or more (task, model) pairs fail during a phase, EER continues processing all remaining pairs before exiting. All errors are collected and reported together after the phase completes. EER exits with a non-zero code only after all pairs in the phase have been attempted. Partially written JSONL files are preserved. The run can be resumed with `Extend` or `Model` mode.

**REQ-8.1.5** All configuration validation rules (→ §5.5) are applied before any LLM call or filesystem operation. All errors are reported together in a single pass with descriptive messages. EER exits with code 1 if any validation error is found.

### 8.2 EEA — `coeval analyze` *(Post-MVP)*

Full specification in COEVAL-SPEC-002. Summary of the command interface:

```
coeval analyze <subcommand> --run <path> --out <path> [options]
```

Available subcommands: `complete-report`, `score-distribution`, `teacher-report`, `judge-report`, `student-report`, `interaction-matrix`, `judge-consistency`, `coverage-summary`, `robust-summary`, `export-benchmark`, `all`.

Key options: `--agreement-metric <spa|wpa|kappa>`, `--agreement-threshold <float>`, `--judge-selection <top_half|all>`, `--teacher-score-formula <v1|s2|r3>`, `--benchmark-format <jsonl|parquet>`, `--partial-ok`.

EEA is a read-only consumer of EES. It does not write to or modify any EES artifact. All outputs go to the directory specified by `--out`.

---

## 9. Prompt System

**REQ-9.1** The system defines six canonical prompt types used across pipeline phases.

| Prompt ID           | Phase | Role    | Description                                |
| ------------------- | ----- | ------- | ------------------------------------------ |
| `map_target_attrs`  | 1     | Teacher | Generate target attribute space            |
| `map_nuanced_attrs` | 1     | Teacher | Generate a nuanced attribute space         |
| `autorubric`        | 2     | Teacher | Generate an evaluation rubric              |
| `sample`            | 3     | Teacher | Generate a single benchmark datapoint      |
| `test`              | 4     | Student | Produce a response for a given input       |
| `evaluate`          | 5     | Judge   | Score a response against one rubric factor |

**REQ-9.2 Canonical Prompt Templates**

Template variables use `{variable_name}` syntax. All variables are required unless marked optional.

**`map_target_attrs`:**

```
Generate synthetic data specifications for the {task_description} task by defining an attribute
space that characterizes possible outputs. Return a JSON object mapping each attribute name to
a list of possible values, and output only the JSON.
```

**`map_nuanced_attrs`:**

```
Define synthetic data specifications for the {task_description} task by creating a nuanced
variability-focused attribute space. Include only attributes that change document phrasing,
structure, noise, and context—without changing the underlying outputs. Return a single JSON
object mapping each attribute name to a list of allowed values, and output only the JSON.
```

**`autorubric`:**

```
For the task {task_description}, where the model's output is {output_description}, create an
evaluation rubric. Return only a JSON object where each key is a quality factor, and each value
is a concise description of that factor. Output only the JSON.
```

**`sample`:**

```
Generate a natural benchmark data point for the task {task_description} and produce a response
{output_description}, where the response is specified with {target_attributes}. To make the
datapoint naturalistic, use the following nuance parameters: {nuanced_attributes}. Return as
JSON with exactly two keys: "prompt" and "response".
```

**`test`:**

```
Given the datapoint: {input}
Perform the following task: {task_description}
Produce the response: {output_description}
```

**`evaluate` — `single` mode (default):**

One call per response. The Judge receives the full rubric and returns a JSON object mapping each factor name to a score.

```
Evaluate the following student response for the task "{task_description}" that produces
"{output_description}", given input "{input}" and known attributes {target_attributes}.

Reference answer: {reference_response}
Student response: {response}

Score the student response against each of the following rubric factors:
{rubric}

Return only a JSON object where each key is a rubric factor name and each value is one of:
"High", "Medium", or "Low". Output only the JSON.
```

**`evaluate` — `per_factor` mode:**

One call per rubric factor per response. The Judge receives a single factor and returns one word.

```
Evaluate the following student response for the task "{task_description}" that produces
"{output_description}", with input "{input}" and known attributes {target_attributes}.

Reference answer: {reference_response}
Student response: {response}

According to rubric factor "{rubric_factor_name}": "{rubric_factor_description}".
Return one word: High, Medium, or Low.
```

The `evaluation_mode` task field (→ REQ-5.3.1) controls which variant is used. In `single` mode, the response to the `evaluate` prompt is parsed as JSON; if parsing fails, the call is retried up to 3 times before the phase exits with an error. In `per_factor` mode, each call returns a single word; no JSON parsing is required.

**REQ-9.3** Prompt overrides are specified in the `prompt_library` field of a task. A task-level override replaces the full canonical template for that prompt ID within that task only.

**REQ-9.4** Per-model overrides use the key `{prompt_id}.{model_name}`. Model-specific overrides take precedence over task-level overrides.

```yaml
prompt_library:
  sample: "Custom template for all models on this task..."
  sample.ft-reminder-v2: "Custom template only for ft-reminder-v2..."
```

**REQ-9.5** LLM responses to structured prompts (`map_target_attrs`, `map_nuanced_attrs`, `autorubric`, `sample`, and `evaluate` in `single` mode) MUST be parsed as JSON. If parsing fails, the call is retried up to 3 times. If all retries fail, the phase exits with an error. The `evaluate` prompt in `per_factor` mode returns a single word and requires no JSON parsing; if the response is not one of `High`, `Medium`, or `Low`, the call is retried up to 3 times before the phase exits with an error.

---

## 10. Model Interfaces

**REQ-10.1** Both interfaces MUST implement a common contract:

```python
def generate(prompt: str, parameters: dict) -> str
```

Role-parameter overrides (→ REQ-5.2.3) are merged into `parameters` before each call.

**REQ-10.2 OpenAI Interface**

| Parameter       | Type   | Description                                                         |
| --------------- | ------ | ------------------------------------------------------------------- |
| `model`         | string | OpenAI model identifier (e.g., `gpt-4o`, `gpt-3.5-turbo`, `ft:...`) |
| `temperature`   | float  | Sampling temperature (0.0–2.0)                                      |
| `max_tokens`    | int    | Maximum completion tokens                                           |
| `system_prompt` | string | *(optional)* System message prepended to each call                  |

Authentication: environment variable `OPENAI_API_KEY`, or `access_key` in model config (→ REQ-5.2.1).

**REQ-10.3 HuggingFace Interface**

The HuggingFace interface loads model weights **locally** using the `transformers` library (`transformers.pipeline("text-generation", ...)`). Model weights are downloaded from the HuggingFace Hub on first use and cached locally. No remote inference API is used.

| Parameter        | Type   | Description                                                    |
| ---------------- | ------ | -------------------------------------------------------------- |
| `model`          | string | HuggingFace repo ID (e.g., `meta-llama/Llama-3.2-8B-Instruct`) |
| `temperature`    | float  | Sampling temperature                                           |
| `max_new_tokens` | int    | Maximum new tokens to generate                                 |
| `device`         | string | `"cpu"` \| `"cuda"` \| `"auto"` — passed directly to `pipeline(device=...)` |

Authentication: environment variable `HF_TOKEN`, or `access_key` in model config. Required for gated models; public models may omit it.

**REQ-10.4** All LLM calls are retried up to **3 times** with exponential backoff (initial delay: 1 s, multiplier: 2) on transient errors (rate limits, timeouts, 5xx responses). Non-transient errors (invalid API key, model not found) cause immediate failure.

---

## 11. Examples

### Example 11.1 — Minimal Single-Model Configuration

All roles are assigned to one model. Attribute maps and rubrics are auto-generated.

```yaml
models:
  - name: gpt-4o
    interface: openai
    parameters:
      model: gpt-4o
      temperature: 0.7
      max_tokens: 1024
    roles: [teacher, student, judge]

tasks:
  - name: followup_reminder
    description: "Extract follow-up test from the medical visit summary."
    output_description: "A polite reminder message to the patient to follow the instructions."
    target_attributes: auto
    nuanced_attributes: auto
    sampling:
      target: [1, 1]
      nuance: [1, 2]
      total: 20
    rubric: auto

experiment:
  id: "followup-demo-v1"
  storage_folder: "./runs"
```

---

### Example 11.2 — Multi-Model Experiment with Static Rubric

Two student models (OpenAI fine-tuned + HuggingFace) were evaluated by a dedicated judge.

```yaml
models:
  - name: gpt-4o-teacher
    interface: openai
    parameters: {model: gpt-4o, temperature: 0.8, max_tokens: 2048}
    roles: [teacher]

  - name: ft-reminder-v2
    interface: openai
    parameters: {model: ft:gpt-3.5-turbo:org:reminder:abc123, temperature: 0.3, max_tokens: 512}
    roles: [student]

  - name: hf-llama-student
    interface: huggingface
    parameters: {model: meta-llama/Llama-3.2-8B-Instruct, temperature: 0.3, max_new_tokens: 512, device: auto}
    roles: [student]

  - name: gpt-4o-judge
    interface: openai
    parameters: {model: gpt-4o, temperature: 0.0}
    roles: [judge]

tasks:
  - name: followup_reminder
    description: "Extract follow-up test from the medical visit summary."
    output_description: "A polite reminder message to the patient to follow the instructions."
    target_attributes:
      test_type: ["blood test", "X-ray", "EKG"]
      timing: ["in 1 week", "in 1 month"]
    nuanced_attributes: auto
    sampling:
      target: [1, 1]
      nuance: [1, 3]
      total: 50
    rubric:
      test_identity_grounding: "Correctly identifies the follow-up test. Does not introduce extra tests."
      timing_grounding: "States timing exactly as written. No modification."
      instruction_fidelity: "Reflects only instructions in the note. No hallucinated advice."
      tone_and_clarity: "Message is polite, clear, and suitable for patient communication."

experiment:
  id: "followup-multimodel-v1"
  storage_folder: "./runs"
  log_level: INFO
```

---

### Example 11.3 — Resume: Add a New Student Model

Inherits attributes, rubric, and datapoints from v1. Runs only response collection and evaluation for the new model.

```yaml
models:
  # ... same as Example 11.2, plus:
  - name: gpt-4o-student
    interface: openai
    parameters: {model: gpt-4o, temperature: 0.3, max_tokens: 512}
    roles: [student]

experiment:
  id: "followup-multimodel-v2"
  storage_folder: "./runs"
  resume_from: "followup-multimodel-v1"
  phases:
    attribute_mapping: Keep     # reuse phase1_attributes/ from v1
    rubric_mapping: Keep        # reuse phase2_rubric/ from v1
    data_generation: Keep       # reuse phase3_datapoints/ from v1
    response_collection: Model  # run only for gpt-4o-student
    evaluation: Model           # run only for new response files
```

---

### Example 11.4 — End-to-End Artifact Chain (medical follow-up task)

This example traces one benchmark item through all five phases.

**Phase 1 — `followup_reminder.target_attrs.json`:**

```json
{"test_type": ["blood test", "X-ray"], "timing": ["in 1 week", "in 1 month"]}
```

**Phase 2 — `followup_reminder.rubric.json`:**

```json
{"test_identity_grounding": "Correctly identifies the follow-up test.", "timing_grounding": "States timing exactly as written."}
```

**Phase 3 — `followup_reminder.gpt-4o-teacher.datapoints.jsonl` (one line):**

```json
{"id": "followup_reminder__gpt-4o-teacher__00001", "task_id": "followup_reminder", "teacher_model_id": "gpt-4o-teacher", "sampled_target_attributes": {"test_type": "blood test", "timing": "in 1 week"}, "prompt": "PLAN:\n1) Repeat blood work in 1 week.", "reference_response": "Please complete your blood test in 1 week.", "generated_at": "2026-02-22T10:15:00Z"}
```

**Phase 4 — `followup_reminder.gpt-4o-teacher.ft-reminder-v2.responses.jsonl` (one line):**

```json
{"id": "followup_reminder__gpt-4o-teacher__00001__ft-reminder-v2", "datapoint_id": "followup_reminder__gpt-4o-teacher__00001", "task_id": "followup_reminder", "teacher_model_id": "gpt-4o-teacher", "student_model_id": "ft-reminder-v2", "input": "PLAN:\n1) Repeat blood work in 1 week.", "response": "Hello—please complete your blood work in 1 week as outlined.", "generated_at": "2026-02-22T10:30:00Z"}
```

**Phase 5 — `followup_reminder.gpt-4o-teacher.gpt-4o-judge.evaluations.jsonl` (one line):**

```json
{"id": "followup_reminder__gpt-4o-teacher__00001__ft-reminder-v2__gpt-4o-judge", "response_id": "followup_reminder__gpt-4o-teacher__00001__ft-reminder-v2", "datapoint_id": "followup_reminder__gpt-4o-teacher__00001", "task_id": "followup_reminder", "teacher_model_id": "gpt-4o-teacher", "judge_model_id": "gpt-4o-judge", "scores": {"test_identity_grounding": "High", "timing_grounding": "High"}, "evaluated_at": "2026-02-22T10:45:00Z"}
```

---

## 12. MVP Scope & Limitations

**REQ-12.1** The MVP implements EER only. EEA (report generation) is post-MVP.

**REQ-12.2** Supported interfaces: `openai` and `huggingface` only. Additional interfaces are post-MVP.

**REQ-12.3** Task type: text-to-text only. Each datapoint is a `(prompt, reference_response)` pair. Multi-turn, multi-modal, and structured output tasks are post-MVP.

**REQ-12.4** Execution is local and sequential (single-threaded LLM calls). No parallelism. EES uses the local filesystem only. Cloud execution and distributed storage are post-MVP.

**REQ-12.5** Analysis and reporting in MVP is performed externally by reading EES JSONL files with Python or other tools.

**REQ-12.6** Benchmark synthesis (distilling high-dispersion items into a reusable static benchmark) is post-MVP despite being described in the PRD.

**REQ-12.7 — Usage note: same-model role overlap and self-judging.** The spec permits a single model to hold all three roles simultaneously (`roles: [teacher, student, judge]`). This is a valid configuration — for example, when only one model is available or when testing self-consistency — but it introduces two known biases that users must account for during analysis:

- **Self-grading bias.** When the same model acts as both student and judge, it tends to score its own responses more generously than an independent judge would. This is a well-documented phenomenon in LLM-as-judge research. Users comparing models should treat same-model (student == judge) evaluation scores as potentially inflated relative to cross-model scores.
- **Circular evaluation.** When a model acts as teacher, student, and judge for the same (task, datapoint), the student already "knows" the expected output format from having generated the datapoint as teacher. This can artificially inflate student performance on teacher-generated items from the same model. Cross-model evaluation files (where teacher ≠ student and judge is independent) are the most reliable basis for model comparison.

EER does not prevent or warn about same-model overlap; detection and interpretation is the user's responsibility.

**REQ-12.8 — Usage note: Phase 5 artifact volume scales as M² × T.** With M models each assigned all roles and T tasks, Phase 5 produces M² × T evaluation files, each containing M × `sampling.total` records. Total evaluation records = M³ × T × `sampling.total`. Example: 5 models, 3 tasks, 10 datapoints per teacher → 5² × 3 = 75 files, 5³ × 3 × 10 = 3,750 evaluation records. Users should size `sampling.total` and the number of multi-role models accordingly when storage or runtime is a concern.

---

*Document end. Cross-reference key: REQ-N.N = requirement; §N = section.*
