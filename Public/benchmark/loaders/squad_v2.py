"""SQuAD v2 benchmark loader.

Dataset  : rajpurkar/squad_v2 (HuggingFace)
Split    : validation
Prompt   : A passage and a question; instruct the model to answer from the passage
           or reply "unanswerable" if the answer is not present.
Reference: First answer text from answers["text"], or "unanswerable" for questions
           with no answer.
GT metric: Exact-match / F1 for answerable; exact-match on "unanswerable" for
           unanswerable questions.
Attributes:
  - answerability  : "answerable" or "unanswerable"
  - passage_length : "short" (<80 words) / "medium" (<200 words) / "long" (>=200)
"""
from __future__ import annotations

from typing import Any

from .base import BenchmarkLoader


def _passage_length(context: str) -> str:
    n = len(context.split())
    if n < 80:
        return "short"
    if n < 200:
        return "medium"
    return "long"


class SQuADv2Loader(BenchmarkLoader):
    """Loader for the SQuAD v2 reading-comprehension QA benchmark."""

    benchmark_id = "squad_v2"
    task_id = "reading_comprehension_qa"
    default_split = "validation"

    def _load_dataset(self) -> list[dict[str, Any]]:
        from datasets import load_dataset

        ds = load_dataset("rajpurkar/squad_v2", split=self.split)
        items: list[dict[str, Any]] = []
        for idx, row in enumerate(ds):
            question = (row.get("question") or "").strip()
            context = (row.get("context") or "").strip()
            answers = row.get("answers") or {}
            answer_texts = answers.get("text") or []

            if not question or not context:
                continue

            if answer_texts:
                reference = answer_texts[0].strip()
                answerability = "answerable"
            else:
                reference = "unanswerable"
                answerability = "unanswerable"

            native_id = row.get("id") or str(idx)

            items.append({
                "_native_id": str(native_id),
                "_question": question,
                "_context": context,
                "_reference": reference,
                "_inferred_attrs": {
                    "answerability": answerability,
                    "passage_length": _passage_length(context),
                },
            })
        return items

    def _to_record(self, item: dict[str, Any], seq: int) -> dict[str, Any]:
        prompt = (
            "Read the passage and answer the question. "
            "If the answer is not contained in the passage, respond with 'unanswerable'.\n\n"
            f"Passage:\n{item['_context']}\n\n"
            f"Question: {item['_question']}"
        )
        return {
            "id": self._make_id(seq),
            "task_id": self.task_id,
            "teacher_model_id": self.teacher_id,
            "sampled_target_attributes": item["_inferred_attrs"],
            "prompt": prompt,
            "reference_response": item["_reference"],
            "generated_at": self._now_iso(),
            "benchmark_id": self.benchmark_id,
            "benchmark_split": self.split,
            "benchmark_native_id": item["_native_id"],
            "benchmark_native_score": None,
        }
