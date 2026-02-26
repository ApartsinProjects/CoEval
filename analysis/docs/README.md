# Analysis Documentation Index

This folder contains documentation for the CoEval Evaluation Experiment Analyzer (EEA).

## Files

### running_analysis.md — User Manual
Operator-facing guide for running `coeval analyze`. Covers:
- All 11 subcommands and what each report shows
- Robust filtering options (`--judge-selection`, `--agreement-metric`, `--agreement-threshold`, `--teacher-score-formula`)
- Output file formats: HTML (self-contained folders), Excel workbook, JSONL, Parquet
- Analyzing in-progress experiments (`--partial-ok`)
- Use-case examples: single report, all-at-once, exporting benchmark data
- Frequently asked questions

### spec_phase2_claude.md — COEVAL-SPEC-002
Formal specification for the EEA. Covers:
- All 11 EEA subcommands and their output formats
- The Experiment Storage Set (EES) input format and directory layout
- Model classification rules (teacher / student / judge roles)
- Agreement metrics: SPA, WPA, Cohen's kappa
- Teacher scoring formulas (v1, s2, r3)
- Robust filtering algorithm (J\*, T\*, consistency threshold)

## See Also

- [docs/developer_guide.md](../../docs/developer_guide.md) — full developer reference
- [analysis/tests/](../tests/) — unit tests for the EEA
- [analysis/samples/](../samples/) — sample EES folders used as test fixtures
