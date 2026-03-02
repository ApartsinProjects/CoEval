# docs/ — CoEval Documentation

This directory contains the full documentation suite for CoEval.

## Section-by-Section Guide (`docs/README/`)

The [`README/`](README/) subdirectory splits the documentation into 13 focused, standalone sections:

| # | File | Contents |
|---|------|----------|
| 01 | [Overview](README/01-overview.md) | Problem space, solution approach, target audience, feature catalogue |
| 02 | [Installation](README/02-installation.md) | Requirements, pip install, optional extras, provider SDKs |
| 03 | [Quick Start](README/03-quick-start.md) | Three paths to first run, typical workflow |
| 04 | [Configuration](README/04-configuration.md) | Models, tasks, sampling, rubric, experiment settings, multi-role params |
| 05 | [Providers & Pricing](README/05-providers.md) | All 15 interfaces with auth, batch support, code examples, pricing tables |
| 06 | [Running Experiments](README/06-running.md) | Phase modes, quotas, batch, cost estimation, resuming, use-case examples |
| 07 | [Benchmark Datasets](README/07-benchmarks.md) | Pre-ingested datasets, `coeval ingest`, benchmark teachers, reproducing results |
| 08 | [Analytics & Reports](README/08-reports.md) | All 11 report types, metrics, data model, programmatic API, paper tables |
| 09 | [Resume & Recovery](README/09-recovery.md) | Checkpointing, `--continue`, `--resume`, repair workflow, decision tree |
| 10 | [Architecture](README/10-architecture.md) | Five-phase pipeline, phase details, role assignment, storage layout |
| 11 | [Testing](README/11-testing.md) | Running tests, coverage areas, CI setup |
| 12 | [Repository Layout](README/12-repository.md) | Annotated directory tree, key file index |
| 13 | [Documentation](README/13-documentation.md) | Full index with HTML examples gallery |

## Reference Documents

| File | Description |
|------|-------------|
| [cli_reference.md](cli_reference.md) | Complete CLI reference for all 11 `coeval` subcommands and flags |
| [developer_guide.md](developer_guide.md) | Architecture overview, contribution guidelines, and extension points |
| [tutorial.md](tutorial.md) | End-to-end walkthrough: from config to analysis report |

## Related

- [`examples/`](../examples/) — example experiment configs
- [`benchmark/`](../benchmark/) — benchmark configs and setup scripts
