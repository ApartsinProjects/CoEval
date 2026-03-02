"""Tests for 16 additional benchmark loaders.

Covers:
  LogiQALoader, WinograndeLoader, MultiNLILoader, COPALoader, CosmosQALoader,
  BBQLoader, TriviaQALoader, SQuADv2Loader, NQOpenLoader, NarrativeQALoader,
  CNNDailyMailLoader, SAMSumLoader, FEVERLoader, SciFactLoader, MGSMLoader,
  MathQALoader

For each loader the test suite covers:
  - Helper functions (where applicable)
  - _load_dataset(): valid rows loaded, skip conditions honoured
  - _to_record(): Phase 3 JSONL schema compliance
  - Registry: dataset registered, attribute map file exists
  - BENCHMARK_METRIC: correct metric assigned

All tests use mocked datasets.load_dataset so no network access occurs.
"""
from __future__ import annotations

from pathlib import Path
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
    assert record["benchmark_native_score"] is None


def _make_mock_ds(rows: list) -> MagicMock:
    mock_ds = MagicMock()
    mock_ds.__iter__ = MagicMock(return_value=iter(rows))
    return mock_ds


# ===========================================================================
# 1. LogiQALoader
# ===========================================================================

class TestPassageLengthLogiQA:
    def _fn(self):
        from benchmark.loaders.logiqa import _passage_length
        return _passage_length

    def test_short_under_50_words(self):
        text = " ".join(["word"] * 30)
        assert self._fn()(text) == "short"

    def test_boundary_49_words_is_short(self):
        text = " ".join(["word"] * 49)
        assert self._fn()(text) == "short"

    def test_boundary_50_words_is_medium(self):
        text = " ".join(["word"] * 50)
        assert self._fn()(text) == "medium"

    def test_medium_under_100_words(self):
        text = " ".join(["word"] * 75)
        assert self._fn()(text) == "medium"

    def test_boundary_99_words_is_medium(self):
        text = " ".join(["word"] * 99)
        assert self._fn()(text) == "medium"

    def test_boundary_100_words_is_long(self):
        text = " ".join(["word"] * 100)
        assert self._fn()(text) == "long"

    def test_long_over_100_words(self):
        text = " ".join(["word"] * 150)
        assert self._fn()(text) == "long"


class TestLogiQALoaderLoadDataset:
    def _loader(self):
        from benchmark.loaders.logiqa import LogiQALoader
        return LogiQALoader(attribute_map={}, sample_size=100, split="test", seed=42)

    def test_loads_valid_rows(self):
        rows = [
            {"context": "A passage.", "question": "What?", "options": ["A","B","C","D"], "label": 0, "id": 1},
            {"context": "Another.", "question": "Which?", "options": ["x","y","z","w"], "label": 2, "id": 2},
        ]
        mock_ds = _make_mock_ds(rows)
        with patch("datasets.load_dataset", return_value=mock_ds):
            items = self._loader()._load_dataset()
        assert len(items) == 2

    def test_skips_empty_context(self):
        rows = [{"context": "", "question": "Q?", "options": ["a","b","c","d"], "label": 0, "id": 1}]
        mock_ds = _make_mock_ds(rows)
        with patch("datasets.load_dataset", return_value=mock_ds):
            items = self._loader()._load_dataset()
        assert len(items) == 0

    def test_skips_empty_question(self):
        rows = [{"context": "Valid.", "question": "", "options": ["a","b","c","d"], "label": 1, "id": 2}]
        mock_ds = _make_mock_ds(rows)
        with patch("datasets.load_dataset", return_value=mock_ds):
            items = self._loader()._load_dataset()
        assert len(items) == 0

    def test_skips_too_few_options(self):
        rows = [{"context": "Valid.", "question": "Q?", "options": ["a","b"], "label": 0, "id": 3}]
        mock_ds = _make_mock_ds(rows)
        with patch("datasets.load_dataset", return_value=mock_ds):
            items = self._loader()._load_dataset()
        assert len(items) == 0

    def test_skips_invalid_label(self):
        rows = [{"context": "Valid.", "question": "Q?", "options": ["a","b","c","d"], "label": 99, "id": 4}]
        mock_ds = _make_mock_ds(rows)
        with patch("datasets.load_dataset", return_value=mock_ds):
            items = self._loader()._load_dataset()
        assert len(items) == 0

    def test_inferred_attrs_present(self):
        rows = [{"context": "A short passage.", "question": "Q?", "options": ["a","b","c","d"], "label": 1, "id": 5}]
        mock_ds = _make_mock_ds(rows)
        with patch("datasets.load_dataset", return_value=mock_ds):
            items = self._loader()._load_dataset()
        assert items[0]["_inferred_attrs"]["reasoning_type"] == "logical"
        assert items[0]["_inferred_attrs"]["passage_length"] in ("short", "medium", "long")


class TestLogiQALoaderToRecord:
    def _loader(self):
        from benchmark.loaders.logiqa import LogiQALoader
        return LogiQALoader(attribute_map={}, sample_size=10, split="test", seed=42)

    def _make_item(self, label=0):
        return {
            "_native_id": "42",
            "_context": "Some passage for reasoning.",
            "_question": "What conclusion follows?",
            "_options": ["First option", "Second option", "Third option", "Fourth option"],
            "_label": label,
            "_inferred_attrs": {"passage_length": "short", "reasoning_type": "logical"},
        }

    def test_record_has_required_keys(self):
        record = self._loader()._to_record(self._make_item(), seq=0)
        _assert_phase3_record(record)

    def test_task_id_is_logical_reasoning(self):
        record = self._loader()._to_record(self._make_item(), seq=0)
        assert record["task_id"] == "logical_reasoning"

    def test_benchmark_id_is_logiqa(self):
        record = self._loader()._to_record(self._make_item(), seq=0)
        assert record["benchmark_id"] == "logiqa"

    def test_reference_response_letter_a(self):
        record = self._loader()._to_record(self._make_item(label=0), seq=0)
        assert record["reference_response"] == "A"

    def test_reference_response_letter_d(self):
        record = self._loader()._to_record(self._make_item(label=3), seq=0)
        assert record["reference_response"] == "D"

    def test_prompt_contains_context(self):
        item = self._make_item()
        record = self._loader()._to_record(item, seq=0)
        assert item["_context"] in record["prompt"]

    def test_prompt_contains_question(self):
        item = self._make_item()
        record = self._loader()._to_record(item, seq=0)
        assert item["_question"] in record["prompt"]

    def test_prompt_contains_options(self):
        item = self._make_item()
        record = self._loader()._to_record(item, seq=0)
        assert "First option" in record["prompt"]
        assert "Fourth option" in record["prompt"]

# ===========================================================================
# 2. WinograndeLoader
# ===========================================================================

class TestOptionLengthWinogrande:
    def _fn(self):
        from benchmark.loaders.winogrande import _option_length
        return _option_length

    def test_short_max_5_words(self):
        assert self._fn()("cat", "dog") == "short"

    def test_boundary_5_words_is_short(self):
        assert self._fn()("one two three four five", "x") == "short"

    def test_boundary_6_words_is_medium(self):
        assert self._fn()("one two three four five six", "x") == "medium"

    def test_medium_up_to_10_words(self):
        assert self._fn()("a b c d e f g", "x") == "medium"

    def test_boundary_10_words_is_medium(self):
        assert self._fn()("a b c d e f g h i j", "x") == "medium"

    def test_boundary_11_words_is_long(self):
        assert self._fn()("a b c d e f g h i j k", "x") == "long"

    def test_uses_max_of_both_options(self):
        # 11 words in option2 -> max_len > 10 -> "long"
        assert self._fn()("cat", "one two three four five six seven eight nine ten eleven") == "long"


class TestWinograndeLoaderLoadDataset:
    def _loader(self):
        from benchmark.loaders.winogrande import WinograndeLoader
        return WinograndeLoader(attribute_map={}, sample_size=100, split="validation", seed=42)

    def test_loads_valid_rows(self):
        rows = [
            {"sentence": "The _ sat.", "option1": "cat", "option2": "dog", "answer": "1"},
            {"sentence": "She put _ away.", "option1": "book", "option2": "phone", "answer": "2"},
        ]
        mock_ds = _make_mock_ds(rows)
        with patch("datasets.load_dataset", return_value=mock_ds):
            items = self._loader()._load_dataset()
        assert len(items) == 2

    def test_skips_invalid_answer(self):
        rows = [{"sentence": "She _ fast.", "option1": "ran", "option2": "walked", "answer": "3"}]
        mock_ds = _make_mock_ds(rows)
        with patch("datasets.load_dataset", return_value=mock_ds):
            items = self._loader()._load_dataset()
        assert len(items) == 0

    def test_skips_empty_sentence(self):
        rows = [{"sentence": "", "option1": "cat", "option2": "dog", "answer": "1"}]
        mock_ds = _make_mock_ds(rows)
        with patch("datasets.load_dataset", return_value=mock_ds):
            items = self._loader()._load_dataset()
        assert len(items) == 0

    def test_answer_stored_correctly(self):
        rows = [{"sentence": "_ is on table.", "option1": "cup", "option2": "plate", "answer": "1"}]
        mock_ds = _make_mock_ds(rows)
        with patch("datasets.load_dataset", return_value=mock_ds):
            items = self._loader()._load_dataset()
        assert items[0]["_answer"] == "1"

    def test_inferred_format_is_fill_in_blank(self):
        rows = [{"sentence": "_ ran away.", "option1": "cat", "option2": "dog", "answer": "2"}]
        mock_ds = _make_mock_ds(rows)
        with patch("datasets.load_dataset", return_value=mock_ds):
            items = self._loader()._load_dataset()
        assert items[0]["_inferred_attrs"]["format"] == "fill_in_blank"


class TestWinograndeLoaderToRecord:
    def _loader(self):
        from benchmark.loaders.winogrande import WinograndeLoader
        return WinograndeLoader(attribute_map={}, sample_size=10, split="validation", seed=42)

    def _make_item(self, answer="1"):
        return {
            "_native_id": "0",
            "_sentence": "The _ sat on the mat.",
            "_option1": "cat",
            "_option2": "dog",
            "_answer": answer,
            "_inferred_attrs": {"option_length": "short", "format": "fill_in_blank"},
        }

    def test_record_has_required_keys(self):
        record = self._loader()._to_record(self._make_item(), seq=0)
        _assert_phase3_record(record)

    def test_benchmark_id_is_winogrande(self):
        record = self._loader()._to_record(self._make_item(), seq=0)
        assert record["benchmark_id"] == "winogrande"

    def test_task_id_is_commonsense_reasoning(self):
        record = self._loader()._to_record(self._make_item(), seq=0)
        assert record["task_id"] == "commonsense_reasoning"

    def test_reference_a_for_answer_1(self):
        record = self._loader()._to_record(self._make_item(answer="1"), seq=0)
        assert record["reference_response"] == "A"

    def test_reference_b_for_answer_2(self):
        record = self._loader()._to_record(self._make_item(answer="2"), seq=0)
        assert record["reference_response"] == "B"

    def test_prompt_contains_sentence(self):
        item = self._make_item()
        record = self._loader()._to_record(item, seq=0)
        assert item["_sentence"] in record["prompt"]

    def test_prompt_contains_both_options(self):
        item = self._make_item()
        record = self._loader()._to_record(item, seq=0)
        assert "cat" in record["prompt"]
        assert "dog" in record["prompt"]

# ===========================================================================
# 3. MultiNLILoader
# ===========================================================================

class TestNormaliseGenreMultiNLI:
    def _fn(self):
        from benchmark.loaders.multinli import _normalise_genre
        return _normalise_genre

    def test_basic_lowercasing(self):
        assert self._fn()("Telephone") == "telephone"

    def test_takes_first_word(self):
        assert self._fn()("Government Documents") == "government"

    def test_none_defaults_to_fiction(self):
        assert self._fn()(None) == "fiction"

    def test_strips_whitespace(self):
        assert self._fn()("  travel  ") == "travel"

    def test_single_word_lowercased(self):
        assert self._fn()("TRAVEL") == "travel"


class TestMultiNLILoaderLoadDataset:
    def _loader(self):
        from benchmark.loaders.multinli import MultiNLILoader
        return MultiNLILoader(attribute_map={}, sample_size=100, split="validation_matched", seed=42)

    def test_loads_valid_rows(self):
        rows = [
            {"premise": "Cat sat.", "hypothesis": "Animal sat.", "label": 0, "genre": "fiction"},
            {"premise": "It rains.", "hypothesis": "It is wet.", "label": 1, "genre": "telephone"},
        ]
        mock_ds = _make_mock_ds(rows)
        with patch("datasets.load_dataset", return_value=mock_ds):
            items = self._loader()._load_dataset()
        assert len(items) == 2

    def test_skips_label_minus_one(self):
        rows = [{"premise": "S.", "hypothesis": "H.", "label": -1, "genre": "fiction"}]
        mock_ds = _make_mock_ds(rows)
        with patch("datasets.load_dataset", return_value=mock_ds):
            items = self._loader()._load_dataset()
        assert len(items) == 0

    def test_skips_empty_premise(self):
        rows = [{"premise": "", "hypothesis": "H.", "label": 0, "genre": "fiction"}]
        mock_ds = _make_mock_ds(rows)
        with patch("datasets.load_dataset", return_value=mock_ds):
            items = self._loader()._load_dataset()
        assert len(items) == 0

    def test_label_maps_to_contradiction(self):
        rows = [{"premise": "A.", "hypothesis": "B.", "label": 2, "genre": "travel"}]
        mock_ds = _make_mock_ds(rows)
        with patch("datasets.load_dataset", return_value=mock_ds):
            items = self._loader()._load_dataset()
        assert items[0]["_label_str"] == "contradiction"

    def test_label_maps_to_entailment(self):
        rows = [{"premise": "A cat.", "hypothesis": "An animal.", "label": 0, "genre": "fiction"}]
        mock_ds = _make_mock_ds(rows)
        with patch("datasets.load_dataset", return_value=mock_ds):
            items = self._loader()._load_dataset()
        assert items[0]["_label_str"] == "entailment"

    def test_label_maps_to_neutral(self):
        rows = [{"premise": "She smiled.", "hypothesis": "She is happy.", "label": 1, "genre": "slate"}]
        mock_ds = _make_mock_ds(rows)
        with patch("datasets.load_dataset", return_value=mock_ds):
            items = self._loader()._load_dataset()
        assert items[0]["_label_str"] == "neutral"


class TestMultiNLILoaderToRecord:
    def _loader(self):
        from benchmark.loaders.multinli import MultiNLILoader
        return MultiNLILoader(attribute_map={}, sample_size=10, split="validation_matched", seed=42)

    def _make_item(self, label_str="entailment"):
        return {
            "_native_id": "0",
            "_premise": "The cat is on the mat.",
            "_hypothesis": "An animal is on the mat.",
            "_label_str": label_str,
            "_inferred_attrs": {"genre": "fiction", "label": label_str},
        }

    def test_record_has_required_keys(self):
        record = self._loader()._to_record(self._make_item(), seq=0)
        _assert_phase3_record(record)

    def test_benchmark_id_is_multinli(self):
        record = self._loader()._to_record(self._make_item(), seq=0)
        assert record["benchmark_id"] == "multinli"

    def test_task_id_is_nli(self):
        record = self._loader()._to_record(self._make_item(), seq=0)
        assert record["task_id"] == "natural_language_inference"

    def test_reference_response_is_label_string(self):
        record = self._loader()._to_record(self._make_item("contradiction"), seq=0)
        assert record["reference_response"] == "contradiction"

    def test_prompt_contains_premise_and_hypothesis(self):
        item = self._make_item()
        record = self._loader()._to_record(item, seq=0)
        assert item["_premise"] in record["prompt"]
        assert item["_hypothesis"] in record["prompt"]

# ===========================================================================
# 4. COPALoader
# ===========================================================================

class TestCOPALoaderLoadDataset:
    def _loader(self):
        from benchmark.loaders.copa import COPALoader
        return COPALoader(attribute_map={}, sample_size=100, split="validation", seed=42)

    def test_loads_valid_rows(self):
        rows = [
            {"premise": "She tripped.", "choice1": "She fell.", "choice2": "She ran.",
             "question": "effect", "label": 0, "idx": 0},
        ]
        mock_ds = _make_mock_ds(rows)
        with patch("datasets.load_dataset", return_value=mock_ds):
            items = self._loader()._load_dataset()
        assert len(items) == 1

    def test_skips_empty_premise(self):
        rows = [{"premise": "", "choice1": "A.", "choice2": "B.", "question": "effect", "label": 0, "idx": 0}]
        mock_ds = _make_mock_ds(rows)
        with patch("datasets.load_dataset", return_value=mock_ds):
            items = self._loader()._load_dataset()
        assert len(items) == 0

    def test_skips_invalid_label(self):
        rows = [{"premise": "She ran.", "choice1": "A.", "choice2": "B.", "question": "effect", "label": 5, "idx": 0}]
        mock_ds = _make_mock_ds(rows)
        with patch("datasets.load_dataset", return_value=mock_ds):
            items = self._loader()._load_dataset()
        assert len(items) == 0

    def test_question_type_in_attrs(self):
        rows = [{"premise": "It rained.", "choice1": "Flooded.", "choice2": "Sun.", "question": "effect", "label": 0, "idx": 2}]
        mock_ds = _make_mock_ds(rows)
        with patch("datasets.load_dataset", return_value=mock_ds):
            items = self._loader()._load_dataset()
        assert items[0]["_inferred_attrs"]["question_type"] == "effect"
        assert items[0]["_inferred_attrs"]["difficulty"] == "medium"

    def test_idx_used_as_native_id(self):
        rows = [{"premise": "P.", "choice1": "A.", "choice2": "B.", "question": "cause", "label": 1, "idx": 42}]
        mock_ds = _make_mock_ds(rows)
        with patch("datasets.load_dataset", return_value=mock_ds):
            items = self._loader()._load_dataset()
        assert items[0]["_native_id"] == "42"


class TestCOPALoaderToRecord:
    def _loader(self):
        from benchmark.loaders.copa import COPALoader
        return COPALoader(attribute_map={}, sample_size=10, split="validation", seed=42)

    def _make_item(self, question="effect", label=0):
        return {
            "_native_id": "5",
            "_premise": "She tripped on the step.",
            "_choice1": "She fell down.",
            "_choice2": "She jumped up.",
            "_question": question,
            "_label": label,
            "_inferred_attrs": {"question_type": question, "difficulty": "medium"},
        }

    def test_record_has_required_keys(self):
        record = self._loader()._to_record(self._make_item(), seq=0)
        _assert_phase3_record(record)

    def test_benchmark_id_is_copa(self):
        record = self._loader()._to_record(self._make_item(), seq=0)
        assert record["benchmark_id"] == "copa"

    def test_task_id_is_causal_reasoning(self):
        record = self._loader()._to_record(self._make_item(), seq=0)
        assert record["task_id"] == "causal_reasoning"

    def test_reference_a_for_label_0(self):
        record = self._loader()._to_record(self._make_item(label=0), seq=0)
        assert record["reference_response"] == "A"

    def test_reference_b_for_label_1(self):
        record = self._loader()._to_record(self._make_item(label=1), seq=0)
        assert record["reference_response"] == "B"

    def test_effect_prompt_framing(self):
        item = self._make_item(question="effect")
        record = self._loader()._to_record(item, seq=0)
        assert any(w in record["prompt"].lower() for w in ("result", "happened", "effect"))

    def test_cause_prompt_framing(self):
        item = self._make_item(question="cause")
        record = self._loader()._to_record(item, seq=0)
        assert "cause" in record["prompt"].lower() or "CAUSE" in record["prompt"]

    def test_prompt_contains_choices(self):
        item = self._make_item()
        record = self._loader()._to_record(item, seq=0)
        assert item["_choice1"] in record["prompt"]
        assert item["_choice2"] in record["prompt"]

# ===========================================================================
# 5. CosmosQALoader
# ===========================================================================

class TestContextLengthCosmosQA:
    def _fn(self):
        from benchmark.loaders.cosmos_qa import _context_length
        return _context_length

    def test_short_under_60_words(self):
        text = " ".join(["word"] * 30)
        assert self._fn()(text) == "short"

    def test_boundary_59_words_is_short(self):
        text = " ".join(["word"] * 59)
        assert self._fn()(text) == "short"

    def test_boundary_60_words_is_medium(self):
        text = " ".join(["word"] * 60)
        assert self._fn()(text) == "medium"

    def test_boundary_120_words_is_long(self):
        text = " ".join(["word"] * 120)
        assert self._fn()(text) == "long"

    def test_long_over_120_words(self):
        text = " ".join(["word"] * 200)
        assert self._fn()(text) == "long"


class TestCosmosQALoaderLoadDataset:
    def _loader(self):
        from benchmark.loaders.cosmos_qa import CosmosQALoader
        return CosmosQALoader(attribute_map={}, sample_size=100, split="validation", seed=42)

    def test_loads_valid_rows(self):
        rows = [{"context": "A story.", "question": "Why?", "answer0": "A", "answer1": "B", "answer2": "C", "answer3": "D", "label": 1, "id": "abc"}]
        mock_ds = _make_mock_ds(rows)
        with patch("datasets.load_dataset", return_value=mock_ds):
            items = self._loader()._load_dataset()
        assert len(items) == 1

    def test_skips_empty_answer(self):
        rows = [{"context": "C.", "question": "Q?", "answer0": "", "answer1": "B", "answer2": "C", "answer3": "D", "label": 0, "id": "x"}]
        mock_ds = _make_mock_ds(rows)
        with patch("datasets.load_dataset", return_value=mock_ds):
            items = self._loader()._load_dataset()
        assert len(items) == 0

    def test_skips_invalid_label(self):
        rows = [{"context": "C.", "question": "Q?", "answer0": "A", "answer1": "B", "answer2": "C", "answer3": "D", "label": 10, "id": "y"}]
        mock_ds = _make_mock_ds(rows)
        with patch("datasets.load_dataset", return_value=mock_ds):
            items = self._loader()._load_dataset()
        assert len(items) == 0

    def test_answer_count_attr_is_four(self):
        rows = [{"context": "C.", "question": "Q?", "answer0": "A", "answer1": "B", "answer2": "C", "answer3": "D", "label": 0, "id": "z"}]
        mock_ds = _make_mock_ds(rows)
        with patch("datasets.load_dataset", return_value=mock_ds):
            items = self._loader()._load_dataset()
        assert items[0]["_inferred_attrs"]["answer_count"] == "four"


class TestCosmosQALoaderToRecord:
    def _loader(self):
        from benchmark.loaders.cosmos_qa import CosmosQALoader
        return CosmosQALoader(attribute_map={}, sample_size=10, split="validation", seed=42)

    def _make_item(self, label=2):
        return {
            "_native_id": "abc",
            "_context": "He went to the store.",
            "_question": "Why did he go?",
            "_answer0": "He was hungry.",
            "_answer1": "He was bored.",
            "_answer2": "He needed milk.",
            "_answer3": "He was tired.",
            "_label": label,
            "_inferred_attrs": {"context_length": "short", "answer_count": "four"},
        }

    def test_record_has_required_keys(self):
        record = self._loader()._to_record(self._make_item(), seq=0)
        _assert_phase3_record(record)

    def test_benchmark_id_is_cosmos_qa(self):
        record = self._loader()._to_record(self._make_item(), seq=0)
        assert record["benchmark_id"] == "cosmos_qa"

    def test_task_id_is_narrative_reasoning(self):
        record = self._loader()._to_record(self._make_item(), seq=0)
        assert record["task_id"] == "narrative_reasoning"

    def test_reference_c_for_label_2(self):
        record = self._loader()._to_record(self._make_item(label=2), seq=0)
        assert record["reference_response"] == "C"

    def test_prompt_contains_context_and_question(self):
        item = self._make_item()
        record = self._loader()._to_record(item, seq=0)
        assert item["_context"] in record["prompt"]
        assert item["_question"] in record["prompt"]

    def test_prompt_contains_all_answers(self):
        item = self._make_item()
        record = self._loader()._to_record(item, seq=0)
        assert "He was hungry." in record["prompt"]
        assert "He needed milk." in record["prompt"]

# ===========================================================================
# 6. BBQLoader
# ===========================================================================

class TestNormaliseCategoryBBQ:
    def _fn(self):
        from benchmark.loaders.bbq import _normalise_category
        return _normalise_category

    def test_lowercases_category(self):
        assert self._fn()("Age") == "age"

    def test_replaces_spaces_with_underscores(self):
        assert self._fn()("Sexual Orientation") == "sexual_orientation"

    def test_none_returns_unknown(self):
        assert self._fn()(None) == "unknown"

    def test_empty_returns_unknown(self):
        assert self._fn()("") == "unknown"

    def test_strips_whitespace(self):
        assert self._fn()("  gender  ") == "gender"


class TestBBQLoaderLoadDataset:
    def _loader(self):
        from benchmark.loaders.bbq import BBQLoader
        return BBQLoader(attribute_map={}, sample_size=100, split="test", seed=42)

    def test_loads_valid_rows(self):
        rows = [{
            "context": "Two people applied for a job.",
            "question": "Who is less qualified?",
            "ans0": "The older applicant.",
            "ans1": "The younger applicant.",
            "ans2": "Cannot be determined.",
            "label": 2,
            "category": "Age",
            "question_polarity": "neg",
        }]
        mock_ds = _make_mock_ds(rows)
        with patch("datasets.load_dataset", return_value=mock_ds):
            items = self._loader()._load_dataset()
        assert len(items) == 1

    def test_skips_empty_context(self):
        rows = [{"context": "", "question": "Q?", "ans0": "A", "ans1": "B", "ans2": "C", "label": 0, "category": "Age", "question_polarity": "neg"}]
        mock_ds = _make_mock_ds(rows)
        with patch("datasets.load_dataset", return_value=mock_ds):
            items = self._loader()._load_dataset()
        assert len(items) == 0

    def test_skips_empty_answers(self):
        rows = [{"context": "C.", "question": "Q?", "ans0": "", "ans1": "B", "ans2": "C", "label": 0, "category": "Age", "question_polarity": "neg"}]
        mock_ds = _make_mock_ds(rows)
        with patch("datasets.load_dataset", return_value=mock_ds):
            items = self._loader()._load_dataset()
        assert len(items) == 0

    def test_category_normalised_in_attrs(self):
        rows = [{"context": "C.", "question": "Q?", "ans0": "A", "ans1": "B", "ans2": "C", "label": 1, "category": "Race Ethnicity", "question_polarity": "nonneg"}]
        mock_ds = _make_mock_ds(rows)
        with patch("datasets.load_dataset", return_value=mock_ds):
            items = self._loader()._load_dataset()
        assert items[0]["_inferred_attrs"]["category"] == "race_ethnicity"

    def test_polarity_stored_in_attrs(self):
        rows = [{"context": "C.", "question": "Q?", "ans0": "A", "ans1": "B", "ans2": "C", "label": 0, "category": "Gender", "question_polarity": "neg"}]
        mock_ds = _make_mock_ds(rows)
        with patch("datasets.load_dataset", return_value=mock_ds):
            items = self._loader()._load_dataset()
        assert items[0]["_inferred_attrs"]["polarity"] == "neg"


class TestBBQLoaderToRecord:
    def _loader(self):
        from benchmark.loaders.bbq import BBQLoader
        return BBQLoader(attribute_map={}, sample_size=10, split="test", seed=42)

    def _make_item(self, label=1):
        return {
            "_native_id": "0",
            "_context": "Two people applied for a job.",
            "_question": "Who is more qualified?",
            "_ans0": "The older person.",
            "_ans1": "The younger person.",
            "_ans2": "Cannot be determined.",
            "_label": label,
            "_inferred_attrs": {"category": "age", "polarity": "neg"},
        }

    def test_record_has_required_keys(self):
        record = self._loader()._to_record(self._make_item(), seq=0)
        _assert_phase3_record(record)

    def test_benchmark_id_is_bbq(self):
        record = self._loader()._to_record(self._make_item(), seq=0)
        assert record["benchmark_id"] == "bbq"

    def test_task_id_is_bias_evaluation_qa(self):
        record = self._loader()._to_record(self._make_item(), seq=0)
        assert record["task_id"] == "bias_evaluation_qa"

    def test_reference_a_for_label_0(self):
        record = self._loader()._to_record(self._make_item(label=0), seq=0)
        assert record["reference_response"] == "A"

    def test_reference_c_for_label_2(self):
        record = self._loader()._to_record(self._make_item(label=2), seq=0)
        assert record["reference_response"] == "C"

    def test_prompt_contains_context_and_question(self):
        item = self._make_item()
        record = self._loader()._to_record(item, seq=0)
        assert item["_context"] in record["prompt"]
        assert item["_question"] in record["prompt"]

    def test_prompt_contains_all_three_answers(self):
        item = self._make_item()
        record = self._loader()._to_record(item, seq=0)
        assert "The older person." in record["prompt"]
        assert "Cannot be determined." in record["prompt"]

# ===========================================================================
# 7. TriviaQALoader
# ===========================================================================

class TestAnswerLengthTriviaQA:
    def _fn(self):
        from benchmark.loaders.trivia_qa import _answer_length
        return _answer_length

    def test_one_word_is_short(self):
        assert self._fn()("Paris") == "short"

    def test_two_words_is_medium(self):
        assert self._fn()("New York") == "medium"

    def test_three_words_is_medium(self):
        assert self._fn()("United States America") == "medium"

    def test_four_words_is_long(self):
        assert self._fn()("one two three four") == "long"

    def test_many_words_is_long(self):
        assert self._fn()("a very long answer here now") == "long"


class TestTriviaQALoaderLoadDataset:
    def _loader(self):
        from benchmark.loaders.trivia_qa import TriviaQALoader
        return TriviaQALoader(attribute_map={}, sample_size=100, split="validation", seed=42)

    def test_loads_valid_rows(self):
        rows = [
            {"question": "Capital of France?", "answer": {"value": "Paris"}, "question_id": "q1"},
            {"question": "Who wrote Hamlet?", "answer": {"value": "Shakespeare"}, "question_id": "q2"},
        ]
        mock_ds = _make_mock_ds(rows)
        with patch("datasets.load_dataset", return_value=mock_ds):
            items = self._loader()._load_dataset()
        assert len(items) == 2

    def test_skips_empty_question(self):
        rows = [{"question": "", "answer": {"value": "Paris"}, "question_id": "q1"}]
        mock_ds = _make_mock_ds(rows)
        with patch("datasets.load_dataset", return_value=mock_ds):
            items = self._loader()._load_dataset()
        assert len(items) == 0

    def test_skips_empty_answer_value(self):
        rows = [{"question": "Something?", "answer": {"value": ""}, "question_id": "q2"}]
        mock_ds = _make_mock_ds(rows)
        with patch("datasets.load_dataset", return_value=mock_ds):
            items = self._loader()._load_dataset()
        assert len(items) == 0

    def test_domain_is_trivia(self):
        rows = [{"question": "Some Q?", "answer": {"value": "Answer"}, "question_id": "q3"}]
        mock_ds = _make_mock_ds(rows)
        with patch("datasets.load_dataset", return_value=mock_ds):
            items = self._loader()._load_dataset()
        assert items[0]["_inferred_attrs"]["domain"] == "trivia"

    def test_native_id_from_question_id(self):
        rows = [{"question": "Q?", "answer": {"value": "A"}, "question_id": "myid_123"}]
        mock_ds = _make_mock_ds(rows)
        with patch("datasets.load_dataset", return_value=mock_ds):
            items = self._loader()._load_dataset()
        assert items[0]["_native_id"] == "myid_123"


class TestTriviaQALoaderToRecord:
    def _loader(self):
        from benchmark.loaders.trivia_qa import TriviaQALoader
        return TriviaQALoader(attribute_map={}, sample_size=10, split="validation", seed=42)

    def _make_item(self):
        return {
            "_native_id": "q99",
            "_question": "What is the capital of France?",
            "_answer_value": "Paris",
            "_inferred_attrs": {"answer_length": "short", "domain": "trivia"},
        }

    def test_record_has_required_keys(self):
        record = self._loader()._to_record(self._make_item(), seq=0)
        _assert_phase3_record(record)

    def test_benchmark_id_is_trivia_qa(self):
        record = self._loader()._to_record(self._make_item(), seq=0)
        assert record["benchmark_id"] == "trivia_qa"

    def test_task_id_is_knowledge_retrieval(self):
        record = self._loader()._to_record(self._make_item(), seq=0)
        assert record["task_id"] == "knowledge_retrieval"

    def test_reference_response_is_answer(self):
        record = self._loader()._to_record(self._make_item(), seq=0)
        assert record["reference_response"] == "Paris"

    def test_prompt_contains_question(self):
        item = self._make_item()
        record = self._loader()._to_record(item, seq=0)
        assert item["_question"] in record["prompt"]


# ===========================================================================
# 8. SQuADv2Loader
# ===========================================================================

class TestPassageLengthSQuADv2:
    def _fn(self):
        from benchmark.loaders.squad_v2 import _passage_length
        return _passage_length

    def test_short_under_80_words(self):
        assert self._fn()(" ".join(["w"] * 50)) == "short"

    def test_boundary_79_is_short(self):
        assert self._fn()(" ".join(["w"] * 79)) == "short"

    def test_boundary_80_is_medium(self):
        assert self._fn()(" ".join(["w"] * 80)) == "medium"

    def test_boundary_199_is_medium(self):
        assert self._fn()(" ".join(["w"] * 199)) == "medium"

    def test_boundary_200_is_long(self):
        assert self._fn()(" ".join(["w"] * 200)) == "long"


class TestSQuADv2LoaderLoadDataset:
    def _loader(self):
        from benchmark.loaders.squad_v2 import SQuADv2Loader
        return SQuADv2Loader(attribute_map={}, sample_size=100, split="validation", seed=42)

    def test_answerable_row_stored(self):
        rows = [{"question": "Who?", "context": "Alice did it.", "answers": {"text": ["Alice"]}, "id": "id1"}]
        mock_ds = _make_mock_ds(rows)
        with patch("datasets.load_dataset", return_value=mock_ds):
            items = self._loader()._load_dataset()
        assert items[0]["_reference"] == "Alice"
        assert items[0]["_inferred_attrs"]["answerability"] == "answerable"

    def test_unanswerable_row_stored(self):
        rows = [{"question": "Who?", "context": "Nothing here.", "answers": {"text": []}, "id": "id2"}]
        mock_ds = _make_mock_ds(rows)
        with patch("datasets.load_dataset", return_value=mock_ds):
            items = self._loader()._load_dataset()
        assert items[0]["_reference"] == "unanswerable"
        assert items[0]["_inferred_attrs"]["answerability"] == "unanswerable"

    def test_skips_empty_question(self):
        rows = [{"question": "", "context": "ctx", "answers": {"text": ["a"]}, "id": "id3"}]
        mock_ds = _make_mock_ds(rows)
        with patch("datasets.load_dataset", return_value=mock_ds):
            items = self._loader()._load_dataset()
        assert len(items) == 0

    def test_skips_empty_context(self):
        rows = [{"question": "q", "context": "", "answers": {"text": []}, "id": "id4"}]
        mock_ds = _make_mock_ds(rows)
        with patch("datasets.load_dataset", return_value=mock_ds):
            items = self._loader()._load_dataset()
        assert len(items) == 0


class TestSQuADv2LoaderToRecord:
    def _loader(self):
        from benchmark.loaders.squad_v2 import SQuADv2Loader
        return SQuADv2Loader(attribute_map={}, sample_size=10, split="validation", seed=42)

    def _make_item(self, reference="Some answer"):
        return {
            "_native_id": "id1",
            "_question": "What happened?",
            "_context": "Alice did it first.",
            "_reference": reference,
            "_inferred_attrs": {"answerability": "answerable", "passage_length": "short"},
        }

    def test_record_has_required_keys(self):
        record = self._loader()._to_record(self._make_item(), seq=0)
        _assert_phase3_record(record)

    def test_benchmark_id_is_squad_v2(self):
        assert self._loader()._to_record(self._make_item(), seq=0)["benchmark_id"] == "squad_v2"

    def test_reference_response_stored(self):
        assert self._loader()._to_record(self._make_item("Alice"), seq=0)["reference_response"] == "Alice"

    def test_unanswerable_reference(self):
        assert self._loader()._to_record(self._make_item("unanswerable"), seq=0)["reference_response"] == "unanswerable"

    def test_prompt_contains_context_and_question(self):
        item = self._make_item()
        record = self._loader()._to_record(item, seq=0)
        assert item["_context"] in record["prompt"] and item["_question"] in record["prompt"]


# ===========================================================================
# 9. NQOpenLoader
# ===========================================================================

class TestNQOpenLoaderLoadDataset:
    def _loader(self):
        from benchmark.loaders.nq_open import NQOpenLoader
        return NQOpenLoader(attribute_map={}, sample_size=100, split="validation", seed=42)

    def test_loads_valid_rows(self):
        rows = [{"question": "WW2 end?", "answer": ["1945"]},
                {"question": "Hamlet author?", "answer": ["Shakespeare"]}]
        mock_ds = _make_mock_ds(rows)
        with patch("datasets.load_dataset", return_value=mock_ds):
            assert len(self._loader()._load_dataset()) == 2

    def test_skips_empty_answer_list(self):
        rows = [{"question": "What?", "answer": []}]
        mock_ds = _make_mock_ds(rows)
        with patch("datasets.load_dataset", return_value=mock_ds):
            assert len(self._loader()._load_dataset()) == 0

    def test_domain_is_factoid(self):
        rows = [{"question": "Capital?", "answer": ["Paris"]}]
        mock_ds = _make_mock_ds(rows)
        with patch("datasets.load_dataset", return_value=mock_ds):
            assert self._loader()._load_dataset()[0]["_inferred_attrs"]["domain"] == "factoid"

    def test_single_word_answer_is_short(self):
        rows = [{"question": "Capital?", "answer": ["Paris"]}]
        mock_ds = _make_mock_ds(rows)
        with patch("datasets.load_dataset", return_value=mock_ds):
            assert self._loader()._load_dataset()[0]["_inferred_attrs"]["answer_length"] == "short"

    def test_long_answer_classified(self):
        rows = [{"question": "Describe?", "answer": ["a very long answer indeed here"]}]
        mock_ds = _make_mock_ds(rows)
        with patch("datasets.load_dataset", return_value=mock_ds):
            assert self._loader()._load_dataset()[0]["_inferred_attrs"]["answer_length"] == "long"


class TestNQOpenLoaderToRecord:
    def _loader(self):
        from benchmark.loaders.nq_open import NQOpenLoader
        return NQOpenLoader(attribute_map={}, sample_size=10, split="validation", seed=42)

    def _make_item(self):
        return {"question": "Who wrote Hamlet?", "answers": ["Shakespeare"],
                "_native_id": "0", "_inferred_attrs": {"answer_length": "short", "domain": "factoid"}}

    def test_record_has_required_keys(self):
        _assert_phase3_record(self._loader()._to_record(self._make_item(), seq=0))

    def test_benchmark_id_is_nq_open(self):
        assert self._loader()._to_record(self._make_item(), seq=0)["benchmark_id"] == "nq_open"

    def test_reference_response_is_first_answer(self):
        assert self._loader()._to_record(self._make_item(), seq=0)["reference_response"] == "Shakespeare"

    def test_prompt_contains_question(self):
        item = self._make_item()
        assert item["question"] in self._loader()._to_record(item, seq=0)["prompt"]


# ===========================================================================
# 10. NarrativeQALoader
# ===========================================================================

class TestNarrativeQALoaderLoadDataset:
    def _loader(self):
        from benchmark.loaders.narrativeqa import NarrativeQALoader
        return NarrativeQALoader(attribute_map={}, sample_size=100, split="test", seed=42)

    def test_loads_valid_rows(self):
        rows = [{"document": {"summary": {"text": "Alice falls."}, "kind": "gutenberg"},
                 "question": {"text": "What did Alice do?"}, "answers": [{"text": "She fell."}]}]
        mock_ds = _make_mock_ds(rows)
        with patch("datasets.load_dataset", return_value=mock_ds):
            assert len(self._loader()._load_dataset()) == 1

    def test_summary_as_string(self):
        rows = [{"document": {"summary": "A simple story.", "kind": "movie"},
                 "question": {"text": "What happened?"}, "answers": [{"text": "Something."}]}]
        mock_ds = _make_mock_ds(rows)
        with patch("datasets.load_dataset", return_value=mock_ds):
            assert self._loader()._load_dataset()[0]["_inferred_attrs"]["document_kind"] == "movie"

    def test_skips_empty_summary(self):
        rows = [{"document": {"summary": "", "kind": "gutenberg"},
                 "question": {"text": "What?"}, "answers": [{"text": "Answer."}]}]
        mock_ds = _make_mock_ds(rows)
        with patch("datasets.load_dataset", return_value=mock_ds):
            assert len(self._loader()._load_dataset()) == 0

    def test_skips_empty_answers(self):
        rows = [{"document": {"summary": "A story.", "kind": "gutenberg"},
                 "question": {"text": "What?"}, "answers": []}]
        mock_ds = _make_mock_ds(rows)
        with patch("datasets.load_dataset", return_value=mock_ds):
            assert len(self._loader()._load_dataset()) == 0


class TestNarrativeQALoaderToRecord:
    def _loader(self):
        from benchmark.loaders.narrativeqa import NarrativeQALoader
        return NarrativeQALoader(attribute_map={}, sample_size=10, split="test", seed=42)

    def _make_item(self):
        return {"summary": "Alice falls into a rabbit hole.",
                "question": "Where did Alice fall?",
                "answers": [{"text": "Into a rabbit hole."}, {"text": "A rabbit hole."}],
                "_native_id": "0",
                "_inferred_attrs": {"document_kind": "gutenberg", "answer_length": "short"}}

    def test_record_has_required_keys(self):
        _assert_phase3_record(self._loader()._to_record(self._make_item(), seq=0))

    def test_benchmark_id_is_narrativeqa(self):
        assert self._loader()._to_record(self._make_item(), seq=0)["benchmark_id"] == "narrativeqa"

    def test_reference_is_first_answer_text(self):
        assert self._loader()._to_record(self._make_item(), seq=0)["reference_response"] == "Into a rabbit hole."

    def test_prompt_contains_summary_and_question(self):
        item = self._make_item()
        record = self._loader()._to_record(item, seq=0)
        assert item["summary"] in record["prompt"] and item["question"] in record["prompt"]


# ===========================================================================
# 11. CNNDailyMailLoader
# ===========================================================================

class TestCNNDailyMailLoaderLoadDataset:
    def _loader(self):
        from benchmark.loaders.cnn_dailymail import CNNDailyMailLoader
        return CNNDailyMailLoader(attribute_map={}, sample_size=100, split="test", seed=42)

    def test_loads_valid_rows(self):
        rows = [{"article": "A " * 200, "highlights": "Short summary.", "id": "cnn_001"}]
        mock_ds = _make_mock_ds(rows)
        with patch("datasets.load_dataset", return_value=mock_ds):
            assert len(self._loader()._load_dataset()) == 1

    def test_skips_empty_article(self):
        rows = [{"article": "", "highlights": "summary", "id": "cnn_002"}]
        mock_ds = _make_mock_ds(rows)
        with patch("datasets.load_dataset", return_value=mock_ds):
            assert len(self._loader()._load_dataset()) == 0

    def test_skips_empty_highlights(self):
        rows = [{"article": "An article.", "highlights": "", "id": "dm_001"}]
        mock_ds = _make_mock_ds(rows)
        with patch("datasets.load_dataset", return_value=mock_ds):
            assert len(self._loader()._load_dataset()) == 0

    def test_publication_cnn(self):
        rows = [{"article": "A " * 100, "highlights": "s", "id": "cnn_xyz"}]
        mock_ds = _make_mock_ds(rows)
        with patch("datasets.load_dataset", return_value=mock_ds):
            assert self._loader()._load_dataset()[0]["_inferred_attrs"]["publication"] == "cnn"

    def test_publication_dailymail(self):
        rows = [{"article": "B " * 100, "highlights": "s", "id": "dm_abc"}]
        mock_ds = _make_mock_ds(rows)
        with patch("datasets.load_dataset", return_value=mock_ds):
            assert self._loader()._load_dataset()[0]["_inferred_attrs"]["publication"] == "dailymail"

    def test_article_length_short(self):
        rows = [{"article": "word " * 100, "highlights": "s", "id": "cnn_s"}]
        mock_ds = _make_mock_ds(rows)
        with patch("datasets.load_dataset", return_value=mock_ds):
            assert self._loader()._load_dataset()[0]["_inferred_attrs"]["article_length"] == "short"

    def test_article_length_long(self):
        rows = [{"article": "word " * 800, "highlights": "s", "id": "cnn_l"}]
        mock_ds = _make_mock_ds(rows)
        with patch("datasets.load_dataset", return_value=mock_ds):
            assert self._loader()._load_dataset()[0]["_inferred_attrs"]["article_length"] == "long"


class TestCNNDailyMailLoaderToRecord:
    def _loader(self):
        from benchmark.loaders.cnn_dailymail import CNNDailyMailLoader
        return CNNDailyMailLoader(attribute_map={}, sample_size=10, split="test", seed=42)

    def _make_item(self):
        return {"article": "The economy grew. " * 20, "highlights": "Economy grew.",
                "_native_id": "cnn_001", "_inferred_attrs": {"article_length": "medium", "publication": "cnn"}}

    def test_record_has_required_keys(self):
        _assert_phase3_record(self._loader()._to_record(self._make_item(), seq=0))

    def test_benchmark_id_is_cnn_dailymail(self):
        assert self._loader()._to_record(self._make_item(), seq=0)["benchmark_id"] == "cnn_dailymail"

    def test_reference_is_highlights(self):
        item = self._make_item()
        assert self._loader()._to_record(item, seq=0)["reference_response"] == item["highlights"]

    def test_long_article_truncated_in_prompt(self):
        item = self._make_item()
        item["article"] = "x" * 5000
        assert "x" * 5000 not in self._loader()._to_record(item, seq=0)["prompt"]

    def test_task_id_is_news_summarization(self):
        assert self._loader()._to_record(self._make_item(), seq=0)["task_id"] == "news_summarization"


# ===========================================================================
# 12. SAMSumLoader
# ===========================================================================

class TestSAMSumLoaderLoadDataset:
    def _loader(self):
        from benchmark.loaders.samsum import SAMSumLoader
        return SAMSumLoader(attribute_map={}, sample_size=100, split="test", seed=42)

    def test_loads_valid_rows(self):
        rows = [{"dialogue": "Alice: Hi\nBob: Hello", "summary": "They greeted.", "id": "1"}]
        mock_ds = _make_mock_ds(rows)
        with patch("datasets.load_dataset", return_value=mock_ds):
            assert len(self._loader()._load_dataset()) == 1

    def test_skips_empty_dialogue(self):
        rows = [{"dialogue": "", "summary": "s", "id": "2"}]
        mock_ds = _make_mock_ds(rows)
        with patch("datasets.load_dataset", return_value=mock_ds):
            assert len(self._loader()._load_dataset()) == 0

    def test_skips_empty_summary(self):
        rows = [{"dialogue": "A: Hi\nB: Ok", "summary": "", "id": "3"}]
        mock_ds = _make_mock_ds(rows)
        with patch("datasets.load_dataset", return_value=mock_ds):
            assert len(self._loader()._load_dataset()) == 0

    def test_two_speakers_detected(self):
        rows = [{"dialogue": "Alice: Hi\nBob: Hello\nAlice: Bye", "summary": "chat", "id": "4"}]
        mock_ds = _make_mock_ds(rows)
        with patch("datasets.load_dataset", return_value=mock_ds):
            assert self._loader()._load_dataset()[0]["_inferred_attrs"]["num_speakers"] == "two"

    def test_three_plus_speakers_detected(self):
        rows = [{"dialogue": "A: Hi\nB: Hey\nC: Hello\nA: Bye", "summary": "chat", "id": "5"}]
        mock_ds = _make_mock_ds(rows)
        with patch("datasets.load_dataset", return_value=mock_ds):
            assert self._loader()._load_dataset()[0]["_inferred_attrs"]["num_speakers"] == "three_plus"


class TestSAMSumLoaderToRecord:
    def _loader(self):
        from benchmark.loaders.samsum import SAMSumLoader
        return SAMSumLoader(attribute_map={}, sample_size=10, split="test", seed=42)

    def _make_item(self):
        return {"dialogue": "Alice: Hey!\nBob: Hi!", "summary": "They greeted.",
                "_native_id": "1", "_inferred_attrs": {"dialogue_length": "short", "num_speakers": "two"}}

    def test_record_has_required_keys(self):
        _assert_phase3_record(self._loader()._to_record(self._make_item(), seq=0))

    def test_benchmark_id_is_samsum(self):
        assert self._loader()._to_record(self._make_item(), seq=0)["benchmark_id"] == "samsum"

    def test_reference_is_summary(self):
        item = self._make_item()
        assert self._loader()._to_record(item, seq=0)["reference_response"] == item["summary"]

    def test_prompt_contains_dialogue(self):
        item = self._make_item()
        assert item["dialogue"] in self._loader()._to_record(item, seq=0)["prompt"]

    def test_task_id_is_dialogue_summarization(self):
        assert self._loader()._to_record(self._make_item(), seq=0)["task_id"] == "dialogue_summarization"


# ===========================================================================
# 13. FEVERLoader
# ===========================================================================

class TestFEVERLoaderLoadDataset:
    def _loader(self):
        from benchmark.loaders.fever import FEVERLoader
        return FEVERLoader(attribute_map={}, sample_size=100, split="labelled_dev", seed=42)

    def test_loads_valid_supports(self):
        rows = [{"claim": "The Earth orbits the Sun.", "label": "SUPPORTS", "id": 1}]
        mock_ds = _make_mock_ds(rows)
        with patch("datasets.load_dataset", return_value=mock_ds):
            assert self._loader()._load_dataset()[0]["label"] == "SUPPORTS"

    def test_loads_valid_refutes(self):
        rows = [{"claim": "The Sun orbits the Earth.", "label": "REFUTES", "id": 2}]
        mock_ds = _make_mock_ds(rows)
        with patch("datasets.load_dataset", return_value=mock_ds):
            assert self._loader()._load_dataset()[0]["label"] == "REFUTES"

    def test_loads_not_enough_info(self):
        rows = [{"claim": "There are exactly 200 countries.", "label": "NOT ENOUGH INFO", "id": 3}]
        mock_ds = _make_mock_ds(rows)
        with patch("datasets.load_dataset", return_value=mock_ds):
            assert self._loader()._load_dataset()[0]["_inferred_attrs"]["label"] == "not_enough_info"

    def test_skips_invalid_label(self):
        rows = [{"claim": "Something.", "label": "UNKNOWN", "id": 4}]
        mock_ds = _make_mock_ds(rows)
        with patch("datasets.load_dataset", return_value=mock_ds):
            assert len(self._loader()._load_dataset()) == 0

    def test_label_normalised_for_attr(self):
        rows = [{"claim": "The sky is blue.", "label": "SUPPORTS", "id": 5}]
        mock_ds = _make_mock_ds(rows)
        with patch("datasets.load_dataset", return_value=mock_ds):
            assert self._loader()._load_dataset()[0]["_inferred_attrs"]["label"] == "supports"


class TestFEVERLoaderToRecord:
    def _loader(self):
        from benchmark.loaders.fever import FEVERLoader
        return FEVERLoader(attribute_map={}, sample_size=10, split="labelled_dev", seed=42)

    def _make_item(self, label="SUPPORTS"):
        return {"claim": "The Earth is a planet.", "label": label, "_native_id": "1",
                "_inferred_attrs": {"label": label.lower().replace(" ", "_"), "claim_length": "short"}}

    def test_record_has_required_keys(self):
        _assert_phase3_record(self._loader()._to_record(self._make_item(), seq=0))

    def test_benchmark_id_is_fever(self):
        assert self._loader()._to_record(self._make_item(), seq=0)["benchmark_id"] == "fever"

    def test_reference_is_original_label(self):
        assert self._loader()._to_record(self._make_item("REFUTES"), seq=0)["reference_response"] == "REFUTES"

    def test_prompt_contains_claim(self):
        item = self._make_item()
        assert item["claim"] in self._loader()._to_record(item, seq=0)["prompt"]


# ===========================================================================
# 14. SciFactLoader
# ===========================================================================

class TestGetLabelSciFact:
    def _fn(self):
        from benchmark.loaders.scifact import _get_label
        return _get_label

    def test_supports_wins(self):
        assert self._fn()({"doc1": {"label": "SUPPORTS"}}) == "SUPPORTS"

    def test_contradicts_gives_refutes(self):
        assert self._fn()({"doc1": {"label": "CONTRADICTS"}}) == "REFUTES"

    def test_empty_gives_not_enough_info(self):
        assert self._fn()({}) == "NOT ENOUGH INFO"

    def test_supports_beats_contradicts(self):
        assert self._fn()({"a": {"label": "CONTRADICTS"}, "b": {"label": "SUPPORTS"}}) == "SUPPORTS"


class TestSciFactLoaderLoadDataset:
    def _loader(self):
        from benchmark.loaders.scifact import SciFactLoader
        return SciFactLoader(attribute_map={}, sample_size=100, split="train", seed=42)

    def test_loads_valid_rows(self):
        rows = [{"claim": "Vitamin C prevents scurvy.",
                 "evidence": {"doc1": {"label": "SUPPORTS"}}, "id": 1}]
        mock_ds = _make_mock_ds(rows)
        with patch("datasets.load_dataset", return_value=mock_ds):
            assert len(self._loader()._load_dataset()) == 1

    def test_skips_empty_claim(self):
        rows = [{"claim": "", "evidence": {}, "id": 2}]
        mock_ds = _make_mock_ds(rows)
        with patch("datasets.load_dataset", return_value=mock_ds):
            assert len(self._loader()._load_dataset()) == 0

    def test_label_normalised(self):
        rows = [{"claim": "A scientific claim.", "evidence": {}, "id": 3}]
        mock_ds = _make_mock_ds(rows)
        with patch("datasets.load_dataset", return_value=mock_ds):
            assert self._loader()._load_dataset()[0]["_inferred_attrs"]["label"] == "not_enough_info"


class TestSciFactLoaderToRecord:
    def _loader(self):
        from benchmark.loaders.scifact import SciFactLoader
        return SciFactLoader(attribute_map={}, sample_size=10, split="train", seed=42)

    def _make_item(self, label="SUPPORTS"):
        return {"claim": "Aspirin reduces fever.", "label": label, "_native_id": "1",
                "_inferred_attrs": {"label": "supports", "claim_length": "short"}}

    def test_record_has_required_keys(self):
        _assert_phase3_record(self._loader()._to_record(self._make_item(), seq=0))

    def test_benchmark_id_is_scifact(self):
        assert self._loader()._to_record(self._make_item(), seq=0)["benchmark_id"] == "scifact"

    def test_reference_is_original_label(self):
        assert self._loader()._to_record(self._make_item("REFUTES"), seq=0)["reference_response"] == "REFUTES"

    def test_prompt_contains_claim(self):
        item = self._make_item()
        assert item["claim"] in self._loader()._to_record(item, seq=0)["prompt"]


# ===========================================================================
# 15. MGSMLoader
# ===========================================================================

class TestMGSMLoaderLoadDataset:
    def _loader(self):
        from benchmark.loaders.mgsm import MGSMLoader
        return MGSMLoader(attribute_map={}, sample_size=100, split="test", seed=42)

    def test_loads_valid_rows(self):
        rows = [{"question": "3x=12, x=?", "answer": 4},
                {"question": "2+2=?", "answer": 4}]
        mock_ds = _make_mock_ds(rows)
        with patch("datasets.load_dataset", return_value=mock_ds):
            assert len(self._loader()._load_dataset()) == 2

    def test_skips_none_answer(self):
        rows = [{"question": "x=?", "answer": None}]
        mock_ds = _make_mock_ds(rows)
        with patch("datasets.load_dataset", return_value=mock_ds):
            assert len(self._loader()._load_dataset()) == 0

    def test_skips_empty_question(self):
        rows = [{"question": "", "answer": 42}]
        mock_ds = _make_mock_ds(rows)
        with patch("datasets.load_dataset", return_value=mock_ds):
            assert len(self._loader()._load_dataset()) == 0

    def test_answer_converted_to_string(self):
        rows = [{"question": "5+5=?", "answer": 10}]
        mock_ds = _make_mock_ds(rows)
        with patch("datasets.load_dataset", return_value=mock_ds):
            assert self._loader()._load_dataset()[0]["answer"] == "10"

    def test_language_attr_is_en(self):
        rows = [{"question": "5+5=?", "answer": 10}]
        mock_ds = _make_mock_ds(rows)
        with patch("datasets.load_dataset", return_value=mock_ds):
            assert self._loader()._load_dataset()[0]["_inferred_attrs"]["language"] == "en"


class TestMGSMLoaderToRecord:
    def _loader(self):
        from benchmark.loaders.mgsm import MGSMLoader
        return MGSMLoader(attribute_map={}, sample_size=10, split="test", seed=42)

    def _make_item(self):
        return {"question": "5 apples, Alice takes 2. Remain?", "answer": "3",
                "_native_id": "0", "_inferred_attrs": {"language": "en", "difficulty": "medium"}}

    def test_record_has_required_keys(self):
        _assert_phase3_record(self._loader()._to_record(self._make_item(), seq=0))

    def test_benchmark_id_is_mgsm(self):
        assert self._loader()._to_record(self._make_item(), seq=0)["benchmark_id"] == "mgsm"

    def test_task_id_is_multilingual_math(self):
        assert self._loader()._to_record(self._make_item(), seq=0)["task_id"] == "multilingual_math"

    def test_reference_is_answer_string(self):
        assert self._loader()._to_record(self._make_item(), seq=0)["reference_response"] == "3"

    def test_prompt_contains_question(self):
        item = self._make_item()
        assert item["question"] in self._loader()._to_record(item, seq=0)["prompt"]


# ===========================================================================
# 16. MathQALoader
# ===========================================================================

class TestParseOptionsMathQA:
    def _fn(self):
        from benchmark.loaders.mathqa import _parse_options
        return _parse_options

    def test_parses_five_options(self):
        assert self._fn()("a ) 12 , b ) 15 , c ) 18 , d ) 21 , e ) 24") == [
            "12", "15", "18", "21", "24"]

    def test_strips_whitespace(self):
        result = self._fn()("a )  hello  , b )  world , c ) foo , d ) bar , e ) baz")
        assert result[0] == "hello" and result[1] == "world"

    def test_returns_list(self):
        assert isinstance(self._fn()("a ) 1 , b ) 2 , c ) 3 , d ) 4 , e ) 5"), list)


class TestMathQALoaderLoadDataset:
    def _loader(self):
        from benchmark.loaders.mathqa import MathQALoader
        return MathQALoader(attribute_map={}, sample_size=100, split="test", seed=42)

    def test_loads_valid_rows(self):
        rows = [{"Problem": "If x=2, 2x=?",
                 "options": "a ) 2 , b ) 4 , c ) 6 , d ) 8 , e ) 10",
                 "correct": "b", "category": "general"}]
        mock_ds = _make_mock_ds(rows)
        with patch("datasets.load_dataset", return_value=mock_ds):
            assert len(self._loader()._load_dataset()) == 1

    def test_skips_empty_problem(self):
        rows = [{"Problem": "",
                 "options": "a ) 1 , b ) 2 , c ) 3 , d ) 4 , e ) 5",
                 "correct": "a", "category": "general"}]
        mock_ds = _make_mock_ds(rows)
        with patch("datasets.load_dataset", return_value=mock_ds):
            assert len(self._loader()._load_dataset()) == 0

    def test_correct_letter_to_upper(self):
        rows = [{"Problem": "Solve.",
                 "options": "a ) 2 , b ) 4 , c ) 6 , d ) 8 , e ) 10",
                 "correct": "c", "category": "physics"}]
        mock_ds = _make_mock_ds(rows)
        with patch("datasets.load_dataset", return_value=mock_ds):
            assert self._loader()._load_dataset()[0]["correct"] == "C"

    def test_category_normalised(self):
        rows = [{"Problem": "A problem.",
                 "options": "a ) 1 , b ) 2 , c ) 3 , d ) 4 , e ) 5",
                 "correct": "a", "category": "General Physics"}]
        mock_ds = _make_mock_ds(rows)
        with patch("datasets.load_dataset", return_value=mock_ds):
            assert self._loader()._load_dataset()[0]["_inferred_attrs"]["category"] == "general_physics"


class TestMathQALoaderToRecord:
    def _loader(self):
        from benchmark.loaders.mathqa import MathQALoader
        return MathQALoader(attribute_map={}, sample_size=10, split="test", seed=42)

    def _make_item(self):
        return {"problem": "Train: 60 km/h for 2h. Distance?",
                "parsed_opts": ["60 km", "120 km", "180 km", "240 km", "300 km"],
                "correct": "B", "_native_id": "0",
                "_inferred_attrs": {"category": "general", "difficulty": "medium"}}

    def test_record_has_required_keys(self):
        _assert_phase3_record(self._loader()._to_record(self._make_item(), seq=0))

    def test_benchmark_id_is_mathqa(self):
        assert self._loader()._to_record(self._make_item(), seq=0)["benchmark_id"] == "mathqa"

    def test_task_id_is_math_word_problems_mc(self):
        assert self._loader()._to_record(self._make_item(), seq=0)["task_id"] == "math_word_problems_mc"

    def test_reference_is_correct_letter(self):
        assert self._loader()._to_record(self._make_item(), seq=0)["reference_response"] == "B"

    def test_prompt_contains_problem(self):
        item = self._make_item()
        assert item["problem"] in self._loader()._to_record(item, seq=0)["prompt"]

    def test_prompt_contains_options(self):
        item = self._make_item()
        assert "120 km" in self._loader()._to_record(item, seq=0)["prompt"]


# ===========================================================================
# Registry + metric tests
# ===========================================================================

class TestRegistryAndMetrics:
    def test_all_16_loaders_in_registry(self):
        from benchmark.loaders import _REGISTRY
        for name in ["logiqa", "winogrande", "multinli", "copa", "cosmos_qa", "bbq",
                     "trivia_qa", "squad_v2", "nq_open", "narrativeqa",
                     "cnn_dailymail", "samsum", "fever", "scifact", "mgsm", "mathqa"]:
            assert name in _REGISTRY, f"{name!r} missing from _REGISTRY"

    def test_registry_entries_are_two_tuples(self):
        from benchmark.loaders import _REGISTRY
        for name, entry in _REGISTRY.items():
            assert isinstance(entry, tuple) and len(entry) == 2

    def test_attribute_map_files_exist(self):
        from pathlib import Path
        from benchmark.loaders import _REGISTRY
        for name in ["logiqa", "winogrande", "multinli", "copa", "cosmos_qa", "bbq",
                     "trivia_qa", "squad_v2", "nq_open", "narrativeqa",
                     "cnn_dailymail", "samsum", "fever", "scifact", "mgsm", "mathqa"]:
            _, attr_map_path = _REGISTRY[name]
            assert Path(attr_map_path).exists(), f"Missing attr map for {name!r}"

    def test_benchmark_metric_contains_all_16(self):
        from benchmark.compute_scores import BENCHMARK_METRIC
        for name in ["logiqa", "winogrande", "multinli", "copa", "cosmos_qa", "bbq",
                     "trivia_qa", "squad_v2", "nq_open", "narrativeqa",
                     "cnn_dailymail", "samsum", "fever", "scifact", "mgsm", "mathqa"]:
            assert name in BENCHMARK_METRIC, f"{name!r} missing from BENCHMARK_METRIC"

    def test_summarization_loaders_use_bertscore(self):
        from benchmark.compute_scores import BENCHMARK_METRIC
        assert BENCHMARK_METRIC["cnn_dailymail"] == "bertscore"
        assert BENCHMARK_METRIC["samsum"] == "bertscore"

    def test_narrativeqa_uses_bleu(self):
        from benchmark.compute_scores import BENCHMARK_METRIC
        assert BENCHMARK_METRIC["narrativeqa"] == "bleu"

    def test_mcq_loaders_use_exact_match(self):
        from benchmark.compute_scores import BENCHMARK_METRIC
        for name in ["logiqa", "winogrande", "multinli", "copa", "cosmos_qa", "bbq",
                     "trivia_qa", "squad_v2", "nq_open", "fever", "scifact", "mgsm", "mathqa"]:
            assert BENCHMARK_METRIC[name] == "exact_match"
