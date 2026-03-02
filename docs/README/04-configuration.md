# Configuration Guide

[← Quick Start](03-quick-start.md) · [Providers →](05-providers.md)

---

A CoEval experiment is a single YAML file with three top-level sections:

```yaml
models:       [ ... ]   # who participates and in what role
tasks:        [ ... ]   # what to evaluate and how
experiment:             # pipeline settings, storage, quotas, batching
  id: my-experiment-v1
  storage_folder: ./eval_runs
```

## Models

Each model entry specifies a provider interface, the model ID understood by that provider, the roles it plays, and optional per-role parameter overrides.

```yaml
models:
  - name: gpt-4o                    # unique ID used in filenames and reports
    interface: openai               # provider interface (see Interfaces page)
    parameters:
      model: gpt-4o                 # provider's model identifier
      temperature: 0.7
      max_tokens: 512
    roles: [teacher, student, judge]

    # Per-role parameter overrides (applied on top of parameters above)
    role_parameters:
      teacher:
        temperature: 0.8
        max_tokens: 768
      student:
        temperature: 0.7
        max_tokens: 512
      judge:
        temperature: 0.0   # deterministic for consistent scoring
        max_tokens: 256

    # Optional: embed credentials directly (prefer keys.yaml instead)
    # access_key: sk-...
```

### Automatic Provider Selection

`interface: auto` tells CoEval to select the cheapest available provider for this model at config load time. It scans `benchmark/provider_pricing.yaml`'s `auto_routing` table and picks the first interface for which credentials exist in your key file:

```yaml
- name: deepseek-v3
  interface: auto           # resolves to deepseek, openrouter, or bedrock
  parameters:
    model: deepseek/deepseek-chat
  roles: [student]
```

The resolved interface is logged at `DEBUG` level. Run `coeval plan` to see which provider was selected before committing to a run.

---

## Tasks

Each task defines what the pipeline should evaluate and how.

```yaml
tasks:
  - name: text_summarization        # unique ID used in filenames
    description: >
      Produce a concise one-sentence summary of a news article.
    output_description: >
      A single sentence of 15–25 words capturing the article's main point.

    # Structural dimensions — drive coverage across evaluation space
    target_attributes:
      article_length:  [short, medium, long]
      domain:          [politics, sports, technology]
      # Use 'auto' to let teacher models infer dimensions:
      # target_attributes: auto

    # Diversity dimensions — sampled per item; prevent distribution collapse
    nuanced_attributes:
      writing_style:   [formal, conversational]
      specificity:     [concrete_details, high_level_overview]

    sampling:
      target: [1, 1]   # sample exactly 1 target attribute value per item
      nuance: [1, 2]   # sample 1–2 nuanced attribute values per item
      total:  50       # 50 benchmark items per (task, teacher) pair

    rubric:
      relevance:    "The summary accurately reflects the article's main claim."
      conciseness:  "The summary is free of redundant or filler language."
      fluency:      "The summary reads as natural, grammatically correct English."
      # Use 'auto' to let teachers generate rubric dimensions:
      # rubric: auto

    evaluation_mode: single   # single | per_factor
```

---

## Sampling & Diversity

| Field | Type | Description |
|-------|------|-------------|
| `target_attributes` | `dict` \| `"auto"` \| `"complete"` | Structural coverage dimensions. `auto` = LLM-generated; `complete` = full cross-product |
| `nuanced_attributes` | `dict` \| `"auto"` | Per-item diversity dimensions; keep outputs naturalistic and varied |
| `sampling.target` | `[min, max]` \| `"all"` | How many target attribute values to sample per item |
| `sampling.nuance` | `[min, max]` | How many nuance attribute values to sample per item |
| `sampling.total` | `int` | Total benchmark items per (task, teacher) pair |
| `store_nuanced` | `bool` | Persist nuance sample metadata in JSONL records (default: `false`) |

> **Distribution collapse** occurs when all benchmark items look the same. `nuanced_attributes` injects per-item variation (tone, register, domain, writing style) that makes synthetic data behave more like real-world distributions.

---

## Rubric & Evaluation Mode

```yaml
rubric:
  relevance:    "The summary accurately reflects the article's main claim."
  conciseness:  "The summary is free of redundant or filler language."
  fluency:      "The summary reads as natural, grammatically correct English."

evaluation_mode: single   # one judge call per response; all dimensions at once
# evaluation_mode: per_factor  # one judge call per rubric dimension per response
```

| `rubric` value | Behavior |
|----------------|----------|
| `{key: "criterion", ...}` | Use this static rubric; Phases 1–2 make zero LLM calls |
| `auto` | Teachers generate rubric dimensions from the task description |
| `extend` | Merge new dimensions onto an inherited rubric (requires `resume_from`) |

| `evaluation_mode` | Calls per response | Use when |
|-------------------|--------------------|----------|
| `single` | 1 | Holistic scoring; lower cost; judges return all dimension scores at once |
| `per_factor` | N (one per rubric dimension) | Maximum granularity; dimension-level analysis; higher cost |

---

## Experiment Settings

```yaml
experiment:
  id: paper-eval-v1
  storage_folder: ./eval_runs

  # Fork phases 1–2 from an existing run (attribute and rubric reuse)
  # resume_from: ./eval_runs/paper-eval-v0

  # Per-phase execution mode: New | Keep | Extend | Model
  phases:
    attribute_mapping:   Keep     # re-use existing attribute files
    rubric_mapping:      Keep     # re-use existing rubric files
    data_generation:     Extend   # append missing items only
    response_collection: Extend
    evaluation:          Extend

  # Hard API call ceilings per model (prevents runaway cost)
  quota:
    gpt-4o:
      max_calls: 5000
    claude-sonnet-4-6:
      max_calls: 5000

  # Batch API (50% discount for OpenAI, Anthropic, Gemini)
  batch:
    openai:
      response_collection: true
      evaluation: true
    anthropic:
      response_collection: true
      evaluation: true
    gemini:
      response_collection: true
      evaluation: true

  # Model probe configuration
  probe_mode: full        # full | resume | disable
  probe_on_fail: abort    # abort | warn

  # Cost estimation
  estimate_cost: true
  estimate_samples: 2     # live sample calls per model (0 = heuristics only)

  log_level: INFO
  generation_retries: 2
```

### Phase Execution Modes

| Mode | Behavior |
|------|----------|
| `New` | Start fresh; fails if output files exist (prevents accidental overwrite) |
| `Keep` | Skip files that already exist; safe to add new models to a partial run |
| `Extend` | Append only missing JSONL records; never rewrites existing data |
| `Model` | Re-use existing teacher output directly (Phase 3 only) |

---

## Prompt Templates

CoEval ships canonical prompt templates for all five phases. Override them at task level or for a specific model:

```yaml
tasks:
  - name: code_explanation
    prompt_library:

      # Override Phase 3 teacher prompt for this entire task
      sample: |
        Generate a benchmark item for: {task_description}
        Output format: {output_description}
        Target attributes: {target_attributes}
        Nuance dimensions: {nuanced_attributes}
        Return JSON: {{"prompt": "<code snippet>", "response": "<explanation>"}}

      # Override only for gpt-4o-mini; canonical applies to all other models
      sample.gpt-4o-mini: >
        Create a realistic {task_description} benchmark item with these attributes:
        {target_attributes} and naturalisation: {nuanced_attributes}.
        JSON only — keys "prompt" and "response".
```

**Available template IDs:**

| ID | Phase | Role | Key variables |
|----|-------|------|---------------|
| `sample` | 3 — data generation | teacher | `{task_description}`, `{output_description}`, `{target_attributes}`, `{nuanced_attributes}` |
| `test` | 4 — response collection | student | `{input}`, `{task_description}`, `{output_description}` |
| `evaluate_single` | 5 — evaluation (single mode) | judge | `{input}`, `{response}`, `{reference}`, `{rubric}` |
| `evaluate_per_factor` | 5 — evaluation (per-factor mode) | judge | `{input}`, `{response}`, `{reference}`, `{factor}`, `{criterion}` |

> **Escaping braces in YAML:** Use `{{` and `}}` to produce literal `{` and `}` in template text (e.g., for JSON examples). Python's `str.format()` processes all templates before they reach the model.

---

## Provider Key File

Store all credentials in one place. CoEval discovers and resolves them automatically.

**Search order:**
1. `--keys PATH` CLI flag
2. `COEVAL_KEYS_FILE` environment variable
3. `keys.yaml` at the project root
4. `~/.coeval/keys.yaml`

```yaml
# ~/.coeval/keys.yaml
providers:
  openai:      sk-...
  anthropic:   sk-ant-...
  gemini:      AIza...
  huggingface: hf_...
  openrouter:  sk-or-v1-...
  groq:        gsk_...
  deepseek:    sk-...
  mistral:     ...

  azure_openai:
    api_key:     ...
    endpoint:    https://my-resource.openai.azure.com/
    api_version: 2024-08-01-preview

  bedrock:
    api_key: BedrockAPIKey-...:...    # native API key (no boto3 needed)
    region:  us-east-1
  # — OR — IAM credentials:
  # bedrock:
  #   access_key_id:     AKIA...
  #   secret_access_key: ...
  #   region:            us-east-1

  vertex:
    project:  my-gcp-project
    location: us-central1
    service_account_key: /path/to/key.json   # optional; uses ADC if omitted
```

**Credential resolution order per model:**
```
model.access_key (in YAML)  →  provider entry in keys.yaml  →  environment variable
```

> **Security:** `keys.yaml`, `*.keys.yaml`, and `.coeval/` are included in `.gitignore` by default. Never commit credentials to version control.

---

## Complete Example Configurations

### Example 1: Minimal Sentiment Classification

Single model acting as teacher, student, and judge. 20 items. Uses `label_attributes` for judge-free exact-match scoring on the `sentiment` dimension.

```yaml
models:
  - name: gpt-4o-mini
    interface: openai
    parameters: { model: gpt-4o-mini, temperature: 0.7, max_tokens: 512 }
    roles: [teacher, student, judge]

tasks:
  - name: sentiment_classification
    description: Classify the sentiment of a customer product review as Positive or Negative.
    output_description: A single word — Positive or Negative.
    target_attributes:
      sentiment: [positive, negative]
      product_category: [electronics, clothing, food]
    nuanced_attributes:
      writing_style: [formal, casual, emotional]
      review_length: [short, detailed]
    sampling: { target: [1,2], nuance: [1,2], total: 20 }
    rubric:
      label_accuracy: "The predicted label matches the true sentiment of the review."
      reasoning:      "The classification is consistent with the tone and language used."
    label_attributes: [sentiment]
    evaluation_mode: single

experiment:
  id: sentiment-v1
  storage_folder: ./eval_runs
```

### Example 2: Multi-Model Code Review

Three models with distinct roles. Teachers and judges use `gpt-4o` and `claude-3-5-haiku`; `gpt-4o-mini` is student-only. Batch API enabled for both OpenAI and Anthropic. Rubric is auto-generated by the teacher. A quota ceiling protects against runaway teacher costs.

```yaml
models:
  - name: gpt-4o
    interface: openai
    parameters: { model: gpt-4o, temperature: 0.7, max_tokens: 1024 }
    roles: [teacher, judge]
    role_parameters:
      judge: { temperature: 0.0, max_tokens: 256 }

  - name: claude-3-5-haiku
    interface: anthropic
    parameters: { model: claude-3-5-haiku-20241022, temperature: 0.7, max_tokens: 1024 }
    roles: [student, judge]
    role_parameters:
      judge: { temperature: 0.0, max_tokens: 256 }

  - name: gpt-4o-mini
    interface: openai
    parameters: { model: gpt-4o-mini, temperature: 0.7, max_tokens: 512 }
    roles: [student]

tasks:
  - name: code_review
    description: >
      Review a Python function and identify bugs, code quality issues,
      and improvement suggestions.
    output_description: >
      A structured code review with sections: Bugs Found, Quality Issues,
      and Improvement Suggestions.
    target_attributes:
      bug_type: [logic_error, off_by_one, null_handling, performance]
      code_complexity: [simple, moderate, complex]
      language_feature: [loops, recursion, list_comprehension, classes]
    nuanced_attributes:
      code_style: [clean, messy, over_engineered]
      comment_density: [no_comments, sparse_comments, well_documented]
    sampling: { target: [1,2], nuance: [1,1], total: 40 }
    rubric: auto    # teachers auto-generate rubric dimensions
    evaluation_mode: single

experiment:
  id: code-review-v1
  storage_folder: ./eval_runs
  batch:
    openai:
      response_collection: true
      evaluation: true
    anthropic:
      response_collection: true
      evaluation: true
  quota:
    gpt-4o:
      max_calls: 1000
```

### Example 3: Education Benchmark (Real Datasets + Synthetic Tasks)

Combines a `benchmark` virtual interface (pre-ingested ARC-Challenge dataset responses) with a synthetic task.

```yaml
models:
  - name: arc-challenge
    interface: benchmark
    roles: [teacher]

  - name: gpt-4o-mini
    interface: openai
    parameters: { model: gpt-4o-mini, temperature: 0.7, max_tokens: 512 }
    roles: [teacher, student, judge]

  - name: gpt-4o
    interface: openai
    parameters: { model: gpt-4o, temperature: 0.7, max_tokens: 512 }
    roles: [student, judge]

tasks:
  - name: arc_science_reasoning
    category: benchmark
    description: >
      Answer a multiple-choice science question by selecting the correct answer
      from four options (A, B, C, D).
    output_description: A single letter — A, B, C, or D.
    target_attributes:
      grade_band: [grade_3_5, grade_6_8, grade_9_10]
      knowledge_type: [factual, conceptual, procedural]
    sampling: { target: [1,1], nuance: [0,0], total: 30 }
    rubric:
      correctness:   "The selected answer matches the correct option."
      justification: "The reasoning (if provided) supports the chosen answer."
    evaluation_mode: single

  - name: science_experiment_design
    category: synthetic
    description: >
      Design a simple experiment to test a hypothesis about a natural phenomenon,
      suitable for middle school students.
    output_description: >
      A structured experiment plan with: hypothesis, materials, procedure (3–5 steps),
      and expected results.
    target_attributes:
      science_domain: [biology, chemistry, physics, earth_science]
      difficulty_level: [elementary, middle_school, high_school]
    nuanced_attributes:
      context_type: [classroom, home, outdoor]
      prior_knowledge: [no_prior, some_prior]
    sampling: { target: [1,2], nuance: [1,1], total: 30 }
    rubric: auto
    evaluation_mode: single

experiment:
  id: education-benchmark-v1
  storage_folder: ./eval_runs
  batch:
    openai:
      response_collection: true
      evaluation: true
  estimate_samples: 0
```

### Example 4: Customer Support Email (Per-Factor Evaluation, Prompt Override)

Uses `evaluation_mode: per_factor` to score each rubric dimension in a separate judge call, enabling fine-grained dimension-level analysis.

```yaml
models:
  - name: gpt-4o
    interface: openai
    parameters: { model: gpt-4o, temperature: 0.8, max_tokens: 1024 }
    roles: [teacher]

  - name: gpt-4o-mini
    interface: openai
    parameters: { model: gpt-4o-mini, temperature: 0.7, max_tokens: 1024 }
    roles: [student, judge]

  - name: claude-3-5-haiku
    interface: anthropic
    parameters: { model: claude-3-5-haiku-20241022, temperature: 0.7, max_tokens: 1024 }
    roles: [student, judge]

tasks:
  - name: customer_support_email
    description: >
      Compose a professional customer support email response to a customer complaint
      or inquiry, representing a software company.
    output_description: >
      A complete professional email with greeting, body addressing the customer's
      issue, proposed resolution, and closing.
    target_attributes:
      issue_type: [billing_error, feature_request, bug_report, account_access, cancellation]
      customer_tone: [frustrated, polite, confused, urgent]
      issue_severity: [minor, moderate, critical]
    nuanced_attributes:
      company_size: [startup, mid_market, enterprise]
      product_domain: [saas, ecommerce, fintech]
    sampling: { target: [1,2], nuance: [1,2], total: 50 }
    rubric:
      professionalism: "The email maintains a courteous, professional tone throughout."
      issue_resolution: "The response directly addresses the customer's specific concern."
      empathy:          "The reply acknowledges the customer's feelings and inconvenience."
      actionability:    "The response provides clear next steps or a concrete resolution path."
      clarity:          "The writing is clear, concise, and easy to understand."
    evaluation_mode: per_factor   # one judge call per rubric dimension
    prompt_library:
      sample: |
        Create a customer support scenario for a {task_description}.
        Issue context attributes: {target_attributes}
        Style variation: {nuanced_attributes}
        Return JSON with keys:
          "prompt": the customer's original message/complaint (100-200 words)
          "response": the ideal support reply (150-300 words)
        Output only the JSON, no explanation.

experiment:
  id: customer-support-v1
  storage_folder: ./eval_runs
  batch:
    openai:
      response_collection: true
      evaluation: true
    anthropic:
      response_collection: true
      evaluation: true
```

### Example 5: Mixed Open-Source + API Experiment with OpenRouter

Evaluates four open-source models (via OpenRouter) and one model using `interface: auto`.

```yaml
models:
  - name: gpt-4o-mini
    interface: openai
    parameters: { model: gpt-4o-mini, temperature: 0.7, max_tokens: 512 }
    roles: [teacher, judge]
    role_parameters:
      judge: { temperature: 0.0, max_tokens: 128 }

  - name: llama-3.3-70b
    interface: openrouter
    parameters:
      model: meta-llama/llama-3.3-70b-instruct
      temperature: 0.7
      max_tokens: 512
    roles: [student]

  - name: qwen2.5-72b
    interface: openrouter
    parameters:
      model: qwen/qwen-2.5-72b-instruct
      temperature: 0.7
      max_tokens: 512
    roles: [student]

  - name: mistral-large
    interface: openrouter
    parameters:
      model: mistralai/mistral-large
      temperature: 0.7
      max_tokens: 512
    roles: [student]

  - name: deepseek-v3
    interface: auto     # resolves to cheapest available provider
    parameters:
      model: deepseek/deepseek-chat
      temperature: 0.7
      max_tokens: 512
    roles: [student]

tasks:
  - name: sql_generation
    description: >
      Generate a SQL query from a natural language description of what data
      to retrieve from a given database schema.
    output_description: >
      A single valid SQL SELECT statement with appropriate JOINs, WHERE clauses,
      and aggregations as needed.
    target_attributes:
      query_complexity: [simple_select, join, aggregation, subquery, window_function]
      database_domain:  [ecommerce, analytics, hr, inventory, financial]
      table_count:      [one_table, two_tables, three_or_more]
    nuanced_attributes:
      schema_style: [snake_case, camelCase, abbreviated]
      data_size:    [small, large]
    sampling: { target: [1,2], nuance: [1,1], total: 30 }
    rubric:
      syntactic_correctness: "The SQL is syntactically valid."
      semantic_correctness:  "The query retrieves what the description asks for."
      efficiency:            "The query avoids unnecessary computations or redundant joins."
    evaluation_mode: single

experiment:
  id: sql-generation-v1
  storage_folder: ./eval_runs
  quota:
    gpt-4o-mini:
      max_calls: 2000
  probe_mode: full
  probe_on_fail: warn
```

---

## Label Accuracy for Classification Tasks

For classification and information-extraction tasks where the correct output is a discrete label, CoEval can skip the judge entirely and use exact-match comparison via `label_attributes`.

```yaml
tasks:
  - name: topic_classification
    description: Classify a news headline into one of five topic categories.
    output_description: >
      A single word from this list: politics, technology, sports, business, entertainment.
    target_attributes:
      topic: [politics, technology, sports, business, entertainment]
      headline_style: [sensational, factual, ambiguous]
    sampling: { target: [1,1], nuance: [0,1], total: 30 }
    # label_attributes enables judge-free exact-match scoring
    # for each listed attribute value in the output
    label_attributes: [topic]
    rubric:
      accuracy: "The topic label matches the true category of the headline."
    evaluation_mode: single
```

When `label_attributes` is set, Phase 5 uses exact-match comparison instead of calling judge models, making evaluation free and deterministic. The judge still scores rubric dimensions that are not label attributes.

---

## Multi-Role Model Parameters

A model can hold any combination of `teacher`, `student`, and `judge` roles. Use `role_parameters` to override generation settings per role:

```yaml
- name: gpt-4o-mini
  interface: openai
  roles: [teacher, student, judge]
  parameters:
    model: gpt-4o-mini
    temperature: 0.7
    max_tokens: 512
  role_parameters:
    teacher:
      temperature: 0.8   # slightly higher creativity for generation
      max_tokens: 512
    student:
      temperature: 0.7
      max_tokens: 256
    judge:
      temperature: 0.0   # deterministic scoring
      max_tokens: 128
```

`role_parameters` values are merged on top of `parameters` — only the keys you specify are overridden.

---

[← Quick Start](03-quick-start.md) · [Providers →](05-providers.md)
