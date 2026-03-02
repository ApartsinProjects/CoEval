"""BIG-Bench Hard (BBH) benchmark loader for the reasoning_and_logic task.

Dataset : maveriq/bigbenchhard  (HuggingFace; 23 sub-tasks)
Split   : train  (the only available split; each sub-task has ~250 examples)
Prompt  : Task description prepended to the question
Reference: Correct answer string
GT metric: Exact-match accuracy

Sub-tasks loaded (23 total):
    boolean_expressions, causal_judgement, date_understanding,
    disambiguation_qa, dyck_languages, formal_fallacies,
    geometric_shapes, hyperbaton, logical_deduction_five_objects,
    logical_deduction_seven_objects, logical_deduction_three_objects,
    movie_recommendation, multistep_arithmetic_two,
    navigate, object_counting, penguins_in_a_table, reasoning_about_colored_objects,
    ruin_names, salient_translation_error_detection, snarks,
    sports_understanding, temporal_sequences, tracking_shuffled_objects_five_objects,
    tracking_shuffled_objects_seven_objects, tracking_shuffled_objects_three_objects,
    web_of_lies, word_sorting

Attribute mapping
-----------------
task_type : task cluster (reasoning, language, math, logic, knowledge)
difficulty : inferred from answer complexity
    low     boolean / yes-no answers
    medium  multi-word or choice answers
    high    multi-step / open-ended answers
"""
from __future__ import annotations

from typing import Any

from .base import BenchmarkLoader


# BBH sub-tasks available on HuggingFace (maveriq/bigbenchhard)
_BBH_TASKS: list[str] = [
    "boolean_expressions",
    "causal_judgement",
    "date_understanding",
    "disambiguation_qa",
    "dyck_languages",
    "formal_fallacies",
    "geometric_shapes",
    "hyperbaton",
    "logical_deduction_five_objects",
    "logical_deduction_seven_objects",
    "logical_deduction_three_objects",
    "movie_recommendation",
    "multistep_arithmetic_two",
    "navigate",
    "object_counting",
    "penguins_in_a_table",
    "reasoning_about_colored_objects",
    "ruin_names",
    "salient_translation_error_detection",
    "snarks",
    "sports_understanding",
    "temporal_sequences",
    "tracking_shuffled_objects_five_objects",
    "tracking_shuffled_objects_seven_objects",
    "tracking_shuffled_objects_three_objects",
    "web_of_lies",
    "word_sorting",
]

# Cluster map: task_name → category
_TASK_TYPE: dict[str, str] = {
    "boolean_expressions": "logic",
    "causal_judgement": "reasoning",
    "date_understanding": "reasoning",
    "disambiguation_qa": "language",
    "dyck_languages": "logic",
    "formal_fallacies": "logic",
    "geometric_shapes": "reasoning",
    "hyperbaton": "language",
    "logical_deduction_five_objects": "logic",
    "logical_deduction_seven_objects": "logic",
    "logical_deduction_three_objects": "logic",
    "movie_recommendation": "knowledge",
    "multistep_arithmetic_two": "math",
    "navigate": "reasoning",
    "object_counting": "math",
    "penguins_in_a_table": "reasoning",
    "reasoning_about_colored_objects": "reasoning",
    "ruin_names": "language",
    "salient_translation_error_detection": "language",
    "snarks": "language",
    "sports_understanding": "knowledge",
    "temporal_sequences": "reasoning",
    "tracking_shuffled_objects_five_objects": "reasoning",
    "tracking_shuffled_objects_seven_objects": "reasoning",
    "tracking_shuffled_objects_three_objects": "reasoning",
    "web_of_lies": "logic",
    "word_sorting": "language",
}


def _infer_difficulty(answer: str) -> str:
    a = (answer or "").strip().lower()
    if a in ("true", "false", "yes", "no", "valid", "invalid"):
        return "low"
    if len(a.split()) <= 4:
        return "medium"
    return "high"


class BigBenchHardLoader(BenchmarkLoader):
    """Loader for the BIG-Bench Hard (BBH) dataset.

    Aggregates all 27 sub-tasks into a single JSONL file tagged with the
    sub-task name as a target attribute.
    """

    benchmark_id = "bigbench_hard"
    task_id = "reasoning_and_logic"
    default_split = "train"  # BBH only has 'train'

    @property
    def teacher_id(self) -> str:
        return "bigbench-hard"

    def _load_dataset(self) -> list[dict[str, Any]]:
        from datasets import load_dataset  # type: ignore

        items: list[dict[str, Any]] = []
        for subtask in _BBH_TASKS:
            try:
                ds = load_dataset(
                    "maveriq/bigbenchhard",
                    subtask,
                    split=self.split,
                    trust_remote_code=True,
                )
            except Exception:
                continue  # Skip unavailable sub-tasks gracefully

            for idx, row in enumerate(ds):
                input_text: str = (row.get("input") or "").strip()
                target: str = (row.get("target") or "").strip()

                if not input_text or not target:
                    continue

                items.append({
                    "_native_id": f"{subtask}__{idx}",
                    "_subtask": subtask,
                    "_input": input_text,
                    "_target": target,
                    "_inferred_attrs": {
                        "task_type": _TASK_TYPE.get(subtask, "reasoning"),
                        "difficulty": _infer_difficulty(target),
                    },
                })
        return items

    def _to_record(self, item: dict[str, Any], seq: int) -> dict[str, Any]:
        subtask_label = item["_subtask"].replace("_", " ").title()
        prompt = (
            f"BIG-Bench Task: {subtask_label}\n\n"
            f"{item['_input']}"
        )
        return {
            "id": self._make_id(seq),
            "task_id": self.task_id,
            "teacher_model_id": self.teacher_id,
            "sampled_target_attributes": item["_inferred_attrs"],
            "prompt": prompt,
            "reference_response": item["_target"],
            "generated_at": self._now_iso(),
            "benchmark_id": self.benchmark_id,
            "benchmark_split": self.split,
            "benchmark_native_id": item["_native_id"],
            "benchmark_native_score": None,
        }
