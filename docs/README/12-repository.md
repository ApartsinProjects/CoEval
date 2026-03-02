# Repository Layout

[← Testing](11-testing.md) · [Documentation →](13-documentation.md)

---

```
CoEval/
│
├── experiments/                      # Core pipeline package (experiments.* namespace)
│   │
│   ├── cli.py                        # Entry point: coeval <subcommand>
│   ├── runner.py                     # Pipeline orchestrator — 5 phases, probe, estimation
│   ├── config.py                     # Config loading & validation (V-01–V-17)
│   ├── storage.py                    # All filesystem I/O (EES — experiment storage)
│   ├── logger.py                     # Structured logging (file + console)
│   ├── label_eval.py                 # Judge-free label accuracy (classification tasks)
│   ├── prompts.py                    # Canonical prompt templates for all phases
│   │
│   ├── phases/
│   │   ├── phase1.py                 # Attribute mapping
│   │   ├── phase2.py                 # Rubric mapping
│   │   ├── phase3.py                 # Data generation (teacher → datapoints)
│   │   ├── phase4.py                 # Response collection (student → responses)
│   │   └── phase5.py                 # Evaluation (judge → scores)
│   │
│   ├── interfaces/
│   │   ├── pool.py                   # ModelPool factory + VRAM management
│   │   ├── registry.py               # Key file loading, model listing, auto-routing
│   │   ├── probe.py                  # Model availability probe (all 15 interfaces)
│   │   ├── cost_estimator.py         # Cost/time estimation (PRICE_TABLE + heuristics)
│   │   ├── openai_iface.py           # OpenAI + Batch API
│   │   ├── anthropic_iface.py        # Anthropic + Message Batches API
│   │   ├── gemini_iface.py           # Google Gemini + Batch API
│   │   ├── huggingface_iface.py      # HuggingFace local inference
│   │   ├── azure_openai_iface.py     # Azure OpenAI
│   │   ├── azure_ai_iface.py         # Azure AI Foundry / GitHub Models
│   │   ├── bedrock_iface.py          # AWS Bedrock (native key + IAM)
│   │   ├── vertex_iface.py           # Google Vertex AI
│   │   ├── openrouter_iface.py       # OpenRouter
│   │   └── openai_compat_iface.py    # Groq, DeepSeek, Mistral, DeepInfra, Cerebras
│   │
│   ├── commands/
│   │   ├── probe_cmd.py              # coeval probe
│   │   ├── plan_cmd.py               # coeval plan
│   │   ├── status_cmd.py             # coeval status
│   │   ├── repair_cmd.py             # coeval repair
│   │   ├── describe_cmd.py           # coeval describe (HTML config summary)
│   │   ├── wizard_cmd.py             # coeval wizard (interactive config builder)
│   │   ├── generate_cmd.py           # coeval generate (materialize auto placeholders)
│   │   ├── models_cmd.py             # coeval models (list provider models)
│   │   ├── ingest_cmd.py             # coeval ingest (benchmark dataset ingestion)
│   │   └── analyze_cmd.py            # coeval analyze (report generation)
│   │
│   └── tests/                        # 557 unit tests (pytest)
│       ├── test_config.py            # Config validation V-01–V-17
│       ├── test_probe_and_estimator.py  # Probe + cost estimation
│       ├── test_new_providers.py     # Azure, Bedrock, Vertex, new compat providers
│       ├── test_commands.py          # CLI dispatch and command integration
│       ├── test_auto_interface_and_pricing.py  # Auto-routing, pricing table
│       └── ...
│
├── analysis/                         # Analysis & reporting package (analysis.* namespace)
│   ├── main.py                       # analyze command entry point
│   ├── loader.py                     # Run folder data loader (JSONL → DataFrames)
│   ├── metrics.py                    # Agreement (ρ, τ), differentiation, reliability
│   ├── calibration.py                # Judge calibration (OLS linear fit α, β)
│   ├── paper_tables.py               # Publication-ready LaTeX/CSV tables
│   │
│   ├── reports/                      # HTML report generators
│   │   ├── html_base.py              # Shared HTML utilities and JS helpers
│   │   ├── score_distribution.py
│   │   ├── teacher_report.py
│   │   ├── judge_report.py
│   │   ├── student_report.py
│   │   ├── interaction_matrix.py
│   │   ├── judge_consistency.py
│   │   ├── coverage_summary.py
│   │   ├── summary_report.py
│   │   ├── robust_summary.py
│   │   └── export_benchmark.py
│   │
│   └── tests/
│       ├── test_reports_playwright.py  # 55 Playwright integration tests
│       └── ...
│
├── benchmark/                        # Benchmark configs and dataset tooling
│   ├── mixed.yaml                    # Quick-start: real datasets + OpenAI (~$0.02)
│   ├── paper_dual_track.yaml         # Paper-scale: 14 models × 4 tasks
│   ├── education.yaml                # Education domain benchmark config
│   ├── setup_mixed.py                # Ingest XSum / CodeSearchNet / AESLC / WikiTQ
│   ├── setup_education.py            # One-time ingestion for ARC-Challenge, RACE, SciQ
│   ├── education_description.html    # Generated planning HTML for the education benchmark
│   ├── provider_pricing.yaml         # Auto-routing table + price table per model
│   │
│   ├── loaders/
│   │   ├── xsum.py                   # BBC news summaries (HuggingFace datasets)
│   │   ├── aeslc.py                  # Email subject lines
│   │   ├── codesearchnet.py          # Python code + docstrings
│   │   ├── wikitablequestions.py     # Wikipedia table QA
│   │   ├── arc_challenge.py          # ARC-Challenge loader
│   │   ├── race.py                   # RACE reading comprehension loader
│   │   └── sciq.py                   # SciQ science questions loader
│   │
│   ├── configs/
│   │   ├── arc_challenge_attribute_map.yaml
│   │   ├── race_attribute_map.yaml
│   │   └── sciq_attribute_map.yaml
│   │
│   └── runs/                         # Experiment output folders (git-ignored)
│
├── docs/
│   ├── README/                       # Section-by-section README (this folder)
│   │   ├── 01-overview.md            # Problem space, solution, features
│   │   ├── 02-installation.md        # Requirements, install, extras, SDKs
│   │   ├── 03-quick-start.md         # Three quick-start paths + workflow
│   │   ├── 04-configuration.md       # Models, tasks, sampling, rubric, examples
│   │   ├── 05-providers.md           # All 15 interfaces, pricing, batch, key file
│   │   ├── 06-running.md             # Pipeline phases, modes, cost, quotas, use cases
│   │   ├── 07-benchmarks.md          # Pre-ingested datasets, ingest, reproduce results
│   │   ├── 08-reports.md             # All 11 report types, metrics, API, paper tables
│   │   ├── 09-recovery.md            # Checkpointing, --continue, repair workflow
│   │   ├── 10-architecture.md        # Five-phase pipeline, role assignment, storage
│   │   ├── 11-testing.md             # Running tests, coverage areas, CI setup
│   │   ├── 12-repository.md          # Annotated directory tree, key file index
│   │   └── 13-documentation.md       # Documentation index
│   │
│   ├── cli_reference.md              # Complete CLI flag reference
│   ├── tutorial.md                   # Step-by-step tutorial
│   └── developer_guide.md            # Extending CoEval (new interfaces, phases, reports)
│
├── examples/
│   └── local_smoke_test.yaml         # 5 HuggingFace models, 2 tasks, no cloud APIs
│
├── samples/                          # Example outputs and analysis artefacts
│   ├── analysis/                     # Sample report outputs
│   └── eval_runs/                    # Sample experiment folders
│
├── README.md                         # Project hub and navigation
└── pyproject.toml                    # Package metadata and dependencies
```

## Key File Index

| File | Purpose |
|------|---------|
| `experiments/runner.py` | Top-level pipeline orchestrator; calls all five phases |
| `experiments/config.py` | YAML loading, dataclasses, validation rules V-01–V-17 |
| `experiments/storage.py` | All filesystem read/write; JSONL and JSON helpers |
| `experiments/interfaces/pool.py` | ModelPool: instantiates the right interface class per model |
| `experiments/interfaces/registry.py` | Credential resolution, auto-routing, model listing |
| `experiments/interfaces/probe.py` | Availability probe for all 15 interfaces |
| `experiments/interfaces/cost_estimator.py` | PRICE_TABLE, batch discounts, token heuristics |
| `benchmark/provider_pricing.yaml` | Auto-routing rules and per-model price table |
| `analysis/metrics.py` | Spearman ρ, Kendall τ, ACR, PFR, differentiation score |
| `analysis/calibration.py` | OLS linear calibration (α, β) for judge score correction |

---

[← Testing](11-testing.md) · [Documentation →](13-documentation.md)
