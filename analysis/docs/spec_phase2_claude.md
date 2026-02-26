# CoEval: Analysis Module Specification (EEA)

**Document ID:** COEVAL-SPEC-002
**Version:** 0.1-draft
**Date:** 2026-02-23
**Status:** Draft
**Prerequisite:** COEVAL-SPEC-001 v0.1-draft (EER Specification)
**Sources:** CoEval Phase 2 spec

---

## Table of Contents

0. [Scope and Relationship to Phase 1](#0-scope-and-relationship-to-phase-1)
1. [Overview](#1-overview)
2. [Architecture](#2-architecture)
3. [Core Analytical Concepts](#3-core-analytical-concepts)
4. [EES Data Loading](#4-ees-data-loading)
5. [Computation Layer](#5-computation-layer)
   - 5.1 [Score Normalization](#51-score-normalization)
   - 5.2 [Validity Classification](#52-validity-classification)
   - 5.3 [Judge Agreement Metrics](#53-judge-agreement-metrics)
   - 5.4 [Judge Score](#54-judge-score)
   - 5.5 [Teacher Differentiation Score](#55-teacher-differentiation-score)
   - 5.6 [Student Score](#56-student-score)
   - 5.7 [Robust Filtering Algorithm](#57-robust-filtering-algorithm)
6. [Analyzer Configuration](#6-analyzer-configuration)
7. [Output Artifacts](#7-output-artifacts)
   - 7.1 [Complete Report (Excel)](#71-complete-report-excel)
   - 7.2 [HTML Dashboard Architecture (shared)](#72-html-dashboard-architecture-shared)
   - 7.3 [Score Distribution Report](#73-score-distribution-report)
   - 7.4 [Teacher Model Score Report](#74-teacher-model-score-report)
   - 7.5 [Judge Model Score Report](#75-judge-model-score-report)
   - 7.6 [Student Model Score Report](#76-student-model-score-report)
   - 7.7 [Teacher-Student Interaction Matrix](#77-teacher-student-interaction-matrix)
   - 7.8 [Judge Consistency View](#78-judge-consistency-view)
   - 7.9 [Coverage Summary](#79-coverage-summary)
   - 7.10 [Robust Student Summary Report](#710-robust-student-summary-report)
   - 7.11 [Robust Benchmark Export](#711-robust-benchmark-export)
8. [CLI Interface](#8-cli-interface)
9. [Examples](#9-examples)
10. [MVP Scope](#10-mvp-scope)

---

## 0. Scope and Relationship to Phase 1

**REQ-A-0.1** This document specifies the **Evaluation Experiment Analyzer (EEA)** — the second major component of the CoEval system. All EES file formats, naming conventions, artifact schemas, and terminology are defined in COEVAL-SPEC-001 (EER Specification) and are inherited without modification by this specification. Definitions from that document apply here unless explicitly overridden.

**REQ-A-0.2** EEA is a read-only consumer of EES. It does not write to, modify, or delete any artifact produced by EER. All EEA outputs are written to a user-specified output directory separate from the EES experiment folder.

**REQ-A-0.3** EEA operates on a single completed or in-progress EES experiment folder at a time. It does not compare or merge multiple experiments; cross-experiment comparison is out of scope for this version.

**REQ-A-0.4** EEA may operate on an experiment with `status: "in_progress"` (→ COEVAL-SPEC-001 §6.2.1) as long as Phase 5 data files exist. Reports generated from an in-progress experiment reflect only the artifacts present at analysis time and are marked as partial in their output.

> **Cross-reference key:** REQ-A-N.N refers to requirements in this document (COEVAL-SPEC-002). REQ-N.N without prefix refers to COEVAL-SPEC-001. "§N" without prefix refers to sections of this document; "SPEC-001 §N" refers to COEVAL-SPEC-001 sections.

---

## 1. Overview

**REQ-A-1.1** The EEA reads an EES experiment folder and produces the following outputs:

| Output | Format | Command |
|--------|--------|---------|
| Complete tabular report | Excel workbook (.xlsx) | `coeval analyze complete-report` |
| Score Distribution Report | Self-contained HTML folder | `coeval analyze score-distribution` |
| Teacher Model Score Report | Self-contained HTML folder | `coeval analyze teacher-report` |
| Judge Model Score Report | Self-contained HTML folder | `coeval analyze judge-report` |
| Student Model Score Report | Self-contained HTML folder | `coeval analyze student-report` |
| Teacher-Student Interaction Matrix | Self-contained HTML folder | `coeval analyze interaction-matrix` |
| Judge Consistency View | Self-contained HTML folder | `coeval analyze judge-consistency` |
| Coverage Summary | Self-contained HTML folder | `coeval analyze coverage-summary` |
| Robust Student Summary Report | Self-contained HTML folder | `coeval analyze robust-summary` |
| Robust Benchmark Export | JSONL or Parquet file | `coeval analyze export-benchmark` |
| All HTML reports (batch) | All of the above | `coeval analyze all` |

**REQ-A-1.2** All HTML reports are interactive, self-contained, and offline-loadable. Filtering and slicing are performed entirely within the browser using embedded data and interactive controls. No server-side processing is required after generation.

**REQ-A-1.3** All reports operate on the same pre-computed in-memory data model (→ §4), which is loaded once per `coeval analyze` invocation and shared across all reports generated in that invocation.

---

## 2. Architecture

**REQ-A-2.1** EEA consists of four internal layers:

```
┌──────────────────────────────────────────────────────────────────┐
│                     EEA — coeval analyze                         │
│                                                                  │
│  ┌───────────────┐   ┌─────────────────┐   ┌────────────────┐   │
│  │  Data Loader  │──▶│  Computation    │──▶│ Report         │   │
│  │  (§4)         │   │  Engine (§5)    │   │ Generators(§7) │   │
│  └───────────────┘   └─────────────────┘   └───────┬────────┘   │
│         ▲                                          │            │
│         │                                          ▼            │
│    EES folder                              Output directory      │
│    (read-only)                           (Excel / HTML / JSONL)  │
└──────────────────────────────────────────────────────────────────┘
```

**REQ-A-2.2** The **Data Loader** reads all EES artifacts from the experiment folder and constructs the unified in-memory data model (→ §4). It validates the presence of required files and reports missing or unreadable artifacts as warnings (not errors), allowing partial analysis when a run is incomplete.

**REQ-A-2.3** The **Computation Engine** applies all metric formulas defined in §5 to the loaded data model, producing derived metrics (judge scores, teacher scores, student scores, agreement matrices) that are stored alongside the raw data in memory.

**REQ-A-2.4** Each **Report Generator** consumes the computed data model and produces a self-contained output artifact. HTML generators embed all data as a JSON literal inside the output HTML file. A shared copy of Plotly.js is written to the output folder once and referenced by all HTML files in that folder.

**REQ-A-2.5** EEA is EES-compatible: it reads from the folder structure defined in COEVAL-SPEC-001 §6.1 and the artifact schemas defined in COEVAL-SPEC-001 §6.2 without requiring any EEA-specific schema extensions.

---

## 3. Core Analytical Concepts

This section defines terms used throughout §5 and §7.

**REQ-A-3.1 Evaluation Record** — A single row in a Phase 5 JSONL file (→ COEVAL-SPEC-001 §6.2.6). It represents one Judge's scoring of one Student's response to one datapoint, across all rubric aspects. Identified by: `(task_id, teacher_model_id, student_model_id, judge_model_id, datapoint_id)`.

**REQ-A-3.2 Valid Evaluation Record** — An evaluation record is **valid** if and only if all of the following conditions hold:

1. The Phase 5 JSONL line was parsed successfully (no JSON error).
2. All rubric factor keys present in the corresponding Phase 2 rubric file appear in the `scores` field with a non-null value of `"High"`, `"Medium"`, or `"Low"`.
3. The corresponding Phase 4 response record exists in the Phase 4 JSONL files (the `response_id` resolves to a record).
4. The corresponding Phase 3 datapoint exists in the Phase 3 JSONL files (the `datapoint_id` resolves to a record).

EEA determines validity exclusively from the content of JSONL artifact files. It does not read `run.log`. Failures in prior pipeline phases (Phase 3, 4, or 5) manifest in EES as *absent records*, not as explicit error markers — so conditions 3 and 4 above are the correct way to detect upstream failures. Any datapoint or response that EER failed to produce simply has no JSONL record; EEA treats the corresponding evaluation record as invalid under condition 3 or 4 respectively.

An invalid evaluation record is counted in coverage statistics but excluded from all metric computations. The reason for invalidity is preserved for display in the Coverage Summary (→ §7.9).

**REQ-A-3.3 Slice** — A subset of evaluation records defined by fixing one or more of: task, teacher, student, judge, rubric aspect, or target attribute value. All reports operate on slices; the full dataset is the slice with no fixed dimensions.

**REQ-A-3.4 Judge Pair** — An ordered or unordered pair of distinct Judge models `(Jₐ, J_b)` that both evaluated the same response. Agreement metrics are computed over the set of evaluation records where both judges in the pair produced a valid score for the same `(task_id, teacher_model_id, student_model_id, datapoint_id, rubric_aspect)` tuple.

**REQ-A-3.5 Common Evaluation Set** — For judge pair `(Jₐ, J_b)`, the **common evaluation set** E(Jₐ, J_b) is the set of `(response_id, rubric_aspect)` pairs for which both judges produced a valid score. Agreement metrics are computed over E(Jₐ, J_b). If `|E(Jₐ, J_b)| = 0`, the pair has undefined agreement and is excluded from aggregation.

**REQ-A-3.6 Agreement Coverage** — For judge pair `(Jₐ, J_b)`, the **agreement coverage** is `|E(Jₐ, J_b)| / |E_all|`, where `E_all` is the total number of `(response_id, rubric_aspect)` tuples that either judge scored. Reported alongside each agreement metric value.

**REQ-A-3.7 Top-Half Judge Selection** — The default judge selection mode for robust filtering. Judges are ranked by their Judge Score (→ §5.4) and the top `ceil(N/2)` judges (where N is the total number of judge models) are selected. With N=1, all judges are selected. With N=2, 1 judge is selected. This is denoted J*.

**REQ-A-3.8 Robust Datapoint** — A datapoint is **robust** with respect to a selected judge set J* and agreement threshold θ if: for every `(student_model_id, rubric_aspect)` pair evaluated on that datapoint, all judges in J* that produced a valid score for that pair gave the same score. When θ < 1.0, a datapoint is robust if the fraction of judge-consistent `(student, aspect)` pairs is ≥ θ. The default θ = 1.0 requires full agreement on all (student, aspect) pairs.

**REQ-A-3.9 Self-Judging** — An evaluation record where `judge_model_id == student_model_id`. That is, the same model whose response is being scored also acted as the judge scoring it. Self-judging introduces a known upward bias (→ COEVAL-SPEC-001 REQ-12.7). Self-judging records are **included** in all metric computations but are **flagged** with a ⚠ indicator everywhere they appear in reports (table rows, chart tooltip, heatmap cell tooltip). The flag text is: *"Self-evaluation: judge model = student model."* The count of self-judging records is shown in the report metadata header.

**REQ-A-3.10 Self-Teaching** — A response record where `teacher_model_id == student_model_id`. That is, the same model that generated the benchmark datapoint also generated the response being evaluated on it. Self-teaching may inflate or deflate scores depending on whether the model's generation style favours its own benchmark items. Self-teaching records are **included** in all metric computations but are **flagged** with a ⚠ indicator everywhere they appear in reports (table rows, chart tooltip, heatmap cell tooltip). The flag text is: *"Self-teaching: teacher model = student model."* When a record is both self-teaching and self-judging, both flags are shown. The count of self-teaching records is shown in the report metadata header.

**REQ-A-3.11 Degenerate Metric — Single-Judge Agreement** — When an experiment contains only one judge model (N=1), no pairwise agreement can be computed. In this case:
- All pairwise agreement metrics (SPA, WPA, κ) are reported as **1.0** (a judge is trivially in perfect agreement with itself).
- JudgeScore for the single judge is reported as **1.0 (degenerate)**.
- A prominent notice is shown in all judge-related views: *"⚠ Only 1 judge model in this experiment. Agreement metrics are trivially 1.0 and carry no information. Add ≥2 judge models to obtain meaningful agreement estimates."*
- The robust filtering algorithm proceeds normally (J* = the single judge; D_robust trivially includes all datapoints where that judge produced a valid score).

**REQ-A-3.12 Degenerate Metric — Single-Student Differentiation** — When an experiment contains only one student model (N=1), teacher differentiation scores are computed as specified in §5.5 (yielding 0.0 for all three formulas, since variance/spread/range over a single value is 0). The computed 0.0 values are shown in all teacher-related views with the following notice: *"⚠ Only 1 student model in this experiment. Teacher differentiation scores are trivially 0.0 and carry no information. Add ≥2 student models to obtain meaningful differentiation estimates."*

---

## 4. EES Data Loading

**REQ-A-4.1** EEA reads the following files from the experiment folder at startup. Files that are absent are noted as warnings; phases that depend on them are marked as unavailable in the analysis.

| File(s) | Phase | Required for |
|---------|-------|-------------|
| `meta.json` | — | Experiment metadata, status, and phase completion state |
| `config.yaml` | — | Model and task definitions (names, roles, rubric mode) |
| `phase2_rubric/{task}.rubric.json` | 2 | Rubric factor names and descriptions |
| `phase3_datapoints/{task}.{teacher}.datapoints.jsonl` | 3 | Datapoint prompts, reference responses, target attribute tags |
| `phase4_responses/{task}.{teacher}.{student}.responses.jsonl` | 4 | Student model outputs |
| `phase5_evaluations/{task}.{teacher}.{judge}.evaluations.jsonl` | 5 | Judge scores — primary input for all metric computations |

**REQ-A-4.2** EEA constructs a unified in-memory data model by joining all loaded records on their shared keys. The join order is:

1. Load `config.yaml` → extract model list (with roles) and task list (with rubric definitions).
2. Load `phase2_rubric/` → build rubric map `{task_id → {factor_name → description}}`.
3. Load `phase3_datapoints/` → build datapoint index `{datapoint_id → datapoint_record}`.
4. Load `phase4_responses/` → build response index `{response_id → response_record}`; cross-reference `datapoint_id`.
5. Load `phase5_evaluations/` → build evaluation list; cross-reference `response_id` and `datapoint_id`; classify each record as valid or invalid (→ §5.2).
6. **Denormalize evaluation records into per-aspect analytical units.** Each Phase 5 record stores all rubric factor scores in a single `scores` map (→ COEVAL-SPEC-001 §6.2.6). All agreement and filtering computations in §3 and §5 operate on `(response_id, rubric_aspect)` tuples — one tuple per factor per evaluation record. EEA expands each valid evaluation record into N tuples (where N = number of rubric factors for that task), each carrying: `response_id`, `datapoint_id`, `task_id`, `teacher_model_id`, `student_model_id`, `judge_model_id`, `rubric_aspect`, `score` (ordinal string), `score_norm` (numeric, → §5.1). These tuples form the primary analytical unit for all subsequent computations. The original evaluation record is retained for provenance but computations reference the expanded tuples.

**REQ-A-4.3** All JSONL files are read line by line. Lines that cannot be parsed as valid JSON are logged as warnings with their file path and line number; the corresponding records are treated as invalid.

**REQ-A-4.4** EEA infers the complete experiment dimensions by taking the union across all phases:

| Dimension | Primary source | Supplementary sources | Note |
|-----------|---------------|----------------------|------|
| Tasks | Phase 3, 4, 5 files (`task_id` field) | `config.yaml` task names | Union across all phases. A task present in Phase 3 but absent from Phase 5 is included but marked `no_evaluations`. |
| Teachers | Phase 3 files (`teacher_model_id`) | Phase 4, 5 files | Union. A teacher missing from Phase 3 but present in Phase 5 (e.g., after manual EES manipulation) is included as `teacher_inferred`. |
| Students | Phase 4 files (`student_model_id`) | Phase 5 files | Union. |
| Judges | Phase 5 files (`judge_model_id`) | `config.yaml` model roles | Union. |
| Rubric aspects | Phase 2 rubric JSON (authoritative) | Phase 5 `scores` map keys | Phase 2 is authoritative; Phase 5 keys supplement if Phase 2 is missing. |
| Target attribute keys/values | Phase 3 `sampled_target_attributes` | — | Only from Phase 3; not inferred from Phase 5. |

EEA emits a `WARNING` log entry for each dimension value that could not be found in its primary source and had to be inferred from a supplementary source. This ensures that a teacher whose Phase 5 evaluations are complete but whose Phase 3 datapoints are missing (e.g., deleted) is still visible in the analysis, with its data gaps clearly flagged.

**REQ-A-4.5** EEA does not re-validate the config against the EES contents. If a model ID appears in EES but not in `config.yaml` (e.g., from a resume), it is included in the analysis with its ID as its display name.

---

## 5. Computation Layer

### 5.1 Score Normalization

**REQ-A-5.1.1** Rubric scores stored as ordinal strings in Phase 5 files (→ COEVAL-SPEC-001 §6.2.6) are converted to a numeric scale for all averaging and variance computations:

| Ordinal Score | Numeric Value |
|---------------|---------------|
| `"High"`      | 1.0           |
| `"Medium"`    | 0.5           |
| `"Low"`       | 0.0           |

This conversion is applied uniformly for all metrics in §5.3–§5.7 and all report computations in §7.

**REQ-A-5.1.2** Normalized scores are in the range [0.0, 1.0]. All displayed averages and variance values are reported using this scale. Percentage representations (e.g., "average score: 75%") may be shown in reports by multiplying by 100.

**REQ-A-5.1.3** Ordinal labels (`"High"`, `"Medium"`, `"Low"`) are always displayed alongside or instead of numeric values in tables and charts where individual scores are shown (as opposed to aggregates). Never display only the numeric value when showing a single score.

---

### 5.2 Validity Classification

**REQ-A-5.2.1** During data loading (→ §4), each evaluation record is classified as valid or invalid per REQ-A-3.2. The following error codes are assigned for display in the Coverage Summary (→ §7.9):

| Error Code | Condition | Validity condition violated |
|------------|-----------|----------------------------|
| `PARSE_ERROR_P3` | Phase 3 JSONL line could not be parsed as JSON | Condition 4 (datapoint unreachable) |
| `PARSE_ERROR_P4` | Phase 4 JSONL line could not be parsed as JSON | Condition 3 (response unreachable) |
| `PARSE_ERROR_P5` | Phase 5 JSONL line could not be parsed as JSON | Condition 1 |
| `MISSING_DATAPOINT` | `datapoint_id` in a Phase 4 or Phase 5 record is not present in the Phase 3 index; indicates EER failed to generate or write that datapoint | Condition 4 |
| `MISSING_RESPONSE` | `response_id` in a Phase 5 record is not present in the Phase 4 index; indicates EER failed to collect or write that response | Condition 3 |
| `INCOMPLETE_SCORES` | Phase 5 `scores` map is missing one or more factor keys from the Phase 2 rubric | Condition 2 |
| `INVALID_SCORE_VALUE` | A value in the `scores` map is not `"High"`, `"Medium"`, or `"Low"` | Condition 2 |

**REQ-A-5.2.2** A record may carry multiple error codes if multiple conditions apply. All error codes are stored and displayed.

**REQ-A-5.2.3** Invalid records are excluded from all metric computations (§5.3–§5.7) but are counted in coverage totals and displayed in the Coverage Summary (→ §7.9).

---

### 5.3 Judge Agreement Metrics

EEA computes three agreement metrics for every judge pair. All three are always computed and stored. The user selects which metric to display and use for judge ranking in the interactive HTML reports (→ §7.5) and which to use for robust filtering (→ §5.7, §6.3).

**REQ-A-5.3.1 Simple Percent Agreement (SPA)**

For judge pair `(Jₐ, J_b)` and common evaluation set E(Jₐ, J_b) (→ REQ-A-3.5):

```
SPA(Jₐ, J_b) = |{ (r, a) ∈ E(Jₐ, J_b) : score(Jₐ, r, a) = score(J_b, r, a) }|
                ─────────────────────────────────────────────────────────────────
                                    |E(Jₐ, J_b)|
```

where `r` is a response ID and `a` is a rubric aspect. Range: [0.0, 1.0]. Undefined (reported as `null`) when `|E| = 0`.

**REQ-A-5.3.2 Weighted Percent Agreement (WPA)**

Uses an ordinal weight matrix that gives partial credit to adjacent disagreements:

| Jₐ \ J_b | High | Medium | Low |
|-----------|------|--------|-----|
| **High**  | 1.0  | 0.5    | 0.0 |
| **Medium**| 0.5  | 1.0    | 0.5 |
| **Low**   | 0.0  | 0.5    | 1.0 |

```
WPA(Jₐ, J_b) = (1 / |E(Jₐ, J_b)|) × Σ_{(r,a) ∈ E} W(score(Jₐ, r, a), score(J_b, r, a))
```

Range: [0.0, 1.0]. Undefined when `|E| = 0`.

**REQ-A-5.3.3 Cohen's Kappa (κ)**

Corrects observed agreement for the probability of chance agreement given each judge's marginal score distribution:

```
P_o  = SPA(Jₐ, J_b)

P_e  = Σ_{c ∈ {High, Medium, Low}} P(Jₐ = c) × P(J_b = c)

     where P(Ji = c) = (# items in E where Ji scored c) / |E|

κ(Jₐ, J_b) = (P_o - P_e) / (1 - P_e)
```

Range: (−∞, 1.0]. κ = 1.0 is perfect agreement; κ = 0.0 is agreement at chance level; κ < 0 is worse than chance. Undefined when `P_e = 1.0` (all items in the same category by both judges) or `|E| = 0`.

Interpretation guidance to display in UI:

| κ value   | Conventional label |
|-----------|--------------------|
| < 0.0     | Less than chance   |
| 0.0–0.20  | Slight             |
| 0.21–0.40 | Fair               |
| 0.41–0.60 | Moderate           |
| 0.61–0.80 | Substantial        |
| 0.81–1.00 | Almost perfect     |

**REQ-A-5.3.4** All three metrics are computed for each ordered pair `(Jₐ, J_b)` where `Jₐ ≠ J_b`, over the common evaluation set restricted to the current active slice (task, teacher, student, aspect filters applied). The metrics are symmetric by definition for SPA and WPA; κ may differ by direction if marginal distributions differ, but is treated as symmetric (average of both directions) for ranking purposes.

---

### 5.4 Judge Score

**REQ-A-5.4.1** The **Judge Score** for judge Jₐ quantifies how reliably it agrees with other judges. It is computed as the **mean pairwise agreement** between Jₐ and all other judges J_b (b ≠ a), using the user-selected agreement metric M ∈ {SPA, WPA, κ}:

```
JudgeScore_M(Jₐ) = mean_{b ≠ a, |E(Jₐ, J_b)| > 0} [ M(Jₐ, J_b) ]
```

If there is only one judge model in the experiment, JudgeScore is reported as **1.0 (degenerate)** per REQ-A-3.11. The degenerate notice from REQ-A-3.11 is shown in all judge-related views.

**REQ-A-5.4.2** Agreement coverage (REQ-A-3.6) is reported for each (Jₐ, J_b) pair alongside the agreement value. The Judge Score is also accompanied by a weighted variant:

```
JudgeScore_M_weighted(Jₐ) = Σ_{b ≠ a} [ M(Jₐ, J_b) × |E(Jₐ, J_b)| ] / Σ_{b ≠ a} |E(Jₐ, J_b)|
```

The weighted variant is displayed in addition to the simple mean. Users can toggle between them in the interactive reports.

**REQ-A-5.4.3** Judge scores are recomputed when the user changes the active agreement metric selector in the UI. All ranking tables and filtering algorithms update accordingly without re-loading data.

---

### 5.5 Teacher Differentiation Score

The Teacher Differentiation Score quantifies how well a teacher's benchmark items separate student models. A high score means that different student models perform noticeably differently on the teacher's items — a sign of a discriminative benchmark. The user selects which of three formulas to apply.

**Notation:**

Let D(T, K) = set of valid datapoints generated by teacher T for task K.
Let S = set of all student models.
For teacher T, task K, rubric aspect A, and student s:

```
μ(s, T, K, A) = mean over d ∈ D(T,K) of score_norm( mean over j ∈ J of eval(d, s, j, A) )
```

where `J` is the set of all judges that produced a valid score for `(d, s, A)`, and the inner mean averages over judges before the outer mean averages over datapoints. If no valid scores exist for a (s, T, K, A) combination, that student is excluded from the computation for that slice.

**REQ-A-5.5.1 Formula 1 — Variance of Per-Student Averages:**

```
σ²(T, K, A) = sample_variance({ μ(s, T, K, A) : s ∈ S })
                                                           [at least 2 students required]

TeacherScore_V(T) = mean over (K, A) of σ²(T, K, A)     [weighted by number of valid evals]
```

High σ² means student performances diverge strongly — the teacher generates items that discriminate well.

**REQ-A-5.5.2 Formula 2 — Average Per-Datapoint Student Spread:**

```
spread(d, A) = std_dev({ score_norm( mean_j eval(d, s, j, A) ) : s ∈ S })

TeacherScore_S(T) = mean over K, d ∈ D(T,K), A of spread(d, A)
                    [averaged across all tasks K, all datapoints in each task, and all aspects]
```

This measures item-level discrimination: how much do students differ on any single item? A teacher that generates items where all students agree gets a low score.

**REQ-A-5.5.3 Formula 3 — Range of Per-Student Averages:**

```
range(T, K, A) = max_s μ(s, T, K, A) − min_s μ(s, T, K, A)

TeacherScore_R(T) = mean over (K, A) of range(T, K, A)
```

Range is more interpretable than variance but sensitive to outlier students (one very strong or very weak model).

**REQ-A-5.5.4** All three formulas are computed and stored for every teacher. The user selects which to display via a dropdown in the Teacher Model Score Report (→ §7.4). Rankings update immediately when the selection changes. The active formula is labelled clearly on every chart and table.

**REQ-A-5.5.5** When fewer than 2 student models exist, all three teacher differentiation scores are computed as specified and yield **0.0** (since variance/spread/range over a single value is zero). The computed 0.0 values are displayed in all teacher-related views with the degenerate notice per REQ-A-3.12. No ranking chart is suppressed — the 0.0 values are shown with the notice banner overlaid.

**REQ-A-5.5.6 — Methodological note: judge averaging before student variance.** The formula for μ(s, T, K, A) averages over all judges *before* computing the variance across students. This means that if two judges systematically disagree on student ranking (e.g., Judge A scores Student1 > Student2 while Judge B scores Student2 > Student1), their averaged μ values will both converge toward the mid-point, producing near-zero variance and falsely suggesting the teacher's items are non-discriminative. In practice this pathology is rare — systematic judge rank-reversal would indicate deep judge unreliability, which would already be captured by low judge agreement scores. Users who suspect this situation should inspect the Teacher-Student Interaction Matrix (→ §7.7) and Judge Score Report (→ §7.5) to verify that their judges are broadly consistent before interpreting teacher scores. The per-judge teacher score breakdown available in View 4 of the Teacher Model Score Report (→ §7.4) provides additional diagnostic information by showing score distributions per (teacher, judge) combination.

---

### 5.6 Student Score

**REQ-A-5.6.1** The **Student Score** for student s is the mean normalized score across all valid evaluation records for that student:

```
StudentScore(s) = mean over (T, K, A, d, j) of score_norm(eval(d, s, j, A))
                  [restricted to valid records; judges can be filtered]
```

**REQ-A-5.6.2** Student scores are computed and displayed at multiple granularities:

- **Overall**: single score across all tasks, aspects, teachers, and judges.
- **Per-task**: one score per task, averaged across teachers, aspects, and judges.
- **Per-aspect**: one score per rubric aspect, across all tasks and judges.
- **Per-judge**: one score per judge model, to surface judge-dependent inflations or deflations.
- **Per-teacher**: one score per teacher model, to surface teacher-dependent biases.
- **Per-target-attribute-value**: one score per attribute value (e.g., `test_type=blood test`), restricted to datapoints that were tagged with that attribute.

---

### 5.7 Robust Filtering Algorithm

**REQ-A-5.7.1** The robust filtering algorithm selects a subset of high-confidence datapoints for the Robust Student Summary (→ §7.10). It is parameterized by:

| Parameter | Default | Description |
|-----------|---------|-------------|
| `judge_selection` | `top_half` | How to select the reliable judge set J* |
| `agreement_metric` | User's selected metric (§5.3) | Which metric drives judge ranking |
| `agreement_threshold` θ | `1.0` | Minimum fraction of judge-consistent (student, aspect) pairs for a datapoint to be robust |

**REQ-A-5.7.2** The algorithm proceeds in three steps:

**Step 1 — Select high-quality judges (J*).**

Compute `JudgeScore_M_weighted(Jₐ)` (the **coverage-weighted** variant, → §5.4.2) for all judges using the agreement metric M specified by `--agreement-metric`. The coverage-weighted variant is used here (rather than the simple mean) because it gives more statistical weight to judge pairs with larger common evaluation sets, making the ranking more reliable when judge pairs have uneven coverage.

Rank judges by `JudgeScore_M_weighted` descending.
Select the top `ceil(N/2)` judges, where N is the total number of distinct judge models that produced any valid evaluation in this experiment. This forms the set J*.
If N = 1, J* = {that judge} (no filtering possible; report includes a notice: "Only one judge model exists. J* = all judges; judge quality filtering has no effect.").

**Step 2 — Select best teachers (using J* only).**

Recompute `TeacherScore(T)` restricted to evaluations from judges in J* only (→ §5.5), using the formula specified by `--teacher-score-formula` (default: `v1` — variance of per-student averages, → §5.5.1). This formula is fixed at report generation time and is embedded in the report alongside the other filtering parameters for full traceability.

Rank teachers by score descending.
The top `ceil(M/2)` teachers are selected, where M is the total number of teacher models. This forms the set T*.
If M = 1, T* = {that teacher} (no filtering; report includes a notice).

**Step 3 — Filter to robust datapoints.**

For each datapoint d generated by any teacher in T*:

1. Collect all `(student_model_id, rubric_aspect)` pairs for which at least one judge in J* produced a valid score.
2. For each such `(s, A)` pair:
   - J*_d_s_A = { j ∈ J* : eval(d, s, j, A) is valid }
   - Let q = `ceil(|J*| / 2)` — the minimum number of J* judges required for a consistency verdict (majority of J*).
   - The pair is **judge-consistent** if `|J*_d_s_A| ≥ q` AND all scores in { eval(d, s, j, A) : j ∈ J*_d_s_A } are equal.
   - If `|J*_d_s_A| < q` (too few J* judges scored this pair to form a majority), the pair is **insufficiently covered** and treated as not-consistent.
   - Rationale: requiring a majority prevents a single judge from establishing "consensus." With |J*| = 1, q = 1 (unavoidable single-judge case, already flagged by the N=1 notice above). With |J*| = 2, q = 1 reduces to requiring both judges; with |J*| = 3, q = 2 requires at least two of three to agree.
3. Let `consistent_fraction(d)` = (# judge-consistent pairs) / (# total pairs in step 1).
4. Datapoint d is **robust** if `consistent_fraction(d) ≥ θ`.

**REQ-A-5.7.2a Empty D_robust handling.** If Step 3 produces zero robust datapoints (`|D_robust| = 0`), EEA exits with code 1 (for `robust-summary` and `export-benchmark` commands) and prints a structured diagnostic to stderr showing exactly where coverage was lost:

```
ERROR: Robust filter produced 0 datapoints. No report generated.

Filtering diagnostics:
  Step 1 — Judge selection (J*):
    Judges ranked:         [judge-a: 0.91, judge-b: 0.74, judge-c: 0.43]
    J* selected (top 2):  [judge-a, judge-b]
    Agreement metric:      kappa

  Step 2 — Teacher selection (T*):
    Teachers ranked:       [teacher-x: 0.18, teacher-y: 0.04]
    T* selected (top 1):  [teacher-x]
    Formula:               v1 (variance)
    Datapoints remaining:  45 / 90  (from T* only)

  Step 3 — Datapoint consistency filter:
    Agreement threshold θ: 1.0
    Minimum judges/pair q: 1  (ceil(2/2))
    Datapoints passing:    0 / 45

  Suggested actions:
    • Lower --agreement-threshold (current: 1.0, try: 0.8)
    • Use --judge-selection all to include all judges in J*
    • Use --teacher-score-formula s2 or r3 for a different teacher ranking
    • Check coverage-summary report for invalid evaluation records
```

**REQ-A-5.7.3** Coverage statistics are computed and displayed before and after filtering:

- Total datapoints available: |D_all|
- Datapoints from T*: |D_T*|
- Robust datapoints: |D_robust|
- Coverage drop: `|D_robust| / |D_all|` (percentage of all datapoints retained)
- Per-teacher coverage drop: shown in a breakdown table
- Per-task coverage drop: shown in a breakdown table

**REQ-A-5.7.4** The robust student score is computed as:

```
RobustStudentScore(s) = mean over (d ∈ D_robust, A) of
                          score_norm( mean_{j ∈ J*} eval(d, s, j, A) )
```

Only valid evaluations from judges in J* are used. Datapoints not in D_robust are excluded entirely.

---

## 6. Analyzer Configuration

**REQ-A-6.1** EEA is configured entirely through CLI flags (→ §8). No separate YAML configuration file is required. All interactive filtering and metric-selection parameters are handled in the browser-side UI of the HTML reports.

**REQ-A-6.2** The only pre-computation parameters that must be specified before report generation are the robust filtering settings, because they affect which data is embedded in the Robust Student Summary Report. All other filtering is done interactively inside the browser.

| CLI Flag | Default | Description |
|----------|---------|-------------|
| `--run <path>` | (required) | Path to the EES experiment folder |
| `--out <path>` | (required) | Output path (folder for HTML/`all`; file for Excel/JSONL/Parquet) |
| `--judge-selection <mode>` | `top_half` | `top_half` \| `all` — how to form J* |
| `--agreement-metric <metric>` | `spa` | `spa` \| `wpa` \| `kappa` — metric used for judge ranking (coverage-weighted, → §5.7 Step 1) and robust filtering |
| `--agreement-threshold <float>` | `1.0` | θ ∈ (0.0, 1.0] — minimum judge-consistency fraction for a datapoint to be robust |
| `--teacher-score-formula <formula>` | `v1` | `v1` (variance of per-student averages) \| `s2` (average per-datapoint spread) \| `r3` (range of per-student averages) — formula used to rank teachers in Step 2 of robust filtering (→ §5.5, §5.7 Step 2) |
| `--benchmark-format <fmt>` | `jsonl` | `jsonl` \| `parquet` — output format for export-benchmark |
| `--partial-ok` | false | If set, allow analysis on in-progress experiments without a warning prompt |

**REQ-A-6.3** The `--agreement-metric` flag sets the default metric displayed in the Judge Score Report and used for judge ranking in robust filtering. The user can change the displayed metric interactively in the report UI; however, this does not retroactively change the robust-filtering computation, which uses the metric specified at generation time. The report clearly labels which metric was used for filtering.

---

## 7. Output Artifacts

### 7.1 Complete Report (Excel)

**REQ-A-7.1.1** `coeval analyze complete-report` produces a single Excel workbook (`.xlsx`) with at least three sheets:

**Sheet 1 — Raw Slice Summary**

One row per `(task_id, teacher_model_id, student_model_id, judge_model_id, rubric_aspect)` combination for which at least one valid evaluation record exists.

| Column | Type | Description |
|--------|------|-------------|
| Task ID | string | Task identifier (→ COEVAL-SPEC-001 §5.3) |
| Teacher Model ID | string | Teacher model identifier |
| Student Model ID | string | Student model identifier |
| Judge Model ID | string | Judge model identifier |
| Rubric Aspect | string | Rubric factor name |
| Total Data Points | int | All records in this slice (valid + invalid) |
| Valid Data Points | int | Records with no errors |
| Invalid Data Points | int | Records with any error |
| Average Score | float | Mean normalized score over valid records (0.0–1.0) |
| Score Std Dev | float | Standard deviation of normalized scores |
| High Count | int | Count of "High" scores |
| Medium Count | int | Count of "Medium" scores |
| Low Count | int | Count of "Low" scores |

**Sheet 2 — Aggregated by (Task, Teacher, Student, Judge)**

One row per `(task_id, teacher_model_id, student_model_id, judge_model_id)`, with scores averaged across all rubric aspects.

Columns: same as Sheet 1, omitting Rubric Aspect; "Average Score" is the mean across all aspects.

**Sheet 3 — Model Summary**

One row per model (any role), with overall statistics:

| Column | Description |
|--------|-------------|
| Model ID | Model identifier |
| Roles | Comma-separated list of roles this model played |
| As Student — Average Score | Mean score across all tasks, teachers, judges, aspects |
| As Student — Valid Evals | Count of valid evaluation records |
| As Teacher — Score (Formula 1) | Variance-based teacher differentiation score |
| As Teacher — Score (Formula 2) | Spread-based teacher differentiation score |
| As Teacher — Score (Formula 3) | Range-based teacher differentiation score |
| As Judge — SPA | Mean pairwise Simple Percent Agreement |
| As Judge — WPA | Mean pairwise Weighted Percent Agreement |
| As Judge — Kappa | Mean pairwise Cohen's Kappa |

**REQ-A-7.1.2** The workbook uses the following formatting:
- Frozen header row on each sheet.
- Alternating row shading (light grey / white).
- Numeric columns aligned right, formatted to 3 decimal places.
- Integer columns aligned right, no decimal places.
- Column widths auto-fitted to content.
- Average Score column uses a conditional colour scale: red (0.0) → yellow (0.5) → green (1.0).

---

### 7.2 HTML Dashboard Architecture (shared)

All HTML reports share the following architecture requirements.

**REQ-A-7.2.1 Tech stack:** Pure HTML5 + CSS3 + Plotly.js. No server-side rendering. No build step required at report-generation time.

**REQ-A-7.2.2 Self-contained output folder:** Each HTML report command produces a folder containing:
- `index.html` — main dashboard entry point.
- `plotly.min.js` — bundled Plotly.js library (latest stable version at implementation time), served locally. No CDN dependency at render time.
- `data.js` — all embedded data as a JavaScript `const DATA = { ... };` declaration, loaded by `index.html`.

**REQ-A-7.2.3 Data embedding:** All data required by the report is embedded in `data.js` as a single JSON-like JavaScript object. This object contains: raw slice records (pre-aggregated at the level of the report), pre-computed metric values (judge scores, teacher scores, student scores, agreement matrices), and experiment metadata (experiment ID, model list, task list, rubric definitions).

**REQ-A-7.2.4 Common layout:** Every HTML dashboard has:
- A **header bar** showing: experiment ID, EES path, number of tasks, models, and datapoints, report type, and the date of analysis.
- A **filter panel** (left sidebar or collapsible top bar) with interactive controls for all applicable filter dimensions.
- A **metric selector** (dropdown or radio group) where multiple metric formulas apply.
- A **main content area** with charts and tables.
- A **stats bar** showing: total records in current view, valid records, filter summary.

**REQ-A-7.2.5 Interactive filtering:** All filter controls operate client-side on the embedded data without reloading the page. Supported filter types:
- Multi-select dropdown (e.g., select one or more tasks, models, judges, aspects).
- Target attribute filter: for each target attribute key (e.g., `test_type`), a multi-select dropdown of allowed values.
- Minimum valid data point count slider (hide slices below threshold).

**REQ-A-7.2.6 Metric selector:** Where multiple formulas exist (agreement metric, teacher score formula), a clearly labelled dropdown or radio group allows the user to switch between them. Charts and ranking tables update immediately on selection change.

**REQ-A-7.2.7 Tooltip behavior:** All Plotly charts are configured with informative hover tooltips showing: the exact value, the sample size (valid data points), and the entity name (model ID, task, aspect, attribute value).

**REQ-A-7.2.8 Null / undefined handling:** When a metric is undefined (e.g., only one judge model exists), the report displays a labelled placeholder ("N/A — at least 2 judge models required") instead of an empty or broken chart.

**REQ-A-7.2.9 Colour scheme:**
- Student scores use a green gradient (higher = greener).
- Teacher differentiation scores use a blue gradient.
- Judge agreement scores use a purple gradient.
- Agreement heat maps use a diverging scale: red (low agreement) → white (0.5) → green (high agreement).
- Invalid/coverage gaps use light orange / grey.

---

### 7.3 Score Distribution Report

**Goal:** Show how High/Medium/Low scores are distributed across the experiment, broken down by rubric aspect, model, and attribute. Reveals rubric aspects that are too easy (all High) or too hard (all Low), and surfaces systematic model differences.

**REQ-A-7.3.1** The Score Distribution Report (`coeval analyze score-distribution`) produces an HTML folder (→ §7.2) with the following views:

**View 1 — Overall score distribution (stacked bar chart)**

- X-axis: rubric aspects (one bar per aspect).
- Bar segments: High (green) / Medium (yellow) / Low (red) — stacked to 100%.
- Each bar shows the count and percentage of each ordinal level.
- Filter: task, judge, teacher, student, target attribute value.

**View 2 — Score distribution by student model (grouped bar chart)**

- X-axis: rubric aspects.
- Bar groups: one group per rubric aspect, one bar per student model within each group.
- Bar height: fraction of "High" scores (or user-selected level).
- Level selector: radio to choose which score level (High / Medium / Low) to display as bar height.
- Filter: task, teacher, judge.

**View 3 — Score distribution by target attribute value (heatmap)**

- Rows: target attribute values (e.g., `test_type=blood test`, `timing=in 1 week`).
- Columns: rubric aspects.
- Cell value: fraction of "High" scores for datapoints with that attribute value.
- Cell colour: green gradient (high fraction = green, low fraction = red).
- Filter: task, student, judge, teacher.
- Note: only attributes present in `sampled_target_attributes` (→ COEVAL-SPEC-001 §6.2.4) are shown. Datapoints not tagged with an attribute are counted under a synthetic "(not tagged)" row.

**View 4 — Judge score drift over evaluation order (line chart)**

- X-axis: evaluation record sequence number, ordered by `evaluated_at` (Phase 5 timestamp) — tracks judge behavior over the course of the evaluation run.
- Y-axis: rolling average normalized score (window = 20 records per judge).
- One line per judge model.
- Purpose: detect **judge calibration drift** — whether a judge gives systematically different scores later in a run than earlier, which can indicate prompt-sensitivity, API model changes, or temperature effects.
- This view is hidden if any judge has fewer than 20 valid evaluation records.
- Filter: task, student, rubric aspect.

**View 5 — Score by generation order (line chart, optional)**

- X-axis: datapoint sequence number ordered by `generated_at` (Phase 3 timestamp) — tracks teacher output quality over the generation run.
- Y-axis: rolling average normalized score (window = 20 datapoints), averaged across all judges and students for each datapoint.
- One line per teacher model.
- Purpose: detect **teacher generation drift** — whether teacher-generated items become easier or harder as generation progresses (e.g., the teacher model running out of diverse scenarios at high sequence numbers).
- This view is hidden if any teacher has fewer than 20 valid datapoints.
- Filter: task, judge, rubric aspect.

---

### 7.4 Teacher Model Score Report

**Goal:** Rank teacher models by how well their benchmark items differentiate student models. A good teacher produces items that cause meaningful performance spread across students.

**REQ-A-7.4.1** The Teacher Model Score Report (`coeval analyze teacher-report`) produces an HTML folder (→ §7.2) with the following views:

**View 1 — Teacher ranking table**

- One row per teacher model.
- Columns: Teacher ID, Task(s), Number of Datapoints (valid), Score (active formula), Score (formula 2), Score (formula 3), Coverage.
- Rows sorted by active formula score descending.
- Formula selector (dropdown) updates score column and row order.

**View 2 — Teacher score bar chart**

- X-axis: teacher models (sorted by active score).
- Y-axis: teacher differentiation score.
- Error bars: standard deviation of the score across tasks (if multiple tasks exist).
- Formula selector matches View 1.

**View 3 — Per-aspect score heatmap**

- Rows: teacher models.
- Columns: rubric aspects (within each task).
- Cell value: teacher's differentiation score for that aspect, using the active formula.
- Cell colour: blue gradient (higher = more discriminative for this aspect).
- Interpretation: aspects where all teachers score near 0 may indicate the rubric aspect is too easy or too hard to differentiate students.

**View 4 — Student score distribution per teacher (box plots)**

- One box plot per teacher model, per student model combination.
- Box shows the distribution of normalized scores across all datapoints from that teacher.
- Purpose: visually see whether a teacher produces a wide or narrow score range for each student.
- Filter: task, aspect, judge.

**REQ-A-7.4.2** The report includes an informational note:

> **Interpretation warning:** Teacher scores depend on which student and judge models are included. A teacher may appear highly discriminative only because one student model performs very poorly on all its items. Use the student and judge filters to verify that the differentiation is genuine.

---

### 7.5 Judge Model Score Report

**Goal:** Rank judge models by their reliability, measured as agreement with other judges.

**REQ-A-7.5.1** The Judge Model Score Report (`coeval analyze judge-report`) produces an HTML folder (→ §7.2) with the following views:

**View 1 — Judge ranking table**

- One row per judge model.
- Columns: Judge ID, SPA, WPA, κ (Kappa), Coverage-Weighted Score, Coverage, Valid Evaluations.
  - SPA / WPA / κ: mean pairwise agreement for each metric (simple mean across judge pairs, → §5.4.1).
  - Coverage-Weighted Score: coverage-weighted mean for the active metric (→ §5.4.2); reflects agreement adjusted for how many items each judge pair actually shares.
- Rows sorted by active metric descending.
- Metric selector (dropdown: SPA / WPA / κ) updates which column drives sorting and highlighting.
- Kappa column includes the conventional label ("Substantial", "Moderate", etc. → REQ-A-5.3.3).

**View 2 — Pairwise agreement matrix (heatmap)**

- Square matrix: rows = Jₐ, columns = J_b.
- Cell value: M(Jₐ, J_b) for the active metric.
- Cell colour: diverging scale (red=0, white=0.5, green=1.0 for SPA/WPA; red=0, white=0, green=1.0 for κ).
- Diagonal cells: grey (agreement with self is undefined).
- Hover tooltip: shows all three metric values and |E(Jₐ, J_b)| (common evaluation count).

**View 3 — Per-aspect agreement bar chart**

- X-axis: rubric aspects.
- Y-axis: mean pairwise agreement across all judge pairs for that aspect, using the active metric.
- Purpose: identify rubric aspects where all judges tend to disagree — a signal of an ambiguous or underspecified rubric factor.
- Filter: task, teacher, student.

**View 4 — Agreement distribution histogram**

- X-axis: agreement value (binned 0.0–1.0 in 10 bins).
- Y-axis: count of (Jₐ, J_b, r, a) tuples falling in each bin.
- One histogram per judge model (or overlaid with different colours and opacity).
- Purpose: reveal whether a judge tends to give scores that cluster at one end of the scale.

**REQ-A-7.5.2** The report includes a notice when only one judge model exists: "Agreement metrics require at least 2 judge models. Add more judge models and re-run Phase 5 to enable this report."

---

### 7.6 Student Model Score Report

**Goal:** Compare student model performance across all dimensions — task, aspect, judge, and teacher.

**REQ-A-7.6.1** The Student Model Score Report (`coeval analyze student-report`) produces an HTML folder (→ §7.2) with the following views:

**View 1 — Student ranking table**

- One row per student model.
- Columns: Student ID, Overall Average Score, per-task scores (one column per task), Valid Evaluations, Coverage.
- Rows sorted by Overall Average Score descending.
- Filter: task, teacher, judge — updates all scores in the table live.

**View 2 — Aspect heatmap (student × aspect)**

- Rows: student models.
- Columns: rubric aspects (grouped by task if multiple tasks exist).
- Cell value: average normalized score for that (student, aspect) slice.
- Cell colour: green gradient.
- Filter: task, teacher, judge.

**View 3 — Per-judge score comparison (grouped bar chart)**

- X-axis: student models.
- One bar group per student model; one bar per judge model within each group.
- Bar height: average normalized score for that (student, judge) pair.
- Purpose: detect judge-dependent score inflation (→ COEVAL-SPEC-001 REQ-12.7).
- Filter: task, teacher, aspect.

**View 4 — Per-attribute score breakdown (box plots)**

- For each target attribute key (e.g., `test_type`):
  - One box plot per attribute value, per student model.
  - Box shows score distribution across datapoints with that attribute value.
- Purpose: identify student model weaknesses on specific attribute values.
- Filter: task, teacher, judge.

---

### 7.7 Teacher-Student Interaction Matrix

**Goal:** Reveal systematic bias in teacher-student pairings — cases where a specific teacher model inflates or deflates scores for a specific student model.

**REQ-A-7.7.1** The Teacher-Student Interaction Matrix (`coeval analyze interaction-matrix`) produces an HTML folder (→ §7.2) with the following views:

**View 1 — Interaction heatmap (teacher × student)**

- Rows: teacher models.
- Columns: student models.
- Cell value: average normalized score for all evaluations with that (teacher, student) pairing, across all tasks, aspects, and judges.
- Cell colour: green gradient (→ §7.2 colour scheme).
- Hover tooltip: shows cell value, number of valid evaluations, and count of distinct tasks and judges in that cell.

**View 2 — Deviation heatmap**

- Same structure as View 1.
- Cell value: deviation from the student's row-mean score — i.e., `score(teacher, student) − mean_teacher(score(*, student))`.
- A positive deviation (warm colour) means this teacher inflates this student's scores relative to other teachers; negative (cool colour) means deflation.
- Diverging colour scale: blue (negative) → white (0) → red (positive).
- Purpose: directly surface teacher-student pairing biases, including circular evaluation cases (→ COEVAL-SPEC-001 REQ-12.7).

**View 3 — Per-aspect breakdown (faceted heatmaps)**

- One heatmap (teacher × student) per rubric aspect.
- Laid out as a grid if multiple aspects exist.
- Allows identification of teacher-student biases that are aspect-specific.
- Filter: task, judge.

**REQ-A-7.7.2** The report includes an informational note:

> **Self-evaluation warning:** Cells where teacher = student or judge = student may reflect self-evaluation bias (→ COEVAL-SPEC-001 REQ-12.7). These cells are highlighted with a dashed border. Interpret them with caution.

**REQ-A-7.7.3 Self-flag propagation across all reports.** The ⚠ indicators defined in REQ-A-3.9 (self-judging) and REQ-A-3.10 (self-teaching) apply globally across all report types, not only the interaction matrix. Specifically:
- In the **Student Report** (§7.6): table rows for (teacher, student, judge) combinations involving self-judging or self-teaching carry a ⚠ tooltip.
- In the **Judge Report** (§7.5): judge summary rows where that judge is also a student in the experiment carry a ⚠ tooltip noting "This judge also acted as a student — self-evaluations are included and flagged in per-pair views."
- In the **Score Distribution** (§7.3): chart annotations or legend entries note how many data points involve self-judging/self-teaching, with a toggle to show/hide those points.
- In the **Teacher Report** (§7.4): teacher rows where that teacher is also a student carry a ⚠ tooltip noting "Self-teaching responses are included in this teacher's differentiation score computation."
- In the **Complete Excel report** (§7.1): Sheet 1 includes a boolean column `self_judging` and a boolean column `self_teaching` for each row; rows with either flag set are highlighted in light orange.
- The report metadata panel (shown on each HTML dashboard header) lists: `Self-judging records: N`, `Self-teaching records: M`, `Self-judging + self-teaching records: K`.

---

### 7.8 Judge Consistency View

**Goal:** Assess how internally consistent each judge is — does the same judge give reproducible scores to structurally similar inputs?

**REQ-A-7.8.1** The Judge Consistency View (`coeval analyze judge-consistency`) produces an HTML folder (→ §7.2) with the following views:

**View 1 — Within-judge score variance by target attribute (heatmap)**

- Rows: judge models.
- Columns: target attribute values (e.g., `test_type=blood test`).
- Cell value: **within-judge score variance** — for each judge, compute the variance of scores given to all datapoints tagged with that attribute value, across all students and aspects.

```
IntraVar(j, attr=v, A) = sample_variance({ score_norm(eval(d, s, j, A)) :
                           sampled_target_attributes[attr] = v, valid eval })
```

- Cell colour: blue gradient (higher variance = less consistent for that attribute value).
- Interpretation: A consistent judge should give high scores to "High" attribute values and low scores to "Low" attribute values. High variance within a single attribute value suggests the judge is not reliably applying the rubric for that attribute.

**View 2 — Judge score distribution by target attribute (box plots)**

- For each judge model and each target attribute key:
  - One box plot per attribute value.
  - Box shows the distribution of scores the judge gave to items with that attribute value.
- Purpose: verify that judges are appropriately differentiating between different attribute values. A well-calibrated judge for `timing` should score `timing=in 1 week` differently from `timing=in 3 months`.
- Filter: task, student, rubric aspect.

**View 3 — Judge agreement stability (line chart)**

- X-axis: evaluation record number (in order of `evaluated_at` timestamp of the earlier judge's score in each pair).
- Y-axis: rolling pairwise SPA between this judge and each other judge (window = 50 common evaluation records). If fewer than 10 common records exist for a judge pair, this view is hidden for that pair with a notice.
- One line per (judge pair).
- Purpose: detect judges whose agreement with peers drifts over the course of the evaluation run, which may indicate prompt sensitivity or model degradation.
- Filter: task, student, rubric aspect.

**View 4 — Score calibration table**

- One row per `(judge, rubric_aspect)`.
- Columns: Mean Score Given, Std Dev, % High, % Medium, % Low, Most common score.
- Rows where % High > 90% or % Low > 90% are highlighted as potential calibration issues (the judge may be giving the same score indiscriminately).
- Filter: task, teacher, student.

---

### 7.9 Coverage Summary

**Goal:** Give a complete accounting of all (task, teacher, student, judge) combinations in the experiment — how many records exist, how many are valid, and where gaps or errors are.

**REQ-A-7.9.1** The Coverage Summary (`coeval analyze coverage-summary`) produces an HTML folder (→ §7.2) with the following views:

**View 1 — Coverage matrix table**

One row per `(task, teacher, student, judge)` combination. Columns:

| Column | Description |
|--------|-------------|
| Task | Task ID |
| Teacher | Teacher model ID |
| Student | Student model ID |
| Judge | Judge model ID |
| Expected Evaluations | `sampling.total` for this task (from config, if available). For a fully complete run, each (task, teacher, student, judge) row should contain exactly `sampling.total` evaluation records — one per datapoint the teacher generated. |
| Actual Phase 5 Records | Count of lines in the evaluation file |
| Valid Records | Count of records classified as valid (§5.2) |
| Invalid Records | Count of records with any error |
| Error Breakdown | Counts by error code (→ §5.2.1) |
| Coverage % | Valid / Expected (or Valid / Actual if Expected unknown) |

Rows with Coverage% < 100% are highlighted in orange. Rows with 0 valid records are highlighted in red.

**View 2 — Phase coverage waterfall (bar chart)**

Shows attrition through the pipeline for each task:

- Phase 3: datapoints generated.
- Phase 4: responses collected (per student).
- Phase 5: evaluations produced (per judge).
- Valid evaluations: after error filtering.

One stacked horizontal bar per task. Segments coloured by valid (green) / failed (red) / missing (grey).

**View 3 — Error code breakdown (stacked bar)**

- X-axis: error codes (→ §5.2.1).
- Y-axis: count of records with that error code.
- Grouped by task or model if filters applied.

**View 4 — Experiment meta panel**

Plain text summary shown at top of the page:

- Experiment ID, status, `created_at`, `updated_at` (from `meta.json`).
- Phases completed, phases in progress.
- Total models (by role), total tasks, total datapoints across all teachers.
- Total expected evaluations, total actual evaluations, total valid evaluations.
- If status is `in_progress`: yellow notice with last completed phase.

---

### 7.10 Robust Student Summary Report

**Goal:** Produce a conservative, high-confidence student ranking using only the most reliable judges, best teachers, and highest-agreement datapoints.

**REQ-A-7.10.1** The Robust Student Summary Report (`coeval analyze robust-summary`) produces an HTML folder (→ §7.2). All robust filtering (→ §5.7) uses the parameters specified at generation time (`--agreement-metric`, `--agreement-threshold`, `--judge-selection`). These parameters are embedded in the report and displayed prominently.

**View 1 — Robust filtering summary panel**

A clear summary box at the top of the report showing:

```
Robust Filtering Settings
─────────────────────────────────────────────────────────
Agreement metric:          Cohen's Kappa  (--agreement-metric kappa)
Judge selection:           Top half       (--judge-selection top_half)
Selected judges (J*):      [gpt4o-judge, llama3-judge]  (N=2 of 3)
Teacher score formula:     v1 — variance  (--teacher-score-formula v1)
Teacher selection (T*):    [gpt4o-teacher]              (N=1 of 2)
Agreement threshold θ:     1.0            (--agreement-threshold 1.0)
Consistency minimum q:     1              (ceil(|J*|/2) = ceil(2/2))

Coverage impact:
  All datapoints:          120
  From T* only:             60  (50.0%)
  Robust datapoints:        38  (31.7% of all, 63.3% of T*)
─────────────────────────────────────────────────────────
```

**View 2 — Robust student ranking table**

- One row per student model.
- Columns: Student ID, Robust Average Score, Full-Run Average Score, Delta (Robust − Full), Valid Robust Evaluations.
- Rows sorted by Robust Average Score descending.
- Students where |Delta| > 0.1 are highlighted with a flag icon and a tooltip: "Large difference between robust and full-run score may indicate sensitivity to judge quality or data quality."

**View 3 — Robust vs. full-run score comparison (scatter plot)**

- X-axis: Full-run average score per student.
- Y-axis: Robust average score per student.
- Each student is one dot.
- A diagonal line (y = x) is overlaid for reference.
- Students above the line improve in robust scoring; students below degrade.
- Hover tooltip: student ID, both scores, delta.

**View 4 — Robust aspect heatmap (student × aspect)**

- Same as Student Model Score Report View 2 (→ §7.6) but restricted to robust datapoints and J* judges.
- Label at top: "Computed from [N] robust datapoints using [M] selected judges."

**View 5 — Coverage breakdown table**

- Rows: teacher models.
- Columns: Task, # Datapoints, # Robust Datapoints, Coverage %.
- Shows per-teacher coverage drop so the user can see which teachers lost the most datapoints to the filter.

**REQ-A-7.10.2** The report includes a methodological note:

> **How to read this report:** Robust scores are computed from datapoints where all selected high-quality judges agreed on the student outcomes. This subset is smaller but more reliable. A student that ranks the same in both the full-run and robust reports is likely to be genuinely better or worse. A student that ranks very differently may be benefiting from lenient judges or easy teacher items in the full run.

---

### 7.11 Robust Benchmark Export

**Goal:** Export the robust datapoints as a reusable static benchmark dataset for subsequent use without CoEval infrastructure.

**REQ-A-7.11.1** `coeval analyze export-benchmark` applies the robust filtering algorithm (→ §5.7) using the specified CLI parameters and exports each robust datapoint as one record in the output file.

**REQ-A-7.11.2** Each exported record contains the following fields:

| Field | Type | Source | Description |
|-------|------|--------|-------------|
| `schema_version` | string | EEA | Fixed value `"coeval-benchmark-v1"` |
| `experiment_id` | string | EES `meta.json` | Source experiment |
| `datapoint_id` | string | Phase 3 | Original datapoint ID (→ COEVAL-SPEC-001 §6.2.4) |
| `task_id` | string | Phase 3 | Task identifier |
| `teacher_model_id` | string | Phase 3 | Teacher that generated the item |
| `prompt` | string | Phase 3 | Input to student models (benchmark question) |
| `reference_response` | string | Phase 3 | Teacher's ideal answer |
| `sampled_target_attributes` | map | Phase 3 | Target attribute tags |
| `rubric` | map | Phase 2 | Evaluation rubric (`{factor_name: description}`) |
| `student_scores` | map | Phase 5 | `{student_model_id: {rubric_aspect: "High"\|"Medium"\|"Low"}}` — scores from J* judges. When θ = 1.0, all J* judges agreed, so the score is unanimous. When θ < 1.0, the score is the **plurality vote** among J* judges for that (student, aspect) pair: the ordinal value appearing most frequently. Ties are broken conservatively (lower ordinal wins: Low > Medium > High in priority). |
| `judge_set` | list[string] | EEA | J* judge IDs used for filtering |
| `agreement_metric` | string | EEA | Metric used for robust filtering (`"spa"\|"wpa"\|"kappa"`) |
| `agreement_threshold` | float | EEA | θ value used |
| `consistent_fraction` | float | EEA | Fraction of (student, aspect) pairs that were judge-consistent for this datapoint |
| `exported_at` | string | EEA | ISO 8601 UTC timestamp of export |

**REQ-A-7.11.3** Supported output formats:

- **JSONL** (`--benchmark-format jsonl`): one JSON object per line, UTF-8, no trailing whitespace.
- **Parquet** (`--benchmark-format parquet`): columnar format; `student_scores` serialized as a JSON string column. Schema version written as a Parquet file metadata key `coeval_schema_version`.

**REQ-A-7.11.4** The export command prints to stdout:

```
Exported N robust datapoints from experiment <id>
  Judge set (J*):   [model1, model2]
  Teacher set (T*): [teacher1]
  Agreement metric: kappa
  Threshold θ:      1.0
  Output:           ./benchmark.jsonl
```

**REQ-A-7.11.5** The schema version field `"coeval-benchmark-v1"` enables consuming tools to detect the format version. Future versions of this spec that change the field set MUST increment the version string.

---

## 8. CLI Interface

### 8.1 Command structure

**REQ-A-8.1.1** All EEA commands use the prefix `coeval analyze` (→ COEVAL-SPEC-001 §8.2). The full command signature is:

```
coeval analyze <subcommand> --run <path> --out <path> [options]
```

**REQ-A-8.1.2** Available subcommands:

| Subcommand | Output | `--out` type |
|------------|--------|-------------|
| `complete-report` | Excel workbook | file path (`.xlsx`) |
| `score-distribution` | HTML folder | directory path |
| `teacher-report` | HTML folder | directory path |
| `judge-report` | HTML folder | directory path |
| `student-report` | HTML folder | directory path |
| `interaction-matrix` | HTML folder | directory path |
| `judge-consistency` | HTML folder | directory path |
| `coverage-summary` | HTML folder | directory path |
| `robust-summary` | HTML folder | directory path |
| `export-benchmark` | JSONL or Parquet file | file path |
| `all` | All HTML reports + Excel | directory path (subfolders created per report) |

**REQ-A-8.1.3** The `all` subcommand generates all reports and places them in subfolders. A single shared `plotly.min.js` is written to `<out>/` and each subfolder's `index.html` references it as `../plotly.min.js`. When using individual subcommands (not `all`), each report folder contains its own copy of `plotly.min.js` (→ §7.2.2).

```
<out>/
├── complete_report.xlsx
├── plotly.min.js                    ← shared by all subfolders (all command only)
├── score_distribution/
│   └── index.html                   (references ../plotly.min.js)
├── teacher_report/
├── judge_report/
├── student_report/
├── interaction_matrix/
├── judge_consistency/
├── coverage_summary/
└── robust_summary/
```

**REQ-A-8.1.4** Shared options:

| Flag | Default | Applies to |
|------|---------|------------|
| `--run <path>` | (required) | All |
| `--out <path>` | (required) | All |
| `--judge-selection <mode>` | `top_half` | `robust-summary`, `export-benchmark`, `all` |
| `--agreement-metric <m>` | `spa` | `robust-summary`, `export-benchmark`, `all` |
| `--agreement-threshold <float>` | `1.0` | `robust-summary`, `export-benchmark`, `all` |
| `--teacher-score-formula <f>` | `v1` | `robust-summary`, `export-benchmark`, `all` |
| `--benchmark-format <fmt>` | `jsonl` | `export-benchmark` |
| `--partial-ok` | false | All |
| `--log-level <level>` | `INFO` | All |

**REQ-A-8.1.5** EEA exits with code 0 on success and code 1 if:
- The `--run` path does not exist or contains no recognizable EES structure (no `meta.json` and no `phase5_evaluations/` folder).
- A required output file cannot be written (e.g., permission error).

Warnings (e.g., missing optional phases, invalid records) do not cause a non-zero exit; they are printed to stderr and continue.

**REQ-A-8.1.6** EEA prints a brief summary on startup:

```
CoEval Analyze — COEVAL-SPEC-002 v0.1
Experiment:    followup-multimodel-v1  (status: completed)
EES path:      ./runs/followup-multimodel-v1
Tasks:         2  |  Models: 3 (1 teacher, 2 student, 1 judge)
Phase 5 files: 2  |  Evaluation records: 100  |  Valid: 97
Output:        ./reports/followup-v1/
```

---

## 9. Examples

### Example A-9.1 — Generate all reports for a completed experiment

```bash
coeval analyze all \
  --run ./runs/followup-multimodel-v1 \
  --out ./reports/followup-v1 \
  --agreement-metric kappa \
  --agreement-threshold 1.0 \
  --judge-selection top_half
```

Produces:
```
./reports/followup-v1/
├── complete_report.xlsx
├── coverage_summary/index.html
├── score_distribution/index.html
├── teacher_report/index.html
├── judge_report/index.html
├── student_report/index.html
├── interaction_matrix/index.html
├── judge_consistency/index.html
├── robust_summary/index.html
└── plotly.min.js                    # shared across all reports
```

---

### Example A-9.2 — Export a robust benchmark and inspect coverage

```bash
# First, inspect coverage to decide on threshold
coeval analyze coverage-summary --run ./runs/followup-multimodel-v1 --out ./reports/coverage

# Then export with default settings
coeval analyze export-benchmark \
  --run ./runs/followup-multimodel-v1 \
  --out ./benchmark/followup-robust.jsonl \
  --agreement-metric kappa \
  --agreement-threshold 0.8 \
  --benchmark-format jsonl
```

---

### Example A-9.3 — Robust benchmark record (JSONL)

```json
{
  "schema_version": "coeval-benchmark-v1",
  "experiment_id": "followup-multimodel-v1",
  "datapoint_id": "followup_reminder__gpt-4o-teacher__00003",
  "task_id": "followup_reminder",
  "teacher_model_id": "gpt-4o-teacher",
  "prompt": "PLAN:\n1) Repeat blood work in 1 week.\n2) Follow-up EKG in 1 month.",
  "reference_response": "Please schedule your blood test in 1 week and your EKG in 1 month.",
  "sampled_target_attributes": {"test_type": "blood test", "timing": "in 1 week"},
  "rubric": {
    "test_identity_grounding": "Correctly identifies the follow-up test.",
    "timing_grounding": "States timing exactly as written."
  },
  "student_scores": {
    "ft-reminder-v2": {"test_identity_grounding": "High", "timing_grounding": "High"},
    "hf-llama-student": {"test_identity_grounding": "Medium", "timing_grounding": "High"}
  },
  "judge_set": ["gpt-4o-judge"],
  "agreement_metric": "kappa",
  "agreement_threshold": 1.0,
  "consistent_fraction": 1.0,
  "exported_at": "2026-02-23T14:00:00Z"
}
```

---

### Example A-9.4 — Excel Model Summary sheet (partial)

| Model ID | Roles | As Student — Avg Score | As Teacher — Score (V) | As Judge — SPA | As Judge — κ |
|----------|-------|------------------------|------------------------|----------------|--------------|
| gpt-4o-teacher | teacher | N/A | 0.182 | N/A | N/A |
| ft-reminder-v2 | student | 0.847 | N/A | N/A | N/A |
| hf-llama-student | student | 0.703 | N/A | N/A | N/A |
| gpt-4o-judge | judge | N/A | N/A | 0.914 | 0.821 |

---

## 10. MVP Scope

**REQ-A-10.1** The EEA MVP implements all outputs defined in §7. No report is deferred.

**REQ-A-10.2** All computation is performed in memory on the local machine. No database, no caching layer, and no background workers are required. For experiments with very large `sampling.total` values or many models, EEA may require significant memory; this is a known limitation of the in-memory design.

**REQ-A-10.3** Plotly.js must be available at HTML report generation time (either as a local file bundled with the EEA installation, or downloaded once to a cache directory on first use). EEA checks for the Plotly.js file at startup and exits with a descriptive error if it is not found.

**REQ-A-10.4** The `export-benchmark` Parquet output requires the `pyarrow` library to be installed. If `pyarrow` is not available and `--benchmark-format parquet` is requested, EEA exits with a descriptive error suggesting `pip install pyarrow`.

**REQ-A-10.5** Cross-experiment analysis (comparing two or more EES experiments) is out of scope. The robust benchmark export (§7.11) is the intended mechanism for creating reusable datasets that can be compared across experiments externally.

**REQ-A-10.6** Statistical significance testing (e.g., bootstrap confidence intervals on student score differences) is out of scope for this version. Report values are point estimates; the Valid Data Points and Coverage columns provide the user with the sample size to interpret reliability manually.

**REQ-A-10.7** The robust benchmark schema version `"coeval-benchmark-v1"` is the only supported version in this release. No forward or backward compatibility guarantees are made for format changes in future spec versions.

---

*Document end. Cross-reference key: REQ-A-N.N = requirement in this document (COEVAL-SPEC-002); REQ-N.N = requirement in COEVAL-SPEC-001; §N = section of this document; SPEC-001 §N = section of COEVAL-SPEC-001.*
