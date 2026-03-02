"""Generic OpenAI-compatible interface for multiple inference providers.

Covers any provider that exposes an OpenAI chat-completions REST API, including:

  - Groq      (https://api.groq.com/openai/v1)       — ~500 tok/s; price-competitive
  - DeepSeek  (https://api.deepseek.com/v1)           — $0.07/$0.28 per 1M for V3
  - Mistral   (https://api.mistral.ai/v1)              — direct; avoids OpenRouter markup
  - DeepInfra (https://api.deepinfra.com/v1/openai)   — competitive open-model pricing
  - Cerebras  (https://api.cerebras.ai/v1)             — 1000+ tok/s wafer-scale hardware

All providers share the same OpenAI-SDK-compatible interface. Credentials are
resolved from: model-level access_key → provider key file → environment variable.

Key file format (keys.yaml)::

    providers:
      groq:      gsk-...
      deepseek:  sk-...
      mistral:   ...
      deepinfra: di-...
      cerebras:  csk-...
"""
from __future__ import annotations

import os
import time

from .base import ModelInterface

# ---------------------------------------------------------------------------
# Provider registry
# ---------------------------------------------------------------------------

#: interface_name → (base_url, env_var_name, display_label)
_REGISTRY: dict[str, tuple[str, str, str]] = {
    'groq':      ('https://api.groq.com/openai/v1',      'GROQ_API_KEY',      'Groq'),
    'deepseek':  ('https://api.deepseek.com/v1',          'DEEPSEEK_API_KEY',  'DeepSeek'),
    'mistral':   ('https://api.mistral.ai/v1',            'MISTRAL_API_KEY',   'Mistral'),
    'deepinfra': ('https://api.deepinfra.com/v1/openai',  'DEEPINFRA_API_KEY', 'DeepInfra'),
    'cerebras':  ('https://api.cerebras.ai/v1',           'CEREBRAS_API_KEY',  'Cerebras'),
}

_TRANSIENT = ('rate limit', 'timeout', 'connection', '502', '503', '504', '529')
_FATAL     = ('invalid api key', 'authentication', 'model not found', 'does not exist')


def supported_interfaces() -> list[str]:
    """Return the interface names handled by this module (alphabetically sorted)."""
    return sorted(_REGISTRY)


class OpenAICompatInterface(ModelInterface):
    """Chat completions via any OpenAI-compatible REST endpoint.

    Pass the ``interface`` name (e.g. ``'groq'``) to select the provider.
    The ``base_url`` and required environment variable are looked up from
    :data:`_REGISTRY` automatically.

    Parameters
    ----------
    interface:
        One of ``'groq'``, ``'deepseek'``, ``'mistral'``, ``'deepinfra'``,
        ``'cerebras'``.
    access_key:
        Optional API key override; falls back to the provider's env var.

    Raises
    ------
    ValueError
        If ``interface`` is not registered or no API key is available.
    ImportError
        If the ``openai`` package is not installed.
    """

    def __init__(
        self,
        interface: str,
        access_key: str | None = None,
    ) -> None:
        if interface not in _REGISTRY:
            raise ValueError(
                f"Unknown OpenAI-compat interface '{interface}'. "
                f"Registered providers: {sorted(_REGISTRY)}"
            )
        base_url, env_key, label = _REGISTRY[interface]
        try:
            from openai import OpenAI
        except ImportError:
            raise ImportError("openai package is required: pip install openai")

        key = access_key or os.environ.get(env_key)
        if not key:
            raise ValueError(
                f"{label} API key not found. "
                f"Set the {env_key} environment variable or add "
                f"'{interface}' to your provider key file."
            )
        self._client = OpenAI(api_key=key, base_url=base_url)
        self._label  = label

    def generate(self, prompt: str, parameters: dict) -> str:
        params = dict(parameters)
        model  = params.pop('model')
        system = params.pop('system_prompt', None)
        temp   = params.pop('temperature', 0.7)
        max_t  = params.pop('max_tokens', None)

        messages: list[dict] = []
        if system:
            messages.append({'role': 'system', 'content': system})
        messages.append({'role': 'user', 'content': prompt})

        kwargs: dict = {'model': model, 'messages': messages, 'temperature': temp}
        if max_t is not None:
            kwargs['max_tokens'] = max_t
        kwargs.update(params)

        delay, last_err = 1.0, None
        for attempt in range(3):
            try:
                resp = self._client.chat.completions.create(**kwargs)
                return resp.choices[0].message.content.strip()
            except Exception as exc:
                el = str(exc).lower()
                if any(s in el for s in _FATAL):
                    raise
                last_err = exc
                if attempt < 2:
                    time.sleep(delay)
                    delay *= 2
        raise last_err  # type: ignore[misc]
