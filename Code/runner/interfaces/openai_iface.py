"""OpenAI model interface (REQ-10.2)."""
from __future__ import annotations

import os
import time

from .base import ModelInterface

# Transient error substrings (case-insensitive) that warrant a retry
_TRANSIENT_SIGNALS = ('rate limit', 'timeout', 'connection', '502', '503', '504', '529')
# Non-transient signals that should fail immediately
_FATAL_SIGNALS = ('invalid api key', 'authentication', 'model not found', 'does not exist')


class OpenAIInterface(ModelInterface):
    """Calls the OpenAI Chat Completions API with exponential-backoff retry (REQ-10.4)."""

    def __init__(self, access_key: str | None = None) -> None:
        try:
            from openai import OpenAI
        except ImportError:
            raise ImportError("openai package is required: pip install openai")
        key = access_key or os.environ.get('OPENAI_API_KEY')
        self._client = OpenAI(api_key=key)

    def generate(self, prompt: str, parameters: dict) -> str:
        params = dict(parameters)
        model = params.pop('model')
        system_prompt = params.pop('system_prompt', None)
        temperature = params.pop('temperature', 0.7)
        max_tokens = params.pop('max_tokens', None)

        messages = []
        if system_prompt:
            messages.append({'role': 'system', 'content': system_prompt})
        messages.append({'role': 'user', 'content': prompt})

        kwargs: dict = {'model': model, 'messages': messages, 'temperature': temperature}
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
