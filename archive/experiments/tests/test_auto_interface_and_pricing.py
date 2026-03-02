"""Tests for interface:auto resolution, provider pricing YAML, and dual-track config.

Covers:
  - experiments/interfaces/registry.py
      load_provider_pricing()     — YAML load, fallback to {}, custom path
      resolve_auto_interface()    — fragment match, credential gating, no-match → None
  - experiments/interfaces/cost_estimator.py
      _load_pricing_yaml()        — loads real YAML, returns {} on missing file
      _build_price_table()        — converts providers block to fragment→price dict
      _build_batch_discount()     — extracts per-interface discounts
      PRICE_TABLE                 — populated from YAML (not empty)
      BATCH_DISCOUNT              — gemini = 0.50 after update
      get_prices()                — finds prices for openrouter models too
  - experiments/config.py
      _resolve_auto_interfaces()  — resolves interface:auto in place
      load_config()               — end-to-end: writes YAML, loads, checks resolution
      validate_config()           — V-06 still rejects unknown interfaces post-resolution
  - benchmark/paper_dual_track.yaml
      loads and validates without errors
      correct number of models, tasks, judges
      benchmark_data model present as teacher
      all expected student models present

All tests use mocking or tmp_path; no real network calls.
"""
from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml

from experiments.config import (
    CoEvalConfig,
    ExperimentConfig,
    ModelConfig,
    SamplingConfig,
    TaskConfig,
    _parse_config,
    _resolve_auto_interfaces,
    load_config,
    validate_config,
)
from experiments.interfaces.cost_estimator import (
    BATCH_DISCOUNT,
    DEFAULT_PRICE_INPUT,
    DEFAULT_PRICE_OUTPUT,
    PRICE_TABLE,
    _build_batch_discount,
    _build_price_table,
    _load_pricing_yaml,
    get_prices,
)
from experiments.interfaces.registry import load_provider_pricing, resolve_auto_interface


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

_PROJECT_ROOT = Path(__file__).parent.parent.parent
_PRICING_YAML = _PROJECT_ROOT / 'benchmark' / 'provider_pricing.yaml'
_DUAL_TRACK_YAML = _PROJECT_ROOT / 'benchmark' / 'paper_dual_track.yaml'


def _minimal_model(name='m1', interface='openai', model_id=None, roles=None):
    return ModelConfig(
        name=name,
        interface=interface,
        parameters={'model': model_id or name},
        roles=roles or ['student'],
        access_key=None,
    )


def _minimal_cfg_with_auto(model_id: str, provider_keys: dict) -> CoEvalConfig:
    """Build a CoEvalConfig with one model that has interface='auto'."""
    teacher = _minimal_model('teacher1', 'openai', 'gpt-4o-mini', ['teacher'])
    auto_model = ModelConfig(
        name='auto-model',
        interface='auto',
        parameters={'model': model_id},
        roles=['student'],
    )
    judge = _minimal_model('judge1', 'openai', 'gpt-4o-mini', ['judge'])
    task = TaskConfig(
        name='task1',
        description='Test task.',
        output_description='One word.',
        target_attributes={'quality': ['high', 'low']},
        nuanced_attributes={},
        sampling=SamplingConfig(target=[1], nuance=[0], total=2),
        rubric={'quality': 'Output quality.'},
    )
    exp = ExperimentConfig(id='test-auto', storage_folder='/tmp/coeval_auto_test')
    cfg = CoEvalConfig(models=[teacher, auto_model, judge], tasks=[task], experiment=exp)
    cfg._provider_keys = provider_keys
    return cfg


def _minimal_raw_yaml(interface='openai', model_id='gpt-4o', extra_model_keys=None):
    """Return a minimal valid raw config dict with one all-roles model."""
    m = {
        'name': 'mdl',
        'interface': interface,
        'parameters': {'model': model_id},
        'roles': ['teacher', 'student', 'judge'],
    }
    if extra_model_keys:
        m.update(extra_model_keys)
    return {
        'models': [m],
        'tasks': [{
            'name': 'task1',
            'description': 'Test.',
            'output_description': 'One word.',
            'target_attributes': {'a': ['x', 'y']},
            'nuanced_attributes': {},
            'sampling': {'target': [1], 'nuance': [0], 'total': 2},
            'rubric': {'quality': 'Good.'},
        }],
        'experiment': {
            'id': 'exp-test',
            'storage_folder': '/tmp/coeval_tests',
        },
    }


# ---------------------------------------------------------------------------
# 1. load_provider_pricing() — registry.py
# ---------------------------------------------------------------------------

class TestLoadProviderPricing:
    """Tests for registry.load_provider_pricing()."""

    def test_loads_real_pricing_yaml(self):
        """The real provider_pricing.yaml should load without errors."""
        data = load_provider_pricing()
        assert isinstance(data, dict), "Should return a dict"
        assert 'providers' in data, "Should have 'providers' key"
        assert 'auto_routing' in data, "Should have 'auto_routing' key"

    def test_providers_have_expected_interfaces(self):
        """Each provider entry should declare an interface name."""
        data = load_provider_pricing()
        for name, pdata in data.get('providers', {}).items():
            assert 'interface' in pdata, f"Provider '{name}' missing 'interface'"
            assert 'batch_discount' in pdata, f"Provider '{name}' missing 'batch_discount'"
            assert 'models' in pdata, f"Provider '{name}' missing 'models'"

    def test_openai_prices_reasonable(self):
        """OpenAI GPT-4o price should be in a sane range."""
        data = load_provider_pricing()
        gpt4o = data['providers']['openai']['models'].get('gpt-4o', {})
        assert gpt4o, "gpt-4o should be in openai provider"
        assert 0 < gpt4o['input'] < 100
        assert 0 < gpt4o['output'] < 200

    def test_gemini_batch_discount_is_50_percent(self):
        """Gemini should have batch_discount: 0.50 (updated from 1.00)."""
        data = load_provider_pricing()
        discount = data['providers']['gemini']['batch_discount']
        assert discount == 0.50, f"Gemini batch_discount should be 0.50, got {discount}"

    def test_auto_routing_has_entries(self):
        """auto_routing should have at least 10 entries."""
        data = load_provider_pricing()
        routing = data.get('auto_routing', {})
        assert len(routing) >= 10, f"auto_routing has only {len(routing)} entries"

    def test_auto_routing_entries_have_interface(self):
        """Every auto_routing entry must have an 'interface' key."""
        data = load_provider_pricing()
        for fragment, route in data.get('auto_routing', {}).items():
            assert 'interface' in route, (
                f"auto_routing['{fragment}'] missing 'interface'"
            )
            assert isinstance(route['interface'], str)

    def test_custom_path_missing_returns_empty(self, tmp_path, monkeypatch):
        """When both the custom path AND the default path are missing, returns {}."""
        import experiments.interfaces.registry as reg
        # Patch the module-level default path so there is no fallback
        monkeypatch.setattr(reg, '_PRICING_YAML_PATH', tmp_path / 'also_missing.yaml')
        result = load_provider_pricing(tmp_path / 'nonexistent.yaml')
        assert result == {}

    def test_custom_path_used_when_provided(self, tmp_path):
        """Custom path overrides the default when the file exists."""
        custom_pricing = {
            'providers': {
                'openai': {
                    'interface': 'openai',
                    'batch_discount': 0.5,
                    'models': {'my-custom-model': {'input': 9.99, 'output': 19.99}},
                }
            },
            'auto_routing': {
                'my-custom-model': {'interface': 'openai'},
            },
        }
        path = tmp_path / 'custom_pricing.yaml'
        path.write_text(yaml.dump(custom_pricing), encoding='utf-8')
        result = load_provider_pricing(path)
        assert 'providers' in result
        assert 'my-custom-model' in result['providers']['openai']['models']

    def test_malformed_yaml_returns_empty(self, tmp_path):
        """A YAML parse error should return {} silently."""
        bad = tmp_path / 'bad.yaml'
        bad.write_text('{ unclosed: [bracket', encoding='utf-8')
        result = load_provider_pricing(bad)
        assert result == {}


# ---------------------------------------------------------------------------
# 2. resolve_auto_interface() — registry.py
# ---------------------------------------------------------------------------

class TestResolveAutoInterface:
    """Tests for registry.resolve_auto_interface()."""

    def test_gpt4o_resolves_to_openai_when_key_available(self):
        provider_keys = {'openai': {'api_key': 'sk-test'}}
        result = resolve_auto_interface('gpt-4o', provider_keys)
        assert result == 'openai'

    def test_gpt4o_mini_resolves_to_openai(self):
        provider_keys = {'openai': {'api_key': 'sk-test'}}
        result = resolve_auto_interface('gpt-4o-mini', provider_keys)
        assert result == 'openai'

    def test_claude_haiku_resolves_to_anthropic(self):
        provider_keys = {'anthropic': {'api_key': 'sk-ant-test'}}
        result = resolve_auto_interface('claude-3-5-haiku-20241022', provider_keys)
        assert result == 'anthropic'

    def test_gemini_flash_resolves_to_gemini(self):
        provider_keys = {'gemini': {'api_key': 'AIza-test'}}
        result = resolve_auto_interface('gemini-2.0-flash', provider_keys)
        assert result == 'gemini'

    def test_llama_resolves_to_openrouter(self):
        provider_keys = {'openrouter': {'api_key': 'sk-or-test'}}
        result = resolve_auto_interface('meta-llama/llama-3.3-70b-instruct', provider_keys)
        assert result == 'openrouter'

    def test_deepseek_resolves_to_openrouter(self):
        provider_keys = {'openrouter': {'api_key': 'sk-or-test'}}
        result = resolve_auto_interface('deepseek/deepseek-chat', provider_keys)
        assert result == 'openrouter'

    def test_no_credentials_returns_none(self):
        """If no credentials for the cheapest provider, return None."""
        # gpt-4o needs openai credentials; no openai key provided
        result = resolve_auto_interface('gpt-4o', provider_keys={})
        assert result is None

    def test_skips_to_next_provider_if_first_unavailable(self, tmp_path):
        """Falls through to a cheaper alternative when first-choice creds missing."""
        # Create a custom pricing YAML where gpt-4o routes to openai first,
        # then openrouter as second option
        custom = {
            'providers': {
                'openai': {
                    'interface': 'openai',
                    'batch_discount': 0.5,
                    'models': {'gpt-4o': {'input': 2.50, 'output': 10.00}},
                },
                'openrouter': {
                    'interface': 'openrouter',
                    'batch_discount': 1.0,
                    'models': {'openai/gpt-4o': {'input': 3.00, 'output': 12.00}},
                },
            },
            'auto_routing': {
                'gpt-4o': {'interface': 'openai'},
                'openai/gpt-4o': {'interface': 'openrouter'},
            },
        }
        path = tmp_path / 'pricing.yaml'
        path.write_text(yaml.dump(custom), encoding='utf-8')
        # No openai credentials, but openrouter is configured
        provider_keys = {'openrouter': {'api_key': 'sk-or-test'}}
        result = resolve_auto_interface('openai/gpt-4o', provider_keys, pricing_path=path)
        assert result == 'openrouter'

    def test_benchmark_resolves_without_credentials(self, tmp_path):
        """benchmark virtual interface requires no credentials."""
        custom = {
            'providers': {},
            'auto_routing': {
                'benchmark-model': {'interface': 'benchmark'},
            },
        }
        path = tmp_path / 'pricing.yaml'
        path.write_text(yaml.dump(custom), encoding='utf-8')
        result = resolve_auto_interface('benchmark-model', {}, pricing_path=path)
        assert result == 'benchmark'

    def test_unknown_model_returns_none(self):
        """Model with no matching fragment returns None."""
        result = resolve_auto_interface(
            'some-completely-unknown-model-xyz-9999',
            provider_keys={'openai': {'api_key': 'sk-test'}},
        )
        assert result is None

    def test_case_insensitive_matching(self):
        """Fragment matching is case-insensitive."""
        provider_keys = {'openai': {'api_key': 'sk-test'}}
        # 'GPT-4O' should match fragment 'gpt-4o'
        result = resolve_auto_interface('GPT-4O', provider_keys)
        assert result == 'openai'

    def test_custom_pricing_path_used(self, tmp_path):
        """Explicit pricing_path overrides the default YAML."""
        custom = {
            'providers': {
                'myiface': {
                    'interface': 'myiface',
                    'batch_discount': 1.0,
                    'models': {'my-custom-llm': {'input': 0.01, 'output': 0.02}},
                },
            },
            'auto_routing': {
                'my-custom-llm': {'interface': 'myiface'},
            },
        }
        path = tmp_path / 'custom.yaml'
        path.write_text(yaml.dump(custom), encoding='utf-8')
        result = resolve_auto_interface(
            'my-custom-llm',
            provider_keys={'myiface': {'api_key': 'xyz'}},
            pricing_path=path,
        )
        assert result == 'myiface'


# ---------------------------------------------------------------------------
# 3. _build_price_table() and _build_batch_discount() — cost_estimator.py
# ---------------------------------------------------------------------------

class TestBuildPriceTable:
    """Unit tests for _build_price_table() with synthetic pricing data."""

    def _make_data(self, extra_providers=None):
        data = {
            'providers': {
                'openai': {
                    'interface': 'openai',
                    'batch_discount': 0.5,
                    'models': {
                        'gpt-4o':      {'input': 2.50, 'output': 10.00},
                        'gpt-4o-mini': {'input': 0.15, 'output': 0.60},
                    },
                },
                'anthropic': {
                    'interface': 'anthropic',
                    'batch_discount': 0.5,
                    'models': {
                        'claude-3-5-haiku-20241022': {'input': 0.80, 'output': 4.00},
                    },
                },
            },
            'auto_routing': {},
        }
        if extra_providers:
            data['providers'].update(extra_providers)
        return data

    def test_returns_nonempty_dict_for_valid_data(self):
        data = self._make_data()
        table = _build_price_table(data)
        assert isinstance(table, dict)
        assert len(table) >= 3

    def test_model_ids_present_in_table(self):
        data = self._make_data()
        table = _build_price_table(data)
        assert 'gpt-4o' in table
        assert 'gpt-4o-mini' in table
        assert 'claude-3-5-haiku-20241022' in table

    def test_prices_are_tuples_of_floats(self):
        data = self._make_data()
        table = _build_price_table(data)
        for key, prices in table.items():
            assert isinstance(prices, tuple), f"{key}: expected tuple"
            assert len(prices) == 2
            assert isinstance(prices[0], float), f"{key}: input price not float"
            assert isinstance(prices[1], float), f"{key}: output price not float"

    def test_openai_takes_precedence_over_azure(self):
        """Primary providers (openai/anthropic/gemini) override secondary (azure_openai)."""
        data = self._make_data(extra_providers={
            'azure_openai': {
                'interface': 'azure_openai',
                'batch_discount': 1.0,
                'models': {
                    # Same model ID but higher price (should be overridden)
                    'gpt-4o': {'input': 99.00, 'output': 99.00},
                },
            },
        })
        table = _build_price_table(data)
        # OpenAI's gpt-4o price should win (2.50, not 99.00)
        assert table['gpt-4o'] == (2.50, 10.00)

    def test_empty_data_returns_empty_table(self):
        table = _build_price_table({})
        assert table == {}

    def test_real_yaml_price_table_nonempty(self):
        """The real pricing YAML produces a non-empty PRICE_TABLE."""
        assert len(PRICE_TABLE) >= 20, (
            f"PRICE_TABLE has only {len(PRICE_TABLE)} entries; expected >= 20"
        )


class TestBuildBatchDiscount:
    """Unit tests for _build_batch_discount()."""

    def test_extracts_correct_discounts(self):
        data = {
            'providers': {
                'openai':    {'interface': 'openai',    'batch_discount': 0.50, 'models': {}},
                'anthropic': {'interface': 'anthropic', 'batch_discount': 0.50, 'models': {}},
                'gemini':    {'interface': 'gemini',    'batch_discount': 0.50, 'models': {}},
                'openrouter':{'interface': 'openrouter','batch_discount': 1.00, 'models': {}},
            },
            'auto_routing': {},
        }
        discounts = _build_batch_discount(data)
        assert discounts['openai'] == 0.50
        assert discounts['anthropic'] == 0.50
        assert discounts['gemini'] == 0.50
        assert discounts['openrouter'] == 1.00

    def test_real_batch_discount_gemini_is_50pct(self):
        """After the gemini batch update, BATCH_DISCOUNT['gemini'] should be 0.50."""
        assert 'gemini' in BATCH_DISCOUNT, "gemini should be in BATCH_DISCOUNT"
        assert BATCH_DISCOUNT['gemini'] == 0.50, (
            f"gemini batch_discount should be 0.50, got {BATCH_DISCOUNT['gemini']}"
        )

    def test_real_batch_discount_openai_50pct(self):
        assert BATCH_DISCOUNT.get('openai') == 0.50

    def test_real_batch_discount_anthropic_50pct(self):
        assert BATCH_DISCOUNT.get('anthropic') == 0.50

    def test_empty_data_returns_empty(self):
        assert _build_batch_discount({}) == {}


# ---------------------------------------------------------------------------
# 4. get_prices() with open-model entries — cost_estimator.py
# ---------------------------------------------------------------------------

class TestGetPricesExtended:
    """get_prices() should find prices for openrouter-routed open models."""

    def _model_cfg(self, model_id: str, interface: str = 'openrouter') -> ModelConfig:
        return ModelConfig(
            name='test-model',
            interface=interface,
            parameters={'model': model_id},
            roles=['student'],
        )

    def test_gpt4o_price(self):
        inp, out = get_prices(self._model_cfg('gpt-4o', 'openai'))
        assert inp == pytest.approx(2.50, rel=0.01)
        assert out == pytest.approx(10.00, rel=0.01)

    def test_gpt4o_mini_price(self):
        inp, out = get_prices(self._model_cfg('gpt-4o-mini', 'openai'))
        assert inp == pytest.approx(0.15, rel=0.01)

    def test_llama_33_70b_has_price(self):
        """Llama 3.3 70B should be found via substring in PRICE_TABLE."""
        inp, out = get_prices(self._model_cfg(
            'meta-llama/llama-3.3-70b-instruct', 'openrouter'
        ))
        # Should not fall back to DEFAULT (1.00 / 3.00) because llama-3.3-70b
        # is now in PRICE_TABLE via the pricing YAML
        assert inp < DEFAULT_PRICE_INPUT or out < DEFAULT_PRICE_OUTPUT, (
            "llama-3.3-70b price should be cheaper than default 1.00/3.00"
        )

    def test_deepseek_v3_has_price(self):
        inp, out = get_prices(self._model_cfg('deepseek/deepseek-chat', 'openrouter'))
        assert inp < DEFAULT_PRICE_INPUT

    def test_unknown_model_falls_back_to_default(self):
        inp, out = get_prices(self._model_cfg('totally-unknown-model-xyz', 'openai'))
        assert inp == DEFAULT_PRICE_INPUT
        assert out == DEFAULT_PRICE_OUTPUT


# ---------------------------------------------------------------------------
# 5. _load_pricing_yaml() — cost_estimator.py
# ---------------------------------------------------------------------------

class TestLoadPricingYaml:
    """Unit tests for _load_pricing_yaml() in cost_estimator."""

    def test_loads_real_yaml_without_error(self):
        data = _load_pricing_yaml()
        assert isinstance(data, dict)
        # Real file should have data
        if _PRICING_YAML.is_file():
            assert len(data) > 0

    def test_missing_yaml_path_returns_empty(self, monkeypatch):
        """If the YAML path does not exist, returns {}."""
        import experiments.interfaces.cost_estimator as ce
        monkeypatch.setattr(ce, '_PRICING_YAML_PATH', Path('/nonexistent/pricing.yaml'))
        result = ce._load_pricing_yaml()
        assert result == {}


# ---------------------------------------------------------------------------
# 6. _resolve_auto_interfaces() in config.py
# ---------------------------------------------------------------------------

class TestResolveAutoInterfaces:
    """Tests for config._resolve_auto_interfaces() called directly."""

    def test_non_auto_interface_unchanged(self):
        """Models with explicit interfaces should not be modified."""
        cfg = _minimal_cfg_with_auto('gpt-4o', {'openai': {'api_key': 'sk-test'}})
        # Change the auto model to explicit
        cfg.models[1].interface = 'openai'
        original = cfg.models[1].interface
        _resolve_auto_interfaces(cfg)
        assert cfg.models[1].interface == original

    def test_auto_resolves_to_openai_for_gpt4o(self):
        provider_keys = {'openai': {'api_key': 'sk-test'}}
        cfg = _minimal_cfg_with_auto('gpt-4o', provider_keys)
        assert cfg.models[1].interface == 'auto'
        _resolve_auto_interfaces(cfg)
        assert cfg.models[1].interface == 'openai'

    def test_auto_resolves_to_anthropic_for_claude(self):
        provider_keys = {'anthropic': {'api_key': 'sk-ant-test'}}
        cfg = _minimal_cfg_with_auto('claude-3-5-haiku-20241022', provider_keys)
        _resolve_auto_interfaces(cfg)
        assert cfg.models[1].interface == 'anthropic'

    def test_auto_resolves_to_openrouter_for_llama(self):
        provider_keys = {'openrouter': {'api_key': 'sk-or-test'}}
        cfg = _minimal_cfg_with_auto(
            'meta-llama/llama-3.3-70b-instruct', provider_keys
        )
        _resolve_auto_interfaces(cfg)
        assert cfg.models[1].interface == 'openrouter'

    def test_auto_with_no_matching_credentials_raises(self):
        """If no provider has credentials for the model, ValueError is raised."""
        cfg = _minimal_cfg_with_auto('gpt-4o', provider_keys={})
        # No openai key → should raise
        with pytest.raises(ValueError, match="interface: auto"):
            _resolve_auto_interfaces(cfg)

    def test_auto_resolves_using_parameters_model(self):
        """Resolution uses parameters.model, not model.name."""
        provider_keys = {'openai': {'api_key': 'sk-test'}}
        cfg = _minimal_cfg_with_auto('gpt-4o-mini', provider_keys)
        # The model name is 'auto-model' but parameters.model is 'gpt-4o-mini'
        _resolve_auto_interfaces(cfg)
        assert cfg.models[1].interface == 'openai'

    def test_auto_falls_back_to_model_name_when_no_parameters_model(self):
        """If parameters has no 'model' key, uses model.name for resolution."""
        provider_keys = {'openai': {'api_key': 'sk-test'}}
        # Build a model with interface=auto and no 'model' in parameters
        auto_model = ModelConfig(
            name='gpt-4o',   # name IS the gpt-4o fragment
            interface='auto',
            parameters={},   # no 'model' key
            roles=['student'],
        )
        teacher = _minimal_model('teacher1', 'openai', 'gpt-4o-mini', ['teacher'])
        judge = _minimal_model('judge1', 'openai', 'gpt-4o-mini', ['judge'])
        task = TaskConfig(
            name='t1', description='d', output_description='o',
            target_attributes={'a': ['x']},
            nuanced_attributes={},
            sampling=SamplingConfig(target=[1], nuance=[0], total=1),
            rubric={'q': 'r'},
        )
        exp = ExperimentConfig(id='e', storage_folder='/tmp/t')
        cfg = CoEvalConfig(
            models=[teacher, auto_model, judge],
            tasks=[task],
            experiment=exp,
        )
        cfg._provider_keys = provider_keys
        _resolve_auto_interfaces(cfg)
        assert auto_model.interface == 'openai'


# ---------------------------------------------------------------------------
# 7. load_config() end-to-end with interface:auto
# ---------------------------------------------------------------------------

class TestLoadConfigAutoInterface:
    """End-to-end tests that write a YAML file and call load_config()."""

    def _write_config(self, tmp_path: Path, interface: str, model_id: str) -> Path:
        raw = _minimal_raw_yaml(interface=interface, model_id=model_id)
        cfg_path = tmp_path / 'experiment.yaml'
        cfg_path.write_text(yaml.dump(raw), encoding='utf-8')
        return cfg_path

    def _write_keys(self, tmp_path: Path, provider: str, key: str) -> Path:
        keys = {'providers': {provider: key}}
        keys_path = tmp_path / 'keys.yaml'
        keys_path.write_text(yaml.dump(keys), encoding='utf-8')
        return keys_path

    def test_explicit_interface_unchanged(self, tmp_path):
        cfg_path = self._write_config(tmp_path, 'openai', 'gpt-4o')
        keys_path = self._write_keys(tmp_path, 'openai', 'sk-test')
        cfg = load_config(str(cfg_path), keys_file=str(keys_path))
        assert cfg.models[0].interface == 'openai'

    def test_auto_interface_resolved_for_gpt4o(self, tmp_path):
        """interface:auto should be resolved to 'openai' for gpt-4o."""
        cfg_path = self._write_config(tmp_path, 'auto', 'gpt-4o')
        keys_path = self._write_keys(tmp_path, 'openai', 'sk-test')
        cfg = load_config(str(cfg_path), keys_file=str(keys_path))
        assert cfg.models[0].interface == 'openai', (
            f"Expected 'openai', got '{cfg.models[0].interface}'"
        )

    def test_auto_interface_resolved_for_claude_haiku(self, tmp_path):
        cfg_path = self._write_config(tmp_path, 'auto', 'claude-3-5-haiku-20241022')
        keys_path = self._write_keys(tmp_path, 'anthropic', 'sk-ant-test')
        cfg = load_config(str(cfg_path), keys_file=str(keys_path))
        assert cfg.models[0].interface == 'anthropic'

    def test_auto_interface_resolved_for_llama_via_openrouter(self, tmp_path):
        cfg_path = self._write_config(
            tmp_path, 'auto', 'meta-llama/llama-3.3-70b-instruct'
        )
        keys_path = self._write_keys(tmp_path, 'openrouter', 'sk-or-test')
        cfg = load_config(str(cfg_path), keys_file=str(keys_path))
        assert cfg.models[0].interface == 'openrouter'

    def test_auto_then_validate_passes(self, tmp_path):
        """After interface:auto is resolved, validate_config should return no errors."""
        cfg_path = self._write_config(tmp_path, 'auto', 'gpt-4o')
        keys_path = self._write_keys(tmp_path, 'openai', 'sk-test')
        cfg = load_config(str(cfg_path), keys_file=str(keys_path))
        errors = validate_config(cfg, _skip_folder_validation=True)
        assert errors == [], f"Unexpected validation errors: {errors}"

    def test_auto_no_credentials_raises_valueerror(self, tmp_path, monkeypatch):
        """interface:auto with no matching credentials raises ValueError at load time.

        We clear all provider env vars so the test is not contaminated by
        credentials configured in the developer's environment.
        """
        # Remove all provider env vars that might supply a fallback key
        for env_var in [
            'OPENAI_API_KEY', 'ANTHROPIC_API_KEY', 'GEMINI_API_KEY',
            'GOOGLE_API_KEY', 'OPENROUTER_API_KEY', 'HF_TOKEN',
            'HUGGINGFACE_HUB_TOKEN', 'AZURE_OPENAI_API_KEY',
            'AWS_ACCESS_KEY_ID', 'AWS_SECRET_ACCESS_KEY',
            'GOOGLE_CLOUD_PROJECT', 'COEVAL_KEYS_FILE',
        ]:
            monkeypatch.delenv(env_var, raising=False)

        cfg_path = self._write_config(tmp_path, 'auto', 'gpt-4o')
        # Provide only gemini key — gpt-4o routes to openai, not gemini
        keys_path = self._write_keys(tmp_path, 'gemini', 'AIza-test-only')
        with pytest.raises(ValueError, match="interface: auto"):
            load_config(str(cfg_path), keys_file=str(keys_path))


# ---------------------------------------------------------------------------
# 8. validate_config() V-06 still rejects truly unknown interfaces
# ---------------------------------------------------------------------------

class TestV06StillRejectsUnknownInterfaces:
    """V-06 must reject genuinely unknown interface names (not 'auto')."""

    def test_unknown_interface_rejected(self):
        raw = _minimal_raw_yaml(interface='completely_fake_interface')
        cfg = _parse_config(raw)
        errors = validate_config(cfg, _skip_folder_validation=True)
        assert any('Unknown interface' in e for e in errors), (
            f"V-06 should flag unknown interface; errors={errors}"
        )

    def test_known_interfaces_accepted(self):
        for iface in ('openai', 'anthropic', 'gemini', 'openrouter',
                      'bedrock', 'azure_openai', 'vertex'):
            raw = _minimal_raw_yaml(interface=iface)
            cfg = _parse_config(raw)
            errors = [e for e in validate_config(cfg, _skip_folder_validation=True)
                      if 'Unknown interface' in e]
            assert errors == [], f"Interface '{iface}' should be valid; errors={errors}"

    def test_auto_not_in_valid_interfaces_constant(self):
        """'auto' must NOT be in VALID_INTERFACES — it is resolved before validation."""
        from experiments.config import VALID_INTERFACES
        assert 'auto' not in VALID_INTERFACES, (
            "'auto' should not be in VALID_INTERFACES; it is resolved before V-06"
        )


# ---------------------------------------------------------------------------
# 9. paper_dual_track.yaml loads and validates
# ---------------------------------------------------------------------------

@pytest.mark.skipif(
    not _DUAL_TRACK_YAML.is_file(),
    reason="benchmark/paper_dual_track.yaml not found",
)
class TestDualTrackConfig:
    """Integration tests for the dual-track paper experiment YAML."""

    @pytest.fixture(scope='class')
    def dual_cfg(self):
        """Load paper_dual_track.yaml with no credentials (skip folder validation)."""
        with open(_DUAL_TRACK_YAML, encoding='utf-8') as fh:
            raw = yaml.safe_load(fh)
        cfg = _parse_config(raw)
        cfg._provider_keys = {}
        return cfg

    def test_config_loads(self, dual_cfg):
        assert isinstance(dual_cfg, CoEvalConfig)

    def test_has_14_models(self, dual_cfg):
        """Should have 14 models: 10 real + 4 virtual benchmark teachers."""
        assert len(dual_cfg.models) == 14, (
            f"Expected 14 models, got {len(dual_cfg.models)}"
        )

    def test_has_4_tasks(self, dual_cfg):
        task_names = {t.name for t in dual_cfg.tasks}
        assert 'text_summarization' in task_names
        assert 'code_explanation' in task_names
        assert 'email_composition' in task_names
        assert 'data_interpretation' in task_names

    def test_benchmark_teachers_present(self, dual_cfg):
        """All 4 virtual benchmark teachers should be present with correct interface."""
        expected_names = {'xsum', 'codesearchnet-python', 'aeslc', 'wikitablequestions'}
        benchmark_models = {
            m.name for m in dual_cfg.models if m.interface == 'benchmark'
        }
        assert expected_names == benchmark_models, (
            f"Benchmark teachers mismatch. Missing: {expected_names - benchmark_models}, "
            f"extra: {benchmark_models - expected_names}"
        )
        for m in dual_cfg.models:
            if m.interface == 'benchmark':
                assert 'teacher' in m.roles, (
                    f"Benchmark model '{m.name}' should have teacher role"
                )

    def test_all_student_models_present(self, dual_cfg):
        student_models = {
            m.name for m in dual_cfg.models if 'student' in m.roles
        }
        expected = {
            'gpt-4o', 'gpt-4o-mini', 'claude-sonnet-4-6', 'claude-3-5-haiku',
            'gemini-2.0-flash', 'llama-3.3-70b', 'llama-3.1-8b',
            'mistral-small', 'deepseek-v3', 'qwen2.5-72b',
        }
        assert expected == student_models, (
            f"Student models mismatch. Missing: {expected - student_models}, "
            f"extra: {student_models - expected}"
        )

    def test_judges_are_all_10_llm_models(self, dual_cfg):
        """All 10 LLM models serve as judge (all-roles design)."""
        judges = [m for m in dual_cfg.models if 'judge' in m.roles]
        judge_names = {j.name for j in judges}
        expected_judges = {
            'gpt-4o', 'gpt-4o-mini', 'claude-sonnet-4-6', 'claude-3-5-haiku',
            'gemini-2.0-flash', 'llama-3.3-70b', 'llama-3.1-8b',
            'mistral-small', 'deepseek-v3', 'qwen2.5-72b',
        }
        assert expected_judges == judge_names, (
            f"Judge mismatch. Missing: {expected_judges - judge_names}, "
            f"extra: {judge_names - expected_judges}"
        )

    def test_teachers_are_all_10_llm_plus_4_benchmarks(self, dual_cfg):
        """All 10 LLM models + 4 benchmark virtual teachers have the teacher role."""
        teacher_names = {m.name for m in dual_cfg.models if 'teacher' in m.roles}
        # All 10 LLM models
        for name in ('gpt-4o', 'gpt-4o-mini', 'claude-sonnet-4-6', 'claude-3-5-haiku',
                     'gemini-2.0-flash', 'llama-3.3-70b', 'llama-3.1-8b',
                     'mistral-small', 'deepseek-v3', 'qwen2.5-72b'):
            assert name in teacher_names, f"{name} should be a teacher"
        # 4 benchmark virtual teachers
        for name in ('xsum', 'codesearchnet-python', 'aeslc', 'wikitablequestions'):
            assert name in teacher_names, f"Benchmark teacher {name} should be present"

    def test_each_task_has_100_items(self, dual_cfg):
        for task in dual_cfg.tasks:
            assert task.sampling.total == 100, (
                f"Task '{task.name}' has {task.sampling.total} items, expected 100"
            )

    def test_rubrics_contain_ba_dimension(self, dual_cfg):
        """Each task rubric should have at least one [BA] benchmark-aligned dimension."""
        for task in dual_cfg.tasks:
            assert isinstance(task.rubric, dict), (
                f"Task '{task.name}': rubric should be a dict"
            )
            ba_dims = [
                k for k, v in task.rubric.items()
                if isinstance(v, str) and '[BA]' in v
            ]
            assert ba_dims, (
                f"Task '{task.name}': no benchmark-aligned [BA] rubric dimension found"
            )

    def test_batch_enabled_for_openai_and_anthropic(self, dual_cfg):
        assert dual_cfg.use_batch('openai', 'response_collection') is True
        assert dual_cfg.use_batch('anthropic', 'response_collection') is True
        assert dual_cfg.use_batch('openai', 'evaluation') is True

    def test_validate_config_no_errors(self, dual_cfg):
        """The dual-track config should pass all validations (folder skipped)."""
        errors = validate_config(dual_cfg, _skip_folder_validation=True)
        assert errors == [], f"Unexpected validation errors: {errors}"

    def test_openrouter_models_use_openrouter_interface(self, dual_cfg):
        openrouter_expected = {
            'llama-3.3-70b', 'llama-3.1-8b', 'mistral-small',
            'deepseek-v3', 'qwen2.5-72b',
        }
        for m in dual_cfg.models:
            if m.name in openrouter_expected:
                assert m.interface == 'openrouter', (
                    f"Model '{m.name}' should use 'openrouter', got '{m.interface}'"
                )

    def test_no_huggingface_models(self, dual_cfg):
        """Dual-track config must not contain any HuggingFace local models."""
        hf_models = [m for m in dual_cfg.models if m.interface == 'huggingface']
        assert hf_models == [], (
            f"Found HuggingFace models (should be API-only): {[m.name for m in hf_models]}"
        )

    def test_experiment_id(self, dual_cfg):
        assert dual_cfg.experiment.id == 'paper-dual-track-v1'

    def test_gemini_batch_enabled(self, dual_cfg):
        """Gemini batch should be enabled for the dual-track config."""
        assert dual_cfg.use_batch('gemini', 'response_collection') is True
        assert dual_cfg.use_batch('gemini', 'evaluation') is True


# ---------------------------------------------------------------------------
# 10. pricing_yaml is used by PRICE_TABLE (not just fallback)
# ---------------------------------------------------------------------------

class TestPriceTableLoadedFromYaml:
    """Verify PRICE_TABLE reflects content loaded from provider_pricing.yaml."""

    def test_price_table_has_openrouter_entries(self):
        """Open models from OpenRouter section should appear in PRICE_TABLE."""
        # Llama 3.3 70B is in provider_pricing.yaml under openrouter
        llama_key = next(
            (k for k in PRICE_TABLE if 'llama-3.3-70b' in k),
            None,
        )
        assert llama_key is not None, (
            "llama-3.3-70b not found in PRICE_TABLE — pricing YAML may not be loaded"
        )

    def test_price_table_has_gemini_entries(self):
        gemini_key = next((k for k in PRICE_TABLE if 'gemini-2.0-flash' in k), None)
        assert gemini_key is not None

    def test_price_table_has_deepseek_entries(self):
        ds_key = next((k for k in PRICE_TABLE if 'deepseek' in k), None)
        assert ds_key is not None, "DeepSeek not found in PRICE_TABLE"

    def test_price_table_has_mistral_entries(self):
        ms_key = next((k for k in PRICE_TABLE if 'mistral-small' in k), None)
        assert ms_key is not None, "mistral-small not found in PRICE_TABLE"
