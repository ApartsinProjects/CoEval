# Architecture — The Five-Phase Pipeline

[← Recovery](09-recovery.md) · [Testing →](11-testing.md)

---

CoEval orchestrates LLM evaluation through a structured five-phase pipeline. Every phase is independently checkpointed, resumable, and configurable. A single YAML file drives everything.

> **Code entry point:** [`Code/runner/cli.py`](../../Code/runner/cli.py) → [`Code/runner/runner.py`](../../Code/runner/runner.py) orchestrates the five phases; config is loaded and validated by [`Code/runner/config.py`](../../Code/runner/config.py).

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

> **Code:** [`Code/runner/phases/phase1.py`](../../Code/runner/phases/phase1.py)

Teacher models map each task onto a set of **target attributes** — the structural dimensions that define the evaluation space (e.g., `{domain: [politics, sports, tech], length: [short, long]}`).

- Runs only when `target_attributes: auto` or `target_attributes: complete` is set
- Static attribute dicts skip Phase 1 entirely (zero LLM calls)
- Multiple teachers vote; attributes are merged and deduplicated
- Output written to `{task_name}.attributes.json` per task

### Phase 2 — Rubric Mapping (`rubric_mapping`)

> **Code:** [`Code/runner/phases/phase2.py`](../../Code/runner/phases/phase2.py)

Teacher models generate the **evaluation rubric** — a set of named criteria against which judge models will score student responses.

- Runs only when `rubric: auto` or `rubric: extend` is set
- Static rubric dicts skip Phase 2 entirely (zero LLM calls)
- `rubric: extend` merges new dimensions onto a rubric inherited from a prior run
- Output written to `{task_name}.rubric.json` per task

### Phase 3 — Data Generation (`data_generation`)

> **Code:** [`Code/runner/phases/phase3.py`](../../Code/runner/phases/phase3.py)

Teacher models produce **(prompt, reference_response)** pairs — the benchmark items. Each item is drawn from a sampled combination of target and nuanced attributes.

- `benchmark` interface teachers are skipped (data pre-ingested via `coeval ingest`)
- Sampling respects `sampling.target` and `sampling.nuance` ranges
- Output written to `{task_name}__{teacher_name}.datapoints.jsonl`
- Retry logic handles transient API failures (`generation_retries`)

### Phase 4 — Response Collection (`response_collection`)

> **Code:** [`Code/runner/phases/phase4.py`](../../Code/runner/phases/phase4.py) · Interfaces: [`Code/runner/interfaces/pool.py`](../../Code/runner/interfaces/pool.py)

Student models receive Phase 3 prompts and generate responses. Every (task, teacher, student) triple produces a JSONL file of student outputs.

- Batch API (OpenAI, Anthropic, Gemini, Azure OpenAI) submits jobs and polls for completion
- Non-batch interfaces run concurrently up to the configured worker pool size
- HuggingFace models run sequentially (GPU-bound)
- Output written to `{task_name}__{teacher_name}__{student_name}.responses.jsonl`

### Phase 5 — Evaluation (`evaluation`)

> **Code:** [`Code/runner/phases/phase5.py`](../../Code/runner/phases/phase5.py) · Label eval: [`Code/runner/label_eval.py`](../../Code/runner/label_eval.py)

Judge models score each student response against the rubric using the (prompt, student_response, reference_response) triple.

- **`evaluation_mode: single`** — one call per response; judge returns all rubric dimension scores at once
- **`evaluation_mode: per_factor`** — one call per rubric dimension per response; maximum granularity, higher cost
- When `label_attributes` is set, `LabelEvaluator` performs exact-match scoring without a judge call
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

## Code Reference

Key source files by architectural area:

| Area | File |
|------|------|
| CLI entry point | [`Code/runner/cli.py`](../../Code/runner/cli.py) |
| Pipeline orchestration | [`Code/runner/runner.py`](../../Code/runner/runner.py) |
| Config loading + validation (V-01–V-17) | [`Code/runner/config.py`](../../Code/runner/config.py) |
| Storage / filesystem I/O (EES) | [`Code/runner/storage.py`](../../Code/runner/storage.py) |
| Phase 1 — attribute mapping | [`Code/runner/phases/phase1.py`](../../Code/runner/phases/phase1.py) |
| Phase 2 — rubric mapping | [`Code/runner/phases/phase2.py`](../../Code/runner/phases/phase2.py) |
| Phase 3 — data generation | [`Code/runner/phases/phase3.py`](../../Code/runner/phases/phase3.py) |
| Phase 4 — response collection | [`Code/runner/phases/phase4.py`](../../Code/runner/phases/phase4.py) |
| Phase 5 — evaluation | [`Code/runner/phases/phase5.py`](../../Code/runner/phases/phase5.py) |
| Label evaluation (exact-match) | [`Code/runner/label_eval.py`](../../Code/runner/label_eval.py) |
| Model interface factory | [`Code/runner/interfaces/pool.py`](../../Code/runner/interfaces/pool.py) |
| Credential resolution + key loading | [`Code/runner/interfaces/registry.py`](../../Code/runner/interfaces/registry.py) |
| Cost estimation | [`Code/runner/interfaces/cost_estimator.py`](../../Code/runner/interfaces/cost_estimator.py) |
| Pre-run model probe | [`Code/runner/interfaces/probe.py`](../../Code/runner/interfaces/probe.py) |
| `coeval ingest` benchmark adapters | [`Code/runner/benchmarks/registry.py`](../../Code/runner/benchmarks/registry.py) |
| CLI subcommand implementations | [`Code/runner/commands/`](../../Code/runner/commands/) |
| Analysis & reporting | [`Code/analyzer/`](../../Code/analyzer/) |
| Benchmark dataset loaders | [`Public/benchmark/loaders/`](../../Public/benchmark/loaders/) |
| Benchmark-native metric scoring | [`Public/benchmark/compute_scores.py`](../../Public/benchmark/compute_scores.py) |

---

## Frequently Asked Questions

**Q: What are the five phases of the CoEval pipeline?**
A: The five phases are: (1) Attribute Mapping — teachers infer task dimensions; (2) Rubric Mapping — teachers build evaluation criteria; (3) Data Generation — teachers produce (prompt, reference_response) pairs; (4) Response Collection — students answer Phase 3 prompts; (5) Evaluation — judges score student responses against the rubric. Each phase is independently checkpointed and resumable.

**Q: Can Phases 1 and 2 be skipped entirely?**
A: Yes. If you supply static `target_attributes` (a dict rather than `"auto"`) and a static `rubric` (a dict rather than `"auto"`), Phases 1 and 2 make zero LLM calls. Set both phases to `Keep` in the `experiment.phases` block and they are skipped on every run, saving time and API cost.

**Q: Can one model serve as teacher, student, and judge at the same time?**
A: Yes. Role assignment is fully flexible — any model can hold any combination of the three roles in a single experiment. A minimal single-model experiment has one model in all three roles. Use `role_parameters` to apply different temperature and token budgets per role without duplicating the model entry.

**Q: How does the pipeline handle the Batch API?**
A: For Phase 4 and Phase 5 with batch-enabled interfaces (OpenAI, Anthropic, Azure OpenAI), CoEval submits all requests as a single batch job at the start of the phase and polls the provider API at intervals until completion. Results are downloaded and processed identically to real-time responses — the rest of the pipeline is unaware of whether batch or real-time was used.

**Q: Where are all the phase output files stored?**
A: All artifacts are written under `{storage_folder}/{experiment_id}/`. Phase 1 outputs are `{task}.attributes.json`; Phase 2 is `{task}.rubric.json`; Phase 3 is `{task}__{teacher}.datapoints.jsonl`; Phase 4 is `{task}__{teacher}__{student}.responses.jsonl`; Phase 5 is `{task}__{teacher}__{judge}.evaluations.jsonl`. A `meta.json` file tracks phase completion state and a `run.log` contains structured logs.

**Q: How does `evaluation_mode: per_factor` differ from `single`?**
A: In `single` mode, the judge makes one API call per student response and returns scores for all rubric dimensions at once — lower cost, but dimensions are scored together. In `per_factor` mode, the judge makes one API call per rubric dimension per response — N times more calls, but each dimension is scored in isolation, enabling finer-grained analysis and reducing inter-dimension influence on scoring.

---

[← Recovery](09-recovery.md) · [Testing →](11-testing.md)
