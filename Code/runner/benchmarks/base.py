"""Abstract base class for benchmark adapters."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterator


@dataclass
class BenchmarkItem:
    """Single item from a benchmark, normalised into CoEval format."""

    id: str
    """Stable unique identifier within the benchmark (e.g. 'mmlu-0042')."""

    prompt: str
    """The question / problem text shown to student models."""

    reference_answer: str | None = None
    """Gold-standard answer text (for judge evaluation / display)."""

    target_attributes: dict[str, str] = field(default_factory=dict)
    """
    Structured metadata encoded as sampled_target_attributes.

    For MCQ benchmarks: {'correct_answer': 'B', 'subject': 'astronomy'}
    For open-ended:     {'difficulty': 'hard', 'category': 'algebra'}

    When 'correct_answer' (or another label_attribute) is present AND the
    task is configured with label_attributes, Phase 5 performs judge-free
    exact-match evaluation instead of LLM judging.
    """

    metadata: dict[str, Any] = field(default_factory=dict)
    """Adapter-specific extra fields (not written to EES, for debugging)."""


class BenchmarkAdapter(ABC):
    """Convert a downloaded benchmark dataset into CoEval BenchmarkItems."""

    # --------------------------------------------------------------------------
    # Class-level metadata — override in every subclass
    # --------------------------------------------------------------------------
    name: str = ''
    """Short identifier used as teacher_model_id and in file names."""

    description: str = ''
    """One-line human description of the benchmark."""

    task_name: str = ''
    """CoEval task name that will be created in the experiment config."""

    output_description: str = ''
    """What student models should produce (shown in phase-4 prompt)."""

    homepage: str = ''
    """URL for reference / attribution."""

    default_split: str = 'test'
    """Default split name used when no split is specified in ``load()``."""

    benchmark_metric: str | None = None
    """Default metric for this benchmark (e.g. ``"bertscore"``, ``"bleu"``,
    ``"exact_match"``).

    When set, ``coeval ingest`` will automatically inject the corresponding
    metric factor into the task rubric and add a metric judge model to the
    config.  Set to ``None`` (default) for benchmarks that rely on
    ``label_eval`` or LLM-only judging.

    The value must be one of the metrics defined in
    ``runner.metric_judge.SUPPORTED_METRICS``.
    """

    # --------------------------------------------------------------------------
    # Abstract interface
    # --------------------------------------------------------------------------

    @abstractmethod
    def load(self, data_dir: Path, split: str = 'test') -> Iterator[BenchmarkItem]:
        """
        Yield BenchmarkItems from *data_dir / name / split.jsonl* (or
        equivalent).  If the file does not exist raise FileNotFoundError.
        """
        ...

    @abstractmethod
    def get_rubric(self) -> dict[str, str]:
        """
        Return the rubric dict {aspect: description} for this benchmark task.

        For judge-free MCQ benchmarks a minimal rubric is still required
        because Phase 5 may also run LLM judges in addition to label eval.
        """
        ...

    def get_target_attribute_schema(self) -> dict[str, list[str]]:
        """
        Return the full domain of each target attribute, e.g.::

            {'correct_answer': ['A', 'B', 'C', 'D'], 'subject': [...]}

        Used to write the Phase-1 target_attrs.json file.
        Override when the schema is known statically; the default returns {}.
        """
        return {}

    def get_label_attributes(self) -> list[str]:
        """
        Return attribute names that enable judge-free exact-match evaluation.

        Defaults to [] (always use LLM judges).
        For MCQ benchmarks return ['correct_answer'] or similar.
        """
        return []

    def uses_label_eval(self) -> bool:
        """True when this benchmark supports judge-free label evaluation."""
        return bool(self.get_label_attributes())

    # --------------------------------------------------------------------------
    # Helpers
    # --------------------------------------------------------------------------

    def _jsonl_path(self, data_dir: Path, split: str) -> Path:
        return data_dir / self.name / f'{split}.jsonl'

    def _iter_jsonl(self, path: Path) -> Iterator[dict]:
        import json
        if not path.exists():
            raise FileNotFoundError(
                f"Benchmark data not found at {path}. "
                f"Run `python stdbenchmarks/download_benchmarks.py` first."
            )
        with open(path, encoding='utf-8') as fh:
            for line in fh:
                line = line.strip()
                if line:
                    yield json.loads(line)
