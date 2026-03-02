"""coeval models — list available text-generation models from each provider.

Queries each configured provider's model-listing endpoint and prints which models
are available given the resolved API credentials.  Only providers whose credentials
are resolvable (via config, provider key file, or environment variables) are queried.

Usage::

    # List models for providers whose keys are in the environment / key file:
    coeval models

    # Use a specific provider key file:
    coeval models --keys ~/.coeval/keys.yaml

    # Show only models from specific providers:
    coeval models --providers openai,anthropic

    # Show verbose details (context window, pricing tier, etc.) where available:
    coeval models --verbose
"""
from __future__ import annotations

import argparse
import sys


def cmd_models(args: argparse.Namespace) -> None:
    """Entry point for ``coeval models``."""
    from ..interfaces.registry import list_provider_models, resolve_provider_keys

    keys_file = getattr(args, 'keys', None)
    provider_filter: set[str] | None = None
    if getattr(args, 'providers', None):
        provider_filter = {p.strip() for p in args.providers.split(',') if p.strip()}

    verbose = getattr(args, 'verbose', False)

    provider_keys = resolve_provider_keys(keys_file=keys_file)

    # Determine which providers to query
    all_providers = ['openai', 'anthropic', 'gemini', 'azure_openai', 'azure_ai', 'bedrock', 'vertex', 'huggingface', 'openrouter']
    active_providers = [
        p for p in all_providers
        if (provider_filter is None or p in provider_filter)
    ]

    any_found = False
    for provider in active_providers:
        creds = provider_keys.get(provider, {})
        if not creds:
            _print_provider_header(provider)
            print("  (no credentials — set keys in provider key file or environment)")
            print()
            continue

        try:
            models = list_provider_models(provider, creds, verbose=verbose)
        except Exception as exc:
            _print_provider_header(provider)
            msg = str(exc).encode(sys.stdout.encoding or 'utf-8', errors='replace').decode(sys.stdout.encoding or 'utf-8', errors='replace')
            print(f"  ERROR: {msg}")
            print()
            continue

        if not models:
            _print_provider_header(provider)
            print("  (no models listed)")
            print()
            continue

        any_found = True
        _print_provider_header(provider)
        if verbose:
            for m in models:
                name = m.get('id', m.get('name', '?'))
                details = []
                if m.get('context_length'):
                    details.append(f"ctx={m['context_length']:,}")
                if m.get('owned_by'):
                    details.append(f"owner={m['owned_by']}")
                detail_str = f"  ({', '.join(details)})" if details else ''
                print(f"  {name}{detail_str}")
        else:
            for m in models:
                name = m.get('id', m.get('name', '?'))
                print(f"  {name}")
        print()

    if not any_found and not provider_filter:
        print(
            "No provider credentials found.\n"
            "Set API keys in environment variables, a provider key file, or pass --keys PATH.\n"
            "\nExpected environment variables:\n"
            "  OPENAI_API_KEY, ANTHROPIC_API_KEY, GEMINI_API_KEY / GOOGLE_API_KEY,\n"
            "  AWS_ACCESS_KEY_ID + AWS_SECRET_ACCESS_KEY + AWS_DEFAULT_REGION,\n"
            "  AZURE_OPENAI_API_KEY + AZURE_OPENAI_ENDPOINT, HF_TOKEN"
        )


def _print_provider_header(provider: str) -> None:
    labels = {
        'openai': 'OpenAI',
        'anthropic': 'Anthropic',
        'gemini': 'Google Gemini',
        'azure_openai': 'Azure OpenAI',
        'azure_ai': 'Azure AI (Foundry / GitHub Models)',
        'bedrock': 'AWS Bedrock',
        'vertex': 'Google Vertex AI',
        'huggingface': 'HuggingFace Hub',
        'openrouter': 'OpenRouter',
    }
    label = labels.get(provider, provider)
    print("-" * 60)
    print(f"  {label}")
    print("-" * 60)
