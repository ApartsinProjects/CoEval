# scripts/

Utility scripts for development and maintenance tasks.

## Contents

| Script | Description |
|--------|-------------|
| [`run_tests_safe.py`](run_tests_safe.py) | Memory-capped pytest wrapper — kills the test process if RSS exceeds a threshold (default: 3 GB). Uses `psutil` to monitor the full process tree. |
| [`fix_imports_dir.py`](fix_imports_dir.py) | Batch import-rename script used during the project refactoring. Replaces `from experiments.` → `from runner.` and `from analysis.` → `from analyzer.` across `.py` and `.md` files. |
| [`prompt_format_test.py`](prompt_format_test.py) | Interactive prompt formatting diagnostic — renders built-in prompt templates and prints the filled output for visual inspection. |

## Usage

```bash
# Run tests with a 2 GB memory cap
python scripts/run_tests_safe.py Tests/runner Tests/benchmark -q --limit 2048

# Run tests with default 3 GB cap
python scripts/run_tests_safe.py

# Batch rename imports in a directory
python scripts/fix_imports_dir.py Code/runner py
python scripts/fix_imports_dir.py docs md
```

## Related

- [`Tests/`](../Tests/) — test suites
