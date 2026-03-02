"""Cosmos QA benchmark loader.

Dataset  : cosmos_qa (HuggingFace)
Split    : validation
Prompt   : A narrative passage with a reading-comprehension question and four
           answer options (A-D); ask for the letter of the best answer.
Reference: "A", "B", "C", or "D" derived from the integer label field.
GT metric: Exact-match on the answer letter.
Attributes:
  - context_length : "short" (<60 words) / "medium" (<120 words) / "long" (>=120)
  - answer_count   : always "four"
"""
from __future__ import annotations

from typing import Any

from .base import BenchmarkLoader

_LABEL_TO_LETTER = {0: "A", 1: "B", 2: "C", 3: "D"}


def _context_length(context: str) -> str:
    n = len(context.split())
    if n < 60:
        return "short"
    if n < 120:
        return "medium"
    return "long"


class CosmosQALoader(BenchmarkLoader):
    """Loader for the Cosmos QA narrative-reasoning benchmark."""

    benchmark_id = "cosmos_qa"
    task_id = "narrative_reasoning"
    default_split = "validation"

    def _load_dataset(self) -> list[dict[str, Any]]:
        from datasets import load_dataset

        ds = load_dataset("cosmos_qa", split=self.split)
        items: list[dict[str, Any]] = []
        for idx, row in enumerate(ds):
            context = (row.get("context") or "").strip()
            question = (row.get("question") or "").strip()
            answer0 = (row.get("answer0") or "").strip()
            answer1 = (row.get("answer1") or "").strip()
            answer2 = (row.get("answer2") or "").strip()
            answer3 = (row.get("answer3") or "").strip()
            label = row.get("label")

            if not context or not question:
                continue
            if not answer0 or not answer1 or not answer2 or not answer3:
                continue
            if label is None or label not in _LABEL_TO_LETTER:
                continue

            native_id = row.get("id") or str(idx)

            items.append({
                "_native_id": str(native_id),
                "_context": context,
                "_question": question,
                "_answer0": answer0,
                "_answer1": answer1,
                "_answer2": answer2,
                "_answer3": answer3,
                "_label": label,
                "_inferred_attrs": {
                    "context_length": _context_length(context),
                    "answer_count": "four",
                },
            })
        return items

    def _to_record(self, item: dict[str, Any], seq: int) -> dict[str, Any]:
        prompt = (
            "Read the passage and choose the best answer to the question.\n\n"
            f"Passage:\n{item['_context']}\n\n"
            f"Question: {item['_question']}\n\n"
            f"A. {item['_answer0']}\nB. {item['_answer1']}\n"
            f"C. {item['_answer2']}\nD. {item['_answer3']}\n\n"
            "Answer with the letter of the best answer (A, B, C, or D)."
        )
        return {
            "id": self._make_id(seq),
            "task_id": self.task_id,
            "teacher_model_id": self.teacher_id,
            "sampled_target_attributes": item["_inferred_attrs"],
            "prompt": prompt,
            "reference_response": _LABEL_TO_LETTER[item["_label"]],
            "generated_at": self._now_iso(),
            "benchmark_id": self.benchmark_id,
            "benchmark_split": self.split,
            "benchmark_native_id": item["_native_id"],
            "benchmark_native_score": None,
        }
