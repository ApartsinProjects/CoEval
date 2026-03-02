# Tests/

Test suites for the CoEval project. Uses `pytest` with `--import-mode=importlib`.

## Structure

```
Tests/
├── runner/                         # Unit and integration tests for Code/runner
│   ├── test_config.py              # Config loading and validation (V-01 … V-17)
│   ├── test_storage.py             # Storage I/O
│   ├── test_phases.py              # Phase 1–5 logic
│   ├── test_batch_runners.py       # Batch API runners (OpenAI, Anthropic, …)
│   ├── test_label_eval.py          # LabelEvaluator
│   ├── test_auto_interface_and_pricing.py  # interface: auto, cost estimator
│   └── ...
│
├── benchmark/                      # Tests for Public/benchmark utilities
│   └── test_compute_scores.py
│
├── analyzer/                       # Playwright integration tests for HTML reports
│   ├── test_reports_playwright.py  # Launches Chromium to verify rendered output
│   └── README.md
│
└── test_structural_integrity.py    # Verifies directory layout, imports, config paths
```

## Running tests

```bash
# All tests (excludes Playwright by default — see pyproject.toml addopts)
pytest

# Specific suites
pytest Tests/runner -v
pytest Tests/benchmark -v
pytest Tests/runner Tests/benchmark -v --tb=short

# Playwright integration tests (requires: playwright install chromium)
pytest Tests/analyzer/test_reports_playwright.py -v

# Single test file
pytest Tests/runner/test_config.py -v

# Memory-safe run with limit
python scripts/run_tests_safe.py Tests/runner Tests/benchmark -q --limit 2048
```

## Key conventions

- **No `__init__.py`** in any test directory — prevents double module loading and memory explosion on Windows.
- `--import-mode=importlib` is set in `pyproject.toml` so test modules are discovered without packages.
- Root `conftest.py` applies an autouse `gc.collect()` after every test (prevents MagicMock reference-cycle leaks).
- Playwright tests are excluded from the default run via `addopts = "--ignore=Tests/analyzer/..."` in `pyproject.toml`.

## Coverage areas

| Test file | What it covers |
|---|---|
| `test_config.py` | YAML parsing, 17 config validations (V-01 … V-17) |
| `test_storage.py` | Phase file read/write, JSONL atomic writes, meta.json |
| `test_phases.py` | Phase 1–5 orchestration, mock LLM calls |
| `test_batch_runners.py` | OpenAI, Anthropic, Gemini, Azure, Bedrock, Vertex, Mistral batch flows |
| `test_label_eval.py` | Exact-match and custom match_fn label evaluation |
| `test_auto_interface_and_pricing.py` | interface: auto routing, cost estimation formulas |
| `test_structural_integrity.py` | Directory layout, import paths, YAML storage_folder values |
| `test_reports_playwright.py` | HTML report rendering in real browser |

## Related

- [`docs/README/11-testing.md`](../docs/README/11-testing.md) — testing guide
- [`conftest.py`](../conftest.py) — root pytest configuration
- [`pyproject.toml`](../pyproject.toml) — test paths and options
