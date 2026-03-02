# examples/ — Example Experiment Configs and Notebooks

This directory contains example experiment configurations and supporting files that demonstrate typical CoEval usage patterns.

## Contents

| File | Description |
|------|-------------|
| [local_smoke_test.yaml](local_smoke_test.yaml) | Minimal single-model config for verifying a local installation without real API costs |

## Usage

Run any YAML config with:

```bash
coeval run --config examples/<config>.yaml
```

Estimate the cost before running:

```bash
coeval plan --config examples/<config>.yaml
```

## Related

- [`benchmark/`](../../Runs/) — production benchmark configs (`medium_benchmark.yaml`, `mixed.yaml`, `paper_dual_track.yaml`)
- [`docs/README/06-running.md`](../README/06-running.md) — full guide to writing experiment configs
- [`docs/tutorial.md`](../tutorial.md) — end-to-end walkthrough
