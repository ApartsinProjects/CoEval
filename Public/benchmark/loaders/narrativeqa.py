"""Loader for NarrativeQA (DeepMind).

Dataset : deepmind/narrativeqa
Task    : narrative_qa
Metric  : bleu (free-form answers over long story summaries)
Split   : test

Each row has a document (with a "summary" key), a question dict (with a
"text" key), and a list of answer dicts (each with a "text" key).
We skip rows where the answer list is empty or the summary is empty.
"""
from __future__ import annotations

from typing import Any

from .base import BenchmarkLoader


class NarrativeQALoader(BenchmarkLoader):
    """Loads NarrativeQA test split for narrative comprehension evaluation."""

    benchmark_id: str = "narrativeqa"
    task_id: str = "narrative_qa"
    default_split: str = "test"

    # ------------------------------------------------------------------
    # Dataset loading
    # ------------------------------------------------------------------

    def _load_dataset(self) -> list[dict[str, Any]]:
        from datasets import load_dataset  # noqa: PLC0415

        ds = load_dataset("deepmind/narrativeqa", split=self.split)
        items: list[dict[str, Any]] = []
        for idx, row in enumerate(ds):
            answers: list[dict] = row.get("answers") or []
            document: dict = row.get("document") or {}
            summary: str = document.get("summary", {})
            # summary may itself be a dict with a "text" sub-key
            if isinstance(summary, dict):
                summary = summary.get("text") or ""
            if not answers or not summary:
                continue
            question_field = row.get("question") or {}
            question_text: str = (
                question_field.get("text") if isinstance(question_field, dict) else str(question_field)
            ) or ""
            first_answer_text: str = answers[0].get("text") or ""
            words = first_answer_text.split()
            if len(words) <= 5:
                answer_length = "short"
            elif len(words) <= 15:
                answer_length = "medium"
            else:
                answer_length = "long"
            document_kind: str = document.get("kind") or "gutenberg"
            items.append(
                {
                    "summary": summary,
                    "question": question_text,
                    "answers": answers,
                    "_native_id": str(idx),
                    "_inferred_attrs": {
                        "document_kind": document_kind,
                        "answer_length": answer_length,
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
            "Read the following story summary and answer the question.\n\n"
            f"Summary:\n{item['summary']}\n\n"
            f"Question: {item['question']}\n\n"
            "Provide a concise answer."
        )
        return {
            "id": self._make_id(seq),
            "task_id": self.task_id,
            "teacher_model_id": self.teacher_id,
            "sampled_target_attributes": attrs,
            "prompt": prompt,
            "reference_response": item["answers"][0]["text"],
            "generated_at": self._now_iso(),
            "benchmark_id": self.benchmark_id,
            "benchmark_split": self.split,
            "benchmark_native_id": item["_native_id"],
            "benchmark_native_score": None,
        }
