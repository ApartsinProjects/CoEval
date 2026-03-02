"""Central registry of all available benchmark adapters."""
from __future__ import annotations

from .base import BenchmarkAdapter
from .adapters.mmlu import MMLUAdapter
from .adapters.hellaswag import HellaSwagAdapter
from .adapters.truthfulqa import TruthfulQAAdapter
from .adapters.humaneval import HumanEvalAdapter
from .adapters.medqa import MedQAAdapter
from .adapters.gsm8k import GSM8KAdapter

# Registry maps benchmark name → adapter instance
BENCHMARK_REGISTRY: dict[str, BenchmarkAdapter] = {
    adapter.name: adapter
    for adapter in [
        MMLUAdapter(),
        HellaSwagAdapter(),
        TruthfulQAAdapter(),
        HumanEvalAdapter(),
        MedQAAdapter(),
        GSM8KAdapter(),
    ]
}


def get_adapter(name: str) -> BenchmarkAdapter:
    """Return the adapter for *name*, raising KeyError if not found."""
    if name not in BENCHMARK_REGISTRY:
        known = ', '.join(sorted(BENCHMARK_REGISTRY))
        raise KeyError(
            f"Unknown benchmark '{name}'. Available: {known}"
        )
    return BENCHMARK_REGISTRY[name]


def list_benchmarks() -> list[dict]:
    """Return a list of dicts describing each registered benchmark."""
    return [
        {
            'name': a.name,
            'description': a.description,
            'task_name': a.task_name,
            'homepage': a.homepage,
            'label_eval': a.uses_label_eval(),
            'label_attributes': a.get_label_attributes(),
        }
        for a in BENCHMARK_REGISTRY.values()
    ]
