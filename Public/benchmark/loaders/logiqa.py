"""LogiQA benchmark loader.

Dataset  : lucasmccabe/logiqa (HuggingFace)
Split    : test
Prompt   : Passage + question + four labelled options (A-D); ask for letter answer.
Reference: Single letter "A", "B", "C", or "D" derived from the integer label field.
GT metric: Exact-match on the answer letter.
Attributes:
  - passage_length : "short" (<50 words) / "medium" (<100 words) / "long" (>=100 words)
  - reasoning_type : always "logical"
"""
from __future__ import annotations

from typing import Any

from .base import BenchmarkLoader

_LABEL_TO_LETTER = {0: "A", 1: "B", 2: "C", 3: "D"}


def _passage_length(context: str) -> str:
    n = len(context.split())
    if n < 50:
        return "short"
    if n < 100:
        return "medium"
    return "long"


class LogiQALoader(BenchmarkLoader):
    """Loader for the LogiQA logical-reasoning benchmark."""

    benchmark_id = "logiqa"
    task_id = "logical_reasoning"
    default_split = "test"

    def _load_dataset(self) -> list[dict[str, Any]]:
        from datasets import load_dataset

        ds = load_dataset("lucasmccabe/logiqa", split=self.split)
        items: list[dict[str, Any]] = []
        for idx, row in enumerate(ds):
            context = (row.get("context") or "").strip()
            question = (row.get("question") or "").strip()
            options = row.get("options") or []
            label = row.get("label")

            if not context or not question or len(options) < 4 or label is None:
                continue
            if label not in _LABEL_TO_LETTER:
                continue

            items.append({
                "_native_id": str(row.get("id") if row.get("id") is not None else idx),
                "_context": context,
                "_question": question,
                "_options": [str(o) for o in options[:4]],
                "_label": label,
                "_inferred_attrs": {
                    "passage_length": _passage_length(context),
                    "reasoning_type": "logical",
                },
            })
        return items

    def _to_record(self, item: dict[str, Any], seq: int) -> dict[str, Any]:
        opts = item["_options"]
        prompt = (
            "Read the passage and answer the question by choosing the correct option.\n\n"
            f"Passage:\n{item['_context']}\n\n"
            f"Question: {item['_question']}\n\n"
            f"Options:\nA. {opts[0]}\nB. {opts[1]}\nC. {opts[2]}\nD. {opts[3]}\n\n"
            "Answer with the letter of the correct option (A, B, C, or D)."
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
