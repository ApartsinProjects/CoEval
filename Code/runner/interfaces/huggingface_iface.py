"""HuggingFace local-inference interface (REQ-10.3)."""
from __future__ import annotations

import os

from .base import ModelInterface


def _require_gpu() -> None:
    """Raise a clear RuntimeError if no CUDA GPU is visible.

    Called once before any model weights are loaded so the failure is immediate
    rather than silently falling back to slow CPU inference.
    """
    try:
        import torch
    except ImportError:
        raise ImportError(
            "torch is required for local HuggingFace models: "
            "pip install 'coeval[huggingface]'"
        )
    if not torch.cuda.is_available():
        raise RuntimeError(
            "\n"
            "╔══════════════════════════════════════════════════════════════╗\n"
            "║  ERROR: No CUDA-capable GPU detected                        ║\n"
            "╠══════════════════════════════════════════════════════════════╣\n"
            "║  Local HuggingFace models must run on GPU.                  ║\n"
            "║                                                              ║\n"
            "║  Troubleshooting:                                            ║\n"
            "║   • Run  nvidia-smi  to verify GPU visibility               ║\n"
            "║   • Ensure CUDA drivers match your PyTorch build            ║\n"
            "║   • In containers: pass  --gpus all  to docker run          ║\n"
            "║   • In Slurm: request  --gres=gpu:1                         ║\n"
            "║                                                              ║\n"
            "║  torch.cuda.is_available() returned False                   ║\n"
            "╚══════════════════════════════════════════════════════════════╝\n"
        )


class HuggingFaceInterface(ModelInterface):
    """Loads model weights locally via transformers.pipeline (REQ-10.3).

    The pipeline is created once at construction; subsequent generate() calls
    reuse the loaded weights.  Weights are cached to the HuggingFace Hub cache
    directory on first use.

    A CUDA GPU is **required**.  If no GPU is available the constructor raises
    RuntimeError with a diagnostic message before any weights are downloaded.
    """

    def __init__(
        self,
        model_id: str,
        access_key: str | None = None,
        device: str = 'auto',
        load_in_4bit: bool = False,
        load_in_8bit: bool = False,
    ) -> None:
        _require_gpu()
        try:
            from transformers import pipeline, BitsAndBytesConfig
        except ImportError:
            raise ImportError(
                "transformers is required for the HuggingFace interface: "
                "pip install 'coeval[huggingface]'"
            )
        token = access_key or os.environ.get('HF_TOKEN') or None

        # Build model_kwargs for quantization (requires bitsandbytes).
        # Passed via model_kwargs so they only reach from_pretrained(), NOT
        # model.generate() — passing quantization_config directly to pipeline()
        # causes it to be forwarded to every generate() call, triggering warnings.
        # Quantization reduces VRAM ~4× (4-bit) or ~2× (8-bit).
        model_kwargs: dict = {}
        if load_in_4bit or load_in_8bit:
            try:
                model_kwargs['quantization_config'] = BitsAndBytesConfig(
                    load_in_4bit=load_in_4bit,
                    load_in_8bit=load_in_8bit,
                )
            except Exception as exc:
                raise RuntimeError(
                    f"4/8-bit quantization requires bitsandbytes: "
                    f"pip install bitsandbytes. Original error: {exc}"
                )

        # "auto" means let transformers pick the best device via device_map;
        # specific values like "cpu" or "cuda" are passed directly as device=.
        if device == 'auto':
            self._pipeline = pipeline(
                'text-generation',
                model=model_id,
                device_map='auto',
                token=token,
                model_kwargs=model_kwargs or None,
            )
        else:
            self._pipeline = pipeline(
                'text-generation',
                model=model_id,
                device=device,
                token=token,
                model_kwargs=model_kwargs or None,
            )

    def release(self) -> None:
        """Free GPU memory held by this pipeline.

        Deletes the transformers pipeline object and calls
        ``torch.cuda.empty_cache()`` so the freed VRAM is immediately
        available for the next model to be loaded.  Called by
        :class:`ModelPool` before loading a different HuggingFace model.
        """
        del self._pipeline
        self._pipeline = None  # type: ignore[assignment]
        try:
            import torch
            torch.cuda.empty_cache()
        except Exception:
            pass

    def generate(self, prompt: str, parameters: dict) -> str:
        params = dict(parameters)
        params.pop('model', None)          # already loaded at init
        params.pop('device', None)         # already set at init
        params.pop('load_in_4bit', None)   # init-time param, not a generate arg
        params.pop('load_in_8bit', None)   # init-time param, not a generate arg
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
