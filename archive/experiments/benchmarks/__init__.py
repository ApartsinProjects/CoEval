"""Standard benchmark ingestion framework for CoEval.

Provides adapters that convert public LLM benchmarks into CoEval datapoint
format so they can be injected into an existing experiment run as a virtual
'benchmark teacher' model.

Usage (programmatic):
    from experiments.benchmarks.registry import get_adapter, BENCHMARK_REGISTRY
    adapter = get_adapter('mmlu')
    for item in adapter.load(data_dir):
        print(item.prompt, item.target_attributes)

CLI:
    coeval ingest --run PATH/TO/RUN --benchmark mmlu --limit 200
"""
from experiments.benchmarks.base import BenchmarkAdapter, BenchmarkItem
from experiments.benchmarks.registry import BENCHMARK_REGISTRY, get_adapter, list_benchmarks

__all__ = ['BenchmarkAdapter', 'BenchmarkItem', 'BENCHMARK_REGISTRY', 'get_adapter', 'list_benchmarks']
