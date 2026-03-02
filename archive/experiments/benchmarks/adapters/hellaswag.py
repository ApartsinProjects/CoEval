"""HellaSwag adapter — commonsense NLI / sentence completion (4-way MCQ).

Reference: Zellers et al. 2019 — https://arxiv.org/abs/1905.07830
HuggingFace: Rowan/hellaswag (validation split used; test labels are withheld)
"""
from __future__ import annotations

from pathlib import Path
from typing import Iterator

from experiments.benchmarks.base import BenchmarkAdapter, BenchmarkItem

_CHOICE_LABELS = ['A', 'B', 'C', 'D']


class HellaSwagAdapter(BenchmarkAdapter):
    name = 'hellaswag'
    description = 'HellaSwag — commonsense sentence-completion benchmark (4-way MCQ)'
    task_name = 'hellaswag'
    default_split = 'validation'
    output_description = (
        'A single uppercase letter (A, B, C, or D) identifying which sentence '
        'continuation is most plausible. Respond with only the letter.'
    )
    homepage = 'https://rowanzellers.com/hellaswag/'

    def load(self, data_dir: Path, split: str = 'validation') -> Iterator[BenchmarkItem]:
        path = self._jsonl_path(data_dir, split)
        for raw in self._iter_jsonl(path):
            # Fields: ind (str), activity_label, ctx_a, ctx_b, ctx (full),
            #         endings (list[str]), label (str "0"-"3")
            ctx: str = raw.get('ctx', raw.get('ctx_a', ''))
            endings: list[str] = raw['endings']
            label_str: str = str(raw['label'])    # "0", "1", "2", "3"
            activity: str = raw.get('activity_label', 'Activity')
            item_id: str = f"hellaswag-{raw.get('ind', raw.get('_idx', '?'))}"

            if not label_str.isdigit():
                continue  # skip items with missing labels (test split)

            correct_idx = int(label_str)
            correct_label = _CHOICE_LABELS[correct_idx]

            choices_block = '\n'.join(
                f'{lbl}. {txt}' for lbl, txt in zip(_CHOICE_LABELS, endings)
            )
            prompt = (
                f"Activity: {activity}\n\n"
                f"Context: {ctx}\n\n"
                f"Which of the following is the most plausible continuation?\n\n"
                f"{choices_block}\n\n"
                f"Reply with only the letter A, B, C, or D."
            )

            yield BenchmarkItem(
                id=item_id,
                prompt=prompt,
                reference_answer=f"{correct_label}. {endings[correct_idx]}",
                target_attributes={
                    'correct_answer': correct_label,
                    'activity': activity[:60] if activity else 'general',
                },
                metadata={'raw': raw},
            )

    def get_rubric(self) -> dict[str, str]:
        return {
            'correctness': (
                'Did the model select the most plausible sentence continuation '
                '(A, B, C, or D)? High if the letter matches ground truth, Low otherwise.'
            ),
        }

    def get_target_attribute_schema(self) -> dict[str, list[str]]:
        return {
            'correct_answer': _CHOICE_LABELS,
        }

    def get_label_attributes(self) -> list[str]:
        return ['correct_answer']
