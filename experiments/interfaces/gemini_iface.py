"""Google Gemini model interface."""
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
    """Calls the Google Gemini generative AI API with exponential-backoff retry."""

    def __init__(self, access_key: str | None = None) -> None:
        try:
            import google.generativeai as genai
        except ImportError:
            raise ImportError(
                "google-generativeai package is required: pip install google-generativeai"
            )
        key = access_key or os.environ.get('GEMINI_API_KEY') or os.environ.get('GOOGLE_API_KEY')
        genai.configure(api_key=key)
        self._genai = genai

    def generate(self, prompt: str, parameters: dict) -> str:
        params = {k: v for k, v in parameters.items() if k not in _STRIP_PARAMS}
        model_name = params.pop('model')
        system_prompt = params.pop('system_prompt', None)
        temperature = params.pop('temperature', 0.7)
        # Gemini uses max_output_tokens; accept either name
        max_tokens = params.pop('max_tokens', None) or params.pop('max_output_tokens', None)

        gen_config: dict = {'temperature': temperature}
        if max_tokens is not None:
            gen_config['max_output_tokens'] = max_tokens

        model = self._genai.GenerativeModel(
            model_name,
            system_instruction=system_prompt,
            generation_config=gen_config,
        )

        delay = 1.0
        last_err: Exception | None = None
        for attempt in range(3):
            try:
                response = model.generate_content(prompt)
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
