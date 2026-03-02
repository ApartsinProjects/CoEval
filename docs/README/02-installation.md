# Installation

[← Overview](01-overview.md) · [Quick Start →](03-quick-start.md)

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

```bash
# Verify GPU (required for local HuggingFace models)
python -c "import torch; print('CUDA:', torch.cuda.is_available())"
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

## Frequently Asked Questions

**Q: What is the minimum Python version required?**
A: CoEval requires Python 3.10 or later. This is enforced at import time — earlier versions will fail with a clear error.

**Q: Do I need to install all provider SDKs upfront?**
A: No. The core install includes the OpenAI SDK and PyYAML, which covers all OpenAI-compatible providers (Groq, DeepSeek, Mistral, DeepInfra, Cerebras, OpenRouter) out of the box. Install only the SDKs you actually need: `pip install anthropic` for Anthropic, `pip install google-genai` for Gemini, `pip install boto3` for Bedrock IAM auth, and `pip install google-cloud-aiplatform` for Vertex AI.

**Q: Do I need a GPU to run CoEval?**
A: Only if you want to run local HuggingFace models. All cloud interfaces (OpenAI, Anthropic, Gemini, etc.) work on any machine with a network connection. For HuggingFace, a CUDA GPU is strongly recommended — CPU inference is very slow for models above ~360M parameters.

**Q: What does `pip install -e ".[huggingface]"` install?**
A: The `huggingface` extra pulls in `transformers`, `torch`, and `accelerate` — everything needed to load and run instruction-tuned models locally via the HuggingFace Hub. The `parquet` extra adds `pyarrow` for Parquet export in the analysis package.

**Q: How do I verify that my installation is working?**
A: Run `coeval --help` to confirm the CLI is installed, then `coeval models --keys ~/.coeval/keys.yaml` to verify that at least one provider is reachable. You can also run the full test suite with `pytest experiments/tests/ analysis/tests/ -v`.

**Q: How do I install the Playwright browser needed for HTML report tests?**
A: After installing `pytest playwright` via pip, run `playwright install chromium`. This downloads the headless Chromium binary used by the 55 Playwright integration tests in `analysis/tests/test_reports_playwright.py`.

---

[← Overview](01-overview.md) · [Quick Start →](03-quick-start.md)
