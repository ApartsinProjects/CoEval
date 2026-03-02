# experiments/interfaces/ — Model Interface Modules

This directory contains the interface layer between the CoEval pipeline and external LLM providers. Each module implements the `ModelInterface` base class defined in [`base.py`](base.py).

## Core Infrastructure

| File | Description |
|------|-------------|
| [`base.py`](base.py) | Abstract `ModelInterface` base class; defines `generate()` and `batch_generate()` |
| [`pool.py`](pool.py) | `ModelPool` factory — instantiates the correct interface for each model; accepts `provider_keys: dict` |
| [`registry.py`](registry.py) | Key file loading (`load_keys_file`), credential resolution (`resolve_provider_keys`), model listing (`list_provider_models`) |
| [`probe.py`](probe.py) | `probe_model()` — tests model availability before a run; supports all interfaces |
| [`cost_estimator.py`](cost_estimator.py) | `estimate_experiment_cost()` — pre-flight cost/time estimation using `PRICE_TABLE` |

## Provider Interfaces

| File | Interface ID | Provider | Batching | Auth env var |
|------|-------------|----------|----------|--------------|
| [`openai_iface.py`](openai_iface.py) | `openai` | OpenAI | OpenAI Batch API (50% off) | `OPENAI_API_KEY` |
| [`anthropic_iface.py`](anthropic_iface.py) | `anthropic` | Anthropic | Message Batches API (50% off) | `ANTHROPIC_API_KEY` |
| [`gemini_iface.py`](gemini_iface.py) | `gemini` | Google Gemini AI Studio | Gemini Batch API (50% off) | `GEMINI_API_KEY` or `GOOGLE_API_KEY` |
| [`huggingface_iface.py`](huggingface_iface.py) | `huggingface` | HuggingFace local | None (GPU required) | `HF_TOKEN` |
| [`azure_openai_iface.py`](azure_openai_iface.py) | `azure_openai` | Azure OpenAI | Azure Global Batch (50% off) | `AZURE_OPENAI_API_KEY` + `AZURE_OPENAI_ENDPOINT` |
| [`bedrock_iface.py`](bedrock_iface.py) | `bedrock` | AWS Bedrock | None yet (real-time only) | Native `api_key` or IAM env vars |
| [`vertex_iface.py`](vertex_iface.py) | `vertex` | Google Vertex AI | Routes to `gemini` | `GOOGLE_CLOUD_PROJECT` + ADC |
| [`openrouter_iface.py`](openrouter_iface.py) | `openrouter` | OpenRouter (meta-router) | None (real-time) | `OPENROUTER_API_KEY` |
| [`openai_compat_iface.py`](openai_compat_iface.py) | `groq`, `deepseek`, `mistral`, `deepinfra`, `cerebras` | Multiple OpenAI-compatible providers | None (real-time) | Provider-specific env vars |

## Batch Runner Modules

| File | Description |
|------|-------------|
| [`openai_batch.py`](openai_batch.py) | OpenAI Batch API runner — submit, poll, retrieve |
| [`anthropic_batch.py`](anthropic_batch.py) | Anthropic Message Batches runner |
| [`gemini_batch.py`](gemini_batch.py) | Gemini Batch API runner |
| [`azure_batch.py`](azure_batch.py) | Azure Global Batch runner (`AzureBatchRunner`) |

## OpenAI-Compatible Providers (openai_compat_iface.py)

The `openai_compat_iface.py` module covers any provider with an OpenAI-compatible chat completions API:

| Provider | Interface ID | API Base URL | Env var |
|----------|-------------|--------------|---------|
| Groq | `groq` | `https://api.groq.com/openai/v1` | `GROQ_API_KEY` |
| DeepSeek | `deepseek` | `https://api.deepseek.com/v1` | `DEEPSEEK_API_KEY` |
| Mistral | `mistral` | `https://api.mistral.ai/v1` | `MISTRAL_API_KEY` |
| DeepInfra | `deepinfra` | `https://api.deepinfra.com/v1/openai` | `DEEPINFRA_API_KEY` |
| Cerebras | `cerebras` | `https://api.cerebras.ai/v1` | `CEREBRAS_API_KEY` |

Configure any of these in `keys.yaml`:

```yaml
providers:
  groq: gsk-...
  deepseek: sk-...
  mistral: ...
  deepinfra: di-...
  cerebras: csk-...
```

## Adding a New Interface

1. Create `<provider>_iface.py` (copy `openrouter_iface.py` for OpenAI-compat providers)
2. Add the interface ID to `VALID_INTERFACES` in `experiments/config.py`
3. Register in `ModelPool` factory in [`pool.py`](pool.py)
4. Add to `probe.py` supported providers list
5. Add pricing block to `benchmark/provider_pricing.yaml`

See [`docs/README/05-providers.md`](../../docs/README/05-providers.md) for provider details and pricing tables.
