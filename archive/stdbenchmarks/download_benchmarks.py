#!/usr/bin/env python3
"""Download standard LLM benchmarks to the stdbenchmarks/ data folder.

Benchmarks downloaded
---------------------
General:
  mmlu        — Massive Multitask Language Understanding (Hendrycks 2020)
  hellaswag   — Commonsense NLI sentence completion (Zellers 2019)
  truthfulqa  — Truthfulness / misconception avoidance (Lin 2021)

Domain-specific:
  humaneval   — Python code generation (Chen 2021)
  medqa       — Medical licensing exam (Jin 2021)
  gsm8k       — Grade-school math reasoning (Cobbe 2021)

Usage
-----
    python stdbenchmarks/download_benchmarks.py [--benchmarks mmlu hellaswag ...]
                                                [--out-dir stdbenchmarks/data]
                                                [--limit N]
                                                [--split test]

Requirements
------------
    pip install datasets
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Benchmark download specifications
# ---------------------------------------------------------------------------

# Each entry: name → (hf_path, hf_name_or_None, split, row_transform_fn)
# row_transform_fn(row, idx) → dict suitable for adapter's _iter_jsonl to consume.

def _identity(row: dict, idx: int) -> dict:
    return dict(row)


def _mmlu_row(row: dict, idx: int) -> dict:
    """cais/mmlu rows: question, choices (list), answer (int 0-3), subject."""
    return {
        'id': f'mmlu-{idx:05d}',
        'question': row['question'],
        'choices': list(row['choices']),
        'answer': int(row['answer']),
        'subject': row.get('subject', 'general'),
    }


def _hellaswag_row(row: dict, idx: int) -> dict:
    """Rowan/hellaswag rows: ind, activity_label, ctx, endings, label."""
    return {
        'ind': row.get('ind', str(idx)),
        '_idx': idx,
        'activity_label': row.get('activity_label', ''),
        'ctx_a': row.get('ctx_a', ''),
        'ctx_b': row.get('ctx_b', ''),
        'ctx': row.get('ctx', ''),
        'endings': list(row['endings']),
        'label': str(row['label']),
    }


def _truthfulqa_row(row: dict, idx: int) -> dict:
    """truthful_qa generation rows: question, best_answer, correct_answers,
    incorrect_answers, category, source."""
    return {
        'id': f'truthfulqa-{idx:04d}',
        'question': row['question'],
        'best_answer': row.get('best_answer', ''),
        'correct_answers': list(row.get('correct_answers', [])),
        'incorrect_answers': list(row.get('incorrect_answers', [])),
        'category': row.get('category', 'Other'),
        'source': row.get('source', ''),
    }


def _humaneval_row(row: dict, idx: int) -> dict:
    """openai_humaneval rows: task_id, prompt, canonical_solution, test, entry_point."""
    return {
        'task_id': row['task_id'],
        'prompt': row['prompt'],
        'canonical_solution': row['canonical_solution'],
        'test': row['test'],
        'entry_point': row.get('entry_point', ''),
    }


def _medqa_row(row: dict, idx: int) -> dict:
    """bigbio/med_qa rows vary by config. We normalise to a flat dict.

    The 'us' config (4 options) uses: question, answer (letter), options (dict),
    meta_info, answer_idx.  We handle both dict and list options formats.
    """
    options_raw = row.get('options', {})
    if isinstance(options_raw, dict):
        options = {k: str(v) for k, v in options_raw.items()}
    elif isinstance(options_raw, list):
        # Some configs store [{key:'A', value:'...'}, ...]
        options = {}
        for opt in options_raw:
            if isinstance(opt, dict) and 'key' in opt:
                options[opt['key']] = opt.get('value', str(opt))
            else:
                break
    else:
        options = {}

    answer = row.get('answer', row.get('answer_idx', ''))
    # Normalise answer to letter
    if isinstance(answer, int):
        letters = ['A', 'B', 'C', 'D']
        answer = letters[answer] if 0 <= answer < len(letters) else ''
    else:
        answer = str(answer).strip().upper()[:1]

    return {
        'id': f'medqa-{idx:04d}',
        'question': row.get('question', ''),
        'options': options,
        'answer': answer,
        'meta_info': row.get('meta_info', row.get('category', 'Other')),
    }


def _gsm8k_row(row: dict, idx: int) -> dict:
    """openai/gsm8k rows: question, answer (solution + #### N)."""
    return {
        'id': f'gsm8k-{idx:04d}',
        'question': row['question'],
        'answer': row['answer'],
    }


# ---------------------------------------------------------------------------
# Canonical download specs
# ---------------------------------------------------------------------------

BENCHMARK_SPECS: dict[str, dict] = {
    'mmlu': {
        'hf_path': 'cais/mmlu',
        'hf_name': 'all',
        'split': 'test',
        'row_fn': _mmlu_row,
        'description': 'MMLU — Massive Multitask Language Understanding (57 subjects)',
    },
    'hellaswag': {
        'hf_path': 'Rowan/hellaswag',
        'hf_name': None,
        'split': 'validation',
        'row_fn': _hellaswag_row,
        'description': 'HellaSwag — commonsense sentence-completion benchmark',
    },
    'truthfulqa': {
        'hf_path': 'truthful_qa',
        'hf_name': 'generation',
        'split': 'validation',
        'row_fn': _truthfulqa_row,
        'description': 'TruthfulQA — measures truthfulness and avoidance of misconceptions',
    },
    'humaneval': {
        'hf_path': 'openai_humaneval',
        'hf_name': None,
        'split': 'test',
        'row_fn': _humaneval_row,
        'description': 'HumanEval — 164 Python programming problems',
    },
    'medqa': {
        'hf_path': 'bigbio/med_qa',
        'hf_name': 'med_qa_en_source',
        'split': 'test',
        'row_fn': _medqa_row,
        'description': 'MedQA-USMLE — medical licensing exam MCQ',
    },
    'gsm8k': {
        'hf_path': 'openai/gsm8k',
        'hf_name': 'main',
        'split': 'test',
        'row_fn': _gsm8k_row,
        'description': 'GSM8K — grade-school math word problems',
    },
}


# ---------------------------------------------------------------------------
# Download logic
# ---------------------------------------------------------------------------

def download_benchmark(
    name: str,
    out_dir: Path,
    split: str | None = None,
    limit: int | None = None,
) -> Path:
    """Download one benchmark and write <out_dir>/<name>/<split>.jsonl.

    Returns the path to the written file.
    """
    try:
        from datasets import load_dataset
    except ImportError:
        print(
            "ERROR: 'datasets' package is required. Install with:\n"
            "  pip install datasets",
            file=sys.stderr,
        )
        sys.exit(1)

    spec = BENCHMARK_SPECS[name]
    effective_split = split or spec['split']
    row_fn = spec['row_fn']

    print(f"[{name}] Downloading from HuggingFace: {spec['hf_path']!r} "
          f"(config={spec['hf_name']!r}, split={effective_split!r}) …")

    ds = load_dataset(
        spec['hf_path'],
        spec['hf_name'],
        split=effective_split,
        trust_remote_code=True,
    )

    out_subdir = out_dir / name
    out_subdir.mkdir(parents=True, exist_ok=True)
    out_path = out_subdir / f'{effective_split}.jsonl'

    n_written = 0
    with open(out_path, 'w', encoding='utf-8') as fh:
        for i, row in enumerate(ds):
            if limit is not None and n_written >= limit:
                break
            transformed = row_fn(dict(row), i)
            fh.write(json.dumps(transformed, ensure_ascii=False) + '\n')
            n_written += 1

    print(f"[{name}] ✓  Wrote {n_written} rows → {out_path}")
    return out_path


def main() -> None:
    parser = argparse.ArgumentParser(
        description='Download standard LLM benchmarks to JSONL files.',
    )
    parser.add_argument(
        '--benchmarks', nargs='+',
        default=list(BENCHMARK_SPECS.keys()),
        choices=list(BENCHMARK_SPECS.keys()),
        metavar='NAME',
        help=f'Benchmarks to download (default: all). '
             f'Choices: {", ".join(BENCHMARK_SPECS)}',
    )
    parser.add_argument(
        '--out-dir', default='stdbenchmarks/data', metavar='PATH',
        help='Output directory (default: stdbenchmarks/data)',
    )
    parser.add_argument(
        '--limit', type=int, default=None, metavar='N',
        help='Max rows per benchmark (default: all)',
    )
    parser.add_argument(
        '--split', default=None, metavar='SPLIT',
        help='Dataset split to download (default: per-benchmark default)',
    )
    parser.add_argument(
        '--list', action='store_true',
        help='List available benchmarks and exit',
    )
    args = parser.parse_args()

    if args.list:
        print('\nAvailable benchmarks:')
        for bname, spec in BENCHMARK_SPECS.items():
            print(f'  {bname:<12} {spec["description"]}')
        return

    out_dir = Path(args.out_dir)
    failures: list[str] = []

    for name in args.benchmarks:
        try:
            download_benchmark(name, out_dir, split=args.split, limit=args.limit)
        except Exception as exc:
            print(f'[{name}] ✗  FAILED: {exc}', file=sys.stderr)
            failures.append(name)

    if failures:
        print(
            f'\n{len(failures)} benchmark(s) failed to download: {", ".join(failures)}',
            file=sys.stderr,
        )
        sys.exit(1)

    print(f'\nAll done. Data in: {out_dir.resolve()}')
    print('You can now run:  coeval ingest --run <RUN_PATH> --benchmark <NAME>')


if __name__ == '__main__':
    main()
