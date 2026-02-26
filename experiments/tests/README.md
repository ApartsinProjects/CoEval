# EER Unit Tests

Unit tests for the CoEval Experiment Execution Runtime (EER).

## Running the Tests

```bash
python -m pytest experiments/tests/
```

Add `-v` for verbose output or `-x` to stop on the first failure.

## Test Files

### test_config.py
Tests for config loading and validation.
- Validation rules V-01 through V-11 (required fields, type checks, mutual exclusivity, etc.)
- Role-parameter merging: how model-level settings override global defaults
- Phase mode defaults and how they interact with explicit overrides

### test_storage.py
Tests for the ExperimentStorage layer.
- Round-trip serialization: write a result, read it back, verify integrity
- Metadata lifecycle: creation, update, and finalization of experiment metadata
- Resume copy: verifying that a resumed experiment correctly inherits prior state

### test_prompts.py
Tests for prompt construction and resolution.
- Prompt resolution order (config-level vs. task-level vs. role-level)
- All 6 supported template IDs
- Variable substitution: `{task}`, `{response}`, `{rubric}`, and other placeholders

### test_utils.py
Tests for shared utility functions.
- JSON extraction from freeform model output
- `extract_prompt_response`: parsing raw completions into structured records
- Merge helpers: deep-merge logic for nested config dicts
- `QuotaTracker`: rate-limit token accounting and backoff logic

## See Also

- [experiments/docs/spec_claude.md](../docs/spec_claude.md) — formal spec (COEVAL-SPEC-001)
- [experiments/docs/running_experiments.md](../docs/running_experiments.md) — usage guide
