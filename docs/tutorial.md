# CoEval Tutorial — End-to-End Guide

This tutorial walks you through the full CoEval workflow: from understanding why the tool
exists to exporting a publishable benchmark dataset.  It is written as a narrative, so
reading it top-to-bottom gives you a complete mental model.  After finishing it you can use
the reference documents for the fine details.

**Document map**

| Section | Covers |
|---------|--------|
| [1. Motivation](#1-motivation) | What problem CoEval solves and the core idea |
| [2. Installation & Keys](#2-installation--keys) | Getting started with providers |
| [3. Designing & Running Experiments](#3-designing--running-experiments) | Config, probing, estimation, ingestion |
| [4. Monitoring, Resuming & Repairing](#4-monitoring-resuming--repairing) | Status, --continue, repair |
| [5. Producing Analysis](#5-producing-analysis) | Running all reports |
| [6. Report Types & Raw Files](#6-report-types--raw-files) | What each report answers |
| [7. Exporting Robust Benchmarks](#7-exporting-robust-benchmarks) | What "robust" means and how to export |
| [8. Further Reading](#8-further-reading) | Links to reference docs |

---

## 1. Motivation

CoEval addresses the core difficulty in practical LLM evaluation: generic benchmarks do not
transfer to your use-case, human raters are expensive, and a single judge model is biased
toward its own style.  The answer is a **multi-model, multi-role ensemble** where each
participating model rotates through three distinct roles:

| Role | What it does |
|------|-------------|
| **Teacher** | Generates synthetic (prompt, reference-response) pairs and proposes the attribute taxonomy and rubric |
| **Student** | Receives teacher prompts and produces its own responses — these are the models under evaluation |
| **Judge** | Scores every student response against the rubric on a High / Medium / Low scale |

Rotating roles across the full model ensemble and aggregating over multiple judges washes
out individual biases — yielding a *robust*, reproducible, and cost-efficient quality signal.

> **Deeper background** — problem statement, design rationale, leakage pitfalls, and
> typical use-cases: [Overview & Why CoEval → docs/README/01-overview.md](README/01-overview.md)

---

## 2. Installation & Keys

### Installing CoEval

```bash
# From PyPI
pip install coeval

# From source (development)
git clone https://github.com/ApartsinProjects/CoEval
cd CoEval/main
pip install -e .

# With HuggingFace local-model support (requires a CUDA GPU)
pip install -e ".[huggingface]"
```

### Provider key file

CoEval discovers credentials through a YAML key file.  The default lookup order is:

1. `--keys PATH` argument on any command
2. `COEVAL_KEYS_FILE` environment variable
3. `keys.yaml` in the project root
4. `~/.coeval/keys.yaml` (global fallback)

Create `keys.yaml` at your project root:

```yaml
providers:
  openai:     sk-...
  anthropic:  sk-ant-...
  gemini:     AIza...
  huggingface: hf_...
  openrouter: sk-or-v1-...
  # azure_openai: {api_key: ..., endpoint: https://..., api_version: 2024-08-01-preview}
  # bedrock: {api_key: BedrockAPIKey-..., region: us-east-1}
  # vertex: {project: my-gcp-project, location: us-central1}
```

> **Security:** `keys.yaml` is in `.gitignore` by default.  Never commit credentials.

### Automatic provider selection (`interface: auto`)

Setting `interface: auto` on a model tells CoEval to automatically select the
cheapest configured provider for that model, based on `Config/provider_pricing.yaml`:

```yaml
- name: deepseek-v3
  interface: auto          # resolves to openrouter (cheapest with your credentials)
  parameters:
    model: deepseek/deepseek-chat
    temperature: 0.7
    max_tokens: 512
  roles: [student]
```

CoEval scans the `auto_routing` table in `Config/provider_pricing.yaml` top-to-bottom
(cheapest first) and picks the first matching provider for which you have credentials.
Resolution happens at config load time, before validation or probing.

**When to use it:** Use `interface: auto` when you want your config to be portable —
different users with different provider credentials will each get the cheapest option
they have access to.

### Supported providers

CoEval supports **16 model interfaces** across cloud, local, and virtual providers.  For
the complete table — auth setup, async batch support, pricing, and YAML examples — see:

> 📋 **[Provider Guide → docs/README/05-providers.md](README/05-providers.md)**

**Quick reference — most commonly used interfaces:**

| Interface | Auth env var | Async batch | Best for |
|-----------|-------------|:-----------:|---------|
| `openai` | `OPENAI_API_KEY` | ✅ 50% off | GPT-4o, o-series |
| `anthropic` | `ANTHROPIC_API_KEY` | ✅ 50% off | Claude Haiku/Sonnet |
| `gemini` | `GEMINI_API_KEY` | ⚡ Concurrent¹ | Gemini Flash (fast/cheap) |
| `azure_openai` | `AZURE_OPENAI_API_KEY` | ✅ 50% off | Azure enterprise GPT |
| `bedrock` | AWS key or IAM | ✅ 50% off² | AWS-native (Claude, Nova) |
| `vertex` | GCP ADC | ✅ 50% off² | GCP enterprise Gemini |
| `openrouter` | `OPENROUTER_API_KEY` | — | Open models: Llama, Qwen, DeepSeek |
| `huggingface` | `HF_TOKEN` | — | Local GPU inference |

> ¹ Gemini uses concurrent requests, not a native async batch endpoint — no additional discount.
> ² Bedrock and Vertex async batch require cloud storage (S3/GCS) and a service role — see the [Provider Guide](README/05-providers.md#aws-bedrock) for setup details.

For open-weight models, `openrouter` provides access to hundreds of models with a single
key.  Direct-API providers (Groq, DeepInfra, DeepSeek direct, Mistral direct, Cerebras,
Ollama) are also available — see the [Provider Guide](README/05-providers.md#openai-compatible-providers).

> **Security:** `keys.yaml` is in `.gitignore` by default.  Never commit credentials.
> Full key-file format and lookup order: [CLI Reference → Provider Key File](cli_reference.md#provider-key-file).

### Verifying your setup

```bash
# List available models from all configured providers
coeval models

# Filter to a specific provider
coeval models --providers openai anthropic
```

---

## 3. Designing & Running Experiments

### 3.1 The five-phase pipeline

Every CoEval experiment is an ordered sequence of five phases:

| # | Phase ID | What happens | Output files |
|---|----------|-------------|-------------|
| 1 | `attribute_mapping` | Teachers propose `target_attributes` (e.g., complexity, tone) and `nuanced_attributes` from the task description | `phase1_attributes/{task}_target_attrs.json`, `{task}_nuanced_attrs.json` |
| 2 | `rubric_mapping` | Teachers define the evaluation rubric (aspect name → definition) | `phase2_rubric/{task}.rubric.json` |
| 3 | `data_generation` | Teachers generate (prompt, reference-response) pairs covering the attribute space | `phase3_datapoints/{task}.{teacher}.datapoints.jsonl` |
| 4 | `response_collection` | Students respond to every teacher-generated prompt | `phase4_responses/{task}.{student}.responses.jsonl` |
| 5 | `evaluation` | Judges score each student response on every rubric aspect | `phase5_evaluations/{task}.{teacher}.{judge}.evaluations.jsonl` |

All artifacts accumulate inside a single **Experiment Evaluation Storage (EES) folder**:

```
benchmark/runs/my-experiment-v1/
├── meta.json                      ← run status, phase completion log
├── config.yaml                    ← snapshot of the YAML used
├── pending_batches.json           ← batch job tracking
├── run_errors.jsonl               ← per-item error log
├── phase1_attributes/
├── phase2_rubric/
├── phase3_datapoints/
├── phase4_responses/
└── phase5_evaluations/
```

### 3.2 Writing a config file

Every experiment is described by a single YAML file.  The three top-level keys are
`models`, `tasks`, and `experiment`.

```yaml
# ── MODELS ─────────────────────────────────────────────────────────────────────
models:

  # A model can hold any combination of teacher / student / judge roles.
  - name: gpt-4o-mini
    interface: openai
    parameters:
      model: gpt-4o-mini
      temperature: 0.7
      max_tokens: 512
    roles: [teacher, student, judge]
    # Override parameters per role (optional)
    role_parameters:
      judge:
        temperature: 0.0    # deterministic scoring
        max_tokens: 128

  - name: gpt-3.5-turbo
    interface: openai
    parameters:
      model: gpt-3.5-turbo
      temperature: 0.7
      max_tokens: 512
    roles: [student, judge]


# ── TASKS ──────────────────────────────────────────────────────────────────────
tasks:

  - name: text_summarization
    description: >
      Summarise a passage of text concisely and accurately.
    output_description: >
      A 1–3 sentence summary in plain prose.

    # Attributes define the diversity axes for generated prompts.
    target_attributes:
      complexity: [simple, moderate, complex]
      tone:       [neutral, formal, conversational]

    # Nuanced attributes add secondary variation within each datapoint.
    nuanced_attributes:
      domain: [science, business, politics]

    sampling:
      target: [1, 2]   # sample 1–2 target attribute values per datapoint
      nuance: [1]       # sample 1 nuanced attribute value
      total:  20        # datapoints per (task, teacher) pair

    rubric:
      accuracy:    "The summary correctly captures all key points without distortion."
      conciseness: "The summary avoids redundancy and respects the length target."
      readability: "The writing is clear, grammatical, and flows naturally."

    evaluation_mode: single   # judge scores all aspects in one JSON response

    prompt_library:
      sample: |
        Generate a datapoint for: {task_description}
        Attributes: {target_attributes}. Nuance: {nuanced_attributes}.
        Return JSON with keys "prompt" and "response". No explanation.


# ── EXPERIMENT ─────────────────────────────────────────────────────────────────
experiment:
  id: text-summarization-v1
  storage_folder: ./runs
  log_level: INFO

  # Phase modes: New | Keep | Extend
  phases:
    attribute_mapping:   New
    rubric_mapping:      New
    data_generation:     New
    response_collection: New
    evaluation:          New

  # Enable OpenAI Batch API (50 % cost reduction)
  batch:
    openai:
      response_collection: true
      evaluation: true

  # Safety ceiling per model (optional but recommended)
  quota:
    gpt-4o-mini:
      max_calls: 5000
```

> **Full YAML reference** — every config field (models, tasks, sampling, rubric, phases,
> batch, quota) with types, defaults, and validation rules:
> [Configuration Guide → docs/README/04-configuration.md](README/04-configuration.md)

**Phase mode quick reference**

| Mode | Behaviour |
|------|-----------|
| `New` | Delete any existing output and regenerate from scratch |
| `Keep` | Skip the phase entirely; use whatever is already on disk |
| `Extend` | Generate only the missing items; skip what already exists |

### 3.3 Auto-generating a config with the wizard

If you prefer to describe your goal in plain English, the wizard generates a ready-to-run
YAML for you:

```bash
coeval wizard --out experiments/my-eval.yaml
```

The wizard prompts you for:

* The task (what should models do?)
* Which providers and models to use
* How many datapoints and rubric dimensions
* Whether to enable batch pricing

The generated file uses the same format as a hand-written config and can be edited freely
afterwards.

**Materialising auto placeholders.**  You can also write a "sketch" config with
`target_attributes: auto` and `rubric: auto` and let CoEval fill them in:

```bash
coeval generate --config sketch.yaml --out design.yaml
```

This runs phases 1–2 in a temporary directory, reads the generated values, and writes
them as static YAML into `design.yaml`.  Review and edit the result before using
`design.yaml` as your production config.

### 3.4 Previewing the config as HTML

Before committing to a run, generate a human-readable summary:

```bash
coeval describe --config experiments/my-eval.yaml
```

This opens a self-contained HTML page in your browser showing:

* Model cards with interface icons, role badges, and parameter tables
* Task cards (collapsible) with target attributes and rubric
* Phase plan with estimated API call counts
* Batch configuration and per-model quota

No API calls are made; the command is purely informational.

> **Example planning HTML:** Open the [Education Benchmark Plan](https://htmlpreview.github.io/?https://raw.githubusercontent.com/ApartsinProjects/CoEval/master/Runs/education/education_description.html) to see a real planning view for the education benchmark (3 real-dataset tasks + 10 synthetic tasks, 6 models, cost table).

### 3.5 Checking model availability

Verify that every model in your config responds before spending real budget:

```bash
# Standalone probe (exits after probing, no experiment started)
coeval probe --config experiments/my-eval.yaml

# Probe automatically before running (full = re-probe on every run)
coeval run --config experiments/my-eval.yaml --probe full
```

Results are written to `probe_results.json` in the EES folder.  If a model fails,
`--probe-on-fail abort` (default) stops the experiment immediately; use `warn` to
continue without the failing model.

> **All probe options** — `--probe` modes (`full`, `resume`, `disable`), `--probe-on-fail`,
> and the `probe_results.json` schema:
> [CLI Reference → `coeval probe`](cli_reference.md#coeval-probe)

### 3.6 Estimating cost and time

```bash
# Estimate only (no LLM calls, no experiment folder created)
coeval plan --config experiments/my-eval.yaml

# Estimate during a run (print table then exit before phase 1)
coeval run --config experiments/my-eval.yaml --estimate-only
```

The plan command prints a per-phase, per-model call budget and writes
`cost_estimate.json`.  The estimation uses heuristics; add `--estimate-samples 3` to
make two real sample calls per model for more accurate token-count data.

**Quick mental formula:**

```
Phase 3 calls = n_teachers × n_tasks × datapoints_per_task
Phase 4 calls = n_students × Phase_3_calls
Phase 5 calls = n_judges   × Phase_4_calls
Total         = sum of the above
```

With async batch pricing enabled (OpenAI, Anthropic, Azure OpenAI, Bedrock, or Vertex),
phases 4 and 5 cost 50 % less.

> **All plan/estimate options** — `--estimate-samples`, `cost_estimate.json` schema,
> and per-provider batch discount details:
> [CLI Reference → `coeval plan`](cli_reference.md#coeval-plan)

### 3.7 Running the experiment

```bash
coeval run --config experiments/my-eval.yaml
```

CoEval prints live progress for each phase and each model.  Every item is written to disk
immediately — if the process is killed, no work is lost.

Useful flags:

| Flag | Effect |
|------|--------|
| `--dry-run` | Validate config, print phase plan, exit — no API calls |
| `--estimate-only` | Print cost table then exit — no API calls |
| `--continue` | Restart a failed experiment in-place (see §4.3) |
| `--probe full` | Probe all models before starting |
| `--only-models A B` | Restrict which models participate (useful for incremental additions) |

> **All `coeval run` flags** — `--dry-run`, `--estimate-only`, `--only-models`,
> `--probe`, phase modes, and batch configuration options:
> [CLI Reference → `coeval run`](cli_reference.md#coeval-run)

### 3.8 Using real benchmark datasets as teachers

Instead of asking teacher LLMs to invent prompts, you can source (prompt, reference-response)
pairs directly from established NLP benchmarks.  This gives you ground-truth quality
and aligns your evaluation with the research literature.

**Two workflows are available:**

#### Option A — `coeval ingest` (add a benchmark to an existing run)

```bash
# Step 1 — Ingest benchmark data into an existing EES folder (or create a new one)
coeval ingest \
    --run runs/my-exp \
    --benchmarks mmlu \
    --limit 200

# Step 2 — Resume the experiment; phases 4-5 now run for the new teacher too
coeval run --config experiments/my-eval.yaml --continue
```

Supported benchmark names: `mmlu`, `hellaswag`, `truthfulqa`, `humaneval`, `medqa`, `gsm8k`.

#### Option B — `interface: benchmark` (purpose-built benchmark experiment)

For experiments designed from the start to use benchmark data, declare a `benchmark`
interface teacher in your config.  Phase 3 is automatically skipped for that model:

```yaml
models:
  - name: benchmark
    interface: benchmark    # virtual; no API calls
    parameters: {}
    roles: [teacher]
```

Then pre-ingest the data once before running:

```bash
python -m benchmark.setup_mixed   # writes phase3_datapoints/ files
coeval run --config Runs/mixed/mixed.yaml --continue
```

See `Runs/mixed/mixed.yaml` and `Public/benchmark/setup_mixed.py` for a complete working example
using XSum, CodeSearchNet, AESLC, and WikiTableQuestions.

### Dual-track experiments: benchmark vs. synthetic

A dual-track experiment runs the same student models on two data sources for the same tasks:

- **Track A (benchmark):** Pre-emitted datapoints from a real benchmark dataset.
  Use a `benchmark` virtual teacher — no LLM API calls are made for Phase 3.
- **Track B (synthetic):** LLM-generated datapoints from your teacher models.

This lets you cross-validate rankings: if Kendall τ between Track A and Track B
rankings is high (≥ 0.85), your evaluation is stable regardless of data source.

```yaml
models:
  # Track A teacher — no API calls; loads from pre-emitted JSONL
  - name: benchmark_data
    interface: benchmark
    parameters: {}
    roles: [teacher]

  # Track B teacher — generates synthetic prompts
  - name: gpt-4o
    interface: openai
    parameters: {model: gpt-4o, temperature: 0.8, max_tokens: 768}
    roles: [teacher, student, judge]
```

See `benchmark/paper_dual_track.yaml` for the full dual-track paper experiment config.

---

## 4. Monitoring, Resuming & Repairing

### 4.1 Checking experiment progress

```bash
coeval status --run runs/my-experiment-v1
```

The output shows:

* `meta.json` fields — experiment ID, status (`in_progress` / `completed`), phases completed
* Artifact counts per phase (JSON files, JSONL records)
* Any pending batch jobs (batch ID, provider, status, submitted time)
* The last 10 errors from `run_errors.jsonl`

### 4.2 Fetching and applying batch results

When you use the OpenAI or Anthropic Batch APIs, jobs are submitted asynchronously and
may take minutes to hours.  To check whether jobs have completed and apply their results
to the EES folder:

```bash
coeval status --run runs/my-experiment-v1 --fetch-batches
```

This polls the provider APIs for each pending batch, downloads completed output, and
writes the results directly into `phase4_responses/` or `phase5_evaluations/`.  The
experiment can then be continued:

```bash
coeval run --config experiments/my-eval.yaml --continue
```

> **Note:** Phase 3 batch results (data generation) cannot be automatically applied —
> they are resubmitted on the next `--continue` run instead.

### 4.3 Resuming after a failure or interruption

Because every item is written to disk immediately, a crash wastes at most one
in-flight batch.  To restart where you left off:

```bash
coeval run --config experiments/my-eval.yaml --continue
```

`--continue` applies two levels of skip logic simultaneously:

1. **Phase-level skip** — any phase listed in `phases_completed` inside `meta.json` is
   skipped entirely.
2. **Item-level skip** — within each incomplete phase, already-written JSONL records are
   read and only the missing items are processed (Extend mode).

**Requirements:**

* The `meta.json` file must already exist in the EES folder (created by any previous run
  attempt).
* The `id` in your config must match the `experiment_id` in `meta.json`.

### 4.4 Diagnosing and repairing broken records

Occasionally a phase 4 or phase 5 file contains structurally invalid records (malformed
JSON, missing required fields, incorrect score values).  The `repair` command finds and
marks these:

```bash
# Step 1 — Audit only (read-only; nothing modified)
coeval repair --run runs/my-experiment-v1 --stats --dry-run

# Step 2 — See details with examples
coeval repair --run runs/my-experiment-v1 --dry-run --examples 5

# Step 3 — Apply: mark invalid records as failed, reopen affected phases in meta.json
coeval repair --run runs/my-experiment-v1

# Step 4 — Regenerate only the marked records
coeval run --config experiments/my-eval.yaml --continue

# Step 5 — Confirm the run is now clean
coeval repair --run runs/my-experiment-v1 --stats
```

`coeval repair` never deletes data.  It marks broken records with a `_coeval_invalid`
flag and updates `meta.json` so that `--continue` picks up the gaps.

---

## 5. Producing Analysis

Once an experiment has at least some phase 4 and phase 5 data you can generate reports.

### 5.1 Generating all reports at once

```bash
coeval analyze all \
    --run runs/my-experiment-v1 \
    --out runs/my-experiment-v1/reports
```

This creates a folder of HTML reports, one Excel workbook, and a shared `plotly.min.js`
file.  Opening `reports/index.html` gives you an interactive portal with links to all
individual reports.

### 5.2 Running individual reports

```bash
# Teacher quality report
coeval analyze teacher-report \
    --run runs/my-experiment-v1 --out reports/

# Student performance report
coeval analyze student-report \
    --run runs/my-experiment-v1 --out reports/

# Full Excel workbook
coeval analyze complete-report \
    --run runs/my-experiment-v1 --out results.xlsx
```

### 5.3 Analysing incomplete experiments

Add `--partial-ok` to run analysis while the experiment is still in progress:

```bash
coeval analyze all \
    --run runs/my-experiment-v1 \
    --out reports/ \
    --partial-ok
```

A warning banner appears at the top of each HTML report to indicate the data is
preliminary.

### 5.4 Raw files and data model

All analysis reads the same EES folder you already know.  The key unit is:

```
(datapoint_id, student_model_id, rubric_aspect, judge_model_id) → score ∈ {High, Medium, Low}
```

Normalised to floats: `High = 1.0`, `Medium = 0.5`, `Low = 0.0`.

Phase 3 JSONL records contain:

| Field | Description |
|-------|-------------|
| `id` | Unique datapoint ID |
| `task_id` | Task name |
| `teacher_model_id` | Name of the teacher that generated it |
| `prompt` | The input text given to students |
| `reference_response` | Teacher's reference answer |
| `sampled_target_attributes` | Which attribute values were sampled for this item |

Phase 4 records add `student_model_id` and `response`.  Phase 5 records add
`judge_model_id`, `rubric_aspect`, and `score`.

---

## 6. Report Types & What They Tell You

> **Sample reports** — all of the following report types have pre-generated examples in `samples/analysis/coeval-demo-v2/`. Click to open rendered in browser:
>
> | Sample file | Report type |
> |-------------|-------------|
> | [Student Report](https://htmlpreview.github.io/?https://raw.githubusercontent.com/ApartsinProjects/CoEval/master/docs/samples/analysis/coeval-demo-v2/coeval-demo-v2_student_report.html) | Student Report |
> | [Judge Consistency](https://htmlpreview.github.io/?https://raw.githubusercontent.com/ApartsinProjects/CoEval/master/docs/samples/analysis/coeval-demo-v2/coeval-demo-v2_judge_consistency.html) | Judge Consistency |
> | [Robust Summary](https://htmlpreview.github.io/?https://raw.githubusercontent.com/ApartsinProjects/CoEval/master/docs/samples/analysis/coeval-demo-v2/coeval-demo-v2_robust_summary.html) | Robust Summary |
> | [Score Distribution](https://htmlpreview.github.io/?https://raw.githubusercontent.com/ApartsinProjects/CoEval/master/docs/samples/analysis/coeval-demo-v2/coeval-demo-v2_score_distribution.html) | Score Distribution |
> | [Teacher Report](https://htmlpreview.github.io/?https://raw.githubusercontent.com/ApartsinProjects/CoEval/master/docs/samples/analysis/coeval-demo-v2/coeval-demo-v2_teacher_report.html) | Teacher Report |
> | [Interaction Matrix](https://htmlpreview.github.io/?https://raw.githubusercontent.com/ApartsinProjects/CoEval/master/docs/samples/analysis/coeval-demo-v2/coeval-demo-v2_interaction_matrix.html) | Interaction Matrix |
> | [Coverage Summary](https://htmlpreview.github.io/?https://raw.githubusercontent.com/ApartsinProjects/CoEval/master/docs/samples/analysis/coeval-demo-v2/coeval-demo-v2_coverage_summary.html) | Coverage Summary |
> | [Judge Report](https://htmlpreview.github.io/?https://raw.githubusercontent.com/ApartsinProjects/CoEval/master/docs/samples/analysis/coeval-demo-v2/coeval-demo-v2_judge_report.html) | Judge Report |

### Coverage Summary

**Command:** `coeval analyze coverage-summary`

**Answers:** Did the teacher generate enough datapoints across the full attribute space?

Shows stacked bar charts of artifact counts per phase and per model, with a breakdown
of which attribute-value combinations were actually covered.  If a rare attribute
value (e.g., `complexity=technical`) has zero datapoints, this report is where you will
see it.  Check this first after phase 3 to catch systematic gaps before running phases 4–5.

### Score Distribution

**Command:** `coeval analyze score-distribution`

**Answers:** Are scores spread across High / Medium / Low, or is every model rated the same?

Histograms and box plots of rubric scores sliced by judge, teacher, student, task, and
attribute.  If a judge gives every response "High", it is not providing useful signal —
visible here as a degenerate distribution.

### Teacher Report

**Command:** `coeval analyze teacher-report`

**Answers:** Which teacher generates the most *discriminating* prompts?

Teachers are scored on their ability to elicit different student quality levels.  A
teacher with high differentiation score produces prompts where good models clearly
outperform poor ones.  Three formula choices are available via `--teacher-score-formula`:

| Formula | Meaning |
|---------|---------|
| `v1` | Variance of per-student composite scores |
| `s2` | Spread (max − min) across students |
| `r3` | Range weighted by response count |

A teacher with score near zero means all students got similar ratings — the prompts are
not challenging or are too easy for all models.

### Judge Report

**Command:** `coeval analyze judge-report`

**Answers:** How much do judges agree with each other?

Pairwise agreement metrics (SPA, WPA, κ) for every judge pair, per task.  A judge that
disagrees strongly with all others is either more insightful or simply unreliable.  The
inter-judge reliability ranking helps you decide which judges to trust for the final
robust ranking.

### Student Report

**Command:** `coeval analyze student-report`

**Answers:** Which model performs best, on which tasks, and on which rubric dimensions?

Per-model composite scores, per-task rankings, and a task × aspect heatmap.  This is
typically the report you care most about: it gives you the headline ranking.

### Interaction Matrix

**Command:** `coeval analyze interaction-matrix`

**Answers:** Do score differences reflect model capability or data source effects?

Heatmap of mean score for every (teacher, student) pair.  If row effects (teacher
contribution) dominate column effects (student contribution), your evaluation signal is
confounded by which teacher produced the data — a common pitfall.

### Judge Consistency

**Command:** `coeval analyze judge-consistency`

**Answers:** Is each judge internally consistent, or do scores drift over time?

Within-judge variance across rubric aspects and across attributes.  A judge whose scores
vary wildly for the same type of response is unreliable — this report diagnoses it.

### Robust Summary

**Command:** `coeval analyze robust-summary`

**Answers:** What is the *reliable* ranking after filtering out noisy signal?

This report applies the robust filter: it selects the best judge subset (J\*) and the
best teacher subset (T\*) and recomputes rankings on the filtered data.  Rankings here are
more stable than the unfiltered student report.  Use `--agreement-threshold` to tune how
strict the filter is.

### Summary Report

**Command:** `coeval analyze summary-report`

**Answers:** Everything at once, in one interactive page.

A single-page Chart.js dashboard with tabs for teacher quality, judge reliability, and
student performance.  Global filters let you slice by task, judge, or student in real
time.  Good starting point for a presentation or paper appendix.

### Complete Report (Excel)

**Command:** `coeval analyze complete-report`

**Answers:** Everything in a spreadsheet.

Multi-sheet Excel workbook with frozen headers and conditional colour scales:
`Summary`, `StudentScores`, `TeacherCoverage`, `JudgeAgreement`, `FailedRecords`.
Useful for sharing results with colleagues who prefer Excel over HTML.

---

## 7. Exporting Robust Benchmarks

### 7.1 What "robust" means

After running an experiment you have thousands of (prompt, response, score) triples.  Not
all of them are equally trustworthy:

* A datapoint where all judges agreed on the score is more reliable than one where they
  disagreed.
* A teacher who generated datapoints that strongly separated good students from poor ones
  produced higher-quality data.

The *robust* filter selects:

* **J\*** — the subset of judges with the highest pairwise agreement scores
* **T\*** — the subset of teachers with the highest differentiation scores
* **D\*** — the datapoints produced by T\* where J\* scored with agreement ≥ θ (the
  consistency threshold)

Only the D\* datapoints are exported.  This means the exported benchmark represents the
most reliable, least noisy portion of your experiment's data.

### 7.2 Exporting

```bash
# Default: JSONL, strict filter (top half of judges, SPA ≥ 1.0)
coeval analyze export-benchmark \
    --run runs/my-experiment-v1 \
    --out my-benchmark.jsonl

# Relax the filter for more data
coeval analyze export-benchmark \
    --run runs/my-experiment-v1 \
    --out my-benchmark.jsonl \
    --agreement-threshold 0.75 \
    --judge-selection all

# Parquet format (for large datasets or pipeline integration)
coeval analyze export-benchmark \
    --run runs/my-experiment-v1 \
    --out my-benchmark.parquet \
    --benchmark-format parquet

# HuggingFace-ready directory (Parquet + dataset card)
coeval analyze export-benchmark \
    --run runs/my-experiment-v1 \
    --out my-org/my-benchmark \
    --benchmark-format huggingface \
    --dataset-name "my-org/my-benchmark" \
    --author "My Org" \
    --agreement-threshold 0.8
```

If the filter is too strict and produces zero records, the command prints diagnostics
and exits with code 1.  The suggested remedies are:

* Lower `--agreement-threshold` (try 0.75 or 0.5)
* Use `--judge-selection all` instead of `top_half`
* Check the coverage summary to ensure phase 3 has enough diverse datapoints

### 7.3 Output schema

Each record in the JSONL export is a self-contained benchmark item:

| Field | Description |
|-------|-------------|
| `schema_version` | Always `"coeval-benchmark-v1"` |
| `experiment_id` | The experiment that produced this item |
| `datapoint_id` | Unique identifier — stable across re-runs |
| `task_id` | Task the prompt belongs to |
| `teacher_model_id` | Teacher that generated the prompt |
| `prompt` | The input text |
| `reference_response` | Teacher's reference answer |
| `sampled_target_attributes` | Attribute values (e.g., `{complexity: complex, tone: formal}`) |
| `rubric` | Full rubric definition (aspect → criterion text) |
| `student_scores` | Per-student, per-aspect scores after plurality vote over J\* |
| `judge_set` | J\* — judges used for voting |
| `agreement_metric` | Which metric was used (`spa`, `wpa`, `kappa`) |
| `agreement_threshold` | θ applied during filtering |
| `consistent_fraction` | Fraction of J\* judgements that agreed on this item |
| `exported_at` | ISO timestamp of export |

In **Parquet** format, nested fields (`sampled_target_attributes`, `rubric`,
`student_scores`, `judge_set`) are serialised to JSON strings; all other fields are
native Parquet types.

---

## 8. Further Reading

| Document | What it covers |
|----------|---------------|
| [`docs/README/06-running.md`](README/06-running.md) | Complete running guide: phase modes, multi-role config, HuggingFace local models, cost estimation, use-case examples |
| [`docs/cli_reference.md`](cli_reference.md) | Every CLI subcommand with full option tables and exit codes |
| [`docs/developer_guide.md`](developer_guide.md) | Repository layout, module APIs, how to add a new provider interface or phase |
| [`docs/README/05-providers.md`](README/05-providers.md) | All 16 interfaces (incl. Bedrock/Vertex async batch), pricing tables, provider setup guides, `interface: auto` routing |
| [`docs/README/07-benchmarks.md`](README/07-benchmarks.md) | Benchmark datasets, `coeval ingest`, `interface: benchmark` virtual teacher, reproducing published results |
| [`docs/README/08-reports.md`](README/08-reports.md) | Analysis CLI reference, metrics formulas (ACR, RAR, Spearman ρ), programmatic API, calibration |
| [`benchmark/mixed.yaml`](../Runs/mixed/mixed.yaml) | Complete working config for the mixed benchmark experiment |
| [`benchmark/paper_dual_track.yaml`](../Runs/paper/paper_dual_track.yaml) | Full dual-track paper experiment config (10 SOTA models, Track A + Track B) |

---

*Generated for CoEval v0.3.0 — March 2026.*
