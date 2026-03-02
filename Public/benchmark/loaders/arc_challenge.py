"""ARC-Challenge benchmark loader for the arc_science_reasoning task.

Dataset : allenai/ai2_arc  (config: ARC-Challenge)  (HuggingFace)
Split   : test  (1,172 questions)
Prompt  : Science question + 4 answer choices
Reference: Correct answer text
GT metric: Exact-match accuracy (student picks matching choice text)

Attribute mapping
-----------------
grade_band      : inferred from question complexity / vocabulary
    grade_3_5   short questions with simple vocabulary
    grade_6_8   mid-length questions
    grade_9_10  long questions with domain vocabulary

knowledge_type  : inferred from question phrasing
    factual       what / which (recall)
    conceptual    how / why / what happens (understanding)
    procedural    calculate / determine / measure (application)
"""
from __future__ import annotations

from typing import Any

from .base import BenchmarkLoader


_PROCEDURAL_WORDS = frozenset([
    "calculate", "measure", "determine", "compute", "find the",
    "predict", "estimate",
])

_CONCEPTUAL_WORDS = frozenset([
    "how does", "how do", "why does", "why do", "what happens",
    "which process", "what causes", "explain",
])


def _infer_knowledge_type(question: str) -> str:
    q = question.lower()
    if any(w in q for w in _PROCEDURAL_WORDS):
        return "procedural"
    if any(w in q for w in _CONCEPTUAL_WORDS):
        return "conceptual"
    return "factual"


def _infer_grade_band(question: str) -> str:
    words = question.split()
    n = len(words)
    if n < 14:
        return "grade_3_5"
    if n < 24:
        return "grade_6_8"
    return "grade_9_10"


class ARCChallengeLoader(BenchmarkLoader):
    """Loader for the AI2 Reasoning Challenge (ARC-Challenge) dataset."""

    benchmark_id = "arc_challenge"
    task_id = "arc_science_reasoning"
    default_split = "test"

    @property
    def teacher_id(self) -> str:
        return "arc-challenge"

    def _load_dataset(self) -> list[dict[str, Any]]:
        from datasets import load_dataset  # type: ignore

        ds = load_dataset("allenai/ai2_arc", "ARC-Challenge", split=self.split)
        items: list[dict[str, Any]] = []
        for row in ds:
            question: str = (row.get("question") or "").strip()
            choices = row.get("choices", {})
            labels: list[str] = choices.get("label", [])
            texts: list[str]  = choices.get("text", [])
            answer_key: str = (row.get("answerKey") or "").strip()

            if not question or not labels or not texts or not answer_key:
                continue

            # Build human-readable options block
            options_lines = "\n".join(
                f"({lbl}) {txt}" for lbl, txt in zip(labels, texts)
            )

            # Resolve correct answer text (answer_key may be A/B/C/D or 1/2/3/4)
            correct_text = ""
            for lbl, txt in zip(labels, texts):
                if lbl == answer_key:
                    correct_text = txt
                    break
            if not correct_text:
                # Numeric answer key (1-indexed)
                try:
                    idx = int(answer_key) - 1
                    correct_text = texts[idx] if 0 <= idx < len(texts) else texts[0]
                except (ValueError, IndexError):
                    correct_text = texts[0]

            items.append({
                "_native_id":    str(row.get("id", "")),
                "_question":     question,
                "_options_lines": options_lines,
                "_correct_text":  correct_text,
                "_inferred_attrs": {
                    "grade_band":     _infer_grade_band(question),
                    "knowledge_type": _infer_knowledge_type(question),
                },
            })
        return items

    def _to_record(self, item: dict[str, Any], seq: int) -> dict[str, Any]:
        prompt = (
            f"Science Question:\n{item['_question']}\n\n"
            f"Options:\n{item['_options_lines']}\n\n"
            f"Select the correct answer and explain your reasoning."
        )
        return {
            "id":                        self._make_id(seq),
            "task_id":                   self.task_id,
            "teacher_model_id":          self.teacher_id,
            "sampled_target_attributes": item["_inferred_attrs"],
            "prompt":                    prompt,
            "reference_response":        item["_correct_text"],
            "generated_at":              self._now_iso(),
            "benchmark_id":              self.benchmark_id,
            "benchmark_split":           self.split,
            "benchmark_native_id":       item["_native_id"],
            "benchmark_native_score":    None,
        }
