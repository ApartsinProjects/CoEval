"""Anthropic Claude model interface."""
from __future__ import annotations

import os
import time

from .base import ModelInterface

# Transient errors that warrant a retry
_TRANSIENT_SIGNALS = ('rate_limit_error', 'overloaded', 'timeout', 'connection', '529', '503', '502')
# Non-transient errors that should fail immediately
_FATAL_SIGNALS = ('authentication_error', 'invalid api key', 'api key not valid', 'permission_denied')
# HuggingFace-only params to strip before sending to the API
_STRIP_PARAMS = frozenset({'load_in_4bit', 'load_in_8bit', 'device', 'max_new_tokens'})


class AnthropicInterface(ModelInterface):
    """Calls the Anthropic Messages API with exponential-backoff retry."""

    def __init__(self, access_key: str | None = None) -> None:
        try:
            import anthropic
        except ImportError:
            raise ImportError("anthropic package is required: pip install anthropic")
        key = access_key or os.environ.get('ANTHROPIC_API_KEY')
        self._client = anthropic.Anthropic(api_key=key)

    def generate(self, prompt: str, parameters: dict) -> str:
        params = {k: v for k, v in parameters.items() if k not in _STRIP_PARAMS}
        model = params.pop('model')
        system_prompt = params.pop('system_prompt', None)
        temperature = params.pop('temperature', 0.7)
        # Anthropic requires max_tokens; use a sensible default if unset
        max_tokens = params.pop('max_tokens', 1024)

        kwargs: dict = {
            'model': model,
            'max_tokens': max_tokens,
            'temperature': temperature,
            'messages': [{'role': 'user', 'content': prompt}],
        }
        if system_prompt:
            kwargs['system'] = system_prompt
        kwargs.update(params)  # any remaining provider-specific params

        delay = 1.0
        last_err: Exception | None = None
        for attempt in range(3):
            try:
                response = self._client.messages.create(**kwargs)
                return response.content[0].text.strip()
            except Exception as exc:
                err_lower = str(exc).lower()
                if any(sig in err_lower for sig in _FATAL_SIGNALS):
                    raise
                last_err = exc
                if attempt < 2:
                    time.sleep(delay)
                    delay *= 2
        raise last_err  # type: ignore[misc]
