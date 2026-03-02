"""Loader for CNN / DailyMail summarization benchmark.

Dataset : cnn_dailymail (config 3.0.0)
Task    : news_summarization
Metric  : bertscore
Split   : test

Articles are truncated to 2000 characters in the prompt to stay within
reasonable context limits.  The reference is the bullet-point highlights
string provided by the dataset.
"""
from __future__ import annotations

from typing import Any

from .base import BenchmarkLoader

_MAX_ARTICLE_CHARS = 2000


class CNNDailyMailLoader(BenchmarkLoader):
    """Loads CNN/DailyMail test split for news summarisation evaluation."""

    benchmark_id: str = "cnn_dailymail"
    task_id: str = "news_summarization"
    default_split: str = "test"

    # ------------------------------------------------------------------
    # Dataset loading
    # ------------------------------------------------------------------

    def _load_dataset(self) -> list[dict[str, Any]]:
        from datasets import load_dataset  # noqa: PLC0415

        ds = load_dataset("cnn_dailymail", "3.0.0", split=self.split)
        items: list[dict[str, Any]] = []
        for idx, row in enumerate(ds):
            article: str = row.get("article") or ""
            highlights: str = row.get("highlights") or ""
            if not article or not highlights:
                continue
            native_id: str = row.get("id") or str(idx)
            publication: str = "cnn" if native_id.startswith("cnn") else "dailymail"
            word_count = len(article.split())
            if word_count < 300:
                article_length = "short"
            elif word_count < 700:
                article_length = "medium"
            else:
                article_length = "long"
            items.append(
                {
                    "article": article,
                    "highlights": highlights,
                    "_native_id": native_id,
                    "_inferred_attrs": {
                        "article_length": article_length,
                        "publication": publication,
                    },
                }
            )
        return items

    # ------------------------------------------------------------------
    # Record conversion
    # ------------------------------------------------------------------

    def _to_record(self, item: dict[str, Any], seq: int) -> dict[str, Any]:
        attrs = item["_inferred_attrs"]
        article_text = item["article"]
        if len(article_text) > _MAX_ARTICLE_CHARS:
            article_text = article_text[:_MAX_ARTICLE_CHARS]
        prompt = (
            "Summarize the following news article in 2-3 concise sentences, "
            "capturing the key facts.\n\n"
            f"Article:\n{article_text}"
        )
        return {
            "id": self._make_id(seq),
            "task_id": self.task_id,
            "teacher_model_id": self.teacher_id,
            "sampled_target_attributes": attrs,
            "prompt": prompt,
            "reference_response": item["highlights"],
            "generated_at": self._now_iso(),
            "benchmark_id": self.benchmark_id,
            "benchmark_split": self.split,
            "benchmark_native_id": item["_native_id"],
            "benchmark_native_score": None,
        }
