# experiments/phases/ — Pipeline Phase Implementations

This directory contains the five core pipeline phases of CoEval, plus shared utilities. Each phase is orchestrated by [`experiments/runner.py`](../runner.py).

## Phase Modules

| File | Phase | Name | LLM Calls | Output directory |
|------|-------|------|-----------|-----------------|
| [`phase1.py`](phase1.py) | 1 | Attribute Mapping | `n_teachers × n_tasks` | `phase1_attributes/` |
| [`phase2.py`](phase2.py) | 2 | Rubric Construction | `n_teachers × n_tasks` | `phase2_rubric/` |
| [`phase3.py`](phase3.py) | 3 | Data Generation | `n_teachers × n_tasks × datapoints` | `phase3_datapoints/` |
| [`phase4.py`](phase4.py) | 4 | Response Collection | `n_students × total_datapoints` | `phase4_responses/` |
| [`phase5.py`](phase5.py) | 5 | Ensemble Scoring | `n_judges × n_students × total_datapoints` | `phase5_evaluations/` |
| [`utils.py`](utils.py) | — | Shared utilities | — | — |

## Phase Descriptions

### Phase 1: Attribute Mapping
Teacher models analyze each task description and propose:
- **Target attributes** — dimensions for stratified sampling (e.g., `complexity: [simple, moderate, complex]`)
- **Nuanced attributes** — secondary dimensions not used for stratification (e.g., `domain: [science, business]`)

Output: `{task_id}_target_attrs.json` and `{task_id}_nuanced_attrs.json` per teacher.

### Phase 2: Rubric Construction
Teacher models propose or refine a scoring rubric for each task. Each rubric is a dict of `{factor: description}` pairs used as evaluation criteria in Phase 5.

Output: `{task_id}.rubric.json`

### Phase 3: Data Generation
Teachers generate `(prompt, reference_response)` pairs sampled across the attribute space defined in Phase 1. Each datapoint is tagged with its sampled target and nuanced attribute values.

Output: `{task_id}.{teacher_id}.datapoints.jsonl`

### Phase 4: Response Collection
Student models receive teacher-generated prompts and produce responses. Supports both real-time and batch API modes.

Output: `{task_id}.{student_id}.responses.jsonl`

### Phase 5: Ensemble Scoring
Judge models score each student response against the Phase 2 rubric. Each evaluation record contains per-factor scores (`High` / `Medium` / `Low`). Multiple judges form the CoEval ensemble.

Output: `{task_id}.{teacher_id}.{judge_id}.evaluations.jsonl`

## Phase Modes

Each phase supports four execution modes (set in `experiment.phases` config key):

| Mode | Behaviour |
|------|-----------|
| `New` | Overwrite existing output and regenerate from scratch |
| `Keep` | Skip; use existing output as-is |
| `Extend` | Generate only missing items; skip existing JSONL records |
| `Model` | Skip if the output file for this model already exists |

## Related

- [`experiments/runner.py`](../runner.py) — orchestrates all 5 phases
- [`experiments/interfaces/`](../interfaces/) — LLM provider interfaces used by each phase
- [`analysis/loader.py`](../../analysis/loader.py) — loads EES artifacts after all phases complete
