# Cost Planning & Control

[← CLI Reference](08-cli-reference.md) · [Resume & Recovery →](10-resume-recovery.md)

---

CoEval treats cost visibility as a first-class feature. Before a single API call is made, you can get an itemized cost breakdown per model per phase. During the run, hard quotas prevent budget overruns. Batch API support cuts bills in half for three major providers.

## Pre-Run Estimation

### Standalone estimate

```bash
coeval plan --config my-experiment.yaml
```

Samples 2 live API calls per model by default to measure real latency and throughput for the heuristic model. Use `--estimate-samples 0` for pure heuristics (no API calls at all).

### Estimate embedded in a run

```bash
# Estimate, print table, write cost_estimate.json, then exit — no phases run
coeval run --config my-experiment.yaml --estimate-only

# Estimate first, then proceed if within budget
coeval run --config my-experiment.yaml
# (estimate_cost: true in config triggers estimation before Phase 1)
```

### Sample output

```
┌──────────────────────────────────────────────────────────────────────────┐
│  Cost Estimate — paper-eval-v1                                           │
├───────────────────┬────────┬──────────┬───────────┬──────────┬──────────┤
│  Model            │ Phase  │  Calls   │  Tokens   │  Price   │ w/ Batch │
├───────────────────┼────────┼──────────┼───────────┼──────────┼──────────┤
│  gpt-4o           │ P3     │    400   │  240,000  │  $0.72   │  $0.36   │
│  gpt-4o           │ P4     │  4,400   │  880,000  │  $2.64   │  $1.32   │
│  gpt-4o           │ P5     │ 44,000   │ 5,280,000 │ $15.84   │  $7.92   │
│  claude-sonnet-4-6│ P3     │    400   │  240,000  │  $0.87   │  $0.44   │
│  claude-sonnet-4-6│ P4     │  4,400   │  880,000  │  $3.08   │  $1.54   │
│  claude-sonnet-4-6│ P5     │ 44,000   │ 5,280,000 │ $18.48   │  $9.24   │
│  ...              │ ...    │   ...    │    ...    │   ...    │   ...    │
├───────────────────┴────────┴──────────┴───────────┴──────────┴──────────┤
│  Total (10 models × 4 tasks × 100 items)            ~$492  w/ batch ~$246│
└──────────────────────────────────────────────────────────────────────────┘
```

### Remaining-work estimation

When used with `--continue`, the estimator computes cost for only the remaining work:

```bash
coeval plan --config my-experiment.yaml --continue
# → shows cost for phases/items not yet completed
```

---

## Batch API — Up to 50% Off

Enable batch processing per provider in the experiment config:

```yaml
experiment:
  batch:
    openai:
      response_collection: true
      evaluation: true
    anthropic:
      response_collection: true
      evaluation: true
    gemini:
      response_collection: true
      evaluation: true
    azure_openai:
      response_collection: true
      evaluation: true
```

| Provider | API | Discount |
|----------|-----|---------|
| `openai` | OpenAI Batch API (async, 24h window) | **50%** |
| `anthropic` | Message Batches API (async, 24h window) | **50%** |
| `gemini` | Gemini Batch API (async) | **50%** |
| `azure_openai` | Azure Batch API (async) | **50%** |

**How it works:**
1. At the start of a batch-enabled phase, CoEval submits all requests as a batch job
2. The process polls the provider API at intervals until the job completes
3. Results are downloaded and processed identically to real-time responses
4. Use `coeval status --fetch-batches` to check status manually

Batch mode is transparent to the rest of the pipeline — no changes to output format or downstream analysis.

---

## Per-Model Quotas

Hard API call ceilings prevent runaway experiments. Set per model in the `quota` block:

```yaml
experiment:
  quota:
    gpt-4o:
      max_calls: 50000
    claude-sonnet-4-6:
      max_calls: 50000
    llama-3.3-70b:
      max_calls: 30000
```

CoEval tracks calls per model across all phases. When a model reaches its ceiling:
- The current phase records a warning in the log
- The model stops making new calls for that phase
- The pipeline continues for other models
- Remaining items for the quota-reached model are left as gaps (fillable with `--continue` after adjusting the quota)

This means experiments never crash due to quota exhaustion — they complete gracefully with partial results for the affected model.

---

## Built-In Price Table

CoEval ships a price table covering all major models. Prices are in USD per 1M tokens:

| Model fragment | Input | Output |
|----------------|-------|--------|
| `gpt-4o-mini` | $0.15 | $0.60 |
| `gpt-4o` | $2.50 | $10.00 |
| `o1-mini` | $3.00 | $12.00 |
| `o1` | $15.00 | $60.00 |
| `claude-3-5-haiku` | $0.80 | $4.00 |
| `claude-3-5-sonnet` | $3.00 | $15.00 |
| `claude-3-opus` | $15.00 | $75.00 |
| `gemini-2.0-flash` | $0.10 | $0.40 |
| `gemini-2.5-flash` | $0.15 | $0.60 |
| `gemini-2.5-pro` | $1.25 | $10.00 |
| `llama-3.3-70b` | $0.12 | $0.40 |
| `deepseek-chat` | $0.14 | $0.28 |
| `qwen-2.5-72b` | $0.12 | $0.39 |
| *(default fallback)* | $1.00 | $3.00 |

For models not in the built-in table, CoEval falls back to the default price and flags the uncertainty in the estimate output.

---

## Cost Reduction Strategies

| Strategy | Saving |
|----------|--------|
| Enable Batch API for OpenAI, Anthropic, Gemini, Azure OpenAI | **50%** off Phases 4 and 5 |
| Use `benchmark` teachers instead of LLM teachers | Eliminate Phase 3 entirely |
| Use smaller judge models (Haiku, GPT-4o-mini) | 5–20× cheaper per call vs. frontier |
| Set `evaluation_mode: single` | Reduces Phase 5 calls to 1× vs. N× per rubric dimension |
| Use `--only-models` to add models incrementally | Pay for new models only, not re-runs |
| Set `sampling.total` conservatively, extend later | Start small, scale up with `--continue` |

---

[← CLI Reference](08-cli-reference.md) · [Resume & Recovery →](10-resume-recovery.md)
