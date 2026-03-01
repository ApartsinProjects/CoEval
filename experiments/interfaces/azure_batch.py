"""Azure OpenAI Batch API runner for CoEval pipeline phases.

Azure OpenAI's Batch API is structurally identical to the OpenAI Batch API,
providing the same 50% cost discount and higher throughput. This runner wraps
``openai.AzureOpenAI`` so phase code remains interface-agnostic.

The runner lazily captures ``azure_endpoint`` and ``api_version`` from the
parameters dict of the first ``add()`` call, so the pipeline phase code does
not need to pass them explicitly — they flow naturally from the model config's
``parameters`` block.

Usage::

    runner = AzureBatchRunner(access_key="<azure-api-key>")
    runner.add("k1", "Evaluate…", {"model": "Kimi-K2.5",
                                   "azure_endpoint": "https://…azure.com/",
                                   "api_version": "2024-05-01-preview", …})
    results = runner.run(description="Phase 5 evaluations", logger=logger)
    # results -> {"k1": "{ … JSON … }", …}

Model config YAML example::

    models:
      - name: kimi-k2-5
        interface: azure_openai
        batch_enabled: true
        parameters:
          model: Kimi-K2.5
          azure_endpoint: https://coeval-resource.cognitiveservices.azure.com/
          api_version: 2024-05-01-preview
          temperature: 0.7
          max_tokens: 1024
        roles: [teacher, student, judge]

Multiple deployments from the same resource — each model entry uses a
different ``parameters.model`` (deployment name) while sharing the same
endpoint and API key from ``keys.yaml``::

    - name: gpt-4o-azure
      interface: azure_openai
      batch_enabled: true
      parameters:
        model: gpt-4o-deployment
        temperature: 0.7
        max_tokens: 512

    - name: kimi-k2-5
      interface: azure_openai
      batch_enabled: true
      parameters:
        model: Kimi-K2.5
        temperature: 0.6
        max_tokens: 2048
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
_MAX_REQUESTS_PER_BATCH = 50_000
_STRIP_PARAMS = frozenset({
    "load_in_4bit", "load_in_8bit", "device", "max_new_tokens",
    "azure_endpoint", "api_version",
})


class AzureBatchRunner:
    """Collect Azure OpenAI chat-completion requests, submit one Batch API job.

    Interface mirrors :class:`OpenAIBatchRunner` so phase code is interface-agnostic.
    Requests that fail within the batch map to ``''`` in the returned dict.
    The runner clears its internal request list after :meth:`run` completes.

    Endpoint and API version are resolved in this priority order:

    1. Constructor arguments (``azure_endpoint``, ``api_version``).
    2. Environment variables (``AZURE_OPENAI_ENDPOINT``, ``AZURE_OPENAI_API_VERSION``).
    3. First :meth:`add` call's ``params`` dict — captured automatically from the
       model config parameters so the pipeline phase code needs no changes.
    """

    def __init__(
        self,
        access_key: str | None = None,
        azure_endpoint: str | None = None,
        api_version: str | None = None,
        poll_seconds: int = _DEFAULT_POLL_SECONDS,
    ) -> None:
        self._access_key = (
            access_key
            or os.environ.get('AZURE_OPENAI_API_KEY')
        )
        # Endpoint/api_version may be filled in later from add() params
        self._azure_endpoint = azure_endpoint or os.environ.get('AZURE_OPENAI_ENDPOINT')
        self._api_version = (
            api_version
            or os.environ.get('AZURE_OPENAI_API_VERSION')
            or '2024-08-01-preview'
        )
        self._poll = poll_seconds
        self._requests: list[dict] = []
        self._id_to_key: dict[str, str] = {}

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def add(self, key: str, prompt: str, params: dict) -> None:
        """Append one chat-completion request to the pending batch.

        ``azure_endpoint`` and ``api_version`` are stripped from the request
        body (they are connection parameters, not model parameters) but are
        captured as instance state if not already set.
        """
        if len(self._requests) >= _MAX_REQUESTS_PER_BATCH:
            raise ValueError(
                f"Batch size limit reached ({_MAX_REQUESTS_PER_BATCH} requests). "
                "Call run() before adding more."
            )

        p = dict(params)

        # Capture connection params from first add() if not already known
        if not self._azure_endpoint:
            self._azure_endpoint = p.get('azure_endpoint') or os.environ.get('AZURE_OPENAI_ENDPOINT')
        ep_from_params = p.get('api_version')
        if ep_from_params and self._api_version == '2024-08-01-preview':
            self._api_version = ep_from_params

        # Strip everything that must not reach the Batch API request body
        for k in _STRIP_PARAMS:
            p.pop(k, None)

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
        body.update(p)

        custom_id = f"r{len(self._requests)}"
        self._id_to_key[custom_id] = key
        self._requests.append({
            "custom_id": custom_id,
            "method": "POST",
            "url": "/v1/chat/completions",
            "body": body,
        })

    def __len__(self) -> int:
        return len(self._requests)

    def clear(self) -> None:
        """Discard all pending requests without submitting them."""
        self._requests.clear()
        self._id_to_key.clear()

    def run(
        self,
        description: str = "CoEval batch",
        logger: 'RunLogger | None' = None,
        storage=None,
        phase: str = '',
    ) -> dict[str, str]:
        """Submit the pending batch and block until the job completes.

        Returns:
            ``{user_key: response_text}`` for every request.
            Failed requests map to ``''`` (empty string).
        """
        if not self._requests:
            return {}

        if not self._azure_endpoint:
            raise ValueError(
                "Azure OpenAI endpoint not set. Add 'azure_endpoint' to model "
                "parameters, set AZURE_OPENAI_ENDPOINT, or pass azure_endpoint= "
                "to AzureBatchRunner()."
            )

        def _log(msg: str) -> None:
            if logger is not None:
                logger.info(msg)

        # Build client here (after endpoint is known)
        try:
            from openai import AzureOpenAI
        except ImportError:
            raise ImportError("openai package required: pip install openai")

        client = AzureOpenAI(
            api_key=self._access_key,
            azure_endpoint=self._azure_endpoint,
            api_version=self._api_version,
        )

        n = len(self._requests)

        # 1. Upload JSONL input file
        jsonl_bytes = "\n".join(
            json.dumps(r, ensure_ascii=False) for r in self._requests
        ).encode("utf-8")

        _log(
            f"Azure Batch API: uploading {n:,} request(s) "
            f"({len(jsonl_bytes) / 1024:.1f} KB, description={description!r})"
        )

        file_obj = client.files.create(
            file=("batch_input.jsonl", io.BytesIO(jsonl_bytes), "application/jsonl"),
            purpose="batch",
        )

        # 2. Create batch job
        batch = client.batches.create(
            input_file_id=file_obj.id,
            endpoint="/v1/chat/completions",
            completion_window="24h",
            metadata={"description": description},
        )
        _log(
            f"Azure Batch API: job created (id={batch.id}), "
            f"polling every {self._poll}s ..."
        )

        # Persist for recovery via coeval status --fetch-batches
        if storage is not None:
            try:
                storage.add_pending_batch(
                    batch.id, 'azure_openai', phase, description, n,
                    dict(self._id_to_key),
                )
            except Exception:
                pass

        # 3. Poll until terminal
        _PENDING = {"validating", "in_progress", "finalizing"}
        while batch.status in _PENDING:
            time.sleep(self._poll)
            batch = client.batches.retrieve(batch.id)
            rc = batch.request_counts
            counts = (
                f"{rc.completed}/{rc.total} completed, {rc.failed} failed"
                if rc else "counts unavailable"
            )
            _log(f"Azure Batch API: status={batch.status!r} -- {counts}")

        if batch.status != "completed":
            if storage is not None:
                try:
                    storage.update_pending_batch_status(batch.id, f'api_{batch.status}')
                except Exception:
                    pass
            raise RuntimeError(
                f"Azure batch job {batch.id} ended with status '{batch.status}'. "
                f"Error file id: {batch.error_file_id}"
            )

        # 4. Download and parse output
        raw_output = client.files.content(batch.output_file_id).text
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
                _log(f"Azure Batch API: request {custom_id!r} failed — {err}")
                results[user_key] = ""
                n_errors += 1
                continue

            resp_body = (item.get("response") or {}).get("body") or {}
            choices = resp_body.get("choices") or []
            if choices:
                content = choices[0]["message"].get("content") or ""
                results[user_key] = content.strip()
            else:
                _log(f"Azure Batch API: request {custom_id!r} returned no choices")
                results[user_key] = ""
                n_errors += 1

        n_ok = len(results) - n_errors
        _log(
            f"Azure Batch API: complete — {n_ok:,} succeeded, {n_errors:,} failed "
            f"(out of {n:,})"
        )

        # 5. Clean up uploaded input file
        try:
            client.files.delete(file_obj.id)
        except Exception:
            pass

        # 6. Remove pending batch record
        if storage is not None:
            try:
                storage.remove_pending_batch(batch.id)
            except Exception:
                pass

        self.clear()
        return results
