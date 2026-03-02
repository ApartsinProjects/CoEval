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

---

### 1.4 OpenRouter

OpenRouter is a meta-router providing a single OpenAI-compatible API for hundreds of open and commercial models. It is the recommended interface for open-weight models (Llama, Mistral, Qwen, DeepSeek) because:
- Single API key and interface covers all open models
- Routes to cheapest available backend automatically
- Supports all CoEval model parameters (`temperature`, `max_tokens`)

> **Why not a provider with batch discounts?** Batch discounts (OpenAI 50%, Anthropic 50%, Gemini 50%) are **proprietary** — they only apply to each provider's own models. No inference provider today offers batch discounts for Llama, Mistral, DeepSeek, or Qwen models. For open-weight models, OpenRouter is already the cheapest convenient option at $0.04–$0.12/M input tokens.

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

**Batch status:** AWS Bedrock **does** have a native Batch Inference API (launched late 2023) supporting Claude, Amazon Nova, Llama, and Mistral models with ~50% discount. However, **CoEval does not yet have a `BedrockBatchRunner`**, so batch mode is not available for Bedrock in CoEval. It runs real-time only (`batch_discount: 1.00` in pricing YAML).

> **TODO:** Implement `BedrockBatchRunner` to unlock the ~50% Bedrock batch discount. Once implemented, update `bedrock: batch_discount: 0.50` in `benchmark/provider_pricing.yaml` and add `bedrock` to `create_batch_runner()` in `experiments/interfaces/__init__.py`.

Selected Bedrock model prices:

| Model | Input ($/1M) | Output ($/1M) | CoEval Batch? |
|-------|-------------|--------------|---------------|
| anthropic.claude-3-5-haiku-20241022-v1 | $0.80 | $4.00 | ❌ not yet |
| anthropic.claude-3-5-sonnet-20241022-v2 | $3.00 | $15.00 | ❌ not yet |
| amazon.nova-micro-v1 | $0.035 | $0.14 | ❌ not yet |
| amazon.nova-lite-v1 | $0.06 | $0.24 | ❌ not yet |
| amazon.nova-pro-v1 | $0.80 | $3.20 | ❌ not yet |
| meta.llama3-70b-instruct-v1 | $0.99 | $0.99 | ❌ not yet |

---

### 1.6 Azure OpenAI

Azure OpenAI supports **Global Batch** (50% discount) — **`AzureBatchRunner` is already implemented** in CoEval.

```yaml
providers:
  azure_openai:
    api_key: ...
    endpoint: https://my-resource.openai.azure.com/
    api_version: 2024-08-01-preview
```

**Batch discount:** 50% via Azure Global Batch API. Enable it per-phase in the experiment config:

```yaml
experiment:
  batch:
    azure_openai:
      response_collection: true
      evaluation: true
```

Selected Azure OpenAI model prices:

| Deployment | Input ($/1M) | Output ($/1M) | Batch (50% off) |
|------------|-------------|--------------|-----------------|
| gpt-4o | $2.50 | $10.00 | ✅ $1.25 / $5.00 |
| gpt-4o-mini | $0.165 | $0.66 | ✅ $0.083 / $0.33 |

> **Note:** Azure prices include a small Azure markup over native OpenAI pricing (e.g. GPT-4o-mini $0.165 vs $0.15). After the 50% batch discount, the effective price is similar to OpenAI native batch. Use Azure when your team already has Azure credits or enterprise agreements.

---

### 1.7 Google Vertex AI

```yaml
providers:
  vertex:
    project: my-gcp-project
    location: us-central1
```

Requires Application Default Credentials (`gcloud auth application-default login`).

Supports same Gemini models as the Gemini AI Studio interface. Vertex batch is supported with 50% discount but CoEval routes through the `gemini` interface by default.

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

**How to update the routing table:** Edit `benchmark/provider_pricing.yaml` and modify the `auto_routing` section (entries are ordered cheapest-first):

```yaml
auto_routing:
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

### 4.1 Why Are Open Models on OpenRouter (Not a Cheaper Batch Provider)?

The 50% batch discounts are **exclusive to each provider's own proprietary models**:

| Batch discount | Applies to |
|----------------|-----------|
| OpenAI Batch API (50%) | GPT-4o, GPT-4o-mini, GPT-4.1, o-series only |
| Anthropic Message Batches (50%) | Claude 3.x / Claude 4.x only |
| Gemini Batch API (50%) | Gemini 1.5 / 2.0 / 2.5 only |
| Azure Global Batch (50%) | GPT-4o, GPT-4o-mini (Azure deployments) |
| **Open-weight models (Llama, Mistral, Qwen, DeepSeek)** | **No batch discount anywhere** |

For `interface: auto`, frontier models are automatically routed to their native batch-enabled provider. Open-weight models go to OpenRouter because **no third-party inference provider offers a batch discount for them**. OpenRouter at $0.04–$0.12/M is already the cheapest option for these models.

### 4.2 Provider Candidates (Priority-Ordered)

These providers are not yet implemented as dedicated CoEval interfaces but can be accessed today via `interface: openrouter`.

| Provider | Priority | Batch? | Notable Models | Input ($/1M) | Output ($/1M) | Why add natively? |
|----------|----------|--------|----------------|-------------|--------------|-------------------|
| **Groq** | P1 ★★★ | No | Llama-3.1-8B-Instant | $0.05 | $0.08 | ~500 tok/s (10–20× faster); ideal for large-scale Phase 4 |
| | | | Llama-3.3-70B | $0.59 | $0.79 | API: `api.groq.com` (OpenAI-compat) |
| | | | Mixtral-8x7B | $0.24 | $0.24 | |
| **DeepSeek** | P1 ★★★ | No | DeepSeek-V3 | $0.07 | $0.28 | 2× cheaper than OpenRouter for V3 |
| (direct) | | | DeepSeek-R1 | $0.55 | $2.19 | API: `api.deepseek.com` (OpenAI-compat) |
| **Mistral API** | P2 ★★ | No | Mistral-Small-Latest | $0.10 | $0.30 | Same price as OpenRouter; no markup + better SLAs |
| (direct) | | | Mistral-Large-Latest | $2.00 | $6.00 | Codestral (code tasks) only on direct, not OpenRouter |
| | | | Codestral | $0.20 | $0.60 | |
| **DeepInfra** | P2 ★★ | No | Llama-3.3-70B | $0.12 | $0.40 | Same price as OpenRouter; more reliable SLAs |
| | | | DeepSeek-R1 | $0.55 | $2.19 | API: `api.deepinfra.com` (OpenAI-compat) |
| | | | Qwen2.5-72B | $0.13 | $0.40 | |
| **Cerebras** | P2 ★★ | No | Llama-3.1-8B | $0.10 | $0.10 | Wafer-scale AI chip; ~1000 tok/s sustained |
| | | | Llama-3.1-70B | $0.60 | $0.60 | API: `api.cerebras.ai` (OpenAI-compat) |
| **Fireworks AI** | P2 ★★ | No | Llama-3.3-70B | $0.20 | $0.20 | Flat output price; cheap for verbose outputs |
| | | | DeepSeek-V3 | $0.50 | $1.50 | API: `api.fireworks.ai` (OpenAI-compat) |
| **Novita AI** | P2 ★★ | No | Llama-3.3-70B | $0.09 | $0.35 | Slightly cheaper than OpenRouter for Llama |
| | | | Qwen2.5-72B | $0.12 | $0.39 | API: `api.novita.ai` (OpenAI-compat) |
| **Bedrock Batch** | P1 ★★★ | Yes (~50%) | Amazon Nova family | $0.018 | $0.07 | Already auth-supported; just needs BatchRunner impl |
| | | | Claude via Bedrock | same as Anthropic direct | | BedrockBatchRunner in `experiments/interfaces/` |
| **Cohere** | P3 ★ | No | Command-R | $0.15 | $0.60 | RAG-optimised; unique retrieval features |
| | | | Command-R+ | $2.50 | $10.00 | `api.cohere.com` (native SDK) |
| **AI21 Labs** | P3 ★ | No | Jamba-1.5-Mini | $0.20 | $0.40 | SSM-Transformer hybrid; 256K context |
| | | | Jamba-1.5-Large | $2.00 | $8.00 | `api.ai21.com` (OpenAI-compat) |
| **Cloudflare** | P3 ★ | No | Llama-3-8B | $0.01 | $0.01 | Extremely cheap for small-model quick evals |
| (Workers AI) | | | Mistral-7B | $0.01 | $0.01 | Serverless; good for Phase 1/2 drafts |

### 4.3 Implementation Effort

All P1/P2 providers use **OpenAI-compatible REST APIs** (chat completions endpoint). Adding a dedicated native interface:

1. Create `experiments/interfaces/<provider>_iface.py` (copy `openrouter_iface.py`; change base URL and auth)
2. Add to `VALID_INTERFACES` in `experiments/config.py`
3. Add to `create_batch_runner()` factory in `experiments/interfaces/__init__.py` (if batch supported)
4. Add pricing block to `benchmark/provider_pricing.yaml` and `auto_routing` entries
5. Add to `probe.py` supported providers list

**Estimated effort:** 2–4 hours per provider. **BedrockBatchRunner** is highest-priority since authentication is already implemented.

---

## 5. Batch API Reference

| Interface | Batch API | CoEval Status | Discount |
|-----------|-----------|--------------|---------|
| `openai` | OpenAI Batch API | ✅ Implemented | 50% |
| `anthropic` | Message Batches API | ✅ Implemented | 50% |
| `gemini` | Gemini Batch API | ✅ Implemented | 50% |
| `azure_openai` | Azure Global Batch | ✅ Implemented (`AzureBatchRunner`) | 50% |
| `bedrock` | AWS Bedrock Batch Inference | ❌ Not yet (native API exists) | ~50% when added |
| `openrouter` | None (real-time) | N/A | — |
| `vertex` | Vertex Batch (via Gemini) | Routes to `gemini` | — |
| `huggingface` | None (local) | N/A | — |

Enable batch per-interface in the experiment config:
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
    azure_openai:          # ← also supported
      response_collection: true
      evaluation: true
```

---

*Prices as of 2026-03-02. Verify at provider pricing pages before running large experiments.*
