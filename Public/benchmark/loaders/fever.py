"""Loader for FEVER (Fact Extraction and VERification) benchmark.

Dataset : fever (config v1.0)
Task    : fact_verification
Metric  : exact_match
Split   : labelled_dev

FEVER labels are "SUPPORTS", "REFUTES", or "NOT ENOUGH INFO".
We normalise to lowercase-with-underscores for the attribute value
but keep the original casing as the reference response so that
exact_match against model output (which is asked to use original
casing) is straightforward.
"""
from __future__ import annotations

from typing import Any

from .base import BenchmarkLoader

_VALID_LABELS: set[str] = {"SUPPORTS", "REFUTES", "NOT ENOUGH INFO"}

_LABEL_NORM: dict[str, str] = {
    "SUPPORTS": "supports",
    "REFUTES": "refutes",
    "NOT ENOUGH INFO": "not_enough_info",
}


class FEVERLoader(BenchmarkLoader):
    """Loads FEVER labelled_dev split for fact verification evaluation."""

    benchmark_id: str = "fever"
    task_id: str = "fact_verification"
    default_split: str = "labelled_dev"

    # ------------------------------------------------------------------
    # Dataset loading
    # ------------------------------------------------------------------

    def _load_dataset(self) -> list[dict[str, Any]]:
        from datasets import load_dataset  # noqa: PLC0415

        ds = load_dataset("fever", "v1.0", split=self.split)
        items: list[dict[str, Any]] = []
        for idx, row in enumerate(ds):
            label: str = (row.get("label") or "").strip()
            if label not in _VALID_LABELS:
                continue
            claim: str = row.get("claim") or ""
            word_count = len(claim.split())
            if word_count < 10:
                claim_length = "short"
            elif word_count < 20:
                claim_length = "medium"
            else:
                claim_length = "long"
            items.append(
                {
                    "claim": claim,
                    "label": label,
                    "_native_id": str(row.get("id") or idx),
                    "_inferred_attrs": {
                        "label": _LABEL_NORM[label],
                        "claim_length": claim_length,
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
            "Determine whether the following claim is SUPPORTED, REFUTED, "
            "or if there is NOT ENOUGH INFO to decide.\n\n"
            f"Claim: {item['claim']}\n\n"
            "Answer with exactly one of: SUPPORTS, REFUTES, NOT ENOUGH INFO"
        )
        return {
            "id": self._make_id(seq),
            "task_id": self.task_id,
            "teacher_model_id": self.teacher_id,
            "sampled_target_attributes": attrs,
            "prompt": prompt,
            "reference_response": item["label"],
            "generated_at": self._now_iso(),
            "benchmark_id": self.benchmark_id,
            "benchmark_split": self.split,
            "benchmark_native_id": item["_native_id"],
            "benchmark_native_score": None,
        }
