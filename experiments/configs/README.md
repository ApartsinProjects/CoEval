# Experiment Config Examples

This folder contains example YAML config files for use with the CoEval experiment runner.

## Files

### local_smoke_test.yaml
A self-contained smoke test using only HuggingFace models (no API keys required).
- 5 small HuggingFace models ranging from 135M to 1.5B parameters
- 2 evaluation tasks
- Static rubric (no LLM judge needed)
- Suitable for verifying a local installation end-to-end

### mixed_backend_test.yaml
A cross-backend comparison config using both OpenAI and HuggingFace models.
- 2 OpenAI models + 2 HuggingFace models
- 1 evaluation task
- Useful for comparing quality across providers on the same prompt

## Environment Variables

Configs that include OpenAI models require the `OPENAI_API_KEY` environment variable to be
set before running. HuggingFace models do not require an API key for public checkpoints.

```bash
export OPENAI_API_KEY="sk-..."
python -m experiments.runner --config experiments/configs/mixed_backend_test.yaml
```

## See Also

- [experiments/docs/running_experiments.md](../docs/running_experiments.md) — full config reference and usage guide
- [experiments/docs/spec_claude.md](../docs/spec_claude.md) — formal config schema (COEVAL-SPEC-001)
