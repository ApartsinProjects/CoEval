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


_SPLIT_PARQUET: dict[str, str] = {
    # Pre-converted Parquet shard from the Hugging Face Hub dataset viewer cache.
    # These URLs are stable as long as the dataset card is not deleted.
    "validation": "https://huggingface.co/datasets/wikitablequestions/resolve/refs%2Fconvert%2Fparquet/default/validation/0000.parquet",
    "test":       "https://huggingface.co/datasets/wikitablequestions/resolve/refs%2Fconvert%2Fparquet/default/test/0000.parquet",
    "train":      "https://huggingface.co/datasets/wikitablequestions/resolve/refs%2Fconvert%2Fparquet/default/train/0000.parquet",
}


class WikiTableQuestionsLoader(BenchmarkLoader):
    benchmark_id = "wikitablequestions"
    task_id = "data_interpretation"
    default_split = "validation"

    def _load_dataset(self) -> list[dict[str, Any]]:
        """Load WTQ dataset.

        The original ``wikitablequestions`` HuggingFace dataset uses a custom
        loading script that is no longer supported in datasets ≥ 3.x, and no
        Parquet version exists on the Hub.  We fall through four loading
        strategies (see ``_hf_load_wtq``) and ultimately download the master
        archive from the original GitHub repo as a last resort.
        """
        ds = self._hf_load_wtq()
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
            "teacher_model_id": self.benchmark_id,
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

    # ------------------------------------------------------------------
    # Private: HuggingFace dataset loading with script-deprecation workaround
    # ------------------------------------------------------------------

    def _hf_load_wtq(self):
        """Return an iterable of row-dicts for the requested split.

        Strategy (tried in order):
        1. ``load_dataset("wikitablequestions")`` — works on datasets < 3.x.
        2. Direct Parquet URL from the HF Hub ``refs/convert/parquet`` cache.
        3. HF datasets-server REST API (``/parquet?dataset=wikitablequestions``)
           to get a live Parquet URL.
        4. Download the full repo archive from ``ppasupat/WikiTableQuestions``
           on GitHub and parse TSV + CSV files entirely in memory.
        """
        import datasets as _datasets  # type: ignore

        # --- Attempt 1: standard load (may work on older library versions) ---
        try:
            return _datasets.load_dataset(
                "wikitablequestions", split=self.split
            )
        except Exception:
            pass

        # --- Attempt 2: Parquet shard from HF Hub convert cache ---
        split_key = self.split if self.split in _SPLIT_PARQUET else "validation"
        parquet_url = _SPLIT_PARQUET[split_key]
        try:
            return _datasets.load_dataset(
                "parquet",
                data_files={"data": parquet_url},
                split="data",
            )
        except Exception:
            pass

        # --- Attempt 3: query HF datasets-server REST API for live Parquet URLs ---
        import urllib.request as _ureq
        import json as _json

        api_url = (
            "https://datasets-server.huggingface.co/parquet"
            "?dataset=wikitablequestions"
        )
        try:
            with _ureq.urlopen(api_url, timeout=20) as _resp:
                _info = _json.loads(_resp.read())
            for _pf in _info.get("parquet_files", []):
                if _pf.get("split") == split_key:
                    return _datasets.load_dataset(
                        "parquet",
                        data_files={"data": _pf["url"]},
                        split="data",
                    )
        except Exception:
            pass

        # --- Attempt 4: download full repo archive from the original GitHub repo ---
        # The WTQ dataset (ppasupat/WikiTableQuestions) is not on the HF Hub in
        # a usable form.  Fall back to the canonical GitHub release: download the
        # master zip (~4 MB compressed) which contains both the question TSV files
        # and all referenced CSV table files.  Returns a plain list[dict] — the
        # caller only does ``for row in ds`` so an iterable list works fine.
        return self._load_from_github(split_key)

    # ------------------------------------------------------------------
    # Private: GitHub archive fallback for WTQ
    # ------------------------------------------------------------------

    @staticmethod
    def _load_from_github(split_key: str) -> list[dict]:
        """Download WikiTableQuestions from the canonical GitHub repo.

        Downloads the master zip once (≈4 MB) and parses both the split TSV
        and the referenced per-table CSV files entirely in memory.
        """
        import csv as _csv
        import io as _io
        import urllib.request as _ureq
        import zipfile as _zf

        _SPLIT_TSV: dict[str, str] = {
            "train":      "WikiTableQuestions-master/data/training.tsv",
            "validation": "WikiTableQuestions-master/data/random-split-1-dev.tsv",
            "test":       "WikiTableQuestions-master/data/pristine-unseen-tables.tsv",
        }
        _ZIP_URL = (
            "https://github.com/ppasupat/WikiTableQuestions"
            "/archive/refs/heads/master.zip"
        )

        req = _ureq.Request(
            _ZIP_URL,
            headers={"User-Agent": "CoEval-benchmark-loader/1.0"},
        )
        with _ureq.urlopen(req, timeout=180) as _r:
            zip_bytes = _r.read()

        records: list[dict] = []
        with _zf.ZipFile(_io.BytesIO(zip_bytes)) as zf:
            tsv_entry = _SPLIT_TSV.get(split_key, _SPLIT_TSV["validation"])
            with zf.open(tsv_entry) as f:
                tsv_text = f.read().decode("utf-8", errors="replace")

            for row in _csv.DictReader(_io.StringIO(tsv_text), delimiter="\t"):
                context = row.get("context", "")
                if not context:
                    continue

                csv_entry = "WikiTableQuestions-master/" + context
                try:
                    with zf.open(csv_entry) as cf:
                        csv_str = cf.read().decode("utf-8", errors="replace")
                    csv_rows = list(_csv.reader(_io.StringIO(csv_str)))
                except Exception:
                    continue

                if not csv_rows:
                    continue

                header = csv_rows[0]
                table_rows = [list(r) for r in csv_rows[1:]]

                answer_raw = row.get("targetValue", "").strip()
                answers = [answer_raw] if answer_raw else []

                records.append(
                    {
                        "id": row.get("id", ""),
                        "question": row.get("utterance", "").strip(),
                        "table": {"header": header, "rows": table_rows},
                        "answers": answers,
                    }
                )

        return records
