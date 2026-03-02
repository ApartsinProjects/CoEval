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

---

## Environment Variables

| Variable | Used by | Purpose |
|----------|---------|---------|
| `OPENAI_API_KEY` | OpenAI models | Authentication for GPT models and Batch API |
| `ANTHROPIC_API_KEY` | Anthropic models | Authentication for Claude models and Batch API |
| `GEMINI_API_KEY` | Gemini models | Authentication for Gemini models |
| `GOOGLE_API_KEY` | Gemini models | Alternative to `GEMINI_API_KEY` |
| `HF_TOKEN` | Private HuggingFace models | Access token for gated / private repos |
| `HUGGINGFACE_HUB_TOKEN` | Private HuggingFace models | Alternative to `HF_TOKEN` |

Each key can also be set inline in the YAML using the model's `access_key` field, though
setting environment variables is recommended to avoid committing credentials to version control.

```bash
export OPENAI_API_KEY="sk-..."
export ANTHROPIC_API_KEY="sk-ant-..."
export GEMINI_API_KEY="AIza..."
coeval run --config experiments/configs/mixed_backend_test.yaml
```

---

## New Config Options (v0.3+)

### Probe configuration (`experiment` block)

```yaml
experiment:
  probe_mode: full       # full | resume | disable
  probe_on_fail: abort   # abort | warn
```

| Option | Values | Default | Description |
|--------|--------|---------|-------------|
| `probe_mode` | `full`, `resume`, `disable` | `full` | When to test model availability before starting the pipeline |
| `probe_on_fail` | `abort`, `warn` | `abort` | What to do if a model is unreachable |

- **`full`**: Probe every model in the config (default).
- **`resume`**: Probe only the models needed for phases that haven't been completed yet.
- **`disable`**: Skip the probe entirely (equivalent to the deprecated `--skip-probe` flag).
- **`abort`**: Halt the experiment if any model is unavailable.
- **`warn`**: Log a warning and continue (some later phases may fail).

### Cost/time estimation (`experiment` block)

```yaml
experiment:
  estimate_cost: true    # run estimation at the start of the experiment
  estimate_samples: 2    # number of sample calls per model (default: 2)
```

The estimator runs a small number of real API/inference calls, measures latency and
token counts, then extrapolates to the full experiment size using built-in pricing
tables. A `cost_estimate.json` file is written to the experiment folder and a
human-readable table is printed to the log. Use `--estimate-only` on the CLI to
run the estimator without executing the pipeline.

### Label accuracy (`tasks` block)

```yaml
tasks:
  - name: sentiment_classification
    ...
    target_attributes:
      sentiment: [positive, negative, neutral]
    label_attributes: [sentiment]   # ← new
```

When `label_attributes` is set, `experiments/label_eval.py` can compute exact-match
accuracy, per-class precision/recall/F1, and Hamming accuracy directly from Phase 3
datapoints and Phase 4 student responses — **without requiring an LLM judge** in
Phase 5. This is useful for classification and information-extraction benchmarks where
ground-truth labels are already embedded in the sampled target attributes.

---

## See Also

- [experiments/docs/running_experiments.md](../docs/running_experiments.md) — full config reference and usage guide
- [experiments/docs/spec_claude.md](../docs/spec_claude.md) — formal config schema (COEVAL-SPEC-001)
- [experiments/label_eval.py](../label_eval.py) — label accuracy module
- [experiments/interfaces/cost_estimator.py](../interfaces/cost_estimator.py) — cost/time estimation probe
- [experiments/interfaces/probe.py](../interfaces/probe.py) — model availability probe
