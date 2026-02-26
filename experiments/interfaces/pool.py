"""Model pool: creates and caches interface instances to avoid reloading weights."""
from __future__ import annotations

from ..config import ModelConfig
from .base import ModelInterface
from .openai_iface import OpenAIInterface
from .huggingface_iface import HuggingFaceInterface


class ModelPool:
    """Factory + cache for ModelInterface instances.

    HuggingFace pipelines are expensive to load; the pool ensures each model's
    weights are loaded exactly once for the lifetime of the experiment run.
    """

    def __init__(self) -> None:
        self._cache: dict[str, ModelInterface] = {}

    def get(self, model_cfg: ModelConfig) -> ModelInterface:
        if model_cfg.name not in self._cache:
            if model_cfg.interface == 'openai':
                self._cache[model_cfg.name] = OpenAIInterface(
                    access_key=model_cfg.access_key
                )
            else:
                params = model_cfg.parameters
                self._cache[model_cfg.name] = HuggingFaceInterface(
                    model_id=params['model'],
                    access_key=model_cfg.access_key,
                    device=params.get('device', 'auto'),
                )
        return self._cache[model_cfg.name]
