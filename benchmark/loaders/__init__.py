"""Benchmark loader registry.

Usage
-----
    from benchmark.loaders import load_benchmark

    n = load_benchmark(
        dataset="xsum",
        out_path="benchmark/runs/paper-eval/phase3_datapoints/text_summarization.benchmark_xsum.datapoints.jsonl",
        attribute_map_path="benchmark/configs/xsum_attribute_map.yaml",
        sample_size=620,
        split="validation",
    )
    print(f"Wrote {n} records")
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


# Registry: dataset name -> (loader class, default attribute_map path)
_REGISTRY: dict[str, tuple[str, str]] = {
    "xsum": (
        "benchmark.loaders.xsum.XSumLoader",
        "benchmark/configs/xsum_attribute_map.yaml",
    ),
    "codesearchnet": (
        "benchmark.loaders.codesearchnet.CodeSearchNetLoader",
        "benchmark/configs/codesearchnet_attribute_map.yaml",
    ),
    "aeslc": (
        "benchmark.loaders.aeslc.AESLCLoader",
        "benchmark/configs/aeslc_attribute_map.yaml",
    ),
    "wikitablequestions": (
        "benchmark.loaders.wikitablequestions.WikiTableQuestionsLoader",
        "benchmark/configs/wikitablequestions_attribute_map.yaml",
    ),
    # --- Education domain ---
    "arc_challenge": (
        "benchmark.loaders.arc_challenge.ARCChallengeLoader",
        "benchmark/configs/arc_challenge_attribute_map.yaml",
    ),
    "race": (
        "benchmark.loaders.race.RACELoader",
        "benchmark/configs/race_attribute_map.yaml",
    ),
    "sciq": (
        "benchmark.loaders.sciq.SciQLoader",
        "benchmark/configs/sciq_attribute_map.yaml",
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
