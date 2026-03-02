# Testing Guide

---

## Overview

CoEval's test suite covers the full pipeline — config validation, phase I/O, metrics, report generation, benchmark scoring, and structural integrity. All tests run without real API credentials; external services are mocked.

| Suite | Location | Count | What it covers |
|-------|----------|-------|----------------|
| **Runner** | `Tests/runner/` | ~197 tests | Config validation, storage, phases, CLI, providers |
| **Analyzer** | `Tests/analyzer/` | ~42 tests | Metrics, reports, loader; + 12 Playwright tests |
| **Benchmark** | `Tests/benchmark/` | ~9 tests | Compute scores (BLEU, BERTScore, exact-match) |
| **Structural** | `Tests/` (root) | ~6 test classes | Directory layout, imports, path constants |

---

## Running Tests

### Default: all tests (excluding Playwright)

```bash
pytest
```

The `pyproject.toml` sets `testpaths = ["Tests"]` and excludes the Playwright tests automatically via `addopts`.

### Individual suites

```bash
# Runner unit tests only
pytest Tests/runner -v

# Analyzer unit tests only
pytest Tests/analyzer -v --ignore=Tests/analyzer/test_reports_playwright.py

# Benchmark scoring tests
pytest Tests/benchmark -v

# Structural integrity
pytest Tests/test_structural_integrity.py -v
```

### Stop on first failure

```bash
pytest -x
```

### With coverage

```bash
pytest --cov=Code/runner --cov=Code/analyzer --cov=Public/benchmark --cov-report=term-missing
```

### Memory-safe wrapper (Windows — caps RAM at 3 GB)

```bash
python scripts/run_tests_safe.py Tests/runner Tests/benchmark -q
```

---

## Test Suites

### Runner (`Tests/runner/`)

The largest suite — 14 files covering the Experiment Execution Runtime (EER).

#### `test_config.py` — Config loading and validation

Tests all 17 validation rules (V-01 through V-17) and config-parsing helpers.

| Rule | What is tested |
|------|---------------|
| V-01 | `models` and `tasks` must be present and non-empty |
| V-02 | Model names must be unique |
| V-03 | Task names must be unique |
| V-04 | Names may only use `[a-zA-Z0-9\-_.]`; `__` is reserved |
| V-05 | Each model must have ≥ 1 valid role (`teacher`, `student`, `judge`) |
| V-06 | Interface must be one of the 18 known identifiers or `auto` |
| V-07 | At least one teacher/student/judge present as required by active phases |
| V-08 | Phase mode `Model` is only valid for `data_generation` |
| V-09 | `rubric: extend` requires `resume_from` to be set |
| V-10 | `resume_from` path must exist on disk |
| V-11 | Target run folder must not exist for new runs |
| V-12 | `generation_retries` must be ≥ 0 |
| V-13 | `batch` may only reference batchable interfaces and valid phase names |
| V-14 | `--continue` requires existing run folder and `meta.json` |
| V-15 | `probe_mode` must be `full`, `resume`, or `disable` |
| V-16 | `probe_on_fail` must be `abort` or `warn` |
| V-17 | `label_attributes` must be a subset of `target_attributes` keys |

Also covers: `role_parameters` merge, default phase modes, config field parsing (`estimate_cost`, `label_attributes`, etc.).

#### `test_storage.py` / `test_storage_extended.py` — ExperimentStorage I/O

Tests the [`Code/runner/storage.py`](../Code/runner/storage.py) layer across all five phases.

| Category | What is tested |
|----------|---------------|
| `initialize()` | Folder creation, `config.yaml`, `meta.json`, `resume_from` copy |
| Phase 1 | `write_target_attrs()`, `write_nuanced_attrs()`, read round-trip |
| Phase 2 | `write_rubric()`, `read_rubric()` |
| Phase 3 | `append_datapoints()`, `read_datapoints()`, `count_datapoints()` |
| Phase 4 | `append_responses()`, `read_responses()`, `get_responded_datapoint_ids()` |
| Phase 5 | `append_evaluations()`, `read_evaluations()`, `get_evaluated_response_ids()` |
| Error records | `append_run_error()`, `read_run_errors()`, failed-status handling |
| Lifecycle | Phase completion state, continue-in-place, metadata updates |

#### `test_prompts.py` — Prompt template resolution

Tests all 7 canonical template IDs and the resolution priority chain:

```
canonical template  →  task-level override  →  model-level override
```

Template IDs tested: `map_target_attrs`, `map_nuanced_attrs`, `autorubric`, `sample`, `test`, `evaluate_single`, `evaluate_per_factor`.

#### `test_utils.py` — Phase utilities

| Utility | What is tested |
|---------|---------------|
| `_extract_json` | 3 extraction strategies: direct parse, strip prose, balanced-brackets |
| `extract_prompt_response` | Canonical and alias key names (`prompt`/`input`, `response`/`reference_response`) |
| `merge_attr_maps` | Deep merge of attribute dicts from multiple teachers |
| `merge_rubrics` | Rubric merging with extend semantics |
| `QuotaTracker` | Per-model call budgets and ceiling enforcement |

#### `test_phase4_phase5.py` — Response collection and evaluation

Phase 4 and Phase 5 logic in all four execution modes (`New`, `Keep`, `Extend`, `Model`). Batch path disabled in all unit tests (`cfg.use_batch.return_value = False`).

#### `test_label_eval.py` — Label accuracy (classification/IE tasks)

Tests [`Code/runner/label_eval.py`](../Code/runner/label_eval.py) — judge-free exact-match scoring via `label_attributes`.

| Component | What is tested |
|-----------|---------------|
| `extract_label` | JSON key lookup, alias keys, markdown fences, short free-text (≤ 60 chars), long text → `None` |
| `extract_multilabel` | Multiple attributes, missing keys, free-text fallback |
| `LabelEvaluator.evaluate` | Perfect/partial/zero accuracy, case-insensitive, custom `match_fn` |
| `LabelEvaluator.evaluate_multilabel` | Hamming accuracy |
| Per-label P/R/F1 | Precision, recall, F1 per label value |
| Edge cases | Extraction failure (skipped), missing datapoint, missing attribute in ground truth |

#### `test_probe_and_estimator.py` — Model probe and cost estimation

The largest single test file (~95 test functions).

| Component | What is tested |
|-----------|---------------|
| `probe._models_needed` | `full` vs `resume` mode; filters models by remaining phases |
| `run_probe` | `disable` mode returns empty results; `abort`/`warn` on failure; writes `probe_results.json` |
| `get_prices` | Price table lookup; defaults for unknown models |
| `count_tokens_approx` | Length÷4 heuristic, minimum of 1 |
| `estimate_experiment_cost` | Per-phase per-model cost, batch discount (~50%), `cost_estimate.json` |
| Remaining-work estimate | `continue_in_place=True` accounting for partial completions |

#### `test_commands.py` — CLI commands

Tests `probe_cmd`, `plan_cmd`, and `status_cmd` in isolation.

| Command | What is tested |
|---------|---------------|
| `coeval probe` | Config load, probe execution, result printing, exit codes 0/1/2 |
| `coeval plan` | Cost estimation, `--continue` flag, `--estimate-samples` override |
| `coeval status` | Metadata display, phase artifact counts, batch tracking, run errors |

#### `test_batch_runners.py` — Batch API runners

Tests the AWS Bedrock and Google Vertex batch runners.

| Runner | What is tested |
|--------|---------------|
| `BedrockBatchRunner` | `add()`, `len()`, `clear()`, `_validate_config()`, `run()`; Model Invocation Jobs output parsing |
| `VertexBatchRunner` | `add()`, `len()`, `clear()`, `_validate_config()`, `run()`; Batch Prediction Jobs output parsing |
| Factory | `create_batch_runner()` dispatches to the correct class per interface |
| Error handling | Throttling, failed records, IAM vs. native API key auth |

External libraries (`boto3`, `google-cloud-aiplatform`) are mocked via `sys.modules` injection.

#### `test_auto_interface_and_pricing.py` — Auto interface selection

Tests the `interface: auto` resolution logic and the `provider_pricing.yaml` lookup.

#### `test_repair.py` — Error repair

Tests strategies for recovering failed response or evaluation records in a partial run.

#### `test_benchmarks.py` — Benchmark virtual interface

Tests `interface: benchmark` — the virtual teacher that replays pre-ingested responses from JSONL without LLM calls.

#### `test_new_providers.py` — Provider integrations

Tests authentication flows and batch API behavior for newer interfaces (Azure AI, Cohere, Cerebras, etc.).

---

### Analyzer (`Tests/analyzer/`)

Tests the Experiment Evaluation Analyzer (EEA) — [`Code/analyzer/`](../Code/analyzer/).

#### `test_loader.py` — EES data loading

Tests `analyzer.loader.load_ees`: JSONL parsing, metadata extraction, model classification (teacher/student/judge), status detection (complete/partial/failed).

#### `test_metrics.py` — Evaluation metrics

| Metric | What is tested |
|--------|---------------|
| `normalize()` | Score normalization (High/Medium/Low → 1.0/0.5/0.0) |
| `compute_agreement()` | SPA, WPA, Cohen's kappa |
| `compute_student_scores()` | Composite EES score aggregation |
| `compute_judge_scores()` | Judge bias rates and calibration |
| `robust_filter()` | Removal of out-of-range, empty, malformed records |
| `kappa_label()` | Label-based kappa calculation |

#### `test_analyze_reports.py` — Report generation

Smoke-tests all 11 `coeval analyze` subcommands against fixture data. Verifies each produces output without errors and that key output keys/types are correct. Does not assert specific numeric values (report output varies with input data).

#### `test_reports_playwright.py` — HTML report rendering *(excluded by default)*

Requires a Chromium browser installation. Renders each HTML report type in a real browser and tests interactivity (tab switching, filter controls, tooltip visibility).

**How to run:**
```bash
playwright install chromium
pytest Tests/analyzer/test_reports_playwright.py -v
```

This suite is **excluded** from the default `pytest` run to avoid requiring browser dependencies in CI.

---

### Benchmark (`Tests/benchmark/`)

#### `test_compute_scores.py` — Benchmark-native metrics

Tests [`Public/benchmark/compute_scores.py`](../Public/benchmark/compute_scores.py).

| Test | What is tested |
|------|---------------|
| `_bleu4_single` | Sentence BLEU-4 with NIST smoothing |
| `_exact_match` | Case-insensitive string comparison |
| `BENCHMARK_METRIC` mapping | Default metric per dataset (xsum→bertscore, codesearchnet→bleu, etc.) |
| `_infer_benchmark` | Dataset detection from JSONL filename or record `benchmark_id` field |
| `_score_file` | End-to-end scoring: reads JSONL, fills `benchmark_native_score`, skips already-scored records |
| Idempotency | Re-running `_score_file` without `--force` leaves existing scores unchanged |
| `--dry-run` | Scores computed but file not written |
| `main()` | CLI argument parsing, exit codes |

BERTScore is mocked (requires PyTorch; tested separately in integration). BLEU is tested directly when `nltk` is available.

---

### Structural Integrity (`Tests/test_structural_integrity.py`)

Verifies the repository layout and import graph are correct after the v0.3.0 folder refactoring. Runs in seconds and catches regressions before anything else.

| Check | What is verified |
|-------|-----------------|
| Directory existence | `Code/runner/`, `Code/analyzer/`, `Public/benchmark/`, `Config/`, `Runs/`, `Tests/` all exist |
| Package imports | `runner`, `runner.cli`, `runner.config`, `analyzer`, `analyzer.loader`, `benchmark`, etc. importable |
| Path constants | `registry._PROJECT_KEYS_FILE` → `keys.yaml` at root; `cost_estimator._PRICING_YAML_PATH` → `Config/provider_pricing.yaml` |
| No `__init__.py` in test dirs | Prevents double-collection memory explosion (critical on Windows) |
| Run YAML storage paths | `storage_folder: ./Runs` in `Runs/*/` configs |
| CLI smoke test | `python -m runner.cli --help` exits 0 and lists core subcommands |

---

## Interpreting Results

### Pass / fail

A clean run looks like:
```
==================== 267 passed in 12.3s ====================
```

### Common failures and fixes

| Symptom | Likely cause | Fix |
|---------|-------------|-----|
| `ModuleNotFoundError: runner` | Package not installed | `pip install -e .` |
| `FileNotFoundError: Config/provider_pricing.yaml` | Wrong CWD or broken path constant | Run from project root; check `test_structural_integrity.py` |
| `E   ImportError: double import` | `__init__.py` added to a test dir | Remove `__init__.py` from `Tests/runner/`, `Tests/analyzer/`, `Tests/benchmark/` |
| Memory >3 GB killed | MagicMock trees not freed | `gc.collect()` after mock-heavy tests; check `conftest.py` GC fixture |
| `playwright not found` | Chromium not installed | `playwright install chromium` |
| `E   FileNotFoundError: ...meta.json` | Continue test without prior run | Use `tmp_path` and `initialize(continue_in_place=False)` |
| V-11 failure in test_config.py | Test run folder exists from previous run | Tests use `tmp_path`; check for hardcoded paths in test |

### Warning: CRLF line endings

Git will show `warning: LF will be replaced by CRLF` on Windows — this is cosmetic and does not affect test execution.

---

## CI/CD Notes

- All tests are designed to run without API credentials (all external services mocked)
- `pytest --import-mode=importlib` (set in `pyproject.toml`) prevents double-module loading
- `conftest.py` root-level GC fixture runs after every test to prevent memory accumulation on Windows
- Playwright tests should run in a separate CI job that installs `playwright install chromium`
- Recommended CI command: `pytest Tests/runner Tests/benchmark Tests/ --ignore=Tests/analyzer`

---

## See Also

- [`docs/README/11-testing.md`](README/11-testing.md) — brief testing section in the README series
- [`Tests/runner/README.md`](../Tests/runner/README.md) — per-file test descriptions for the runner suite
- [`Tests/analyzer/README.md`](../Tests/analyzer/README.md) — per-file test descriptions for the analyzer suite
- [`Tests/benchmark/README.md`](../Tests/benchmark/README.md) — benchmark scoring test details
- [`scripts/run_tests_safe.py`](../scripts/run_tests_safe.py) — memory-capped pytest wrapper
