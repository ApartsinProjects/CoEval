"""Mistral AI Batch API runner for CoEval pipeline phases.

Submits many chat-completion requests as a single Mistral Batch API job
instead of making individual synchronous calls.  Benefits:
  - ~50% cost reduction (Mistral Batch pricing)
  - Higher effective throughput (no per-request rate-limit pressure)
  - Consistent add()/run() interface with other CoEval batch runners

Mistral's Batch API is fully OpenAI-compatible in format:
  - File upload via ``/v1/files`` (same JSONL format as OpenAI Batch)
  - Batch creation via ``/v1/batches`` with ``endpoint="/v1/chat/completions"``
  - Output parsing: same ``{"custom_id", "response": {"body": {"choices": [...]}}}``
    format as OpenAI Batch output

This runner is a thin wrapper around :class:`OpenAIBatchRunner` that points the
OpenAI SDK at Mistral's API base URL and uses ``MISTRAL_API_KEY`` for auth.

Requirements
------------
* The ``openai`` Python package (pre-installed with CoEval)
* A Mistral API key with Batch API access

Configuration
-------------
Add to your model parameters (YAML)::

    models:
      - name: mistral-small
        interface: mistral
        batch_enabled: true
        parameters:
          model: mistral-small-latest
          temperature: 0.7
          max_tokens: 512
        roles: [student, judge]

Or store credentials in ``keys.yaml``::

    providers:
      mistral: <your-mistral-api-key>

Enable batch per-phase::

    experiment:
      batch:
        mistral:
          response_collection: true
          evaluation: true

Supported models (as of 2026-03-02)
-------------------------------------
Mistral Batch API supports: Mistral Small, Mistral Large, Codestral,
Pixtral, Mistral NeMo, and open-weights variants.
See https://docs.mistral.ai/api/#tag/batch

Pricing
-------
Mistral batch pricing is approximately 50% of standard real-time pricing.
See https://mistral.ai/technology/#pricing
"""
from __future__ import annotations

import os
from typing import TYPE_CHECKING

from .openai_batch import OpenAIBatchRunner

if TYPE_CHECKING:
    from ..logger import RunLogger

_MISTRAL_BASE_URL = 'https://api.mistral.ai/v1'
_MISTRAL_ENV_VAR = 'MISTRAL_API_KEY'


class MistralBatchRunner(OpenAIBatchRunner):
    """Collect Mistral chat-completion requests, submit one Batch API job,
    return all results.

    Inherits the full add/run/clear interface from :class:`OpenAIBatchRunner`.
    The only difference is that the OpenAI SDK is configured with:
      - ``base_url = 'https://api.mistral.ai/v1'``
      - ``api_key`` resolved from ``access_key`` → ``MISTRAL_API_KEY`` env var

    Requests that fail within the batch map to ``''`` in the returned dict.
    The runner clears its internal request list after :meth:`run` completes.
    """

    def __init__(
        self,
        access_key: str | None = None,
        poll_seconds: int = 30,
    ) -> None:
        """
        Args:
            access_key:   Mistral API key.  Falls back to ``MISTRAL_API_KEY``
                          environment variable if not provided.
            poll_seconds: How often (in seconds) to poll for job completion.
                          Defaults to 30 s (Mistral jobs complete faster than
                          OpenAI jobs on average).
        """
        try:
            from openai import OpenAI
        except ImportError:
            raise ImportError("openai package is required: pip install openai")

        key = access_key or os.environ.get(_MISTRAL_ENV_VAR)
        if not key:
            raise ValueError(
                f"Mistral API key not found.  Set {_MISTRAL_ENV_VAR} or pass "
                "access_key= to MistralBatchRunner."
            )

        # Initialise without calling super().__init__() to avoid the
        # OpenAI-specific client construction, then set up the same attributes.
        self._poll = poll_seconds
        self._requests: list[dict] = []
        self._id_to_key: dict[str, str] = {}

        # Point the OpenAI SDK at Mistral's API
        self._client = OpenAI(api_key=key, base_url=_MISTRAL_BASE_URL)

    def run(
        self,
        description: str = 'CoEval batch',
        logger: 'RunLogger | None' = None,
        storage=None,
        phase: str = '',
    ) -> dict[str, str]:
        """Submit the pending Mistral batch and block until the job completes.

        Delegates to :meth:`OpenAIBatchRunner.run` but records the interface
        name as ``'mistral'`` in any pending-batch storage records.
        """
        if not self._requests:
            return {}

        # Temporarily patch storage calls to use 'mistral' as the interface name.
        # We do this by wrapping storage with a proxy that intercepts
        # add_pending_batch and passes 'mistral' as the interface argument.
        if storage is not None:
            storage = _MistralStorageProxy(storage)

        return super().run(
            description=description,
            logger=logger,
            storage=storage,
            phase=phase,
        )


class _MistralStorageProxy:
    """Thin proxy around ExperimentStorage that rewrites the interface name
    in ``add_pending_batch()`` calls from ``'openai'`` to ``'mistral'``."""

    def __init__(self, wrapped) -> None:
        self._wrapped = wrapped

    def add_pending_batch(
        self, batch_id: str, interface: str, phase: str,
        description: str, n: int, id_to_key: dict,
    ) -> None:
        # Always record as 'mistral' regardless of what the parent passes
        self._wrapped.add_pending_batch(
            batch_id, 'mistral', phase, description, n, id_to_key
        )

    def remove_pending_batch(self, batch_id: str) -> None:
        self._wrapped.remove_pending_batch(batch_id)

    def update_pending_batch_status(self, batch_id: str, status: str) -> None:
        self._wrapped.update_pending_batch_status(batch_id, status)

    def __getattr__(self, name: str):
        return getattr(self._wrapped, name)
