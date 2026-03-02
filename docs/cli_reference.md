# CoEval CLI Reference

Complete reference for all `coeval` command-line options.

---

## Global syntax

```
coeval <subcommand> [options]
```

Subcommands: [`run`](#coeval-run), [`probe`](#coeval-probe), [`plan`](#coeval-plan), [`status`](#coeval-status), [`repair`](#coeval-repair), [`describe`](#coeval-describe), [`wizard`](#coeval-wizard), [`generate`](#coeval-generate), [`models`](#coeval-models), [`ingest`](#coeval-ingest), [`analyze`](#coeval-analyze)

---

## Provider key file

Most subcommands that load a config accept a `--keys PATH` flag pointing at a YAML file with provider API keys.  This lets you store credentials in one place rather than repeating them per-experiment.

**Default location:** `~/.coeval/keys.yaml`  (or `COEVAL_KEYS_FILE` environment variable)

```yaml
# ~/.coeval/keys.yaml
providers:
  openai: sk-...
  anthropic: sk-ant-...
  gemini: AIza...
  huggingface: hf_...

  azure_openai:
    api_key: ...
    endpoint: https://my-resource.openai.azure.com/
    api_version: 2024-08-01-preview

  bedrock:
    access_key_id: AKIA...
    secret_access_key: ...
    region: us-east-1

  vertex:
    project: my-gcp-project
    location: us-central1
    service_account_key: /path/to/key.json   # optional; uses ADC if omitted
```

**Resolution order** (per model):
1. Model-level `access_key` in the experiment YAML
2. Provider key file (`--keys` or default path)
3. Standard environment variables (`OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, etc.)

#### `interface: auto`

Setting `interface: auto` on a model triggers automatic provider selection at config
load time. CoEval scans `benchmark/provider_pricing.yaml`'s `auto_routing` table and
selects the cheapest available provider for which credentials exist in `keys.yaml`.

```yaml
- name: deepseek-v3
  interface: auto
  parameters:
    model: deepseek/deepseek-chat
  roles: [student]
```

The resolved interface is logged at `DEBUG` level. To see which provider was selected
before running the experiment, use `coeval plan --config your.yaml`.

---

## `coeval run`

Execute an evaluation experiment.  Runs all five pipeline phases
(attribute_mapping → rubric_mapping → data_generation →
response_collection → evaluation) and writes results to the storage folder.

```
coeval run --config PATH [options]
```

### Required

| Option | Description |
|--------|-------------|
| `--config PATH` | Path to the YAML experiment configuration file. |

### Optional

| Option | Default | Description |
|--------|---------|-------------|
| `--continue` | off | Continue a previously interrupted experiment **in-place**. Reads `phases_completed` from `meta.json`, skips completed phases entirely, and resumes partial phases from the last saved item. Phases 1–2 use *Keep* mode (skip per-task files that exist); phases 3–5 use *Extend* mode (skip already-written JSONL records). |
| `--resume EXPERIMENT_ID` | — | Create a new experiment that copies Phase 1–2 artifacts from an existing experiment. Overrides `experiment.resume_from` in config. |
| `--only-models MODEL_IDS` | — | Comma-separated list of model IDs to activate. All others are skipped for phases 3–5. Useful for running OpenAI and HuggingFace models in parallel processes. Phase-completion markers are **not** written when this flag is set. |
| `--dry-run` | off | Validate the config and print the execution plan without making any LLM calls. |
| `--probe MODE` | `full` | Model availability probe mode. `full` — test all models; `resume` — test only models needed for remaining phases; `disable` — skip probe entirely. Overrides `experiment.probe_mode`. |
| `--probe-on-fail MODE` | `abort` | Action when a probed model is unavailable. `abort` — stop immediately; `warn` — log a warning and continue. Overrides `experiment.probe_on_fail`. |
| `--skip-probe` | off | *Deprecated.* Alias for `--probe disable`. |
| `--estimate-only` | off | Run the cost/time estimator, print the breakdown, write `cost_estimate.json`, and exit **without** starting any pipeline phases. When combined with `--continue`, estimates only remaining work. |
| `--estimate-samples N` | 2 | Number of sample LLM calls per model for latency calibration. `0` uses heuristics only. Overrides `experiment.estimate_samples`. |
| `--log-level LEVEL` | from config | Override the log level (`DEBUG`, `INFO`, `WARNING`, `ERROR`). |
| `--keys PATH` | `~/.coeval/keys.yaml` | Path to a provider key file (YAML). Credentials in this file act as fallbacks after model-level `access_key` values. |

### Exit codes

| Code | Meaning |
|------|---------|
| 0 | Experiment completed successfully. |
| 1 | Configuration error or unrecoverable pipeline failure. |

### Examples

```bash
# Fresh run
coeval run --config experiments/my_exp.yaml

# Dry-run to validate config
coeval run --config experiments/my_exp.yaml --dry-run

# Resume an interrupted run
coeval run --config experiments/my_exp.yaml --continue

# Estimate cost before running
coeval run --config experiments/my_exp.yaml --estimate-only --estimate-samples 0

# Estimate remaining cost for a partial run
coeval run --config experiments/my_exp.yaml --estimate-only --continue

# Run with only OpenAI models, skip probe
coeval run --config experiments/my_exp.yaml --only-models gpt-4o-mini,gpt-3.5-turbo --probe disable
```

---

## `coeval probe`

Test model availability without starting any experiment phases.

Runs the same pre-flight probe that `coeval run` executes, but exits
immediately after printing results.  Useful for verifying API keys and
model access before committing to a full run.

```
coeval probe --config PATH [options]
```

### Required

| Option | Description |
|--------|-------------|
| `--config PATH` | Path to the YAML experiment configuration file. |

### Optional

| Option | Default | Description |
|--------|---------|-------------|
| `--probe MODE` | from config (`full`) | Probe scope. `full` — test all models; `resume` — test only models needed for phases not yet completed; `disable` — skip probe (exits immediately). |
| `--probe-on-fail MODE` | from config (`abort`) | What to do when a model is unavailable. `abort` — exit with code 2; `warn` — print a warning and exit 0. |
| `--log-level LEVEL` | `INFO` | Console log level. |
| `--keys PATH` | `~/.coeval/keys.yaml` | Path to a provider key file (YAML). |

### Exit codes

| Code | Meaning |
|------|---------|
| 0 | All probed models are available (or `--probe-on-fail warn` with some failures). |
| 1 | Configuration error (bad YAML, validation failures). |
| 2 | One or more models unavailable and `--probe-on-fail abort`. |

> **Note:** Folder-existence validation (V-11 / V-14) is suppressed for `coeval probe`.
> The command can be run against any config regardless of whether the experiment
> folder already exists.

### Examples

```bash
# Test all models in the config
coeval probe --config experiments/my_exp.yaml

# Test only models needed for the remaining phases
coeval probe --config experiments/my_exp.yaml --probe resume

# Test with warn-on-fail (always exit 0)
coeval probe --config experiments/my_exp.yaml --probe-on-fail warn
```

---

## `coeval plan`

Estimate cost and runtime without starting any experiment phases.

Makes a small number of sample API calls per model (configurable) to
calibrate latency, then extrapolates to the full experiment size.  Results
are printed as a table and written to `cost_estimate.json` in the
experiment folder (if it exists).

```
coeval plan --config PATH [options]
```

### Required

| Option | Description |
|--------|-------------|
| `--config PATH` | Path to the YAML experiment configuration file. |

### Optional

| Option | Default | Description |
|--------|---------|-------------|
| `--continue` | off | Estimate only the **remaining** work for an already-started experiment. Reads existing phase artifacts from the storage folder and subtracts completed items from the full budget. The experiment folder must already exist. |
| `--estimate-samples N` | from config (2) | Number of sample LLM calls per model for latency calibration. `0` uses heuristics only (no real API calls). |
| `--log-level LEVEL` | `INFO` | Console log level. |
| `--keys PATH` | `~/.coeval/keys.yaml` | Path to a provider key file (YAML). |

> **Note:** Folder-existence validation is suppressed when `--continue` is **not** set,
> so `coeval plan` can be run against a new config before the experiment folder exists.

### Examples

```bash
# Estimate a fresh experiment (heuristics only, no API calls)
coeval plan --config experiments/my_exp.yaml --estimate-samples 0

# Estimate with 3 calibration calls per model
coeval plan --config experiments/my_exp.yaml --estimate-samples 3

# Estimate remaining work for a partial run
coeval plan --config experiments/my_exp.yaml --continue --estimate-samples 0
```

---

## `coeval status`

Show experiment progress and pending batch job status.

Reads the experiment folder directly (no config file required) and prints:

1. **Metadata** — experiment ID, status, creation time, completed/in-progress phases.
2. **Phase artifacts** — file counts and JSONL record counts per phase.
3. **Pending batch jobs** — batch IDs, provider, phase, request count, and last-known status from `pending_batches.json`.
4. **Recent errors** — last 10 entries from `run_errors.jsonl`.

```
coeval status --run PATH [options]
```

### Required

| Option | Description |
|--------|-------------|
| `--run PATH` | Path to the experiment folder (the EES run folder, e.g. `benchmark/runs/my-exp`). |

### Optional

| Option | Default | Description |
|--------|---------|-------------|
| `--fetch-batches` | off | Poll the provider APIs (OpenAI / Anthropic) for each pending batch job. For completed jobs, download and apply the results to the experiment storage. Phase 4 (response_collection) and Phase 5 (evaluation) results are applied automatically. Phase 3 (data_generation) results cannot be reconstructed automatically — the command reports their status and instructs the user to rerun with `--continue`. Uses `OPENAI_API_KEY` / `ANTHROPIC_API_KEY` environment variables. |

### Exit codes

| Code | Meaning |
|------|---------|
| 0 | Status printed successfully. |
| 1 | Experiment folder not found or missing `meta.json`. |

### Batch tracking

When `coeval run` submits a batch job (OpenAI Batch API or Anthropic Message
Batches API), it writes a record to `pending_batches.json` inside the
experiment folder **before** polling begins.  This ensures that if the
process is interrupted while waiting for results, the batch job ID and the
mapping from compact request IDs to experiment keys are preserved.

`coeval status` reads this file and shows the current status of all tracked
batches.  With `--fetch-batches`, it polls the live API and applies
completed results to the experiment storage, then removes the entries from
`pending_batches.json`.  After applying results, run `coeval run --config
<cfg> --continue` to complete any remaining work.

### Examples

```bash
# Show current experiment status
coeval status --run benchmark/runs/medium-benchmark-v1

# Check for and apply any completed batch results
coeval status --run benchmark/runs/medium-benchmark-v1 --fetch-batches
```

---

## `coeval repair`

Scan Phase 3, 4, and 5 JSONL files for two classes of problems and prepare
the minimum set of re-generation needed — no valid data is discarded.

**Class 1 — Invalid records** (exist but have empty/null required fields):

| Phase | File suffix | Invalid when … |
|-------|-------------|----------------|
| 3 — datapoints | `.datapoints.jsonl` | `reference_response` is empty/null, or `status='failed'` |
| 4 — responses | `.responses.jsonl` | `response` is empty/null, or `status='failed'` |
| 5 — evaluations | `.evaluations.jsonl` | `scores` is empty/all-null, or `status='failed'` |

Any JSONL line that cannot be parsed as JSON is also reported.
These are marked `status='failed'` in-place so that `--continue` Extend mode
regenerates them (and only them) on the next run.

**Class 2 — Coverage gaps** (records expected but entirely missing):

Cross-references upstream phases to find files with fewer records than
expected: Phase 4 gaps compare response JSONL vs Phase 3 datapoint IDs;
Phase 5 gaps compare evaluation JSONL vs Phase 4 response IDs.  When gaps
are found, the affected phase is **removed from `phases_completed`** in
`meta.json` so that `--continue` re-runs it in Extend mode, which skips
already-present records and generates only the missing ones.

> **Typical cause:** HuggingFace models running out of memory or crashing
> mid-phase, leaving large gaps in evaluation or response files.

**Repair workflow**

```bash
# Step 1 — scan only (read-only audit, nothing modified)
coeval repair --run benchmark/runs/my-exp --dry-run

# Step 2 — repair: mark invalid records + re-open gapped phases in meta.json
coeval repair --run benchmark/runs/my-exp

# Step 3 — re-generate the missing/failed records (only those)
coeval run --config my-experiment.yaml --continue
```

> **Note:** `coeval repair` never deletes records or clears entire phases.
> All valid, present data is fully preserved.

### Required

| Flag | Description |
|------|-------------|
| `--run PATH` | Path to the experiment folder (e.g. `benchmark/runs/my-exp`) |

### Optional

| Flag | Default | Description |
|------|---------|-------------|
| `--dry-run` | off | Scan and print a report without modifying any files. Safe to run at any time. |
| `--stats` | off | Print a compact per-phase summary table (valid / invalid / gap counts) and exit. No files are modified. |
| `--examples N` | 5 | Number of example records to show per issue group. Use `0` to suppress examples entirely; `-1` to show all. |
| `--phase PHASE` | all | Restrict scan and report to a single phase (`3`, `4`, or `5`). |
| `--breakdown` | off | Show a per-file breakdown table with valid/invalid/gap counts for every JSONL file. Can be combined with `--stats`. |
| `--show-valid N` | 0 | Show *N* example **valid** records per phase for spot-checking data quality (0 = disabled). |

### Exit codes

| Code | Meaning |
|------|---------|
| 0 | Scan complete (0 or more issues found; files patched if not `--dry-run`) |
| 1 | Fatal error (experiment folder not found, no `meta.json`, etc.) |

### Diagnostic flag guide

#### `--stats` — phase-level summary

Prints a single compact table that gives a quick health check across all
three phases:

```
Phase    Valid   Invalid    Gaps
phase3    1600         0       0
phase4    7987         0       0
phase5    7978         9       0
```

Useful as a first pass to see whether any problems exist.  Combine with
`--phase` to focus on one phase.

#### `--breakdown` — per-file detail

Expands the phase-level view into a row per JSONL file, showing how valid,
invalid, and gap counts are distributed across individual (task, teacher,
model) combinations.  Files with any invalid or gap records are highlighted
with a `!` indicator.  Combine with `--stats` for the full picture:

```bash
coeval repair --run benchmark/runs/my-exp --stats --breakdown
```

#### `--examples N` — control example verbosity

By default, the detailed report shows 5 examples per issue group.  Set a
higher number to see more context, or `0` to suppress examples and keep the
output compact:

```bash
# Verbose: 10 examples per group
coeval repair --run benchmark/runs/my-exp --dry-run --examples 10

# Silent: counts only, no records shown
coeval repair --run benchmark/runs/my-exp --dry-run --examples 0
```

#### `--phase PHASE` — focus on one phase

Filter all output to a single phase.  Useful when you know the problem is
confined to evaluation (phase 5) or responses (phase 4):

```bash
# Investigate only phase 5 failures in detail
coeval repair --run benchmark/runs/my-exp --phase 5 --examples 20 --dry-run
```

#### `--show-valid N` — spot-check good records

Samples up to *N* valid records per phase and prints their key fields
(`reference_response` for phase 3, `response` for phase 4, `scores` dict
for phase 5).  Helps verify that data quality is acceptable even among
records that passed validation, without opening the raw JSONL files:

```bash
coeval repair --run benchmark/runs/my-exp --show-valid 3 --dry-run
```

### Examples

```bash
# Quick health check: phase summary table
coeval repair --run benchmark/runs/my-exp --stats

# Full health check: phase summary + per-file breakdown
coeval repair --run benchmark/runs/my-exp --stats --breakdown

# Audit without touching files, show 10 examples per issue group
coeval repair --run benchmark/runs/my-exp --dry-run --examples 10

# Focus on phase 5 only, with spot-check of valid records
coeval repair --run benchmark/runs/my-exp --phase 5 --show-valid 3 --dry-run

# Repair: mark invalid records and update meta.json (no --dry-run)
coeval repair --run benchmark/runs/my-exp

# Regenerate only the repaired records
coeval run --config benchmark/medium-benchmark-v1.yaml --continue
```

---

## `coeval describe`

Generate a self-contained HTML summary of an experiment configuration.

Reads a YAML config and writes a styled HTML page showing all models, tasks,
rubrics, phase plan, estimated call budget, batch settings, and per-model
quotas.  No LLM API calls are made and the experiment folder does not need to
exist.

```
coeval describe --config PATH [options]
```

### Options

| Flag | Default | Description |
|------|---------|-------------|
| `--config PATH` | *(required)* | Path to the YAML configuration file. |
| `--out PATH` | `<stem>_description.html` | Output HTML file path. Defaults to `<config_stem>_description.html` placed next to the config file. |
| `--no-open` | off | Do not open the HTML file in the default browser after writing. |
| `--keys PATH` | auto-discovered | Path to a provider key file (YAML). |

### HTML page contents

- **Stats bar** — total models, teacher/student/judge counts, estimated LLM calls.
- **Models table** — interface icon, model ID, colour-coded role badges, base parameters, per-role overrides.
- **Tasks** — collapsible cards showing description, output format, target and nuanced attributes, rubric criteria, and sampling configuration.
- **Phase plan table** — mode badge per phase (New/Extend/Keep), estimated call count, batch API indicators.
- **Batch & quota** — active batch providers/phases and per-model call ceilings.

> **Note:** Folder-existence validation (V-11 / V-14) is suppressed — `coeval describe` works on brand-new configs before the experiment folder is created.

### Examples

```bash
# Write mixed_description.html next to mixed.yaml and open in browser
coeval describe --config benchmark/mixed.yaml

# Write to a specific path without opening the browser
coeval describe --config benchmark/mixed.yaml --out docs/mixed_overview.html --no-open
```

---

## `coeval wizard`

Interactive LLM-assisted experiment configuration wizard.

Guides you through defining an evaluation experiment via a conversational
interface.  Describe your goal in plain English, answer a few clarifying
questions, and the wizard generates a complete, valid YAML configuration
ready for `coeval run`.

```
coeval wizard [options]
```

### How it works

1. **Describe your goal** — Type a free-text description of what you want to evaluate (e.g. *"Compare how different LLMs summarize scientific papers across different domains and difficulty levels"*).
2. **Answer clarifying questions** — Experiment ID, storage folder, number of items per task, preferred models.
3. **Review the generated YAML** — The wizard calls an LLM to produce a complete configuration and displays it for review.
4. **Refine interactively** — Type any requested changes in plain English (e.g. *"add a third task for question answering"*, *"change the judge model to gpt-4o"*). Repeat until satisfied.
5. **Save** — The final config is written to the path you specify, ready for use.

### Optional

| Option | Default | Description |
|--------|---------|-------------|
| `--out PATH` | interactive | Output path for the generated YAML config. If omitted, the wizard asks interactively (or prints to stdout if left empty). |
| `--model MODEL_ID` | auto-selected | LLM model to use for config generation. Defaults to the best available from the key file: OpenAI → Anthropic → Gemini → OpenRouter. |
| `--keys PATH` | `~/.coeval/keys.yaml` | Path to a provider key file (YAML). |

### Provider selection for generation

The wizard automatically selects the best available generation model in this order:

1. **OpenAI** — `gpt-4o-mini` (requires `OPENAI_API_KEY` or `providers.openai` in key file)
2. **Anthropic** — `claude-3-5-haiku-20241022`
3. **Gemini** — `gemini-2.0-flash`
4. **OpenRouter** — `openai/gpt-4o-mini`

Use `--model` to override, e.g. `--model gpt-4o` or `--model claude-3-5-sonnet-20241022`.

### After the wizard

```bash
# Verify model access
coeval probe --config my-experiment.yaml

# Estimate cost before running
coeval plan --config my-experiment.yaml --estimate-samples 0

# Run the experiment
coeval run --config my-experiment.yaml
```

### Examples

```bash
# Launch wizard interactively (save path prompted at end)
coeval wizard

# Save directly to a file
coeval wizard --out experiments/summarization-eval.yaml

# Use a specific generation model
coeval wizard --out experiments/my-eval.yaml --model gpt-4o

# Use a custom key file
coeval wizard --out experiments/my-eval.yaml --keys ~/.coeval/prod-keys.yaml
```

---

## `coeval generate`

Run phases 1–2 (attribute mapping + rubric mapping) in a temporary staging
directory and write a **materialized** YAML configuration where all `auto` /
`complete` / `extend` placeholders are replaced by generated static values.

This decouples the *design* step (teacher generates attributes and rubric)
from the *execution* step (`coeval run`), allowing human review and editing
between them.

```
coeval generate --config PATH --out PATH [options]
```

### Workflow

```bash
# Step 1 — generate attributes and rubric
coeval generate --config draft.yaml --out design.yaml

# Step 2 — review and edit design.yaml (attributes and rubric are now static lists)

# Step 3 — run the full pipeline from the materialized design
coeval run --config design.yaml
```

### Required

| Option | Description |
|--------|-------------|
| `--config PATH` | Path to the draft YAML configuration file. |
| `--out PATH` | Output path for the materialized YAML design file. |

### Optional

| Option | Default | Description |
|--------|---------|-------------|
| `--probe MODE` | `full` | Model availability probe mode before generation. `full` — test all teacher models; `disable` — skip probe. |
| `--probe-on-fail MODE` | `abort` | What to do when a probed model is unavailable. |
| `--log-level LEVEL` | `INFO` | Console log level. |
| `--keys PATH` | `~/.coeval/keys.yaml` | Path to a provider key file (YAML). |

### Output YAML

The output file is valid YAML with a comment header documenting what changed:

```yaml
# Generated by: coeval generate --config draft.yaml --out design.yaml
# Generated at: 2026-02-28T12:00:00Z
#
# Changes from source config:
#   [task1] target_attributes: 'auto' → {tone(3), urgency(2)}
#   [task1] rubric: 'auto' → 2 factors: ['tone', 'urgency']
#
experiment:
  id: my-experiment
  ...
```

### Exit codes

| Code | Meaning |
|------|---------|
| 0 | Design file written successfully. |
| 1 | Configuration error or phase 1/2 failure. |

### Examples

```bash
# Generate with default probe
coeval generate --config draft.yaml --out design.yaml

# Skip probe (models already known to be available)
coeval generate --config draft.yaml --out design.yaml --probe disable

# Use a custom key file
coeval generate --config draft.yaml --out design.yaml --keys ~/.coeval/prod-keys.yaml
```

---

## `coeval models`

List available text-generation models from each configured provider.

Queries each provider's model-listing endpoint using the resolved credentials
(provider key file → environment variables).  Useful for verifying which models
are accessible before writing an experiment config.

```
coeval models [options]
```

### Optional

| Option | Default | Description |
|--------|---------|-------------|
| `--providers LIST` | all configured | Comma-separated list of provider names to query (e.g. `openai,anthropic`). Providers without resolved credentials are silently skipped. |
| `--verbose` | off | Show additional model details (context window, ownership tier, etc.) where available. |
| `--keys PATH` | `~/.coeval/keys.yaml` | Path to a provider key file (YAML). |

### Supported providers

| Provider name | Auth env var(s) |
|---------------|-----------------|
| `openai` | `OPENAI_API_KEY` |
| `anthropic` | `ANTHROPIC_API_KEY` |
| `gemini` | `GEMINI_API_KEY` or `GOOGLE_API_KEY` |
| `azure_openai` | `AZURE_OPENAI_API_KEY` + `AZURE_OPENAI_ENDPOINT` |
| `bedrock` | `AWS_ACCESS_KEY_ID` + `AWS_SECRET_ACCESS_KEY` + `AWS_DEFAULT_REGION` |
| `vertex` | `GOOGLE_CLOUD_PROJECT` (+ ADC or `GOOGLE_APPLICATION_CREDENTIALS`) |
| `huggingface` | `HF_TOKEN` or `HUGGINGFACE_HUB_TOKEN` |

### Exit codes

| Code | Meaning |
|------|---------|
| 0 | Always exits 0 (errors per-provider are printed inline). |

### Examples

```bash
# List models from all providers with available credentials
coeval models

# List only OpenAI and Anthropic models
coeval models --providers openai,anthropic

# Use a specific key file
coeval models --keys ~/.coeval/prod-keys.yaml

# Show verbose details
coeval models --providers openai --verbose
```

---

## `coeval ingest`

Inject a downloaded standard benchmark into an existing experiment run as a virtual teacher model.

```
coeval ingest --run PATH --benchmarks NAME [NAME ...] [options]
```

After ingesting, resume the experiment with `coeval run --config PATH/config.yaml --continue`
to run Phases 4–5 (response collection and evaluation) on the new teacher.

### Options

| Flag | Description |
|------|-------------|
| `--run PATH` | Path to an existing EES run folder (must contain `meta.json` and `config.yaml`). |
| `--benchmarks NAME [NAME ...]` | One or more benchmark names to ingest. Supported: `mmlu`, `hellaswag`, `truthfulqa`, `humaneval`, `medqa`, `gsm8k`. |
| `--data-dir PATH` | Root directory of downloaded benchmark data (default: `./stdbenchmarks/data`). |
| `--split SPLIT` | Dataset split to load (default: adapter's `default_split`, e.g. `test` or `validation`). |
| `--limit N` | Ingest at most N datapoints per benchmark (useful for quick tests). |
| `--task-name NAME` | Override the task name written to the EES run. |
| `--verbose` | Print progress every 100 items. |

### Benchmark support

| Benchmark | Category | Task type | Label eval? |
|-----------|----------|-----------|-------------|
| `mmlu` | General | Multiple-choice (57 subjects) | Yes — exact match on `correct_answer` |
| `hellaswag` | General | Multiple-choice (commonsense) | Yes — exact match on `correct_answer` |
| `truthfulqa` | General | Open-ended factuality | No — judge required |
| `humaneval` | Code | Python function synthesis | No — judge required |
| `medqa` | Medical | USMLE-style MCQ | Yes — exact match on `correct_answer` |
| `gsm8k` | Math | Arithmetic word problems | Yes — exact match on `answer` |

### Download benchmarks first

```bash
python stdbenchmarks/download_benchmarks.py --benchmarks mmlu hellaswag gsm8k
```

### Workflow

```bash
# 1. Download benchmarks
python stdbenchmarks/download_benchmarks.py --benchmarks mmlu

# 2. Ingest into an existing run
coeval ingest --run benchmark/runs/my-exp --benchmarks mmlu --limit 200

# 3. Resume the experiment (Phases 4–5 only for the new teacher)
coeval run --config benchmark/runs/my-exp/config.yaml --continue
```

The ingest command is **idempotent**: re-running it skips items already written.
The virtual teacher model is named `<benchmark>-benchmark` (e.g. `mmlu-benchmark`).

---

## `coeval analyze`

Analyze an experiment folder and generate reports.

```
coeval analyze <subcommand> --run PATH --out PATH [options]
```

### Subcommands

| Subcommand | Output | Description |
|------------|--------|-------------|
| `complete-report` | Excel | Workbook with all slice and aggregate data. |
| `score-distribution` | HTML | Score distribution by aspect, model, and attribute. |
| `teacher-report` | HTML | Teacher model differentiation scores. |
| `judge-report` | HTML | Judge agreement and reliability scores. |
| `student-report` | HTML | Student model performance report. |
| `interaction-matrix` | HTML | Teacher–student interaction heatmap. |
| `judge-consistency` | HTML | Within-judge consistency analysis. |
| `coverage-summary` | HTML | EES artifact coverage and error breakdown. |
| `summary-report` | HTML | Interactive multi-view dashboard (teacher / judge / student). |
| `export-benchmark` | JSONL/Parquet/HF | Export benchmark dataset suitable for publishing. |
| `all` | mixed | Generate all HTML reports and Excel into subdirectories (excludes `robust-summary`). |
| `robust-summary` | HTML | *(Advanced)* Robust student ranking with filtered datapoints. Not included in `all`. |

### Common options

| Option | Default | Description |
|--------|---------|-------------|
| `--run PATH` | (required) | Path to the EES experiment folder. |
| `--out PATH` | (required) | Output path (file for Excel/JSONL; folder for HTML/`all`). |
| `--partial-ok` | off | Allow analysis on in-progress experiments without a warning. |
| `--log-level LEVEL` | `INFO` | Log level. |

### Robust filtering options

Applied to `robust-summary` and `export-benchmark`:

| Option | Default | Description |
|--------|---------|-------------|
| `--judge-selection` | `top_half` | Judge selection strategy (`top_half` or `all`). |
| `--agreement-metric` | `spa` | Agreement metric for judge ranking (`spa`, `wpa`, `kappa`). |
| `--agreement-threshold` | `1.0` | Minimum judge-consistency fraction θ. |
| `--teacher-score-formula` | `v1` | Teacher score formula for T* selection (`v1`, `s2`, `r3`). |

### Export options

Applied to `export-benchmark` only:

| Option | Default | Description |
|--------|---------|-------------|
| `--benchmark-format` | `jsonl` | Output format: `jsonl`, `parquet`, or `huggingface`. |
| `--dataset-name` | *(exp id)* | Dataset name embedded in the HuggingFace dataset card. |
| `--author` | — | Author/organisation for the dataset card (e.g. `my-org`). |
| `--include-metadata` | on | Embed rubric, attribute map, evaluation model info, and suggested prompts in the export. |

### Examples

```bash
# Generate all HTML reports + Excel
coeval analyze all --run benchmark/runs/my-exp --out benchmark/runs/my-exp/reports

# Generate Excel workbook only
coeval analyze complete-report --run benchmark/runs/my-exp --out my-exp-results.xlsx

# Export benchmark dataset as HuggingFace-ready directory (Parquet + dataset card)
coeval analyze export-benchmark \
    --run benchmark/runs/my-exp \
    --out my-exp-hf-dataset/ \
    --benchmark-format huggingface \
    --dataset-name "my-org/my-benchmark" \
    --author "My Org" \
    --judge-selection top_half \
    --agreement-threshold 0.8

# Export as plain JSONL (no HF card)
coeval analyze export-benchmark \
    --run benchmark/runs/my-exp \
    --out my-exp-benchmark.jsonl \
    --benchmark-format jsonl

# Advanced: robust student ranking with custom thresholds (not part of 'all')
coeval analyze robust-summary \
    --run benchmark/runs/my-exp \
    --out benchmark/runs/my-exp/reports/robust_summary \
    --agreement-threshold 0.8 \
    --teacher-score-formula s2
```

---

## Typical workflows

### Quick start with the wizard

```bash
# 1. Launch the wizard — describe your goal, pick models, get a YAML
coeval wizard --out experiments/my-eval.yaml

# 2. Preview cost and verify model access
coeval plan  --config experiments/my-eval.yaml --estimate-samples 0
coeval probe --config experiments/my-eval.yaml

# 3. Run the experiment
coeval run --config experiments/my-eval.yaml

# 4. Analyse results
coeval analyze all \
    --run experiments/runs/my-eval \
    --out experiments/runs/my-eval/reports
```

### Two-step workflow (generate then run)

```bash
# 1. Generate design: run phases 1–2 and write a materialized YAML
coeval generate --config draft.yaml --out design.yaml

# 2. Review / edit design.yaml (attributes and rubric are now static lists)

# 3. Validate and estimate cost
coeval plan  --config design.yaml --estimate-samples 0
coeval probe --config design.yaml

# 4. Run the full experiment from the materialized design
coeval run   --config design.yaml

# 5. Analyse results
coeval analyze all \
    --run experiments/runs/my-exp \
    --out experiments/runs/my-exp/reports
```

### Fresh experiment (single-step)

```bash
# 1. Validate and estimate cost
coeval plan  --config experiments/my_exp.yaml --estimate-samples 0
coeval probe --config experiments/my_exp.yaml

# 2. Run the experiment (phases 1–2 generate inline)
coeval run   --config experiments/my_exp.yaml

# 3. Analyse results
coeval analyze all \
    --run experiments/runs/my-exp \
    --out experiments/runs/my-exp/reports
```

### Resume after interruption

```bash
# Check what was already done and whether any batch jobs completed
coeval status --run experiments/runs/my-exp --fetch-batches

# Resume from where it left off
coeval run --config experiments/my_exp.yaml --continue

# Estimate remaining cost before resuming
coeval plan --config experiments/my_exp.yaml --continue --estimate-samples 0
```

### Diagnose and repair a failed experiment

```bash
# 1. Quick health check — phase-level summary table
coeval repair --run benchmark/runs/my-exp --stats

# 2. Full audit — per-phase + per-file breakdown, no changes made
coeval repair --run benchmark/runs/my-exp --stats --breakdown --dry-run

# 3. Investigate specific failures in detail
coeval repair --run benchmark/runs/my-exp --phase 5 --examples 10 --dry-run

# 4. Spot-check valid records to verify data quality
coeval repair --run benchmark/runs/my-exp --show-valid 3 --dry-run

# 5. Apply repair: mark invalid records as failed, reopen gapped phases
coeval repair --run benchmark/runs/my-exp

# 6. Regenerate only the marked/missing records
coeval run --config benchmark/my-exp.yaml --continue

# 7. Confirm the experiment is now clean
coeval repair --run benchmark/runs/my-exp --stats
```

### Discover available models

```bash
# List all models accessible with current credentials
coeval models

# List only specific providers
coeval models --providers openai,anthropic --verbose

# Use a custom key file
coeval models --keys ~/.coeval/staging-keys.yaml
```

### Parallel model runs

```bash
# Run OpenAI models in one terminal
coeval run --config experiments/my_exp.yaml --continue \
           --only-models gpt-4o-mini,gpt-3.5-turbo \
           --probe disable &

# Run HuggingFace models in another (CPU-only, slower)
coeval run --config experiments/my_exp.yaml --continue \
           --only-models smollm2-1b7 \
           --probe disable
```

---

## Environment variables

| Variable | Used by |
|----------|---------|
| `OPENAI_API_KEY` | OpenAI models and batch jobs |
| `ANTHROPIC_API_KEY` | Anthropic models and batch jobs |
| `GEMINI_API_KEY` / `GOOGLE_API_KEY` | Gemini models |
| `HF_TOKEN` / `HUGGINGFACE_HUB_TOKEN` | HuggingFace models |

API keys can also be set per-model in the YAML config under
`models[*].access_key`.  The environment variable is used as a fallback.
