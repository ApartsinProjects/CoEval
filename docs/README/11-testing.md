# Testing

[← Architecture](10-architecture.md) · [Repository →](12-repository.md)

---

CoEval ships with a comprehensive test suite covering config validation, all 15 model interfaces, cost estimation, resume logic, CLI dispatch, and all eight HTML report types.

## Running the Tests

```bash
# Full test suite (from project root)
pytest experiments/tests/ analysis/tests/ -v

# Experiments package only
pytest experiments/tests/ -v

# Analysis package only
pytest analysis/tests/ -v

# Specific test area
pytest experiments/tests/ -k probe -v         # probe + estimator
pytest experiments/tests/ -k config -v        # config validation
pytest experiments/tests/ -k command -v       # CLI commands
pytest experiments/tests/ -k provider -v      # model interfaces

# HTML report Playwright tests (requires Playwright install)
playwright install chromium
pytest analysis/tests/test_reports_playwright.py -v
```

## Test Coverage

### `experiments/tests/` — 557 unit tests

| Test file | Coverage area |
|-----------|---------------|
| `test_config.py` | YAML loading, all validation rules V-01–V-17, dataclass fields |
| `test_probe_and_estimator.py` | Model probe (all interfaces), cost estimation, batch discounts, quota |
| `test_new_providers.py` | Azure OpenAI, Azure AI, Bedrock, Vertex AI, Groq, DeepSeek, Mistral, DeepInfra, Cerebras |
| `test_commands.py` | CLI dispatch, all 11 subcommands, exit codes, flag handling |
| `test_auto_interface_and_pricing.py` | Auto-routing, PRICE_TABLE lookups, provider-specific pricing |
| `test_resume_continue.py` | `--continue`, `--resume`, phase mode logic, meta.json state |
| `test_batch_runners.py` | Batch job submission, polling, result assembly |
| `test_label_eval.py` | Judge-free exact-match evaluation for classification tasks |

### `analysis/tests/` — 55 Playwright integration tests

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
def _no_default_keys_file(monkeypatch):
    """Prevent tests from reading ~/.coeval/keys.yaml or project keys.yaml."""
    monkeypatch.setenv('COEVAL_KEYS_FILE', '/dev/null')
```

API calls in probe and interface tests are mocked at the SDK level — no real API calls are made during testing.

## Continuous Integration

The test suite is designed to run in any CI environment with Python ≥ 3.10:

```yaml
# Example GitHub Actions step
- name: Run tests
  run: |
    pip install -e ".[huggingface,parquet]"
    pip install pytest playwright
    playwright install chromium
    pytest experiments/tests/ analysis/tests/ -v --tb=short
```

Expected: **557 tests passing** in `experiments/tests/`, plus analysis tests.

---

## Frequently Asked Questions

**Q: How do I run the full test suite?**
A: From the project root, run `pytest experiments/tests/ analysis/tests/ -v`. This runs all 557 unit tests plus the analysis tests. The Playwright HTML report tests require a separate `playwright install chromium` step and are in `analysis/tests/test_reports_playwright.py`.

**Q: Do the tests make real API calls to provider endpoints?**
A: No. All API calls in probe and interface tests are mocked at the SDK level. Credential-sensitive tests use an autouse `monkeypatch` fixture that sets `COEVAL_KEYS_FILE` to `/dev/null`, preventing any interaction with real key files at `~/.coeval/keys.yaml` or the project root.

**Q: How do I run only the tests for a specific area like config validation or CLI commands?**
A: Use pytest's `-k` flag to filter by keyword. For example: `pytest experiments/tests/ -k config -v` for config validation tests, `pytest experiments/tests/ -k command -v` for CLI dispatch tests, `pytest experiments/tests/ -k probe -v` for probe and estimator tests, and `pytest experiments/tests/ -k provider -v` for model interface tests.

**Q: What do the Playwright tests actually verify?**
A: The 55 Playwright integration tests in `analysis/tests/test_reports_playwright.py` launch a headless Chromium browser and exercise all eight HTML report types end-to-end. They verify that reports render without JavaScript errors, interactive filters and sort controls work, CSV export buttons produce valid output, chart elements are present and labeled, and score tables match expected aggregations.

**Q: How do I set up CoEval for CI (e.g., GitHub Actions)?**
A: Install with `pip install -e ".[huggingface,parquet]"`, add `pip install pytest playwright`, run `playwright install chromium`, then execute `pytest experiments/tests/ analysis/tests/ -v --tb=short`. The test suite requires Python >= 3.10 and no network access to provider APIs, making it safe for standard CI runners.

---

[← Architecture](10-architecture.md) · [Repository →](12-repository.md)
