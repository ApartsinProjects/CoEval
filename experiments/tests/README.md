# EER Unit Tests

Unit tests for the CoEval Experiment Execution Runtime (EER).

## Running the Tests

```bash
python -m pytest experiments/tests/
```

Add `-v` for verbose output or `-x` to stop on the first failure.

**Current test count: 404 tests** across 8 test modules.

## Test Files

### test_config.py
Tests for config loading and validation.
- Validation rules V-01 through V-17 (required fields, type checks, mutual exclusivity, etc.)
- V-15: `probe_mode` must be one of `disable`, `full`, `resume`
- V-16: `probe_on_fail` must be one of `abort`, `warn`
- V-17: `label_attributes` entries must be a subset of `target_attributes` keys (when static)
- Role-parameter merging: how model-level settings override global defaults
- Phase mode defaults and how they interact with explicit overrides
- Parsing of new experiment-level fields: `probe_mode`, `probe_on_fail`, `estimate_cost`, `estimate_samples`
- Parsing of new task-level field: `label_attributes`

### test_storage.py
Tests for the ExperimentStorage layer.
- Round-trip serialization: write a result, read it back, verify integrity
- Metadata lifecycle: creation, update, and finalization of experiment metadata
- Resume copy: verifying that a resumed experiment correctly inherits prior state
- Continue in-place: `initialize(continue_in_place=True)` reopens without clearing data
- Continue does not overwrite `meta.json` (phases_completed preserved)

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

### test_phase4_phase5.py
Tests for Phase 4 (response collection) and Phase 5 (evaluation).
- Phase 4 and 5 in New, Keep, Extend, and Model modes
- Batch path disabled in all unit tests (`cfg.use_batch.return_value = False`)
- Phase 5 Extend mode: already-evaluated responses are always skipped (regardless of new rubric factors)
- Per-phase skip logic and JSONL record counting

### test_label_eval.py *(new)*
Tests for `experiments/label_eval.py` — label accuracy for classification and IE tasks.
- `extract_label`: JSON exact key, alias key (`label`/`prediction`/`class`/`answer`), markdown fence,
  short free-text (≤60 chars), long text (returns `None`), empty text, null value, integer coercion
- `extract_multilabel`: JSON multi-key, missing keys, short free-text fallback, empty attr list
- `LabelEvaluator.evaluate`: perfect/partial/zero accuracy, case-insensitive default match,
  custom `match_fn`, extraction failure (skipped), per-label P/R/F1, missing datapoint (skipped),
  missing attribute in ground truth (skipped)
- `LabelEvaluator.evaluate_multilabel`: Hamming accuracy (perfect, partial, empty)
- `LabelEvaluator`: empty `label_attributes` raises `ValueError`
- Information-extraction scenario (`entity_type` attribute)

### test_probe_and_estimator.py *(new)*
Tests for `experiments/interfaces/probe.py` and `experiments/interfaces/cost_estimator.py`.

**Probe tests:**
- `_models_needed`: resume mode filters models by roles needed for remaining phases
- `run_probe` with `mode='disable'` returns empty results without probing
- `run_probe` writes `probe_results.json` containing mode, results, and probed model list
- `on_fail='abort'` calls `logger.error`; `on_fail='warn'` calls `logger.warning`

**Cost estimator tests:**
- `get_prices`: known models return correct prices; unknown models use defaults
- `count_tokens_approx`: length/4 heuristic, minimum of 1
- Heuristic latency/TPS fallbacks for HuggingFace and disabled sampling
- `estimate_experiment_cost`: required keys present in result, all phases accounted for,
  total cost > 0, `cost_estimate.json` written to experiment folder,
  batch mode reduces estimated cost vs. non-batch

**Validation tests (V-15 through V-17):**
- V-15: invalid `probe_mode` values are rejected; valid values pass
- V-16: invalid `probe_on_fail` values are rejected; valid values pass
- V-17: `label_attributes` referencing unknown keys fail; valid subsets pass;
  auto/complete `target_attributes` skip validation

## See Also

- [experiments/docs/spec_claude.md](../docs/spec_claude.md) — formal spec (COEVAL-SPEC-001)
- [experiments/docs/running_experiments.md](../docs/running_experiments.md) — usage guide
- [experiments/label_eval.py](../label_eval.py) — label accuracy module
- [experiments/interfaces/cost_estimator.py](../interfaces/cost_estimator.py) — cost/time estimation
- [experiments/interfaces/probe.py](../interfaces/probe.py) — model availability probe
