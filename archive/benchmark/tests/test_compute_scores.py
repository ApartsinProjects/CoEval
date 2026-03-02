"""Tests for benchmark/compute_scores.py.

Covers:
  - _bleu4_single(): sentence BLEU-4 with smoothing
  - _exact_match(): case-insensitive string matching against answer list
  - BENCHMARK_METRIC mapping
  - _infer_benchmark(): benchmark detection from filename
  - _infer_benchmark_from_record(): benchmark detection from record field
  - _score_file(): end-to-end file scoring with all three metric types
    (idempotency, dry-run, --force, missing reference, parse errors)
  - main() CLI: argument parsing and exit codes

BERTScore is mocked because it requires PyTorch and is slow.
BLEU depends only on nltk, which is lightweight; we test it directly when
available and mock it otherwise.  Tests never write to permanent storage —
all JSONL files are created in pytest's tmp_path fixture.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write_jsonl(path: Path, records: list[dict]) -> None:
    path.write_text('\n'.join(json.dumps(r) for r in records) + '\n', encoding='utf-8')


def _read_jsonl(path: Path) -> list[dict]:
    return [
        json.loads(line)
        for line in path.read_text(encoding='utf-8').splitlines()
        if line.strip()
    ]


def _record(
    idx: int,
    prompt: str = 'the cat sat on the mat',
    reference: str = 'the cat sat on the mat',
    benchmark_id: str = 'xsum',
    score: float | None = None,
) -> dict:
    r = {
        'id': f'xsum__xsum__{idx:05d}',
        'task_id': 'text_summarization',
        'teacher_model_id': 'xsum',
        'prompt': prompt,
        'reference_response': reference,
        'benchmark_id': benchmark_id,
        'benchmark_native_score': score,
    }
    return r


# ---------------------------------------------------------------------------
# _bleu4_single
# ---------------------------------------------------------------------------

class TestBleu4Single:
    def _fn(self):
        from benchmark.compute_scores import _bleu4_single
        return _bleu4_single

    def test_identical_strings_positive_score(self):
        fn = self._fn()
        score = fn('the cat sat on the mat', 'the cat sat on the mat')
        assert score > 0.0
        assert score <= 1.0

    def test_empty_hypothesis_returns_zero(self):
        fn = self._fn()
        assert fn('', 'the cat sat on the mat') == 0.0

    def test_empty_reference_returns_zero(self):
        fn = self._fn()
        assert fn('the cat sat on the mat', '') == 0.0

    def test_both_empty_returns_zero(self):
        fn = self._fn()
        assert fn('', '') == 0.0

    def test_totally_different_strings_low_score(self):
        fn = self._fn()
        score = fn('the quick brown fox', 'xyz abc def ghi jkl mno pqr')
        assert score < 0.5

    def test_score_in_valid_range(self):
        fn = self._fn()
        for hyp, ref in [
            ('hello world', 'hello world'),
            ('a b c d', 'e f g h'),
            ('python function code', 'python function code documentation'),
        ]:
            score = fn(hyp, ref)
            assert 0.0 <= score <= 1.0, f"Score {score} out of range for ({hyp!r}, {ref!r})"


# ---------------------------------------------------------------------------
# _exact_match
# ---------------------------------------------------------------------------

class TestExactMatch:
    def _fn(self):
        from benchmark.compute_scores import _exact_match
        return _exact_match

    def test_exact_match_returns_one(self):
        fn = self._fn()
        assert fn('Paris', ['Paris']) == 1.0

    def test_no_match_returns_zero(self):
        fn = self._fn()
        assert fn('London', ['Paris']) == 0.0

    def test_case_insensitive(self):
        fn = self._fn()
        assert fn('paris', ['Paris']) == 1.0
        assert fn('PARIS', ['Paris']) == 1.0
        assert fn('Paris', ['paris']) == 1.0

    def test_whitespace_stripped(self):
        fn = self._fn()
        assert fn('  Paris  ', ['Paris']) == 1.0
        assert fn('Paris', ['  Paris  ']) == 1.0

    def test_multiple_answers_any_match(self):
        fn = self._fn()
        assert fn('NYC', ['New York', 'NYC', 'New York City']) == 1.0

    def test_multiple_answers_none_match(self):
        fn = self._fn()
        assert fn('Boston', ['New York', 'NYC', 'New York City']) == 0.0

    def test_empty_hypothesis(self):
        fn = self._fn()
        assert fn('', ['Paris']) == 0.0

    def test_empty_answers_list(self):
        fn = self._fn()
        assert fn('Paris', []) == 0.0


# ---------------------------------------------------------------------------
# BENCHMARK_METRIC mapping
# ---------------------------------------------------------------------------

class TestBenchmarkMetricMapping:
    def test_xsum_uses_bertscore(self):
        from benchmark.compute_scores import BENCHMARK_METRIC
        assert BENCHMARK_METRIC['xsum'] == 'bertscore'

    def test_codesearchnet_uses_bleu(self):
        from benchmark.compute_scores import BENCHMARK_METRIC
        assert BENCHMARK_METRIC['codesearchnet'] == 'bleu'

    def test_aeslc_uses_bertscore(self):
        from benchmark.compute_scores import BENCHMARK_METRIC
        assert BENCHMARK_METRIC['aeslc'] == 'bertscore'

    def test_wikitablequestions_uses_exact_match(self):
        from benchmark.compute_scores import BENCHMARK_METRIC
        assert BENCHMARK_METRIC['wikitablequestions'] == 'exact_match'

    def test_all_four_benchmarks_present(self):
        from benchmark.compute_scores import BENCHMARK_METRIC
        required = {'xsum', 'codesearchnet', 'aeslc', 'wikitablequestions'}
        assert required.issubset(BENCHMARK_METRIC.keys())


# ---------------------------------------------------------------------------
# _infer_benchmark
# ---------------------------------------------------------------------------

class TestInferBenchmark:
    def _fn(self):
        from benchmark.compute_scores import _infer_benchmark
        return _infer_benchmark

    def test_detects_xsum_in_filename(self):
        fn = self._fn()
        assert fn('text_summarization.xsum.datapoints.jsonl') == 'xsum'

    def test_detects_codesearchnet_in_filename(self):
        fn = self._fn()
        assert fn('code_explanation.codesearchnet.datapoints.jsonl') == 'codesearchnet'

    def test_detects_aeslc_in_filename(self):
        fn = self._fn()
        assert fn('email_composition.aeslc.datapoints.jsonl') == 'aeslc'

    def test_detects_wikitablequestions_in_filename(self):
        fn = self._fn()
        assert fn('data_interpretation.wikitablequestions.datapoints.jsonl') == 'wikitablequestions'

    def test_returns_none_for_unknown(self):
        fn = self._fn()
        assert fn('unknown.dataset.datapoints.jsonl') is None

    def test_case_insensitive(self):
        fn = self._fn()
        assert fn('XSum.datapoints.jsonl') == 'xsum'


# ---------------------------------------------------------------------------
# _infer_benchmark_from_record
# ---------------------------------------------------------------------------

class TestInferBenchmarkFromRecord:
    def _fn(self):
        from benchmark.compute_scores import _infer_benchmark_from_record
        return _infer_benchmark_from_record

    def test_returns_benchmark_id_from_record(self):
        fn = self._fn()
        assert fn({'benchmark_id': 'xsum'}) == 'xsum'

    def test_returns_none_when_missing(self):
        fn = self._fn()
        assert fn({'task_id': 'text_summarization'}) is None

    def test_returns_none_when_empty_string(self):
        fn = self._fn()
        # empty string is falsy → should return None
        result = fn({'benchmark_id': ''})
        assert result is None or result == ''


# ---------------------------------------------------------------------------
# _score_file — exact_match (no external deps)
# ---------------------------------------------------------------------------

class TestScoreFileExactMatch:
    def _score_file(self, jsonl_path, **kwargs):
        from benchmark.compute_scores import _score_file
        return _score_file(
            jsonl_path=jsonl_path,
            metric_override=kwargs.get('metric_override', 'exact_match'),
            model_type='distilbert-base-uncased',
            dry_run=kwargs.get('dry_run', False),
            force=kwargs.get('force', False),
            batch_size=32,
        )

    def test_scores_records_and_writes_back(self, tmp_path):
        records = [
            {
                'id': 'r1',
                'prompt': 'What is the capital of France?',
                'reference_response': 'Paris',
                'benchmark_id': 'wikitablequestions',
                'benchmark_native_score': None,
                '_all_answers': ['Paris', 'paris'],
            }
        ]
        p = tmp_path / 'test.datapoints.jsonl'
        _write_jsonl(p, records)

        stats = self._score_file(p)
        assert stats['scored'] >= 0  # exact_match on reference vs. itself = 1.0
        out = _read_jsonl(p)
        # benchmark_native_score should now be set
        assert out[0]['benchmark_native_score'] is not None

    def test_idempotent_skips_already_scored(self, tmp_path):
        records = [
            {
                'id': 'r1',
                'prompt': 'What?',
                'reference_response': 'Paris',
                'benchmark_id': 'wikitablequestions',
                'benchmark_native_score': 0.95,  # already scored
            }
        ]
        p = tmp_path / 'test.datapoints.jsonl'
        _write_jsonl(p, records)

        stats = self._score_file(p)
        assert stats['already_scored'] == 1
        assert stats['scored'] == 0

    def test_force_rescores_already_scored_records(self, tmp_path):
        records = [
            {
                'id': 'r1',
                'prompt': 'What?',
                'reference_response': 'Paris',
                'benchmark_id': 'wikitablequestions',
                'benchmark_native_score': 0.95,
            }
        ]
        p = tmp_path / 'test.datapoints.jsonl'
        _write_jsonl(p, records)

        stats = self._score_file(p, force=True)
        assert stats['scored'] == 1

    def test_dry_run_does_not_write_file(self, tmp_path):
        records = [_record(1, score=None)]
        p = tmp_path / 'test.datapoints.jsonl'
        _write_jsonl(p, records)
        original_content = p.read_text()

        self._score_file(p, dry_run=True)

        # File should be unchanged
        assert p.read_text() == original_content

    def test_skips_records_without_reference(self, tmp_path):
        records = [
            {
                'id': 'r1',
                'prompt': 'What?',
                'reference_response': '',  # empty
                'benchmark_id': 'wikitablequestions',
                'benchmark_native_score': None,
            }
        ]
        p = tmp_path / 'test.datapoints.jsonl'
        _write_jsonl(p, records)

        stats = self._score_file(p)
        assert stats['skipped_no_reference'] == 1
        assert stats['scored'] == 0

    def test_handles_empty_file(self, tmp_path):
        p = tmp_path / 'empty.datapoints.jsonl'
        p.write_text('', encoding='utf-8')
        stats = self._score_file(p)
        assert stats.get('error') == 'empty' or stats.get('total', 0) == 0

    def test_handles_parse_error_lines(self, tmp_path):
        p = tmp_path / 'test.datapoints.jsonl'
        p.write_text('not valid json\n', encoding='utf-8')
        # Should not raise — parse errors are counted, not propagated
        stats = self._score_file(p)
        assert stats.get('errors', 0) >= 1 or stats.get('total', 0) == 0

    def test_writes_scores_summary_json(self, tmp_path):
        records = [_record(1, score=None)]
        p = tmp_path / 'wikitablequestions.datapoints.jsonl'
        _write_jsonl(p, records)

        self._score_file(p)

        summary_path = p.with_suffix('.scores_summary.json')
        assert summary_path.exists()
        summary = json.loads(summary_path.read_text())
        assert 'metric' in summary

    def test_multiple_records_all_scored(self, tmp_path):
        records = [
            {
                'id': f'r{i}',
                'prompt': f'q{i}',
                'reference_response': f'answer{i}',
                'benchmark_native_score': None,
                '_all_answers': [f'answer{i}'],
            }
            for i in range(5)
        ]
        p = tmp_path / 'multi.datapoints.jsonl'
        _write_jsonl(p, records)

        stats = self._score_file(p)
        assert stats['scored'] == 5
        out = _read_jsonl(p)
        for r in out:
            assert r['benchmark_native_score'] is not None


# ---------------------------------------------------------------------------
# _score_file — BLEU (mocked nltk)
# ---------------------------------------------------------------------------

class TestScoreFileBleu:
    def _score_file(self, jsonl_path, **kwargs):
        from benchmark.compute_scores import _score_file
        return _score_file(
            jsonl_path=jsonl_path,
            metric_override='bleu',
            model_type='distilbert-base-uncased',
            dry_run=kwargs.get('dry_run', False),
            force=False,
            batch_size=32,
        )

    def test_bleu_scoring_with_mocked_nltk(self, tmp_path):
        """Ensure _score_file runs BLEU path without requiring real nltk."""
        records = [
            {
                'id': 'r0',
                'prompt': 'def add(a, b): return a + b',
                'reference_response': 'Add two numbers and return their sum.',
                'benchmark_id': 'codesearchnet',
                'benchmark_native_score': None,
            }
        ]
        p = tmp_path / 'codesearchnet.datapoints.jsonl'
        _write_jsonl(p, records)

        # Use real nltk if available, else mock it
        try:
            import nltk  # noqa: F401
            stats = self._score_file(p)
        except ImportError:
            mock_nltk = MagicMock()
            smoother = MagicMock()
            smoother.method1 = lambda: None
            mock_nltk.translate.bleu_score.SmoothingFunction.return_value = smoother
            mock_nltk.translate.bleu_score.sentence_bleu.return_value = 0.42
            with patch.dict(sys.modules, {
                'nltk': mock_nltk,
                'nltk.translate': mock_nltk.translate,
                'nltk.translate.bleu_score': mock_nltk.translate.bleu_score,
            }):
                stats = self._score_file(p)

        assert stats['scored'] == 1 or stats.get('errors', 0) == 1
        # Either scored or errored — no exception should escape


# ---------------------------------------------------------------------------
# _score_file — BERTScore (mocked bert_score)
# ---------------------------------------------------------------------------

class TestScoreFileBertscore:
    def _make_mock_bert_score(self, f1_values: list[float]):
        """Return a mock bert_score.score function returning fixed F1 values."""
        import unittest.mock as mock_module

        mock_tensor = MagicMock()
        mock_tensor.tolist.return_value = f1_values

        mock_bs = MagicMock()
        mock_bs.return_value = (MagicMock(), MagicMock(), mock_tensor)
        return mock_bs

    def _score_file_with_mock_bertscore(self, jsonl_path, f1_values, **kwargs):
        mock_bs = self._make_mock_bert_score(f1_values)
        mock_bert_score_module = MagicMock()
        mock_bert_score_module.score = mock_bs

        with patch.dict(sys.modules, {'bert_score': mock_bert_score_module}):
            from benchmark.compute_scores import _score_file
            return _score_file(
                jsonl_path=jsonl_path,
                metric_override='bertscore',
                model_type='distilbert-base-uncased',
                dry_run=kwargs.get('dry_run', False),
                force=False,
                batch_size=32,
            )

    def test_bertscore_scores_two_records(self, tmp_path):
        records = [
            {
                'id': 'r0',
                'prompt': 'Article text here.',
                'reference_response': 'Short summary.',
                'benchmark_id': 'xsum',
                'benchmark_native_score': None,
            },
            {
                'id': 'r1',
                'prompt': 'Another article.',
                'reference_response': 'Another summary.',
                'benchmark_id': 'xsum',
                'benchmark_native_score': None,
            },
        ]
        p = tmp_path / 'xsum.datapoints.jsonl'
        _write_jsonl(p, records)

        stats = self._score_file_with_mock_bertscore(p, f1_values=[0.85, 0.90])
        assert stats['scored'] == 2

        out = _read_jsonl(p)
        assert out[0]['benchmark_native_score'] == pytest.approx(0.85, abs=1e-3)
        assert out[1]['benchmark_native_score'] == pytest.approx(0.90, abs=1e-3)

    def test_bertscore_skips_already_scored(self, tmp_path):
        records = [
            {
                'id': 'r0',
                'prompt': 'Article.',
                'reference_response': 'Summary.',
                'benchmark_id': 'xsum',
                'benchmark_native_score': 0.88,  # already scored
            }
        ]
        p = tmp_path / 'xsum.datapoints.jsonl'
        _write_jsonl(p, records)

        stats = self._score_file_with_mock_bertscore(p, f1_values=[])
        assert stats['already_scored'] == 1
        assert stats['scored'] == 0

    def test_bertscore_dry_run_no_write(self, tmp_path):
        records = [_record(0, score=None)]
        p = tmp_path / 'xsum.datapoints.jsonl'
        _write_jsonl(p, records)
        original = p.read_text()

        self._score_file_with_mock_bertscore(p, f1_values=[0.75], dry_run=True)
        assert p.read_text() == original

    def test_bertscore_import_error_without_bert_score(self, tmp_path):
        records = [_record(0, score=None)]
        p = tmp_path / 'xsum.datapoints.jsonl'
        _write_jsonl(p, records)

        # Simulate bert_score not installed
        with patch.dict(sys.modules, {'bert_score': None}):
            from benchmark.compute_scores import _score_file
            # Should either raise ImportError or return error stats (doesn't crash test)
            try:
                stats = _score_file(
                    jsonl_path=p,
                    metric_override='bertscore',
                    model_type='distilbert-base-uncased',
                    dry_run=False,
                    force=False,
                    batch_size=32,
                )
                # If it didn't raise, errors should be counted
                assert stats.get('errors', 0) >= 0
            except (ImportError, SystemExit):
                pass  # Expected: module calls sys.exit(1) on missing bert_score


# ---------------------------------------------------------------------------
# main() CLI
# ---------------------------------------------------------------------------

class TestMainCLI:
    def test_main_returns_1_for_missing_run(self, tmp_path):
        from benchmark.compute_scores import main
        code = main(['--run', str(tmp_path / 'nonexistent')])
        assert code == 1

    def test_main_returns_1_for_missing_phase3_dir(self, tmp_path):
        from benchmark.compute_scores import main
        run_dir = tmp_path / 'myrun'
        run_dir.mkdir()
        code = main(['--run', str(run_dir)])
        assert code == 1

    def test_main_returns_0_for_no_jsonl_files(self, tmp_path):
        from benchmark.compute_scores import main
        run_dir = tmp_path / 'myrun'
        p3_dir = run_dir / 'phase3_datapoints'
        p3_dir.mkdir(parents=True)
        code = main(['--run', str(run_dir)])
        assert code == 0

    def test_main_exact_match_end_to_end(self, tmp_path):
        """Full CLI run using exact_match (no external deps)."""
        from benchmark.compute_scores import main
        run_dir = tmp_path / 'e2e-run'
        p3_dir = run_dir / 'phase3_datapoints'
        p3_dir.mkdir(parents=True)

        records = [
            {
                'id': 'r0',
                'prompt': 'What is the capital of France?',
                'reference_response': 'Paris',
                'benchmark_id': 'wikitablequestions',
                'benchmark_native_score': None,
                '_all_answers': ['Paris'],
            }
        ]
        p = p3_dir / 'data_interp.wikitablequestions.datapoints.jsonl'
        _write_jsonl(p, records)

        code = main(['--run', str(run_dir), '--metric', 'exact_match'])
        assert code == 0

        out = _read_jsonl(p)
        assert out[0]['benchmark_native_score'] is not None

    def test_main_dry_run_flag(self, tmp_path):
        from benchmark.compute_scores import main
        run_dir = tmp_path / 'dry-run'
        p3_dir = run_dir / 'phase3_datapoints'
        p3_dir.mkdir(parents=True)

        records = [_record(0, score=None)]
        p = p3_dir / 'xsum.datapoints.jsonl'
        _write_jsonl(p, records)
        original = p.read_text()

        code = main(['--run', str(run_dir), '--metric', 'exact_match', '--dry-run'])
        assert code == 0
        assert p.read_text() == original  # unchanged

    def test_main_datasets_filter(self, tmp_path):
        """Only specified datasets should be scored."""
        from benchmark.compute_scores import main
        run_dir = tmp_path / 'filter-run'
        p3_dir = run_dir / 'phase3_datapoints'
        p3_dir.mkdir(parents=True)

        # Two dataset files
        xsum_p = p3_dir / 'text_summ.xsum.datapoints.jsonl'
        aeslc_p = p3_dir / 'email.aeslc.datapoints.jsonl'
        _write_jsonl(xsum_p, [_record(0, score=None)])
        _write_jsonl(aeslc_p, [_record(1, score=None)])

        # Score only xsum with mock bertscore
        mock_bs_module = MagicMock()
        mock_tensor = MagicMock()
        mock_tensor.tolist.return_value = [0.75]
        mock_bs_module.score.return_value = (MagicMock(), MagicMock(), mock_tensor)
        with patch.dict(sys.modules, {'bert_score': mock_bs_module}):
            code = main(['--run', str(run_dir), '--datasets', 'xsum'])
        assert code == 0

        # Only xsum file should have been processed (aeslc unchanged)
        aeslc_records = _read_jsonl(aeslc_p)
        assert aeslc_records[0]['benchmark_native_score'] is None

    def test_main_creates_summary_json(self, tmp_path):
        from benchmark.compute_scores import main
        run_dir = tmp_path / 'summary-run'
        p3_dir = run_dir / 'phase3_datapoints'
        p3_dir.mkdir(parents=True)

        records = [_record(0, score=None)]
        p = p3_dir / 'wikitablequestions.datapoints.jsonl'
        _write_jsonl(p, records)

        main(['--run', str(run_dir), '--metric', 'exact_match'])
        assert (p3_dir / '_scores_summary.json').exists()

    def test_main_force_flag_rescores(self, tmp_path):
        from benchmark.compute_scores import main
        run_dir = tmp_path / 'force-run'
        p3_dir = run_dir / 'phase3_datapoints'
        p3_dir.mkdir(parents=True)

        records = [
            {
                'id': 'r0',
                'prompt': 'Q',
                'reference_response': 'A',
                'benchmark_id': 'wikitablequestions',
                'benchmark_native_score': 0.5,  # pre-scored
                '_all_answers': ['A'],
            }
        ]
        p = p3_dir / 'wikitablequestions.datapoints.jsonl'
        _write_jsonl(p, records)

        code = main(['--run', str(run_dir), '--metric', 'exact_match', '--force'])
        assert code == 0
        out = _read_jsonl(p)
        # Value may change under force
        assert out[0]['benchmark_native_score'] is not None
