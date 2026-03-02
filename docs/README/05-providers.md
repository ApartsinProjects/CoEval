# Providers & Pricing

[← Configuration](04-configuration.md) · [Running Experiments →](06-running.md)

---

## Interface Overview

CoEval supports **18 model interfaces** spanning every major cloud provider, OpenAI-compatible APIs, local GPU inference, and virtual benchmark teachers.

| Interface | Provider / Runtime | Batch API | 50% Discount | Auth |
|-----------|-------------------|:---------:|:------------:|------|
| `openai` | OpenAI (GPT-4o, o3, o1, GPT-3.5, …) | ✅ OpenAI Batch API | ✅ | `OPENAI_API_KEY` |
| `anthropic` | Anthropic (Claude 3.5 Sonnet/Haiku, Claude 3 Opus) | ✅ Message Batches API | ✅ | `ANTHROPIC_API_KEY` |
| `gemini` | Google Gemini 2.0 Flash, 1.5 Pro/Flash | ⚡ Concurrent¹ | — | `GEMINI_API_KEY` or `GOOGLE_API_KEY` |
| `azure_openai` | Azure OpenAI deployments (any GPT model) | ✅ Azure Batch API | ✅ | `AZURE_OPENAI_API_KEY` + `AZURE_OPENAI_ENDPOINT` |
| `azure_ai` | Azure AI Foundry / GitHub Models | — | — | `AZURE_AI_API_KEY` or `GITHUB_TOKEN` |
| `bedrock` | AWS Bedrock — all foundation models | ✅ Model Invocation Jobs² | ✅ | Native API key **or** IAM |
| `vertex` | Google Vertex AI (Gemini on GCP) | ✅ Batch Prediction Jobs² | ✅ | `GOOGLE_CLOUD_PROJECT` + ADC |
| `openrouter` | OpenRouter — 300+ models | — | — | `OPENROUTER_API_KEY` |
| `groq` | Groq Cloud (ultra-fast inference) | — | — | `GROQ_API_KEY` |
| `deepseek` | DeepSeek API | — | — | `DEEPSEEK_API_KEY` |
| `mistral` | Mistral AI | ✅ Mistral Batch API | ✅ | `MISTRAL_API_KEY` |
| `deepinfra` | DeepInfra | — | — | `DEEPINFRA_API_KEY` |
| `cerebras` | Cerebras (ultra-fast inference) | — | — | `CEREBRAS_API_KEY` |
| `cohere` | Cohere (Command R/R+/A family) | — | — | `COHERE_API_KEY` |
| `huggingface_api` | HuggingFace Inference API (50k+ Hub models) | — | — | `HF_TOKEN` or `HUGGINGFACE_HUB_TOKEN` |
| `ollama` | Ollama — local model server | — | — | none (no key needed) |
| `huggingface` | Any HuggingFace model (local GPU) | — | — | `HF_TOKEN` or `HUGGINGFACE_HUB_TOKEN` |
| `benchmark` | Virtual — pre-ingested dataset responses | N/A | N/A | none |

> ¹ **Gemini concurrent mode**: Google's Generative AI API does not offer a native asynchronous batch endpoint. CoEval submits all Gemini requests concurrently via a thread pool (`GeminiBatchRunner`). This is faster than sequential calls but does **not** provide a 50% batch discount — you pay standard per-token rates.
>
> ² **Bedrock and Vertex batch** use cloud storage (S3/GCS) as the job transport. Additional setup is required: an S3 bucket + IAM service role for Bedrock; a GCS bucket + ADC for Vertex. See the [Batch API](#batch-api) section below.

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

Submits requests concurrently via a thread pool (pseudo-batch mode). Google's Generative AI API does **not** offer a native async batch endpoint — there is no 50% batch discount. Requires `pip install google-genai`.

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

### `cohere`

Cohere's Command R/R+/A family via their OpenAI-compatible endpoint (`https://api.cohere.com/compatibility/v1`). Best-in-class for retrieval-augmented generation (RAG) and long-context tasks. No batch discount — real-time only.

```yaml
- name: command-r-plus
  interface: cohere
  parameters:
    model: command-r-plus-08-2024
    temperature: 0.7
    max_tokens: 512
  roles: [teacher, student, judge]
```

**Pricing (Command family):**

| Model | Input ($/1M) | Output ($/1M) |
|-------|-------------|--------------|
| command-a-03-2025 | $2.50 | $10.00 |
| command-r-plus-08-2024 | $2.50 | $10.00 |
| command-r-08-2024 | $0.15 | $0.60 |
| command-r7b-12-2024 | $0.04 | $0.15 |

**Key file:**
```yaml
providers:
  cohere: co-...
```

---

### `huggingface_api` — HuggingFace Inference API

Access any of the 50,000+ hosted models on HuggingFace Hub via their serverless Inference API (`https://api-inference.huggingface.co/v1`). No GPU required — inference runs on HuggingFace's infrastructure. Model IDs must be full Hub paths (e.g. `mistralai/Mistral-7B-Instruct-v0.3`).

```yaml
- name: mistral-7b-hf
  interface: huggingface_api
  parameters:
    model: mistralai/Mistral-7B-Instruct-v0.3
    temperature: 0.7
    max_tokens: 512
  roles: [student]
```

**Pricing:** Pay-per-token for serverless inference. Rates depend on model size; popular models cost $0.04–$0.23/M tokens. HuggingFace PRO subscribers get free monthly quota on many models.

| Model | Input & Output ($/1M) |
|-------|----------------------|
| meta-llama/Llama-3.1-8B-Instruct | $0.06 |
| meta-llama/Llama-3.3-70B-Instruct | $0.23 |
| mistralai/Mistral-7B-Instruct-v0.3 | $0.04 |
| Qwen/Qwen2.5-72B-Instruct | $0.23 |
| google/gemma-2-9b-it | $0.06 |

> **Note:** `huggingface_api` (cloud inference, this section) is distinct from `huggingface` (local GPU inference, below). Use `huggingface_api` when you don't have a GPU; use `huggingface` for private or quantized models that must run locally.

**Key file:**
```yaml
providers:
  huggingface_api: hf_...   # same token as huggingface; accepts HF_TOKEN or HUGGINGFACE_HUB_TOKEN
```

---

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

### `ollama` — Local Model Server

Ollama runs any supported open-weight model locally using a lightweight server that exposes an OpenAI-compatible REST API. No API key is required. Ideal for privacy-sensitive experiments or air-gapped environments.

**Install Ollama:** https://ollama.com — then pull a model:
```bash
ollama pull llama3.2
ollama pull phi4
ollama pull gemma3
```

**Minimal config (default localhost):**
```yaml
- name: llama3.2-local
  interface: ollama
  parameters:
    model: llama3.2
    temperature: 0.7
    max_tokens: 512
  roles: [student]
```

**Custom host (remote Ollama server or non-default port):**
```yaml
- name: llama3.2-remote
  interface: ollama
  parameters:
    model: llama3.2
    base_url: http://192.168.1.50:11434/v1   # overrides default localhost
  roles: [student]
```

Alternatively, set `OLLAMA_HOST=http://192.168.1.50:11434` in your environment.

**Key file entry (optional base_url override):**
```yaml
providers:
  ollama:
    base_url: http://192.168.1.50:11434/v1
```

**Notes:**
- Ollama is treated as a network interface (no GPU pool management in CoEval)
- No batching — requests are sent concurrently via the standard sequential path
- Cost estimation returns $0 for Ollama models (no per-token cost)
- `coeval probe` calls `models.list()` on the Ollama server to verify connectivity

---

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

**Six interfaces** support **true asynchronous batch processing** with a ~50% cost discount. Gemini uses a concurrent runner (faster than sequential but no discount). See the per-interface sections for setup details.

| Interface | Batch Mode | Discount | Extra Requirements |
|-----------|-----------|---------|-------------------|
| `openai` | OpenAI Batch API — async, 24h window | ✅ 50% | None |
| `anthropic` | Message Batches API — async, 24h window | ✅ 50% | None |
| `azure_openai` | Azure Global Batch API — async | ✅ 50% | Azure endpoint |
| `mistral` | Mistral Batch API — async (OpenAI-compat format) | ✅ ~50% | None |
| `bedrock` | AWS Model Invocation Jobs — async | ✅ ~50% | S3 bucket + IAM role |
| `vertex` | Vertex AI Batch Prediction — async | ✅ 50% | GCS bucket + ADC |
| `gemini` | Concurrent thread pool (pseudo-batch) | ❌ none | None |

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
    azure_openai:
      response_collection: true
      evaluation: true
    mistral:                # Mistral Batch API — async, ~50% off; no extra requirements
      response_collection: true
      evaluation: true
    bedrock:                # requires batch_s3_bucket + batch_role_arn in model params
      response_collection: true
      evaluation: true
    vertex:                 # requires batch_gcs_bucket in model params
      response_collection: true
      evaluation: true
    gemini:                 # concurrent mode — no discount, but faster than sequential
      response_collection: true
      evaluation: true
```

Batch jobs are submitted at the start of each phase and polled automatically. Use `coeval status --fetch-batches` to check completion status manually.

**How async batch works (OpenAI / Anthropic / Azure / Bedrock / Vertex):**
1. At the start of a batch-enabled phase, CoEval submits all requests as a batch job
2. The process polls the provider API at intervals until the job completes
3. Results are downloaded and processed identically to real-time responses
4. Batch mode is transparent to the rest of the pipeline — no changes to output format or downstream analysis

**Full batch status:**

| Interface | Batch Mode | CoEval Implementation | Discount |
|-----------|-----------|----------------------|---------|
| `openai` | OpenAI Batch API (async) | ✅ `OpenAIBatchRunner` | 50% |
| `anthropic` | Message Batches API (async) | ✅ `AnthropicBatchRunner` | 50% |
| `azure_openai` | Azure Global Batch (async) | ✅ `AzureBatchRunner` | 50% |
| `mistral` | Mistral Batch API (async, OpenAI-compat) | ✅ `MistralBatchRunner` | ~50% |
| `bedrock` | AWS Model Invocation Jobs (async) | ✅ `BedrockBatchRunner` | ~50% |
| `vertex` | Vertex AI Batch Prediction (async) | ✅ `VertexBatchRunner` | 50% |
| `gemini` | Concurrent thread pool (pseudo-batch) | ✅ `GeminiBatchRunner` | ❌ none |
| `openrouter` | None (real-time) | N/A | — |
| `cohere` | None (real-time) | N/A | — |
| `huggingface_api` | None (real-time) | N/A | — |
| `huggingface` | None (local GPU) | N/A | — |

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
| gemini-2.0-flash | $0.10 | $0.40 | — |
| gemini-2.0-flash-lite | $0.075 | $0.30 | — |
| gemini-2.5-flash | $0.15 | $0.60 | — |
| gemini-2.5-flash-lite | $0.075 | $0.30 | — |
| gemini-1.5-flash | $0.075 | $0.30 | — |
| gemini-1.5-pro | $1.25 | $5.00 | — |
| gemini-2.5-pro | $1.25 | $10.00 | — |

**No batch discount.** CoEval uses concurrent requests (thread pool) for Gemini — you pay standard per-token rates. Google does not expose a batch discount API comparable to OpenAI or Anthropic.

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

### Mistral AI (Direct)

Direct access to Mistral models with **native Batch API support (~50% off)**. `MistralBatchRunner` is a thin wrapper over `OpenAIBatchRunner` that points the OpenAI SDK at `https://api.mistral.ai/v1` — the batch API format is identical to OpenAI's (same `/v1/files` + `/v1/batches` endpoints).

| Model | Input ($/1M) | Output ($/1M) | Batch (~50% off) |
|-------|-------------|--------------|-----------------|
| mistral-small-latest | $0.10 | $0.30 | ✅ $0.05 / $0.15 |
| mistral-large-latest | $2.00 | $6.00 | ✅ $1.00 / $3.00 |
| codestral-latest | $0.20 | $0.60 | ✅ $0.10 / $0.30 |
| ministral-8b-latest | $0.10 | $0.10 | ✅ $0.05 / $0.05 |
| open-mistral-nemo | $0.15 | $0.15 | ✅ $0.075 / $0.075 |
| pixtral-12b-2409 | $0.15 | $0.15 | ✅ $0.075 / $0.075 |

**Enable batch in config:**
```yaml
experiment:
  batch:
    mistral:
      response_collection: true
      evaluation: true
```

#### Async Batch (✅ `MistralBatchRunner`)

Mistral's Batch API follows the same OpenAI-compatible format: upload a JSONL file to `/v1/files`, create a batch job via `/v1/batches`, poll until complete, download results. CoEval's `MistralBatchRunner` automates the full workflow — no additional setup beyond a valid API key.

**Supported models for batch:** All models listed above. See [Mistral Batch docs](https://docs.mistral.ai/api/#tag/batch) for updates.

**Configuration:**
```yaml
providers:
  mistral: ...   # MISTRAL_API_KEY
```

---

### Cohere

Command R/R+/A family via OpenAI-compatible endpoint. Best for RAG-oriented tasks and long-context reasoning. No batch discount — real-time only.

| Model | Input ($/1M) | Output ($/1M) |
|-------|-------------|--------------|
| command-a-03-2025 | $2.50 | $10.00 |
| command-r-plus-08-2024 | $2.50 | $10.00 |
| command-r-08-2024 | $0.15 | $0.60 |
| command-r7b-12-2024 | $0.04 | $0.15 |

**Configuration:**
```yaml
providers:
  cohere: co-...   # COHERE_API_KEY
```

---

### HuggingFace Inference API

Serverless pay-per-token inference for 50k+ Hub models. Rates depend on model size.

| Model | Input & Output ($/1M) |
|-------|----------------------|
| meta-llama/Llama-3.1-8B-Instruct | $0.06 |
| meta-llama/Llama-3.3-70B-Instruct | $0.23 |
| mistralai/Mistral-7B-Instruct-v0.3 | $0.04 |
| Qwen/Qwen2.5-72B-Instruct | $0.23 |
| google/gemma-2-9b-it | $0.06 |

HuggingFace PRO subscribers receive free monthly quota on many popular models. See [HuggingFace pricing](https://huggingface.co/pricing#serverless) for the full model list and rates.

**Configuration:**
```yaml
providers:
  huggingface_api: hf_...   # HF_TOKEN (same token as huggingface interface)
```

---

### AWS Bedrock

CoEval supports two Bedrock authentication modes for real-time inference:

**Native API key (for real-time inference):**
```yaml
providers:
  bedrock:
    api_key: BedrockAPIKey-...:...
    region: us-east-1
```

**IAM credentials (also required for batch inference):**
```yaml
providers:
  bedrock:
    access_key_id: AKIA...
    secret_access_key: ...
    region: us-east-1
    batch_role_arn: arn:aws:iam::123456789012:role/BedrockBatchRole  # for batch
```

> **Note:** The native API key is only for the real-time Converse API. Batch inference
> (Model Invocation Jobs) requires IAM auth and an IAM service role. Both can coexist —
> CoEval uses the native key for real-time calls and IAM creds for batch.

#### Async Batch Inference (✅ `BedrockBatchRunner`)

AWS Bedrock's **Model Invocation Jobs API** provides ~50% off for supported models. CoEval's `BedrockBatchRunner` automates the full workflow — upload JSONL to S3, submit the job, poll, download results.

**Additional model parameters required:**
```yaml
- name: claude-bedrock
  interface: bedrock
  batch_enabled: true
  parameters:
    model: anthropic.claude-3-5-haiku-20241022-v1:0
    region: us-east-1
    batch_s3_bucket: my-coeval-batch-bucket   # required: S3 bucket in same region
    batch_s3_prefix: coeval-jobs              # optional (default: "coeval")
    batch_role_arn: arn:aws:iam::123456789012:role/BedrockBatchRole  # required
  roles: [student, judge]
```

**IAM service role setup (one-time):**

1. Create an S3 bucket in the same region as your Bedrock endpoint.
2. Create an IAM role with trust policy for `bedrock.amazonaws.com`:
   ```json
   {
     "Effect": "Allow",
     "Principal": {"Service": "bedrock.amazonaws.com"},
     "Action": "sts:AssumeRole",
     "Condition": {"StringEquals": {"aws:SourceAccount": "<ACCOUNT_ID>"}}
   }
   ```
3. Attach an inline policy granting S3 access to the bucket:
   ```json
   {"Effect": "Allow",
    "Action": ["s3:GetObject", "s3:PutObject", "s3:ListBucket"],
    "Resource": ["arn:aws:s3:::my-coeval-batch-bucket",
                 "arn:aws:s3:::my-coeval-batch-bucket/*"]}
   ```
4. Copy the role ARN (`arn:aws:iam::<account>:role/<name>`) into `batch_role_arn`.

**Supported models:** Anthropic Claude, Amazon Nova, Meta Llama 3.x, Mistral Large, AI21 Jamba.
Not all models are available in all regions — see [AWS Batch Inference docs](https://docs.aws.amazon.com/bedrock/latest/userguide/batch-inference-supported.html).

Selected Bedrock model prices:

| Model | Input ($/1M) | Output ($/1M) | Batch (~50% off) |
|-------|-------------|--------------|-----------------|
| anthropic.claude-3-5-haiku-20241022-v1 | $0.80 | $4.00 | ✅ ~$0.40 / $2.00 |
| anthropic.claude-3-5-sonnet-20241022-v2 | $3.00 | $15.00 | ✅ ~$1.50 / $7.50 |
| amazon.nova-micro-v1 | $0.035 | $0.14 | ✅ ~$0.018 / $0.07 |
| amazon.nova-lite-v1 | $0.06 | $0.24 | ✅ ~$0.03 / $0.12 |
| amazon.nova-pro-v1 | $0.80 | $3.20 | ✅ ~$0.40 / $1.60 |
| meta.llama3-70b-instruct-v1 | $0.99 | $0.99 | ✅ ~$0.50 / $0.50 |

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
    # Optional: service account key file path (default: ADC)
    # service_account_key: /path/to/sa-key.json
```

Requires Application Default Credentials (run `gcloud auth application-default login`). Supports the same Gemini models as the Gemini AI Studio interface with enterprise-grade SLAs.

#### Async Batch Prediction (✅ `VertexBatchRunner`)

Vertex AI **Batch Prediction Jobs** offer 50% off for Gemini models. CoEval's `VertexBatchRunner` uploads a JSONL file to GCS, submits the batch job, polls until completion, and downloads results.

**Additional model parameters required:**
```yaml
- name: gemini-vertex
  interface: vertex
  batch_enabled: true
  parameters:
    model: gemini-2.0-flash-001
    project: my-gcp-project
    location: us-central1
    batch_gcs_bucket: gs://my-coeval-batch-bucket   # required for batch
    batch_gcs_prefix: coeval-jobs                   # optional (default: "coeval")
  roles: [student, judge]
```

**Prerequisites:**
- A GCS bucket in the same region as the Vertex AI endpoint
- IAM permissions on the service account: `aiplatform.batchPredictionJobs.create`, `aiplatform.batchPredictionJobs.get`, `storage.objects.create/get`, `storage.buckets.get`
- `pip install google-cloud-aiplatform google-cloud-storage`

**Supported Gemini models for batch:** Gemini 2.5 Pro/Flash, Gemini 2.0 Flash, Gemini 1.5 Pro/Flash. See [Vertex Batch docs](https://cloud.google.com/vertex-ai/docs/generative-ai/batch-requests) for updates.

Selected Vertex AI (Gemini) model prices:

| Model | Input ($/1M) | Output ($/1M) | Batch (50% off) |
|-------|-------------|--------------|-----------------|
| gemini-2.0-flash-001 | $0.10 | $0.40 | ✅ $0.05 / $0.20 |
| gemini-2.5-flash | $0.15 | $0.60 | ✅ $0.075 / $0.30 |
| gemini-1.5-flash | $0.075 | $0.30 | ✅ $0.038 / $0.15 |
| gemini-1.5-pro | $1.25 | $5.00 | ✅ $0.63 / $2.50 |

### Why Open Models Use OpenRouter (Not a Batch Provider)

The async batch discounts are **exclusive to each provider's own proprietary models**:

| Batch discount | Applies to |
|----------------|-----------|
| OpenAI Batch API (50%) | GPT-4o, GPT-4o-mini, GPT-4.1, o-series only |
| Anthropic Message Batches (50%) | Claude 3.x / Claude 4.x only |
| Azure Global Batch (50%) | GPT-4o, GPT-4o-mini (Azure deployments) |
| Mistral Batch API (~50%) | All Mistral-hosted models via `interface: mistral` |
| AWS Bedrock Batch (~50%) | Claude, Amazon Nova, Llama, Mistral on Bedrock |
| Vertex AI Batch Prediction (50%) | Gemini 1.5 / 2.0 / 2.5 models on GCP |
| **Gemini AI Studio** (concurrent, no discount) | Gemini models — thread pool only |
| **Open-weight models via OpenRouter / DeepInfra / Cerebras** | **No batch discount** |

For `interface: auto`, frontier models are automatically routed to their native batch-enabled provider. Open-weight models go to OpenRouter because no third-party hosting provider offers a batch discount for them. OpenRouter at $0.04–$0.12/M is already the cheapest option for these models.

> **Mistral exception:** Unlike other open-weight model providers, Mistral AI offers ~50% off on its own hosted models via `interface: mistral`. If you are using Mistral Small, Mistral Large, or Codestral, prefer `interface: mistral` with batch enabled over `interface: openrouter`.

---

## `interface: auto` Routing

Setting `interface: auto` in a model configuration tells CoEval to automatically select the **cheapest available provider** for the given model, based on:

1. The `auto_routing` table in `Config/provider_pricing.yaml`
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

**How to update the routing table:** Edit `Config/provider_pricing.yaml` and modify the `auto_routing` section (entries are ordered cheapest-first):

```yaml
auto_routing:
  deepseek/deepseek-r1: {interface: openrouter, notes: "reasoning model"}
  deepseek:             {interface: openrouter, notes: "default deepseek"}
```

**To update prices:** Edit `Config/provider_pricing.yaml` — find the model under its `providers:` block and update `input:` / `output:` values. The cost estimator loads this file at runtime. The hardcoded `PRICE_TABLE` in `cost_estimator.py` is only a fallback if the YAML is unavailable.

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
  cohere:      co-...
  huggingface_api: hf_...   # same token as huggingface; accepts HF_TOKEN or HUGGINGFACE_HUB_TOKEN

  # Ollama — no key needed; only set if using a non-default host
  ollama:
    base_url: http://192.168.1.50:11434/v1   # optional

  azure_openai:
    api_key:     ...
    endpoint:    https://my-resource.openai.azure.com/
    api_version: 2024-08-01-preview

  bedrock:
    api_key: BedrockAPIKey-...:...    # native API key (no boto3 needed; real-time only)
    region:  us-east-1
  # — OR — IAM credentials (supports both real-time and batch):
  # bedrock:
  #   access_key_id:     AKIA...
  #   secret_access_key: ...
  #   region:            us-east-1
  #   batch_role_arn:    arn:aws:iam::123456789012:role/BedrockBatchRole  # for batch

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

## Frequently Asked Questions

**Q: Does Gemini get a 50% batch discount like OpenAI and Anthropic?**
A: It depends on the interface. When you use `interface: gemini` (Google AI Studio), CoEval's `GeminiBatchRunner` submits requests concurrently via a thread pool — faster than sequential calls but at standard per-token rates with **no batch discount**. However, if you access Gemini models via `interface: vertex` (Google Cloud Vertex AI), Vertex AI Batch Prediction Jobs **do** provide a ~50% cost reduction. See the [Vertex AI section](#google-vertex-ai) for setup details.

**Q: How do I use Ollama for local models without any API key?**
A: Install Ollama from https://ollama.com, pull a model (e.g., `ollama pull llama3.2`), and set `interface: ollama` in your config with `model: llama3.2`. No API key is required. If your Ollama server is on a different host or port, set `base_url: http://<host>:11434/v1` either in the model parameters or in `keys.yaml` under `providers.ollama.base_url`.

**Q: Which providers support the 50% batch discount?**
A: Six interfaces support true asynchronous batch processing with a ~50% cost discount: `openai` (OpenAI Batch API), `anthropic` (Message Batches API), `azure_openai` (Azure Global Batch API), `mistral` (Mistral Batch API — same OpenAI-compatible format, no extra setup), `bedrock` (AWS Model Invocation Jobs), and `vertex` (Vertex AI Batch Prediction Jobs). `gemini` uses a concurrent thread pool (faster than sequential, but no discount). Enable batch per-phase in the `experiment.batch` config block.

**Q: What is `interface: auto` and how does it pick a provider?**
A: `interface: auto` tells CoEval to select the cheapest available provider for the given model at config load time. It scans the `auto_routing` table in `Config/provider_pricing.yaml` top-to-bottom and picks the first interface for which credentials exist in your key file. The resolved interface is logged at DEBUG level, and `coeval plan` shows the selected provider before any calls are made.

**Q: What is the difference between using Bedrock with a native API key vs. IAM credentials?**
A: Bedrock's native API key mode (`api_key: BedrockAPIKey-...:...`) uses direct HTTP with an `x-amzn-bedrock-key` header and requires no extra library — it works with CoEval's core install. IAM credentials (`access_key_id` + `secret_access_key`) use the `boto3` SDK, which must be installed separately with `pip install boto3`. Native API key takes priority if both are present. **Note:** For Bedrock batch jobs, IAM credentials are always required — the native API key cannot be used to manage Model Invocation Jobs.

**Q: How do I set up Bedrock or Vertex batch jobs?**
A: Both require cloud storage for job I/O and a service identity with write access:
- **Bedrock:** Create an S3 bucket and an IAM role that trusts `bedrock.amazonaws.com` with `s3:GetObject`/`s3:PutObject`/`s3:ListBucket`. Add `batch_s3_bucket` and `batch_role_arn` to the model's `parameters` block (see [AWS Bedrock](#aws-bedrock)).
- **Vertex:** Create a GCS bucket and enable Vertex AI in your project. Add `batch_gcs_bucket` and `project` to the model's `parameters` block. Authentication uses Application Default Credentials (`gcloud auth application-default login`) or a service account key file (see [Google Vertex AI](#google-vertex-ai)).

**Q: Can I access open-weight models like Llama or Mistral without managing individual provider accounts?**
A: Yes — use `interface: openrouter`. OpenRouter provides a single OpenAI-compatible API and a single key covering 300+ models including Llama, Mistral, Qwen, DeepSeek, Cohere, and Gemma. It is the recommended interface for open-weight models when you want broad model access without juggling multiple API keys.

---

[← Configuration](04-configuration.md) · [Running Experiments →](06-running.md)
