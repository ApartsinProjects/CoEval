# Installation

[← Architecture](03-architecture.md) · [Quick Start →](05-quick-start.md)

---

## Requirements

- **Python ≥ 3.10**
- An API key for at least one supported provider (or a local GPU for HuggingFace models)

## Core Installation

The core package includes all cloud interfaces (OpenAI, Anthropic, Gemini, Azure, Bedrock, Vertex, OpenRouter, Groq, DeepSeek, Mistral, DeepInfra, Cerebras) with no extra dependencies beyond the OpenAI SDK and PyYAML.

```bash
# Clone and install in editable mode
git clone https://github.com/ApartsinProjects/CoEval
cd CoEval
pip install -e .
```

## Optional Extras

Install only the extras you need:

```bash
# Local HuggingFace model support (requires GPU recommended)
pip install -e ".[huggingface]"

# Parquet export for analysis outputs
pip install -e ".[parquet]"

# Both
pip install -e ".[huggingface,parquet]"
```

## Provider SDK Dependencies

The OpenAI SDK is included in the core install. For other cloud providers, install only the SDKs you need:

```bash
pip install anthropic                  # Anthropic Claude (Claude 3.5, Claude 3)
pip install google-genai               # Google Gemini (AI Studio)
pip install google-cloud-aiplatform    # Google Vertex AI (Gemini on GCP)
pip install boto3                      # AWS Bedrock — IAM auth only
                                       # (native API key auth requires no extra install)
```

> **Tip:** Bedrock's native API key mode (`api_key: BedrockAPIKey-...:...`) requires no `boto3` install. Only the IAM credential path (`access_key_id` + `secret_access_key`) needs `boto3`.

```bash
# OpenAI-compatible providers (Groq, DeepSeek, Mistral, DeepInfra, Cerebras)
# No extra SDK needed — they use the openai package already installed
# Just add your API keys to keys.yaml:
#   groq:      gsk_...
#   deepseek:  sk-...
#   mistral:   ...
#   deepinfra: di-...
#   cerebras:  csk-...
```

## Verify Installation

```bash
# Show available subcommands
coeval --help

# List models for your configured providers
coeval models --keys ~/.coeval/keys.yaml
```

## Development Setup

```bash
# Install with test dependencies
pip install -e ".[huggingface,parquet]"
pip install pytest playwright

# Install Playwright browser for HTML report tests
playwright install chromium

# Run the full test suite
pytest experiments/tests/ analysis/tests/ -v
```

---

[← Architecture](03-architecture.md) · [Quick Start →](05-quick-start.md)
