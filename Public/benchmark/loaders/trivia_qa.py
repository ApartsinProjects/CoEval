"""TriviaQA benchmark loader.

Dataset  : trivia_qa, config=rc.nocontext (HuggingFace)
Split    : validation
Prompt   : A trivia question; ask for a concise, accurate answer.
Reference: The canonical answer string from answer["value"].
GT metric: Exact-match or token-overlap (F1) against canonical answer / aliases.
Attributes:
  - answer_length : "short" (1 word) / "medium" (2-3 words) / "long" (>3 words)
  - domain        : always "trivia"
"""
from __future__ import annotations

from typing import Any

from .base import BenchmarkLoader


def _answer_length(answer_value: str) -> str:
    n = len(answer_value.split())
    if n == 1:
        return "short"
    if n <= 3:
        return "medium"
    return "long"


class TriviaQALoader(BenchmarkLoader):
    """Loader for the TriviaQA knowledge-retrieval benchmark (rc.nocontext split)."""

    benchmark_id = "trivia_qa"
    task_id = "knowledge_retrieval"
    default_split = "validation"

    def _load_dataset(self) -> list[dict[str, Any]]:
        from datasets import load_dataset

        ds = load_dataset("trivia_qa", "rc.nocontext", split=self.split)
        items: list[dict[str, Any]] = []
        for idx, row in enumerate(ds):
            question = (row.get("question") or "").strip()
            answer = row.get("answer") or {}
            answer_value = (answer.get("value") or "").strip()

            if not question or not answer_value:
                continue

            native_id = row.get("question_id") or str(idx)

            items.append({
                "_native_id": str(native_id),
                "_question": question,
                "_answer_value": answer_value,
                "_inferred_attrs": {
                    "answer_length": _answer_length(answer_value),
                    "domain": "trivia",
                },
            })
        return items

    def _to_record(self, item: dict[str, Any], seq: int) -> dict[str, Any]:
        prompt = (
            "Answer the following trivia question. Provide a concise, accurate answer.\n\n"
            f"Question: {item['_question']}"
        )
        return {
            "id": self._make_id(seq),
            "task_id": self.task_id,
            "teacher_model_id": self.teacher_id,
            "sampled_target_attributes": item["_inferred_attrs"],
            "prompt": prompt,
            "reference_response": item["_answer_value"],
            "generated_at": self._now_iso(),
            "benchmark_id": self.benchmark_id,
            "benchmark_split": self.split,
            "benchmark_native_id": item["_native_id"],
            "benchmark_native_score": None,
        }
