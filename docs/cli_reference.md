# CoEval CLI Reference

Complete reference for all `coeval` command-line options.

---

## Global syntax

```
coeval <subcommand> [options]
```

Subcommands: [`run`](#coeval-run), [`probe`](#coeval-probe), [`plan`](#coeval-plan), [`status`](#coeval-status), [`repair`](#coeval-repair), [`generate`](#coeval-generate), [`models`](#coeval-models), [`analyze`](#coeval-analyze)

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

| Flag | Description |
|------|-------------|
| `--dry-run` | Scan and print a report without modifying any files |

### Exit codes

| Code | Meaning |
|------|---------|
| 0 | Scan complete (0 or more issues found; files patched if not `--dry-run`) |
| 1 | Fatal error (experiment folder not found, no `meta.json`, etc.) |

### Examples

```bash
# Audit a completed experiment without touching files
coeval repair --run benchmark/runs/medium-benchmark-v1 --dry-run

# Mark any invalid records and prepare for --continue
coeval repair --run benchmark/runs/medium-benchmark-v1

# Regenerate only the repaired records
coeval run --config benchmark/medium-benchmark-v1.yaml --continue
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
| `robust-summary` | HTML | Robust student ranking with filtered datapoints. |
| `export-benchmark` | JSONL/Parquet | Export robust benchmark datapoints. |
| `all` | mixed | Generate all HTML reports and Excel into subdirectories. |

### Common options

| Option | Default | Description |
|--------|---------|-------------|
| `--run PATH` | (required) | Path to the EES experiment folder. |
| `--out PATH` | (required) | Output path (file for Excel/JSONL; folder for HTML/`all`). |
| `--partial-ok` | off | Allow analysis on in-progress experiments without a warning. |
| `--log-level LEVEL` | `INFO` | Log level. |

### Robust filtering options

Applied to `robust-summary`, `export-benchmark`, and `all`:

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
| `--benchmark-format` | `jsonl` | Output format (`jsonl` or `parquet`). |

### Examples

```bash
# Generate all HTML reports
coeval analyze all --run benchmark/runs/my-exp --out benchmark/runs/my-exp/reports

# Generate Excel workbook
coeval analyze complete-report --run benchmark/runs/my-exp --out my-exp-results.xlsx

# Export robust benchmark datapoints as Parquet
coeval analyze export-benchmark \
    --run benchmark/runs/my-exp \
    --out my-exp-benchmark.parquet \
    --benchmark-format parquet \
    --judge-selection top_half \
    --agreement-threshold 0.8
```

---

## Typical workflows

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
