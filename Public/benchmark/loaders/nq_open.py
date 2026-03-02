"""Loader for Google Natural Questions Open (NQ-Open).

Dataset : google-research-datasets/nq_open
Task    : open_domain_qa
Metric  : exact_match (case-insensitive, after light normalisation)
Split   : validation (3610 rows)

Each row contains a question and a list of acceptable short answers.
We use the first answer as the reference response and skip any row
whose answer list is empty.
"""
from __future__ import annotations

import random
from typing import Any

from .base import BenchmarkLoader


class NQOpenLoader(BenchmarkLoader):
    """Loads NQ-Open validation split for open-domain QA evaluation."""

    benchmark_id: str = "nq_open"
    task_id: str = "open_domain_qa"
    default_split: str = "validation"

    # ------------------------------------------------------------------
    # Dataset loading
    # ------------------------------------------------------------------

    def _load_dataset(self) -> list[dict[str, Any]]:
        from datasets import load_dataset  # noqa: PLC0415

        ds = load_dataset("google-research-datasets/nq_open", split=self.split)
        items: list[dict[str, Any]] = []
        for idx, row in enumerate(ds):
            answers: list[str] = row.get("answer") or []
            if not answers:
                continue
            question: str = row.get("question") or ""
            first_answer: str = answers[0]
            words = first_answer.split()
            if len(words) == 1:
                answer_length = "short"
            elif len(words) <= 3:
                answer_length = "medium"
            else:
                answer_length = "long"
            items.append(
                {
                    "question": question,
                    "answers": answers,
                    "_native_id": str(idx),
                    "_inferred_attrs": {
                        "answer_length": answer_length,
                        "domain": "factoid",
                    },
                }
            )
        return items

    # ------------------------------------------------------------------
    # Record conversion
    # ------------------------------------------------------------------

    def _to_record(self, item: dict[str, Any], seq: int) -> dict[str, Any]:
        attrs = item["_inferred_attrs"]
        question: str = item["question"]
        prompt = (
            "Answer the following question with a brief, factual answer.\n\n"
            f"Question: {question}"
        )
        return {
            "id": self._make_id(seq),
            "task_id": self.task_id,
            "teacher_model_id": self.teacher_id,
            "sampled_target_attributes": attrs,
            "prompt": prompt,
            "reference_response": item["answers"][0],
            "generated_at": self._now_iso(),
            "benchmark_id": self.benchmark_id,
            "benchmark_split": self.split,
            "benchmark_native_id": item["_native_id"],
            "benchmark_native_score": None,
        }
