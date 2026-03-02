"""Anthropic Message Batches API runner for CoEval pipeline phases.

Submits many Messages requests in one Batch API job.  Benefits:
  - Cost reduction vs synchronous calls (check Anthropic pricing page)
  - Higher effective throughput
  - Simpler error handling (one job, one result stream)

Typical processing time: a few minutes to an hour depending on load.
Results are available for 29 days after creation.

Usage::

    runner = AnthropicBatchRunner(access_key="sk-ant-...")
    runner.add("my-key-1", "Score this response …", {"model": "claude-3-5-haiku-20241022", …})
    runner.add("my-key-2", "Score that response …", {"model": "claude-3-5-haiku-20241022", …})
    results = runner.run(description="Phase 5 evaluations", logger=logger)
    # results -> {"my-key-1": "{ … JSON … }", "my-key-2": "High", …}
"""
from __future__ import annotations

import os
import time
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..logger import RunLogger

_DEFAULT_POLL_SECONDS = 60   # Anthropic recommends polling no more frequently than 60s
_MAX_REQUESTS_PER_BATCH = 10_000  # Anthropic Batch API limit per job
# Params that are CoEval / HuggingFace-specific and must not reach the Anthropic API
_STRIP_PARAMS = frozenset({'load_in_4bit', 'load_in_8bit', 'device', 'max_new_tokens'})


class AnthropicBatchRunner:
    """Collect Messages requests, submit one Batch API job, return all results.

    Interface mirrors :class:`OpenAIBatchRunner` so phase code is interface-agnostic.
    Requests that fail within the batch map to ``''`` in the returned dict.
    The runner clears its internal request list after :meth:`run` completes.
    """

    def __init__(
        self,
        access_key: str | None = None,
        poll_seconds: int = _DEFAULT_POLL_SECONDS,
    ) -> None:
        try:
            import anthropic
        except ImportError:
            raise ImportError("anthropic package is required: pip install anthropic")
        key = access_key or os.environ.get('ANTHROPIC_API_KEY')
        self._client = anthropic.Anthropic(api_key=key)
        self._poll = poll_seconds
        self._requests: list[dict] = []
        self._id_to_key: dict[str, str] = {}

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def add(self, key: str, prompt: str, params: dict) -> None:
        """Append one Messages request to the pending batch.

        Args:
            key:    Arbitrary caller-supplied identifier returned as-is in results.
            prompt: User-turn text for the message.
            params: Model parameters dict (``model``, ``temperature``, ``max_tokens``,
                    ``system_prompt``, …).  HuggingFace-only keys are stripped silently.
        """
        if len(self._requests) >= _MAX_REQUESTS_PER_BATCH:
            raise ValueError(
                f"Batch size limit reached ({_MAX_REQUESTS_PER_BATCH} requests). "
                "Call run() to submit the current batch before adding more."
            )

        p = {k: v for k, v in params.items() if k not in _STRIP_PARAMS}
        model = p.pop('model')
        system_prompt = p.pop('system_prompt', None)
        temperature = p.pop('temperature', 0.7)
        max_tokens = p.pop('max_tokens', 1024)  # Anthropic requires max_tokens

        req_params: dict = {
            'model': model,
            'max_tokens': max_tokens,
            'temperature': temperature,
            'messages': [{'role': 'user', 'content': prompt}],
        }
        if system_prompt:
            req_params['system'] = system_prompt
        req_params.update(p)  # any remaining provider-specific params

        custom_id = f"r{len(self._requests)}"
        self._id_to_key[custom_id] = key
        self._requests.append({'custom_id': custom_id, 'params': req_params})

    def __len__(self) -> int:
        return len(self._requests)

    def clear(self) -> None:
        """Discard all pending requests without submitting them."""
        self._requests.clear()
        self._id_to_key.clear()

    def run(
        self,
        description: str = 'CoEval batch',
        logger: RunLogger | None = None,
        storage=None,
        phase: str = '',
    ) -> dict[str, str]:
        """Submit the pending batch and block until the job ends.

        Args:
            description: Human-readable label for the batch job.
            logger:      Optional RunLogger for progress messages.
            storage:     Optional ExperimentStorage.  When provided, the batch job
                         ID and request-key mapping are written to
                         ``pending_batches.json`` before polling begins.
            phase:       Pipeline phase name (e.g. ``"evaluation"``).

        Returns:
            ``{user_key: response_text}`` for every request.
            Failed requests map to ``''`` (empty string).

        Raises:
            RuntimeError: if the batch ends in an unexpected terminal state.
        """
        if not self._requests:
            return {}

        def _log(msg: str) -> None:
            if logger is not None:
                logger.info(msg)

        n = len(self._requests)
        _log(f"Anthropic Batch: submitting {n:,} request(s) ({description!r})")

        # 1. Create the batch job
        batch = self._client.beta.messages.batches.create(requests=self._requests)
        _log(
            f"Anthropic Batch: job created (id={batch.id}), "
            f"polling every {self._poll}s ..."
        )

        # Persist batch ID + key map before polling so a crash is recoverable.
        if storage is not None:
            try:
                storage.add_pending_batch(
                    batch.id, 'anthropic', phase, description, n,
                    dict(self._id_to_key),
                )
            except Exception:
                pass  # non-fatal

        # 2. Poll until processing ends
        while batch.processing_status == 'in_progress':
            time.sleep(self._poll)
            batch = self._client.beta.messages.batches.retrieve(batch.id)
            rc = batch.request_counts
            if rc:
                counts = (
                    f"{rc.succeeded} succeeded, {rc.errored} errored, "
                    f"{rc.processing} processing"
                )
            else:
                counts = "counts unavailable"
            _log(f"Anthropic Batch: status={batch.processing_status!r} -- {counts}")

        if batch.processing_status != 'ended':
            if storage is not None:
                try:
                    storage.update_pending_batch_status(
                        batch.id, f'api_{batch.processing_status}'
                    )
                except Exception:
                    pass
            raise RuntimeError(
                f"Anthropic batch job {batch.id} ended with unexpected status "
                f"'{batch.processing_status}'"
            )

        # 3. Stream and parse results
        results: dict[str, str] = {}
        n_errors = 0

        for result in self._client.beta.messages.batches.results(batch.id):
            custom_id: str = result.custom_id
            user_key = self._id_to_key.get(custom_id, custom_id)

            if result.result.type == 'succeeded':
                content = result.result.message.content
                if content:
                    results[user_key] = content[0].text.strip()
                else:
                    _log(f"Anthropic Batch: request {custom_id!r} returned no content")
                    results[user_key] = ''
                    n_errors += 1
            else:
                err_info = getattr(result.result, 'error', result.result)
                _log(f"Anthropic Batch: request {custom_id!r} failed — {err_info}")
                results[user_key] = ''
                n_errors += 1

        n_ok = len(results) - n_errors
        _log(
            f"Anthropic Batch: complete -- {n_ok:,} succeeded, {n_errors:,} failed "
            f"(out of {n:,})"
        )

        # 4. Remove pending batch record now that results are saved.
        if storage is not None:
            try:
                storage.remove_pending_batch(batch.id)
            except Exception:
                pass

        # 5. Reset for potential reuse
        self.clear()
        return results
