# Sample EES Experiment Folders

This folder contains sample Experiment Storage Set (EES) data used as fixtures by the EEA test suite.

## Contents

### run-coeval-demo-v1/ and run-coeval-demo-v2/
Pre-generated experiment output folders in the EES format. These represent complete experiment
runs produced by the CoEval EER and are the primary input consumed by the EEA and its tests.
Each folder contains model responses, judge scores, and experiment metadata as they would appear
after a real experiment finishes.

### coeval-demo-v1/ and coeval-demo-v2/
The experiment config inputs that were used to generate `run-coeval-demo-v1/` and
`run-coeval-demo-v2/` respectively. Kept here for reproducibility and to document how the
sample runs were originally produced.

## Important

Do not modify any files in this folder. These folders are test fixtures consumed by
`analysis/tests/`. Altering them will cause tests to fail or produce misleading results.

If you need custom fixture data for a new test, create a separate folder and reference it
explicitly in your test; do not overwrite or extend the existing samples.

## See Also

- [analysis/tests/README.md](../tests/README.md) — the test suite that uses these fixtures
- [analysis/docs/spec_phase2_claude.md](../docs/spec_phase2_claude.md) — EES format specification
