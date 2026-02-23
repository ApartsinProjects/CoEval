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
    # Strategy 1 — direct
    try:
        result = json.loads(text)
        if isinstance(result, list) and len(result) == 1 and isinstance(result[0], dict):
            result = result[0]
        return result
    except json.JSONDecodeError:
        pass

    # Strategy 2 — strip leading non-JSON prose
    for start_char in ('{', '['):
        idx = text.find(start_char)
        if idx != -1:
            try:
                result = json.loads(text[idx:])
                if isinstance(result, list) and len(result) == 1 and isinstance(result[0], dict):
                    result = result[0]
                return result
            except json.JSONDecodeError:
                pass

    # Strategy 3 — extract outermost balanced brackets
    for start_char, end_char in (('{', '}'), ('[', ']')):
        start_idx = text.find(start_char)
        end_idx = text.rfind(end_char)
        if 0 <= start_idx < end_idx:
            try:
                result = json.loads(text[start_idx:end_idx + 1])
                if isinstance(result, list) and len(result) == 1 and isinstance(result[0], dict):
                    result = result[0]
                return result
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


class QuotaTracker:
    """Tracks remaining LLM calls per model (REQ-5.4.1 quota field)."""

    def __init__(self, quota_config: dict[str, dict[str, int]]) -> None:
        self._remaining: dict[str, float] = {
            model_name: float(spec.get('max_calls', float('inf')))
            for model_name, spec in quota_config.items()
        }

    def is_exhausted(self, model_name: str) -> bool:
        return self._remaining.get(model_name, float('inf')) <= 0

    def consume(self, model_name: str) -> None:
        if model_name in self._remaining:
            self._remaining[model_name] -= 1
