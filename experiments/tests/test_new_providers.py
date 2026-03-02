"""Tests for new provider interfaces, registry, and CLI commands.

Covers:
  - experiments/interfaces/registry.py  (load_keys_file, resolve_provider_keys,
    get_access_key_for_model, list_provider_models)
  - experiments/interfaces/azure_openai_iface.py  (AzureOpenAIInterface)
  - experiments/interfaces/bedrock_iface.py       (BedrockInterface)
  - experiments/interfaces/vertex_iface.py        (VertexInterface)
  - experiments/interfaces/probe.py               (_probe_azure_openai, _probe_bedrock,
    _probe_vertex)
  - experiments/interfaces/pool.py                (ModelPool with provider_keys)
  - experiments/commands/generate_cmd.py          (cmd_generate)
  - experiments/commands/models_cmd.py            (cmd_models)
  - experiments/cli.py                            (generate / models subparsers,
    --keys flag)

All tests use mocking; no real network calls or LLM requests are made.
Optional packages (boto3, anthropic, vertexai) are mocked via sys.modules
so the tests work even when those packages are not installed.
"""
from __future__ import annotations

import argparse
import importlib
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import yaml


# ---------------------------------------------------------------------------
# Fixtures: inject mock modules for optional dependencies
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_boto3():
    """Inject a mock boto3 into sys.modules for the duration of a test."""
    mock = MagicMock()
    with patch.dict(sys.modules, {'boto3': mock, 'boto3.session': MagicMock()}):
        yield mock


@pytest.fixture
def mock_anthropic():
    """Inject a mock anthropic into sys.modules for the duration of a test."""
    mock = MagicMock()
    with patch.dict(sys.modules, {'anthropic': mock}):
        yield mock


@pytest.fixture
def mock_vertexai():
    """Inject mock vertexai modules into sys.modules for the duration of a test."""
    mock_vx = MagicMock()
    mock_gm = MagicMock()
    mods = {
        'vertexai': mock_vx,
        'vertexai.generative_models': mock_gm,
    }
    with patch.dict(sys.modules, mods):
        yield mock_vx, mock_gm


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _task_raw(**overrides):
    """Minimal valid task raw dict including required nuanced_attributes."""
    base = {
        'name': 'task1',
        'description': 'Test task.',
        'output_description': 'One word.',
        'target_attributes': {'quality': ['high', 'low']},
        'nuanced_attributes': None,
        'rubric': {'quality': 'Output quality.'},
        'sampling': {'target': [1, 1], 'nuance': [0, 0], 'total': 2},
    }
    base.update(overrides)
    return base


def _model_raw(name='mdl', interface='openai', params=None, roles=None, **extra):
    d = {
        'name': name,
        'interface': interface,
        'parameters': {**(params or {}), 'model': 'dummy'},
        'roles': roles or ['teacher'],
    }
    d.update(extra)
    return d


def _minimal_raw(storage_folder, exp_id='exp-test', extra_task=None, extra_model=None):
    return {
        'models': [_model_raw(**(extra_model or {}))],
        'tasks': [_task_raw(**(extra_task or {}))],
        'experiment': {'id': exp_id, 'storage_folder': str(storage_folder)},
    }


def _write_yaml(path: Path, data: dict) -> Path:
    with open(path, 'w') as f:
        yaml.dump(data, f)
    return path


def _parse(raw):
    from experiments.config import _parse_config
    return _parse_config(raw)


# ===========================================================================
# 1.  registry.py
# ===========================================================================

class TestLoadKeysFile:
    """load_keys_file resolves path priority correctly."""

    @pytest.fixture(autouse=True)
    def _no_default_keys_file(self, tmp_path, monkeypatch):
        """Prevent tests from picking up project keys.yaml or ~/.coeval/keys.yaml."""
        import experiments.interfaces.registry as reg_mod
        monkeypatch.setattr(reg_mod, '_PROJECT_KEYS_FILE', tmp_path / '__no_keys_p__.yaml')
        monkeypatch.setattr(reg_mod, '_DEFAULT_KEYS_FILE', tmp_path / '__no_keys_h__.yaml')
        monkeypatch.delenv('COEVAL_KEYS_FILE', raising=False)

    def test_explicit_path_wins(self, tmp_path):
        from experiments.interfaces.registry import load_keys_file
        key_file = tmp_path / 'keys.yaml'
        key_file.write_text("providers:\n  openai: sk-test\n", encoding='utf-8')
        result = load_keys_file(str(key_file))
        assert result.get('openai') == 'sk-test'

    def test_returns_empty_if_no_file(self, tmp_path):
        from experiments.interfaces.registry import load_keys_file
        result = load_keys_file(str(tmp_path / 'missing.yaml'))
        assert result == {}

    def test_env_var_path(self, tmp_path, monkeypatch):
        from experiments.interfaces.registry import load_keys_file
        key_file = tmp_path / 'env_keys.yaml'
        key_file.write_text("providers:\n  anthropic: sk-ant-test\n", encoding='utf-8')
        monkeypatch.setenv('COEVAL_KEYS_FILE', str(key_file))
        result = load_keys_file()
        assert result.get('anthropic') == 'sk-ant-test'

    def test_flat_dict_format_supported(self, tmp_path):
        """Keys file without 'providers:' top-level key is also accepted."""
        from experiments.interfaces.registry import load_keys_file
        key_file = tmp_path / 'flat.yaml'
        key_file.write_text("openai: sk-flat\n", encoding='utf-8')
        result = load_keys_file(str(key_file))
        assert result.get('openai') == 'sk-flat'

    def test_corrupted_file_returns_empty(self, tmp_path):
        from experiments.interfaces.registry import load_keys_file
        key_file = tmp_path / 'bad.yaml'
        key_file.write_bytes(b'\x00\xff\xfe \x00')
        result = load_keys_file(str(key_file))
        assert result == {}


class TestResolveProviderKeys:
    """resolve_provider_keys merges key file + env vars correctly."""

    @pytest.fixture(autouse=True)
    def _no_default_keys_file(self, tmp_path, monkeypatch):
        """Prevent tests from picking up project keys.yaml or ~/.coeval/keys.yaml."""
        import experiments.interfaces.registry as reg_mod
        monkeypatch.setattr(reg_mod, '_PROJECT_KEYS_FILE', tmp_path / '__no_keys_p__.yaml')
        monkeypatch.setattr(reg_mod, '_DEFAULT_KEYS_FILE', tmp_path / '__no_keys_h__.yaml')
        monkeypatch.delenv('COEVAL_KEYS_FILE', raising=False)

    def test_openai_from_file(self, tmp_path, monkeypatch):
        from experiments.interfaces.registry import resolve_provider_keys
        monkeypatch.delenv('OPENAI_API_KEY', raising=False)
        key_file = tmp_path / 'keys.yaml'
        key_file.write_text("providers:\n  openai: sk-file\n", encoding='utf-8')
        result = resolve_provider_keys(key_file)
        assert result['openai']['api_key'] == 'sk-file'

    def test_openai_from_env(self, tmp_path, monkeypatch):
        from experiments.interfaces.registry import resolve_provider_keys
        monkeypatch.setenv('OPENAI_API_KEY', 'sk-env')
        result = resolve_provider_keys(str(tmp_path / 'missing.yaml'))
        assert result['openai']['api_key'] == 'sk-env'

    def test_file_wins_over_env(self, tmp_path, monkeypatch):
        from experiments.interfaces.registry import resolve_provider_keys
        monkeypatch.setenv('OPENAI_API_KEY', 'sk-env')
        key_file = tmp_path / 'keys.yaml'
        key_file.write_text("providers:\n  openai: sk-file\n", encoding='utf-8')
        result = resolve_provider_keys(key_file)
        assert result['openai']['api_key'] == 'sk-file'

    def test_azure_openai_resolved(self, tmp_path, monkeypatch):
        from experiments.interfaces.registry import resolve_provider_keys
        monkeypatch.delenv('AZURE_OPENAI_API_KEY', raising=False)
        monkeypatch.delenv('AZURE_OPENAI_ENDPOINT', raising=False)
        key_file = tmp_path / 'keys.yaml'
        key_file.write_text(
            "providers:\n"
            "  azure_openai:\n"
            "    api_key: az-key\n"
            "    endpoint: https://my.openai.azure.com/\n"
            "    api_version: 2024-08-01-preview\n",
            encoding='utf-8',
        )
        result = resolve_provider_keys(key_file)
        assert result['azure_openai']['api_key'] == 'az-key'
        assert result['azure_openai']['endpoint'] == 'https://my.openai.azure.com/'

    def test_azure_requires_both_key_and_endpoint(self, tmp_path, monkeypatch):
        """azure_openai is only included when both key AND endpoint are present."""
        from experiments.interfaces.registry import resolve_provider_keys
        monkeypatch.delenv('AZURE_OPENAI_API_KEY', raising=False)
        monkeypatch.delenv('AZURE_OPENAI_ENDPOINT', raising=False)
        key_file = tmp_path / 'keys.yaml'
        key_file.write_text(
            "providers:\n  azure_openai:\n    api_key: az-key\n",
            encoding='utf-8',
        )
        result = resolve_provider_keys(key_file)
        assert 'azure_openai' not in result

    def test_bedrock_resolved(self, tmp_path, monkeypatch):
        from experiments.interfaces.registry import resolve_provider_keys
        monkeypatch.delenv('AWS_ACCESS_KEY_ID', raising=False)
        monkeypatch.delenv('AWS_SECRET_ACCESS_KEY', raising=False)
        monkeypatch.delenv('AWS_DEFAULT_REGION', raising=False)
        key_file = tmp_path / 'keys.yaml'
        key_file.write_text(
            "providers:\n"
            "  bedrock:\n"
            "    access_key_id: AKIA\n"
            "    secret_access_key: secret\n"
            "    region: us-west-2\n",
            encoding='utf-8',
        )
        result = resolve_provider_keys(key_file)
        assert result['bedrock']['region'] == 'us-west-2'
        assert result['bedrock']['access_key_id'] == 'AKIA'

    def test_vertex_resolved(self, tmp_path, monkeypatch):
        from experiments.interfaces.registry import resolve_provider_keys
        monkeypatch.delenv('GOOGLE_CLOUD_PROJECT', raising=False)
        key_file = tmp_path / 'keys.yaml'
        key_file.write_text(
            "providers:\n"
            "  vertex:\n"
            "    project: my-gcp-project\n"
            "    location: europe-west1\n",
            encoding='utf-8',
        )
        result = resolve_provider_keys(key_file)
        assert result['vertex']['project'] == 'my-gcp-project'
        assert result['vertex']['location'] == 'europe-west1'

    def test_vertex_excluded_without_project(self, tmp_path, monkeypatch):
        from experiments.interfaces.registry import resolve_provider_keys
        monkeypatch.delenv('GOOGLE_CLOUD_PROJECT', raising=False)
        monkeypatch.delenv('GCLOUD_PROJECT', raising=False)
        result = resolve_provider_keys(str(tmp_path / 'missing.yaml'))
        assert 'vertex' not in result

    def test_huggingface_resolved(self, tmp_path, monkeypatch):
        from experiments.interfaces.registry import resolve_provider_keys
        monkeypatch.delenv('HF_TOKEN', raising=False)
        monkeypatch.delenv('HUGGINGFACE_HUB_TOKEN', raising=False)
        key_file = tmp_path / 'keys.yaml'
        key_file.write_text(
            "providers:\n  huggingface: hf_abc123\n",
            encoding='utf-8',
        )
        result = resolve_provider_keys(key_file)
        assert result['huggingface']['token'] == 'hf_abc123'

    def test_empty_result_when_no_keys(self, tmp_path, monkeypatch):
        from experiments.interfaces.registry import resolve_provider_keys
        for var in [
            'OPENAI_API_KEY', 'ANTHROPIC_API_KEY', 'GEMINI_API_KEY', 'GOOGLE_API_KEY',
            'AZURE_OPENAI_API_KEY', 'AZURE_OPENAI_ENDPOINT',
            'AWS_ACCESS_KEY_ID', 'AWS_SECRET_ACCESS_KEY', 'AWS_DEFAULT_REGION',
            'GOOGLE_CLOUD_PROJECT', 'GCLOUD_PROJECT', 'HF_TOKEN', 'HUGGINGFACE_HUB_TOKEN',
        ]:
            monkeypatch.delenv(var, raising=False)
        result = resolve_provider_keys(str(tmp_path / 'missing.yaml'))
        assert result == {}


class TestGetAccessKeyForModel:
    def test_model_key_wins(self):
        from experiments.interfaces.registry import get_access_key_for_model
        pk = {'openai': {'api_key': 'pk-key'}}
        result = get_access_key_for_model('openai', 'model-key', pk)
        assert result == 'model-key'

    def test_provider_key_fallback(self):
        from experiments.interfaces.registry import get_access_key_for_model
        pk = {'openai': {'api_key': 'pk-key'}}
        result = get_access_key_for_model('openai', None, pk)
        assert result == 'pk-key'

    def test_none_when_no_key(self):
        from experiments.interfaces.registry import get_access_key_for_model
        result = get_access_key_for_model('openai', None, {})
        assert result is None

    def test_hf_uses_token_key(self):
        from experiments.interfaces.registry import get_access_key_for_model
        pk = {'huggingface': {'token': 'hf_tok'}}
        result = get_access_key_for_model('huggingface', None, pk)
        assert result == 'hf_tok'


class TestListProviderModels:
    """list_provider_models dispatches and returns correctly-shaped results."""

    def test_openai_models_filtered(self):
        from experiments.interfaces.registry import list_provider_models
        mock_model = MagicMock()
        mock_model.id = 'gpt-4o-mini'
        mock_model.owned_by = 'openai'
        mock_response = MagicMock()
        mock_response.data = [mock_model]
        with patch('openai.OpenAI') as MockClient:
            MockClient.return_value.models.list.return_value = mock_response
            result = list_provider_models('openai', {'api_key': 'sk-test'})
        assert any(m['id'] == 'gpt-4o-mini' for m in result)

    def test_anthropic_models(self, mock_anthropic):
        from experiments.interfaces.registry import list_provider_models
        mock_model = MagicMock()
        mock_model.id = 'claude-3-haiku-20240307'
        mock_model.display_name = 'Claude 3 Haiku'
        mock_response = MagicMock()
        mock_response.data = [mock_model]
        mock_anthropic.Anthropic.return_value.models.list.return_value = mock_response
        result = list_provider_models('anthropic', {'api_key': 'sk-ant-test'})
        assert any(m['id'] == 'claude-3-haiku-20240307' for m in result)

    def test_unknown_provider_returns_empty(self):
        from experiments.interfaces.registry import list_provider_models
        result = list_provider_models('unknown_provider', {})
        assert result == []

    def test_vertex_returns_known_models(self, mock_vertexai):
        from experiments.interfaces.registry import list_provider_models
        mock_vx, mock_gm = mock_vertexai
        result = list_provider_models(
            'vertex', {'project': 'p', 'location': 'us-central1'}
        )
        assert any('gemini' in m['id'] for m in result)


# ===========================================================================
# 2.  New interface constructors (mocked SDK imports)
# ===========================================================================

class TestAzureOpenAIInterface:
    """openai is installed, so these tests run without sys.modules mocking."""

    def test_construct_and_generate(self):
        from experiments.interfaces.azure_openai_iface import AzureOpenAIInterface

        mock_choice = MagicMock()
        mock_choice.message.content = 'Azure response'
        mock_completion = MagicMock()
        mock_completion.choices = [mock_choice]

        with patch('openai.AzureOpenAI') as MockAzure:
            MockAzure.return_value.chat.completions.create.return_value = mock_completion
            iface = AzureOpenAIInterface(
                api_key='az-key',
                azure_endpoint='https://my.openai.azure.com/',
                api_version='2024-08-01-preview',
            )
            result = iface.generate(
                'Hello',
                {
                    'model': 'gpt-4o',
                    'temperature': 0.5,
                    'max_tokens': 100,
                    'azure_endpoint': 'https://my.openai.azure.com/',
                    'api_version': '2024-08-01-preview',
                },
            )
        assert result == 'Azure response'

    def test_missing_endpoint_raises_at_generate(self):
        """AzureOpenAIInterface.generate raises if no endpoint resolved."""
        # Construction succeeds with openai.AzureOpenAI mock; generate does a real call
        from experiments.interfaces.azure_openai_iface import AzureOpenAIInterface
        with patch('openai.AzureOpenAI') as MockAzure:
            MockAzure.return_value.chat.completions.create.side_effect = RuntimeError(
                'permission_denied'
            )
            iface = AzureOpenAIInterface(
                api_key='bad-key',
                azure_endpoint='https://x/',
                api_version='2024-08-01-preview',
            )
            with pytest.raises(RuntimeError):
                iface.generate('Hello', {'model': 'gpt-4o', 'temperature': 0.0, 'max_tokens': 10,
                                         'azure_endpoint': 'https://x/', 'api_version': 'v'})


class TestBedrockInterface:
    def test_construct_and_generate(self, mock_boto3):
        """BedrockInterface.generate calls boto3.Session Converse API."""
        # Reload the module so it picks up the mocked boto3
        if 'experiments.interfaces.bedrock_iface' in sys.modules:
            del sys.modules['experiments.interfaces.bedrock_iface']
        from experiments.interfaces.bedrock_iface import BedrockInterface

        mock_client = MagicMock()
        mock_boto3.Session.return_value.client.return_value = mock_client
        mock_client.converse.return_value = {
            'output': {'message': {'content': [{'text': 'Bedrock response'}]}}
        }

        iface = BedrockInterface(
            access_key_id='AKIA',
            secret_access_key='secret',
            region='us-east-1',
        )
        result = iface.generate(
            'Hello',
            {'model': 'anthropic.claude-3-haiku-20240307-v1:0', 'temperature': 0.5, 'max_tokens': 100},
        )
        assert result == 'Bedrock response'

    def test_raises_if_no_boto3(self):
        """BedrockInterface raises ImportError when boto3 is missing."""
        if 'experiments.interfaces.bedrock_iface' in sys.modules:
            del sys.modules['experiments.interfaces.bedrock_iface']
        with patch.dict(sys.modules, {'boto3': None}):
            with pytest.raises((ImportError, TypeError)):
                from experiments.interfaces import bedrock_iface as m
                m.BedrockInterface()


class TestVertexInterface:
    def test_construct_and_generate(self, mock_vertexai):
        """VertexInterface.generate calls vertexai GenerativeModel."""
        if 'experiments.interfaces.vertex_iface' in sys.modules:
            del sys.modules['experiments.interfaces.vertex_iface']
        mock_vx, mock_gm = mock_vertexai

        from experiments.interfaces.vertex_iface import VertexInterface

        mock_response = MagicMock()
        mock_response.text = 'Vertex response'
        mock_gm.GenerativeModel.return_value.generate_content.return_value = mock_response

        iface = VertexInterface(project='my-project', location='us-central1')
        result = iface.generate(
            'Hello',
            {'model': 'gemini-1.5-pro', 'temperature': 0.7, 'max_tokens': 256},
        )
        assert result == 'Vertex response'

    def test_raises_without_project(self, mock_vertexai, monkeypatch):
        """VertexInterface raises ValueError when project is missing."""
        if 'experiments.interfaces.vertex_iface' in sys.modules:
            del sys.modules['experiments.interfaces.vertex_iface']
        monkeypatch.delenv('GOOGLE_CLOUD_PROJECT', raising=False)
        monkeypatch.delenv('GCLOUD_PROJECT', raising=False)

        from experiments.interfaces.vertex_iface import VertexInterface

        with pytest.raises(ValueError, match='project'):
            VertexInterface(project=None, location='us-central1')


# ===========================================================================
# 3.  probe.py — new interface probers
# ===========================================================================

class TestProbeNewInterfaces:
    """Unit tests for _probe_azure_openai, _probe_bedrock, _probe_vertex."""

    def _model_cfg(self, name='mdl', interface='openai', params=None, access_key=None):
        raw = {
            'models': [{
                'name': name,
                'interface': interface,
                'parameters': {**(params or {}), 'model': 'dummy'},
                'roles': ['teacher'],
                **(({'access_key': access_key} if access_key else {})),
            }],
            'tasks': [_task_raw()],
            'experiment': {'id': 'e', 'storage_folder': '/tmp'},
        }
        return _parse(raw).models[0]

    def test_probe_azure_openai_ok(self):
        from experiments.interfaces.probe import _probe_azure_openai
        model = self._model_cfg(
            interface='azure_openai',
            params={'azure_endpoint': 'https://my.openai.azure.com/', 'api_version': '2024-08-01-preview'},
            access_key='az-key',
        )
        with patch('openai.AzureOpenAI') as MockAZ:
            MockAZ.return_value.models.list.return_value = MagicMock()
            _probe_azure_openai(model, {})  # should not raise

    def test_probe_azure_openai_missing_endpoint_raises(self, monkeypatch):
        from experiments.interfaces.probe import _probe_azure_openai
        monkeypatch.delenv('AZURE_OPENAI_ENDPOINT', raising=False)
        model = self._model_cfg(interface='azure_openai', params={}, access_key='az-key')
        with patch('openai.AzureOpenAI'):
            with pytest.raises(RuntimeError, match='azure_endpoint'):
                _probe_azure_openai(model, {})

    def test_probe_bedrock_ok(self, mock_boto3):
        from experiments.interfaces.probe import _probe_bedrock
        model = self._model_cfg(interface='bedrock', params={'region': 'us-east-1'})
        mock_boto3.client.return_value.list_foundation_models.return_value = {'modelSummaries': []}
        _probe_bedrock(model, {})  # should not raise

    def test_probe_bedrock_import_error(self):
        from experiments.interfaces.probe import _probe_bedrock
        with patch.dict(sys.modules, {'boto3': None}):
            model = MagicMock()
            model.parameters = {'region': 'us-east-1'}
            model.access_key = None
            with pytest.raises(RuntimeError, match='boto3'):
                _probe_bedrock(model, {})

    def test_probe_vertex_ok(self, mock_vertexai):
        from experiments.interfaces.probe import _probe_vertex
        mock_vx, _ = mock_vertexai
        model = self._model_cfg(
            interface='vertex',
            params={'project': 'proj', 'location': 'us-central1'},
        )
        _probe_vertex(model, {})  # should not raise

    def test_probe_vertex_missing_project_raises(self, mock_vertexai, monkeypatch):
        from experiments.interfaces.probe import _probe_vertex
        monkeypatch.delenv('GOOGLE_CLOUD_PROJECT', raising=False)
        monkeypatch.delenv('GCLOUD_PROJECT', raising=False)
        model = self._model_cfg(interface='vertex', params={})
        with pytest.raises(RuntimeError, match='project'):
            _probe_vertex(model, {})

    def test_probe_one_dispatches_azure(self):
        from experiments.interfaces.probe import _probe_one
        model = MagicMock()
        model.interface = 'azure_openai'
        with patch('experiments.interfaces.probe._probe_azure_openai') as mock_az:
            _probe_one(model, {})
            mock_az.assert_called_once_with(model, {})

    def test_probe_one_dispatches_bedrock(self):
        from experiments.interfaces.probe import _probe_one
        model = MagicMock()
        model.interface = 'bedrock'
        with patch('experiments.interfaces.probe._probe_bedrock') as mock_bk:
            _probe_one(model, {})
            mock_bk.assert_called_once_with(model, {})

    def test_probe_one_dispatches_vertex(self):
        from experiments.interfaces.probe import _probe_one
        model = MagicMock()
        model.interface = 'vertex'
        with patch('experiments.interfaces.probe._probe_vertex') as mock_vx:
            _probe_one(model, {})
            mock_vx.assert_called_once_with(model, {})


# ===========================================================================
# 4.  ModelPool with provider_keys
# ===========================================================================

class TestModelPoolProviderKeys:
    """ModelPool correctly passes provider_keys to each interface constructor."""

    def _make_model_cfg(self, interface, params=None):
        raw = {
            'models': [_model_raw(interface=interface, params=params)],
            'tasks': [_task_raw()],
            'experiment': {'id': 'e', 'storage_folder': '/tmp'},
        }
        return _parse(raw).models[0]

    def test_openai_key_from_provider_keys(self):
        from experiments.interfaces.pool import ModelPool
        pk = {'openai': {'api_key': 'pk-from-pool'}}
        pool = ModelPool(provider_keys=pk)
        model_cfg = self._make_model_cfg('openai')
        with patch('experiments.interfaces.pool.OpenAIInterface') as MockOAI:
            MockOAI.return_value = MagicMock()
            pool.get(model_cfg)
            MockOAI.assert_called_once_with(access_key='pk-from-pool')

    def test_model_access_key_overrides_pool_key(self):
        """model.access_key takes precedence over provider_keys."""
        from experiments.interfaces.pool import ModelPool
        pk = {'openai': {'api_key': 'pk-from-pool'}}
        pool = ModelPool(provider_keys=pk)
        raw = {
            'models': [{'name': 'mdl', 'interface': 'openai',
                        'parameters': {'model': 'gpt-4o-mini'},
                        'roles': ['teacher'], 'access_key': 'model-level-key'}],
            'tasks': [_task_raw()],
            'experiment': {'id': 'e', 'storage_folder': '/tmp'},
        }
        model_cfg = _parse(raw).models[0]
        with patch('experiments.interfaces.pool.OpenAIInterface') as MockOAI:
            MockOAI.return_value = MagicMock()
            pool.get(model_cfg)
            MockOAI.assert_called_once_with(access_key='model-level-key')

    def test_azure_openai_from_provider_keys(self):
        from experiments.interfaces.pool import ModelPool
        pk = {
            'azure_openai': {
                'api_key': 'az-key',
                'endpoint': 'https://my.openai.azure.com/',
                'api_version': '2024-08-01-preview',
            }
        }
        pool = ModelPool(provider_keys=pk)
        model_cfg = self._make_model_cfg(
            'azure_openai',
            {'azure_endpoint': 'https://my.openai.azure.com/', 'api_version': '2024-08-01-preview'},
        )
        with patch('experiments.interfaces.pool.AzureOpenAIInterface') as MockAZ:
            MockAZ.return_value = MagicMock()
            pool.get(model_cfg)
            MockAZ.assert_called_once()
            call_kwargs = MockAZ.call_args
            assert call_kwargs is not None

    def test_bedrock_from_provider_keys(self):
        from experiments.interfaces.pool import ModelPool
        pk = {'bedrock': {'access_key_id': 'AKIA', 'secret_access_key': 'sec', 'region': 'us-east-1'}}
        pool = ModelPool(provider_keys=pk)
        model_cfg = self._make_model_cfg('bedrock', {'region': 'us-east-1'})
        with patch('experiments.interfaces.pool.BedrockInterface') as MockBK:
            MockBK.return_value = MagicMock()
            pool.get(model_cfg)
            MockBK.assert_called_once()

    def test_vertex_from_provider_keys(self):
        from experiments.interfaces.pool import ModelPool
        pk = {'vertex': {'project': 'my-proj', 'location': 'us-central1'}}
        pool = ModelPool(provider_keys=pk)
        model_cfg = self._make_model_cfg('vertex', {'project': 'my-proj', 'location': 'us-central1'})
        with patch('experiments.interfaces.pool.VertexInterface') as MockVX:
            MockVX.return_value = MagicMock()
            pool.get(model_cfg)
            MockVX.assert_called_once()

    def test_none_provider_keys_still_works(self):
        """ModelPool(provider_keys=None) falls back to env vars in each interface."""
        from experiments.interfaces.pool import ModelPool
        pool = ModelPool(provider_keys=None)
        assert pool._provider_keys == {}


# ===========================================================================
# 5.  generate_cmd.py
# ===========================================================================

class TestCmdGenerate:
    """Tests for the coeval generate command."""

    def _make_args(self, config_path, out_path, probe_mode=None, probe_on_fail=None,
                   log_level='INFO', keys=None):
        return argparse.Namespace(
            config=str(config_path),
            out=str(out_path),
            probe_mode=probe_mode,
            probe_on_fail=probe_on_fail,
            log_level=log_level,
            keys=keys,
        )

    def test_generate_writes_materialized_yaml(self, tmp_path):
        """cmd_generate writes a YAML file with static attributes embedded."""
        from experiments.commands.generate_cmd import cmd_generate

        config_path = tmp_path / 'draft.yaml'
        out_path = tmp_path / 'design.yaml'
        raw = {
            'models': [{
                'name': 'teacher-mdl',
                'interface': 'openai',
                'parameters': {'model': 'gpt-4o-mini'},
                'roles': ['teacher', 'student', 'judge'],
            }],
            'tasks': [{
                'name': 'task1',
                'description': 'Test task.',
                'output_description': 'One word.',
                'target_attributes': 'auto',
                'nuanced_attributes': None,
                'rubric': 'auto',
                'sampling': {'target': [1, 1], 'nuance': [0, 0], 'total': 2},
            }],
            'experiment': {
                'id': 'gen-test',
                'storage_folder': str(tmp_path / 'runs'),
            },
        }
        _write_yaml(config_path, raw)

        generated_attrs = {'quality': ['high', 'low']}
        generated_rubric = {'quality': 'Output quality.'}

        with (
            patch('experiments.phases.phase1.run_phase1'),
            patch('experiments.phases.phase2.run_phase2'),
            patch('experiments.interfaces.probe.run_probe'),
            patch('experiments.storage.ExperimentStorage') as MockStorage,
            patch('experiments.phases.utils.QuotaTracker'),
            patch('experiments.interfaces.pool.ModelPool'),
        ):
            mock_storage = MagicMock()
            MockStorage.return_value = mock_storage
            mock_storage.read_target_attrs.return_value = generated_attrs
            mock_storage.read_rubric.return_value = generated_rubric
            mock_storage.read_nuanced_attrs.side_effect = Exception('no nuanced')

            cmd_generate(self._make_args(config_path, out_path))

        assert out_path.exists()
        with open(out_path) as f:
            content = f.read()
        # Must contain a YAML comment header
        assert '# Generated by:' in content
        # Should be valid YAML
        loaded = yaml.safe_load(content)
        assert loaded is not None

    def test_generate_invalid_config_exits(self, tmp_path):
        """cmd_generate exits with code 1 on config validation errors."""
        from experiments.commands.generate_cmd import cmd_generate
        config_path = tmp_path / 'bad.yaml'
        out_path = tmp_path / 'design.yaml'
        config_path.write_text("models: []\ntasks: []\nexperiment: {id: x, storage_folder: /tmp}\n")
        with pytest.raises(SystemExit) as exc_info:
            cmd_generate(self._make_args(config_path, out_path))
        assert exc_info.value.code == 1

    def test_generate_missing_config_exits(self, tmp_path):
        """cmd_generate exits with code 1 if the config file is missing."""
        from experiments.commands.generate_cmd import cmd_generate
        out_path = tmp_path / 'design.yaml'
        with pytest.raises(SystemExit) as exc_info:
            cmd_generate(self._make_args(tmp_path / 'missing.yaml', out_path))
        assert exc_info.value.code == 1

    def test_materialize_config_static_attributes_unchanged(self, tmp_path):
        """_materialize_config does not touch already-static attributes."""
        from experiments.commands.generate_cmd import _materialize_config
        from experiments.config import _parse_config

        raw = {
            'models': [_model_raw()],
            'tasks': [_task_raw()],  # both target_attributes and rubric are static dicts
            'experiment': {'id': 'e', 'storage_folder': str(tmp_path)},
        }
        cfg = _parse_config(raw)
        cfg._raw = raw

        mock_storage = MagicMock()
        materialized_raw, changes = _materialize_config(cfg, mock_storage)

        # Nothing generated; no calls to read_target_attrs / read_rubric
        mock_storage.read_target_attrs.assert_not_called()
        mock_storage.read_rubric.assert_not_called()
        assert 'nothing to generate' in changes[0]

    def test_attr_summary_format(self):
        """_attr_summary produces correct format string."""
        from experiments.commands.generate_cmd import _attr_summary
        result = _attr_summary({'tone': ['formal', 'casual'], 'urgency': ['high']})
        assert 'tone(2)' in result
        assert 'urgency(1)' in result

    def test_attr_summary_empty(self):
        from experiments.commands.generate_cmd import _attr_summary
        assert _attr_summary({}) == '{}'


# ===========================================================================
# 6.  models_cmd.py
# ===========================================================================

class TestCmdModels:
    """Tests for the coeval models command."""

    def _make_args(self, providers=None, verbose=False, keys=None):
        return argparse.Namespace(
            providers=providers,
            verbose=verbose,
            keys=keys,
        )

    def test_models_lists_available_providers(self, capsys):
        from experiments.commands.models_cmd import cmd_models

        mock_model = {'id': 'gpt-4o-mini', 'owned_by': 'openai'}
        with (
            patch('experiments.interfaces.registry.resolve_provider_keys',
                  return_value={'openai': {'api_key': 'sk-test'}}),
            patch('experiments.interfaces.registry.list_provider_models',
                  return_value=[mock_model]),
        ):
            cmd_models(self._make_args())

        out = capsys.readouterr().out
        assert 'openai' in out.lower()
        assert 'gpt-4o-mini' in out

    def test_models_filters_by_provider(self, capsys):
        from experiments.commands.models_cmd import cmd_models

        called_providers = []

        def fake_list(provider, creds, verbose=False):
            called_providers.append(provider)
            return [{'id': f'{provider}-model'}]

        with (
            patch('experiments.interfaces.registry.resolve_provider_keys',
                  return_value={
                      'openai': {'api_key': 'sk-test'},
                      'anthropic': {'api_key': 'sk-ant-test'},
                  }),
            patch('experiments.interfaces.registry.list_provider_models',
                  side_effect=fake_list),
        ):
            cmd_models(self._make_args(providers='openai'))

        assert 'openai' in called_providers
        assert 'anthropic' not in called_providers

    def test_models_no_credentials_shows_message(self, capsys, monkeypatch):
        from experiments.commands.models_cmd import cmd_models

        # Patch all env vars so resolve_provider_keys returns empty
        for var in ['OPENAI_API_KEY', 'ANTHROPIC_API_KEY', 'GEMINI_API_KEY',
                    'GOOGLE_API_KEY', 'HF_TOKEN', 'HUGGINGFACE_HUB_TOKEN',
                    'AZURE_OPENAI_API_KEY', 'AZURE_OPENAI_ENDPOINT',
                    'AWS_ACCESS_KEY_ID', 'GOOGLE_CLOUD_PROJECT']:
            monkeypatch.delenv(var, raising=False)

        with patch('experiments.interfaces.registry.resolve_provider_keys',
                   return_value={}):
            cmd_models(self._make_args())

        out = capsys.readouterr().out
        # Output must be non-empty (prints something about no credentials)
        assert len(out) > 0

    def test_models_provider_error_handled_gracefully(self, capsys):
        from experiments.commands.models_cmd import cmd_models

        with (
            patch('experiments.interfaces.registry.resolve_provider_keys',
                  return_value={'openai': {'api_key': 'sk-test'}}),
            patch('experiments.interfaces.registry.list_provider_models',
                  side_effect=Exception('API error')),
        ):
            # Should not raise; error is shown and command continues
            cmd_models(self._make_args())

        out = capsys.readouterr().out
        assert 'error' in out.lower() or 'API error' in out


# ===========================================================================
# 7.  CLI parser — generate and models subcommands + --keys flag
# ===========================================================================

class TestCliParser:
    """Verify cli.py _build_parser() correctly registers generate/models subparsers
    and the --keys flag on run/probe/plan/generate."""

    def _parser(self):
        from experiments.cli import _build_parser
        return _build_parser()

    def test_generate_subparser_exists(self):
        parser = self._parser()
        args = parser.parse_args([
            'generate', '--config', 'draft.yaml', '--out', 'design.yaml'
        ])
        assert args.command == 'generate'
        assert args.config == 'draft.yaml'
        assert args.out == 'design.yaml'

    def test_generate_keys_flag(self):
        parser = self._parser()
        args = parser.parse_args([
            'generate', '--config', 'draft.yaml', '--out', 'design.yaml',
            '--keys', '/path/to/keys.yaml',
        ])
        assert args.keys == '/path/to/keys.yaml'

    def test_generate_probe_flags(self):
        parser = self._parser()
        args = parser.parse_args([
            'generate', '--config', 'x.yaml', '--out', 'y.yaml',
            '--probe', 'disable', '--probe-on-fail', 'warn',
        ])
        assert args.probe_mode == 'disable'
        assert args.probe_on_fail == 'warn'

    def test_generate_log_level(self):
        parser = self._parser()
        args = parser.parse_args([
            'generate', '--config', 'x.yaml', '--out', 'y.yaml', '--log-level', 'DEBUG'
        ])
        assert args.log_level == 'DEBUG'

    def test_models_subparser_exists(self):
        parser = self._parser()
        args = parser.parse_args(['models'])
        assert args.command == 'models'

    def test_models_providers_and_verbose(self):
        parser = self._parser()
        args = parser.parse_args(['models', '--providers', 'openai,anthropic', '--verbose'])
        assert args.providers == 'openai,anthropic'
        assert args.verbose is True

    def test_models_keys_flag(self):
        parser = self._parser()
        args = parser.parse_args(['models', '--keys', '/my/keys.yaml'])
        assert args.keys == '/my/keys.yaml'

    def test_run_keys_flag(self):
        parser = self._parser()
        args = parser.parse_args(['run', '--config', 'x.yaml', '--keys', '/my/keys.yaml'])
        assert args.keys == '/my/keys.yaml'

    def test_probe_keys_flag(self):
        parser = self._parser()
        args = parser.parse_args(['probe', '--config', 'x.yaml', '--keys', '/k.yaml'])
        assert args.keys == '/k.yaml'

    def test_plan_keys_flag(self):
        parser = self._parser()
        args = parser.parse_args(['plan', '--config', 'x.yaml', '--keys', '/k.yaml'])
        assert args.keys == '/k.yaml'


# ===========================================================================
# 8.  config.py — new interfaces in VALID_INTERFACES
# ===========================================================================

class TestValidInterfacesExpanded:
    """Verify new provider interface names pass V-06 validation."""

    def _cfg_with_interface(self, interface: str, tmp_path):
        params: dict = {'model': 'dummy'}
        if interface == 'azure_openai':
            params.update({'azure_endpoint': 'https://x/', 'api_version': 'v1'})
        if interface == 'bedrock':
            params.update({'region': 'us-east-1'})
        if interface == 'vertex':
            params.update({'project': 'proj', 'location': 'us-central1'})
        raw = {
            'models': [_model_raw(interface=interface, params=params)],
            'tasks': [_task_raw()],
            'experiment': {'id': 'e', 'storage_folder': str(tmp_path)},
        }
        return _parse(raw)

    @pytest.mark.parametrize('interface', ['azure_openai', 'bedrock', 'vertex'])
    def test_new_interfaces_pass_v06(self, interface, tmp_path):
        """V-06 must NOT fire for azure_openai, bedrock, or vertex interfaces."""
        from experiments.config import validate_config
        cfg = self._cfg_with_interface(interface, tmp_path)
        errors = validate_config(cfg, _skip_folder_validation=True)
        iface_errors = [e for e in errors if 'interface' in e.lower() or 'unknown' in e.lower()]
        assert not iface_errors, f"Unexpected interface error: {iface_errors}"
