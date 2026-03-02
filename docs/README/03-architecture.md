# Architecture — The Five-Phase Pipeline

[← Features](02-features.md) · [Installation →](04-installation.md)

---

CoEval orchestrates LLM evaluation through a structured five-phase pipeline. Every phase is independently checkpointed, resumable, and configurable. A single YAML file drives everything.

## Pipeline Overview

```
┌──────────────────────────────────────────────────────────────────┐
│                        YAML Configuration                         │
│    models · tasks · rubric · sampling · prompts · experiment      │
└───────────────────────────┬──────────────────────────────────────┘
                            │
          ┌─────────────────▼─────────────────┐
          │  Phase 1 — Attribute Mapping       │  Teachers infer
          │  attribute_mapping                 │  task dimensions
          └─────────────────┬─────────────────┘  (or use static attrs)
                            │
          ┌─────────────────▼─────────────────┐
          │  Phase 2 — Rubric Mapping          │  Teachers build
          │  rubric_mapping                    │  evaluation criteria
          └─────────────────┬─────────────────┘  (or use static rubric)
                            │
          ┌─────────────────▼─────────────────┐
          │  Phase 3 — Data Generation         │  Teachers produce
          │  data_generation                   │  (prompt, reference)
          └─────────────────┬─────────────────┘  pairs per attribute
                            │
          ┌─────────────────▼─────────────────┐
          │  Phase 4 — Response Collection     │  Students respond
          │  response_collection               │  to Phase 3 prompts
          └─────────────────┬─────────────────┘
                            │
          ┌─────────────────▼─────────────────┐
          │  Phase 5 — Evaluation              │  Judges score
          │  evaluation                        │  student responses
          └─────────────────┬─────────────────┘  vs. reference
                            │
          ┌─────────────────▼─────────────────┐
          │  Analysis & Reports                │  8 HTML reports
          │  coeval analyze all                │  Excel · tables · ρ
          └────────────────────────────────────┘
```

## Phase Details

### Phase 1 — Attribute Mapping (`attribute_mapping`)

Teacher models map each task onto a set of **target attributes** — the structural dimensions that define the evaluation space (e.g., `{domain: [politics, sports, tech], length: [short, long]}`).

- Runs only when `target_attributes: auto` or `target_attributes: complete` is set
- Static attribute dicts skip Phase 1 entirely (zero LLM calls)
- Multiple teachers vote; attributes are merged and deduplicated
- Output written to `{task_name}.attributes.json` per task

### Phase 2 — Rubric Mapping (`rubric_mapping`)

Teacher models generate the **evaluation rubric** — a set of named criteria against which judge models will score student responses.

- Runs only when `rubric: auto` or `rubric: extend` is set
- Static rubric dicts skip Phase 2 entirely (zero LLM calls)
- `rubric: extend` merges new dimensions onto a rubric inherited from a prior run
- Output written to `{task_name}.rubric.json` per task

### Phase 3 — Data Generation (`data_generation`)

Teacher models produce **(prompt, reference_response)** pairs — the benchmark items. Each item is drawn from a sampled combination of target and nuanced attributes.

- `benchmark` interface teachers are skipped (data pre-ingested via `coeval ingest`)
- Sampling respects `sampling.target` and `sampling.nuance` ranges
- Output written to `{task_name}__{teacher_name}.datapoints.jsonl`
- Retry logic handles transient API failures (`generation_retries`)

### Phase 4 — Response Collection (`response_collection`)

Student models receive Phase 3 prompts and generate responses. Every (task, teacher, student) triple produces a JSONL file of student outputs.

- Batch API (OpenAI, Anthropic, Gemini) submits jobs and polls for completion
- Non-batch interfaces run concurrently up to the configured worker pool size
- HuggingFace models run sequentially (GPU-bound)
- Output written to `{task_name}__{teacher_name}__{student_name}.responses.jsonl`

### Phase 5 — Evaluation (`evaluation`)

Judge models score each student response against the rubric using the (prompt, student_response, reference_response) triple.

- **`evaluation_mode: single`** — one call per response; judge returns all rubric dimension scores at once
- **`evaluation_mode: per_factor`** — one call per rubric dimension per response; maximum granularity, higher cost
- Batch API support as in Phase 4
- Output written to `{task_name}__{teacher_name}__{judge_name}.evaluations.jsonl`

## Role Assignment

**Role assignment is fully flexible.** Any model can hold any combination of roles. A single model can serve as teacher, student, and judge within the same experiment.

| Role | Phases | What it does |
|------|--------|-------------|
| `teacher` | 1, 2, 3 | Discovers attributes, builds rubrics, generates synthetic benchmark items |
| `student` | 4 | Produces responses to benchmark prompts |
| `judge` | 5 | Evaluates student responses against rubric dimensions |

```yaml
# A model with all three roles participates in all five phases
- name: gpt-4o
  roles: [teacher, student, judge]
  role_parameters:
    teacher: { temperature: 0.8, max_tokens: 768 }
    student: { temperature: 0.7, max_tokens: 512 }
    judge:   { temperature: 0.0, max_tokens: 256 }
```

Per-role `role_parameters` let you fine-tune temperature, token budgets, and other generation settings independently per role without duplicating the model entry.

## Phase Execution Modes

Each phase can be configured independently:

| Mode | Behavior |
|------|----------|
| `New` | Start fresh; fails if output files already exist |
| `Keep` | Skip files that already exist; useful for adding new models to a partial run |
| `Extend` | Append only missing records; preserves existing data |
| `Model` | Use existing teacher output without re-running (Phase 3 only) |

## Storage Layout

Each experiment writes to `{storage_folder}/{experiment_id}/`:

```
{experiment_id}/
├── meta.json                                   # phase completion state
├── run.log                                     # structured log
├── probe_results.json                          # model availability probe
├── cost_estimate.json                          # pre-run cost estimate
│
├── {task}.attributes.json                      # Phase 1 output
├── {task}.rubric.json                          # Phase 2 output
│
├── {task}__{teacher}.datapoints.jsonl          # Phase 3 output
├── {task}__{teacher}__{student}.responses.jsonl  # Phase 4 output
└── {task}__{teacher}__{judge}.evaluations.jsonl  # Phase 5 output
```

---

[← Features](02-features.md) · [Installation →](04-installation.md)
