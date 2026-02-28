"""Gemini concurrent-batch runner for CoEval pipeline phases.

Google Gemini's generative AI API does not offer a native asynchronous batch
endpoint comparable to OpenAI's or Anthropic's (batch prediction through
Vertex AI requires GCP infrastructure and is outside CoEval's scope).

This runner submits all requests *concurrently* using a thread pool, providing
the same ``add`` / ``run`` interface as the native batch runners.  Phase code
is therefore interface-agnostic: it just calls ``runner.add(...)`` and
``runner.run(...)`` regardless of provider.

Benefits over the old per-triple ThreadPoolExecutor:
  - All Gemini requests from ALL (task, teacher/student/judge) triples share one
    pool, achieving higher parallelism.
  - Consistent interface with OpenAI / Anthropic batch runners.

Rate-limiting: concurrent calls are subject to Gemini's requests-per-minute
quota.  Adjust max_workers downward if you hit 429 errors.
"""
from __future__ import annotations

import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..logger import RunLogger

_DEFAULT_MAX_WORKERS = 10
# Params that are CoEval / HuggingFace-specific and must not reach the Gemini API
_STRIP_PARAMS = frozenset({'load_in_4bit', 'load_in_8bit', 'device', 'max_new_tokens'})


class GeminiBatchRunner:
    """Collect Gemini requests and run them concurrently via a thread pool.

    Interface mirrors :class:`OpenAIBatchRunner` so phase code is interface-agnostic.
    Requests that fail (after internal retries) map to ``''`` in the returned dict.
    The runner clears its internal request list after :meth:`run` completes.
    """

    def __init__(
        self,
        access_key: str | None = None,
        max_workers: int = _DEFAULT_MAX_WORKERS,
    ) -> None:
        try:
            import google.generativeai as genai
        except ImportError:
            raise ImportError(
                "google-generativeai package is required: pip install google-generativeai"
            )
        key = access_key or os.environ.get('GEMINI_API_KEY') or os.environ.get('GOOGLE_API_KEY')
        genai.configure(api_key=key)
        self._genai = genai
        self._workers = max_workers
        self._requests: list[dict] = []
        self._id_to_key: dict[str, str] = {}

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def add(self, key: str, prompt: str, params: dict) -> None:
        """Append one Gemini request to the pending batch.

        Args:
            key:    Arbitrary caller-supplied identifier returned as-is in results.
            prompt: User-turn text.
            params: Model parameters dict.  HuggingFace-only keys are stripped.
        """
        p = {k: v for k, v in params.items() if k not in _STRIP_PARAMS}
        model_name = p.pop('model')
        system_prompt = p.pop('system_prompt', None)
        temperature = p.pop('temperature', 0.7)
        max_tokens = p.pop('max_tokens', None) or p.pop('max_output_tokens', None)

        gen_config: dict = {'temperature': temperature}
        if max_tokens is not None:
            gen_config['max_output_tokens'] = int(max_tokens)

        custom_id = f"r{len(self._requests)}"
        self._id_to_key[custom_id] = key
        self._requests.append({
            'custom_id': custom_id,
            'prompt': prompt,
            'model_name': model_name,
            'system_prompt': system_prompt,
            'gen_config': gen_config,
        })

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
    ) -> dict[str, str]:
        """Submit all pending requests concurrently and block until all complete.

        Returns:
            ``{user_key: response_text}`` for every request.
            Failed requests map to ``''`` (empty string).
        """
        if not self._requests:
            return {}

        def _log(msg: str) -> None:
            if logger is not None:
                logger.info(msg)

        n = len(self._requests)
        _log(
            f"Gemini Batch: submitting {n:,} concurrent request(s) "
            f"(workers={self._workers}, description={description!r})"
        )

        results: dict[str, str] = {}
        n_errors = 0

        with ThreadPoolExecutor(max_workers=self._workers) as executor:
            futures = {
                executor.submit(self._call_one, req): req['custom_id']
                for req in self._requests
            }
            for future in as_completed(futures):
                custom_id = futures[future]
                user_key = self._id_to_key.get(custom_id, custom_id)
                try:
                    response_text = future.result()
                    results[user_key] = response_text
                    if not response_text:
                        n_errors += 1
                except Exception as exc:
                    _log(f"Gemini Batch: request {custom_id!r} failed — {exc}")
                    results[user_key] = ''
                    n_errors += 1

        n_ok = len(results) - n_errors
        _log(
            f"Gemini Batch: complete — {n_ok:,} succeeded, {n_errors:,} failed "
            f"(out of {n:,})"
        )

        self.clear()
        return results

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _call_one(self, req: dict) -> str:
        """Call Gemini API for one request; returns response text or raises."""
        model = self._genai.GenerativeModel(
            req['model_name'],
            system_instruction=req['system_prompt'],
            generation_config=req['gen_config'],
        )
        delay = 1.0
        last_err: Exception | None = None
        for attempt in range(3):
            try:
                response = model.generate_content(req['prompt'])
                return response.text.strip()
            except Exception as exc:
                last_err = exc
                if attempt < 2:
                    time.sleep(delay)
                    delay *= 2
        return ''  # silently failed after retries — caller maps to ''
