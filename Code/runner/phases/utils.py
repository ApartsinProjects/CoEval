"""Shared utilities for pipeline phases: LLM call with retry, attribute merging."""
from __future__ import annotations

import json
import re
import time
from typing import Any

from ..interfaces import ModelInterface

_MAX_RETRIES = 3
_INITIAL_DELAY = 1.0


def _extract_json(text: str) -> Any:
    """Extract JSON from noisy model output using multiple fallback strategies.

    Small models often wrap JSON in prose, markdown fences, or return a
    single-element list instead of a bare object.  Strategies (in order):
      1. Direct parse of the full text.
      2. Locate the first '{' or '[' and parse from there to the end.
      3. Locate the substring between the first '{' and the last '}' (or
         first '[' and last ']') and parse that window.

    After a successful parse, single-element lists whose sole item is a dict
    are automatically unwrapped to match the expected ``{"key": ...}`` shape.
    """
    def _unwrap_list(obj: Any) -> Any:
        """Return the first dict element if obj is a non-empty list of dicts."""
        if isinstance(obj, list) and obj and isinstance(obj[0], dict):
            return obj[0]
        return obj

    # Strategy 1 — direct
    try:
        return _unwrap_list(json.loads(text))
    except json.JSONDecodeError:
        pass

    # Strategy 2 — strip leading non-JSON prose
    for start_char in ('{', '['):
        idx = text.find(start_char)
        if idx != -1:
            try:
                return _unwrap_list(json.loads(text[idx:]))
            except json.JSONDecodeError:
                pass

    # Strategy 3 — extract outermost balanced brackets
    for start_char, end_char in (('{', '}'), ('[', ']')):
        start_idx = text.find(start_char)
        end_idx = text.rfind(end_char)
        if 0 <= start_idx < end_idx:
            try:
                return _unwrap_list(json.loads(text[start_idx:end_idx + 1]))
            except json.JSONDecodeError:
                pass

    raise json.JSONDecodeError('Cannot extract JSON from model output', text, 0)


def call_llm_json(
    iface: ModelInterface,
    prompt: str,
    parameters: dict,
    max_retries: int = _MAX_RETRIES,
) -> Any:
    """Call LLM and parse JSON response. Retries up to max_retries on parse failure (REQ-9.5)."""
    delay = _INITIAL_DELAY
    last_err: Exception | None = None
    for attempt in range(max_retries):
        try:
            raw = iface.generate(prompt, parameters)
            # Strip markdown code fences that some models emit
            cleaned = re.sub(r'^```(?:json)?\s*', '', raw.strip(), flags=re.MULTILINE)
            cleaned = re.sub(r'```\s*$', '', cleaned.strip(), flags=re.MULTILINE)
            return _extract_json(cleaned.strip())
        except json.JSONDecodeError as exc:
            last_err = exc
            if attempt < max_retries - 1:
                time.sleep(delay)
                delay *= 2
        except Exception as exc:
            # Surface non-JSON errors immediately (network retries are in the interface)
            raise
    raise ValueError(
        f"JSON parse failed after {max_retries} attempts. Last error: {last_err}"
    )


def call_llm_word(
    iface: ModelInterface,
    prompt: str,
    parameters: dict,
    valid_words: set[str] = frozenset({'High', 'Medium', 'Low'}),
    max_retries: int = _MAX_RETRIES,
) -> str:
    """Call LLM and expect a single word from valid_words. Retries on invalid response (REQ-9.5)."""
    delay = _INITIAL_DELAY
    last_val: str = ''
    for attempt in range(max_retries):
        raw = iface.generate(prompt, parameters).strip()
        # Accept the word even if there's surrounding whitespace or punctuation
        word = raw.strip().rstrip('.')
        if word in valid_words:
            return word
        last_val = raw
        if attempt < max_retries - 1:
            time.sleep(delay)
            delay *= 2
    raise ValueError(
        f"Expected one of {valid_words} but got '{last_val}' after {max_retries} attempts"
    )


def merge_attr_maps(*maps: dict) -> dict[str, list]:
    """Union of attribute values across multiple attribute maps (REQ-5.3.2, REQ-5.3.3)."""
    result: dict[str, list] = {}
    for m in maps:
        if not isinstance(m, dict):
            continue
        for attr, values in m.items():
            if not isinstance(values, list):
                continue
            if attr not in result:
                result[attr] = []
            for v in values:
                if v not in result[attr]:
                    result[attr].append(v)
    return result


def merge_rubrics(*rubrics: dict) -> dict[str, str]:
    """Union of rubric factors; first occurrence of a factor name wins."""
    result: dict[str, str] = {}
    for r in rubrics:
        if not isinstance(r, dict):
            continue
        for factor, desc in r.items():
            if factor not in result:
                result[factor] = desc
    return result


# Ordered lists of key-name alternatives for the two required datapoint fields.
# First match wins; these cover common naming variations from small models.
_PROMPT_KEYS = ('prompt', 'input', 'question', 'task', 'context', 'user_input', 'text', 'scenario')
_RESPONSE_KEYS = ('response', 'output', 'answer', 'completion', 'result', 'reference', 'label')


def extract_prompt_response(data: Any) -> tuple[str, str]:
    """Extract the prompt and response strings from a datapoint dict (or list of dicts).

    Small models frequently use key names other than the canonical
    ``"prompt"`` / ``"response"`` (e.g. ``"input"``/``"output"``,
    ``"question"``/``"answer"``), and sometimes wrap the object in a list.
    This helper normalises the structure and returns the first matching values.

    Raises ``KeyError`` if neither field can be located.
    """
    # Unwrap list — use the first dict element if the model returned a list
    if isinstance(data, list):
        for item in data:
            if isinstance(item, dict):
                data = item
                break
        else:
            raise KeyError(
                f"Model returned a list but no dict element was found: {data!r}"
            )

    if not isinstance(data, dict):
        raise KeyError(f"Expected a dict from model output, got {type(data).__name__}: {data!r}")

    prompt_val: str | None = None
    for key in _PROMPT_KEYS:
        if key in data:
            prompt_val = str(data[key])
            break

    response_val: str | None = None
    for key in _RESPONSE_KEYS:
        if key in data:
            response_val = str(data[key])
            break

    if prompt_val is None:
        raise KeyError(
            f"No prompt-like key found in model output — keys present: {list(data.keys())}"
        )
    if response_val is None:
        raise KeyError(
            f"No response-like key found in model output — keys present: {list(data.keys())}"
        )
    return prompt_val, response_val


def parse_json_text(text: str) -> Any:
    """Parse JSON from raw model output text, stripping markdown fences.

    Equivalent to the JSON-extraction step inside :func:`call_llm_json` but
    works directly on a response string rather than making an LLM call.
    Useful for processing Batch API results where retries are not available.
    """
    cleaned = re.sub(r'^```(?:json)?\s*', '', text.strip(), flags=re.MULTILINE)
    cleaned = re.sub(r'```\s*$', '', cleaned.strip(), flags=re.MULTILINE)
    return _extract_json(cleaned.strip())


def parse_word_text(
    text: str,
    valid_words: frozenset = frozenset({'High', 'Medium', 'Low'}),
) -> str:
    """Extract a valid evaluation word from raw model output.

    More lenient than the retry-based :func:`call_llm_word`: scans the response
    for any occurrence of a valid word rather than requiring the entire response
    to equal the word.  Returns ``'Low'`` as a fallback when no valid word is
    found.  Useful for Batch API results where per-item retries are not possible.
    """
    stripped = text.strip().rstrip('.')
    if stripped in valid_words:
        return stripped
    for token in text.strip().split():
        cleaned = token.strip('.,!?;:')
        if cleaned in valid_words:
            return cleaned
    return 'Low'  # conservative fallback


class QuotaTracker:
    """Tracks remaining LLM calls per model (REQ-5.4.1 quota field).

    Thread-safe: all mutations are protected by a ``threading.Lock`` so that
    concurrent phase workers (e.g. the OAI ThreadPoolExecutor in Phase 4/5)
    cannot race on the shared counter.
    """

    def __init__(self, quota_config: dict[str, dict[str, int]]) -> None:
        import threading
        self._lock = threading.Lock()
        self._remaining: dict[str, float] = {
            model_name: float(spec.get('max_calls', float('inf')))
            for model_name, spec in quota_config.items()
        }

    def is_exhausted(self, model_name: str) -> bool:
        with self._lock:
            return self._remaining.get(model_name, float('inf')) <= 0

    def consume(self, model_name: str) -> None:
        with self._lock:
            if model_name in self._remaining:
                self._remaining[model_name] -= 1
