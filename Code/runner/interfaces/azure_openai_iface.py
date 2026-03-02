"""Azure OpenAI interface (REQ-10.x).

Drop-in replacement for OpenAIInterface that targets an Azure OpenAI resource.
Uses the same ``openai`` Python library with ``AzureOpenAI`` client.

Authentication
--------------
In decreasing priority:
  1. ``access_key`` field on the model config (maps to ``api_key``)
  2. ``azure_openai.api_key`` in the provider key file
  3. ``AZURE_OPENAI_API_KEY`` environment variable

Additionally required (from ``parameters`` dict or provider key file or env):
  - ``azure_endpoint`` / ``AZURE_OPENAI_ENDPOINT`` — the resource endpoint URL
  - ``api_version``  / ``AZURE_OPENAI_API_VERSION`` — defaults to ``2024-08-01-preview``

YAML example::

    models:
      - name: gpt4o-azure
        interface: azure_openai
        parameters:
          model: gpt-4o            # deployment name in your Azure resource
          azure_endpoint: https://my-resource.openai.azure.com/
          api_version: 2024-08-01-preview
          temperature: 0.7
          max_tokens: 512
        roles: [teacher, student, judge]
        # access_key: <azure api key>   # or set AZURE_OPENAI_API_KEY

Batch support
-------------
Azure OpenAI Batch API is structurally identical to the OpenAI Batch API.
Set ``batch_enabled: true`` on the model to activate it.
"""
from __future__ import annotations

import os
import time

from .base import ModelInterface

_RETRY_ERRORS = ('rate limit', 'timeout', 'connection', '429', '503', '504')
_FATAL_ERRORS = ('invalid api key', 'authentication', 'authorization', 'model not found', '404', '401')


class AzureOpenAIInterface(ModelInterface):
    """Chat Completions via Azure OpenAI with exponential-backoff retry."""

    def __init__(
        self,
        api_key: str | None = None,
        azure_endpoint: str | None = None,
        api_version: str | None = None,
    ) -> None:
        try:
            import openai
        except ImportError:
            raise ImportError(
                "openai>=1.0 is required for the Azure OpenAI interface: pip install openai"
            )

        resolved_key = api_key or os.environ.get('AZURE_OPENAI_API_KEY')
        resolved_endpoint = azure_endpoint or os.environ.get('AZURE_OPENAI_ENDPOINT')
        resolved_version = (
            api_version
            or os.environ.get('AZURE_OPENAI_API_VERSION')
            or '2024-08-01-preview'
        )

        if not resolved_key:
            raise ValueError(
                "Azure OpenAI API key not found.  Set AZURE_OPENAI_API_KEY, "
                "add 'access_key' to the model config, or define "
                "'azure_openai.api_key' in your provider key file."
            )
        if not resolved_endpoint:
            raise ValueError(
                "Azure OpenAI endpoint not found.  Set AZURE_OPENAI_ENDPOINT, "
                "add 'azure_endpoint' to model parameters, or define "
                "'azure_openai.endpoint' in your provider key file."
            )

        self._client = openai.AzureOpenAI(
            api_key=resolved_key,
            azure_endpoint=resolved_endpoint,
            api_version=resolved_version,
        )

    def generate(self, prompt: str, parameters: dict) -> str:
        params = dict(parameters)
        model = params.pop('model')
        params.pop('azure_endpoint', None)
        params.pop('api_version', None)
        system_prompt = params.pop('system_prompt', None)
        temperature = params.pop('temperature', 0.7)
        max_tokens = params.pop('max_tokens', params.pop('max_new_tokens', None))

        messages = []
        if system_prompt:
            messages.append({'role': 'system', 'content': system_prompt})
        messages.append({'role': 'user', 'content': prompt})

        call_kwargs: dict = {'model': model, 'messages': messages, 'temperature': temperature}
        if max_tokens:
            call_kwargs['max_tokens'] = max_tokens

        delay = 1.0
        for attempt in range(3):
            try:
                response = self._client.chat.completions.create(**call_kwargs)
                return response.choices[0].message.content or ''
            except Exception as exc:
                msg = str(exc).lower()
                if any(e in msg for e in _FATAL_ERRORS):
                    raise
                if attempt < 2 and any(e in msg for e in _RETRY_ERRORS):
                    time.sleep(delay)
                    delay *= 2
                    continue
                raise
        raise RuntimeError('Azure OpenAI generate failed after 3 attempts')
