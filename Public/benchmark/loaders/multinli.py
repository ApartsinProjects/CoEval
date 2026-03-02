"""MultiNLI benchmark loader.

Dataset  : multi_nli (HuggingFace)
Split    : validation_matched
Prompt   : Premise + hypothesis; ask for entailment label.
Reference: "entailment", "neutral", or "contradiction".
GT metric: Exact-match on the label string.
Attributes:
  - genre : source genre (telephone/travel/government/slate/fiction/nineeleven/
             letters/oup/verbatim); first token lowercase if multi-word.
  - label : the NLI label string ("entailment"/"neutral"/"contradiction")
"""
from __future__ import annotations

from typing import Any

from .base import BenchmarkLoader

_LABEL_TO_STR = {0: "entailment", 1: "neutral", 2: "contradiction"}


def _normalise_genre(raw: str) -> str:
    return (raw or "fiction").strip().lower().split()[0]


class MultiNLILoader(BenchmarkLoader):
    """Loader for the MultiNLI natural-language-inference benchmark."""

    benchmark_id = "multinli"
    task_id = "natural_language_inference"
    default_split = "validation_matched"

    def _load_dataset(self) -> list[dict[str, Any]]:
        from datasets import load_dataset

        ds = load_dataset("multi_nli", split=self.split)
        items: list[dict[str, Any]] = []
        for idx, row in enumerate(ds):
            premise = (row.get("premise") or "").strip()
            hypothesis = (row.get("hypothesis") or "").strip()
            label = row.get("label")

            if not premise or not hypothesis:
                continue
            if label is None or label == -1:
                continue
            if label not in _LABEL_TO_STR:
                continue

            label_str = _LABEL_TO_STR[label]
            genre = _normalise_genre(row.get("genre") or "fiction")

            items.append({
                "_native_id": str(idx),
                "_premise": premise,
                "_hypothesis": hypothesis,
                "_label_str": label_str,
                "_inferred_attrs": {
                    "genre": genre,
                    "label": label_str,
                },
            })
        return items

    def _to_record(self, item: dict[str, Any], seq: int) -> dict[str, Any]:
        prompt = (
            "Given the premise and hypothesis, determine the relationship.\n\n"
            f"Premise: {item['_premise']}\n\n"
            f"Hypothesis: {item['_hypothesis']}\n\n"
            "Answer with exactly one of: entailment, neutral, contradiction"
        )
        return {
            "id": self._make_id(seq),
            "task_id": self.task_id,
            "teacher_model_id": self.teacher_id,
            "sampled_target_attributes": item["_inferred_attrs"],
            "prompt": prompt,
            "reference_response": item["_label_str"],
            "generated_at": self._now_iso(),
            "benchmark_id": self.benchmark_id,
            "benchmark_split": self.split,
            "benchmark_native_id": item["_native_id"],
            "benchmark_native_score": None,
        }
