"""MedQA-USMLE adapter — 4-option medical licensing exam questions.

Reference: Jin et al. 2021 — https://arxiv.org/abs/2009.13081
HuggingFace: bigbio/med_qa (us subset, test split, 1273 questions)
"""
from __future__ import annotations

from pathlib import Path
from typing import Iterator

from experiments.benchmarks.base import BenchmarkAdapter, BenchmarkItem

_CHOICE_LABELS = ['A', 'B', 'C', 'D']

_MEDICAL_CATEGORIES = [
    'Internal Medicine', 'Surgery', 'Obstetrics and Gynecology',
    'Pediatrics', 'Psychiatry', 'Pharmacology', 'Pathology',
    'Anatomy', 'Physiology', 'Biochemistry', 'Microbiology',
    'Preventive Medicine', 'Other',
]


class MedQAAdapter(BenchmarkAdapter):
    name = 'medqa'
    description = (
        'MedQA-USMLE — 1,273 U.S. medical licensing exam questions '
        '(4-option MCQ, clinical reasoning)'
    )
    task_name = 'medqa'
    output_description = (
        'A single uppercase letter (A, B, C, or D) representing the correct '
        'answer to the clinical question. Respond with only the letter.'
    )
    homepage = 'https://github.com/jind11/MedQA'

    def load(self, data_dir: Path, split: str = 'test') -> Iterator[BenchmarkItem]:
        path = self._jsonl_path(data_dir, split)
        for i, raw in enumerate(self._iter_jsonl(path)):
            # Stored fields: question, answer (letter A-D), options (dict A-D),
            #                meta_info (category), answer_idx (int)
            question: str = raw['question']
            options: dict[str, str] = raw.get('options', {})
            answer_letter: str = raw.get('answer', '')
            meta_info: str = raw.get('meta_info', 'Other')
            item_id: str = raw.get('id', f'medqa-{i:04d}')

            if not answer_letter or answer_letter not in _CHOICE_LABELS:
                continue

            # Build consistent A/B/C/D choices block
            choices_block = '\n'.join(
                f'{lbl}. {options.get(lbl, "")}' for lbl in _CHOICE_LABELS
            )
            prompt = (
                f"The following is a medical licensing exam question (USMLE style).\n\n"
                f"Question: {question}\n\n"
                f"{choices_block}\n\n"
                f"Which answer is correct? Reply with only the letter A, B, C, or D."
            )

            # Normalise category
            cat = meta_info.strip()[:60] if meta_info else 'Other'

            yield BenchmarkItem(
                id=item_id,
                prompt=prompt,
                reference_answer=f"{answer_letter}. {options.get(answer_letter, '')}",
                target_attributes={
                    'correct_answer': answer_letter,
                    'category': cat,
                },
                metadata={'raw': raw},
            )

    def get_rubric(self) -> dict[str, str]:
        return {
            'correctness': (
                'Did the model select the correct answer option (A, B, C, or D)? '
                'Award High if the answer letter matches the ground truth, Low otherwise.'
            ),
            'clinical_reasoning': (
                'Does the response demonstrate sound medical reasoning? '
                'High = identifies the key clinical finding and selects the correct '
                'diagnosis / treatment; Medium = partially correct reasoning; '
                'Low = incorrect or no reasoning shown.'
            ),
        }

    def get_target_attribute_schema(self) -> dict[str, list[str]]:
        return {
            'correct_answer': _CHOICE_LABELS,
            'category': _MEDICAL_CATEGORIES,
        }

    def get_label_attributes(self) -> list[str]:
        return ['correct_answer']
