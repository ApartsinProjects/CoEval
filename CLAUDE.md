# CoEval — Claude Project Memory

> This file travels with the git repository so Claude retains full context
> on any machine the project is cloned to.  It is the single source of truth
> for project layout, conventions and current state.  **Do not store secrets
> here.**  API keys live in `keys.yaml` (git-ignored).

---

## Repository

- **Remote**: https://github.com/ApartsinProjects/CoEval
- **Default working directory**: wherever you cloned it (e.g. `E:\Projects\CoEval\main\`)
- **Version**: v0.3.0

---

## Directory layout

```
Code/
  runner/          ← main pipeline package   (runner.* namespace, 59 .py, ~15 k LoC)
  analyzer/        ← analysis & reporting     (analyzer.* namespace, 21 .py, ~9.5 k LoC)
Public/
  benchmark/       ← benchmark loaders & utils (benchmark.* namespace, 34 .py, ~5.2 k LoC)
    loaders/       ← 28 dataset-specific loaders (base + one per benchmark)
    configs/       ← per-loader attribute-map YAMLs
    scripts/       ← utility scripts
Config/
  provider_pricing.yaml   ← single source of truth for all cost estimation
Tests/
  runner/          ← 14 test modules, 680 tests
  benchmark/       ← 8 test modules, 346 tests
  analyzer/        ← Playwright integration tests (excluded from default run)
  test_structural_integrity.py
Runs/              ← one sub-dir per experiment (YAML config + run data)
docs/              ← all documentation (~35 .md, ~12.5 k LoC)
scripts/           ← repo-level utility scripts
keys.yaml          ← provider API keys  ← git-ignored, never commit
pyproject.toml     ← build + pytest config
```

---

## Running tests

```bash
# Standard run (1 026 tests, ~35 s)
pytest Tests/runner Tests/benchmark -q --tb=short

# Benchmark only (346 tests, ~30 s)
pytest Tests/benchmark -q

# Runner only (680 tests, ~35 s)
pytest Tests/runner -q

# Playwright reports (requires playwright install)
pytest Tests/analyzer/test_reports_playwright.py
```

pytest config (`pyproject.toml`):
- `testpaths = ["Tests"]`
- `addopts = "--import-mode=importlib --ignore=Tests/analyzer/test_reports_playwright.py"`

**Known pre-existing failures (not regressions):**
- `Tests/benchmark/test_compute_scores.py::TestBleu4Single` (6) — requires `pip install nltk`
- `Tests/benchmark/test_new_loaders.py::TestBBHLoaderLoadDataset::test_loads_multiple_subtasks` (1) — mock setup mismatch

---

## CLI entry point

```
coeval run/probe/plan/status/generate/models/analyze/describe/ingest/repair/wizard
```

`runner.cli:main` → `Code/runner/cli.py`

Key subcommands:
| Command | Purpose |
|---------|---------|
| `run` | Execute full EER pipeline (phases 1–5) |
| `probe` | Standalone model availability check |
| `plan` | Cost/time estimation without running |
| `status` | Progress dashboard + batch result fetch |
| `generate` | Run phases 1–2 only → materialised YAML |
| `ingest` | Inject benchmark data as virtual teacher |
| `repair` | Scan + mark invalid JSONL records for re-gen |
| `wizard` | LLM-assisted interactive YAML builder |
| `analyze` | Run EEA on a completed experiment folder |

---

## Key source files

| File | Purpose |
|------|---------|
| `Code/runner/runner.py` | Orchestrates 5-phase pipeline |
| `Code/runner/storage.py` | All filesystem I/O (EES) |
| `Code/runner/config.py` | Config loading + validation (V-01…V-19) |
| `Code/runner/metric_judge.py` | Non-LLM metric judges (BERTScore, BLEU, exact_match) |
| `Code/runner/cli.py` | CLI entry point |
| `Code/runner/phases/phase{1-5}.py` | Per-phase implementations |
| `Code/runner/interfaces/pool.py` | `ModelPool` factory |
| `Code/runner/interfaces/probe.py` | Model availability probe |
| `Code/runner/interfaces/cost_estimator.py` | Cost/time estimates (`PRICE_TABLE`) |
| `Code/runner/interfaces/registry.py` | Key loading + provider model listing |
| `Code/runner/label_eval.py` | `LabelEvaluator` — classification tasks, no judge |
| `Code/analyzer/calibration.py` | OLS calibration (α, β) — disabled by default (3-level limitation) |
| `Code/analyzer/paper_tables.py` | Tables 3–9; RAR, surface bias, calibration |
| `Public/benchmark/loaders/base.py` | `BenchmarkLoader` ABC |
| `Public/benchmark/loaders/__init__.py` | `_REGISTRY` — maps dataset name → loader |
| `Public/benchmark/compute_scores.py` | Fills `benchmark_native_score`; `BENCHMARK_METRIC` |
| `Config/provider_pricing.yaml` | Provider prices + batch discounts |

---

## Benchmark loaders (28 total)

Registered in `Public/benchmark/loaders/__init__.py` (`_REGISTRY`).

| Loader | Metric |
|--------|--------|
| xsum, aeslc, cnn_dailymail, samsum | bertscore |
| codesearchnet, mbpp, narrativeqa | bleu |
| All others (MCQ, QA, NLI, etc.) | exact_match |

Loaders: arc_challenge, bbq, bigbench_hard, copa, cosmos_qa, fever,
logiqa, math_dataset, mathqa, mbpp, mgsm, multinli, narrativeqa,
nq_open, race, samsum, scifact, sciq, squad_v2, trivia_qa,
wikitablequestions, winogrande — plus xsum, aeslc, codesearchnet,
cnn_dailymail, bigbench_hard/math_dataset (MATH).

---

## Supported model interfaces

| Interface | Batch | Auth env var |
|-----------|-------|--------------|
| `openai` | OpenAI Batch API | `OPENAI_API_KEY` |
| `anthropic` | Message Batches API | `ANTHROPIC_API_KEY` |
| `gemini` | Gemini Batch (google-genai) | `GEMINI_API_KEY` / `GOOGLE_API_KEY` |
| `vertex` | Vertex AI Batch Prediction | ADC + `GOOGLE_CLOUD_PROJECT` |
| `azure_openai` | Azure Batch | `AZURE_OPENAI_API_KEY` + endpoint |
| `bedrock` | Bedrock Batch | `api_key` OR AWS IAM |
| `huggingface` | None (GPU) | `HF_TOKEN` |
| `openrouter` | None | `OPENROUTER_API_KEY` |
| `groq` | None | `GROQ_API_KEY` |
| `deepseek` | None | `DEEPSEEK_API_KEY` |
| `mistral` | Mistral Batch | `MISTRAL_API_KEY` |
| `azure_ai` | None | `AZURE_AI_API_KEY` |
| `openai_compat` | None | provider-specific |
| `benchmark` | N/A (virtual) | none |
| `metric` | N/A (deterministic) | none |
| `auto` | resolves at load time | — |

---

## Provider key file

- **Auto-discovered**: `keys.yaml` in project root
- **Lookup order**: `--keys PATH` → `COEVAL_KEYS_FILE` env → `keys.yaml` → `~/.coeval/keys.yaml`
- **Format**: `providers:` block with per-provider key dicts
- `keys.yaml` and `.coeval/` are git-ignored — never commit keys

---

## Phase 3 JSONL schema (benchmark records)

```json
{
  "id": "...",
  "task_id": "...",
  "teacher_model_id": "...",
  "sampled_target_attributes": {...},
  "prompt": "...",
  "reference_response": "...",
  "generated_at": "2026-...",
  "benchmark_id": "logiqa",
  "benchmark_split": "test",
  "benchmark_native_id": "42",
  "benchmark_native_score": null
}
```

---

## Phase 4 response record schema

```json
{
  "id": "dp001__gpt-4o",
  "datapoint_id": "dp001",
  "task_id": "text_summarization",
  "teacher_model_id": "benchmark:xsum",
  "student_model_id": "gpt-4o",
  "input": "...",
  "response": "...",
  "token_count": 247,
  "generated_at": "2026-..."
}
```

---

## Config validation rules

V-01 through V-19.  `validate_config()` in `Code/runner/config.py`.

- V-15: `probe_mode` ∈ {`disable`, `full`, `resume`}
- V-16: `probe_on_fail` ∈ {`abort`, `warn`}
- V-17: `label_attributes` must be a subset of `target_attributes`
- V-18: metric rubric factors must reference supported metrics (bertscore, bleu, exact_match)
- V-19: metric interface models must have `judge` role

---

## Continue / resume feature

```bash
coeval run --config X.yaml --continue
```

Reads `phases_completed` from `meta.json`, skips done phases.
Phases 1–2: Keep mode; Phases 3–5: Extend mode.

---

## Known model quirks

- `qwen2p5-0b5` as JUDGE: produces empty JSON → use as student only
- `smollm2-1b7` as TEACHER (Phase 3): sometimes wrong JSON keys
- HF judge needs `max_new_tokens` ≥ 256

---

## Metric judges (v0.3.1)

Non-LLM judges that compute deterministic metrics as rubric dimensions.
Returns continuous [0, 1] scores instead of ordinal High/Medium/Low.

- **Supported metrics**: `bertscore`, `bleu`, `exact_match`
- **Interface**: `metric` (virtual — no LLM calls, no API keys)
- **Rubric format**: metric factors are dicts with a `"metric"` key:
  ```yaml
  rubric:
    accuracy: "All key facts are preserved"    # LLM-evaluated
    bertscore_f1:                               # metric-evaluated
      metric: bertscore
      description: "BERTScore F1 similarity"
  ```
- **Phase 5 dispatch**: metric judges run first (deterministic, no batching).
  LLM judges see only their qualitative factors — metric factors are filtered out.
- **Module**: `Code/runner/metric_judge.py`

## Calibration status

OLS calibration (`Code/analyzer/calibration.py`) is **disabled by default**.
LLM judges produce only 3 ordinal values (1.0, 0.5, 0.0), making OLS fit
unreliable. Enable with `--enable-calibration` only when metric judges
provide continuous scores.

---

## Paper status (as of 2026-03-03)

- 7 sections + ethics + appendix written; 8 figures in `docs/paper/figures/`
- **Numbers in `docs/paper/04_results.md` are FICTIONAL PLACEHOLDERS**
- Gaps fixed: G1 (RAR), G3 (token_count), G4 (calibration), G5 (baselines), G8 (surface bias)
- Deferred: G2 (positional swap), G6 (cost tracking), G7 (pass@k)
