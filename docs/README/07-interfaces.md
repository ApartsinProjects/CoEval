# Supported Model Interfaces

[← Configuration Guide](06-configuration.md) · [CLI Reference →](08-cli-reference.md)

---

CoEval supports **15 model interfaces** spanning every major cloud provider, OpenAI-compatible APIs, local GPU inference, and virtual benchmark teachers.

## Interface Table

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
Connects to Azure OpenAI deployments. Requires deployment name in `model`, endpoint URL, and API version. No batch discount.

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

## Batch API Details

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
    azure_openai:
      response_collection: true
      evaluation: true
```

Batch jobs are submitted at the start of each phase and polled automatically. Use `coeval status --fetch-batches` to check completion status manually.

---

[← Configuration Guide](06-configuration.md) · [CLI Reference →](08-cli-reference.md)
