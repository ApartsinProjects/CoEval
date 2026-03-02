# Benchmark Datasets

[← Running](06-running.md) · [Reports →](08-reports.md)

---

## What Are Benchmark Teachers?

CoEval supports two modes for supplying evaluation datapoints:

```
Synthetic (generative) mode                Benchmark-sourced mode
──────────────────────────                 ──────────────────────
Phase 1: teachers → attributes             Phase 1: SKIP (static from attribute_map.yaml)
Phase 2: teachers → rubric                 Phase 2: SKIP (static from task YAML)
Phase 3: teachers → datapoints  ──vs──    Phase 3: SKIP (pre-emitted from benchmark)
Phase 4: students → responses              Phase 4: students → responses  (identical)
Phase 5: judges   → scores                 Phase 5: judges   → scores     (identical)
                                           [Extra] metric computation → benchmark_native_score
                                           [Extra] paper_tables.py    → Spearman ρ tables
```

The `interface: benchmark` is a special virtual interface that replays pre-ingested responses from real datasets. No LLM API calls are made for models using this interface. The benchmark teacher's responses are loaded from pre-ingested JSONL files created by `coeval ingest` or setup scripts.

This approach decouples the benchmark creation step from the model evaluation step. Once you have a published benchmark package, anyone can run phases 4 and 5 against it to evaluate any model — without needing access to your original teacher models or API keys.

Benchmark teachers are completely skipped during Phase 3 — their (prompt, reference-response) pairs are loaded directly from pre-ingested JSONL files. Only Phase 4 (student response collection) and Phase 5 (judge evaluation) make LLM API calls. This makes benchmark-sourced experiments significantly cheaper than synthetic ones.

The two modes are fully compatible: Phases 4 and 5 behave identically regardless of how the Phase 3 datapoints were sourced.

---

## Pre-Ingested Datasets

| Dataset | Task | Split | Items | Ground-Truth Metric |
|---------|------|-------|-------|---------------------|
| `xsum` | `text_summarization` | validation | 11,332 | BERTScore-F1 vs. gold summary |
| `codesearchnet` | `code_explanation` | validation | ~10K (Python) | BERTScore-F1 vs. docstring |
| `aeslc` | `email_composition` | validation | ~1K | BERTScore-F1 vs. reference email |
| `wikitablequestions` | `data_interpretation` | validation | 2,831 | Exact-match accuracy |

Additional datasets available via `coeval ingest`: `mmlu`, `hellaswag`, `truthfulqa`, `humaneval`, `medqa`, `gsm8k`, `arc-challenge`, `race`, `sciq`.

Loader files:

| Loader file | Dataset | Domain |
|---|---|---|
| `benchmark/loaders/xsum.py` | XSum | Text summarization |
| `benchmark/loaders/codesearchnet.py` | CodeSearchNet | Code explanation |
| `benchmark/loaders/aeslc.py` | AESLC | Email composition |
| `benchmark/loaders/wikitablequestions.py` | WikiTableQuestions | Data interpretation |
| `benchmark/loaders/arc_challenge.py` | ARC-Challenge | Science reasoning (MCQ) |
| `benchmark/loaders/race.py` | RACE | Reading comprehension (MCQ) |
| `benchmark/loaders/sciq.py` | SciQ | Science questions (MCQ) |

---

## Setup

### Mixed benchmark (XSum, CodeSearchNet, AESLC, WikiTableQuestions)

```bash
# Run once before using benchmark/mixed.yaml
python -m benchmark.setup_mixed
```

This ingests all four benchmarks (10 items each) into a new run folder.

### Education benchmark (ARC-Challenge, RACE-High, SciQ)

```bash
python -m benchmark.setup_education
```

### Emitting datapoints directly

```bash
# All four benchmarks, 620 items each, into a new run folder
python -m benchmark.emit_datapoints \
    --run-id paper-eval-v1 \
    --sample-size 620

# Single dataset
python -m benchmark.emit_datapoints \
    --dataset xsum \
    --run-id paper-eval-v1 \
    --sample-size 620

# Custom output directory
python -m benchmark.emit_datapoints \
    --dataset codesearchnet \
    --out-dir ./benchmark/runs/my-run/phase3_datapoints \
    --sample-size 300 \
    --split test
```

Output files are written to:
```
benchmark/runs/{run-id}/phase3_datapoints/
  text_summarization.benchmark_xsum.datapoints.jsonl
  code_explanation.benchmark_codesearchnet.datapoints.jsonl
  email_composition.benchmark_aeslc.datapoints.jsonl
  data_interpretation.benchmark_wikitablequestions.datapoints.jsonl
```

**Stratified sampling:** By default, the loader applies stratified sampling across all attribute value combinations in the attribute map. This ensures the selected items cover the benchmark's difficulty/domain distribution rather than clustering at its mode.

```
Full benchmark (e.g., 11,332 XSum items)
  ↓ attribute inference (complexity × domain = 4 × 6 = 24 strata)
  ↓ stratified sample: ≈ 26 items per stratum
  ↓ 620 items selected with near-uniform stratum coverage
```

---

## `coeval ingest`

The `coeval ingest` command converts an external JSONL dataset into Phase 3 format:

```bash
coeval ingest \
  --dataset path/to/my_benchmark.jsonl \
  --run-id my-experiment-v1 \
  --task text_summarization \
  --teacher-id my-benchmark
```

The input JSONL must have at minimum `prompt` and `reference_response` fields. Additional fields are preserved as passthrough metadata.

### Phase 3 JSONL Format Reference

Each line in a Phase 3 datapoints file is a JSON object:

```json
{
  "id": "text_summarization__gpt-4o-mini__00001",
  "task_id": "text_summarization",
  "teacher_model_id": "gpt-4o-mini",
  "sampled_target_attributes": {
    "article_length": "medium",
    "domain": "technology"
  },
  "prompt": "Summarise the following article in 1–3 sentences:\n\nApple announced today that...",
  "reference_response": "Apple unveiled a new chip architecture that doubles inference throughput while reducing power draw by 30 percent.",
  "generated_at": "2025-03-01T14:23:11Z"
}
```

For benchmark-sourced records, additional fields are included:

```json
{
  "benchmark_id":          "xsum",
  "benchmark_split":       "validation",
  "benchmark_native_id":   "29750436",
  "benchmark_native_score": null
}
```

`benchmark_native_score` is `null` at emit time and filled in by the metric computation step.

### Writing a Loader for a New Dataset

A loader is a Python module with a `load(task_id, n_items)` function:

```python
# benchmark/loaders/my_dataset.py
from .base import BenchmarkLoader

class MyDatasetLoader(BenchmarkLoader):
    benchmark_id = "my_dataset"
    task_id = "my_task"
    default_split = "test"

    def _load_dataset(self, split: str, seed: int, sample_size: int):
        from datasets import load_dataset
        ds = load_dataset("author/my_dataset", split=split)
        return ds.shuffle(seed=seed).select(range(sample_size))

    def _to_record(self, raw, idx: int) -> dict:
        return {
            "prompt": f"Answer this question: {raw['question']}",
            "reference_response": raw["answer"],
            "sampled_target_attributes": self._infer_attributes(raw),
        }

    def _infer_attributes(self, raw: dict) -> dict:
        return {
            "difficulty": "hard" if len(raw["question"]) > 100 else "easy",
        }
```

Register it in `benchmark/loaders/__init__.py`:

```python
_REGISTRY["my_dataset"] = (
    "benchmark.loaders.my_dataset.MyDatasetLoader",
    "benchmark/configs/my_dataset_attribute_map.yaml",
)
```

Create `benchmark/configs/my_dataset_attribute_map.yaml` and add the dataset to `benchmark/emit_datapoints.py`'s `_DATASETS` dict.

---

## Running Benchmark Experiments

### Config with `interface: benchmark`

```yaml
experiment:
  id: paper-eval-v1
  storage_folder: ./benchmark/runs
  phases:
    attribute_mapping:   Keep   # skip: attributes defined statically in YAML
    rubric_mapping:      Keep   # skip: rubric defined statically in YAML
    data_generation:     Keep   # skip: datapoints pre-emitted by emit_datapoints.py
    response_collection: New    # run students
    evaluation:          New    # run judges
```

The benchmark model acts as teacher:

```yaml
models:
  - name: benchmark          # resolves to the default ingested dataset
    interface: benchmark
    roles: [teacher]

  - name: gpt-4o-mini
    interface: openai
    roles: [student, judge]
```

The `name` field should match the `teacher_model_id` values in the JSONL files. For example, `benchmark-xsum` with task `text_summarization` will load:
```
phase3_datapoints/text_summarization.benchmark-xsum.datapoints.jsonl
```

### Example A: XSum text summarization benchmark

```yaml
models:
  - name: benchmark
    interface: benchmark
    roles: [teacher]

  - name: gpt-4o-mini
    interface: openai
    parameters: { model: gpt-4o-mini, temperature: 0.7, max_tokens: 512 }
    roles: [student, judge]
    role_parameters:
      judge: { temperature: 0.0, max_tokens: 128 }

tasks:
  - name: text_summarization
    description: Produce a concise one-sentence summary of a news article.
    output_description: A single sentence of 15–25 words capturing the article's main point.
    target_attributes:
      article_length: [short, medium, long]
      domain: [politics, sports, technology, science]
    sampling: { target: [1,1], nuance: [0,0], total: 30 }
    rubric:
      relevance:    "The summary accurately reflects the article's main claim."
      conciseness:  "The summary is free of redundant or filler language."
      fluency:      "The summary reads as natural, grammatically correct English."
    evaluation_mode: single

experiment:
  id: xsum-benchmark-v1
  storage_folder: ./benchmark/runs
  batch:
    openai:
      response_collection: true
      evaluation: true
```

Setup and run:

```bash
python -m benchmark.emit_datapoints --dataset xsum --run-id xsum-benchmark-v1 --sample-size 30
coeval run --config xsum-benchmark-v1.yaml --continue
coeval analyze all --run ./benchmark/runs/xsum-benchmark-v1 --out ./reports
```

### Example B: Mixed benchmark (public dataset teacher + OpenAI students)

```yaml
# benchmark/mixed.yaml
experiment_id: mixed-benchmark-v1
phases: [3, 4, 5]

models:
  - name: benchmark
    interface: benchmark
    roles: [teacher]

  - name: gpt-4o-mini
    interface: openai
    roles: [student, judge]

  - name: gpt-3.5-turbo
    interface: openai
    roles: [student]

tasks:
  - id: xsum_summarization
    description: Summarise a BBC news article in one sentence.
    items_per_teacher: 10

  - id: code_explanation
    description: Explain what a code function does.
    items_per_teacher: 10

batch_api:
  enabled: true

output_dir: benchmark/runs/
```

### Example C: Multi-teacher benchmark generation

```yaml
experiment_id: multi-teacher-benchmark-v1
phases: [1, 2, 3]

models:
  - name: gpt-4o
    interface: openai
    roles: [teacher]

  - name: claude-3-5-sonnet
    interface: anthropic
    roles: [teacher]

  - name: gemini-1.5-pro
    interface: gemini
    roles: [teacher]

tasks:
  - id: scientific_qa
    description: >
      Answer a graduate-level science question with a thorough, accurate explanation.
    target_attributes:
      discipline: [physics, chemistry, biology, earth_science]
      difficulty: [undergraduate, graduate, research]
    items_per_teacher: 25

output_dir: benchmark/runs/
```

### Example D: Multi-dataset education benchmark (ARC-Challenge, RACE-High, SciQ)

```yaml
models:
  - name: arc-challenge
    interface: benchmark
    roles: [teacher]

  - name: race-high
    interface: benchmark
    roles: [teacher]

  - name: sciq
    interface: benchmark
    roles: [teacher]

  - name: gpt-4o-mini
    interface: openai
    parameters: { model: gpt-4o-mini, temperature: 0.7, max_tokens: 512 }
    roles: [student, judge]

  - name: gpt-4o
    interface: openai
    parameters: { model: gpt-4o, temperature: 0.7, max_tokens: 512 }
    roles: [student, judge]
    role_parameters:
      judge: { temperature: 0.0, max_tokens: 128 }

tasks:
  - name: arc_science_reasoning
    description: Answer a multiple-choice science question by selecting A, B, C, or D.
    output_description: A single letter — A, B, C, or D.
    target_attributes:
      grade_band: [grade_3_5, grade_6_8, grade_9_10]
      knowledge_type: [factual, conceptual, procedural]
    sampling: { target: [1,1], nuance: [0,0], total: 30 }
    rubric:
      correctness: "The selected answer is the correct option."
    evaluation_mode: single

experiment:
  id: education-benchmark-v1
  storage_folder: ./benchmark/runs
  batch:
    openai:
      response_collection: true
      evaluation: true
  estimate_samples: 0
```

Setup and run:

```bash
python -m benchmark.setup_education    # ingest ARC, RACE-High, SciQ (30 items each)
coeval run --config benchmark/education.yaml --continue
```

---

## Benchmark-Native Scores

After Phase 5 completes, compute the benchmark-native ground-truth score for each datapoint:

```bash
# Requires: pip install bert-score datasets
python -m benchmark.compute_scores \
    --run-id paper-eval-v1 \
    --dataset xsum \
    --metric bertscore

python -m benchmark.compute_scores \
    --run-id paper-eval-v1 \
    --dataset wikitablequestions \
    --metric exact_match
```

Available metrics:

| Metric flag | Used for | Library |
|-------------|----------|---------|
| `bertscore` | XSum, AESLC, CodeSearchNet | `bert-score` |
| `exact_match` | WikiTableQuestions | built-in |
| `rouge_l` | XSum (alternative) | `rouge-score` |

This fills `benchmark_native_score` in the Phase 3 JSONL files and is required for Spearman ρ computation.

### Label Evaluation (Classification Tasks)

For classification and information-extraction tasks where the correct output is a discrete label, use `label_attributes` for judge-free exact-match evaluation:

```yaml
tasks:
  - id: sentiment_classification
    label_attributes: [sentiment]
    ...
```

When `label_attributes` is set, Phase 5 uses exact-match label evaluation instead of an LLM judge — no judge model is required, no judge bias is introduced.

---

## Reproducing Published Results

If someone shares an exported benchmark package with you, follow these steps:

### Step 1: Place the Datapoint Files

```bash
mkdir -p benchmark/runs/my-repro-v1/phase3_datapoints

cp exports/summarization-benchmark-v1/datapoints/*.jsonl \
   benchmark/runs/my-repro-v1/phase3_datapoints/
```

### Step 2: Create a Config Using `interface: benchmark`

```yaml
experiment_id: my-repro-v1
phases: [4, 5]

models:
  - name: gpt-4o-mini
    interface: benchmark
    roles: [teacher]

  - name: gpt-4o
    interface: openai
    roles: [student]

  - name: claude-3-5-haiku
    interface: anthropic
    roles: [student]

  - name: gpt-4o-mini
    interface: openai
    roles: [judge]

tasks:
  - id: text_summarization
    description: >
      Summarise a news article in 1–3 concise sentences.
    items_per_teacher: 80

output_dir: benchmark/runs/
```

### Step 3: Run Phases 4 and 5

```bash
coeval run --config benchmark/configs/repro-summarization.yaml
```

CoEval will skip Phase 3 generation entirely (since `phases: [4, 5]` is set) and instead load the pre-existing JSONL files from `phase3_datapoints/`.

### Exporting Your Own Benchmark Package

A reusable benchmark package is a directory containing:

1. The Phase 3 JSONL datapoint files
2. The Phase 2 rubric JSON files
3. A `benchmark_info.yaml` manifest

**Manifest example:**
```yaml
name: summarization-benchmark-v1
version: "1.0"
description: >
  A synthetic news summarization benchmark generated by CoEval using
  GPT-4o-mini as teacher. Covers 4 domains and 3 article lengths.
created_at: "2026-03-01"
created_by: "your-team@example.com"
coeval_version: "0.3.0"
license: CC-BY-4.0
citation: >
  If you use this benchmark, please cite: <your citation here>

tasks:
  - id: text_summarization
    description: >
      Summarise a news article in 1–3 concise sentences.
    datapoints_file: datapoints/text_summarization.gpt-4o-mini.datapoints.jsonl
    rubric_file: rubrics/text_summarization.rubric.json
    item_count: 80
    teacher_model: gpt-4o-mini
    target_attributes:
      article_length: [short, medium, long]
      domain: [technology, politics, science, business]
```

**Best practices:**
- Lock your Phase 3 data before publishing — treat JSONL files as immutable after publication
- Always include the rubric JSON — judges need it to score responses fairly
- Document the teacher model — the quality of `reference_response` values depends heavily on it
- Use `--continue` for large exports to resume interrupted generation
- Version your benchmark packages (e.g., `my-benchmark-v1`, `my-benchmark-v2`)

---

## Example Configurations

| File | Description |
|------|-------------|
| `benchmark/mixed.yaml` | Mixed benchmark (OpenAI models + real datasets, ~$0.03) |
| `benchmark/education.yaml` | Education benchmark: 3 real-dataset tasks + synthetic tasks, 6 models |
| `benchmark/paper_benchmarks.yaml` | Paper evaluation config: 8 students, 3 judges, all 4 benchmark tasks |
| `benchmark/paper_dual_track.yaml` | Dual-track paper config: benchmark + generative teacher ablation |

---

## Frequently Asked Questions

**Q: What benchmark datasets are available out of the box?**
A: The `benchmark/setup_mixed.py` script ingests four datasets: XSum (BBC news summarization), CodeSearchNet (Python code explanation), AESLC (email subject-line composition), and WikiTableQuestions (table data interpretation). Additional datasets — including MMLU, HellaSwag, TruthfulQA, HumanEval, MedQA, GSM8K, ARC-Challenge, RACE, and SciQ — are available via `coeval ingest`.

**Q: What does `coeval ingest` do?**
A: `coeval ingest` converts an external JSONL dataset into Phase 3 datapoint format, writing files to `benchmark/runs/{run-id}/phase3_datapoints/`. The input JSONL must have at minimum `prompt` and `reference_response` fields. Once ingested, the dataset can be used as a virtual teacher with `interface: benchmark` — no LLM API calls are made for Phase 3.

**Q: How does the `interface: benchmark` virtual teacher work?**
A: A model with `interface: benchmark` is skipped entirely during Phase 3. Instead of generating datapoints via LLM calls, CoEval loads pre-ingested JSONL files from the `phase3_datapoints/` folder. Phases 4 and 5 then run normally — only student responses and judge evaluations require API calls.

**Q: What is stratified sampling and why does it matter?**
A: When emitting datapoints from a large benchmark, CoEval applies stratified sampling across all attribute value combinations. This ensures that the selected items cover the full difficulty/domain distribution of the dataset rather than clustering at the most common values. For example, 620 XSum items are drawn from 24 strata (4 complexity levels × 6 domain values) with roughly equal representation per stratum.

**Q: How do I reproduce someone else's published benchmark results?**
A: Place their exported Phase 3 JSONL files in your `phase3_datapoints/` folder, create a config with `interface: benchmark` as the teacher, and run `coeval run` with phases set to skip Phase 3 (`attribute_mapping: Keep`, `rubric_mapping: Keep`, `data_generation: Keep`). Your student and judge models run against the original benchmark items without regenerating anything.

**Q: How do I write a custom dataset loader for a new benchmark?**
A: Create a Python module in `benchmark/loaders/` that subclasses `BenchmarkLoader` and implements `_load_dataset()` and `_to_record()`. Register it in `benchmark/loaders/__init__.py` with a dataset ID and attribute map path, then add it to `benchmark/emit_datapoints.py`'s `_DATASETS` dict. The loader is then available to `coeval ingest` and `benchmark/emit_datapoints.py`.

---

[← Running](06-running.md) · [Reports →](08-reports.md)
