# Testing

[← Repository Layout](12-repository-layout.md) · [Documentation →](14-documentation.md)

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

[← Repository Layout](12-repository-layout.md) · [Documentation →](14-documentation.md)
