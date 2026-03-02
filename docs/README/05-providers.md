# Providers & Pricing

[← Configuration](04-configuration.md) · [Running Experiments →](06-running.md)

---

## Interface Overview

CoEval supports **15 model interfaces** spanning every major cloud provider, OpenAI-compatible APIs, local GPU inference, and virtual benchmark teachers.

| Interface | Provider / Runtime | Batch API | 50% Discount | Auth |
|-----------|-------------------|:---------:|:------------:|------|
| `openai` | OpenAI (GPT-4o, o3, o1, GPT-3.5, …) | ✅ OpenAI Batch API | ✅ | `OPENAI_API_KEY` |
| `anthropic` | Anthropic (Claude 3.5 Sonnet/Haiku, Claude 3 Opus) | ✅ Message Batches API | ✅ | `ANTHROPIC_API_KEY` |
| `gemini` | Google Gemini 2.0 Flash, 1.5 Pro/Flash | ✅ Gemini Batch API | ✅ | `GEMINI_API_KEY` or `GOOGLE_API_KEY` |
| `azure_openai` | Azure OpenAI deployments (any GPT model) | ✅ Azure Batch API | ✅ | `AZURE_OPENAI_API_KEY` + `AZURE_OPENAI_ENDPOINT` |
| `azure_ai` | Azure AI Foundry / GitHub Models | — | — | `AZURE_AI_API_KEY` or `GITHUB_TOKEN` |
| `bedrock` | AWS Bedrock — all foundation models | — | — | Native API key **or** IAM |
| `vertex` | Google Vertex AI (Gemini on GCP) | — | — | `GOOGLE_CLOUD_PROJECT` + ADC |
| `openrouter` | OpenRouter — 300+ models | — | — | `OPENROUTER_API_KEY` |
| `groq` | Groq Cloud (ultra-fast inference) | — | — | `GROQ_API_KEY` |
| `deepseek` | DeepSeek API | — | — | `DEEPSEEK_API_KEY` |
| `mistral` | Mistral AI | — | — | `MISTRAL_API_KEY` |
| `deepinfra` | DeepInfra | — | — | `DEEPINFRA_API_KEY` |
| `cerebras` | Cerebras (ultra-fast inference) | — | — | `CEREBRAS_API_KEY` |
| `huggingface` | Any HuggingFace model (local GPU) | — | — | `HF_TOKEN` or `HUGGINGFACE_HUB_TOKEN` |
| `benchmark` | Virtual — pre-ingested dataset responses | N/A | N/A | none |

---

## Interface Notes

### `openai`

The default and most feature-complete interface. Supports OpenAI Batch API for Phase 4 (response collection) and Phase 5 (evaluation) with a 50% cost discount. Batch jobs are submitted automatically and polled until completion.

```yaml
- name: gpt-4o-mini
  interface: openai
  parameters:
    model: gpt-4o-mini
  roles: [teacher, student, judge]
```

### `anthropic`

Supports Anthropic's Message Batches API with a 50% batch discount. Requires `pip install anthropic`.

```yaml
- name: claude-3-5-haiku
  interface: anthropic
  parameters:
    model: claude-3-5-haiku-20241022
  roles: [student, judge]
```

### `gemini`

Supports Google Gemini Batch API with 50% discount. Requires `pip install google-genai`.

```yaml
- name: gemini-2.0-flash
  interface: gemini
  parameters:
    model: gemini-2.0-flash
  roles: [student, judge]
```

### `azure_openai`

Connects to Azure OpenAI deployments. Requires deployment name in `model`, endpoint URL, and API version. Supports Azure Batch API with a 50% discount (see [Batch API](#batch-api) below).

```yaml
- name: my-gpt4-deployment
  interface: azure_openai
  parameters:
    model: my-deployment-name
    azure_endpoint: https://my-resource.openai.azure.com/
    api_version: 2024-08-01-preview
  roles: [student]
```

### `bedrock`

AWS Bedrock supports two mutually exclusive authentication modes:

**Native API key** (no `boto3` required):
```yaml
bedrock:
  api_key: BedrockAPIKey-...:...
  region: us-east-1
```

**IAM credentials** (requires `pip install boto3`):
```yaml
bedrock:
  access_key_id:     AKIA...
  secret_access_key: ...
  region: us-east-1
```

Native API key takes priority if both are present.

### `openrouter`

OpenRouter provides access to 300+ models (Llama, Mistral, Qwen, DeepSeek, Cohere, Gemma, and more) through a single API key and OpenAI-compatible interface. Ideal for multi-model comparisons without managing individual provider accounts.

```yaml
- name: llama-3.3-70b
  interface: openrouter
  parameters:
    model: meta-llama/llama-3.3-70b-instruct
  roles: [teacher, student, judge]
```

### `groq` / `cerebras`

Ultra-fast inference providers — 500–1000 tokens/second throughput. Best for experiments where latency matters more than cost. Both use the OpenAI SDK wire format.

```yaml
- name: llama-3.1-70b-groq
  interface: groq
  parameters:
    model: llama-3.1-70b-versatile
  roles: [student]
```

### `huggingface`

Runs any instruction-tuned HuggingFace model locally. Requires `pip install -e ".[huggingface]"` and a CUDA GPU for reasonable throughput. Models are loaded into VRAM and run sequentially (no concurrent batching for GPU-bound inference).

```yaml
- name: qwen2p5-1b5
  interface: huggingface
  parameters:
    model: Qwen/Qwen2.5-1.5B-Instruct
    device: auto
    max_new_tokens: 512
  roles: [teacher, student, judge]
```

### `benchmark` — Virtual Teacher

The `benchmark` interface is a zero-cost virtual teacher that replays pre-ingested responses from real datasets. Phase 3 is skipped entirely for benchmark models — data was already ingested by `coeval ingest` or `benchmark/setup_mixed.py`.

```yaml
- name: xsum
  interface: benchmark
  parameters:
    dataset: xsum
    split: test
  roles: [teacher]
```

**Pre-ingested datasets available via `benchmark/setup_mixed.py`:**
- `xsum` — BBC news articles with one-sentence summaries
- `codesearchnet-python` — Python functions with docstring explanations
- `aeslc` — Email bodies with subject lines
- `wikitablequestions` — Wikipedia tables with natural language questions

**Additional datasets via `coeval ingest`:**
`mmlu`, `hellaswag`, `truthfulqa`, `humaneval`, `medqa`, `gsm8k`

The benchmark teacher's `name` field should match the dataset identifier used during ingestion. The virtual interface looks for pre-ingested JSONL files named:
```
phase3_datapoints/{task_id}.{model_name}.datapoints.jsonl
```

**Recommended naming pattern:**

| Model name | Dataset source |
|------------|---------------|
| `benchmark` | Default / unspecified ingested data |
| `benchmark-xsum` | XSum summarization dataset |
| `benchmark-aeslc` | AESLC email subject-line corpus |
| `benchmark-codesearchnet` | CodeSearchNet code+docstring pairs |
| `benchmark-wikitableqa` | WikiTableQuestions dataset |

---

## Batch API

Four interfaces support asynchronous batch processing with a 50% discount:

| Interface | Batch Mode | Discount |
|-----------|-----------|---------|
| `openai` | OpenAI Batch API — async, 24h window | 50% |
| `anthropic` | Message Batches API — async, 24h window | 50% |
| `gemini` | Gemini Batch API — async | 50% |
| `azure_openai` | Azure Batch API — async | 50% |

Enable per provider and per phase in the experiment config:

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
    azure_openai:          # also supported
      response_collection: true
      evaluation: true
```

Batch jobs are submitted at the start of each phase and polled automatically. Use `coeval status --fetch-batches` to check completion status manually.

**How batch works:**
1. At the start of a batch-enabled phase, CoEval submits all requests as a batch job
2. The process polls the provider API at intervals until the job completes
3. Results are downloaded and processed identically to real-time responses
4. Batch mode is transparent to the rest of the pipeline — no changes to output format or downstream analysis

**Full batch API status:**

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

---

## Provider Pricing

*Prices as of 2026-03-02. Verify at provider pricing pages before running large experiments.*

### OpenAI

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

### Anthropic

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

### Google Gemini

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

### OpenRouter

OpenRouter is a meta-router providing a single OpenAI-compatible API for hundreds of open and commercial models. It is the recommended interface for open-weight models (Llama, Mistral, Qwen, DeepSeek) because:
- Single API key and interface covers all open models
- Routes to cheapest available backend automatically
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

### AWS Bedrock

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

AWS Bedrock has a native Batch Inference API supporting Claude, Amazon Nova, Llama, and Mistral models with ~50% discount. CoEval does not yet have a `BedrockBatchRunner`, so batch mode is not available for Bedrock in CoEval — it runs real-time only.

Selected Bedrock model prices:

| Model | Input ($/1M) | Output ($/1M) | CoEval Batch? |
|-------|-------------|--------------|---------------|
| anthropic.claude-3-5-haiku-20241022-v1 | $0.80 | $4.00 | ❌ not yet |
| anthropic.claude-3-5-sonnet-20241022-v2 | $3.00 | $15.00 | ❌ not yet |
| amazon.nova-micro-v1 | $0.035 | $0.14 | ❌ not yet |
| amazon.nova-lite-v1 | $0.06 | $0.24 | ❌ not yet |
| amazon.nova-pro-v1 | $0.80 | $3.20 | ❌ not yet |
| meta.llama3-70b-instruct-v1 | $0.99 | $0.99 | ❌ not yet |

### Azure OpenAI

Azure OpenAI supports **Global Batch** (50% discount) — `AzureBatchRunner` is already implemented in CoEval.

```yaml
providers:
  azure_openai:
    api_key: ...
    endpoint: https://my-resource.openai.azure.com/
    api_version: 2024-08-01-preview
```

Enable batch per-phase in the experiment config:

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

> **Note:** Azure prices include a small Azure markup over native OpenAI pricing (e.g. GPT-4o-mini $0.165 vs $0.15). After the 50% batch discount, the effective price is similar to OpenAI native batch.

### Google Vertex AI

```yaml
providers:
  vertex:
    project: my-gcp-project
    location: us-central1
```

Requires Application Default Credentials (`gcloud auth application-default login`). Supports same Gemini models as the Gemini AI Studio interface.

### Why Open Models Use OpenRouter (Not a Batch Provider)

The 50% batch discounts are **exclusive to each provider's own proprietary models**:

| Batch discount | Applies to |
|----------------|-----------|
| OpenAI Batch API (50%) | GPT-4o, GPT-4o-mini, GPT-4.1, o-series only |
| Anthropic Message Batches (50%) | Claude 3.x / Claude 4.x only |
| Gemini Batch API (50%) | Gemini 1.5 / 2.0 / 2.5 only |
| Azure Global Batch (50%) | GPT-4o, GPT-4o-mini (Azure deployments) |
| **Open-weight models (Llama, Mistral, Qwen, DeepSeek)** | **No batch discount anywhere** |

For `interface: auto`, frontier models are automatically routed to their native batch-enabled provider. Open-weight models go to OpenRouter because no third-party inference provider offers a batch discount for them. OpenRouter at $0.04–$0.12/M is already the cheapest option for these models.

---

## `interface: auto` Routing

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

**To update prices:** Edit `benchmark/provider_pricing.yaml` — find the model under its `providers:` block and update `input:` / `output:` values. The cost estimator loads this file at runtime. The hardcoded `PRICE_TABLE` in `cost_estimator.py` is only a fallback if the YAML is unavailable.

---

## Key File Reference

Store all credentials in one place. CoEval discovers and resolves them automatically.

**Search order:**
1. `--keys PATH` CLI flag
2. `COEVAL_KEYS_FILE` environment variable
3. `keys.yaml` at the project root
4. `~/.coeval/keys.yaml`

**Full key file format:**

```yaml
# ~/.coeval/keys.yaml  (or project root keys.yaml)
providers:
  openai:      sk-...
  anthropic:   sk-ant-...
  gemini:      AIza...
  huggingface: hf_...
  openrouter:  sk-or-v1-...
  groq:        gsk_...
  deepseek:    sk-...
  mistral:     ...
  deepinfra:   di-...
  cerebras:    csk-...

  azure_openai:
    api_key:     ...
    endpoint:    https://my-resource.openai.azure.com/
    api_version: 2024-08-01-preview

  bedrock:
    api_key: BedrockAPIKey-...:...    # native API key (no boto3 needed)
    region:  us-east-1
  # — OR — IAM credentials:
  # bedrock:
  #   access_key_id:     AKIA...
  #   secret_access_key: ...
  #   region:            us-east-1

  vertex:
    project:  my-gcp-project
    location: us-central1
    service_account_key: /path/to/key.json   # optional; uses ADC if omitted
```

**Credential resolution order per model:**
```
model.access_key (in YAML)  →  provider entry in keys.yaml  →  environment variable
```

> **Security:** `keys.yaml`, `*.keys.yaml`, and `.coeval/` are included in `.gitignore` by default. Never commit credentials to version control.

---

[← Configuration](04-configuration.md) · [Running Experiments →](06-running.md)
