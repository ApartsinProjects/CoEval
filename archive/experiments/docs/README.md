# Experiments Documentation Index

This folder contains documentation for the CoEval Experiment Execution Runtime (EER).

## Files

### running_experiments.md
User manual for running CoEval experiments. Covers:
- How to write experiment config files (models, tasks, rubrics, phases)
- Supported model interfaces: `openai`, `anthropic`, `gemini`, `huggingface`
- Batch processing configuration per phase (OpenAI Batch API, Anthropic Message Batches, Gemini pseudo-batch)
- Running an experiment end-to-end
- Resuming a partially completed experiment (`resume_from` + phase modes)
- Continuing a failed experiment in-place (`--continue` flag)
- Probe modes: `full`, `resume`, `disable` — and `probe_on_fail: abort|warn`
- Cost and time estimation probe (`--estimate-only`, `estimate_cost`, `estimate_samples`)
- Label accuracy for classification/IE tasks (`label_attributes`, `LabelEvaluator`)
- Using dry-run mode to validate a config without executing API calls
- Environment variable setup and common troubleshooting
- CLI reference (all flags including `--probe`, `--probe-on-fail`, `--estimate-only`, `--continue`)
- Validation rules V-01 through V-17

### spec_claude.md — COEVAL-SPEC-001
Formal specification for the Experiment Execution Runtime (EER). Defines:
- The canonical config schema and all supported fields
- Validation rules (V-01 through V-17)
- Role-parameter merging semantics
- Phase mode defaults and override rules
- Prompt template resolution order
- Storage layout for experiment output (Experiment Storage Set format)

## See Also

- [docs/developer_guide.md](../../docs/developer_guide.md) — full developer reference
- [experiments/configs/](../configs/) — example config files
- [experiments/tests/](../tests/) — unit tests for the EER
- [experiments/label_eval.py](../label_eval.py) — label accuracy module (classification/IE)
- [experiments/interfaces/cost_estimator.py](../interfaces/cost_estimator.py) — cost/time estimation probe
- [experiments/interfaces/probe.py](../interfaces/probe.py) — model availability probe
