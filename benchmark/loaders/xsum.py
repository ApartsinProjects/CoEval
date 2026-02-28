"""XSum benchmark loader for the text_summarization task.

Dataset : EdinburghNLP/xsum  (HuggingFace)
Split   : validation (11,332 articles)
Prompt  : BBC news article text
Reference: One-sentence human-written summary
GT metric: BERTScore-F1 between student summary and gold summary

Attribute mapping
-----------------
complexity  : inferred from article word count
    simple     < 250 words
    moderate   250–500 words
    complex    > 500 words
    technical  article contains ≥3 domain-specific technical terms

domain      : inferred from first 80 chars of article (keyword heuristics)
    science / business / politics / technology / health / other
"""
from __future__ import annotations

import re
from typing import Any

from .base import BenchmarkLoader


_DOMAIN_KEYWORDS: dict[str, list[str]] = {
    "science": ["research", "study", "scientist", "climate", "space", "nasa", "genome",
                "fossil", "particle", "quantum", "biology"],
    "technology": ["tech", "software", "app", "digital", "cyber", "ai ", "robot",
                   "internet", "smartphone", "data", "algorithm"],
    "health": ["hospital", "patient", "cancer", "drug", "vaccine", "health", "medical",
               "nhs", "disease", "surgery", "doctor", "mental health"],
    "business": ["company", "market", "shares", "profit", "revenue", "bank", "economy",
                 "trade", "invest", "stock", "startup", "gdp"],
    "politics": ["government", "minister", "parliament", "election", "party", "vote",
                 "policy", "president", "mp", "congress", "senate"],
}

_TECHNICAL_TERMS = frozenset([
    "algorithm", "genome", "quantum", "cryptocurrency", "cybersecurity",
    "neural", "macroeconomic", "pathogen", "subsidy", "litigation",
    "derivatives", "protocol", "antibody", "referendum",
])


def _infer_domain(text: str) -> str:
    lower = text.lower()
    for domain, kws in _DOMAIN_KEYWORDS.items():
        if any(kw in lower for kw in kws):
            return domain
    return "other"


def _infer_complexity(text: str) -> str:
    words = text.split()
    n = len(words)
    if n > 500:
        return "complex"
    if n > 250:
        return "moderate"
    # Check for technical vocabulary
    lower = text.lower()
    tech_hits = sum(1 for t in _TECHNICAL_TERMS if t in lower)
    if tech_hits >= 3:
        return "technical"
    return "simple"


class XSumLoader(BenchmarkLoader):
    benchmark_id = "xsum"
    task_id = "text_summarization"
    default_split = "validation"

    def _load_dataset(self) -> list[dict[str, Any]]:
        from datasets import load_dataset  # type: ignore

        ds = load_dataset("EdinburghNLP/xsum", split=self.split, trust_remote_code=True)
        items = []
        for row in ds:
            article = (row.get("document") or "").strip()
            summary = (row.get("summary") or "").strip()
            if not article or not summary:
                continue
            complexity = _infer_complexity(article)
            domain = _infer_domain(article[:500])
            items.append({
                "_native_id": str(row.get("id", "")),
                "_article": article,
                "_summary": summary,
                "_inferred_attrs": {
                    "complexity": complexity,
                    "domain": domain,
                },
            })
        return items

    def _to_record(self, item: dict[str, Any], seq: int) -> dict[str, Any]:
        return {
            "id": self._make_id(seq),
            "task_id": self.task_id,
            "teacher_model_id": f"benchmark:{self.benchmark_id}",
            "sampled_target_attributes": item["_inferred_attrs"],
            "prompt": item["_article"],
            "reference_response": item["_summary"],
            "generated_at": self._now_iso(),
            "benchmark_id": self.benchmark_id,
            "benchmark_split": self.split,
            "benchmark_native_id": item["_native_id"],
            "benchmark_native_score": None,  # filled by metric computation step
        }
