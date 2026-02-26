# Research and Utility Scripts

This folder contains standalone research scripts used to calibrate and validate CoEval configs.
These are not part of the main pipeline; they are one-off tools and their outputs.

## Files

### prompt_format_test.py
Standalone experiment comparing 3 prompt strategies across 5 models.
- Strategies tested: `canonical`, `few_shot`, and `two_step`
- Models: 5 HuggingFace checkpoints of varying sizes
- Produces `results.json` with quality-adjusted pass rates per (model, strategy) combination
- Run independently with: `python experiments/scripts/prompt_format_test.py`

### results.json
Output of the most recent `prompt_format_test.py` run. Contains quality-adjusted pass rates
indexed by model name and prompt strategy. These numbers were used to select the default prompt
strategy and calibrate the configs in `experiments/configs/`.

### full_run.log
Full console output captured from the prompt format test run that produced the current
`results.json`. Useful for auditing which model checkpoints were loaded, how long each
inference took, and whether any errors or warnings occurred during the run.

### non_ascii.txt
A small text file containing non-ASCII characters (accented letters, Unicode punctuation, etc.).
Used as a test fixture to verify that the prompt builder and storage layer handle non-ASCII
content correctly without encoding errors.

## See Also

- [experiments/configs/README.md](../configs/README.md) — configs calibrated using these results
- [experiments/docs/running_experiments.md](../docs/running_experiments.md) — main usage guide
