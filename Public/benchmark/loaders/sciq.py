"""SciQ benchmark loader for the sciq_science_questions task.

Dataset : allenai/sciq  (HuggingFace)
Split   : test  (1,000 questions)
Prompt  : Science question + (optional) background support + 4 options
Reference: Correct answer text

Attribute mapping
-----------------
science_domain  : inferred from question keywords
    biology       cell / organism / gene / species / plant / animal
    chemistry     element / compound / reaction / bond / acid / molecule
    physics       force / energy / wave / light / velocity / mass / gravity
    earth_science  everything else (geology, astronomy, ecology, …)

question_type   : inferred from question phrasing
    concept_identification   what is / what are / which is
    mechanism               how does / how do / process / mechanism
    classification           all other (classify / identify / label)
"""
from __future__ import annotations

import random
from typing import Any

from .base import BenchmarkLoader

_BIOLOGY_WORDS = frozenset([
    "cell", "organism", "species", "gene", "plant", "animal",
    "body", "blood", "tissue", "protein", "dna", "evolution",
    "photosynthesis", "metabolism", "enzyme",
])
_CHEMISTRY_WORDS = frozenset([
    "element", "compound", "reaction", "bond", "acid", "molecule",
    "atom", "ion", "solution", "oxidation", "electron", "periodic",
    "base", "ph ", "catalyst",
])
_PHYSICS_WORDS = frozenset([
    "force", "energy", "wave", "light", "velocity", "mass",
    "gravity", "motion", "acceleration", "charge", "electric",
    "magnetic", "thermal", "pressure", "frequency",
])


def _infer_domain(question: str) -> str:
    q = question.lower()
    if any(w in q for w in _BIOLOGY_WORDS):
        return "biology"
    if any(w in q for w in _CHEMISTRY_WORDS):
        return "chemistry"
    if any(w in q for w in _PHYSICS_WORDS):
        return "physics"
    return "earth_science"


def _infer_question_type(question: str) -> str:
    q = question.lower()
    if any(q.startswith(w) for w in ("what is", "what are", "which is", "which are")):
        return "concept_identification"
    if any(w in q for w in ("how does", "how do", "process", "mechanism", "why does", "why do")):
        return "mechanism"
    return "classification"


class SciQLoader(BenchmarkLoader):
    """Loader for the SciQ science multiple-choice dataset."""

    benchmark_id = "sciq"
    task_id = "sciq_science_questions"
    default_split = "test"

    @property
    def teacher_id(self) -> str:
        return "sciq"

    def _load_dataset(self) -> list[dict[str, Any]]:
        from datasets import load_dataset  # type: ignore

        ds = load_dataset("allenai/sciq", split=self.split)
        _labels = ["A", "B", "C", "D"]

        items: list[dict[str, Any]] = []
        for idx, row in enumerate(ds):
            question: str     = (row.get("question") or "").strip()
            correct: str      = (row.get("correct_answer") or "").strip()
            support: str      = (row.get("support") or "").strip()
            d1: str = (row.get("distractor1") or "").strip()
            d2: str = (row.get("distractor2") or "").strip()
            d3: str = (row.get("distractor3") or "").strip()

            if not question or not correct:
                continue

            # Build shuffled options so the correct answer isn't always first
            options = [correct, d1, d2, d3]
            rng = random.Random(self.seed + idx)
            rng.shuffle(options)
            correct_label_idx = options.index(correct)

            options_text = "\n".join(
                f"({lbl}) {opt}" for lbl, opt in zip(_labels, options)
            )

            items.append({
                "_native_id":      str(idx),
                "_question":       question,
                "_support":        support,
                "_options_text":   options_text,
                "_correct_text":   correct,
                "_correct_label":  _labels[correct_label_idx],
                "_inferred_attrs": {
                    "science_domain": _infer_domain(question),
                    "question_type":  _infer_question_type(question),
                },
            })
        return items

    def _to_record(self, item: dict[str, Any], seq: int) -> dict[str, Any]:
        support = item["_support"]
        support_block = (
            f"\nBackground context: {support}\n"
            if support else ""
        )
        prompt = (
            f"Science Question: {item['_question']}"
            f"{support_block}\n\n"
            f"Options:\n{item['_options_text']}\n\n"
            f"Select the correct answer and briefly explain the scientific concept involved."
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
