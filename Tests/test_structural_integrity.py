"""Structural integrity tests for the refactored CoEval repository layout.

Verifies:
- New package directories exist and are importable
- Key path constants resolve to real files
- CLI entry point is functional
- Runs/ subdirs have their YAML configs
- Config/ has required files
"""
from __future__ import annotations
import importlib
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).parent.parent


# ---------------------------------------------------------------------------
# Directory structure
# ---------------------------------------------------------------------------

class TestDirectories:
    def test_code_runner_exists(self):
        assert (ROOT / "Code" / "runner").is_dir()

    def test_code_analyzer_exists(self):
        assert (ROOT / "Code" / "analyzer").is_dir()

    def test_public_benchmark_exists(self):
        assert (ROOT / "Public" / "benchmark").is_dir()

    def test_config_dir_exists(self):
        assert (ROOT / "Config").is_dir()

    def test_tests_runner_exists(self):
        assert (ROOT / "Tests" / "runner").is_dir()

    def test_tests_benchmark_exists(self):
        assert (ROOT / "Tests" / "benchmark").is_dir()

    def test_tests_analyzer_exists(self):
        assert (ROOT / "Tests" / "analyzer").is_dir()

    def test_runs_dir_exists(self):
        assert (ROOT / "Runs").is_dir()

    def test_docs_dir_exists(self):
        assert (ROOT / "docs").is_dir()

    def test_docs_paper_exists(self):
        assert (ROOT / "docs" / "paper").is_dir()

    def test_docs_examples_exists(self):
        assert (ROOT / "docs" / "examples").is_dir()

    def test_docs_samples_exists(self):
        assert (ROOT / "docs" / "samples").is_dir()

    def test_archive_dir_exists(self):
        assert (ROOT / "archive").is_dir()


# ---------------------------------------------------------------------------
# Package imports
# ---------------------------------------------------------------------------

class TestPackageImports:
    def test_runner_importable(self):
        mod = importlib.import_module("runner")
        assert pathlib.Path(mod.__file__).is_relative_to(ROOT / "Code")

    def test_analyzer_importable(self):
        mod = importlib.import_module("analyzer")
        assert pathlib.Path(mod.__file__).is_relative_to(ROOT / "Code")

    def test_runner_cli_importable(self):
        importlib.import_module("runner.cli")

    def test_runner_config_importable(self):
        importlib.import_module("runner.config")

    def test_runner_runner_importable(self):
        importlib.import_module("runner.runner")

    def test_runner_storage_importable(self):
        importlib.import_module("runner.storage")


# ---------------------------------------------------------------------------
# Path constants
# ---------------------------------------------------------------------------

class TestPathConstants:
    def test_provider_pricing_yaml_exists(self):
        """Config/provider_pricing.yaml must exist and be readable."""
        path = ROOT / "Config" / "provider_pricing.yaml"
        assert path.exists(), f"Missing: {path}"
        import yaml
        data = yaml.safe_load(path.read_text())
        assert "providers" in data

    def test_keys_yaml_path_resolves(self):
        """registry._PROJECT_KEYS_FILE must resolve to {root}/keys.yaml."""
        from runner.interfaces.registry import _PROJECT_KEYS_FILE
        assert _PROJECT_KEYS_FILE == ROOT / "keys.yaml", (
            f"Expected {ROOT / 'keys.yaml'}, got {_PROJECT_KEYS_FILE}"
        )

    def test_pricing_yaml_path_resolves(self):
        """cost_estimator._PRICING_YAML_PATH must resolve to Config/provider_pricing.yaml."""
        from runner.interfaces.cost_estimator import _PRICING_YAML_PATH
        assert _PRICING_YAML_PATH == ROOT / "Config" / "provider_pricing.yaml", (
            f"Expected Config/provider_pricing.yaml, got {_PRICING_YAML_PATH}"
        )


# ---------------------------------------------------------------------------
# Test directories do NOT contain __init__.py (prevents double-loading)
# ---------------------------------------------------------------------------

class TestNoTestInitFiles:
    def test_runner_tests_no_init(self):
        assert not (ROOT / "Tests" / "runner" / "__init__.py").exists()

    def test_benchmark_tests_no_init(self):
        assert not (ROOT / "Tests" / "benchmark" / "__init__.py").exists()

    def test_analyzer_tests_no_init(self):
        assert not (ROOT / "Tests" / "analyzer" / "__init__.py").exists()

    def test_code_runner_tests_no_init(self):
        assert not (ROOT / "Code" / "runner" / "tests" / "__init__.py").exists()

    def test_code_analyzer_tests_no_init(self):
        assert not (ROOT / "Code" / "analyzer" / "tests" / "__init__.py").exists()


# ---------------------------------------------------------------------------
# Runs/ structure
# ---------------------------------------------------------------------------

class TestRunsStructure:
    def test_runs_mixed_has_yaml(self):
        assert (ROOT / "Runs" / "mixed" / "mixed.yaml").exists()

    def test_runs_education_has_yaml(self):
        assert (ROOT / "Runs" / "education" / "education.yaml").exists()

    def test_runs_medium_benchmark_has_yaml(self):
        assert (ROOT / "Runs" / "medium-benchmark" / "medium_benchmark.yaml").exists()

    def test_runs_simple_test_has_yaml(self):
        assert (ROOT / "Runs" / "simple-test" / "simple_test.yaml").exists()

    def test_storage_folder_in_yamls_uses_runs(self):
        """All Runs/ YAML configs must reference storage_folder: ./Runs."""
        import yaml
        for yaml_file in (ROOT / "Runs").rglob("*.yaml"):
            if yaml_file.name.startswith("config"):
                continue  # skip saved run configs
            text = yaml_file.read_text(encoding="utf-8")
            data = yaml.safe_load(text)
            # storage_folder may sit at top level or nested under 'experiment:'
            folder = (
                data.get("storage_folder")
                or (data.get("experiment") or {}).get("storage_folder")
            )
            if folder:  # skip files where it's only in a comment or absent
                assert "./Runs" in folder or "Runs" in folder, (
                    f"{yaml_file}: storage_folder should reference ./Runs, got '{folder}'"
                )


# ---------------------------------------------------------------------------
# CLI smoke test
# ---------------------------------------------------------------------------

class TestCLI:
    def test_coeval_help(self):
        result = subprocess.run(
            [sys.executable, "-m", "runner.cli", "--help"],
            capture_output=True, text=True
        )
        assert result.returncode == 0
        assert "coeval" in result.stdout.lower()
