from .base import ModelInterface
from .openai_iface import OpenAIInterface
from .openai_batch import OpenAIBatchRunner
from .anthropic_iface import AnthropicInterface
from .anthropic_batch import AnthropicBatchRunner
from .gemini_iface import GeminiInterface
from .gemini_batch import GeminiBatchRunner
from .azure_batch import AzureBatchRunner
from .huggingface_iface import HuggingFaceInterface
from .pool import ModelPool
from .openai_compat_iface import OpenAICompatInterface, supported_interfaces as _openai_compat_supported

__all__ = [
    'ModelInterface',
    'OpenAIInterface', 'OpenAIBatchRunner',
    'AnthropicInterface', 'AnthropicBatchRunner',
    'GeminiInterface', 'GeminiBatchRunner',
    'AzureBatchRunner',
    'HuggingFaceInterface',
    'ModelPool',
    'OpenAICompatInterface',
    'create_batch_runner',
]


def create_batch_runner(interface: str, access_key: str | None = None, **kwargs):
    """Factory: return the appropriate batch runner for the given interface name.

    Args:
        interface:  One of ``'openai'``, ``'anthropic'``, ``'gemini'``,
                    ``'azure_openai'``.
        access_key: Provider API key.  Falls back to the relevant environment
                    variable if ``None``.
        **kwargs:   Passed through to the runner constructor (e.g. ``poll_seconds``
                    for OpenAI/Anthropic/Azure, ``max_workers`` for Gemini,
                    ``azure_endpoint`` / ``api_version`` for Azure).

    Raises:
        ValueError: if *interface* has no registered batch runner.
    """
    if interface == 'openai':
        return OpenAIBatchRunner(access_key=access_key, **kwargs)
    if interface == 'anthropic':
        return AnthropicBatchRunner(access_key=access_key, **kwargs)
    if interface == 'gemini':
        return GeminiBatchRunner(access_key=access_key, **kwargs)
    if interface == 'azure_openai':
        return AzureBatchRunner(access_key=access_key, **kwargs)
    raise ValueError(
        f"No batch runner available for interface '{interface}'. "
        "Supported: 'openai', 'anthropic', 'gemini', 'azure_openai'."
    )
