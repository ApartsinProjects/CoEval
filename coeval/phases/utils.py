"""Shared utilities for pipeline phases: LLM call with retry, attribute merging."""
from __future__ import annotations

import json
import re
import time
from typing import Any

from ..interfaces import ModelInterface

_MAX_RETRIES = 3
_INITIAL_DELAY = 1.0


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
            raw = re.sub(r'^```(?:json)?\s*', '', raw.strip(), flags=re.MULTILINE)
            raw = re.sub(r'```\s*$', '', raw.strip(), flags=re.MULTILINE)
            return json.loads(raw.strip())
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
