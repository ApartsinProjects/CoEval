"""Loader for MathQA multiple-choice math word problems benchmark.

Dataset : math_qa
Task    : math_word_problems_mc
Metric  : exact_match (letter answer A/B/C/D/E)
Split   : test

Options are stored as a single string like "a ) 12 , b ) 15 , c ) 18 , ..."
and are parsed into a list before constructing the prompt.  The correct
answer is stored as a lowercase letter and converted to uppercase for
the reference response.
"""
from __future__ import annotations

import re
from typing import Any

from .base import BenchmarkLoader

_LETTER_TO_IDX: dict[str, int] = {"a": 0, "b": 1, "c": 2, "d": 3, "e": 4}


def _parse_options(opts_str: str) -> list[str]:
    """Split 'a ) 12 , b ) 15 , ...' into ['12', '15', ...]."""
    parts = re.split(r"\s*,\s*(?=[a-e]\s*\))", opts_str)
    return [re.sub(r"^[a-e]\s*\)\s*", "", p).strip() for p in parts]


class MathQALoader(BenchmarkLoader):
    """Loads MathQA test split for multiple-choice math word problem evaluation."""

    benchmark_id: str = "mathqa"
    task_id: str = "math_word_problems_mc"
    default_split: str = "test"

    # ------------------------------------------------------------------
    # Dataset loading
    # ------------------------------------------------------------------

    def _load_dataset(self) -> list[dict[str, Any]]:
        from datasets import load_dataset  # noqa: PLC0415

        ds = load_dataset("math_qa", split=self.split)
        items: list[dict[str, Any]] = []
        for idx, row in enumerate(ds):
            problem: str = row.get("Problem") or ""
            if not problem:
                continue
            opts_str: str = row.get("options") or ""
            correct_letter: str = (row.get("correct") or "a").strip().lower()
            category_raw: str = row.get("category") or ""
            parsed_opts = _parse_options(opts_str)
            correct_idx = _LETTER_TO_IDX.get(correct_letter, 0)
            correct_upper = chr(65 + correct_idx)  # 'A'..'E'
            category_attr = (
                category_raw.lower().replace(" ", "_") if category_raw else "general"
            )
            items.append(
                {
                    "problem": problem,
                    "parsed_opts": parsed_opts,
                    "correct": correct_upper,
                    "_native_id": str(idx),
                    "_inferred_attrs": {
                        "category": category_attr,
                        "difficulty": "medium",
                    },
                }
            )
        return items

    # ------------------------------------------------------------------
    # Record conversion
    # ------------------------------------------------------------------

    def _to_record(self, item: dict[str, Any], seq: int) -> dict[str, Any]:
        attrs = item["_inferred_attrs"]
        parsed_opts: list[str] = item["parsed_opts"]
        options_text = "\n".join(
            f"{chr(65 + i)}. {opt}" for i, opt in enumerate(parsed_opts)
        )
        prompt = (
            "Solve the following math word problem and choose the correct answer.\n\n"
            f"Problem: {item['problem']}\n\n"
            f"{options_text}\n\n"
            "Answer with the letter of the correct answer."
        )
        return {
            "id": self._make_id(seq),
            "task_id": self.task_id,
            "teacher_model_id": self.teacher_id,
            "sampled_target_attributes": attrs,
            "prompt": prompt,
            "reference_response": item["correct"],
            "generated_at": self._now_iso(),
            "benchmark_id": self.benchmark_id,
            "benchmark_split": self.split,
            "benchmark_native_id": item["_native_id"],
            "benchmark_native_score": None,
        }
