# Runs/

Experiment configurations and run artefacts. Each subdirectory contains a YAML config for one experiment and (after `coeval run`) the phase output files.

## Structure

```
Runs/
├── mixed/                  # Mixed benchmark (XSum, CodeSearchNet, AESLC, WikiTableQuestions)
│   ├── mixed.yaml          # Experiment config: benchmark virtual teacher + GPT-4o-mini student
│   ├── mixed_description.html   # Planning view (coeval describe output)
│   └── phase*/             # Pipeline output files (after coeval run)
│
├── education/              # Education benchmark (ARC-Challenge, RACE-High, SciQ + synthetic tasks)
│   ├── education.yaml
│   └── education_description.html
│
├── medium-benchmark/       # Medium benchmark — full multi-model run with analysis reports
│   ├── medium_benchmark.yaml
│   ├── reports/            # coeval analyze all output (HTML + Excel)
│   └── phase*/             # Pipeline output files
│
├── paper/                  # Paper evaluation configs (dual-track and benchmarks)
│   ├── paper_dual_track.yaml
│   ├── paper_benchmarks.yaml
│   ├── paper_dual_track_description.html
│   └── phase*/
│
├── simple-test/            # Minimal single-task config for quick smoke tests
│   └── simple_test.yaml
│
├── sota-models/            # SOTA model comparison config
│   └── sota_models.yaml
│
├── benchmark-config/       # Benchmark-only config (benchmark virtual teacher, no LLM calls)
│   └── benchmark_config.yaml
│
└── archive/                # Older run artefacts kept for reference
```

## Running an experiment

```bash
# Preview cost and check model access
coeval plan  --config Runs/mixed/mixed.yaml
coeval probe --config Runs/mixed/mixed.yaml

# Run (or resume interrupted run)
coeval run --config Runs/mixed/mixed.yaml --continue

# Generate analysis reports
coeval analyze all \
    --run Runs/mixed-v1 \
    --out Runs/mixed-v1/reports
```

All configs use `storage_folder: ./Runs` so run artefacts are written to `Runs/<experiment-id>/`.

## Phase output files (inside a run folder)

| File pattern | Phase | Contents |
|---|---|---|
| `{task}.attributes.json` | 1 | Target and nuanced attribute map |
| `{task}.rubric.json` | 2 | Evaluation rubric dimensions |
| `{task}__{teacher}.datapoints.jsonl` | 3 | (prompt, reference_response) pairs |
| `{task}__{teacher}__{student}.responses.jsonl` | 4 | Student answers |
| `{task}__{teacher}__{judge}.evaluations.jsonl` | 5 | Judge scores |
| `meta.json` | — | Phase completion state |
| `run.log` | — | Structured run log |

## Related

- [`docs/tutorial.md`](../docs/tutorial.md) — end-to-end walkthrough
- [`docs/README/06-running.md`](../docs/README/06-running.md) — running experiments guide
- [`docs/README/07-benchmarks.md`](../docs/README/07-benchmarks.md) — benchmark dataset setup
- [`Public/benchmark/`](../Public/benchmark/) — benchmark setup scripts
