"""Loader for SciFact scientific claim verification benchmark.

Dataset : allenai/scifact (config "claims")
Task    : scientific_claim_verification
Metric  : exact_match
Split   : train (test split has no labels)

SciFact labels are derived from the evidence dictionary:
  - any SUPPORTS evidence  -> "SUPPORTS"
  - any CONTRADICTS evidence (no SUPPORTS) -> "REFUTES"
  - no evidence -> "NOT ENOUGH INFO"

We skip rows where the claim string is empty.
"""
from __future__ import annotations

from typing import Any

from .base import BenchmarkLoader

_LABEL_NORM: dict[str, str] = {
    "SUPPORTS": "supports",
    "REFUTES": "refutes",
    "NOT ENOUGH INFO": "not_enough_info",
}


def _get_label(evidence_dict: dict) -> str:
    """Derive a FEVER-style label from a SciFact evidence dict."""
    labels = [v.get("label", "") for v in evidence_dict.values()]
    if "SUPPORTS" in labels:
        return "SUPPORTS"
    if "CONTRADICTS" in labels:
        return "REFUTES"
    return "NOT ENOUGH INFO"


class SciFactLoader(BenchmarkLoader):
    """Loads SciFact train split for scientific claim verification evaluation."""

    benchmark_id: str = "scifact"
    task_id: str = "scientific_claim_verification"
    default_split: str = "train"

    # ------------------------------------------------------------------
    # Dataset loading
    # ------------------------------------------------------------------

    def _load_dataset(self) -> list[dict[str, Any]]:
        from datasets import load_dataset  # noqa: PLC0415

        ds = load_dataset("allenai/scifact", "claims", split=self.split)
        items: list[dict[str, Any]] = []
        for idx, row in enumerate(ds):
            claim: str = row.get("claim") or ""
            if not claim:
                continue
            evidence: dict = row.get("evidence") or {}
            label: str = _get_label(evidence)
            word_count = len(claim.split())
            if word_count < 15:
                claim_length = "short"
            elif word_count < 25:
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
            "Determine whether the following scientific claim is SUPPORTED, "
            "REFUTED, or if there is NOT ENOUGH INFO to decide.\n\n"
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
