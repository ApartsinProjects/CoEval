"""Tests for the benchmark adapter framework and coeval ingest command."""
from __future__ import annotations

import json
import textwrap
from pathlib import Path

import pytest
import yaml


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, 'w', encoding='utf-8') as fh:
        for row in rows:
            fh.write(json.dumps(row) + '\n')


# ---------------------------------------------------------------------------
# BenchmarkItem and BenchmarkAdapter base
# ---------------------------------------------------------------------------

class TestBenchmarkBase:
    def test_benchmark_item_defaults(self):
        from experiments.benchmarks.base import BenchmarkItem
        item = BenchmarkItem(id='x', prompt='hello')
        assert item.id == 'x'
        assert item.prompt == 'hello'
        assert item.reference_answer is None
        assert item.target_attributes == {}
        assert item.metadata == {}

    def test_benchmark_item_with_attrs(self):
        from experiments.benchmarks.base import BenchmarkItem
        item = BenchmarkItem(
            id='mmlu-001',
            prompt='What is 2+2?',
            reference_answer='4',
            target_attributes={'correct_answer': 'B', 'subject': 'math'},
        )
        assert item.target_attributes['correct_answer'] == 'B'

    def test_adapter_uses_label_eval_default(self):
        from experiments.benchmarks.base import BenchmarkAdapter, BenchmarkItem

        class _Dummy(BenchmarkAdapter):
            name = 'dummy'
            def load(self, data_dir, split='test'):
                return iter([])
            def get_rubric(self):
                return {}

        d = _Dummy()
        assert not d.uses_label_eval()
        assert d.get_label_attributes() == []
        assert d.get_target_attribute_schema() == {}
        assert d.default_split == 'test'


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

class TestRegistry:
    def test_all_adapters_registered(self):
        from experiments.benchmarks.registry import BENCHMARK_REGISTRY
        expected = {'mmlu', 'hellaswag', 'truthfulqa', 'humaneval', 'medqa', 'gsm8k'}
        assert set(BENCHMARK_REGISTRY.keys()) == expected

    def test_get_adapter_returns_correct_type(self):
        from experiments.benchmarks.registry import get_adapter
        from experiments.benchmarks.adapters.mmlu import MMLUAdapter
        assert isinstance(get_adapter('mmlu'), MMLUAdapter)

    def test_get_adapter_raises_for_unknown(self):
        from experiments.benchmarks.registry import get_adapter
        with pytest.raises(KeyError, match="Unknown benchmark"):
            get_adapter('nonexistent')

    def test_list_benchmarks(self):
        from experiments.benchmarks.registry import list_benchmarks
        items = list_benchmarks()
        assert len(items) == 6
        names = [i['name'] for i in items]
        assert 'mmlu' in names
        assert 'gsm8k' in names

    def test_list_benchmarks_label_eval_info(self):
        from experiments.benchmarks.registry import list_benchmarks
        items = {i['name']: i for i in list_benchmarks()}
        assert items['mmlu']['label_eval'] is True
        assert items['truthfulqa']['label_eval'] is False


# ---------------------------------------------------------------------------
# MMLU adapter
# ---------------------------------------------------------------------------

class TestMMLUAdapter:
    def _make_data(self, tmp_path: Path, n: int = 3) -> Path:
        rows = [
            {
                'id': f'mmlu-{i:05d}',
                'question': f'What is {i}+1?',
                'choices': ['1', '2', '3', f'{i+1}'],
                'answer': 3,  # D is correct
                'subject': 'mathematics',
            }
            for i in range(n)
        ]
        p = tmp_path / 'mmlu' / 'test.jsonl'
        _write_jsonl(p, rows)
        return tmp_path

    def test_load_yields_items(self, tmp_path):
        from experiments.benchmarks.adapters.mmlu import MMLUAdapter
        data_dir = self._make_data(tmp_path)
        adapter = MMLUAdapter()
        items = list(adapter.load(data_dir))
        assert len(items) == 3

    def test_item_structure(self, tmp_path):
        from experiments.benchmarks.adapters.mmlu import MMLUAdapter
        data_dir = self._make_data(tmp_path, n=1)
        adapter = MMLUAdapter()
        item = next(adapter.load(data_dir))
        assert item.target_attributes['correct_answer'] == 'D'
        assert item.target_attributes['subject'] == 'mathematics'
        assert 'D.' in item.reference_answer
        assert 'A.' in item.prompt and 'D.' in item.prompt

    def test_label_attributes(self):
        from experiments.benchmarks.adapters.mmlu import MMLUAdapter
        assert MMLUAdapter().get_label_attributes() == ['correct_answer']

    def test_rubric_has_correctness(self):
        from experiments.benchmarks.adapters.mmlu import MMLUAdapter
        rubric = MMLUAdapter().get_rubric()
        assert 'correctness' in rubric

    def test_file_not_found(self, tmp_path):
        from experiments.benchmarks.adapters.mmlu import MMLUAdapter
        with pytest.raises(FileNotFoundError):
            list(MMLUAdapter().load(tmp_path))


# ---------------------------------------------------------------------------
# HellaSwag adapter
# ---------------------------------------------------------------------------

class TestHellaSwagAdapter:
    def _make_data(self, tmp_path: Path) -> Path:
        rows = [
            {
                'ind': str(i),
                '_idx': i,
                'activity_label': 'Cooking',
                'ctx': 'She put the pasta in the pot.',
                'endings': ['She drank coffee.', 'She boiled the water.', 'She slept.', 'She left.'],
                'label': '1',  # B is correct
            }
            for i in range(4)
        ]
        p = tmp_path / 'hellaswag' / 'validation.jsonl'
        _write_jsonl(p, rows)
        return tmp_path

    def test_load_yields_items(self, tmp_path):
        from experiments.benchmarks.adapters.hellaswag import HellaSwagAdapter
        data_dir = self._make_data(tmp_path)
        items = list(HellaSwagAdapter().load(data_dir, split='validation'))
        assert len(items) == 4

    def test_default_split_is_validation(self):
        from experiments.benchmarks.adapters.hellaswag import HellaSwagAdapter
        assert HellaSwagAdapter().default_split == 'validation'

    def test_correct_answer(self, tmp_path):
        from experiments.benchmarks.adapters.hellaswag import HellaSwagAdapter
        data_dir = self._make_data(tmp_path)
        item = next(HellaSwagAdapter().load(data_dir, split='validation'))
        assert item.target_attributes['correct_answer'] == 'B'
        assert item.target_attributes['activity'] == 'Cooking'

    def test_skip_items_without_labels(self, tmp_path):
        from experiments.benchmarks.adapters.hellaswag import HellaSwagAdapter
        rows = [
            {'ind': '0', 'activity_label': 'X', 'ctx': 'ctx',
             'endings': ['a', 'b', 'c', 'd'], 'label': ''},   # no label — skip
            {'ind': '1', 'activity_label': 'Y', 'ctx': 'ctx',
             'endings': ['a', 'b', 'c', 'd'], 'label': '2'},  # valid
        ]
        p = tmp_path / 'hellaswag' / 'validation.jsonl'
        _write_jsonl(p, rows)
        items = list(HellaSwagAdapter().load(tmp_path, split='validation'))
        assert len(items) == 1

    def test_label_attributes(self):
        from experiments.benchmarks.adapters.hellaswag import HellaSwagAdapter
        assert HellaSwagAdapter().get_label_attributes() == ['correct_answer']


# ---------------------------------------------------------------------------
# TruthfulQA adapter
# ---------------------------------------------------------------------------

class TestTruthfulQAAdapter:
    def _make_data(self, tmp_path: Path) -> Path:
        rows = [
            {
                'question': 'Is the Earth flat?',
                'best_answer': 'No, the Earth is roughly spherical.',
                'correct_answers': ['No, the Earth is roughly spherical.'],
                'incorrect_answers': ['Yes, the Earth is flat.'],
                'category': 'Science',
                'source': 'example',
            }
        ]
        p = tmp_path / 'truthfulqa' / 'validation.jsonl'
        _write_jsonl(p, rows)
        return tmp_path

    def test_load_yields_item(self, tmp_path):
        from experiments.benchmarks.adapters.truthfulqa import TruthfulQAAdapter
        data_dir = self._make_data(tmp_path)
        items = list(TruthfulQAAdapter().load(data_dir, split='validation'))
        assert len(items) == 1

    def test_item_structure(self, tmp_path):
        from experiments.benchmarks.adapters.truthfulqa import TruthfulQAAdapter
        data_dir = self._make_data(tmp_path)
        item = next(TruthfulQAAdapter().load(data_dir, split='validation'))
        assert item.target_attributes['category'] == 'Science'
        assert 'spherical' in item.reference_answer
        assert item.prompt.startswith('Answer the following question')

    def test_no_label_eval(self):
        from experiments.benchmarks.adapters.truthfulqa import TruthfulQAAdapter
        assert TruthfulQAAdapter().get_label_attributes() == []

    def test_rubric_aspects(self):
        from experiments.benchmarks.adapters.truthfulqa import TruthfulQAAdapter
        rubric = TruthfulQAAdapter().get_rubric()
        assert 'truthfulness' in rubric
        assert 'informativeness' in rubric


# ---------------------------------------------------------------------------
# HumanEval adapter
# ---------------------------------------------------------------------------

class TestHumanEvalAdapter:
    def _make_data(self, tmp_path: Path) -> Path:
        rows = [
            {
                'task_id': 'HumanEval/0',
                'prompt': 'def has_close_elements(numbers, threshold):\n    """..."""\n',
                'canonical_solution': '    for i in range(len(numbers)):\n        ...',
                'test': 'def check(candidate): assert candidate([1.0], 0.5) == False',
                'entry_point': 'has_close_elements',
            },
            {
                'task_id': 'HumanEval/60',
                'prompt': 'def do_algebra(operator, operand):\n    """..."""\n',
                'canonical_solution': '    ...',
                'test': 'assert do_algebra(["+"], [2, 3]) == 5',
                'entry_point': 'do_algebra',
            },
            {
                'task_id': 'HumanEval/120',
                'prompt': 'def maximum(arr, k):\n    """..."""\n',
                'canonical_solution': '    ...',
                'test': 'assert maximum([-3, -4, 5], 3) == [-4, -3, 5]',
                'entry_point': 'maximum',
            },
        ]
        p = tmp_path / 'humaneval' / 'test.jsonl'
        _write_jsonl(p, rows)
        return tmp_path

    def test_load_yields_items(self, tmp_path):
        from experiments.benchmarks.adapters.humaneval import HumanEvalAdapter
        data_dir = self._make_data(tmp_path)
        items = list(HumanEvalAdapter().load(data_dir))
        assert len(items) == 3

    def test_difficulty_heuristic(self, tmp_path):
        from experiments.benchmarks.adapters.humaneval import HumanEvalAdapter
        data_dir = self._make_data(tmp_path)
        items = {it.target_attributes['difficulty']: it for it in HumanEvalAdapter().load(data_dir)}
        assert 'easy' in items
        assert 'medium' in items
        assert 'hard' in items

    def test_no_label_eval(self):
        from experiments.benchmarks.adapters.humaneval import HumanEvalAdapter
        assert HumanEvalAdapter().get_label_attributes() == []

    def test_rubric_aspects(self):
        from experiments.benchmarks.adapters.humaneval import HumanEvalAdapter
        rubric = HumanEvalAdapter().get_rubric()
        assert 'correctness' in rubric
        assert 'code_quality' in rubric


# ---------------------------------------------------------------------------
# MedQA adapter
# ---------------------------------------------------------------------------

class TestMedQAAdapter:
    def _make_data(self, tmp_path: Path) -> Path:
        rows = [
            {
                'id': 'medqa-0000',
                'question': 'A patient presents with fever and cough. What is the diagnosis?',
                'options': {'A': 'Flu', 'B': 'Pneumonia', 'C': 'Cold', 'D': 'Asthma'},
                'answer': 'B',
                'meta_info': 'Internal Medicine',
            }
        ]
        p = tmp_path / 'medqa' / 'test.jsonl'
        _write_jsonl(p, rows)
        return tmp_path

    def test_load_yields_item(self, tmp_path):
        from experiments.benchmarks.adapters.medqa import MedQAAdapter
        data_dir = self._make_data(tmp_path)
        items = list(MedQAAdapter().load(data_dir))
        assert len(items) == 1

    def test_correct_answer_preserved(self, tmp_path):
        from experiments.benchmarks.adapters.medqa import MedQAAdapter
        data_dir = self._make_data(tmp_path)
        item = next(MedQAAdapter().load(data_dir))
        assert item.target_attributes['correct_answer'] == 'B'
        assert item.target_attributes['category'] == 'Internal Medicine'

    def test_label_attributes(self):
        from experiments.benchmarks.adapters.medqa import MedQAAdapter
        assert MedQAAdapter().get_label_attributes() == ['correct_answer']

    def test_skip_invalid_answer(self, tmp_path):
        from experiments.benchmarks.adapters.medqa import MedQAAdapter
        rows = [
            {'question': 'q', 'options': {}, 'answer': '', 'meta_info': 'Other'},
        ]
        p = tmp_path / 'medqa' / 'test.jsonl'
        _write_jsonl(p, rows)
        items = list(MedQAAdapter().load(tmp_path))
        assert len(items) == 0


# ---------------------------------------------------------------------------
# GSM8K adapter
# ---------------------------------------------------------------------------

class TestGSM8KAdapter:
    def _make_data(self, tmp_path: Path) -> Path:
        rows = [
            {
                'id': 'gsm8k-0000',
                'question': 'Janet has 3 apples. She buys 2 more. How many does she have?',
                'answer': 'Janet starts with 3 apples.\nShe buys 2 more.\n3 + 2 = 5.\n#### 5',
            }
        ]
        p = tmp_path / 'gsm8k' / 'test.jsonl'
        _write_jsonl(p, rows)
        return tmp_path

    def test_load_yields_item(self, tmp_path):
        from experiments.benchmarks.adapters.gsm8k import GSM8KAdapter
        data_dir = self._make_data(tmp_path)
        items = list(GSM8KAdapter().load(data_dir))
        assert len(items) == 1

    def test_numeric_answer_extracted(self, tmp_path):
        from experiments.benchmarks.adapters.gsm8k import GSM8KAdapter
        data_dir = self._make_data(tmp_path)
        item = next(GSM8KAdapter().load(data_dir))
        assert item.target_attributes.get('answer') == '5'

    def test_label_attributes(self):
        from experiments.benchmarks.adapters.gsm8k import GSM8KAdapter
        assert GSM8KAdapter().get_label_attributes() == ['answer']

    def test_schema_has_answer_key(self):
        from experiments.benchmarks.adapters.gsm8k import GSM8KAdapter
        schema = GSM8KAdapter().get_target_attribute_schema()
        assert 'answer' in schema

    def test_extract_numeric_with_commas(self):
        from experiments.benchmarks.adapters.gsm8k import _extract_numeric_answer
        assert _extract_numeric_answer('Some text. #### 1,234') == '1234'
        assert _extract_numeric_answer('No answer here') is None


# ---------------------------------------------------------------------------
# Config: benchmark interface accepted by validation
# ---------------------------------------------------------------------------

class TestConfigBenchmarkInterface:
    def _minimal_cfg(self, extra_models: list[dict] | None = None) -> dict:
        """Return a minimal raw config dict that should validate without errors."""
        models = [
            {
                'name': 'gpt-4o-mini', 'interface': 'openai',
                'roles': ['student', 'judge'],
                'parameters': {'model': 'gpt-4o-mini', 'max_tokens': 256},
            },
        ]
        if extra_models:
            models.extend(extra_models)
        return {
            'models': models,
            'tasks': [
                {
                    'name': 'mmlu',
                    'description': 'MMLU test',
                    'output_description': 'A letter.',
                    'target_attributes': {'correct_answer': ['A', 'B', 'C', 'D']},
                    'nuanced_attributes': {},
                    'sampling': {'target': [1, 1], 'nuance': [0, 0], 'total': 1},
                    'rubric': {'correctness': 'Is it correct?'},
                    'label_attributes': ['correct_answer'],
                }
            ],
            'experiment': {
                'id': 'test-exp',
                'storage_folder': '/tmp/coeval-test',
            },
        }

    def test_benchmark_interface_passes_v06(self, tmp_path):
        from experiments.config import load_config, validate_config
        cfg_dict = self._minimal_cfg(extra_models=[{
            'name': 'mmlu-benchmark',
            'interface': 'benchmark',
            'roles': ['teacher'],
            'parameters': {'description': 'MMLU'},
        }])
        # Use a real temp folder so V-11 doesn't fire
        cfg_dict['experiment']['storage_folder'] = str(tmp_path)
        cfg_path = tmp_path / 'test_config.yaml'
        with open(cfg_path, 'w') as f:
            yaml.dump(cfg_dict, f)
        cfg = load_config(str(cfg_path))
        errors = validate_config(cfg)
        interface_errors = [e for e in errors if 'benchmark' in e and 'Unknown interface' in e]
        assert not interface_errors, f"Benchmark interface rejected: {interface_errors}"

    def test_v17_label_attrs_pass_for_mmlu(self, tmp_path):
        from experiments.config import load_config, validate_config
        cfg_dict = self._minimal_cfg()
        cfg_dict['experiment']['storage_folder'] = str(tmp_path)
        cfg_path = tmp_path / 'test_config.yaml'
        with open(cfg_path, 'w') as f:
            yaml.dump(cfg_dict, f)
        cfg = load_config(str(cfg_path))
        errors = validate_config(cfg)
        v17_errors = [e for e in errors if 'label_attributes' in e]
        assert not v17_errors, f"V-17 falsely rejected: {v17_errors}"


# ---------------------------------------------------------------------------
# Ingest command
# ---------------------------------------------------------------------------

class TestIngestCmd:
    def _make_run(self, tmp_path: Path) -> Path:
        """Create a minimal EES run folder with config.yaml and meta.json."""
        run = tmp_path / 'my-exp'
        run.mkdir()
        for d in ('phase1_attributes', 'phase2_rubric', 'phase3_datapoints',
                  'phase4_responses', 'phase5_evaluations'):
            (run / d).mkdir()

        config = {
            'models': [
                {'name': 'gpt-4o-mini', 'interface': 'openai',
                 'roles': ['student', 'judge'],
                 'parameters': {'model': 'gpt-4o-mini', 'max_tokens': 256}},
            ],
            'tasks': [],
            'experiment': {'id': 'my-exp', 'storage_folder': str(tmp_path)},
        }
        with open(run / 'config.yaml', 'w') as f:
            yaml.dump(config, f)

        with open(run / 'meta.json', 'w') as f:
            json.dump({'experiment_id': 'my-exp', 'status': 'in_progress',
                       'phases_completed': [], 'phases_in_progress': []}, f)
        return run

    def _make_mmlu_data(self, tmp_path: Path) -> Path:
        data_dir = tmp_path / 'data'
        rows = [
            {'id': f'mmlu-{i:05d}', 'question': f'Q{i}?',
             'choices': ['A', 'B', 'C', f'ans-{i}'],
             'answer': 3, 'subject': 'math'}
            for i in range(5)
        ]
        _write_jsonl(data_dir / 'mmlu' / 'test.jsonl', rows)
        return data_dir

    def test_ingest_writes_datapoints(self, tmp_path):
        from experiments.commands.ingest_cmd import ingest_benchmark
        run = self._make_run(tmp_path)
        data_dir = self._make_mmlu_data(tmp_path)
        n = ingest_benchmark(run, 'mmlu', data_dir)
        assert n == 5
        dp_path = run / 'phase3_datapoints' / 'mmlu.mmlu-benchmark.datapoints.jsonl'
        assert dp_path.exists()
        lines = [json.loads(l) for l in dp_path.read_text().splitlines() if l.strip()]
        assert len(lines) == 5

    def test_ingest_datapoint_fields(self, tmp_path):
        from experiments.commands.ingest_cmd import ingest_benchmark
        run = self._make_run(tmp_path)
        data_dir = self._make_mmlu_data(tmp_path)
        ingest_benchmark(run, 'mmlu', data_dir)
        dp_path = run / 'phase3_datapoints' / 'mmlu.mmlu-benchmark.datapoints.jsonl'
        record = json.loads(dp_path.read_text().splitlines()[0])
        assert record['task_id'] == 'mmlu'
        assert record['teacher_model_id'] == 'mmlu-benchmark'
        assert 'sampled_target_attributes' in record
        assert record['sampled_target_attributes']['correct_answer'] == 'D'
        assert 'prompt' in record
        assert 'reference_response' in record
        assert 'generated_at' in record

    def test_ingest_writes_phase1_and_phase2(self, tmp_path):
        from experiments.commands.ingest_cmd import ingest_benchmark
        run = self._make_run(tmp_path)
        data_dir = self._make_mmlu_data(tmp_path)
        ingest_benchmark(run, 'mmlu', data_dir)
        assert (run / 'phase1_attributes' / 'mmlu.target_attrs.json').exists()
        assert (run / 'phase2_rubric' / 'mmlu.rubric.json').exists()

    def test_ingest_updates_config_yaml(self, tmp_path):
        from experiments.commands.ingest_cmd import ingest_benchmark
        run = self._make_run(tmp_path)
        data_dir = self._make_mmlu_data(tmp_path)
        ingest_benchmark(run, 'mmlu', data_dir)
        with open(run / 'config.yaml') as f:
            cfg = yaml.safe_load(f)
        model_names = [m['name'] for m in cfg['models']]
        assert 'mmlu-benchmark' in model_names
        task_names = [t['name'] for t in cfg['tasks']]
        assert 'mmlu' in task_names

    def test_ingest_updates_meta_json(self, tmp_path):
        from experiments.commands.ingest_cmd import ingest_benchmark
        run = self._make_run(tmp_path)
        data_dir = self._make_mmlu_data(tmp_path)
        ingest_benchmark(run, 'mmlu', data_dir)
        with open(run / 'meta.json') as f:
            meta = json.load(f)
        assert 'ingest_log' in meta
        assert len(meta['ingest_log']) == 1
        assert meta['ingest_log'][0]['benchmark'] == 'mmlu'

    def test_ingest_idempotent(self, tmp_path):
        from experiments.commands.ingest_cmd import ingest_benchmark
        run = self._make_run(tmp_path)
        data_dir = self._make_mmlu_data(tmp_path)
        n1 = ingest_benchmark(run, 'mmlu', data_dir)
        n2 = ingest_benchmark(run, 'mmlu', data_dir)
        assert n1 == 5
        assert n2 == 0  # all items already present → nothing new written
        dp_path = run / 'phase3_datapoints' / 'mmlu.mmlu-benchmark.datapoints.jsonl'
        lines = dp_path.read_text().splitlines()
        assert len(lines) == 5  # not doubled

    def test_ingest_respects_limit(self, tmp_path):
        from experiments.commands.ingest_cmd import ingest_benchmark
        run = self._make_run(tmp_path)
        data_dir = self._make_mmlu_data(tmp_path)
        n = ingest_benchmark(run, 'mmlu', data_dir, limit=3)
        assert n == 3

    def test_ingest_config_has_label_attributes(self, tmp_path):
        from experiments.commands.ingest_cmd import ingest_benchmark
        run = self._make_run(tmp_path)
        data_dir = self._make_mmlu_data(tmp_path)
        ingest_benchmark(run, 'mmlu', data_dir)
        with open(run / 'config.yaml') as f:
            cfg = yaml.safe_load(f)
        mmlu_task = next(t for t in cfg['tasks'] if t['name'] == 'mmlu')
        assert 'label_attributes' in mmlu_task
        assert 'correct_answer' in mmlu_task['label_attributes']

    def test_ingest_benchmark_interface_in_config(self, tmp_path):
        from experiments.commands.ingest_cmd import ingest_benchmark
        run = self._make_run(tmp_path)
        data_dir = self._make_mmlu_data(tmp_path)
        ingest_benchmark(run, 'mmlu', data_dir)
        with open(run / 'config.yaml') as f:
            cfg = yaml.safe_load(f)
        bm_model = next(m for m in cfg['models'] if m['name'] == 'mmlu-benchmark')
        assert bm_model['interface'] == 'benchmark'
        assert 'teacher' in bm_model['roles']


# ---------------------------------------------------------------------------
# Phase 3 skips benchmark teachers
# ---------------------------------------------------------------------------

class TestPhase3SkipsBenchmark:
    def test_benchmark_filtered_from_teachers(self):
        """Benchmark teachers must be excluded from the active teachers list in phase3."""
        from experiments.config import ModelConfig
        benchmark_teacher = ModelConfig(
            name='mmlu-benchmark',
            interface='benchmark',
            parameters={},
            roles=['teacher'],
        )
        real_teacher = ModelConfig(
            name='gpt-4o-mini',
            interface='openai',
            parameters={'model': 'gpt-4o-mini'},
            roles=['teacher'],
        )
        # Simulate the filtering logic from phase3.py
        all_teachers = [benchmark_teacher, real_teacher]
        benchmark_teachers = [t for t in all_teachers if t.interface == 'benchmark']
        teachers = [t for t in all_teachers if t.interface != 'benchmark']
        assert len(benchmark_teachers) == 1
        assert benchmark_teachers[0].name == 'mmlu-benchmark'
        assert len(teachers) == 1
        assert teachers[0].name == 'gpt-4o-mini'
