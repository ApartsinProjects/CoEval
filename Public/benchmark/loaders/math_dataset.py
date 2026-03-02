"""MATH benchmark loader for the math_problem_solving task.

Dataset : hendrycks/competition_math  (HuggingFace)
Split   : test  (5,000 problems)
Prompt  : Problem statement (LaTeX math notation preserved)
Reference: Solution text (LaTeX)
GT metric: Exact-match on the final boxed answer (\\boxed{...} extraction)
           Note: Full symbolic equivalence requires a CAS; exact-match on
           extracted answer strings is used as a practical approximation.

Attribute mapping
-----------------
subject : inferred from type field
    algebra, counting_and_probability, geometry, intermediate_algebra,
    number_theory, prealgebra, precalculus

difficulty : mapped from level field (1–5)
    easy    level 1–2
    medium  level 3
    hard    level 4–5
"""
from __future__ import annotations

from typing import Any

from .base import BenchmarkLoader


def _infer_subject(type_str: str) -> str:
    return (type_str or "algebra").lower().replace(" ", "_")


def _infer_difficulty(level: str | int) -> str:
    try:
        n = int(str(level).replace("Level ", "").strip())
    except ValueError:
        return "medium"
    if n <= 2:
        return "easy"
    if n == 3:
        return "medium"
    return "hard"


class MATHLoader(BenchmarkLoader):
    """Loader for the Hendrycks MATH competition dataset."""

    benchmark_id = "math"
    task_id = "math_problem_solving"
    default_split = "test"

    @property
    def teacher_id(self) -> str:
        return "math"

    def _load_dataset(self) -> list[dict[str, Any]]:
        from datasets import load_dataset  # type: ignore

        ds = load_dataset("hendrycks/competition_math", split=self.split)
        items: list[dict[str, Any]] = []
        for idx, row in enumerate(ds):
            problem: str = (row.get("problem") or "").strip()
            solution: str = (row.get("solution") or "").strip()
            level: str = str(row.get("level") or "Level 3")
            type_str: str = row.get("type") or "Algebra"

            if not problem or not solution:
                continue

            items.append({
                "_native_id": str(idx),
                "_problem": problem,
                "_solution": solution,
                "_inferred_attrs": {
                    "subject": _infer_subject(type_str),
                    "difficulty": _infer_difficulty(level),
                },
            })
        return items

    def _to_record(self, item: dict[str, Any], seq: int) -> dict[str, Any]:
        prompt = (
            f"Solve the following mathematics problem. "
            f"Show your work step by step and state the final answer clearly.\n\n"
            f"Problem:\n{item['_problem']}"
        )
        return {
            "id": self._make_id(seq),
            "task_id": self.task_id,
            "teacher_model_id": self.teacher_id,
            "sampled_target_attributes": item["_inferred_attrs"],
            "prompt": prompt,
            "reference_response": item["_solution"],
            "generated_at": self._now_iso(),
            "benchmark_id": self.benchmark_id,
            "benchmark_split": self.split,
            "benchmark_native_id": item["_native_id"],
            "benchmark_native_score": None,
        }
