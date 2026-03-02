# Config/

Shared configuration files used at runtime by the CoEval pipeline.

## Contents

| File | Description |
|------|-------------|
| [`provider_pricing.yaml`](provider_pricing.yaml) | Per-model pricing table (input/output $/1M tokens) and `auto_routing` table used by `interface: auto` to pick the cheapest available provider |

## `provider_pricing.yaml`

Two sections:

### `providers`

Maps model identifiers to per-interface pricing:

```yaml
providers:
  gpt-4o:
    openai:
      input:  2.50   # $ per 1M input tokens
      output: 10.00  # $ per 1M output tokens
    azure_openai:
      input:  2.50
      output: 10.00
```

### `auto_routing`

Ordered list used by `interface: auto` — CoEval picks the first entry for which credentials exist:

```yaml
auto_routing:
  deepseek/deepseek-chat: {interface: openrouter, notes: "cheapest"}
  deepseek:               {interface: deepseek,   notes: "direct"}
```

Entries are ordered cheapest-first. Edit this file to add new models or change routing priority.

## Editing

- **To add a model:** add a new key under `providers:` with its interface/price pairs.
- **To update prices:** find the model + interface entry and update `input:` / `output:`.
- **To change routing:** reorder entries in `auto_routing:` or add new model patterns.

The cost estimator (`Code/runner/interfaces/cost_estimator.py`) loads this file at runtime. If unavailable, it falls back to a hardcoded `PRICE_TABLE` constant.

## Related

- [`docs/README/05-providers.md`](../docs/README/05-providers.md) — provider auth setup, batch support, and pricing tables
- [`docs/cli_reference.md`](../docs/cli_reference.md) — `interface: auto` documentation
