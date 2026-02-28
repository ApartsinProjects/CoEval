"""Model pool: creates and caches interface instances to avoid reloading weights."""
from __future__ import annotations

from ..config import ModelConfig
from .base import ModelInterface
from .openai_iface import OpenAIInterface
from .anthropic_iface import AnthropicInterface
from .gemini_iface import GeminiInterface
from .huggingface_iface import HuggingFaceInterface
from .azure_openai_iface import AzureOpenAIInterface
from .bedrock_iface import BedrockInterface
from .vertex_iface import VertexInterface
from .openrouter_iface import OpenRouterInterface
from .azure_ai_iface import AzureAIInterface

# Network-based interfaces that are lightweight wrappers with no GPU footprint
_NETWORK_INTERFACES = frozenset({
    'openai', 'anthropic', 'gemini', 'azure_openai', 'azure_ai',
    'bedrock', 'vertex', 'openrouter',
})


class ModelPool:
    """Factory + cache for ModelInterface instances.

    Only **one** HuggingFace model is kept in GPU memory at a time.  Before
    loading a new HF model, all other cached HF models are released via
    :meth:`HuggingFaceInterface.release` so their VRAM is freed.

    Network-based interfaces (OpenAI, Anthropic, Gemini, Azure OpenAI,
    AWS Bedrock, Google Vertex AI) are lightweight API wrappers with no GPU
    footprint and are always kept cached.

    Credential resolution
    ---------------------
    When a ``provider_keys`` dict is supplied (from a provider key file), it
    is used as a fallback for credentials not present in the model's YAML
    config or environment variables.  The resolution order per provider is:

    1. model-level ``access_key`` (YAML)
    2. ``provider_keys[interface]`` (key file)
    3. standard environment variables
    """

    def __init__(self, provider_keys: dict | None = None) -> None:
        self._cache: dict[str, ModelInterface] = {}
        self._provider_keys: dict = provider_keys or {}

    def get(self, model_cfg: ModelConfig) -> ModelInterface:
        if model_cfg.name not in self._cache:
            self._cache[model_cfg.name] = self._create(model_cfg)
        return self._cache[model_cfg.name]

    def _create(self, model_cfg: ModelConfig) -> ModelInterface:
        iface = model_cfg.interface
        params = model_cfg.parameters
        pk = self._provider_keys

        if iface == 'openai':
            key = (
                model_cfg.access_key
                or pk.get('openai', {}).get('api_key')
                # env var is handled inside OpenAIInterface
            )
            return OpenAIInterface(access_key=key)

        if iface == 'anthropic':
            key = (
                model_cfg.access_key
                or pk.get('anthropic', {}).get('api_key')
            )
            return AnthropicInterface(access_key=key)

        if iface == 'gemini':
            key = (
                model_cfg.access_key
                or pk.get('gemini', {}).get('api_key')
            )
            return GeminiInterface(access_key=key)

        if iface == 'azure_openai':
            az = pk.get('azure_openai', {})
            return AzureOpenAIInterface(
                api_key=model_cfg.access_key or az.get('api_key'),
                azure_endpoint=(
                    params.get('azure_endpoint')
                    or az.get('endpoint')
                ),
                api_version=(
                    params.get('api_version')
                    or az.get('api_version')
                ),
            )

        if iface == 'bedrock':
            bk = pk.get('bedrock', {})
            return BedrockInterface(
                api_key=(
                    model_cfg.access_key
                    or params.get('api_key')
                    or bk.get('api_key')
                ),
                access_key_id=(
                    params.get('access_key_id')
                    or bk.get('access_key_id')
                ),
                secret_access_key=(
                    params.get('secret_access_key')
                    or bk.get('secret_access_key')
                ),
                session_token=(
                    params.get('session_token')
                    or bk.get('session_token')
                ),
                region=(
                    params.get('region')
                    or bk.get('region')
                ),
            )

        if iface == 'azure_ai':
            ai = pk.get('azure_ai', {})
            return AzureAIInterface(
                access_key=(
                    model_cfg.access_key
                    or (ai.get('api_key') if isinstance(ai, dict) else ai)
                ),
                azure_endpoint=(
                    params.get('azure_endpoint')
                    or (ai.get('endpoint') if isinstance(ai, dict) else None)
                ),
            )

        if iface == 'openrouter':
            or_key = pk.get('openrouter', {})
            return OpenRouterInterface(
                access_key=(
                    model_cfg.access_key
                    or (or_key.get('api_key') if isinstance(or_key, dict) else or_key)
                ),
                site_url=params.get('site_url'),
                site_name=params.get('site_name'),
            )

        if iface == 'vertex':
            vx = pk.get('vertex', {})
            return VertexInterface(
                project=(
                    params.get('project')
                    or vx.get('project')
                ),
                location=(
                    params.get('location')
                    or vx.get('location')
                ),
                service_account_key=(
                    params.get('service_account_key')
                    or vx.get('service_account_key')
                    or model_cfg.access_key
                ),
            )

        # HuggingFace (GPU-based): evict other HF models from VRAM first
        self._evict_hf_models(keep=model_cfg.name)
        hf_token = (
            model_cfg.access_key
            or self._provider_keys.get('huggingface', {}).get('token')
        )
        return HuggingFaceInterface(
            model_id=params['model'],
            access_key=hf_token,
            device=params.get('device', 'auto'),
            load_in_4bit=params.get('load_in_4bit', False),
            load_in_8bit=params.get('load_in_8bit', False),
        )

    def _evict_hf_models(self, keep: str | None = None) -> None:
        """Release all cached HF models except *keep* from GPU memory.

        Removed entries will be recreated (weights reloaded) on next access.
        """
        to_evict = [
            name for name, iface in self._cache.items()
            if isinstance(iface, HuggingFaceInterface) and name != keep
        ]
        for name in to_evict:
            self._cache[name].release()  # type: ignore[union-attr]
            del self._cache[name]
