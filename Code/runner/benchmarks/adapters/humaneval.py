"""HumanEval adapter — Python code generation from function signatures.

Reference: Chen et al. 2021 — https://arxiv.org/abs/2107.03374
HuggingFace: openai_humaneval (test split, 164 problems)
"""
from __future__ import annotations

from pathlib import Path
from typing import Iterator

from runner.benchmarks.base import BenchmarkAdapter, BenchmarkItem


class HumanEvalAdapter(BenchmarkAdapter):
    name = 'humaneval'
    description = (
        'HumanEval — 164 Python programming problems with function signatures, '
        'docstrings, and unit tests (OpenAI, 2021)'
    )
    task_name = 'humaneval'
    output_description = (
        'A complete Python function implementation. '
        'Include only the function body that follows the given signature and docstring. '
        'Do not repeat the signature or add extra text outside the function.'
    )
    homepage = 'https://github.com/openai/human-eval'

    def load(self, data_dir: Path, split: str = 'test') -> Iterator[BenchmarkItem]:
        path = self._jsonl_path(data_dir, split)
        for raw in self._iter_jsonl(path):
            # Fields: task_id (HumanEval/N), prompt (fn sig + docstring),
            #         canonical_solution, test (assert block), entry_point
            task_id: str = raw['task_id']          # "HumanEval/0"
            fn_prompt: str = raw['prompt']          # includes signature + docstring
            canonical: str = raw['canonical_solution']
            entry_point: str = raw.get('entry_point', '')
            item_id: str = f"humaneval-{task_id.replace('/', '-').lower()}"

            problem_num = task_id.split('/')[-1]
            prompt = (
                f"Complete the following Python function. "
                f"Write only the function body (no imports unless needed, "
                f"no markdown fences).\n\n"
                f"```python\n{fn_prompt}```\n\n"
                f"Provide a complete, correct implementation."
            )

            # Difficulty heuristic based on problem number
            n = int(problem_num) if problem_num.isdigit() else 0
            difficulty = 'easy' if n < 55 else ('medium' if n < 110 else 'hard')

            yield BenchmarkItem(
                id=item_id,
                prompt=prompt,
                reference_answer=canonical,
                target_attributes={
                    'difficulty': difficulty,
                    'entry_point': entry_point[:50] if entry_point else '',
                },
                metadata={'raw': raw},
            )

    def get_rubric(self) -> dict[str, str]:
        return {
            'correctness': (
                'Does the implementation produce correct outputs for the described '
                'problem? High = passes all test cases or is clearly correct; '
                'Medium = mostly correct with minor edge-case failures; '
                'Low = incorrect logic or does not run.'
            ),
            'code_quality': (
                'Is the code clean, readable, and idiomatic Python? '
                'High = clear variable names, concise, no dead code; '
                'Medium = functional but verbose or unclear; '
                'Low = messy, confusing, or uses anti-patterns.'
            ),
        }

    def get_target_attribute_schema(self) -> dict[str, list[str]]:
        return {
            'difficulty': ['easy', 'medium', 'hard'],
        }

    def get_label_attributes(self) -> list[str]:
        return []  # requires execution or LLM judge
