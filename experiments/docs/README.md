# Experiments Documentation Index

This folder contains documentation for the CoEval Experiment Execution Runtime (EER).

## Files

### running_experiments.md
User manual for running CoEval experiments. Covers:
- How to write experiment config files (models, tasks, rubrics, phases)
- Running an experiment end-to-end
- Resuming a partially completed experiment
- Using dry-run mode to validate a config without executing API calls
- Environment variable setup and common troubleshooting

### spec_claude.md — COEVAL-SPEC-001
Formal specification for the Experiment Execution Runtime (EER). Defines:
- The canonical config schema and all supported fields
- Validation rules (V-01 through V-11)
- Role-parameter merging semantics
- Phase mode defaults and override rules
- Prompt template resolution order
- Storage layout for experiment output (Experiment Storage Set format)

## See Also

- [docs/developer_guide.md](../../docs/developer_guide.md) — full developer reference
- [experiments/configs/](../configs/) — example config files
- [experiments/tests/](../tests/) — unit tests for the EER
