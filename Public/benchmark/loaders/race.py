"""RACE benchmark loader for the race_reading_comprehension task.

Dataset : ehovy/race  (HuggingFace)
Config  : "high" (high-school level) or "middle" or "all"
Split   : test
Prompt  : Reading passage + question + 4 multiple-choice options
Reference: Correct answer text

Attribute mapping
-----------------
passage_type  : inferred from article content
    narrative      story / fiction cues (first-person, past tense)
    expository     informational text (no strong stance markers)
    argumentative  persuasive cues (should / must / argue / believe)

question_type : inferred from question wording
    factual        direct recall from passage (who / what / when / where)
    inferential    inference / implication (suggest / imply / infer)
    vocabulary     word meaning (what does … mean / the word … refers to)
"""
from __future__ import annotations

from typing import Any

from .base import BenchmarkLoader

_NARRATIVE_WORDS = frozenset([
    "i felt", "she said", "he remembered", "once upon",
    "i was", "we went", "told me", "i thought",
])
_ARGUMENTATIVE_WORDS = frozenset([
    " should ", " must ", "we argue", "i believe",
    "it is important", "we ought", "in my opinion",
])
_INFERENTIAL_WORDS = frozenset([
    "suggest", "implies", "infer", "probably",
    "most likely", "can be concluded", "according to",
])
_VOCABULARY_WORDS = frozenset([
    "the word ", "what does ", "means ", " refers to",
    "the phrase ", "underlined word",
])


def _infer_passage_type(article: str) -> str:
    lower = article.lower()
    if any(w in lower for w in _ARGUMENTATIVE_WORDS):
        return "argumentative"
    if any(w in lower for w in _NARRATIVE_WORDS):
        return "narrative"
    return "expository"


def _infer_question_type(question: str) -> str:
    q = question.lower()
    if any(w in q for w in _VOCABULARY_WORDS):
        return "vocabulary"
    if any(w in q for w in _INFERENTIAL_WORDS):
        return "inferential"
    return "factual"


_MAX_ARTICLE_CHARS = 1_800   # truncation limit to keep prompts manageable


class RACELoader(BenchmarkLoader):
    """Loader for the RACE reading-comprehension dataset (high or middle school)."""

    benchmark_id = "race"
    task_id = "race_reading_comprehension"
    default_split = "test"

    def __init__(
        self,
        attribute_map: dict[str, list[str]],
        sample_size: int = 620,
        split: str | None = None,
        seed: int = 42,
        level: str = "high",
    ) -> None:
        super().__init__(attribute_map, sample_size, split, seed)
        self.level = level

    @property
    def teacher_id(self) -> str:
        return f"race-{self.level}"

    def _load_dataset(self) -> list[dict[str, Any]]:
        from datasets import load_dataset  # type: ignore

        ds = load_dataset("ehovy/race", self.level, split=self.split)
        items: list[dict[str, Any]] = []
        _labels = ["A", "B", "C", "D"]

        for row in ds:
            article: str  = (row.get("article") or "").strip()
            question: str = (row.get("question") or "").strip()
            options: list[str] = row.get("options", [])
            answer_label: str = (row.get("answer") or "").strip()
            example_id: str = str(row.get("example_id", ""))

            if not article or not question or not options or not answer_label:
                continue

            options_text = "\n".join(
                f"({lbl}) {opt}" for lbl, opt in zip(_labels, options)
            )
            # Resolve correct answer text
            try:
                answer_idx = _labels.index(answer_label)
                correct_text = options[answer_idx]
            except (ValueError, IndexError):
                correct_text = options[0]

            # Truncate very long articles
            display_article = article
            if len(article) > _MAX_ARTICLE_CHARS:
                display_article = article[:_MAX_ARTICLE_CHARS] + " …"

            items.append({
                "_native_id":      example_id,
                "_article":        display_article,
                "_question":       question,
                "_options_text":   options_text,
                "_correct_text":   correct_text,
                "_inferred_attrs": {
                    "passage_type":  _infer_passage_type(article[:500]),
                    "question_type": _infer_question_type(question),
                },
            })
        return items

    def _to_record(self, item: dict[str, Any], seq: int) -> dict[str, Any]:
        prompt = (
            f"Reading Passage:\n{item['_article']}\n\n"
            f"Question: {item['_question']}\n\n"
            f"Options:\n{item['_options_text']}\n\n"
            f"Select the correct answer and explain your reasoning based on the passage."
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
