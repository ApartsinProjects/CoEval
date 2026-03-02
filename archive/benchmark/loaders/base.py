"""Base benchmark loader interface.

Each loader downloads a public benchmark dataset, applies stratified
attribute sampling, and emits CoEval-compatible JSONL records that can
be dropped directly into a Phase 3 datapoints folder.

Record schema (same as teacher-generated Phase 3 output):

    {
        "id":                       "xsum__benchmark__00001",
        "task_id":                  "text_summarization",
        "teacher_model_id":         "xsum",
        "sampled_target_attributes": {"complexity": "...", ...},
        "prompt":                   "[source text / code / table]",
        "reference_response":       "[gold output]",
        "generated_at":             "ISO-8601 timestamp",
        "benchmark_id":             "xsum",
        "benchmark_split":          "validation",
        "benchmark_native_id":      "29750436",
        "benchmark_native_score":   null   # filled later by metric computation
    }
"""
from __future__ import annotations

import json
import random
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class BenchmarkLoader(ABC):
    """Abstract base class for all benchmark loaders."""

    # Subclasses must override these
    benchmark_id: str = ""
    task_id: str = ""
    default_split: str = "validation"

    @property
    def teacher_id(self) -> str:
        """The model name used as ``teacher_model_id`` in Phase 3 records.

        Defaults to ``self.benchmark_id``.  Subclasses that have multiple
        variants (e.g. CodeSearchNet has per-language splits) should override
        this property to return a more specific name such as
        ``"codesearchnet-python"``.
        """
        return self.benchmark_id

    def __init__(
        self,
        attribute_map: dict[str, list[str]],
        sample_size: int = 620,
        split: str | None = None,
        seed: int = 42,
    ) -> None:
        self.attribute_map = attribute_map   # {attr_name: [value1, value2, ...]}
        self.sample_size = sample_size
        self.split = split or self.default_split
        self.seed = seed
        self._rng = random.Random(seed)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def emit(self, out_path: str | Path) -> int:
        """Download, sample, and write JSONL to *out_path*.

        Returns the number of records written.
        """
        out_path = Path(out_path)
        out_path.parent.mkdir(parents=True, exist_ok=True)

        raw_items = self._load_dataset()
        sampled = self._stratified_sample(raw_items)

        written = 0
        with open(out_path, "w", encoding="utf-8") as fh:
            for idx, item in enumerate(sampled, 1):
                record = self._to_record(item, idx)
                fh.write(json.dumps(record, ensure_ascii=False) + "\n")
                written += 1

        return written

    # ------------------------------------------------------------------
    # Abstract methods — implement per dataset
    # ------------------------------------------------------------------

    @abstractmethod
    def _load_dataset(self) -> list[dict[str, Any]]:
        """Download (or load cached) the benchmark split.

        Returns a flat list of raw benchmark items.
        Each item must contain at least the keys that ``_to_record`` uses.
        Items should also include an ``_inferred_attrs`` dict so that
        stratification can work.
        """

    @abstractmethod
    def _to_record(self, item: dict[str, Any], seq: int) -> dict[str, Any]:
        """Convert a raw benchmark item to a CoEval Phase 3 record."""

    # ------------------------------------------------------------------
    # Stratified sampling
    # ------------------------------------------------------------------

    def _stratified_sample(self, items: list[dict]) -> list[dict]:
        """Near-uniform stratified sample over ``_inferred_attrs``."""
        if not self.attribute_map or not items:
            # Fallback: pure random sample
            shuffled = list(items)
            self._rng.shuffle(shuffled)
            return shuffled[: self.sample_size]

        # Build strata
        strata: dict[tuple, list[dict]] = {}
        for item in items:
            key = tuple(
                item.get("_inferred_attrs", {}).get(attr, "unknown")
                for attr in sorted(self.attribute_map)
            )
            strata.setdefault(key, []).append(item)

        # Distribute budget
        n_strata = len(strata)
        if n_strata == 0:
            return items[: self.sample_size]

        base = max(1, self.sample_size // n_strata)
        remainder = self.sample_size - base * n_strata

        selected: list[dict] = []
        stratum_list = list(strata.values())
        self._rng.shuffle(stratum_list)

        for i, bucket in enumerate(stratum_list):
            quota = base + (1 if i < remainder else 0)
            shuffled = list(bucket)
            self._rng.shuffle(shuffled)
            selected.extend(shuffled[:quota])

        self._rng.shuffle(selected)
        return selected[: self.sample_size]

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _now_iso() -> str:
        return datetime.now(timezone.utc).isoformat(timespec="seconds")

    def _make_id(self, seq: int) -> str:
        return f"{self.task_id}__{self.benchmark_id}__{seq:05d}"
