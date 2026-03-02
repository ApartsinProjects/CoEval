"""Loader for SAMSum dialogue summarization benchmark.

Dataset : Samsung/samsum
Task    : dialogue_summarization
Metric  : bertscore
Split   : test

SAMSum contains messenger-style dialogues paired with human-written
summaries.  Speaker count is inferred by finding unique "Name:" patterns
at the start of lines.
"""
from __future__ import annotations

import re
from typing import Any

from .base import BenchmarkLoader


class SAMSumLoader(BenchmarkLoader):
    """Loads SAMSum test split for dialogue summarisation evaluation."""

    benchmark_id: str = "samsum"
    task_id: str = "dialogue_summarization"
    default_split: str = "test"

    # ------------------------------------------------------------------
    # Dataset loading
    # ------------------------------------------------------------------

    def _load_dataset(self) -> list[dict[str, Any]]:
        from datasets import load_dataset  # noqa: PLC0415

        ds = load_dataset("Samsung/samsum", split=self.split)
        items: list[dict[str, Any]] = []
        for idx, row in enumerate(ds):
            dialogue: str = row.get("dialogue") or ""
            summary: str = row.get("summary") or ""
            if not dialogue or not summary:
                continue
            speakers = len(set(re.findall(r"^(\w+):", dialogue, re.MULTILINE)))
            num_speakers = "two" if speakers <= 2 else "three_plus"
            word_count = len(dialogue.split())
            if word_count < 100:
                dialogue_length = "short"
            elif word_count < 250:
                dialogue_length = "medium"
            else:
                dialogue_length = "long"
            items.append(
                {
                    "dialogue": dialogue,
                    "summary": summary,
                    "_native_id": row.get("id") or str(idx),
                    "_inferred_attrs": {
                        "dialogue_length": dialogue_length,
                        "num_speakers": num_speakers,
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
            "Summarize the following conversation in 1-3 sentences.\n\n"
            f"Conversation:\n{item['dialogue']}"
        )
        return {
            "id": self._make_id(seq),
            "task_id": self.task_id,
            "teacher_model_id": self.teacher_id,
            "sampled_target_attributes": attrs,
            "prompt": prompt,
            "reference_response": item["summary"],
            "generated_at": self._now_iso(),
            "benchmark_id": self.benchmark_id,
            "benchmark_split": self.split,
            "benchmark_native_id": item["_native_id"],
            "benchmark_native_score": None,
        }
