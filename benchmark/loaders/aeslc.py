"""AESLC benchmark loader for the email_composition task.

Dataset : aeslc  (HuggingFace — Annotated Enron Subject Line Corpus)
Split   : validation
Prompt  : A workplace email scenario description (derived from subject + opening)
Reference: The full email body (gold professional email)
GT metric: BERTScore-F1 between student email and reference email

AESLC format
------------
Each row has:
    email_body   : the email text (includes subject line prefix in some cases)
    subject_line : human-annotated subject line

We use:
    prompt           = "Write a professional email with the following subject and purpose:
                        Subject: {subject_line}
                        Context: {first_sentence_of_email}"
    reference_response = full email body (cleaned)

Attribute mapping
-----------------
length  : inferred from email word count
    brief      < 80 words
    standard   80–200 words
    detailed   > 200 words

purpose : inferred by keyword heuristics
    information_request / project_update / complaint_resolution / proposal / follow_up

tone    : always "semi_formal" (Enron professional corpus)
"""
from __future__ import annotations

import re
from typing import Any

from .base import BenchmarkLoader


_PURPOSE_KEYWORDS: dict[str, list[str]] = {
    "information_request": ["please", "could you", "let me know", "can you", "request",
                            "wondering", "question"],
    "project_update": ["update", "status", "progress", "completed", "milestone",
                       "project", "schedule"],
    "complaint_resolution": ["issue", "problem", "concern", "error", "incorrect",
                             "resolve", "fix", "wrong"],
    "proposal": ["propose", "suggest", "recommend", "idea", "plan", "consider",
                 "opportunity"],
    "follow_up": ["follow", "reminder", "follow-up", "checking in", "haven't heard",
                  "as discussed"],
}


def _infer_purpose(text: str) -> str:
    lower = text.lower()
    for purpose, kws in _PURPOSE_KEYWORDS.items():
        if any(kw in lower for kw in kws):
            return purpose
    return "information_request"


def _infer_length(text: str) -> str:
    n = len(text.split())
    if n > 200:
        return "detailed"
    if n > 80:
        return "standard"
    return "brief"


def _clean_email(text: str) -> str:
    """Remove email metadata headers that sometimes prefix AESLC bodies."""
    # Remove lines like "To:", "From:", "Date:", "Cc:", "Subject:" at the top
    lines = text.strip().splitlines()
    start = 0
    for i, line in enumerate(lines):
        if re.match(r"^(To|From|Cc|Bcc|Date|Subject|Message-ID):", line, re.IGNORECASE):
            start = i + 1
        elif line.strip() == "":
            if start > 0:
                start = i + 1
                break
    return "\n".join(lines[start:]).strip()


class AESLCLoader(BenchmarkLoader):
    benchmark_id = "aeslc"
    task_id = "email_composition"
    default_split = "train"  # train has 14k items; validation only 1.9k (too few for 620 samples)

    def _load_dataset(self) -> list[dict[str, Any]]:
        from datasets import load_dataset  # type: ignore

        ds = load_dataset("aeslc", split=self.split)
        items = []
        for row in ds:
            body = _clean_email((row.get("email_body") or "").strip())
            subject = (row.get("subject_line") or "").strip()

            if not body or not subject or len(body) < 50:
                continue

            # Extract first sentence as context hint
            first_sentence = re.split(r"[.!?\n]", body)[0].strip()
            if len(first_sentence) < 10:
                first_sentence = body[:120].strip()

            purpose = _infer_purpose(body)
            length = _infer_length(body)

            items.append({
                "_native_id": subject[:60],
                "_subject": subject,
                "_first_sentence": first_sentence,
                "_body": body,
                "_inferred_attrs": {
                    "purpose": purpose,
                    "length": length,
                    "tone": "semi_formal",
                },
            })
        return items

    def _to_record(self, item: dict[str, Any], seq: int) -> dict[str, Any]:
        prompt = (
            f"Write a professional email with the following subject and context.\n\n"
            f"Subject: {item['_subject']}\n"
            f"Context: {item['_first_sentence']}"
        )
        return {
            "id": self._make_id(seq),
            "task_id": self.task_id,
            "teacher_model_id": f"benchmark:{self.benchmark_id}",
            "sampled_target_attributes": item["_inferred_attrs"],
            "prompt": prompt,
            "reference_response": item["_body"],
            "generated_at": self._now_iso(),
            "benchmark_id": self.benchmark_id,
            "benchmark_split": self.split,
            "benchmark_native_id": item["_native_id"],
            "benchmark_native_score": None,
        }
