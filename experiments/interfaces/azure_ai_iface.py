"""Azure AI interface — access 100+ models via Azure AI Foundry / GitHub Models.

Provides access to open-weight and proprietary models hosted on Azure AI Foundry
(formerly Azure AI Studio) and the GitHub Models marketplace.  Both services expose
an **OpenAI-compatible** Chat Completions API, so this interface uses the standard
``openai`` SDK with a configurable ``base_url``.

Supported model families
------------------------
Phi-4, Phi-3, Llama 3.1/3.3, Mistral Large/Small/NeMo, Cohere Command R+,
AI21 Jamba, xAI Grok, DeepSeek, Qwen, and many more.

Authentication
--------------
In decreasing priority:

  1. ``access_key`` on the model config (YAML)
  2. ``azure_ai.api_key`` in the provider key file
  3. ``AZURE_AI_API_KEY`` environment variable
  4. ``GITHUB_TOKEN`` environment variable  (free tier via GitHub Models)

Endpoint
--------
The default endpoint is the **GitHub Models / Azure AI Foundry** inference endpoint::

    https://models.inference.ai.azure.com

For a dedicated Azure AI Foundry deployment, override with ``azure_endpoint``
in model parameters or ``azure_ai.endpoint`` in the key file::

    https://my-deployment.eastus.inference.ai.azure.com

YAML examples::

    # GitHub Models (free tier — ideal for experimentation)
    models:
      - name: phi4
        interface: azure_ai
        parameters:
          model: Phi-4
          temperature: 0.7
          max_tokens: 512
        roles: [teacher, student, judge]

      - name: llama-3-70b
        interface: azure_ai
        parameters:
          model: meta/llama-3.1-70b-instruct
          temperature: 0.8
          max_tokens: 1024
        roles: [teacher, student]

      - name: mistral-large
        interface: azure_ai
        parameters:
          model: mistral-ai/mistral-large-2411
          temperature: 0.7
          max_tokens: 512
        roles: [judge]

    # Dedicated Azure AI Foundry endpoint
      - name: my-custom-model
        interface: azure_ai
        parameters:
          model: my-deployment-name
          azure_endpoint: https://my-resource.eastus.inference.ai.azure.com
          temperature: 0.7

Provider key file entry::

    azure_ai:
      api_key: ghp_...           # GitHub PAT  OR  Azure AI API key
      endpoint: https://models.inference.ai.azure.com   # optional override

Popular model IDs (GitHub Models / Azure AI Foundry)
-----------------------------------------------------
* ``Phi-4``, ``Phi-3.5-MoE-instruct``, ``Phi-3.5-mini-instruct``
* ``meta/llama-3.1-70b-instruct``, ``meta/llama-3.3-70b-instruct``
* ``mistral-ai/mistral-large-2411``, ``mistral-ai/mistral-small-2503``
* ``cohere/command-r-plus-08-2024``
* ``ai21-labs/jamba-1.5-large``
* ``xai/grok-3-mini``
* ``deepseek/deepseek-r1``
* ``openai/gpt-4o`` (pay-as-you-go tier only)

Browse all models at https://github.com/marketplace/models
"""
from __future__ import annotations

import os
import time

from .base import ModelInterface

_DEFAULT_ENDPOINT = "https://models.inference.ai.azure.com"
_TRANSIENT_SIGNALS = ('rate limit', 'timeout', 'connection', '429', '502', '503', '504', '529')
_FATAL_SIGNALS = ('invalid api key', 'authentication', 'model not found', 'does not exist', '401', '403')


class AzureAIInterface(ModelInterface):
    """Chat completions via Azure AI Foundry / GitHub Models (OpenAI-compatible).

    Uses the ``openai`` SDK pointed at the Azure AI inference endpoint.
    Automatically retries on transient errors with exponential backoff.
    """

    def __init__(
        self,
        access_key: str | None = None,
        azure_endpoint: str | None = None,
    ) -> None:
        try:
            from openai import OpenAI
        except ImportError:
            raise ImportError("openai package is required: pip install openai")

        key = (
            access_key
            or os.environ.get('AZURE_AI_API_KEY')
            or os.environ.get('GITHUB_TOKEN')
        )
        if not key:
            raise ValueError(
                "Azure AI API key not found.  Set AZURE_AI_API_KEY, GITHUB_TOKEN, "
                "add 'access_key' to the model config, or define "
                "'azure_ai.api_key' in your provider key file."
            )

        endpoint = azure_endpoint or _DEFAULT_ENDPOINT

        self._client = OpenAI(api_key=key, base_url=endpoint)

    def generate(self, prompt: str, parameters: dict) -> str:
        params = dict(parameters)
        model = params.pop('model')
        system_prompt = params.pop('system_prompt', None)
        temperature = params.pop('temperature', 0.7)
        max_tokens = params.pop('max_tokens', None)
        # Strip Azure-specific non-inference keys
        params.pop('azure_endpoint', None)

        messages = []
        if system_prompt:
            messages.append({'role': 'system', 'content': system_prompt})
        messages.append({'role': 'user', 'content': prompt})

        kwargs: dict = {
            'model': model,
            'messages': messages,
            'temperature': temperature,
        }
        if max_tokens is not None:
            kwargs['max_tokens'] = max_tokens
        kwargs.update(params)

        delay = 1.0
        last_err: Exception | None = None
        for attempt in range(3):
            try:
                response = self._client.chat.completions.create(**kwargs)
                return response.choices[0].message.content.strip()
            except Exception as exc:
                err_lower = str(exc).lower()
                if any(sig in err_lower for sig in _FATAL_SIGNALS):
                    raise
                last_err = exc
                if attempt < 2:
                    time.sleep(delay)
                    delay *= 2
        raise last_err  # type: ignore[misc]
