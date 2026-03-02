# Quick Start

[← Installation](02-installation.md) · [Configuration →](04-configuration.md)

---

## Option A — Cloud Models (5 minutes)

### 1. Add your API keys

Create `~/.coeval/keys.yaml` with at least one provider:

```yaml
providers:
  openai:     sk-...
  anthropic:  sk-ant-...
  gemini:     AIza...
  openrouter: sk-or-v1-...
```

CoEval resolves credentials automatically in priority order:
`model.access_key` → `keys.yaml` → environment variable.

### 2. Probe all models

Verify every model is reachable before spending anything. This uses model listing endpoints — no generation tokens consumed:

```bash
coeval probe --config examples/local_smoke_test.yaml
```

Expected output:
```
============================================================
Probe Results  (mode='full', on_fail='abort')
============================================================
  gpt-4o-mini    [OK]
  gpt-3.5-turbo  [OK]
  ...
============================================================
Total: N available, 0 unavailable
```

### 3. Estimate cost

Get an itemized cost breakdown before committing:

```bash
coeval plan --config examples/local_smoke_test.yaml
```

### 4. Preview the experiment design

Generate a self-contained HTML summary for review:

```bash
coeval describe --config examples/local_smoke_test.yaml
```

### 5. Run the experiment

```bash
coeval run --config examples/local_smoke_test.yaml
```

### 6. Analyze the results

```bash
coeval analyze all \
    --run ./eval_runs/local-smoke-test-v2 \
    --out ./eval_runs/local-smoke-test-v2/reports
```

---

## Option B — Real Benchmark Data (~$0.02)

Use pre-ingested real datasets (XSum, CodeSearchNet, AESLC, WikiTableQuestions) as virtual teachers — zero Phase 3 LLM calls, then evaluate with GPT-4o-mini and GPT-3.5-turbo.

```bash
# Step 1: Ingest the four benchmark datasets (one-time setup)
python -m benchmark.setup_mixed

# Step 2: Run Phases 4–5 with OpenAI Batch API
coeval run --config benchmark/mixed.yaml --continue

# Step 3: Analyze
coeval analyze all \
    --run ./eval_runs/mixed-benchmark \
    --out ./eval_runs/mixed-benchmark/reports
```

Total cost: ~$0.02 for 240 batch-discounted calls.

---

## Option C — Local GPU (no API keys)

Run entirely on local HuggingFace models. No API keys, no API costs:

```bash
coeval run --config examples/local_smoke_test.yaml
```

This config uses five small instruction-tuned models (SmolLM2 135M/360M/1.7B, Qwen2.5 0.5B/1.5B) across two tasks. Requires a CUDA GPU; CPU inference is very slow.

---

## Typical Workflow

```
1. Draft config    →  coeval wizard --out my-experiment.yaml
2. Materialize     →  coeval generate --config my-experiment.yaml --out my-experiment-final.yaml
3. Preview         →  coeval describe --config my-experiment-final.yaml
4. Cost estimate   →  coeval plan --config my-experiment-final.yaml
5. Probe           →  coeval probe --config my-experiment-final.yaml
6. Run             →  coeval run --config my-experiment-final.yaml
7. Monitor         →  coeval status --run ./eval_runs/my-experiment
8. Analyze         →  coeval analyze all --run ./eval_runs/my-experiment --out ./reports
```

---

## Frequently Asked Questions

**Q: What is the fastest way to run a first experiment?**
A: Option A is the quickest path if you have a cloud API key — add your key to `~/.coeval/keys.yaml`, then run `coeval probe`, `coeval plan`, and `coeval run` against `examples/local_smoke_test.yaml`. The whole process takes about five minutes and costs a few cents.

**Q: Can I use the wizard to generate my config instead of writing YAML by hand?**
A: Yes. Run `coeval wizard --out my-experiment.yaml` and describe your evaluation goal in plain English. The wizard uses an LLM to draft the config, which you can then refine conversationally or edit directly. Follow up with `coeval generate` to materialize any `auto` placeholders into concrete values.

**Q: What does `coeval probe` do and should I always run it first?**
A: `coeval probe` calls each provider's model-listing endpoint to verify that all configured models are reachable before any generation tokens are spent. It's strongly recommended as a first step — a misconfigured API key or unavailable model is caught here rather than mid-run.

**Q: How cheap is the real benchmark quick start (Option B)?**
A: The mixed benchmark quick start costs approximately $0.02 for 240 batch-discounted API calls using `gpt-4o-mini` and `gpt-3.5-turbo`. Phase 3 data generation is free because the benchmark teacher (`interface: benchmark`) replays pre-ingested dataset responses rather than calling an LLM.

**Q: Can I run entirely without any API keys using local GPU models?**
A: Yes — Option C uses five small HuggingFace models (SmolLM2 and Qwen2.5 variants) entirely on a local GPU with no cloud API calls or API keys. Install with `pip install -e ".[huggingface]"` and ensure you have a CUDA-capable GPU available.

**Q: What is the recommended workflow for production evaluations?**
A: The eight-step typical workflow covers the full cycle: `coeval wizard` to draft the config, `coeval generate` to materialize placeholders, `coeval describe` to preview the design as HTML, `coeval plan` to estimate cost, `coeval probe` to verify models, `coeval run` to execute, `coeval status` to monitor, and `coeval analyze all` to generate reports.

---

[← Installation](02-installation.md) · [Configuration →](04-configuration.md)
