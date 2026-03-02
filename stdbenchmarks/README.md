# stdbenchmarks/ — Standard LLM Benchmark Downloader

This directory contains a utility for downloading standard public LLM benchmarks from HuggingFace Datasets into local JSONL files. The resulting data files can be ingested into CoEval experiments via `coeval ingest`.

## Contents

| File | Description |
|------|-------------|
| [download_benchmarks.py](download_benchmarks.py) | Script to download and convert benchmark datasets to JSONL |

Downloaded data is written to `stdbenchmarks/data/` (created on first run).

## Supported Benchmarks

| Name | Description | HuggingFace Path |
|------|-------------|-----------------|
| `mmlu` | MMLU — Massive Multitask Language Understanding (57 subjects) | `cais/mmlu` |
| `hellaswag` | HellaSwag — commonsense sentence-completion | `Rowan/hellaswag` |
| `truthfulqa` | TruthfulQA — truthfulness and misconception avoidance | `truthful_qa` |
| `humaneval` | HumanEval — 164 Python programming problems | `openai_humaneval` |
| `medqa` | MedQA-USMLE — medical licensing exam MCQ | `bigbio/med_qa` |
| `gsm8k` | GSM8K — grade-school math word problems | `openai/gsm8k` |

## Usage

```bash
# Download all benchmarks (default: test split, all rows)
python stdbenchmarks/download_benchmarks.py

# Download specific benchmarks with a row limit
python stdbenchmarks/download_benchmarks.py --benchmarks mmlu gsm8k --limit 500

# List available benchmarks
python stdbenchmarks/download_benchmarks.py --list
```

Requires:
```bash
pip install datasets
```

## Ingesting into CoEval

After downloading, ingest a benchmark into a CoEval run:

```bash
coeval ingest --run benchmark/runs/my-run --benchmark mmlu
```

See [`manuals/02_benchmark_experiments.md`](../manuals/02_benchmark_experiments.md) for the full ingestion workflow.
