"""Provider credential resolution and model-listing registry.

Centralises:
 - Loading a provider key file (YAML) from disk
 - Resolving credentials for each provider (key file → env vars)
 - Listing available text-generation models per provider (used by coeval models)
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Default key file paths
# ---------------------------------------------------------------------------

# keys.yaml at the project root (two levels above this file's package root)
_PROJECT_KEYS_FILE = Path(__file__).parent.parent.parent / 'keys.yaml'
_DEFAULT_KEYS_FILE = Path.home() / '.coeval' / 'keys.yaml'
_ENV_KEYS_FILE = 'COEVAL_KEYS_FILE'


# ---------------------------------------------------------------------------
# Load provider key file
# ---------------------------------------------------------------------------

def load_keys_file(path: str | Path | None = None) -> dict:
    """Load a provider key file (YAML) and return its contents as a dict.

    Lookup order:
    1. ``path`` argument (from ``--keys PATH`` CLI flag)
    2. ``COEVAL_KEYS_FILE`` environment variable
    3. ``keys.yaml`` at the project root (next to ``pyproject.toml``)
    4. ``~/.coeval/keys.yaml`` (global default)

    Returns an empty dict if no file is found or the file cannot be parsed.

    Key file format::

        providers:
          openai: sk-...
          anthropic: sk-ant-...
          gemini: AIza...
          openrouter: sk-or-v1-...
          azure_openai:
            api_key: ...
            endpoint: https://my-resource.openai.azure.com/
            api_version: 2024-08-01-preview
          bedrock:
            api_key: BedrockAPIKey-...:...    # native API key
            region: us-east-1
          vertex:
            project: my-project
            location: us-central1
          huggingface: hf_...
    """
    try:
        import yaml
    except ImportError:
        return {}

    candidates = []
    if path:
        candidates.append(Path(path))
    env_path = os.environ.get(_ENV_KEYS_FILE)
    if env_path:
        candidates.append(Path(env_path))
    candidates.append(_PROJECT_KEYS_FILE)
    candidates.append(_DEFAULT_KEYS_FILE)

    for candidate in candidates:
        if candidate.is_file():
            try:
                with open(candidate, encoding='utf-8') as f:
                    data = yaml.safe_load(f) or {}
                return data.get('providers', data)  # support both {providers: ...} and flat dict
            except Exception:
                return {}
    return {}


# ---------------------------------------------------------------------------
# Credential resolution per provider
# ---------------------------------------------------------------------------

def resolve_provider_keys(keys_file: str | Path | None = None) -> dict[str, dict]:
    """Return a dict mapping provider name → credential dict.

    For each provider, merges:
    1. Provider key file (highest explicit priority)
    2. Standard environment variables (fallback)

    Only providers with at least one credential present are included.
    """
    file_keys = load_keys_file(keys_file)

    resolved: dict[str, dict] = {}

    # OpenAI
    openai_key = (
        _str(file_keys.get('openai'))
        or os.environ.get('OPENAI_API_KEY')
    )
    if openai_key:
        resolved['openai'] = {'api_key': openai_key}

    # Anthropic
    anthropic_key = (
        _str(file_keys.get('anthropic'))
        or os.environ.get('ANTHROPIC_API_KEY')
    )
    if anthropic_key:
        resolved['anthropic'] = {'api_key': anthropic_key}

    # Gemini / Google AI Studio
    gemini_cfg = file_keys.get('gemini', {})
    gemini_key = (
        _str(gemini_cfg) if isinstance(gemini_cfg, str) else gemini_cfg.get('api_key')
        or os.environ.get('GEMINI_API_KEY')
        or os.environ.get('GOOGLE_API_KEY')
    )
    if gemini_key:
        resolved['gemini'] = {'api_key': gemini_key}

    # Azure AI (Foundry / GitHub Models)
    aai_cfg = file_keys.get('azure_ai', {})
    aai_key = (
        _str(aai_cfg) if isinstance(aai_cfg, str) else
        aai_cfg.get('api_key') if isinstance(aai_cfg, dict) else None
        or os.environ.get('AZURE_AI_API_KEY')
        or os.environ.get('GITHUB_TOKEN')
    )
    if aai_key:
        resolved['azure_ai'] = {
            'api_key': aai_key,
            'endpoint': (
                aai_cfg.get('endpoint') if isinstance(aai_cfg, dict) else None
            ) or 'https://models.inference.ai.azure.com',
        }

    # Azure OpenAI
    az_cfg = file_keys.get('azure_openai', {})
    az_key = _str(az_cfg.get('api_key')) if isinstance(az_cfg, dict) else None
    az_endpoint = (
        az_cfg.get('endpoint') if isinstance(az_cfg, dict) else None
    )
    az_key = az_key or os.environ.get('AZURE_OPENAI_API_KEY')
    az_endpoint = az_endpoint or os.environ.get('AZURE_OPENAI_ENDPOINT')
    if az_key and az_endpoint:
        resolved['azure_openai'] = {
            'api_key': az_key,
            'endpoint': az_endpoint,
            'api_version': (
                az_cfg.get('api_version') if isinstance(az_cfg, dict) else None
            ) or os.environ.get('AZURE_OPENAI_API_VERSION') or '2024-08-01-preview',
        }

    # AWS Bedrock
    bk_cfg = file_keys.get('bedrock', {})
    bk_api_key = (
        _str(bk_cfg) if isinstance(bk_cfg, str) else
        bk_cfg.get('api_key') if isinstance(bk_cfg, dict) else None
    )
    bk_key_id = (
        bk_cfg.get('access_key_id') if isinstance(bk_cfg, dict) else None
    ) or os.environ.get('AWS_ACCESS_KEY_ID')
    bk_secret = (
        bk_cfg.get('secret_access_key') if isinstance(bk_cfg, dict) else None
    ) or os.environ.get('AWS_SECRET_ACCESS_KEY')
    bk_region = (
        bk_cfg.get('region') if isinstance(bk_cfg, dict) else None
    ) or os.environ.get('AWS_DEFAULT_REGION') or os.environ.get('AWS_REGION')
    bk_session = (
        bk_cfg.get('session_token') if isinstance(bk_cfg, dict) else None
    ) or os.environ.get('AWS_SESSION_TOKEN')
    if bk_api_key or bk_key_id or bk_secret or bk_region:
        resolved['bedrock'] = {
            'api_key': bk_api_key,
            'access_key_id': bk_key_id,
            'secret_access_key': bk_secret,
            'region': bk_region or 'us-east-1',
            'session_token': bk_session,
        }

    # Google Vertex AI
    vx_cfg = file_keys.get('vertex', {})
    vx_project = (
        vx_cfg.get('project') if isinstance(vx_cfg, dict) else None
    ) or os.environ.get('GOOGLE_CLOUD_PROJECT') or os.environ.get('GCLOUD_PROJECT')
    vx_location = (
        vx_cfg.get('location') if isinstance(vx_cfg, dict) else None
    ) or os.environ.get('GOOGLE_CLOUD_LOCATION') or 'us-central1'
    vx_sa_key = (
        vx_cfg.get('service_account_key') if isinstance(vx_cfg, dict) else None
    ) or os.environ.get('GOOGLE_APPLICATION_CREDENTIALS')
    if vx_project:
        resolved['vertex'] = {
            'project': vx_project,
            'location': vx_location,
            'service_account_key': vx_sa_key,
        }

    # OpenRouter
    or_cfg = file_keys.get('openrouter', {})
    or_key = (
        _str(or_cfg) if isinstance(or_cfg, str) else or_cfg.get('api_key') if isinstance(or_cfg, dict) else None
        or os.environ.get('OPENROUTER_API_KEY')
    )
    if or_key:
        resolved['openrouter'] = {'api_key': or_key}

    # HuggingFace
    hf_cfg = file_keys.get('huggingface', {})
    hf_token = (
        _str(hf_cfg) if isinstance(hf_cfg, str) else hf_cfg.get('token')
        or os.environ.get('HF_TOKEN')
        or os.environ.get('HUGGINGFACE_HUB_TOKEN')
    )
    if hf_token:
        resolved['huggingface'] = {'token': hf_token}

    return resolved


def get_access_key_for_model(
    interface: str,
    model_access_key: str | None,
    provider_keys: dict[str, dict],
) -> str | None:
    """Resolve the primary access key for a model.

    Priority: model-level ``access_key`` → provider key file → env var.
    Returns None if no key is available.
    """
    if model_access_key:
        return model_access_key
    creds = provider_keys.get(interface, {})
    return creds.get('api_key') or creds.get('token')


# ---------------------------------------------------------------------------
# Model listing
# ---------------------------------------------------------------------------

def list_provider_models(
    provider: str,
    creds: dict,
    verbose: bool = False,
) -> list[dict[str, Any]]:
    """Return a list of available text-generation models for *provider*.

    Each item is a dict with at least ``id`` or ``name``.  Additional keys
    (``context_length``, ``owned_by``, etc.) are included when ``verbose=True``.

    Raises exceptions on authentication or network errors (caller handles).
    """
    if provider == 'openai':
        return _list_openai_models(creds, verbose)
    if provider == 'anthropic':
        return _list_anthropic_models(creds, verbose)
    if provider == 'gemini':
        return _list_gemini_models(creds, verbose)
    if provider == 'azure_openai':
        return _list_azure_models(creds, verbose)
    if provider == 'bedrock':
        return _list_bedrock_models(creds, verbose)
    if provider == 'vertex':
        return _list_vertex_models(creds, verbose)
    if provider == 'huggingface':
        return _list_huggingface_models(creds, verbose)
    if provider == 'openrouter':
        return _list_openrouter_models(creds, verbose)
    if provider == 'azure_ai':
        return _list_azure_ai_models(creds, verbose)
    return []


def _list_openai_models(creds: dict, verbose: bool) -> list[dict]:
    import openai
    client = openai.OpenAI(api_key=creds['api_key'])
    response = client.models.list()
    models = [
        {'id': m.id, 'owned_by': m.owned_by}
        for m in response.data
        if _is_text_model(m.id)
    ]
    return sorted(models, key=lambda m: m['id'])


def _list_anthropic_models(creds: dict, verbose: bool) -> list[dict]:
    import anthropic
    client = anthropic.Anthropic(api_key=creds['api_key'])
    response = client.models.list()
    models = [{'id': m.id, 'name': getattr(m, 'display_name', m.id)} for m in response.data]
    return sorted(models, key=lambda m: m['id'])


def _list_gemini_models(creds: dict, verbose: bool) -> list[dict]:
    from google import genai
    client = genai.Client(api_key=creds['api_key'])
    models = []
    for m in client.models.list():
        mid = getattr(m, 'name', None) or getattr(m, 'id', str(m))
        # Only include generative text models (skip embedding-only models)
        if 'embed' in mid.lower():
            continue
        models.append({'id': mid, 'name': getattr(m, 'display_name', mid)})
    return sorted(models, key=lambda m: m['id'])


def _list_azure_models(creds: dict, verbose: bool) -> list[dict]:
    import openai
    client = openai.AzureOpenAI(
        api_key=creds['api_key'],
        azure_endpoint=creds['endpoint'],
        api_version=creds.get('api_version', '2024-08-01-preview'),
    )
    response = client.models.list()
    models = [
        {'id': m.id, 'owned_by': getattr(m, 'owned_by', 'azure')}
        for m in response.data
    ]
    return sorted(models, key=lambda m: m['id'])


def _list_bedrock_models(creds: dict, verbose: bool) -> list[dict]:
    region = creds.get('region', 'us-east-1')
    api_key = creds.get('api_key')
    if api_key:
        return _list_bedrock_models_http(api_key, region)
    import boto3
    session_kwargs: dict = {'region_name': region}
    if creds.get('access_key_id'):
        session_kwargs['aws_access_key_id'] = creds['access_key_id']
        session_kwargs['aws_secret_access_key'] = creds['secret_access_key']
        if creds.get('session_token'):
            session_kwargs['aws_session_token'] = creds['session_token']
    session = boto3.Session(**session_kwargs)
    client = session.client('bedrock')
    response = client.list_foundation_models(byOutputModality='TEXT')
    models = [
        {
            'id': m['modelId'],
            'name': m.get('modelName', m['modelId']),
            'owned_by': m.get('providerName', ''),
        }
        for m in response.get('modelSummaries', [])
        if 'TEXT' in m.get('outputModalities', [])
    ]
    return sorted(models, key=lambda m: m['id'])


def _list_bedrock_models_http(api_key: str, region: str) -> list[dict]:
    """List Bedrock foundation models using the native API key (no boto3)."""
    import json
    import urllib.error
    import urllib.request
    url = f"https://bedrock.{region}.amazonaws.com/foundation-models?byOutputModality=TEXT"
    req = urllib.request.Request(url, headers={'x-amzn-bedrock-key': api_key})
    try:
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        raw = exc.read()
        try:
            err = json.loads(raw)
        except Exception:
            err = {'message': raw.decode('utf-8', errors='replace')}
        raise RuntimeError(
            f"Bedrock HTTP {exc.code}: {err.get('message', str(err))}"
        ) from exc
    models = [
        {
            'id': m['modelId'],
            'name': m.get('modelName', m['modelId']),
            'owned_by': m.get('providerName', ''),
        }
        for m in data.get('modelSummaries', [])
        if 'TEXT' in m.get('outputModalities', [])
    ]
    return sorted(models, key=lambda m: m['id'])


def _list_vertex_models(creds: dict, verbose: bool) -> list[dict]:
    """List Gemini models available via Vertex AI."""
    try:
        import vertexai
        from vertexai.generative_models import GenerativeModel
        vertexai.init(
            project=creds['project'],
            location=creds.get('location', 'us-central1'),
        )
    except ImportError:
        raise ImportError(
            "google-cloud-aiplatform is required for Vertex AI: "
            "pip install google-cloud-aiplatform"
        )
    # Vertex AI Gemini models are not dynamically listed via an API;
    # return the known set of publishable Gemini model IDs.
    known = [
        'gemini-1.0-pro',
        'gemini-1.5-flash',
        'gemini-1.5-pro',
        'gemini-2.0-flash-001',
        'gemini-2.0-flash-lite-001',
        'gemini-2.0-pro-exp-02-05',
    ]
    return [{'id': m, 'name': m} for m in known]


def _list_huggingface_models(creds: dict, verbose: bool) -> list[dict]:
    """Return the top-20 trending text-generation models from the Hub."""
    try:
        from huggingface_hub import HfApi
    except ImportError:
        raise ImportError("huggingface_hub is required: pip install huggingface_hub")
    api = HfApi(token=creds.get('token'))
    models = api.list_models(
        filter='text-generation',
        sort='downloads',
        limit=20,
        token=creds.get('token'),
    )
    return [{'id': m.modelId, 'name': m.modelId} for m in models]


def _list_azure_ai_models(creds: dict, verbose: bool) -> list[dict]:
    """Return models available at the Azure AI / GitHub Models endpoint."""
    import openai
    client = openai.OpenAI(
        api_key=creds['api_key'],
        base_url=creds.get('endpoint', 'https://models.inference.ai.azure.com'),
    )
    response = client.models.list()
    models = [{'id': m.id, 'name': getattr(m, 'name', m.id)} for m in response.data]
    return sorted(models, key=lambda m: m['id'])


def _list_openrouter_models(creds: dict, verbose: bool) -> list[dict]:
    """Return all text-generation models available on OpenRouter."""
    import openai
    client = openai.OpenAI(
        api_key=creds['api_key'],
        base_url="https://openrouter.ai/api/v1",
    )
    response = client.models.list()
    models = [{'id': m.id, 'name': getattr(m, 'name', m.id)} for m in response.data]
    return sorted(models, key=lambda m: m['id'])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_TEXT_PREFIXES = (
    'gpt-', 'o1', 'o3', 'text-', 'chatgpt-', 'babbage', 'davinci', 'curie', 'ada',
)
_NON_TEXT_SUFFIXES = ('-embedding', '-tts', '-whisper', '-dall-e', '-moderation', 'audio', 'realtime', 'vision')


def _is_text_model(model_id: str) -> bool:
    """Heuristic filter: returns True for OpenAI models likely to be chat/completion."""
    lower = model_id.lower()
    if any(lower.endswith(s) for s in _NON_TEXT_SUFFIXES):
        return False
    return any(lower.startswith(p) for p in _TEXT_PREFIXES)


def _str(value: Any) -> str | None:
    """Return string value or None."""
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None
