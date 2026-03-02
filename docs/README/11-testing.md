# Testing

[← Architecture](10-architecture.md) · [Repository →](12-repository.md)

---

CoEval ships with a comprehensive test suite covering config validation, all 18 model interfaces, cost estimation, resume logic, CLI dispatch, batch runners, and all eight HTML report types.

## Running the Tests

```bash
# Full test suite (from project root)
pytest Tests/ -v

# Experiments package only
pytest Tests/runner -v

# Benchmark scoring tests
pytest Tests/benchmark -v

# Analysis package only
pytest Tests/analyzer -v

# Specific test area
pytest Tests/runner -k probe -v         # probe + estimator
pytest Tests/runner -k config -v        # config validation
pytest Tests/runner -k command -v       # CLI commands
pytest Tests/runner -k provider -v      # model interfaces
pytest Tests/runner -k batch -v         # batch runners

# HTML report Playwright tests (requires Playwright install)
playwright install chromium
pytest Tests/analyzer/test_reports_playwright.py -v
```

## Test Coverage

###  — unit tests

| Test file | Coverage area |
|-----------|---------------|
| `test_config.py` | YAML loading, all validation rules V-01–V-17, dataclass fields |
| `test_probe_and_estimator.py` | Model probe (all 18 interfaces), cost estimation, batch discounts, quota |
| `test_new_providers.py` | Azure OpenAI, Azure AI, Bedrock, Vertex AI; **Cohere**, **HuggingFace Inference API**; **`MistralBatchRunner`**; `ModelPool` provider key routing |
| `test_commands.py` | CLI dispatch, all 11 subcommands, exit codes, flag handling |
| `test_auto_interface_and_pricing.py` | Auto-routing, PRICE_TABLE lookups, provider-specific pricing |
| `test_batch_runners.py` | Batch job submission, polling, result assembly (Bedrock, Vertex AI) |
| `test_label_eval.py` | Judge-free exact-match evaluation for classification tasks |
| `test_storage.py` / `test_storage_extended.py` | Filesystem I/O, EES phase storage |
| `test_prompts.py` | Prompt template rendering |
| `test_repair.py` | `coeval repair` subcommand |
| `test_phase4_phase5.py` | Phase 4 (response collection) and Phase 5 (evaluation) logic |
| `test_benchmarks.py` | Benchmark dataset loading and ingest pipeline |
| `test_utils.py` | Shared utility functions |

###  — unit tests

| Test file | Coverage area |
|-----------|---------------|
| `test_compute_scores.py` | `benchmark/compute_scores.py`: BLEU-4 scoring, exact-match, BERTScore (mocked), `_infer_benchmark`, idempotency, `--force`, dry-run, CLI `main()` |

###  — Playwright integration tests

`test_reports_playwright.py` launches a headless Chromium browser and exercises all eight HTML report types end-to-end:

- Reports render without JavaScript errors
- Interactive filters and sort controls function correctly
- CSV export buttons produce valid CSV
- Chart elements are present and labeled
- Score tables match expected aggregations

## Test Isolation

Credential-sensitive tests use autouse fixtures to prevent interaction with real key files:

```python
@pytest.fixture(autouse=True)
def _no_default_keys_file(tmp_path, monkeypatch):
    """Prevent tests from reading ~/.coeval/keys.yaml or project keys.yaml."""
    import runner.interfaces.registry as reg_mod
    monkeypatch.setattr(reg_mod, '_PROJECT_KEYS_FILE', tmp_path / '__no_keys_p__.yaml')
    monkeypatch.setattr(reg_mod, '_DEFAULT_KEYS_FILE', tmp_path / '__no_keys_h__.yaml')
    monkeypatch.delenv('COEVAL_KEYS_FILE', raising=False)
```

API calls in probe and interface tests are mocked at the SDK level — no real API calls are made during testing. Optional provider SDKs (boto3, anthropic, vertexai) are injected as `MagicMock` via `patch.dict(sys.modules, ...)`.

## Continuous Integration

The test suite is designed to run in any CI environment with Python ≥ 3.10:

```yaml
# Example GitHub Actions step
- name: Run tests
  run: |
    pip install -e ".[huggingface,parquet]"
    pip install pytest playwright
    playwright install chromium
    pytest Tests/ -v --tb=short
```

Expected: **622+ tests passing** in `Tests/runner/`, `Tests/benchmark/`, plus Playwright tests in `Tests/analyzer/`.

---

## Frequently Asked Questions

**Q: How do I run the full test suite?**
A: From the project root, run `pytest Tests/runner Tests/benchmark -v`. This runs 622+ unit tests. The Playwright tests in `Tests/analyzer/test_reports_playwright.py` require a separate `playwright install chromium` step.

**Q: Do the tests make real API calls to provider endpoints?**
A: No. All API calls in probe and interface tests are mocked at the SDK level. Credential-sensitive tests use an autouse `monkeypatch` fixture that sets `COEVAL_KEYS_FILE` to `/dev/null`, preventing any interaction with real key files at `~/.coeval/keys.yaml` or the project root.

**Q: How do I run only the tests for a specific area like config validation or CLI commands?**
A: Use pytest's `-k` flag to filter by keyword. For example: `pytest Tests/runner -k config -v` for config validation tests, `pytest Tests/runner -k command -v` for CLI dispatch tests, `pytest Tests/runner -k probe -v` for probe and estimator tests, and `pytest Tests/runner -k provider -v` for model interface tests.

**Q: What do the Playwright tests actually verify?**
A: The 55 Playwright integration tests in `Tests/analyzer/test_reports_playwright.py`. launch a headless Chromium browser and exercise all eight HTML report types end-to-end. They verify that reports render without JavaScript errors, interactive filters and sort controls work, CSV export buttons produce valid output, chart elements are present and labeled, and score tables match expected aggregations.

**Q: How do I set up CoEval for CI (e.g., GitHub Actions)?**
A: Install with `pip install -e ".[huggingface,parquet]"`, add `pip install pytest playwright`, run `playwright install chromium`, then execute `pytest Tests/runner Tests/benchmark -v --tb=short`. The test suite requires Python >= 3.10 and no network access to provider APIs, making it safe for standard CI runners.

---

[← Architecture](10-architecture.md) · [Repository →](12-repository.md)
