# Code/

Python source packages for the CoEval framework.

## Contents

| Directory | Package | Description |
|-----------|---------|-------------|
| [`runner/`](runner/) | `runner` | Main pipeline engine — CLI, 5-phase orchestration, 18 model interfaces, config loading, storage I/O |
| [`analyzer/`](analyzer/) | `analyzer` | Analysis and reporting — data model, metrics, 11 HTML report generators, Excel export, paper tables |

## Package layout

```
Code/
├── runner/             # pip-installed as "runner" package
│   ├── cli.py          # coeval CLI entry point
│   ├── config.py       # YAML config loader and validator
│   ├── runner.py       # 5-phase pipeline orchestrator
│   ├── storage.py      # all filesystem I/O
│   ├── label_eval.py   # judge-free label accuracy evaluation
│   ├── interfaces/     # 18 provider adapters + batch runners
│   ├── phases/         # phase1.py … phase5.py
│   └── commands/       # 9 CLI subcommand handlers
│
└── analyzer/           # pip-installed as "analyzer" package
    ├── main.py         # top-level report dispatcher
    ├── loader.py       # EESDataModel loader
    ├── metrics.py      # ICC, SPA, robust filtering
    ├── paper_tables.py # LaTeX/CSV result tables
    └── reports/        # one module per HTML report type
```

## Related

- [`Tests/runner/`](../Tests/runner/) — unit and integration tests for `runner`
- [`Tests/analyzer/`](../Tests/analyzer/) — Playwright integration tests for `analyzer`
- [`docs/developer_guide.md`](../docs/developer_guide.md) — architecture reference and extension how-tos
