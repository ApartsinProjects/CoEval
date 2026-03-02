# Extracting Reusable Benchmarks

CoEval's 5-phase pipeline generates rich synthetic benchmark data as a natural byproduct of running experiments. This guide explains how to extract that data into standalone, reusable benchmark packages that can be shared, published, or used to reproduce evaluation results across different models and teams.

Related documentation: [README](../README.md) | [Tutorial](tutorial.md) | [Benchmark Experiments Manual](../manuals/02_benchmark_experiments.md)

---

## What Is Benchmark Extraction?

When CoEval runs an experiment, Phase 3 (Data Generation) produces a set of `(prompt, reference_response)` pairs annotated with sampled attribute values. These datapoints represent a structured, reproducible evaluation dataset — a benchmark in its own right.

Benchmark extraction is the process of packaging those Phase 3 datapoints, along with the associated rubric and attribute metadata, into a self-contained artifact that can be:

- **Reused** in future experiments without re-generating data
- **Shared** with collaborators or published to a benchmark repository
- **Referenced** as a fixed test set when comparing new models over time
- **Reproduced** by other teams who want to validate results independently

Extraction decouples the benchmark creation step from the model evaluation step. Once you have a published benchmark package, anyone can run phases 4 and 5 against it to evaluate any model — without needing access to your original teacher models or API keys.

---

## Three Common Scenarios

### Scenario A: Export Your Synthetic CoEval Data as a Reusable Benchmark

You have run a CoEval experiment and want to publish the Phase 3 datapoints as a standalone benchmark that others can evaluate against.

**Use case examples:**
- You generated a domain-specific summarization benchmark using GPT-4o and want to share it with your team
- You created a code explanation dataset with a fine-tuned teacher and want to contribute it to a public repository
- You want to lock in a fixed test set for ongoing model regression testing

### Scenario B: Contribute to a Public Benchmark via Ingest

You have an external dataset (a JSONL file, a HuggingFace dataset, or a CSV) and want to bring it into the CoEval Phase 3 format so it can be used as the teacher source in mixed experiments.

**Use case examples:**
- You want to evaluate models against XSum or ARC-Challenge using CoEval's evaluation pipeline
- You have proprietary labeled data and want to use it as ground truth in a CoEval experiment

### Scenario C: Reproduce Published Results Using an Exported Benchmark

Someone has shared an exported benchmark package with you and you want to run your own models against it, reproducing or extending their evaluation.

**Use case examples:**
- Validating that a new model matches a published baseline on a shared benchmark
- Extending an existing benchmark evaluation with additional models or tasks

---

## Scenario A: Exporting a CoEval Experiment as a Benchmark Package

### Step 1: Run a Standard Experiment Through Phase 3

Before you can export, you need a completed Phase 3. A minimal config that reaches Phase 3:

```yaml
# benchmark/configs/summarization-teacher.yaml
experiment_id: summarization-benchmark-v1
phases: [1, 2, 3]

models:
  - name: gpt-4o-mini
    interface: openai
    roles: [teacher]

tasks:
  - id: text_summarization
    description: >
      Summarise a news article in 1–3 concise sentences, preserving the
      main facts and omitting editorial commentary.
    target_attributes:
      article_length: [short, medium, long]
      domain: [technology, politics, science, business]
    items_per_teacher: 20

output_dir: benchmark/runs/
```

Run it:

```bash
coeval run --config benchmark/configs/summarization-teacher.yaml
```

After completion the EES folder will contain:

```
benchmark/runs/summarization-benchmark-v1/
├── meta.json
├── config.yaml
├── phase2_rubrics/
│   └── text_summarization.rubric.json
├── phase3_datapoints/
│   └── text_summarization.gpt-4o-mini.datapoints.jsonl
├── phase4_responses/          # empty — phases 4-5 not run
└── phase5_evaluations/        # empty
```

### Step 2: Assemble the Benchmark Package

A reusable benchmark package is a directory containing:

1. The Phase 3 JSONL datapoint files
2. The Phase 2 rubric JSON files
3. A `benchmark_info.yaml` manifest

Create the package directory and copy the relevant files:

```bash
mkdir -p exports/summarization-benchmark-v1/datapoints
mkdir -p exports/summarization-benchmark-v1/rubrics

cp benchmark/runs/summarization-benchmark-v1/phase3_datapoints/*.jsonl \
   exports/summarization-benchmark-v1/datapoints/

cp benchmark/runs/summarization-benchmark-v1/phase2_rubrics/*.json \
   exports/summarization-benchmark-v1/rubrics/
```

### Step 3: Write the `benchmark_info.yaml` Manifest

The manifest describes the benchmark for consumers who did not create it:

```yaml
# exports/summarization-benchmark-v1/benchmark_info.yaml
name: summarization-benchmark-v1
version: "1.0"
description: >
  A synthetic news summarization benchmark generated by CoEval using
  GPT-4o-mini as teacher. Covers 4 domains and 3 article lengths.
  80 items total (20 items × 4 attribute combinations per stratum).

created_at: "2026-03-01"
created_by: "your-team@example.com"
coeval_version: "0.3.0"

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

license: CC-BY-4.0
citation: >
  If you use this benchmark, please cite: <your citation here>
```

### Step 4: Optionally Include Phase 4+5 Results as Gold-Standard Data

If you have already run phases 4 and 5, you can include the evaluation results as a reference baseline. Copy the relevant JSONL files:

```bash
cp benchmark/runs/summarization-benchmark-v1/phase4_responses/*.jsonl \
   exports/summarization-benchmark-v1/reference_responses/

cp benchmark/runs/summarization-benchmark-v1/phase5_evaluations/*.jsonl \
   exports/summarization-benchmark-v1/reference_evaluations/
```

Document which models produced these reference results in `benchmark_info.yaml` under a `reference_results` key.

---

## Phase 3 JSONL Format Reference

Each line in a Phase 3 datapoints file is a JSON object with the following fields:

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

| Field | Type | Description |
|---|---|---|
| `id` | string | Unique item identifier: `{task_id}__{teacher_model_id}__{index:05d}` |
| `task_id` | string | Matches the `id` field in the task config |
| `teacher_model_id` | string | Name of the model that generated this item |
| `sampled_target_attributes` | object | The attribute values sampled for this item |
| `prompt` | string | The input prompt that will be sent to student models in Phase 4 |
| `reference_response` | string | The teacher's reference answer used by judges in Phase 5 |
| `generated_at` | string | ISO 8601 UTC timestamp of generation |

A second example from a code explanation task:

```json
{
  "id": "code_explanation__claude-3-5-sonnet__00042",
  "task_id": "code_explanation",
  "teacher_model_id": "claude-3-5-sonnet",
  "sampled_target_attributes": {
    "language": "python",
    "complexity": "intermediate",
    "concept": "recursion"
  },
  "prompt": "Explain what the following Python function does and why it works:\n\ndef fib(n):\n    if n <= 1:\n        return n\n    return fib(n-1) + fib(n-2)",
  "reference_response": "This function computes the nth Fibonacci number using recursion. It handles the base cases (0 and 1) directly and builds larger values by summing the two preceding numbers. Each call spawns two more calls, giving it O(2^n) time complexity.",
  "generated_at": "2025-03-01T15:04:52Z"
}
```

---

## Scenario B: Ingesting External Benchmarks

### Using `coeval ingest`

The `coeval ingest` command converts an external JSONL dataset into Phase 3 format and places it in an experiment's `phase3_datapoints/` folder:

```bash
coeval ingest \
  --dataset path/to/my_benchmark.jsonl \
  --run-id my-experiment-v1 \
  --task text_summarization \
  --teacher-id my-benchmark
```

The input JSONL must have at minimum `prompt` and `reference_response` fields. Additional fields are preserved as passthrough metadata.

### Using Built-In Dataset Loaders

CoEval ships with loaders for several public benchmarks under `benchmark/loaders/`. The setup scripts use these loaders to emit Phase 3 JSONL directly:

```bash
# Ingest all supported public datasets (run once before using mixed.yaml)
python -m benchmark.setup_mixed
```

Supported loaders and their task domains:

| Loader file | Dataset | Domain |
|---|---|---|
| `benchmark/loaders/xsum.py` | XSum | Text summarization |
| `benchmark/loaders/codesearchnet.py` | CodeSearchNet | Code explanation |
| `benchmark/loaders/aeslc.py` | AESLC | Email composition |
| `benchmark/loaders/wikitablequestions.py` | WikiTableQuestions | Data interpretation |
| `benchmark/loaders/arc_challenge.py` | ARC-Challenge | Science reasoning (MCQ) |
| `benchmark/loaders/race.py` | RACE | Reading comprehension (MCQ) |
| `benchmark/loaders/sciq.py` | SciQ | Science questions (MCQ) |

### Writing a Loader for a New Dataset

A loader is a Python module that yields Phase 3 records. The minimal interface is a `load(task_id, n_items)` function that returns an iterable of dicts matching the Phase 3 schema:

```python
# benchmark/loaders/my_dataset.py
from datasets import load_dataset
from datetime import datetime, timezone


TEACHER_ID = "my-dataset"


def load(task_id: str, n_items: int):
    """Load n_items records from my_dataset and yield Phase 3 dicts."""
    ds = load_dataset("my-org/my-dataset", split="test")
    for i, row in enumerate(ds):
        if i >= n_items:
            break
        yield {
            "id": f"{task_id}__{TEACHER_ID}__{i+1:05d}",
            "task_id": task_id,
            "teacher_model_id": TEACHER_ID,
            "sampled_target_attributes": {
                "category": row.get("category", "unknown"),
            },
            "prompt": row["question"],
            "reference_response": row["answer"],
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }
```

Then write a setup script that calls your loader and writes the JSONL:

```python
# benchmark/setup_my_dataset.py
import json
from pathlib import Path
from benchmark.loaders.my_dataset import load

RUN_ID = "my-dataset-experiment-v1"
TASK_ID = "my_task"
N_ITEMS = 50
OUTPUT_DIR = Path("benchmark/runs") / RUN_ID / "phase3_datapoints"

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
out_file = OUTPUT_DIR / f"{TASK_ID}.my-dataset.datapoints.jsonl"

with out_file.open("w", encoding="utf-8") as f:
    for record in load(TASK_ID, N_ITEMS):
        f.write(json.dumps(record, ensure_ascii=False) + "\n")

print(f"Wrote {N_ITEMS} records to {out_file}")
```

---

## Scenario C: Reproducing Published Results

If someone shares an exported benchmark package with you, follow these steps to run your own models against it.

### Step 1: Place the Datapoint Files

Copy the shared JSONL files into your experiment's `phase3_datapoints/` folder:

```bash
mkdir -p benchmark/runs/my-repro-v1/phase3_datapoints

cp exports/summarization-benchmark-v1/datapoints/*.jsonl \
   benchmark/runs/my-repro-v1/phase3_datapoints/
```

### Step 2: Create a Config Using `interface: benchmark`

The `interface: benchmark` virtual interface tells CoEval to load Phase 3 data from disk rather than calling a live LLM. Configure the benchmark teacher by setting its `name` to match the `teacher_model_id` values in the JSONL files:

```yaml
# benchmark/configs/repro-summarization.yaml
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

Because the Phase 3 data is already in place and the benchmark teacher makes no API calls, you only need to run the response collection and evaluation phases:

```bash
coeval run --config benchmark/configs/repro-summarization.yaml
```

CoEval will skip Phase 3 generation entirely (since `phases: [4, 5]` is set) and instead load the pre-existing JSONL files from `phase3_datapoints/`.

---

## YAML Config Examples

### Example 1: Phase 3 Only (Generate Benchmark Data)

```yaml
experiment_id: code-benchmark-v1
phases: [1, 2, 3]

models:
  - name: gpt-4o
    interface: openai
    roles: [teacher]

tasks:
  - id: code_explanation
    description: >
      Explain what a short code snippet does, covering its purpose,
      key steps, and any edge cases.
    target_attributes:
      language: [python, javascript, go, rust]
      complexity: [beginner, intermediate, advanced]
      concept: [recursion, concurrency, error_handling, data_structures]
    items_per_teacher: 15

output_dir: benchmark/runs/
```

### Example 2: Mixed Benchmark (Public Dataset Teacher + OpenAI Students)

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

### Example 3: Multi-Teacher Benchmark Generation

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

### Example 4: Reproduction Config with Multiple Students

```yaml
# Reproduce and extend an existing benchmark with additional models
experiment_id: repro-extended-v1
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

  - name: gemini-1.5-flash
    interface: gemini
    roles: [student]

  - name: gpt-4o-mini
    interface: openai
    roles: [judge]

tasks:
  - id: text_summarization
    description: Summarise a news article in 1–3 concise sentences.
    items_per_teacher: 80

batch_api:
  enabled: true

output_dir: benchmark/runs/
```

### Example 5: Classification Benchmark with Label Evaluation

```yaml
experiment_id: sentiment-benchmark-v1
phases: [1, 2, 3, 4, 5]

models:
  - name: gpt-4o
    interface: openai
    roles: [teacher]

  - name: gpt-4o-mini
    interface: openai
    roles: [student]

tasks:
  - id: sentiment_classification
    description: >
      Classify the sentiment of a product review as positive, neutral, or negative.
    target_attributes:
      product_category: [electronics, clothing, food, software]
      review_length: [short, medium, long]
    label_attributes: [sentiment]
    items_per_teacher: 30

output_dir: benchmark/runs/
```

When `label_attributes` is set, Phase 5 uses exact-match label evaluation instead of an LLM judge — no judge model is required in the config.

---

## The `benchmark_info.yaml` Manifest Reference

A complete manifest for a multi-task benchmark package:

```yaml
name: my-benchmark-v2
version: "2.0"
description: >
  A multi-task LLM evaluation benchmark generated with CoEval v0.3.0.
  Covers summarization, code explanation, and classification tasks.
  Generated from three teacher models across stratified attribute grids.

created_at: "2026-03-01"
created_by: "research-team@example.com"
coeval_version: "0.3.0"
license: CC-BY-4.0
citation: "Smith et al. (2026). My Benchmark. arXiv:2026.XXXXX"

tasks:
  - id: text_summarization
    description: Summarise a news article in 1–3 concise sentences.
    datapoints_file: datapoints/text_summarization.gpt-4o-mini.datapoints.jsonl
    rubric_file: rubrics/text_summarization.rubric.json
    item_count: 80
    teacher_model: gpt-4o-mini
    target_attributes:
      article_length: [short, medium, long]
      domain: [technology, politics, science, business]

  - id: code_explanation
    description: Explain what a code snippet does.
    datapoints_file: datapoints/code_explanation.claude-3-5-sonnet.datapoints.jsonl
    rubric_file: rubrics/code_explanation.rubric.json
    item_count: 60
    teacher_model: claude-3-5-sonnet
    target_attributes:
      language: [python, javascript, go]
      complexity: [beginner, intermediate, advanced]
      concept: [recursion, concurrency, error_handling, data_structures]

reference_results:
  - model: gpt-4o
    interface: openai
    responses_file: reference_responses/text_summarization.gpt-4o.responses.jsonl
    evaluations_file: reference_evaluations/text_summarization.gpt-4o.evaluations.jsonl
    mean_score: 8.3

  - model: gpt-3.5-turbo
    interface: openai
    responses_file: reference_responses/text_summarization.gpt-3.5-turbo.responses.jsonl
    evaluations_file: reference_evaluations/text_summarization.gpt-3.5-turbo.evaluations.jsonl
    mean_score: 6.7

ingest_command: >
  coeval ingest
    --dataset datapoints/text_summarization.gpt-4o-mini.datapoints.jsonl
    --run-id your-experiment-id
    --task text_summarization
    --teacher-id gpt-4o-mini
```

---

## Tips and Best Practices

**Lock your Phase 3 data before publishing.** Once you share a benchmark, consumers will depend on the exact prompt and reference_response values. Treat the JSONL files as immutable after publication — any changes should produce a new version number in `benchmark_info.yaml`.

**Include the rubric.** Phase 5 judges use the rubric to score responses. Without the rubric JSON, reproducers cannot run a fair evaluation. Always include the `phase2_rubrics/` files in your package.

**Document the teacher model.** The quality and style of `reference_response` values depends heavily on which model generated them. Include the teacher model name and version in your manifest so consumers understand the provenance of the ground truth.

**Use `--continue` for large exports.** If Phase 3 generation is interrupted, restart with:

```bash
coeval run --config your-config.yaml --continue
```

This resumes from where it left off without re-generating existing datapoints.

**Version your benchmark packages.** Use a versioned directory name (e.g., `my-benchmark-v1`, `my-benchmark-v2`) and increment the version in `benchmark_info.yaml` whenever the datapoints change. This allows reproducers to pin to a specific version.

---

## See Also

- [README](../README.md) — project overview and quickstart
- [Tutorial](tutorial.md) — step-by-step walkthrough of the full CoEval pipeline
- [Benchmark Experiments Manual](manuals/02_benchmark_experiments.md) — detailed reference for benchmark-mode configs and the `interface: benchmark` virtual interface
