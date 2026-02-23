"""HuggingFace local-inference interface (REQ-10.3)."""
from __future__ import annotations

import os

from .base import ModelInterface


class HuggingFaceInterface(ModelInterface):
    """Loads model weights locally via transformers.pipeline (REQ-10.3).

    The pipeline is created once at construction; subsequent generate() calls
    reuse the loaded weights.  Weights are cached to the HuggingFace Hub cache
    directory on first use.
    """

    def __init__(
        self,
        model_id: str,
        access_key: str | None = None,
        device: str = 'auto',
    ) -> None:
        try:
            from transformers import pipeline
        except ImportError:
            raise ImportError(
                "transformers is required for the HuggingFace interface: "
                "pip install 'coeval[huggingface]'"
            )
        token = access_key or os.environ.get('HF_TOKEN')
        self._pipeline = pipeline(
            'text-generation',
            model=model_id,
            device=device,
            token=token or None,
        )

    def generate(self, prompt: str, parameters: dict) -> str:
        params = dict(parameters)
        params.pop('model', None)   # already loaded at init
        params.pop('device', None)  # already set at init
        temperature = params.pop('temperature', 0.7)
        max_new_tokens = params.pop('max_new_tokens', 512)

        messages = [{'role': 'user', 'content': prompt}]
        outputs = self._pipeline(
            messages,
            temperature=temperature,
            max_new_tokens=max_new_tokens,
            do_sample=temperature > 0,
            **params,
        )

        generated = outputs[0]['generated_text']
        # Chat template returns a list of message dicts; grab the last assistant turn
        if isinstance(generated, list):
            for msg in reversed(generated):
                if isinstance(msg, dict) and msg.get('role') == 'assistant':
                    return msg['content'].strip()
        return str(generated).strip()
