# Feature Overview

[← Why CoEval](01-why-coeval.md) · [Architecture →](03-architecture.md)

---

CoEval is organized around five capability clusters that cover the full evaluation lifecycle.

## Experiment Design

- **Declarative YAML configuration** — models, tasks, roles, sampling, rubrics, and prompts in one file; no code required to launch an evaluation
- **Interactive wizard** (`coeval wizard`) — LLM-assisted config generation with conversational refinement; describe your evaluation goal in plain English
- **Auto attribute discovery** — LLMs infer relevant task dimensions from your task description; override or extend at will
- **Auto rubric generation** — build evaluation rubrics automatically from task descriptions, statically from your own criteria, or by extending an existing rubric from a prior run
- **Nuanced attribute sampling** — inject diversity dimensions (tone, domain, urgency, style) per benchmark item to eliminate distribution collapse and keep synthetic data naturalistic
- **Per-model prompt overrides** — tailor generation and evaluation instructions at model granularity without duplicating task definitions
- **`interface: auto`** — automatic cheapest-available provider selection based on your key file; no hardcoded provider choices

## Experiment Execution

- **Five-phase pipeline** — attribute mapping → rubric mapping → data generation → response collection → evaluation; each phase is independently checkpointed and resumable
- **Flexible role assignment** — any model can be teacher, student, judge, or all three simultaneously; assign role-specific temperature and token budgets per model
- **Batch API acceleration** — OpenAI, Anthropic, Gemini, and Azure OpenAI batching enabled with a single config flag; up to **50% cost reduction** on Phase 4 and Phase 5
- **Concurrent execution** — configurable worker pools per phase; HuggingFace models queued for GPU; all other interfaces run concurrently
- **Per-phase mode control** — `New` / `Keep` / `Extend` / `Model` per phase; skip phases you've already run, append only missing items, or reuse an existing model's output
- **Virtual benchmark teachers** (`interface: benchmark`) — inject pre-ingested dataset responses (XSum, CodeSearchNet, AESLC, MMLU, HumanEval, …) as Phase 3 ground truth without any LLM calls
- **Label accuracy mode** — judge-free exact-match evaluation for classification and information extraction tasks via `label_attributes`; no judge calls needed, no judge bias

## Cost Planning & Control

- **Pre-run cost estimation** (`coeval plan`) — samples 2 real API calls per model by default to measure actual latency and throughput; falls back to token-count heuristics with `--estimate-samples 0`
- **Batch discount modeling** — estimation automatically applies provider-specific batch discounts (50% for OpenAI, Anthropic, Gemini, Azure OpenAI)
- **Per-model API quota** — `quota:` block sets hard call ceilings per model; the pipeline stops cleanly at the ceiling rather than crashing mid-phase
- **`--estimate-only`** — validate config, print itemized cost table, write `cost_estimate.json`, and exit before any evaluation work starts

## Diagnostics & Control

- **Model probe** (`coeval probe`) — lightweight availability check for all 15+ interfaces using model listing endpoints; consumes no generation tokens and exits before spending a dollar
- **Progress dashboard** (`coeval status`) — live phase artifact counts, pending batch jobs, and recent log errors; add `--fetch-batches` to poll provider APIs for completion
- **Config HTML preview** (`coeval describe`) — browser-ready summary of models, tasks, rubrics, phase execution plan, prompt templates, and cost budget; shareable for team review before running
- **JSONL repair tool** (`coeval repair`) — scans for malformed records, removes corrupted phase checkpoints, and prepares for targeted re-runs with `--continue`
- **Structured logging** — configurable log level per experiment; full JSONL audit trail written per phase alongside every result

## Resume & Recovery

- **Granular checkpointing** — each JSONL record written atomically; interruption mid-phase loses at most one record
- **`--continue`** — resume any experiment from its last checkpoint; reads `phases_completed` from `meta.json`, skips done phases, and fills gaps in in-progress phases
- **`--resume EXPERIMENT_ID`** — fork phases 1–2 from an existing run; re-use attribute and rubric work across multiple student/judge variants without regenerating data
- **`--only-models`** — re-run specific models in phases 3–5 without touching others; ideal for adding a new model to an existing benchmark
- **Repair + continue workflow** — identify failed records with `coeval repair --dry-run`, apply fixes, then `--continue` fills the gaps without touching intact data

## Evaluation & Analysis

- **Multi-judge ensemble** — average scores across N judges for robust, bias-resistant evaluation; ensemble size configurable per experiment
- **Single and per-factor evaluation modes** — holistic score (one call per response) or one call per rubric dimension per response for maximum granularity
- **8 interactive HTML reports** — score distributions, teacher analysis, judge consistency, student rankings, interaction matrices, coverage summaries, calibration curves, and robust summaries
- **Excel export** — complete results in a structured workbook for downstream statistical analysis or stakeholder review
- **Calibration analysis** — linear α/β calibration fit between judge scores and benchmark ground-truth; corrects for systematic over/under-scoring
- **Agreement metrics** — Spearman ρ, Kendall τ, and inter-judge consistency (ACR); quantify how reliably models agree on relative quality
- **Paper tables** — Spearman ρ comparisons, student rankings, sampling ablation, positional bias detection, calibration effect, and cost comparison tables ready for publication
- **Benchmark score integration** — correlate LLM judge scores with BERTScore, BLEU, ROUGE, and exact-match ground-truth from real datasets

---

[← Why CoEval](01-why-coeval.md) · [Architecture →](03-architecture.md)
