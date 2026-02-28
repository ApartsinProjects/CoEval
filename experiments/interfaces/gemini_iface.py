"""Google Gemini model interface (google-genai SDK)."""
from __future__ import annotations

import os
import time

from .base import ModelInterface

# Transient errors that warrant a retry
_TRANSIENT_SIGNALS = ('quota', 'resource_exhausted', 'timeout', 'unavailable', '503', '429')
# Non-transient errors that should fail immediately
_FATAL_SIGNALS = ('api_key_invalid', 'api key not valid', 'invalid_argument', 'permission_denied')
# HuggingFace-only params to strip before sending to the API
_STRIP_PARAMS = frozenset({'load_in_4bit', 'load_in_8bit', 'device', 'max_new_tokens'})


class GeminiInterface(ModelInterface):
    """Calls the Google Gemini API via the google-genai SDK with exponential-backoff retry."""

    def __init__(self, access_key: str | None = None) -> None:
        try:
            from google import genai
            from google.genai import types as genai_types
        except ImportError:
            raise ImportError(
                "google-genai package is required: pip install google-genai"
            )
        key = access_key or os.environ.get('GEMINI_API_KEY') or os.environ.get('GOOGLE_API_KEY')
        self._client = genai.Client(api_key=key)
        self._types = genai_types

    def generate(self, prompt: str, parameters: dict) -> str:
        params = {k: v for k, v in parameters.items() if k not in _STRIP_PARAMS}
        model_name = params.pop('model')
        system_prompt = params.pop('system_prompt', None)
        temperature = params.pop('temperature', 0.7)
        # Gemini uses max_output_tokens; accept either name
        max_tokens = params.pop('max_tokens', None) or params.pop('max_output_tokens', None)

        gen_config = self._types.GenerateContentConfig(
            temperature=temperature,
            max_output_tokens=max_tokens,
            system_instruction=system_prompt,
        )

        delay = 1.0
        last_err: Exception | None = None
        for attempt in range(3):
            try:
                response = self._client.models.generate_content(
                    model=model_name,
                    contents=prompt,
                    config=gen_config,
                )
                return response.text.strip()
            except Exception as exc:
                err_lower = str(exc).lower()
                if any(sig in err_lower for sig in _FATAL_SIGNALS):
                    raise
                last_err = exc
                if attempt < 2:
                    time.sleep(delay)
                    delay *= 2
        raise last_err  # type: ignore[misc]
