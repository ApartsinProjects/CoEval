"""Benchmark loader registry.

Usage
-----
    from benchmark.loaders import load_benchmark

    n = load_benchmark(
        dataset="xsum",
        out_path="Runs/paper-eval/phase3_datapoints/text_summarization.benchmark_xsum.datapoints.jsonl",
        sample_size=620,
        split="validation",
    )
    print(f"Wrote {n} records")
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


# Default configs directory, resolved relative to this package file.
_CONFIGS_DIR = Path(__file__).parent.parent / "configs"

# Registry: dataset name -> (loader class, default attribute_map path)
_REGISTRY: dict[str, tuple[str, str]] = {
    "xsum": (
        "benchmark.loaders.xsum.XSumLoader",
        str(_CONFIGS_DIR / "xsum_attribute_map.yaml"),
    ),
    "codesearchnet": (
        "benchmark.loaders.codesearchnet.CodeSearchNetLoader",
        str(_CONFIGS_DIR / "codesearchnet_attribute_map.yaml"),
    ),
    "aeslc": (
        "benchmark.loaders.aeslc.AESLCLoader",
        str(_CONFIGS_DIR / "aeslc_attribute_map.yaml"),
    ),
    "wikitablequestions": (
        "benchmark.loaders.wikitablequestions.WikiTableQuestionsLoader",
        str(_CONFIGS_DIR / "wikitablequestions_attribute_map.yaml"),
    ),
    # --- Education domain ---
    "arc_challenge": (
        "benchmark.loaders.arc_challenge.ARCChallengeLoader",
        str(_CONFIGS_DIR / "arc_challenge_attribute_map.yaml"),
    ),
    "race": (
        "benchmark.loaders.race.RACELoader",
        str(_CONFIGS_DIR / "race_attribute_map.yaml"),
    ),
    "sciq": (
        "benchmark.loaders.sciq.SciQLoader",
        str(_CONFIGS_DIR / "sciq_attribute_map.yaml"),
    ),
    # --- Reasoning / Logic ---
    "bigbench_hard": (
        "benchmark.loaders.bigbench_hard.BigBenchHardLoader",
        str(_CONFIGS_DIR / "bigbench_hard_attribute_map.yaml"),
    ),
    # --- Mathematics ---
    "math": (
        "benchmark.loaders.math_dataset.MATHLoader",
        str(_CONFIGS_DIR / "math_attribute_map.yaml"),
    ),
    # --- Code generation ---
    "mbpp": (
        "benchmark.loaders.mbpp.MBPPLoader",
        str(_CONFIGS_DIR / "mbpp_attribute_map.yaml"),
    ),
    # --- MCQ / Reasoning ---
    "logiqa": (
        "benchmark.loaders.logiqa.LogiQALoader",
        str(_CONFIGS_DIR / "logiqa_attribute_map.yaml"),
    ),
    "winogrande": (
        "benchmark.loaders.winogrande.WinograndeLoader",
        str(_CONFIGS_DIR / "winogrande_attribute_map.yaml"),
    ),
    "multinli": (
        "benchmark.loaders.multinli.MultiNLILoader",
        str(_CONFIGS_DIR / "multinli_attribute_map.yaml"),
    ),
    "copa": (
        "benchmark.loaders.copa.COPALoader",
        str(_CONFIGS_DIR / "copa_attribute_map.yaml"),
    ),
    "cosmos_qa": (
        "benchmark.loaders.cosmos_qa.CosmosQALoader",
        str(_CONFIGS_DIR / "cosmos_qa_attribute_map.yaml"),
    ),
    "bbq": (
        "benchmark.loaders.bbq.BBQLoader",
        str(_CONFIGS_DIR / "bbq_attribute_map.yaml"),
    ),
    "trivia_qa": (
        "benchmark.loaders.trivia_qa.TriviaQALoader",
        str(_CONFIGS_DIR / "trivia_qa_attribute_map.yaml"),
    ),
    "squad_v2": (
        "benchmark.loaders.squad_v2.SQuADv2Loader",
        str(_CONFIGS_DIR / "squad_v2_attribute_map.yaml"),
    ),
    # --- Open-domain QA ---
    "nq_open": (
        "benchmark.loaders.nq_open.NQOpenLoader",
        str(_CONFIGS_DIR / "nq_open_attribute_map.yaml"),
    ),
    # --- Reading Comprehension ---
    "narrativeqa": (
        "benchmark.loaders.narrativeqa.NarrativeQALoader",
        str(_CONFIGS_DIR / "narrativeqa_attribute_map.yaml"),
    ),
    # --- Summarization ---
    "cnn_dailymail": (
        "benchmark.loaders.cnn_dailymail.CNNDailyMailLoader",
        str(_CONFIGS_DIR / "cnn_dailymail_attribute_map.yaml"),
    ),
    "samsum": (
        "benchmark.loaders.samsum.SAMSumLoader",
        str(_CONFIGS_DIR / "samsum_attribute_map.yaml"),
    ),
    # --- Fact Verification ---
    "fever": (
        "benchmark.loaders.fever.FEVERLoader",
        str(_CONFIGS_DIR / "fever_attribute_map.yaml"),
    ),
    "scifact": (
        "benchmark.loaders.scifact.SciFactLoader",
        str(_CONFIGS_DIR / "scifact_attribute_map.yaml"),
    ),
    # --- Math (additional) ---
    "mgsm": (
        "benchmark.loaders.mgsm.MGSMLoader",
        str(_CONFIGS_DIR / "mgsm_attribute_map.yaml"),
    ),
    "mathqa": (
        "benchmark.loaders.mathqa.MathQALoader",
        str(_CONFIGS_DIR / "mathqa_attribute_map.yaml"),
    ),
}


def list_datasets() -> list[str]:
    """Return registered dataset names."""
    return list(_REGISTRY.keys())


def load_benchmark(
    dataset: str,
    out_path: str | Path,
    attribute_map_path: str | Path | None = None,
    sample_size: int = 620,
    split: str | None = None,
    seed: int = 42,
    **loader_kwargs: Any,
) -> int:
    """Download *dataset*, sample *sample_size* items, and write JSONL.

    Parameters
    ----------
    dataset:
        Registered dataset name (e.g. "xsum", "codesearchnet").
    out_path:
        Destination JSONL file path.
    attribute_map_path:
        YAML file mapping attribute names to allowed values.
        Defaults to the path registered for the dataset.
    sample_size:
        Number of items to emit.
    split:
        Dataset split (e.g. "validation", "test").
    seed:
        Random seed for stratified sampling.
    **loader_kwargs:
        Extra keyword arguments forwarded to the loader constructor
        (e.g. ``language="python"`` for CodeSearchNet).

    Returns
    -------
    int
        Number of records written.
    """
    if dataset not in _REGISTRY:
        raise ValueError(
            f"Unknown dataset '{dataset}'. "
            f"Available: {list(_REGISTRY.keys())}"
        )

    cls_path, default_map_path = _REGISTRY[dataset]

    # Resolve attribute map
    map_path = Path(attribute_map_path) if attribute_map_path else Path(default_map_path)
    attribute_map: dict[str, list[str]] = {}
    if map_path.exists():
        with open(map_path, encoding="utf-8") as fh:
            attribute_map = yaml.safe_load(fh) or {}

    # Dynamically import loader class
    module_path, cls_name = cls_path.rsplit(".", 1)
    import importlib
    module = importlib.import_module(module_path)
    LoaderClass = getattr(module, cls_name)

    loader = LoaderClass(
        attribute_map=attribute_map,
        sample_size=sample_size,
        split=split,
        seed=seed,
        **loader_kwargs,
    )
    return loader.emit(out_path)
