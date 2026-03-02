# EEA Unit Tests

Unit tests for the CoEval Experiment Evaluation Analyzer (EEA).

## Running the Tests

```bash
python -m pytest analysis/tests/
```

Add `-v` for verbose output or `-x` to stop on the first failure.

## Test Files

### test_loader.py
Tests for loading Experiment Storage Set (EES) data from disk.
- EES directory loading: verifying correct file discovery and parsing
- Status detection: identifying complete, partial, and failed runs
- Model classification: correctly labeling models as teacher, student, or judge based on config and file layout

### test_metrics.py
Tests for evaluation metrics and scoring.
- SPA (Simple Percent Agreement): pairwise judge agreement calculation
- WPA (Weighted Percent Agreement): distance-weighted variant of SPA
- Cohen's kappa: inter-rater reliability with expected-agreement correction
- Teacher scoring formulas: aggregation of teacher-assigned scores across items
- Robust filter: handling of empty responses, malformed JSON, out-of-range scores, and other edge cases

### test_analyze_reports.py
Smoke tests for report generation.
- Exercises all 11 EEA subcommands against sample fixture data
- Verifies that each subcommand produces output without errors
- Checks output structure (keys, types) without asserting specific numeric values

## See Also

- [analysis/docs/spec_phase2_claude.md](../docs/spec_phase2_claude.md) — formal spec (COEVAL-SPEC-002)
- [analysis/samples/](../samples/) — sample EES folders used as fixture data
