"""OpenAI Batch API runner for CoEval pipeline phases.

Submits many chat-completion requests in one Batch API job instead of making
individual synchronous calls.  Benefits vs. the ThreadPoolExecutor approach:
  - 50 % cost reduction (OpenAI Batch pricing)
  - Higher effective throughput (no per-minute rate-limit pressure)
  - Simpler error handling (one job, one result file)

Typical completion time for < 10 k requests: 5 – 30 minutes.
The completion window is set to 24 h so very large batches are also supported.

Usage::

    runner = OpenAIBatchRunner(access_key="sk-...")
    runner.add("my-key-1", "Score this response …", {"model": "gpt-4o-mini", …})
    runner.add("my-key-2", "Score that response …", {"model": "gpt-4o-mini", …})
    results = runner.run(description="Phase 5 evaluations", logger=logger)
    # results -> {"my-key-1": "{ … JSON … }", "my-key-2": "High", …}
"""
from __future__ import annotations

import io
import json
import os
import time
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..logger import RunLogger

_DEFAULT_POLL_SECONDS = 30
# OpenAI Batch API limit per job
_MAX_REQUESTS_PER_BATCH = 50_000
# Params that are CoEval / HuggingFace-specific and must not reach the OAI API
_STRIP_PARAMS = frozenset({"load_in_4bit", "load_in_8bit", "device", "max_new_tokens"})


class OpenAIBatchRunner:
    """Collect chat-completion requests, submit one Batch API job, return all results.

    Each call to :meth:`add` appends one request to an internal list.  When
    :meth:`run` is called the list is serialised to a JSONL file, uploaded to
    the OpenAI Files API, and submitted as a batch job.  The method blocks
    (polling every *poll_seconds* seconds) until the job reaches a terminal
    state, then downloads the output and returns a ``{user_key: response_text}``
    mapping.

    Requests that fail within the batch map to an empty string ``''`` in the
    returned dict; callers should treat ``''`` as a generation failure.

    The runner clears its internal request list after :meth:`run` completes so
    the same instance can be reused for a second batch.
    """

    def __init__(
        self,
        access_key: str | None = None,
        poll_seconds: int = _DEFAULT_POLL_SECONDS,
    ) -> None:
        try:
            from openai import OpenAI
        except ImportError:
            raise ImportError("openai package is required: pip install openai")
        key = access_key or os.environ.get("OPENAI_API_KEY")
        self._client = OpenAI(api_key=key)
        self._poll = poll_seconds
        # List of fully-formed JSONL request objects for the Batch API.
        self._requests: list[dict] = []
        # Map compact sequential custom_id ("r0", "r1", …) → caller's user_key.
        self._id_to_key: dict[str, str] = {}

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def add(self, key: str, prompt: str, params: dict) -> None:
        """Append one chat-completion request to the pending batch.

        Args:
            key:    Arbitrary caller-supplied identifier.  Returned as-is in
                    the results dict so callers can correlate requests with
                    responses without caring about internal ordering.
            prompt: User-turn text for the chat completion.
            params: Model parameters dict (``model``, ``temperature``,
                    ``max_tokens``, ``system_prompt``, …).  HuggingFace-only
                    keys (``load_in_4bit``, ``device``, …) are stripped silently.
        """
        if len(self._requests) >= _MAX_REQUESTS_PER_BATCH:
            raise ValueError(
                f"Batch size limit reached ({_MAX_REQUESTS_PER_BATCH} requests). "
                "Call run() to submit the current batch before adding more."
            )

        p = {k: v for k, v in params.items() if k not in _STRIP_PARAMS}
        model = p.pop("model")
        system_prompt = p.pop("system_prompt", None)
        temperature = p.pop("temperature", 0.7)
        max_tokens = p.pop("max_tokens", None)

        messages: list[dict] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        body: dict = {"model": model, "messages": messages, "temperature": temperature}
        if max_tokens is not None:
            body["max_tokens"] = max_tokens
        body.update(p)  # any remaining provider-specific params

        # Use a compact sequential id to stay well under the 64-char limit.
        custom_id = f"r{len(self._requests)}"
        self._id_to_key[custom_id] = key
        self._requests.append(
            {
                "custom_id": custom_id,
                "method": "POST",
                "url": "/v1/chat/completions",
                "body": body,
            }
        )

    def __len__(self) -> int:
        return len(self._requests)

    def clear(self) -> None:
        """Discard all pending requests without submitting them."""
        self._requests.clear()
        self._id_to_key.clear()

    def run(
        self,
        description: str = "CoEval batch",
        logger: RunLogger | None = None,
        storage=None,
        phase: str = '',
    ) -> dict[str, str]:
        """Submit the pending batch and block until the job completes.

        Args:
            description: Human-readable label stored in the OpenAI batch metadata.
            logger:      Optional RunLogger for progress messages.
            storage:     Optional ExperimentStorage.  When provided, the batch job
                         ID and request-key mapping are written to
                         ``pending_batches.json`` before polling begins, enabling
                         ``coeval status --fetch-batches`` to recover results if
                         the process is interrupted.
            phase:       Pipeline phase name (e.g. ``"evaluation"``).  Only used
                         when *storage* is provided.

        Returns:
            ``{user_key: response_text}`` for every request that was added.
            Failed requests map to ``''`` (empty string).

        Raises:
            RuntimeError: if the Batch API job ends in a non-``completed``
                terminal state (e.g. ``failed``, ``expired``, ``cancelled``).
        """
        if not self._requests:
            return {}

        def _log(msg: str) -> None:
            if logger is not None:
                logger.info(msg)

        n = len(self._requests)

        # 1. Build and upload the JSONL input file
        jsonl_bytes = "\n".join(
            json.dumps(r, ensure_ascii=False) for r in self._requests
        ).encode("utf-8")

        _log(
            f"Batch API: uploading {n:,} request(s) "
            f"({len(jsonl_bytes) / 1024:.1f} KB, description={description!r})"
        )

        file_obj = self._client.files.create(
            file=("batch_input.jsonl", io.BytesIO(jsonl_bytes), "application/jsonl"),
            purpose="batch",
        )

        # 2. Create the batch job
        batch = self._client.batches.create(
            input_file_id=file_obj.id,
            endpoint="/v1/chat/completions",
            completion_window="24h",
            metadata={"description": description},
        )
        _log(
            f"Batch API: job created (id={batch.id}), "
            f"polling every {self._poll}s ..."
        )

        # Persist batch ID + key map before polling so a crash is recoverable.
        if storage is not None:
            try:
                storage.add_pending_batch(
                    batch.id, 'openai', phase, description, n,
                    dict(self._id_to_key),
                )
            except Exception:
                pass  # non-fatal — tracking is best-effort

        # 3. Poll until a terminal state is reached
        _PENDING_STATUSES = {"validating", "in_progress", "finalizing"}
        while batch.status in _PENDING_STATUSES:
            time.sleep(self._poll)
            batch = self._client.batches.retrieve(batch.id)
            rc = batch.request_counts
            if rc:
                counts = (
                    f"{rc.completed}/{rc.total} completed, {rc.failed} failed"
                )
            else:
                counts = "counts unavailable"
            _log(f"Batch API: status={batch.status!r} -- {counts}")

        if batch.status != "completed":
            if storage is not None:
                try:
                    storage.update_pending_batch_status(batch.id, f'api_{batch.status}')
                except Exception:
                    pass
            raise RuntimeError(
                f"Batch job {batch.id} ended with status '{batch.status}'. "
                f"Error file id: {batch.error_file_id}"
            )

        # 4. Download and parse the output file
        raw_output = self._client.files.content(batch.output_file_id).text
        results: dict[str, str] = {}
        n_errors = 0

        for line in raw_output.splitlines():
            line = line.strip()
            if not line:
                continue
            item = json.loads(line)
            custom_id: str = item["custom_id"]
            user_key = self._id_to_key.get(custom_id, custom_id)

            err = item.get("error")
            if err:
                _log(f"Batch API: request {custom_id!r} failed — {err}")
                results[user_key] = ""
                n_errors += 1
                continue

            resp_body = (item.get("response") or {}).get("body") or {}
            choices = resp_body.get("choices") or []
            if choices:
                results[user_key] = choices[0]["message"]["content"].strip()
            else:
                _log(f"Batch API: request {custom_id!r} returned no choices")
                results[user_key] = ""
                n_errors += 1

        n_ok = len(results) - n_errors
        _log(
            f"Batch API: complete — {n_ok:,} succeeded, {n_errors:,} failed "
            f"(out of {n:,})"
        )

        # 5. Clean up uploaded input file (best-effort)
        try:
            self._client.files.delete(file_obj.id)
        except Exception:
            pass

        # 6. Remove pending batch record now that results are saved.
        if storage is not None:
            try:
                storage.remove_pending_batch(batch.id)
            except Exception:
                pass

        # 7. Reset for potential reuse
        self.clear()

        return results
