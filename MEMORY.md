# CoEval Project Memory

## Canonical working directory
`E:\Projects\CoEval\main\` — fresh clone of https://github.com/ApartsinProjects/CoEval

## Structure (v0.3.0)
```
experiments/   ← main pipeline package (experiments.* namespace)
analysis/      ← analysis & reporting package (analysis.* namespace)
benchmark/     ← benchmark configs and runs
docs/
paper/         ← academic paper draft + figures + tables
manuals/
examples/
samples/
pyproject.toml
```
CLI entry: `experiments.cli:main` → `coeval run/probe/plan/status/generate/models/analyze/describe`

## Key files
- `experiments/runner.py` — orchestrates 5-phase pipeline; passes `cfg._provider_keys` to ModelPool
- `experiments/storage.py` — all filesystem I/O (EES)
- `experiments/config.py` — config loading and validation (V-01 through V-17); `load_config(keys_file=None)`
- `experiments/cli.py` — CLI (`coeval run/probe/plan/status/generate/models/analyze/describe`); `--keys PATH` on all config-consuming subcommands
- `experiments/commands/probe_cmd.py` — standalone model probe (`coeval probe`)
- `experiments/commands/plan_cmd.py` — standalone cost estimator (`coeval plan`)
- `experiments/commands/status_cmd.py` — progress dashboard + batch fetch (`coeval status`)
- `experiments/commands/generate_cmd.py` — phases 1-2 in temp dir -> materialized YAML (`coeval generate`)
- `experiments/commands/models_cmd.py` — list provider models (`coeval models`)
- `experiments/commands/describe_cmd.py` — generate HTML summary of experiment config (`coeval describe`)
- `experiments/phases/phase{1-5}.py` — individual phase implementations
- `experiments/phases/phase4.py` — Phase 4 response collection; records include `token_count` field (count_tokens_approx)
- `experiments/label_eval.py` — LabelEvaluator for classification/IE tasks (no judge needed)
- `experiments/interfaces/probe.py` — model availability probe; supports all 8 interfaces
- `experiments/interfaces/pool.py` — ModelPool factory; accepts `provider_keys: dict`
- `experiments/interfaces/registry.py` — `load_keys_file()`, `resolve_provider_keys()`, `list_provider_models()`
- `experiments/interfaces/cost_estimator.py` — cost/time estimation (PRICE_TABLE, estimate_experiment_cost, count_tokens_approx)
- `experiments/interfaces/azure_openai_iface.py` — Azure OpenAI interface
- `experiments/interfaces/bedrock_iface.py` — AWS Bedrock (boto3 IAM OR native api_key HTTP)
- `experiments/interfaces/vertex_iface.py` — Google Vertex AI interface
- `experiments/interfaces/openrouter_iface.py` — OpenRouter interface
- `experiments/tests/` — unit tests (pytest) — 483 passing as of 2026-03-02
- `analysis/tests/` — analysis unit tests
- `analysis/tests/test_reports_playwright.py` — 55 Playwright tests for all 8 HTML reports
- `analysis/calibration.py` — OLS linear calibration (α, β) for judge scores vs benchmark GT
- `analysis/paper_tables.py` — Tables 3-9 generators; includes RAR, Surface Bias, OLS calibration (Tables 4, 7, 8)
- `docs/cli_reference.md` — complete CLI reference for all subcommands
- `docs/tutorial.md` — end-to-end tutorial (motivation through robust benchmark export)
- `benchmark/mixed.yaml` — mixed benchmark config (cheap OpenAI + real benchmark datasets)
- `benchmark/setup_mixed.py` — one-time setup script for mixed benchmark
- `benchmark/paper_benchmarks.yaml` — full paper validation config (4 tasks, 8 students, 3 judges, 620 items/task)
- `benchmark/run_baselines.py` — BERTScore + G-Eval baseline comparison; writes baselines.csv for Table 3
- `benchmark/compute_scores.py` — populates `benchmark_native_score` in Phase 3 JSONL
- `benchmark/emit_datapoints.py` — emits Phase 3 JSONL from benchmark datasets
- `benchmark/loaders/xsum.py`, `aeslc.py`, `codesearchnet.py`, `wikitablequestions.py` — dataset loaders
- `paper/paper_plan.md` — paper plan (ACL 2026 long paper target; 5 core claims; 3-round review checklist)
- `paper/cost_estimate.md` — paper experiment cost breakdown by scenario
- `paper/figures/` — 8 paper figures (fig1_architecture.png through fig8_rubric_drift.png)
- `manuals/02_benchmark_experiments.md` — benchmark experiment workflow (emit → run → compute_scores → baselines → paper_tables → calibration)

## Supported model interfaces
| Interface | Batching | Auth env var | Install |
|-----------|----------|-------------|---------|
| `openai` | OpenAI Batch API (50% discount) | `OPENAI_API_KEY` | pre-installed |
| `anthropic` | Message Batches API (50% discount) | `ANTHROPIC_API_KEY` | `pip install anthropic` |
| `gemini` | Pseudo-batch (no discount) | `GEMINI_API_KEY` or `GOOGLE_API_KEY` | `pip install google-generativeai` |
| `huggingface` | None (GPU required) | `HF_TOKEN` or `HUGGINGFACE_HUB_TOKEN` | `pip install 'coeval[huggingface]'` |
| `azure_openai` | None (real-time) | `AZURE_OPENAI_API_KEY` + `AZURE_OPENAI_ENDPOINT` | pre-installed (openai) |
| `bedrock` | None (real-time) | `api_key` OR (`AWS_ACCESS_KEY_ID` + `AWS_SECRET_ACCESS_KEY`) | `pip install boto3` (IAM only) |
| `vertex` | None (real-time) | `GOOGLE_CLOUD_PROJECT` + ADC | `pip install google-cloud-aiplatform` |
| `openrouter` | None (real-time) | `OPENROUTER_API_KEY` | pre-installed (openai) |
| `benchmark` | N/A (virtual; no API calls) | none | pre-installed |

## Provider key file
- **Primary location**: `E:\Projects\CoEval\main\keys.yaml` (project root, auto-discovered)
- Lookup order: `--keys PATH` → `COEVAL_KEYS_FILE` env → project root `keys.yaml` → `~/.coeval/keys.yaml`
- Key file format: `providers:` block with per-provider keys/dicts
- `.gitignore` includes `keys.yaml`, `*.keys.yaml`, `.coeval/`

## Current provider credential status (as of 2026-03-02)
| Provider | Status | Source |
|----------|--------|--------|
| OpenAI | ✅ Configured | keys.yaml + env |
| Anthropic | ✅ Configured | keys.yaml |
| Gemini | ✅ Configured | keys.yaml |
| HuggingFace | ✅ Configured | keys.yaml |
| OpenRouter | ✅ Configured | keys.yaml |
| AWS Bedrock | ✅ Configured (native API key, us-east-1) | keys.yaml |
| Azure OpenAI | ❌ Not configured | — |
| Google Vertex AI | ❌ Not configured | — |

## Phase 4 response records (as of 2026-03-02)
Phase 4 JSONL records now include `token_count` (heuristic int via `count_tokens_approx`):
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
  "generated_at": "2026-03-02T10:00:00Z"
}
```

## paper_tables.py metrics (as of 2026-03-02)
New computed metrics in `analysis/paper_tables.py`:
- **`_compute_rar(model)`** — Rare-Attribute Recall per task: strata with count < 3 are "rare"; RAR = fraction covered. Used in Table 4 and Table 7 (replaces "19.3%" placeholder).
- **`_surface_bias(prompts)`** — mean pairwise sentence-BLEU across Phase 3 prompts (requires nltk). Used in Table 4.
- **Table 8** now fits OLS calibration (α, β) via `analysis/calibration.py` when benchmark scores exist; saves `calibration_params_overall.json`.

## analysis/calibration.py
- `fit_calibration(raw, gt, holdout_n=200)` — OLS fit, returns α, β, ρ_raw, ρ_cal, MAE_raw, MAE_cal
- `apply_calibration(scores, alpha, beta)` — applies linear transform, clips to [0,1]
- `load_or_fit_calibration(model, out_dir)` — per-judge, per-task calibration from EES; caches to JSON

## benchmark/run_baselines.py
Standalone baseline comparison script for Table 3 of the paper:
- Reads Phase 3 datapoints (with `benchmark_native_score`) + Phase 4 responses
- Computes BERTScore-F1 and single-model G-Eval (GPT-4o, Claude-3.5-Sonnet)
- Writes `baselines.csv` with Spearman ρ per method per task
- Usage: `python -m benchmark.run_baselines --run <path> --out paper/tables --max-pairs 200`

## Paper experiment cost estimate (paper_benchmarks.yaml)
See `paper/cost_estimate.md` for full breakdown. Summary:

| Scenario | Total cost |
|----------|-----------|
| No batch API (current config) | ~$661 |
| With batch API (50% off OpenAI+Anthropic) | ~$331 |
| Replace claude-opus-4-6 judge → claude-3-5-haiku | ~$191 |
| **Recommended: haiku judge + batch API** | **~$95** |

**Cost driver:** claude-opus-4-6 as judge = 75% of total cost.

## Resume / continue feature
`coeval run --config X.yaml --continue` restarts in-place:
- Reads `phases_completed` from meta.json, skips done phases
- Phases 1-2: Keep mode; Phases 3-5: Extend mode
- V-11 suppressed; V-14 requires existing meta.json

## Probe configuration
`probe_mode`: `full` | `resume` | `disable`
`probe_on_fail`: `abort` | `warn`
Probe writes `probe_results.json` to experiment folder.

## Validation rules
V-01 through V-17. VALID_INTERFACES includes all 9 interfaces (including `benchmark`).

## Tests
Run: `pytest experiments/tests/ analysis/tests/ -v` from `E:\Projects\CoEval\main\`
**483 experiments/tests passing** (as of 2026-03-02)
- analysis/tests/test_reports_playwright.py: 55 Playwright tests covering all 8 HTML reports

## Known model limitations
- `qwen2p5-0b5` as JUDGE: produces empty JSON → keep as student only
- `smollm2-1b7` as TEACHER (Phase 3): generates wrong JSON keys sometimes
- HF judge `max_new_tokens`: must be >=256

## HTML report bug fixes (as of 2026-03-01)
- `analysis/reports/html_base.py`: Fixed `\n\r` → `\\n\\r` escape sequences
- `analysis/reports/judge_report.py`: Fixed `!== null` → `!= null` undefined guard

## Paper status (as of 2026-03-02)
- All 7 sections written: abstract, intro, related work, methodology, results, limitations, conclusion
- Ethics statement and appendix complete
- 8 figures generated in `paper/figures/`
- ALL NUMBERS IN paper/04_results.md ARE FICTIONAL PLACEHOLDERS
- Paper gap fixes committed: G1 (RAR), G3 (token_count), G4 (calibration), G5 (baselines script), G8 (surface bias)
- Remaining gaps (deferred): G2 (positional swap), G6 (actual cost tracking), G7 (pass@k — skip)
