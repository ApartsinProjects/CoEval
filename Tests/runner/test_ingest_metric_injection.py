"""
Tests for metric factor auto-injection during ``coeval ingest``.

Covers:
- ``_inject_metric_factor()`` — rubric augmentation
- ``_patch_config()`` — metric judge model auto-addition
- ``BenchmarkAdapter.benchmark_metric`` — base class property
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Iterator
from unittest.mock import MagicMock

import pytest

from runner.commands.ingest_cmd import _inject_metric_factor, _patch_config
from runner.benchmarks.base import BenchmarkAdapter, BenchmarkItem


# ---------------------------------------------------------------------------
# Helpers — lightweight adapter stubs
# ---------------------------------------------------------------------------

class _StubAdapter(BenchmarkAdapter):
    """Minimal adapter for testing.  Overrides only what's required."""

    name = 'stub'
    description = 'Stub benchmark for testing'
    task_name = 'stub_task'
    output_description = 'A stub output'
    homepage = 'https://example.com/stub'

    def load(self, data_dir: Path, split: str = 'test') -> Iterator[BenchmarkItem]:
        yield BenchmarkItem(id='s-001', prompt='Hello', reference_answer='World')

    def get_rubric(self) -> dict[str, str]:
        return {'quality': 'How good is the response'}


class _BertScoreAdapter(_StubAdapter):
    """Adapter that declares bertscore as its benchmark metric."""
    name = 'stub_bertscore'
    benchmark_metric = 'bertscore'


class _BleuAdapter(_StubAdapter):
    """Adapter that declares bleu as its benchmark metric."""
    name = 'stub_bleu'
    benchmark_metric = 'bleu'


class _ExactMatchAdapter(_StubAdapter):
    """Adapter that declares exact_match as its benchmark metric."""
    name = 'stub_em'
    benchmark_metric = 'exact_match'


class _BadMetricAdapter(_StubAdapter):
    """Adapter with an unsupported benchmark_metric value."""
    name = 'stub_bad'
    benchmark_metric = 'rouge'  # not in SUPPORTED_METRICS


# ---------------------------------------------------------------------------
# BenchmarkAdapter.benchmark_metric
# ---------------------------------------------------------------------------

def test_base_adapter_benchmark_metric_default_none():
    """Base class benchmark_metric defaults to None."""
    adapter = _StubAdapter()
    assert adapter.benchmark_metric is None


def test_adapter_benchmark_metric_set():
    """Adapter subclass can set benchmark_metric."""
    adapter = _BertScoreAdapter()
    assert adapter.benchmark_metric == 'bertscore'


# ---------------------------------------------------------------------------
# _inject_metric_factor
# ---------------------------------------------------------------------------

def test_inject_metric_factor_no_metric():
    """When adapter has no benchmark_metric, rubric is returned unchanged."""
    adapter = _StubAdapter()
    rubric = {'quality': 'How good is the response'}
    result = _inject_metric_factor(rubric, adapter)
    assert result == rubric
    assert result is rubric  # same object, no copy needed


def test_inject_metric_factor_bertscore():
    """BERTScore metric factor is injected into rubric."""
    adapter = _BertScoreAdapter()
    rubric = {'quality': 'How good is the response'}
    result = _inject_metric_factor(rubric, adapter)
    assert 'bertscore_f1' in result
    assert result['bertscore_f1']['metric'] == 'bertscore'
    assert 'description' in result['bertscore_f1']
    # Original factor preserved
    assert result['quality'] == 'How good is the response'


def test_inject_metric_factor_bleu():
    """BLEU metric factor is injected into rubric."""
    adapter = _BleuAdapter()
    rubric = {'quality': 'How good is the response'}
    result = _inject_metric_factor(rubric, adapter)
    assert 'bleu4' in result
    assert result['bleu4']['metric'] == 'bleu'


def test_inject_metric_factor_exact_match():
    """exact_match metric factor is injected into rubric."""
    adapter = _ExactMatchAdapter()
    rubric = {'quality': 'How good is the response'}
    result = _inject_metric_factor(rubric, adapter)
    assert 'exact_match' in result
    assert result['exact_match']['metric'] == 'exact_match'


def test_inject_metric_factor_no_overwrite():
    """If factor_name already in rubric, existing entry is kept."""
    adapter = _BertScoreAdapter()
    existing_def = {'metric': 'bertscore', 'description': 'Custom BERTScore'}
    rubric = {'quality': 'How good', 'bertscore_f1': existing_def}
    result = _inject_metric_factor(rubric, adapter)
    assert result['bertscore_f1'] is existing_def  # same object, not replaced


def test_inject_metric_factor_does_not_mutate_original():
    """Injection creates a shallow copy; original rubric is not modified."""
    adapter = _BertScoreAdapter()
    rubric = {'quality': 'How good is the response'}
    original_keys = set(rubric.keys())
    result = _inject_metric_factor(rubric, adapter)
    # Original unchanged
    assert set(rubric.keys()) == original_keys
    # Result has the new key
    assert 'bertscore_f1' in result


def test_inject_metric_factor_bad_metric(capsys):
    """Unsupported metric prints a warning and returns rubric unchanged."""
    adapter = _BadMetricAdapter()
    rubric = {'quality': 'How good is the response'}
    result = _inject_metric_factor(rubric, adapter)
    assert result == rubric
    captured = capsys.readouterr()
    assert 'WARNING' in captured.err
    assert 'rouge' in captured.err


# ---------------------------------------------------------------------------
# _patch_config — metric judge model injection
# ---------------------------------------------------------------------------

def test_patch_config_no_metric_no_judge_model():
    """Adapter without benchmark_metric does not add a metric judge model."""
    adapter = _StubAdapter()
    cfg = {'models': [], 'tasks': []}
    result = _patch_config(cfg, adapter, 'stub', 'stub_task')
    model_names = [m['name'] for m in result['models']]
    assert 'stub' in model_names  # benchmark teacher added
    assert not any(n.startswith('metric-') for n in model_names)


def test_patch_config_with_metric_adds_judge_model():
    """Adapter with benchmark_metric auto-adds metric judge model."""
    adapter = _BertScoreAdapter()
    cfg = {'models': [], 'tasks': []}
    result = _patch_config(cfg, adapter, 'stub_bertscore', 'stub_task')
    model_names = [m['name'] for m in result['models']]
    assert 'metric-bertscore' in model_names
    # Check model definition
    metric_model = next(m for m in result['models'] if m['name'] == 'metric-bertscore')
    assert metric_model['interface'] == 'metric'
    assert metric_model['roles'] == ['judge']
    assert metric_model['parameters']['metric'] == 'bertscore'


def test_patch_config_metric_model_not_duplicated():
    """If metric model already exists in config, it is not duplicated."""
    adapter = _BertScoreAdapter()
    cfg = {
        'models': [
            {'name': 'metric-bertscore', 'interface': 'metric', 'roles': ['judge'],
             'parameters': {'metric': 'bertscore'}},
        ],
        'tasks': [],
    }
    result = _patch_config(cfg, adapter, 'stub_bertscore', 'stub_task')
    metric_models = [m for m in result['models'] if m['name'] == 'metric-bertscore']
    assert len(metric_models) == 1  # no duplicate


def test_patch_config_task_rubric_has_metric_factor():
    """When adapter has benchmark_metric, task rubric includes metric factor."""
    adapter = _BertScoreAdapter()
    cfg = {'models': [], 'tasks': []}
    result = _patch_config(cfg, adapter, 'stub_bertscore', 'stub_task')
    task = next(t for t in result['tasks'] if t['name'] == 'stub_task')
    rubric = task['rubric']
    assert 'bertscore_f1' in rubric
    assert rubric['bertscore_f1']['metric'] == 'bertscore'
    # LLM factor also present
    assert 'quality' in rubric


def test_patch_config_task_rubric_no_metric_factor():
    """When adapter has no benchmark_metric, task rubric has no metric factor."""
    adapter = _StubAdapter()
    cfg = {'models': [], 'tasks': []}
    result = _patch_config(cfg, adapter, 'stub', 'stub_task')
    task = next(t for t in result['tasks'] if t['name'] == 'stub_task')
    rubric = task['rubric']
    assert 'bertscore_f1' not in rubric
    assert 'bleu4' not in rubric
    assert 'exact_match' not in rubric
    # Only the original LLM factor
    assert rubric == {'quality': 'How good is the response'}


def test_patch_config_bleu_metric():
    """BLEU adapter adds metric-bleu model and bleu4 rubric factor."""
    adapter = _BleuAdapter()
    cfg = {'models': [], 'tasks': []}
    result = _patch_config(cfg, adapter, 'stub_bleu', 'stub_task')
    model_names = [m['name'] for m in result['models']]
    assert 'metric-bleu' in model_names
    task = next(t for t in result['tasks'] if t['name'] == 'stub_task')
    assert 'bleu4' in task['rubric']
