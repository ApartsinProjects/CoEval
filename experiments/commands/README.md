# experiments/commands/ — CLI Subcommand Implementations

This directory contains the implementation modules for each `coeval` CLI subcommand. The CLI entry point is [`experiments/cli.py`](../cli.py), which dispatches to these modules.

## Subcommands

| File | Subcommand | Description |
|------|-----------|-------------|
| [`probe_cmd.py`](probe_cmd.py) | `coeval probe` | Test model availability before running an experiment |
| [`plan_cmd.py`](plan_cmd.py) | `coeval plan` | Estimate API cost and wall-clock time without running |
| [`status_cmd.py`](status_cmd.py) | `coeval status` | Show live progress dashboard; fetch completed batches |
| [`generate_cmd.py`](generate_cmd.py) | `coeval generate` | Materialize auto-generated placeholders in a draft config to a final YAML |
| [`models_cmd.py`](models_cmd.py) | `coeval models` | List available models from one or more providers |
| [`describe_cmd.py`](describe_cmd.py) | `coeval describe` | Generate a self-contained HTML summary of an experiment config |
| [`ingest_cmd.py`](ingest_cmd.py) | `coeval ingest` | Ingest a downloaded standard benchmark into an EES run folder |
| [`repair_cmd.py`](repair_cmd.py) | `coeval repair` | Repair or patch artifacts in an existing run folder |
| [`wizard_cmd.py`](wizard_cmd.py) | `coeval wizard` | Interactive wizard to scaffold a new experiment config |

## Quick Reference

```bash
# Probe model availability
coeval probe --config my_experiment.yaml

# Estimate cost (no API calls made)
coeval plan --config my_experiment.yaml

# Run experiment
coeval run --config my_experiment.yaml

# Resume interrupted run
coeval run --config my_experiment.yaml --continue

# Check progress and fetch batch results
coeval status --run benchmark/runs/my-experiment-v1

# List available models
coeval models --providers openai anthropic gemini

# Generate HTML config summary (no LLM calls)
coeval describe --config my_experiment.yaml

# Ingest a downloaded benchmark dataset
coeval ingest --run benchmark/runs/my-run --benchmark mmlu
```

## Related

- [`experiments/cli.py`](../cli.py) — CLI entry point and argument parsing
- [`docs/cli_reference.md`](../../docs/cli_reference.md) — complete CLI reference with all flags
- [`manuals/01_running_experiments.md`](../../manuals/01_running_experiments.md) — running experiments guide
