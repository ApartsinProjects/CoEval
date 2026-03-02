"""COPA (Choice Of Plausible Alternatives) benchmark loader.

Dataset  : super_glue, config=copa (HuggingFace)
Split    : validation
Prompt   : Statement + two choices (A/B); framing depends on question type
           ("cause" → "What was the CAUSE…", "effect" → "What happened as a result…").
Reference: "A" or "B" mapped from the integer label field (0→"A", 1→"B").
GT metric: Exact-match on the answer letter.
Attributes:
  - question_type : "cause" or "effect"
  - difficulty    : always "medium"
"""
from __future__ import annotations

from typing import Any

from .base import BenchmarkLoader

_LABEL_TO_LETTER = {0: "A", 1: "B"}


class COPALoader(BenchmarkLoader):
    """Loader for the COPA causal-reasoning benchmark (SuperGLUE)."""

    benchmark_id = "copa"
    task_id = "causal_reasoning"
    default_split = "validation"

    def _load_dataset(self) -> list[dict[str, Any]]:
        from datasets import load_dataset

        ds = load_dataset("super_glue", "copa", split=self.split)
        items: list[dict[str, Any]] = []
        for idx, row in enumerate(ds):
            premise = (row.get("premise") or "").strip()
            choice1 = (row.get("choice1") or "").strip()
            choice2 = (row.get("choice2") or "").strip()
            question = (row.get("question") or "").strip()
            label = row.get("label")

            if not premise or not choice1 or not choice2 or not question:
                continue
            if label is None or label not in _LABEL_TO_LETTER:
                continue

            native_id = str(row.get("idx") if row.get("idx") is not None else idx)

            items.append({
                "_native_id": native_id,
                "_premise": premise,
                "_choice1": choice1,
                "_choice2": choice2,
                "_question": question,
                "_label": label,
                "_inferred_attrs": {
                    "question_type": question,
                    "difficulty": "medium",
                },
            })
        return items

    def _to_record(self, item: dict[str, Any], seq: int) -> dict[str, Any]:
        if item["_question"] == "cause":
            prompt = (
                f"What was the CAUSE of the following?\n\n"
                f"Statement: {item['_premise']}\n\n"
                f"A. {item['_choice1']}\nB. {item['_choice2']}\n\n"
                "Answer with A or B."
            )
        else:
            prompt = (
                f"What happened as a result of the following?\n\n"
                f"Statement: {item['_premise']}\n\n"
                f"A. {item['_choice1']}\nB. {item['_choice2']}\n\n"
                "Answer with A or B."
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
