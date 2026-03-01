"""MMLU (Massive Multitask Language Understanding) adapter.

Reference: Hendrycks et al. 2020 — https://arxiv.org/abs/2009.03300
HuggingFace: cais/mmlu
"""
from __future__ import annotations

from pathlib import Path
from typing import Iterator

from experiments.benchmarks.base import BenchmarkAdapter, BenchmarkItem

# 57 MMLU subjects
_SUBJECTS = [
    'abstract_algebra', 'anatomy', 'astronomy', 'business_ethics', 'clinical_knowledge',
    'college_biology', 'college_chemistry', 'college_computer_science', 'college_mathematics',
    'college_medicine', 'college_physics', 'computer_security', 'conceptual_physics',
    'econometrics', 'electrical_engineering', 'elementary_mathematics', 'formal_logic',
    'global_facts', 'high_school_biology', 'high_school_chemistry', 'high_school_computer_science',
    'high_school_european_history', 'high_school_geography', 'high_school_government_and_politics',
    'high_school_macroeconomics', 'high_school_mathematics', 'high_school_microeconomics',
    'high_school_physics', 'high_school_psychology', 'high_school_statistics',
    'high_school_us_history', 'high_school_world_history', 'human_aging', 'human_sexuality',
    'international_law', 'jurisprudence', 'logical_fallacies', 'machine_learning',
    'management', 'marketing', 'medical_genetics', 'miscellaneous', 'moral_disputes',
    'moral_scenarios', 'nutrition', 'philosophy', 'prehistory', 'professional_accounting',
    'professional_law', 'professional_medicine', 'professional_psychology', 'public_relations',
    'security_studies', 'sociology', 'us_foreign_policy', 'virology', 'world_religions',
]

_CHOICE_LABELS = ['A', 'B', 'C', 'D']


class MMLUAdapter(BenchmarkAdapter):
    name = 'mmlu'
    description = 'MMLU — Massive Multitask Language Understanding (57 subjects, 4-way MCQ)'
    task_name = 'mmlu'
    output_description = (
        'A single uppercase letter (A, B, C, or D) representing your chosen answer. '
        'Respond with only the letter and nothing else.'
    )
    homepage = 'https://github.com/hendrycks/test'

    def load(self, data_dir: Path, split: str = 'test') -> Iterator[BenchmarkItem]:
        path = self._jsonl_path(data_dir, split)
        for raw in self._iter_jsonl(path):
            # Stored fields: question, choices (list[str]), answer (int 0-3), subject
            question: str = raw['question']
            choices: list[str] = raw['choices']
            answer_idx: int = raw['answer']          # 0-based index
            subject: str = raw.get('subject', 'general')
            item_id: str = raw.get('id', f'mmlu-{raw.get("_idx", "?")}')

            correct_label = _CHOICE_LABELS[answer_idx]
            choices_block = '\n'.join(
                f'{lbl}. {txt}' for lbl, txt in zip(_CHOICE_LABELS, choices)
            )
            prompt = (
                f"The following is a multiple-choice question about {subject.replace('_', ' ')}.\n\n"
                f"Question: {question}\n\n"
                f"{choices_block}\n\n"
                f"Which answer is correct? Reply with only the letter A, B, C, or D."
            )

            yield BenchmarkItem(
                id=item_id,
                prompt=prompt,
                reference_answer=f"{correct_label}. {choices[answer_idx]}",
                target_attributes={
                    'correct_answer': correct_label,
                    'subject': subject,
                },
                metadata={'raw': raw},
            )

    def get_rubric(self) -> dict[str, str]:
        return {
            'correctness': (
                'Did the model select the correct answer option (A, B, C, or D)? '
                'Award High if the answer letter matches the ground truth, Low otherwise.'
            ),
        }

    def get_target_attribute_schema(self) -> dict[str, list[str]]:
        return {
            'correct_answer': _CHOICE_LABELS,
            'subject': _SUBJECTS,
        }

    def get_label_attributes(self) -> list[str]:
        return ['correct_answer']
