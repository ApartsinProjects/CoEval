"""MBPP benchmark loader for the code_generation task.

Dataset : google-research-datasets/mbpp  (HuggingFace)
Split   : test  (374 problems)
Prompt  : Natural-language description + function signature hint
Reference: Canonical Python solution
GT metric: BLEU-4 (practical proxy for Pass@1 which requires code execution)
           Set metric="execution" to evaluate via a sandboxed Python runner
           (not included; requires Docker or subprocess isolation).

Attribute mapping
-----------------
complexity : inferred from prompt/solution length
    simple    description < 100 chars or solution < 5 lines
    moderate  100–200 chars or 5–10 lines
    complex   description > 200 chars or solution > 10 lines

topic : inferred from description keywords
    string_manipulation   string, str, char, text, word
    list_operations       list, array, sequence, element
    math_computation      sum, count, number, digit, max, min, average
    data_structures       dict, set, stack, queue, tree, graph
    general               all other cases
"""
from __future__ import annotations

from typing import Any

from .base import BenchmarkLoader


_STRING_WORDS = frozenset(["string", "str", "char", "text", "word", "substring", "palindrome"])
_LIST_WORDS   = frozenset(["list", "array", "sequence", "element", "tuple", "sorted"])
_MATH_WORDS   = frozenset(["sum", "count", "number", "digit", "max", "min", "average", "product", "factorial"])
_DS_WORDS     = frozenset(["dict", "set", "stack", "queue", "tree", "graph", "heap", "linked"])


def _infer_topic(text: str) -> str:
    t = text.lower()
    if any(w in t for w in _STRING_WORDS):
        return "string_manipulation"
    if any(w in t for w in _LIST_WORDS):
        return "list_operations"
    if any(w in t for w in _MATH_WORDS):
        return "math_computation"
    if any(w in t for w in _DS_WORDS):
        return "data_structures"
    return "general"


def _infer_complexity(text: str, solution: str) -> str:
    n_chars = len(text)
    n_lines = solution.count("\n") + 1
    if n_chars < 100 or n_lines < 5:
        return "simple"
    if n_chars < 200 or n_lines < 10:
        return "moderate"
    return "complex"


class MBPPLoader(BenchmarkLoader):
    """Loader for the MBPP (Mostly Basic Python Problems) dataset."""

    benchmark_id = "mbpp"
    task_id = "code_generation"
    default_split = "test"

    @property
    def teacher_id(self) -> str:
        return "mbpp"

    def _load_dataset(self) -> list[dict[str, Any]]:
        from datasets import load_dataset  # type: ignore

        ds = load_dataset("google-research-datasets/mbpp", "sanitized", split=self.split)
        items: list[dict[str, Any]] = []
        for row in ds:
            text: str = (row.get("text") or "").strip()
            code: str = (row.get("code") or "").strip()
            task_id_raw: int = row.get("task_id") or 0
            test_list: list[str] = row.get("test_list") or []

            if not text or not code:
                continue

            items.append({
                "_native_id": str(task_id_raw),
                "_description": text,
                "_solution": code,
                "_test_list": test_list,
                "_inferred_attrs": {
                    "topic": _infer_topic(text),
                    "complexity": _infer_complexity(text, code),
                },
            })
        return items

    def _to_record(self, item: dict[str, Any], seq: int) -> dict[str, Any]:
        tests_block = ""
        if item["_test_list"]:
            tests_preview = "\n".join(item["_test_list"][:3])
            tests_block = f"\n\nExample tests:\n{tests_preview}"

        prompt = (
            f"Write a Python function that solves the following task.\n\n"
            f"Task description:\n{item['_description']}"
            f"{tests_block}\n\n"
            f"Return only the Python function definition. Do not include test code."
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
