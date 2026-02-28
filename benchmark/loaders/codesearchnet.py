"""CodeSearchNet benchmark loader for the code_explanation task.

Dataset : code_search_net  (HuggingFace)
Language: Python (default)
Split   : validation
Prompt  : Python function source code (stripped of its docstring)
Reference: The function's docstring (gold explanation)
GT metric: BERTScore-F1 between student explanation and reference docstring

Attribute mapping
-----------------
complexity : inferred from function line count
    beginner       ≤ 10 lines
    intermediate   11–30 lines
    advanced       > 30 lines

snippet_type : inferred from function name / signature heuristics
    function           default
    class_definition   if first non-blank line starts with "class "
    algorithm          if name contains sort/search/tree/graph/hash/dp
    database_query     if contains SQL-like keywords

audience : always "junior_developer" for CodeSearchNet (real-world Python OSS)
"""
from __future__ import annotations

import re
from typing import Any

from .base import BenchmarkLoader


_ALGO_PATTERN = re.compile(
    r"(sort|search|tree|graph|hash|heap|dp|dynamic|backtrack|bfs|dfs|dijkstra)",
    re.IGNORECASE,
)
_SQL_PATTERN = re.compile(r"\b(SELECT|INSERT|UPDATE|DELETE|FROM|WHERE|JOIN)\b", re.IGNORECASE)


def _strip_docstring(code: str) -> str:
    """Remove leading docstring from function body (keep signature)."""
    # Simple heuristic: remove triple-quoted string right after def line
    code = code.strip()
    cleaned = re.sub(
        r'(def\s+\w+[^:]*:)\s*"""[\s\S]*?"""',
        r"\1",
        code,
        count=1,
    )
    cleaned = re.sub(
        r"(def\s+\w+[^:]*:)\s*'''[\s\S]*?'''",
        r"\1",
        cleaned,
        count=1,
    )
    return cleaned.strip()


def _infer_complexity(code: str) -> str:
    lines = [l for l in code.splitlines() if l.strip()]
    n = len(lines)
    if n > 30:
        return "advanced"
    if n > 10:
        return "intermediate"
    return "beginner"


def _infer_snippet_type(code: str, func_name: str) -> str:
    if code.lstrip().startswith("class "):
        return "class_definition"
    if _SQL_PATTERN.search(code):
        return "database_query"
    if _ALGO_PATTERN.search(func_name):
        return "algorithm"
    return "function"


class CodeSearchNetLoader(BenchmarkLoader):
    benchmark_id = "codesearchnet"
    task_id = "code_explanation"
    default_split = "validation"

    def __init__(self, language: str = "python", **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.language = language

    def _load_dataset(self) -> list[dict[str, Any]]:
        from datasets import load_dataset  # type: ignore

        ds = load_dataset(
            "code_search_net",
            self.language,
            split=self.split,
            trust_remote_code=True,
        )
        items = []
        for row in ds:
            code = (row.get("func_code_string") or "").strip()
            doc = (row.get("func_documentation_string") or "").strip()
            func_name = (row.get("func_name") or "").strip()

            if not code or not doc or len(doc) < 20:
                continue

            # Strip docstring from code so student has to explain from code alone
            code_no_doc = _strip_docstring(code)
            if not code_no_doc:
                code_no_doc = code

            complexity = _infer_complexity(code)
            snippet_type = _infer_snippet_type(code, func_name)

            items.append({
                "_native_id": func_name,
                "_code": code_no_doc,
                "_docstring": doc,
                "_inferred_attrs": {
                    "complexity": complexity,
                    "snippet_type": snippet_type,
                    "language": self.language,
                },
            })
        return items

    def _to_record(self, item: dict[str, Any], seq: int) -> dict[str, Any]:
        prompt = (
            f"Explain what the following {self.language} code does:\n\n"
            f"```{self.language}\n{item['_code']}\n```"
        )
        return {
            "id": self._make_id(seq),
            "task_id": self.task_id,
            "teacher_model_id": f"benchmark:{self.benchmark_id}",
            "sampled_target_attributes": item["_inferred_attrs"],
            "prompt": prompt,
            "reference_response": item["_docstring"],
            "generated_at": self._now_iso(),
            "benchmark_id": self.benchmark_id,
            "benchmark_split": self.split,
            "benchmark_native_id": item["_native_id"],
            "benchmark_native_score": None,
        }
