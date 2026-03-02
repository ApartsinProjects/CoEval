# CLI Reference

[← Interfaces](07-interfaces.md) · [Cost Planning →](09-cost-control.md)

> **Full reference:** For complete flag tables, examples, and workflow patterns see [`docs/cli_reference.md`](../cli_reference.md).

---

All commands share the global syntax:

```
coeval <subcommand> [options]
```

Available subcommands: [`run`](#coeval-run) · [`probe`](#coeval-probe) · [`plan`](#coeval-plan) · [`status`](#coeval-status) · [`repair`](#coeval-repair) · [`describe`](#coeval-describe) · [`wizard`](#coeval-wizard) · [`generate`](#coeval-generate) · [`models`](#coeval-models) · [`ingest`](#coeval-ingest) · [`analyze`](#coeval-analyze)

---

## `coeval run`

Execute an evaluation experiment through all five pipeline phases.

```bash
coeval run --config PATH [options]
```

| Flag | Description |
|------|-------------|
| `--config PATH` | **Required.** Path to experiment YAML |
| `--continue` | Resume from last checkpoint |
| `--only-models M1,M2` | Restrict phases 3–5 to specific models |
| `--estimate-only` | Print cost estimate and exit |

**Exit codes:** `0` success · `1` config/validation error · `2` probe failure (abort mode)

---

## `coeval probe`

Test model availability before committing to a run; consumes no generation tokens.

```bash
coeval probe --config PATH [--keys PATH] [--probe-on-fail {abort|warn}]
```

| Flag | Description |
|------|-------------|
| `--config PATH` | **Required.** Path to experiment YAML |
| `--probe-on-fail {abort\|warn}` | Exit non-zero on failure, or warn only |
| `--keys PATH` | Provider key file |

**Exit codes:** `0` all available · `1` config error · `2` one or more unavailable (abort mode)

---

## `coeval plan`

Estimate cost and time before running; samples live API calls or uses token-count heuristics.

```bash
coeval plan --config PATH [--estimate-samples N] [--keys PATH]
```

| Flag | Description |
|------|-------------|
| `--config PATH` | **Required.** Path to experiment YAML |
| `--estimate-samples N` | Live sample calls per model (default: 2; `0` = heuristics only) |
| `--keys PATH` | Provider key file |

**Exit codes:** `0` success · `1` config error

---

## `coeval status`

Display experiment progress: phase artifact counts, pending batch jobs, and recent log errors.

```bash
coeval status --run PATH [--fetch-batches]
```

| Flag | Description |
|------|-------------|
| `--run PATH` | **Required.** Path to the experiment run folder |
| `--fetch-batches` | Poll provider APIs for batch job completion status |

**Exit codes:** `0` success · `1` run folder not found

---

## `coeval repair`

Scan JSONL files for invalid records and prepare corrupted runs for `--continue`.

```bash
coeval repair --run PATH [--dry-run] [--stats] [--phase N]
```

| Flag | Description |
|------|-------------|
| `--run PATH` | **Required.** Path to the experiment run folder |
| `--dry-run` | Report what would change without modifying files |
| `--stats` | Print a summary table of record counts per phase |
| `--phase N` | Restrict scan to a single phase (1–5) |

**Exit codes:** `0` success · `1` run folder not found

---

## `coeval describe`

Generate a self-contained HTML summary of an experiment config; no API calls made.

```bash
coeval describe --config PATH [--out PATH] [--no-open] [--keys PATH]
```

| Flag | Description |
|------|-------------|
| `--config PATH` | **Required.** Path to experiment YAML |
| `--out PATH` | Output HTML path (default: `{config_stem}_description.html` next to config) |
| `--no-open` | Suppress auto-opening the file in the browser |
| `--keys PATH` | Provider key file |

**Exit codes:** `0` success · `1` config error

> **Example output:** [`benchmark/education_description.html`](../../benchmark/education_description.html)

---

## `coeval wizard`

Interactive LLM-assisted configuration builder; produces a complete, ready-to-run YAML.

```bash
coeval wizard [--out PATH] [--model MODEL_ID] [--keys PATH]
```

| Flag | Description |
|------|-------------|
| `--out PATH` | Output YAML path (default: prompted interactively) |
| `--model MODEL_ID` | Force a specific model for the wizard session |
| `--keys PATH` | Provider key file |

**Exit codes:** `0` success · `1` error or cancelled

---

## `coeval generate`

Run Phases 1–2 and materialize all `auto`/`extend` placeholders into a fully static YAML.

```bash
coeval generate --config DRAFT --out DESIGN [--keys PATH]
```

| Flag | Description |
|------|-------------|
| `--config DRAFT` | **Required.** Draft config with `auto`/`extend` placeholders |
| `--out DESIGN` | **Required.** Output path for the materialized YAML |
| `--keys PATH` | Provider key file |

**Exit codes:** `0` success · `1` config error

---

## `coeval models`

List available text-generation models for configured providers.

```bash
coeval models [--providers LIST] [--verbose] [--keys PATH]
```

| Flag | Description |
|------|-------------|
| `--providers LIST` | Comma-separated provider names (default: all configured) |
| `--verbose` | Include context length, ownership, and additional metadata |
| `--keys PATH` | Provider key file |

**Exit codes:** `0` success · `1` error

---

## `coeval ingest`

Download and ingest benchmark datasets as Phase 3 virtual teacher data.

```bash
coeval ingest --run PATH --benchmarks NAME [NAME ...]
```

| Flag | Description |
|------|-------------|
| `--run PATH` | **Required.** Target experiment run folder |
| `--benchmarks NAME` | **Required.** One or more dataset names |

Supported datasets: `mmlu`, `hellaswag`, `truthfulqa`, `humaneval`, `medqa`, `gsm8k`

**Exit codes:** `0` success · `1` error

---

## `coeval analyze`

Generate analysis reports from a completed experiment run.

```bash
coeval analyze <report> --run PATH --out PATH [--format {html|excel|both}]
```

| Report | Description |
|--------|-------------|
| `complete-report` | Full Excel workbook with all evaluation data |
| `score-distribution` | Interactive HTML histogram of judge score distributions |
| `teacher-report` | Data coverage, diversity, and attribute balance |
| `judge-report` | Consistency, bias, and agreement with ground truth |
| `student-report` | Per-task scores, rankings, and percentile bands |
| `interaction-matrix` | Heatmap across teacher × student × judge combinations |
| `judge-consistency` | Inter-judge agreement (Spearman ρ, Kendall τ) |
| `coverage-summary` | Attribute and dimension coverage across the benchmark |
| `summary-report` | High-level experiment summary with key metrics |
| `robust-summary` | Outlier-robust score aggregation across ensemble members |
| `export-benchmark` | Export data in benchmark-compatible format |
| `all` | Generate all reports in one command |

**Exit codes:** `0` success · `1` error

---

[← Interfaces](07-interfaces.md) · [Cost Planning →](09-cost-control.md)
