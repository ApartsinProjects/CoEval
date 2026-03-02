"""WinoGrande benchmark loader.

Dataset  : winogrande (HuggingFace), config=winogrande_xl
Split    : validation
Prompt   : A fill-in-the-blank sentence with two options (A/B); ask for letter answer.
Reference: "A" or "B" mapped from the "answer" field ("1"→"A", "2"→"B").
GT metric: Exact-match on the answer letter.
Attributes:
  - option_length : "short" (max option <=5 words) / "medium" (<=10) / "long" (>10)
  - format        : always "fill_in_blank"
"""
from __future__ import annotations

from typing import Any

from .base import BenchmarkLoader

_ANSWER_TO_LETTER = {"1": "A", "2": "B"}


def _option_length(option1: str, option2: str) -> str:
    max_len = max(len(option1.split()), len(option2.split()))
    if max_len <= 5:
        return "short"
    if max_len <= 10:
        return "medium"
    return "long"


class WinograndeLoader(BenchmarkLoader):
    """Loader for the WinoGrande commonsense-reasoning benchmark."""

    benchmark_id = "winogrande"
    task_id = "commonsense_reasoning"
    default_split = "validation"

    def _load_dataset(self) -> list[dict[str, Any]]:
        from datasets import load_dataset

        ds = load_dataset("winogrande", "winogrande_xl", split=self.split)
        items: list[dict[str, Any]] = []
        for idx, row in enumerate(ds):
            sentence = (row.get("sentence") or "").strip()
            option1 = (row.get("option1") or "").strip()
            option2 = (row.get("option2") or "").strip()
            answer = str(row.get("answer") or "").strip()

            if not sentence or not option1 or not option2:
                continue
            if answer not in _ANSWER_TO_LETTER:
                continue

            items.append({
                "_native_id": str(idx),
                "_sentence": sentence,
                "_option1": option1,
                "_option2": option2,
                "_answer": answer,
                "_inferred_attrs": {
                    "option_length": _option_length(option1, option2),
                    "format": "fill_in_blank",
                },
            })
        return items

    def _to_record(self, item: dict[str, Any], seq: int) -> dict[str, Any]:
        prompt = (
            "Complete the sentence by choosing the most appropriate option.\n\n"
            f"Sentence: {item['_sentence']}\n\n"
            f"A. {item['_option1']}\nB. {item['_option2']}\n\n"
            "Answer with the letter of the correct option (A or B)."
        )
        return {
            "id": self._make_id(seq),
            "task_id": self.task_id,
            "teacher_model_id": self.teacher_id,
            "sampled_target_attributes": item["_inferred_attrs"],
            "prompt": prompt,
            "reference_response": _ANSWER_TO_LETTER[item["_answer"]],
            "generated_at": self._now_iso(),
            "benchmark_id": self.benchmark_id,
            "benchmark_split": self.split,
            "benchmark_native_id": item["_native_id"],
            "benchmark_native_score": None,
        }
