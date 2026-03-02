# CoEval — Provider Pricing & Configuration Guide

This document is the reference for all provider integrations available in CoEval, their pricing, batch-discount capabilities, and how to configure them. It also covers the `interface: auto` feature for automatic cheapest-provider selection.

**Related files:**
- `benchmark/provider_pricing.yaml` — machine-readable pricing table (loaded by cost estimator and `interface: auto`)
- `experiments/interfaces/cost_estimator.py` — uses pricing table for pre-flight estimates
- `experiments/interfaces/registry.py` — `resolve_auto_interface()` uses auto-routing table

---

## 1. Implemented Providers

### 1.1 OpenAI

| Model | Input ($/1M) | Output ($/1M) | Batch (50% off) |
|-------|-------------|--------------|-----------------|
| gpt-4o | $2.50 | $10.00 | ✅ $1.25 / $5.00 |
| gpt-4o-mini | $0.15 | $0.60 | ✅ $0.075 / $0.30 |
| gpt-4.1 | $2.00 | $8.00 | ✅ $1.00 / $4.00 |
| gpt-4.1-mini | $0.40 | $1.60 | ✅ $0.20 / $0.80 |
| gpt-4.1-nano | $0.10 | $0.40 | ✅ $0.05 / $0.20 |
| gpt-3.5-turbo | $0.50 | $1.50 | ✅ $0.25 / $0.75 |
| o3-mini | $1.10 | $4.40 | ✅ $0.55 / $2.20 |
| o4-mini | $1.10 | $4.40 | ✅ $0.55 / $2.20 |

**Batch discount:** 50% via OpenAI Batch API. Batches are queued asynchronously; use `coeval status` to poll.

**Configuration:**
```yaml
providers:
  openai: sk-...
```

**Model spec:**
```yaml
- name: gpt-4o
  interface: openai
  parameters:
    model: gpt-4o
    temperature: 0.7
    max_tokens: 512
  roles: [teacher, student, judge]
```

---

### 1.2 Anthropic

| Model | Input ($/1M) | Output ($/1M) | Batch (50% off) |
|-------|-------------|--------------|-----------------|
| claude-3-5-haiku-20241022 | $0.80 | $4.00 | ✅ $0.40 / $2.00 |
| claude-3-5-sonnet-20241022 | $3.00 | $15.00 | ✅ $1.50 / $7.50 |
| claude-sonnet-4-6 | $3.00 | $15.00 | ✅ $1.50 / $7.50 |
| claude-haiku-4-6 | $0.80 | $4.00 | ✅ $0.40 / $2.00 |
| claude-opus-4-6 | $15.00 | $75.00 | ✅ $7.50 / $37.50 |

**Batch discount:** 50% via Anthropic Message Batches API. Async; poll with `coeval status`.

**Configuration:**
```yaml
providers:
  anthropic: sk-ant-...
```

**Model spec:**
```yaml
- name: claude-3-5-haiku
  interface: anthropic
  parameters:
    model: claude-3-5-haiku-20241022
    temperature: 0.0
    max_tokens: 256
  roles: [judge]
```

---

### 1.3 Google Gemini

| Model | Input ($/1M) | Output ($/1M) | Batch (50% off) |
|-------|-------------|--------------|-----------------|
| gemini-2.0-flash | $0.10 | $0.40 | ✅ $0.05 / $0.20 |
| gemini-2.0-flash-lite | $0.075 | $0.30 | ✅ $0.0375 / $0.15 |
| gemini-2.5-flash | $0.15 | $0.60 | ✅ $0.075 / $0.30 |
| gemini-2.5-flash-lite | $0.075 | $0.30 | ✅ $0.0375 / $0.15 |
| gemini-1.5-flash | $0.075 | $0.30 | ✅ $0.0375 / $0.15 |
| gemini-1.5-pro | $1.25 | $5.00 | ✅ $0.625 / $2.50 |
| gemini-2.5-pro | $1.25 | $10.00 | ✅ $0.625 / $5.00 |

**Batch discount:** 50% via Gemini Batch API (async; available for Flash and Pro tiers).

**Configuration:**
```yaml
providers:
  gemini: AIza...
```

**Model spec:**
```yaml
- name: gemini-2.0-flash
  interface: gemini
  parameters:
    model: gemini-2.0-flash
    temperature: 0.7
    max_tokens: 512
  roles: [teacher, student, judge]
```

---

### 1.4 OpenRouter

OpenRouter is a meta-router that provides a single OpenAI-compatible API for hundreds of open and commercial models. It is the recommended interface for open-weight models (Llama, Mistral, Qwen, DeepSeek) because it:
- Requires only one API key and one interface
- Routes to the cheapest available backend automatically
- Supports all CoEval model parameters (`temperature`, `max_tokens`)

**No batch discount.** OpenRouter is real-time only.

| Model ID | Input ($/1M) | Output ($/1M) |
|----------|-------------|--------------|
| meta-llama/llama-3.3-70b-instruct | $0.12 | $0.40 |
| meta-llama/llama-3.1-70b-instruct | $0.10 | $0.28 |
| meta-llama/llama-3.1-8b-instruct | $0.05 | $0.08 |
| mistralai/mistral-small-24b | $0.10 | $0.30 |
| mistralai/mistral-large-2411 | $2.00 | $6.00 |
| deepseek/deepseek-chat | $0.14 | $0.28 |
| deepseek/deepseek-r1 | $0.55 | $2.19 |
| qwen/qwen-2.5-72b-instruct | $0.12 | $0.39 |
| google/gemini-2.0-flash-001 | $0.10 | $0.40 |

**Configuration:**
```yaml
providers:
  openrouter: sk-or-v1-...
```

**Model spec:**
```yaml
- name: llama-3.3-70b
  interface: openrouter
  parameters:
    model: meta-llama/llama-3.3-70b-instruct
    temperature: 0.7
    max_tokens: 512
  roles: [teacher, student]
```

---

### 1.5 AWS Bedrock

CoEval supports two Bedrock authentication modes:

**Native API key (recommended):**
```yaml
providers:
  bedrock:
    api_key: BedrockAPIKey-...:...
    region: us-east-1
```

**IAM credentials:**
```yaml
providers:
  bedrock:
    access_key_id: AKIA...
    secret_access_key: ...
    region: us-east-1
```

No batch discount. Real-time inference only.

---

### 1.6 Azure OpenAI

```yaml
providers:
  azure_openai:
    api_key: ...
    endpoint: https://my-resource.openai.azure.com/
    api_version: 2024-08-01-preview
```

---

### 1.7 Google Vertex AI

```yaml
providers:
  vertex:
    project: my-gcp-project
    location: us-central1
```

Requires Application Default Credentials (`gcloud auth application-default login`).

---

## 2. `interface: auto` — Automatic Provider Selection

Setting `interface: auto` in a model configuration tells CoEval to automatically select the **cheapest available provider** for the given model, based on:

1. The `auto_routing` table in `benchmark/provider_pricing.yaml`
2. Which providers have credentials configured in `keys.yaml`

**Example:**
```yaml
- name: deepseek-v3
  interface: auto          # CoEval resolves to openrouter (cheapest with credentials)
  parameters:
    model: deepseek/deepseek-chat
    temperature: 0.7
    max_tokens: 512
  roles: [student]
```

CoEval scans the `auto_routing` table top-to-bottom (cheapest first), finds the first fragment matching `deepseek/deepseek-chat`, and resolves to `openrouter` if those credentials exist. If OpenRouter is not configured, it tries the next provider in the routing table.

**Resolution happens at config load time** — the interface is permanently set before validation, so `coeval plan`, `coeval probe`, and `coeval run` all see the resolved interface.

**How to update the routing table:**

Edit `benchmark/provider_pricing.yaml` and modify the `auto_routing` section. Entries are ordered cheapest-first. To route a model to a different provider, change the `interface:` value for its fragment or add a new entry with higher specificity:

```yaml
auto_routing:
  # More specific fragment takes precedence
  deepseek/deepseek-r1: {interface: openrouter, notes: "reasoning model"}
  deepseek:             {interface: openrouter, notes: "default deepseek"}
```

---

## 3. Updating Prices

All pricing data is stored in `benchmark/provider_pricing.yaml`. To update a price:

1. Edit `benchmark/provider_pricing.yaml` — find the model under its `providers:` block and update `input:` / `output:` values.
2. Run `coeval plan --config your_experiment.yaml` to see the new estimate.
3. Commit the updated YAML.

The cost estimator loads this file at runtime. The hardcoded `PRICE_TABLE` in `cost_estimator.py` is only a fallback if the YAML is unavailable.

---

## 4. Suggested Future Providers

These providers offer competitive pricing and use OpenAI-compatible REST APIs. They are **not yet implemented** as dedicated CoEval interfaces but can be accessed today via `interface: openrouter`.

| Provider | Batch? | Notable Models | Input ($/1M) | Output ($/1M) |
|----------|--------|----------------|-------------|--------------|
| **Groq** | No | Llama-3.1-8B-Instant | $0.05 | $0.08 |
| | | Mixtral-8x7B | $0.24 | $0.24 |
| **Together AI** | No | Llama-3.3-70B | $0.90 | $0.90 |
| | | Qwen2.5-72B | $1.20 | $1.20 |
| **DeepInfra** | No | Llama-3.3-70B | $0.12 | $0.40 |
| | | Qwen2.5-72B | $0.30 | $0.50 |
| **Fireworks AI** | No | Llama-3.3-70B-Instruct | $0.20 | $0.20 |
| | | Mixtral-8x7B | $0.50 | $0.50 |
| **DeepSeek API** | No | DeepSeek-V3 | $0.14 | $0.28 |
| | | DeepSeek-R1 | $0.55 | $2.19 |
| **Mistral API** | No | Mistral-Small-Latest | $0.10 | $0.30 |
| | | Mistral-Large-Latest | $2.00 | $6.00 |
| **Cohere** | No | Command-R | $0.15 | $0.60 |
| | | Command-R+ | $2.50 | $10.00 |
| **AI21 Labs** | No | Jamba-1.5-Mini | $0.20 | $0.40 |

**Integration effort:** All except Cohere use OpenAI-compatible endpoints. Adding a dedicated interface requires:
1. A new `experiments/interfaces/PROVIDER_iface.py` (copy from `openrouter_iface.py`, change base URL)
2. Adding the provider to `resolve_provider_keys()` in `registry.py`
3. Adding it to `VALID_INTERFACES` in `config.py`
4. Adding entries to `benchmark/provider_pricing.yaml`

**Groq** and **Fireworks AI** are the highest-priority additions due to their extremely low latency (Groq LPU hardware) and competitive pricing for batch-like workloads.

---

## 5. Batch API Reference

| Interface | Batch API | Discount | Polling |
|-----------|-----------|---------|---------|
| `openai` | OpenAI Batch API | 50% | `coeval status` |
| `anthropic` | Message Batches API | 50% | `coeval status` |
| `gemini` | Gemini Batch API | 50% | `coeval status` |
| `openrouter` | None (real-time) | — | — |
| `bedrock` | None (real-time) | — | — |
| `azure_openai` | None (real-time) | — | — |
| `vertex` | None (real-time) | — | — |
| `huggingface` | None (local) | — | — |

Enable batch per-interface in the experiment config:
```yaml
experiment:
  batch:
    openai:
      response_collection: true
      evaluation:          true
    anthropic:
      response_collection: true
      evaluation:          true
    gemini:
      response_collection: true
      evaluation:          true
```

---

*Prices as of 2026-03-02. Verify at provider pricing pages before running large experiments.*
