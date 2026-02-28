from .base import ModelInterface
from .openai_iface import OpenAIInterface
from .openai_batch import OpenAIBatchRunner
from .anthropic_iface import AnthropicInterface
from .anthropic_batch import AnthropicBatchRunner
from .gemini_iface import GeminiInterface
from .gemini_batch import GeminiBatchRunner
from .huggingface_iface import HuggingFaceInterface
from .pool import ModelPool

__all__ = [
    'ModelInterface',
    'OpenAIInterface', 'OpenAIBatchRunner',
    'AnthropicInterface', 'AnthropicBatchRunner',
    'GeminiInterface', 'GeminiBatchRunner',
    'HuggingFaceInterface',
    'ModelPool',
    'create_batch_runner',
]


def create_batch_runner(interface: str, access_key: str | None = None, **kwargs):
    """Factory: return the appropriate batch runner for the given interface name.

    Args:
        interface:  One of ``'openai'``, ``'anthropic'``, ``'gemini'``.
        access_key: Provider API key.  Falls back to the relevant environment
                    variable if ``None``.
        **kwargs:   Passed through to the runner constructor (e.g. ``poll_seconds``
                    for OpenAI/Anthropic, ``max_workers`` for Gemini).

    Raises:
        ValueError: if *interface* has no registered batch runner.
    """
    if interface == 'openai':
        return OpenAIBatchRunner(access_key=access_key, **kwargs)
    if interface == 'anthropic':
        return AnthropicBatchRunner(access_key=access_key, **kwargs)
    if interface == 'gemini':
        return GeminiBatchRunner(access_key=access_key, **kwargs)
    raise ValueError(
        f"No batch runner available for interface '{interface}'. "
        "Supported: 'openai', 'anthropic', 'gemini'."
    )
