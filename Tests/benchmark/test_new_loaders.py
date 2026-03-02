"""Tests for MATH, MBPP, and BIG-Bench Hard benchmark loaders.

Covers:
  MATHLoader
    - _infer_subject(): type_str normalisation
    - _infer_difficulty(): level 1-5 → easy/medium/hard
    - _load_dataset(): calls load_dataset, builds item list, skips empty rows
    - _to_record(): Phase 3 JSONL schema compliance

  MBPPLoader
    - _infer_topic(): keyword-based classification
    - _infer_complexity(): char + line heuristics
    - _load_dataset(): calls load_dataset, builds item list, skips empty rows
    - _to_record(): Phase 3 JSONL schema + optional tests_block in prompt

  BigBenchHardLoader
    - _infer_difficulty(): answer-length heuristic
    - _load_dataset(): iterates 27 sub-tasks, skips unavailable tasks
    - _to_record(): Phase 3 JSONL schema

  Registry
    - all three datasets are registered in __init__.py
    - compute_scores.BENCHMARK_METRIC contains correct metric for each

All tests use mocked ``datasets.load_dataset`` so no network access occurs.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

_REQUIRED_PHASE3_KEYS = {
    "id",
    "task_id",
    "teacher_model_id",
    "sampled_target_attributes",
    "prompt",
    "reference_response",
    "generated_at",
    "benchmark_id",
    "benchmark_split",
    "benchmark_native_id",
    "benchmark_native_score",
}


def _assert_phase3_record(record: dict) -> None:
    """Assert a record has all required Phase 3 JSONL fields."""
    missing = _REQUIRED_PHASE3_KEYS - set(record.keys())
    assert not missing, f"Missing Phase 3 keys: {missing}"
    assert record["benchmark_native_score"] is None  # always null at emit time


# ---------------------------------------------------------------------------
# MATHLoader — unit tests
# ---------------------------------------------------------------------------

class TestInferSubjectMATH:
    def _fn(self):
        from benchmark.loaders.math_dataset import _infer_subject
        return _infer_subject

    def test_algebra(self):
        assert self._fn()("Algebra") == "algebra"

    def test_geometry(self):
        assert self._fn()("Geometry") == "geometry"

    def test_spaces_replaced_with_underscores(self):
        assert self._fn()("Counting & Probability") == "counting_&_probability"

    def test_empty_defaults_to_algebra(self):
        assert self._fn()("") == "algebra"

    def test_none_defaults_to_algebra(self):
        assert self._fn()(None) == "algebra"  # type: ignore[arg-type]

    def test_lowercased(self):
        result = self._fn()("Number Theory")
        assert result == result.lower()


class TestInferDifficultyMATH:
    def _fn(self):
        from benchmark.loaders.math_dataset import _infer_difficulty
        return _infer_difficulty

    def test_level_1_is_easy(self):
        assert self._fn()("Level 1") == "easy"

    def test_level_2_is_easy(self):
        assert self._fn()("Level 2") == "easy"

    def test_level_3_is_medium(self):
        assert self._fn()("Level 3") == "medium"

    def test_level_4_is_hard(self):
        assert self._fn()("Level 4") == "hard"

    def test_level_5_is_hard(self):
        assert self._fn()("Level 5") == "hard"

    def test_integer_input(self):
        assert self._fn()(1) == "easy"
        assert self._fn()(3) == "medium"
        assert self._fn()(5) == "hard"

    def test_invalid_returns_medium(self):
        assert self._fn()("Unknown") == "medium"
        assert self._fn()("") == "medium"


class TestMATHLoaderLoadDataset:
    def _make_mock_ds(self, rows: list[dict]) -> MagicMock:
        mock_ds = MagicMock()
        mock_ds.__iter__ = MagicMock(return_value=iter(rows))
        return mock_ds

    def _loader(self, **kwargs) -> Any:
        from benchmark.loaders.math_dataset import MATHLoader
        return MATHLoader(
            attribute_map={"subject": ["algebra"], "difficulty": ["easy", "medium", "hard"]},
            sample_size=100,
            split="test",
            seed=42,
            **kwargs,
        )

    def test_loads_valid_rows(self):
        rows = [
            {"problem": "What is 2+2?", "solution": "4", "level": "Level 1", "type": "Algebra"},
            {"problem": "Find x.", "solution": "x=3", "level": "Level 4", "type": "Geometry"},
        ]
        mock_ds = self._make_mock_ds(rows)
        with patch("datasets.load_dataset", return_value=mock_ds):
            loader = self._loader()
            items = loader._load_dataset()
        assert len(items) == 2
        assert items[0]["_inferred_attrs"]["difficulty"] == "easy"
        assert items[1]["_inferred_attrs"]["difficulty"] == "hard"
        assert items[0]["_inferred_attrs"]["subject"] == "algebra"

    def test_skips_empty_problem(self):
        rows = [
            {"problem": "", "solution": "4", "level": "Level 1", "type": "Algebra"},
            {"problem": "Valid.", "solution": "42", "level": "Level 2", "type": "Algebra"},
        ]
        mock_ds = self._make_mock_ds(rows)
        with patch("datasets.load_dataset", return_value=mock_ds):
            loader = self._loader()
            items = loader._load_dataset()
        assert len(items) == 1

    def test_skips_empty_solution(self):
        rows = [
            {"problem": "Question?", "solution": "", "level": "Level 1", "type": "Algebra"},
        ]
        mock_ds = self._make_mock_ds(rows)
        with patch("datasets.load_dataset", return_value=mock_ds):
            loader = self._loader()
            items = loader._load_dataset()
        assert len(items) == 0


class TestMATHLoaderToRecord:
    def _loader(self):
        from benchmark.loaders.math_dataset import MATHLoader
        return MATHLoader(attribute_map={}, sample_size=10, split="test", seed=42)

    def test_record_has_required_keys(self):
        loader = self._loader()
        item = {
            "_native_id": "42",
            "_problem": "Solve: x^2 = 4",
            "_solution": "x = ±2",
            "_inferred_attrs": {"subject": "algebra", "difficulty": "medium"},
        }
        record = loader._to_record(item, seq=1)
        _assert_phase3_record(record)

    def test_task_id_is_math_problem_solving(self):
        loader = self._loader()
        item = {
            "_native_id": "1",
            "_problem": "P",
            "_solution": "S",
            "_inferred_attrs": {"subject": "algebra", "difficulty": "easy"},
        }
        record = loader._to_record(item, seq=0)
        assert record["task_id"] == "math_problem_solving"

    def test_benchmark_id_is_math(self):
        loader = self._loader()
        item = {
            "_native_id": "1",
            "_problem": "P",
            "_solution": "S",
            "_inferred_attrs": {"subject": "geometry", "difficulty": "hard"},
        }
        record = loader._to_record(item, seq=0)
        assert record["benchmark_id"] == "math"

    def test_prompt_contains_problem(self):
        loader = self._loader()
        problem_text = "What is the square root of 144?"
        item = {
            "_native_id": "5",
            "_problem": problem_text,
            "_solution": "12",
            "_inferred_attrs": {"subject": "algebra", "difficulty": "easy"},
        }
        record = loader._to_record(item, seq=0)
        assert problem_text in record["prompt"]

    def test_reference_response_is_solution(self):
        loader = self._loader()
        item = {
            "_native_id": "99",
            "_problem": "Q",
            "_solution": "The answer is 7.",
            "_inferred_attrs": {"subject": "algebra", "difficulty": "medium"},
        }
        record = loader._to_record(item, seq=0)
        assert record["reference_response"] == "The answer is 7."


# ---------------------------------------------------------------------------
# MBPPLoader — unit tests
# ---------------------------------------------------------------------------

class TestInferTopicMBPP:
    def _fn(self):
        from benchmark.loaders.mbpp import _infer_topic
        return _infer_topic

    def test_string_keyword_detected(self):
        assert self._fn()("Write a function that reverses a string") == "string_manipulation"

    def test_list_keyword_detected(self):
        assert self._fn()("Return the largest element in a list") == "list_operations"

    def test_math_keyword_detected(self):
        assert self._fn()("Find the sum of all digits of a number") == "math_computation"

    def test_dict_keyword_detected(self):
        assert self._fn()("Merge two dicts and return a new one") == "data_structures"

    def test_general_fallback(self):
        assert self._fn()("Do something useful with the input") == "general"

    def test_case_insensitive(self):
        assert self._fn()("SORT A LIST PLEASE") == "list_operations"


class TestInferComplexityMBPP:
    def _fn(self):
        from benchmark.loaders.mbpp import _infer_complexity
        return _infer_complexity

    def test_short_text_is_simple(self):
        short_text = "Add two numbers."
        short_solution = "def f(a, b):\n    return a + b"
        assert self._fn()(short_text, short_solution) == "simple"

    def test_medium_text_is_moderate(self):
        medium_text = "x" * 150
        medium_solution = "\n".join(f"line{i}" for i in range(7))  # 7 lines
        assert self._fn()(medium_text, medium_solution) == "moderate"

    def test_long_text_is_complex(self):
        long_text = "x" * 250
        long_solution = "\n".join(f"line{i}" for i in range(15))  # 15 lines
        assert self._fn()(long_text, long_solution) == "complex"


class TestMBPPLoaderLoadDataset:
    def _make_mock_ds(self, rows: list[dict]) -> MagicMock:
        mock_ds = MagicMock()
        mock_ds.__iter__ = MagicMock(return_value=iter(rows))
        return mock_ds

    def _loader(self):
        from benchmark.loaders.mbpp import MBPPLoader
        return MBPPLoader(attribute_map={}, sample_size=100, split="test", seed=42)

    def test_loads_valid_rows(self):
        rows = [
            {
                "task_id": 1,
                "text": "Write a function to add two numbers.",
                "code": "def add(a, b):\n    return a + b",
                "test_list": ["assert add(1,2) == 3"],
            }
        ]
        mock_ds = self._make_mock_ds(rows)
        with patch("datasets.load_dataset", return_value=mock_ds):
            items = self._loader()._load_dataset()
        assert len(items) == 1
        assert items[0]["_native_id"] == "1"

    def test_skips_empty_text(self):
        rows = [
            {"task_id": 1, "text": "", "code": "def f(): pass", "test_list": []},
        ]
        mock_ds = self._make_mock_ds(rows)
        with patch("datasets.load_dataset", return_value=mock_ds):
            items = self._loader()._load_dataset()
        assert len(items) == 0

    def test_skips_empty_code(self):
        rows = [
            {"task_id": 2, "text": "Describe something.", "code": "", "test_list": []},
        ]
        mock_ds = self._make_mock_ds(rows)
        with patch("datasets.load_dataset", return_value=mock_ds):
            items = self._loader()._load_dataset()
        assert len(items) == 0

    def test_inferred_attrs_present(self):
        rows = [
            {
                "task_id": 10,
                "text": "Sort a list of numbers.",
                "code": "def f(lst):\n    return sorted(lst)",
                "test_list": [],
            }
        ]
        mock_ds = self._make_mock_ds(rows)
        with patch("datasets.load_dataset", return_value=mock_ds):
            items = self._loader()._load_dataset()
        assert "topic" in items[0]["_inferred_attrs"]
        assert "complexity" in items[0]["_inferred_attrs"]


class TestMBPPLoaderToRecord:
    def _loader(self):
        from benchmark.loaders.mbpp import MBPPLoader
        return MBPPLoader(attribute_map={}, sample_size=10, split="test", seed=42)

    def test_record_has_required_keys(self):
        loader = self._loader()
        item = {
            "_native_id": "1",
            "_description": "Add two numbers.",
            "_solution": "def add(a, b):\n    return a + b",
            "_test_list": ["assert add(1, 2) == 3"],
            "_inferred_attrs": {"topic": "math_computation", "complexity": "simple"},
        }
        record = loader._to_record(item, seq=0)
        _assert_phase3_record(record)

    def test_benchmark_id_is_mbpp(self):
        loader = self._loader()
        item = {
            "_native_id": "5",
            "_description": "Some task.",
            "_solution": "def f(): pass",
            "_test_list": [],
            "_inferred_attrs": {"topic": "general", "complexity": "simple"},
        }
        record = loader._to_record(item, seq=0)
        assert record["benchmark_id"] == "mbpp"

    def test_task_id_is_code_generation(self):
        loader = self._loader()
        item = {
            "_native_id": "5",
            "_description": "Some task.",
            "_solution": "def f(): pass",
            "_test_list": [],
            "_inferred_attrs": {"topic": "general", "complexity": "simple"},
        }
        record = loader._to_record(item, seq=0)
        assert record["task_id"] == "code_generation"

    def test_prompt_includes_description(self):
        loader = self._loader()
        desc = "Write a function that returns the factorial of n."
        item = {
            "_native_id": "7",
            "_description": desc,
            "_solution": "def f(n):\n    return 1 if n <= 1 else n * f(n-1)",
            "_test_list": ["assert f(5) == 120"],
            "_inferred_attrs": {"topic": "math_computation", "complexity": "simple"},
        }
        record = loader._to_record(item, seq=0)
        assert desc in record["prompt"]

    def test_prompt_includes_up_to_3_tests(self):
        loader = self._loader()
        tests = [f"assert f({i}) == {i}" for i in range(5)]
        item = {
            "_native_id": "8",
            "_description": "Some task.",
            "_solution": "def f(x): return x",
            "_test_list": tests,
            "_inferred_attrs": {"topic": "general", "complexity": "simple"},
        }
        record = loader._to_record(item, seq=0)
        # Only first 3 tests should appear
        assert "assert f(0) == 0" in record["prompt"]
        assert "assert f(2) == 2" in record["prompt"]
        assert "assert f(4) == 4" not in record["prompt"]

    def test_no_tests_block_when_empty(self):
        loader = self._loader()
        item = {
            "_native_id": "9",
            "_description": "No tests here.",
            "_solution": "def f(): pass",
            "_test_list": [],
            "_inferred_attrs": {"topic": "general", "complexity": "simple"},
        }
        record = loader._to_record(item, seq=0)
        assert "Example tests:" not in record["prompt"]


# ---------------------------------------------------------------------------
# BigBenchHardLoader — unit tests
# ---------------------------------------------------------------------------

class TestInferDifficultyBBH:
    def _fn(self):
        from benchmark.loaders.bigbench_hard import _infer_difficulty
        return _infer_difficulty

    def test_true_is_low(self):
        assert self._fn()("True") == "low"

    def test_false_is_low(self):
        assert self._fn()("False") == "low"

    def test_yes_is_low(self):
        assert self._fn()("yes") == "low"

    def test_no_is_low(self):
        assert self._fn()("no") == "low"

    def test_valid_is_low(self):
        assert self._fn()("valid") == "low"

    def test_invalid_is_low(self):
        assert self._fn()("invalid") == "low"

    def test_short_multi_word_is_medium(self):
        # ≤ 4 words but not in low set
        assert self._fn()("Option A") == "medium"

    def test_four_words_is_medium(self):
        assert self._fn()("the cat sat") == "medium"

    def test_long_answer_is_high(self):
        assert self._fn()("the quick brown fox jumps over the lazy dog") == "high"

    def test_empty_is_low(self):
        # Empty string lowered is "" which is not in the low set but has 0 split words
        # → should be medium (0 words ≤ 4)
        result = self._fn()("")
        assert result in ("low", "medium")


class TestBBHLoaderLoadDataset:
    def _make_mock_subtask_ds(self, rows: list[dict]) -> MagicMock:
        mock_ds = MagicMock()
        mock_ds.__iter__ = MagicMock(return_value=iter(rows))
        return mock_ds

    def _loader(self):
        from benchmark.loaders.bigbench_hard import BigBenchHardLoader
        return BigBenchHardLoader(attribute_map={}, sample_size=100, split="train", seed=42)

    def test_loads_multiple_subtasks(self):
        rows = [{"input": "Question A?", "target": "True"}]
        mock_ds = self._make_mock_subtask_ds(rows)

        with patch("datasets.load_dataset", return_value=mock_ds):
            items = self._loader()._load_dataset()

        # 27 sub-tasks × 1 row each = 27 items
        assert len(items) == 27

    def test_skips_empty_input(self):
        def side_effect(dataset, subtask, **kwargs):
            ds = MagicMock()
            if subtask == "boolean_expressions":
                ds.__iter__ = MagicMock(return_value=iter([
                    {"input": "", "target": "True"},  # skip: empty input
                    {"input": "2 > 1?", "target": "True"},
                ]))
            else:
                ds.__iter__ = MagicMock(return_value=iter([]))
            return ds

        with patch("datasets.load_dataset", side_effect=side_effect):
            items = self._loader()._load_dataset()
        # Only 1 valid row from boolean_expressions
        assert any(i["_subtask"] == "boolean_expressions" for i in items)
        total_boolean = sum(1 for i in items if i["_subtask"] == "boolean_expressions")
        assert total_boolean == 1

    def test_skips_unavailable_subtasks(self):
        call_count = 0

        def side_effect(dataset, subtask, **kwargs):
            nonlocal call_count
            call_count += 1
            if subtask in ("boolean_expressions", "causal_judgement"):
                raise Exception("Dataset not found")
            ds = MagicMock()
            ds.__iter__ = MagicMock(return_value=iter([
                {"input": "Q", "target": "A"}
            ]))
            return ds

        with patch("datasets.load_dataset", side_effect=side_effect):
            items = self._loader()._load_dataset()

        # 27 - 2 skipped = 25 tasks, 1 item each
        assert len(items) == 25

    def test_native_id_uses_subtask_and_index(self):
        def side_effect(dataset, subtask, **kwargs):
            ds = MagicMock()
            if subtask == "boolean_expressions":
                ds.__iter__ = MagicMock(return_value=iter([
                    {"input": "Q0", "target": "True"},
                    {"input": "Q1", "target": "False"},
                ]))
            else:
                ds.__iter__ = MagicMock(return_value=iter([]))
            return ds

        with patch("datasets.load_dataset", side_effect=side_effect):
            items = self._loader()._load_dataset()

        boolean_items = [i for i in items if i["_subtask"] == "boolean_expressions"]
        assert boolean_items[0]["_native_id"] == "boolean_expressions__0"
        assert boolean_items[1]["_native_id"] == "boolean_expressions__1"

    def test_inferred_attrs_have_task_type_and_difficulty(self):
        def side_effect(dataset, subtask, **kwargs):
            ds = MagicMock()
            ds.__iter__ = MagicMock(return_value=iter([
                {"input": "Q", "target": "True"}
            ]))
            return ds

        with patch("datasets.load_dataset", side_effect=side_effect):
            items = self._loader()._load_dataset()

        assert len(items) > 0
        for item in items:
            attrs = item["_inferred_attrs"]
            assert "task_type" in attrs
            assert "difficulty" in attrs
            assert attrs["task_type"] in ("logic", "reasoning", "math", "language", "knowledge")
            assert attrs["difficulty"] in ("low", "medium", "high")


class TestBBHLoaderToRecord:
    def _loader(self):
        from benchmark.loaders.bigbench_hard import BigBenchHardLoader
        return BigBenchHardLoader(attribute_map={}, sample_size=10, split="train", seed=42)

    def test_record_has_required_keys(self):
        loader = self._loader()
        item = {
            "_native_id": "boolean_expressions__0",
            "_subtask": "boolean_expressions",
            "_input": "Is ( True and False ) True or False?",
            "_target": "False",
            "_inferred_attrs": {"task_type": "logic", "difficulty": "low"},
        }
        record = loader._to_record(item, seq=0)
        _assert_phase3_record(record)

    def test_benchmark_id_is_bigbench_hard(self):
        loader = self._loader()
        item = {
            "_native_id": "causal_judgement__5",
            "_subtask": "causal_judgement",
            "_input": "Question text here.",
            "_target": "yes",
            "_inferred_attrs": {"task_type": "reasoning", "difficulty": "low"},
        }
        record = loader._to_record(item, seq=0)
        assert record["benchmark_id"] == "bigbench_hard"

    def test_task_id_is_reasoning_and_logic(self):
        loader = self._loader()
        item = {
            "_native_id": "x",
            "_subtask": "dyck_languages",
            "_input": "Complete sequence.",
            "_target": "( ) ( )",
            "_inferred_attrs": {"task_type": "logic", "difficulty": "medium"},
        }
        record = loader._to_record(item, seq=0)
        assert record["task_id"] == "reasoning_and_logic"

    def test_prompt_contains_subtask_label(self):
        loader = self._loader()
        item = {
            "_native_id": "x",
            "_subtask": "boolean_expressions",
            "_input": "True AND False",
            "_target": "False",
            "_inferred_attrs": {"task_type": "logic", "difficulty": "low"},
        }
        record = loader._to_record(item, seq=0)
        assert "Boolean Expressions" in record["prompt"]

    def test_prompt_contains_input_text(self):
        loader = self._loader()
        input_text = "Evaluate: not ( True and False )"
        item = {
            "_native_id": "x",
            "_subtask": "boolean_expressions",
            "_input": input_text,
            "_target": "True",
            "_inferred_attrs": {"task_type": "logic", "difficulty": "low"},
        }
        record = loader._to_record(item, seq=0)
        assert input_text in record["prompt"]

    def test_reference_response_is_target(self):
        loader = self._loader()
        item = {
            "_native_id": "x",
            "_subtask": "navigate",
            "_input": "Take 2 steps north.",
            "_target": "yes",
            "_inferred_attrs": {"task_type": "reasoning", "difficulty": "low"},
        }
        record = loader._to_record(item, seq=0)
        assert record["reference_response"] == "yes"


# ---------------------------------------------------------------------------
# Registry tests
# ---------------------------------------------------------------------------

class TestLoaderRegistry:
    def test_math_is_registered(self):
        from benchmark.loaders import _REGISTRY
        assert "math" in _REGISTRY

    def test_mbpp_is_registered(self):
        from benchmark.loaders import _REGISTRY
        assert "mbpp" in _REGISTRY

    def test_bigbench_hard_is_registered(self):
        from benchmark.loaders import _REGISTRY
        assert "bigbench_hard" in _REGISTRY

    def test_math_attribute_map_path_exists(self):
        from benchmark.loaders import _REGISTRY
        _, map_path = _REGISTRY["math"]
        assert Path(map_path).exists(), f"Attribute map not found: {map_path}"

    def test_mbpp_attribute_map_path_exists(self):
        from benchmark.loaders import _REGISTRY
        _, map_path = _REGISTRY["mbpp"]
        assert Path(map_path).exists(), f"Attribute map not found: {map_path}"

    def test_bigbench_hard_attribute_map_path_exists(self):
        from benchmark.loaders import _REGISTRY
        _, map_path = _REGISTRY["bigbench_hard"]
        assert Path(map_path).exists(), f"Attribute map not found: {map_path}"

    def test_list_datasets_includes_new_loaders(self):
        from benchmark.loaders import list_datasets
        datasets = list_datasets()
        assert "math" in datasets
        assert "mbpp" in datasets
        assert "bigbench_hard" in datasets

    def test_math_loader_class_importable(self):
        from benchmark.loaders.math_dataset import MATHLoader
        assert MATHLoader.benchmark_id == "math"

    def test_mbpp_loader_class_importable(self):
        from benchmark.loaders.mbpp import MBPPLoader
        assert MBPPLoader.benchmark_id == "mbpp"

    def test_bigbench_hard_loader_class_importable(self):
        from benchmark.loaders.bigbench_hard import BigBenchHardLoader
        assert BigBenchHardLoader.benchmark_id == "bigbench_hard"


# ---------------------------------------------------------------------------
# BENCHMARK_METRIC entries for new loaders
# ---------------------------------------------------------------------------

class TestBenchmarkMetricNewLoaders:
    def test_math_uses_exact_match(self):
        from benchmark.compute_scores import BENCHMARK_METRIC
        assert BENCHMARK_METRIC["math"] == "exact_match"

    def test_mbpp_uses_bleu(self):
        from benchmark.compute_scores import BENCHMARK_METRIC
        assert BENCHMARK_METRIC["mbpp"] == "bleu"

    def test_bigbench_hard_uses_exact_match(self):
        from benchmark.compute_scores import BENCHMARK_METRIC
        assert BENCHMARK_METRIC["bigbench_hard"] == "exact_match"

    def test_arc_challenge_uses_exact_match(self):
        from benchmark.compute_scores import BENCHMARK_METRIC
        assert BENCHMARK_METRIC["arc_challenge"] == "exact_match"

    def test_race_uses_exact_match(self):
        from benchmark.compute_scores import BENCHMARK_METRIC
        assert BENCHMARK_METRIC["race"] == "exact_match"

    def test_sciq_uses_exact_match(self):
        from benchmark.compute_scores import BENCHMARK_METRIC
        assert BENCHMARK_METRIC["sciq"] == "exact_match"
