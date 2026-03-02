"""GSM8K adapter — grade-school math word problems requiring multi-step reasoning.

Reference: Cobbe et al. 2021 — https://arxiv.org/abs/2110.14168
HuggingFace: openai/gsm8k (main config, test split, 1319 problems)
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Iterator

from runner.benchmarks.base import BenchmarkAdapter, BenchmarkItem

# GSM8K answers are integers (or small decimals) preceded by "####"
_ANSWER_RE = re.compile(r'####\s*([\d,]+(?:\.\d+)?)')


def _extract_numeric_answer(solution: str) -> str | None:
    """Pull the final numeric answer from a GSM8K solution string."""
    m = _ANSWER_RE.search(solution)
    if m:
        return m.group(1).replace(',', '')
    return None


class GSM8KAdapter(BenchmarkAdapter):
    name = 'gsm8k'
    description = (
        'GSM8K — 1,319 grade-school math word problems requiring multi-step '
        'arithmetic reasoning (OpenAI, 2021)'
    )
    task_name = 'gsm8k'
    output_description = (
        'Show your step-by-step solution, then end your answer with '
        '"#### <number>" where <number> is the final numeric answer. '
        'Example: "#### 42"'
    )
    homepage = 'https://github.com/openai/grade-school-math'

    def load(self, data_dir: Path, split: str = 'test') -> Iterator[BenchmarkItem]:
        path = self._jsonl_path(data_dir, split)
        for i, raw in enumerate(self._iter_jsonl(path)):
            # Fields: question, answer (full solution with #### N at end)
            question: str = raw['question']
            solution: str = raw.get('answer', '')
            item_id: str = raw.get('id', f'gsm8k-{i:04d}')

            numeric_answer = _extract_numeric_answer(solution)

            prompt = (
                f"Solve the following math problem step by step.\n\n"
                f"Problem: {question}\n\n"
                f"Show your work, then write your final answer as: #### <number>"
            )

            target_attrs: dict[str, str] = {}
            if numeric_answer is not None:
                target_attrs['answer'] = numeric_answer

            yield BenchmarkItem(
                id=item_id,
                prompt=prompt,
                reference_answer=solution,
                target_attributes=target_attrs,
                metadata={'raw': raw, 'numeric_answer': numeric_answer},
            )

    def get_rubric(self) -> dict[str, str]:
        return {
            'correctness': (
                'Does the model produce the correct final numeric answer '
                '(the number after ####)? '
                'High = exact numeric match; '
                'Medium = correct method but arithmetic error; '
                'Low = incorrect approach or answer.'
            ),
            'reasoning': (
                'Is the step-by-step solution clear and logically sound? '
                'High = clear, complete, easy to follow; '
                'Medium = mostly correct but skips steps; '
                'Low = confusing, missing key steps, or jumps to answer.'
            ),
        }

    def get_target_attribute_schema(self) -> dict[str, list[str]]:
        # answers are open-ended numerics — no static enumeration, but we must
        # declare the key so V-17 validation accepts label_attributes = ['answer']
        return {'answer': []}

    def get_label_attributes(self) -> list[str]:
        # We do have numeric answers, but they require normalised string comparison.
        # Return ['answer'] so ingest writes them; LabelEvaluator will do string match.
        return ['answer']
