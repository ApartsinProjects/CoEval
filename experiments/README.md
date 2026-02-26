# experiments/ — Evaluation Experiment Runner (EER)

This package implements the **EER pipeline** (`coeval run`): it reads a YAML config,
orchestrates the 5-phase evaluation pipeline, and writes results to an
**Experiment Storage Set (EES)** on disk.

---

## Package Contents

```
experiments/
├── cli.py              ← `coeval run` + `coeval analyze` CLI entry point
├── config.py           ← YAML loading, ExperimentConfig dataclasses, validation V-01..V-11
├── logger.py           ← RunLogger: timestamped output to file and console
├── prompts.py          ← Canonical prompt templates and resolution logic
├── runner.py           ← Pipeline orchestrator: iterates phases, manages pool/storage/logger
├── storage.py          ← ExperimentStorage: all filesystem I/O for the EES
│
├── interfaces/         ← Model backends
│   ├── base.py         ← Abstract ModelInterface (generate method contract)
│   ├── openai_iface.py ← OpenAI Chat Completions (retry, quota, role overrides)
│   ├── huggingface_iface.py  ← HuggingFace transformers.pipeline backend
│   └── pool.py         ← ModelPool: lazy-loads and caches one interface per (model, role)
│
├── phases/             ← 5-phase pipeline implementations
│   ├── utils.py        ← Shared helpers: JSON extraction, LLM call wrappers, QuotaTracker
│   ├── phase1.py       ← Attribute mapping (static or LLM-generated)
│   ├── phase2.py       ← Rubric mapping (static, auto, or extend)
│   ├── phase3.py       ← Data generation — teachers produce (prompt, response) pairs
│   ├── phase4.py       ← Response collection — students answer each prompt
│   └── phase5.py       ← Evaluation — judges score student responses
│
├── configs/            ← Example YAML experiment configurations
├── scripts/            ← Research and utility scripts
├── tests/              ← Unit tests (run with: python -m pytest experiments/tests/)
└── docs/               ← User manual + COEVAL-SPEC-001
```

---

## The 5-Phase Pipeline

```
Phase 1  attribute_mapping    → attributes/  (per-task attribute catalogues)
Phase 2  rubric_mapping       → rubric/      (per-task evaluation rubrics)
Phase 3  data_generation      → datapoints/  (teacher-generated prompt+response pairs)
Phase 4  response_collection  → responses/   (student answers to each prompt)
Phase 5  evaluation           → evaluations/ (judge scores per student response)
```

Each phase appends to its folder in the EES. Interrupted runs can be resumed;
completed phases can be kept or extended.

---

## Key Classes

| Class | Module | Role |
|-------|--------|------|
| `ExperimentConfig` | `config.py` | Top-level config dataclass (models, tasks, experiment) |
| `ModelConfig` | `config.py` | Per-model config: interface, parameters, roles, role_parameters |
| `TaskConfig` | `config.py` | Per-task config: attributes, rubric, sampling, prompt_library |
| `ExperimentStorage` | `storage.py` | All EES read/write: datapoints, responses, evaluations, metadata |
| `RunLogger` | `logger.py` | Timestamped log to `experiment.log` + console |
| `ModelPool` | `interfaces/pool.py` | Lazy-loads and caches interfaces; applies role_parameters |
| `ModelInterface` | `interfaces/base.py` | Abstract base: `generate(prompt) -> str` |
| `QuotaTracker` | `phases/utils.py` | Enforces per-model `max_calls` quotas |

---

## Supported Model Backends

| Interface name | Class | When to use |
|----------------|-------|-------------|
| `openai` | `OpenAIInterface` | GPT-4o-mini, GPT-3.5-turbo, fine-tuned models |
| `huggingface` | `HuggingFaceInterface` | Any model on the HF Hub via `transformers.pipeline` |

---

## Quick Commands

```bash
# Validate config (no LLM calls)
coeval run --config experiments/configs/local_smoke_test.yaml --dry-run

# Full run
coeval run --config experiments/configs/local_smoke_test.yaml

# Resume an interrupted run
coeval run --config experiments/configs/local_smoke_test.yaml --resume local-smoke-test-v2

# Run tests
python -m pytest experiments/tests/ -v
```

---

## Documentation

| Document | Description |
|----------|-------------|
| `docs/running_experiments.md` | **User manual** — config reference, phase modes, use-case examples, FAQ |
| `docs/spec_claude.md` | **COEVAL-SPEC-001** — formal EER specification |
| `configs/` | Example YAML configurations with inline comments |
| `../../docs/developer_guide.md` | Full developer guide covering both EER and EEA |
