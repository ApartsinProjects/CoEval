"""WikiTableQuestions benchmark loader for the data_interpretation task.

Dataset : wikitablequestions  (HuggingFace)
Split   : validation
Prompt  : "Here is a data table: [table as text]. Question: [question]"
Reference: The answer string(s)
GT metric: Exact-match accuracy (first answer token in answers list)

Attribute mapping
-----------------
data_type : always "pivot_table" (all WTQ items are Wikipedia tables)

insight_depth : inferred from question complexity
    surface_observation   : simple "what is..." / "how many..." questions
    analytical_interpretation : "which... most/least", comparative questions
    predictive_inference  : questions requiring arithmetic or multi-hop reasoning

audience : always "data_analyst"
"""
from __future__ import annotations

import re
from typing import Any

from .base import BenchmarkLoader


_COMPARATIVE = re.compile(
    r"\b(most|least|highest|lowest|largest|smallest|more|fewer|greater|less|compared)\b",
    re.IGNORECASE,
)
_ARITHMETIC = re.compile(
    r"\b(total|sum|average|mean|difference|percent|ratio|combine|add|subtract)\b",
    re.IGNORECASE,
)
_SIMPLE = re.compile(r"^\s*(what|who|where|when|which)\s+(is|are|was|were)\b", re.IGNORECASE)


def _infer_insight_depth(question: str) -> str:
    if _ARITHMETIC.search(question):
        return "predictive_inference"
    if _COMPARATIVE.search(question):
        return "analytical_interpretation"
    return "surface_observation"


def _table_to_text(table: dict) -> str:
    """Convert WTQ table dict to a readable plain-text table."""
    # WTQ table format: {"header": [...], "rows": [[...], ...]}
    header = table.get("header", [])
    rows = table.get("rows", [])

    if not header and not rows:
        return "[empty table]"

    # Build fixed-width text table
    col_widths = [max(len(str(h)), 4) for h in header]
    for row in rows:
        for i, cell in enumerate(row):
            if i < len(col_widths):
                col_widths[i] = max(col_widths[i], len(str(cell)))

    def fmt_row(cells: list) -> str:
        return " | ".join(
            str(c).ljust(col_widths[i]) if i < len(col_widths) else str(c)
            for i, c in enumerate(cells)
        )

    sep = "-+-".join("-" * w for w in col_widths)
    lines = [fmt_row(header), sep]
    for row in rows[:30]:  # cap at 30 rows for prompt length
        lines.append(fmt_row(row))
    if len(rows) > 30:
        lines.append(f"... ({len(rows) - 30} more rows)")

    return "\n".join(lines)


class WikiTableQuestionsLoader(BenchmarkLoader):
    benchmark_id = "wikitablequestions"
    task_id = "data_interpretation"
    default_split = "validation"

    def _load_dataset(self) -> list[dict[str, Any]]:
        from datasets import load_dataset  # type: ignore

        ds = load_dataset("wikitablequestions", split=self.split, trust_remote_code=True)
        items = []
        for row in ds:
            table = row.get("table", {})
            question = (row.get("question") or "").strip()
            answers = row.get("answers") or []

            if not question or not answers:
                continue

            table_text = _table_to_text(table)
            if len(table_text) < 20:
                continue

            reference = answers[0] if answers else ""
            if not reference:
                continue

            insight_depth = _infer_insight_depth(question)

            items.append({
                "_native_id": str(row.get("id", "")),
                "_table_text": table_text,
                "_question": question,
                "_answers": answers,
                "_inferred_attrs": {
                    "data_type": "pivot_table",
                    "insight_depth": insight_depth,
                    "audience": "data_analyst",
                },
            })
        return items

    def _to_record(self, item: dict[str, Any], seq: int) -> dict[str, Any]:
        prompt = (
            f"Here is a data table:\n\n"
            f"{item['_table_text']}\n\n"
            f"Question: {item['_question']}"
        )
        return {
            "id": self._make_id(seq),
            "task_id": self.task_id,
            "teacher_model_id": f"benchmark:{self.benchmark_id}",
            "sampled_target_attributes": item["_inferred_attrs"],
            "prompt": prompt,
            "reference_response": item["_answers"][0],
            "generated_at": self._now_iso(),
            "benchmark_id": self.benchmark_id,
            "benchmark_split": self.split,
            "benchmark_native_id": item["_native_id"],
            "benchmark_native_score": None,
            # Keep all valid answers for exact-match computation
            "_all_answers": item["_answers"],
        }
