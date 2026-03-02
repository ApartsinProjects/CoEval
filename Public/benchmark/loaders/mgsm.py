"""Loader for MGSM (Multilingual Grade School Math) benchmark — English split.

Dataset : juletxara/mgsm (config "en")
Task    : multilingual_math
Metric  : exact_match (numeric answer extracted from model output)
Split   : test (250 problems)

MGSM problems are uniformly grade-school difficulty; all attributes are
fixed constants for the English configuration used here.
"""
from __future__ import annotations

from typing import Any

from .base import BenchmarkLoader


class MGSMLoader(BenchmarkLoader):
    """Loads MGSM English test split for math reasoning evaluation."""

    benchmark_id: str = "mgsm"
    task_id: str = "multilingual_math"
    default_split: str = "test"

    # ------------------------------------------------------------------
    # Dataset loading
    # ------------------------------------------------------------------

    def _load_dataset(self) -> list[dict[str, Any]]:
        from datasets import load_dataset  # noqa: PLC0415

        ds = load_dataset("juletxara/mgsm", "en", split=self.split)
        items: list[dict[str, Any]] = []
        for idx, row in enumerate(ds):
            question: str = row.get("question") or ""
            answer = row.get("answer")
            if not question or answer is None:
                continue
            items.append(
                {
                    "question": question,
                    "answer": str(answer),
                    "_native_id": str(idx),
                    "_inferred_attrs": {
                        "language": "en",
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
        prompt = (
            "Solve the following math problem. Show your reasoning step by step "
            "and state the final answer as a number.\n\n"
            f"Problem: {item['question']}"
        )
        return {
            "id": self._make_id(seq),
            "task_id": self.task_id,
            "teacher_model_id": self.teacher_id,
            "sampled_target_attributes": attrs,
            "prompt": prompt,
            "reference_response": item["answer"],
            "generated_at": self._now_iso(),
            "benchmark_id": self.benchmark_id,
            "benchmark_split": self.split,
            "benchmark_native_id": item["_native_id"],
            "benchmark_native_score": None,
        }
