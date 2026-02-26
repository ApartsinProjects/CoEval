# CoEval Extensive Benchmark

> **25 tasks · 5 domains · 5 SOTA models · auto-generated rubrics**

This folder contains a ready-to-run CoEval configuration that stress-tests a panel of
state-of-the-art open-weight HuggingFace models across five professional domains.
Every task uses `rubric: auto`, so Phase 2 generates evaluation criteria specific to each
task before any student responses are collected.

---

## Contents

```
benchmark/
├── benchmark_config.yaml   ← CoEval experiment configuration (this drives the run)
├── README.md               ← this file
└── runs/                   ← created automatically when the experiment runs
```

---

## Quick Start

### 1. Validate the config (no LLM calls)

```bash
coeval run --config benchmark/benchmark_config.yaml --dry-run
```

This prints the full execution plan and exits without touching any model.

### 2. Run the benchmark

```bash
coeval run --config benchmark/benchmark_config.yaml
```

Output is written to `benchmark/runs/benchmark-v1/`.

### 3. Generate reports

```bash
# Full Excel workbook
coeval analyze complete-report \
    --run benchmark/runs/benchmark-v1 \
    --out benchmark/runs/benchmark-v1-report.xlsx

# All HTML reports in one go
coeval analyze all \
    --run benchmark/runs/benchmark-v1 \
    --out benchmark/runs/reports/
```

### 4. Export robust benchmark dataset

```bash
coeval analyze export-benchmark \
    --run benchmark/runs/benchmark-v1 \
    --out benchmark/runs/benchmark-v1-robust.jsonl \
    --judge-selection top_half \
    --agreement-metric spa \
    --agreement-threshold 0.8
```

---

## Model Panel

Five open-weight HuggingFace models were selected based on **2025–2026 open-LLM
leaderboard standing**, availability without proprietary API keys, and coverage of
diverse parameter scales.

| # | Name in config | HuggingFace ID | Params | Roles |
|---|---------------|----------------|--------|-------|
| 1 | `qwen2-5-7b` | `Qwen/Qwen2.5-7B-Instruct` | 7 B | teacher · student · judge |
| 2 | `qwen2-5-14b` | `Qwen/Qwen2.5-14B-Instruct` | 14 B | teacher · student · judge |
| 3 | `mistral-nemo` | `mistralai/Mistral-Nemo-Instruct-2407` | 12 B | teacher · student · judge |
| 4 | `phi3-5-mini` | `microsoft/Phi-3.5-mini-instruct` | 3.8 B | student only |
| 5 | `llama3-2-3b` | `meta-llama/Llama-3.2-3B-Instruct` | 3 B | student only |

### Role assignment rationale

- **Teacher / student / judge (models 1–3):** 7–14 B parameter models that reliably
  produce structured JSON output required for Phase 1 (attribute mapping), Phase 2
  (rubric generation), and Phase 5 (score + rationale judgements).
- **Student-only (models 4–5):** Sub-4 B models assessed purely as students. At this
  scale, structured JSON output quality is inconsistent, making teacher and judge roles
  unreliable.

### Temperature settings

| Role | `qwen2-5-7b` | `qwen2-5-14b` | `mistral-nemo` |
|------|-------------|--------------|---------------|
| Teacher | 0.8 | 0.8 | 0.4 |
| Student | 0.7 | 0.7 | 0.3 |
| Judge | 0.1 | 0.1 | 0.1 |

Judge temperatures are set very low to maximise scoring consistency. Teacher temperatures
are slightly higher to encourage variety in generated prompts and rubric criteria.

---

## Domain Coverage

### Domain 1 — Education

Assesses how well models support teaching and learning workflows across different
educational levels, subject areas, and learner profiles.

| Task name | Description | Key attributes |
|-----------|-------------|----------------|
| `edu_concept_explanation` | Explain a concept at a target educational level | concept_complexity × audience_level |
| `edu_quiz_generation` | Generate assessment questions for a learning objective | cognitive_level × question_type × difficulty |
| `edu_essay_feedback` | Provide actionable feedback on a student essay draft | feedback_focus × grade_level |
| `edu_study_plan` | Create a structured study plan for exam preparation | timeframe × study_intensity × subject |
| `edu_learning_adaptation` | Rewrite instructional content for a specific learner profile | learner_profile × adaptation_type |

### Domain 2 — Healthcare

Assesses models on clinical communication, patient education, and decision-support
tasks. Critically, models must be clinically accurate while avoiding definitive diagnosis
language.

| Task name | Description | Key attributes |
|-----------|-------------|----------------|
| `hc_procedure_explanation` | Explain a medical procedure at a patient's health literacy level | procedure_complexity × health_literacy × patient_context |
| `hc_case_summary` | Summarise a clinical case for a specified clinical audience | case_complexity × clinical_audience × case_type |
| `hc_medication_guide` | Create a patient-friendly medication guide | medication_class × health_literacy × patient_risk |
| `hc_symptom_triage` | Describe a triage decision process for a symptom presentation | urgency_level × care_setting × patient_population |
| `hc_lab_results_interpretation` | Interpret lab results for a specified audience | result_pattern × audience × lab_panel |

### Domain 3 — Entertainment

Assesses creative writing capability across narrative, critical, and structured formats.
Rubrics generated here will capture genre-fidelity, voice, and structural quality.

| Task name | Description | Key attributes |
|-----------|-------------|----------------|
| `ent_story_generation` | Write a short story meeting genre and narrative constraints | genre × narrative_quality × tone |
| `ent_dialogue_writing` | Write a dramatic dialogue scene between two characters | relationship_type × emotional_stakes × scene_purpose |
| `ent_movie_synopsis` | Write a compelling movie synopsis for a given premise | genre × audience_rating × narrative_hook |
| `ent_review_writing` | Write an engaging review for a fictional media work | sentiment × media_type × publication_type |
| `ent_trivia_creation` | Generate a themed trivia question set | difficulty_mix × topic_breadth |

### Domain 4 — Manufacturing

Assesses technical documentation quality — SOPs, defect reports, inspection checklists,
maintenance schedules, and process flow documentation — for industrial operators and
engineering teams.

| Task name | Description | Key attributes |
|-----------|-------------|----------------|
| `mfg_sop_writing` | Write a Standard Operating Procedure for a manufacturing task | process_complexity × safety_level × operation_type |
| `mfg_defect_analysis` | Write a defect analysis report with root cause and CAPA | defect_type × root_cause_category × severity |
| `mfg_quality_checklist` | Create a quality inspection checklist for a production stage | inspection_type × compliance_standard × product_category |
| `mfg_maintenance_schedule` | Generate a preventive maintenance schedule for industrial equipment | equipment_type × maintenance_frequency × maintenance_scope |
| `mfg_process_documentation` | Document a manufacturing process flow for engineering teams | process_stage × documentation_purpose × detail_level |

### Domain 5 — Cybersecurity

Assesses models on security communication and documentation — explaining vulnerabilities,
writing incident response procedures, summarising advisories, creating awareness
training, and generating threat models. Tasks require domain accuracy without providing
exploitation guidance.

| Task name | Description | Key attributes |
|-----------|-------------|----------------|
| `sec_vulnerability_explanation` | Explain a vulnerability class to a specified audience | vulnerability_class × audience_level × impact_scope |
| `sec_incident_response` | Write an incident response procedure for a threat type | threat_type × org_size × response_phase |
| `sec_advisory_summary` | Summarise a security advisory for an organisational audience | severity × affected_system_type × advisory_audience |
| `sec_awareness_scenario` | Create a security awareness training scenario | threat_vector × target_employee_role × scenario_realism |
| `sec_threat_modeling` | Generate a threat model for a given system type | system_type × threat_actor_focus × detail_level |

---

## Rubric Generation

All 25 tasks use `rubric: auto`. This means:

1. **Phase 2 (Rubric Mapping):** each of the 3 teacher models independently generates a
   task-specific evaluation rubric based on the task description and output specification.
2. The rubrics are stored in the EES alongside generated prompts and responses.
3. **Phase 5 (Evaluation):** each judge scores student responses against the
   teacher-generated rubric for that (task, teacher) pair.

This design ensures rubrics reflect domain-specific quality criteria rather than a
one-size-fits-all scoring template, and that the rubric generation capability of each
teacher model is itself implicitly assessed.

---

## Sampling Configuration

Every task is configured identically:

```yaml
sampling:
  target: [1, 2]    # 1–2 target attribute values sampled per data point
  nuance: [1, 1]    # exactly 1 nuanced attribute value per data point
  total: 10         # 10 data points generated per task
```

This yields **25 tasks × 10 samples = 250 data points** in the EES.

---

## Estimated Inference Call Budget

The table below shows the approximate number of LLM forward passes by pipeline phase.
All models are local HuggingFace models — there is no monetary API cost, only compute
time.

| Phase | Description | Estimated calls |
|-------|-------------|-----------------|
| 1 — Attribute Mapping | 25 tasks × 3 teachers | ~75 |
| 2 — Rubric Mapping | 25 tasks × 3 teachers (`rubric: auto`) | ~75 |
| 3 — Data Generation | 250 samples × 3 teachers | ~750 |
| 4 — Response Collection | 250 prompts × 5 students | ~1,250 |
| 5 — Evaluation | 250 prompts × 3 teachers × 5 students × 3 judges | ~11,250 |
| **Total** | | **~13,400** |

> **Note:** Phase 5 dominates because every (teacher prompt, student response) pair is
> judged by every judge model. With 3 teacher models × 5 student models × 3 judges this
> creates a 45× multiplier on the base 250 data points.

Per-model quotas are configured to prevent runaway inference:

```yaml
quota:
  qwen2-5-14b: {max_calls: 2000}
  mistral-nemo: {max_calls: 2000}
  qwen2-5-7b:  {max_calls: 2000}
```

---

## Hardware Requirements

| Scenario | Minimum VRAM | Notes |
|----------|-------------|-------|
| All 5 models loaded simultaneously | ~60 GB | Not recommended |
| One model at a time (`device: auto`) | ~30 GB (14B @ fp16) | Default configuration |
| Small models only (phi3-5-mini, llama3-2-3b) | ~8 GB | Useful for quick iteration |

The config uses `device: auto` for all models, allowing HuggingFace `accelerate` to
distribute weights across available GPUs and CPU offload if needed. For multi-GPU
setups, `accelerate` will shard automatically.

---

## Resuming a Partial Run

If the run is interrupted, resume it without re-running completed phases:

```bash
coeval run --config benchmark/benchmark_config.yaml --resume benchmark-v1
```

Or selectively set specific phases to `Resume` in the YAML:

```yaml
experiment:
  phases:
    attribute_mapping:   Resume   # already done
    rubric_mapping:      Resume   # already done
    data_generation:     Resume   # in progress
    response_collection: New
    evaluation:          New
```

---

## Output Structure

After a successful run, `benchmark/runs/benchmark-v1/` will contain:

```
benchmark-v1/
├── metadata.json                   ← experiment metadata and config snapshot
├── phase1_attributes/              ← attribute mapping outputs per task
├── phase2_rubrics/                 ← auto-generated rubrics per task per teacher
├── phase3_prompts/                 ← generated prompts per task per teacher
├── phase4_responses/               ← student model responses
└── phase5_evaluations/             ← judge scores and rationales
```

---

## Analysis Workflow

```bash
BASE=benchmark/runs/benchmark-v1
OUT=benchmark/runs/reports

# Student performance overview
coeval analyze student-report    --run $BASE --out $OUT/student_report.html

# Judge reliability and agreement
coeval analyze judge-report      --run $BASE --out $OUT/judge_report.html

# Teacher differentiation quality
coeval analyze teacher-report    --run $BASE --out $OUT/teacher_report.html

# Score distributions by domain, model, attribute
coeval analyze score-distribution --run $BASE --out $OUT/score_dist.html

# Judge consistency within each judge model
coeval analyze judge-consistency  --run $BASE --out $OUT/judge_consistency.html

# Robust ranking (top-half judges, SPA metric)
coeval analyze robust-summary \
    --run $BASE --out $OUT/robust_summary.html \
    --judge-selection top_half \
    --agreement-metric spa

# Export filtered benchmark dataset
coeval analyze export-benchmark \
    --run $BASE --out benchmark/runs/benchmark-v1-robust.jsonl \
    --judge-selection top_half \
    --agreement-metric spa \
    --agreement-threshold 0.8

# Everything at once
coeval analyze all --run $BASE --out $OUT
```

---

## Design Notes

- **Cross-domain diversity:** The five domains span structured technical writing
  (manufacturing, cybersecurity), open-ended creative writing (entertainment),
  audience-adaptive communication (education, healthcare) — testing genuinely different
  capabilities.
- **Attribute orthogonality:** Within each task, `target_attributes` and
  `nuanced_attributes` are designed to be independently variable, so the EEA can
  slice performance along any single dimension.
- **Safety-aware tasks:** Healthcare and cybersecurity tasks include specific output
  constraints (no definitive diagnosis; no exploitation details). Auto-rubrics generated
  by the teacher models will naturally reflect these constraints, providing an implicit
  safety alignment test.
- **Model size diversity:** Including 3 B and 3.8 B student models alongside 7–14 B
  teacher/judge models makes the benchmark useful for studying capability gaps between
  model scales.
