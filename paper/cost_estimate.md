# Paper Experiment Cost Estimate
> Config: `benchmark/paper_benchmarks.yaml`
> Updated: 2026-03-02

---

## Setup

| Dimension | Value |
|-----------|-------|
| Tasks | 4 (text_summarization, code_explanation, email_composition, data_interpretation) |
| Items per task | 620 (pre-emitted from benchmark datasets) |
| **Total datapoints** | **2,480** |
| Students (API) | gpt-4o, gpt-4o-mini, gpt-3.5-turbo, claude-opus-4-6, claude-sonnet-4-6 |
| Students (HuggingFace, free) | qwen2p5-0b5, qwen2p5-1b5, smollm2-1b7 |
| Judges | gpt-4o, gpt-4o-mini, claude-opus-4-6 |
| Phases 1-3 | Keep (pre-emitted — **$0 cost**) |
| Phases 4-5 | New |

---

## Token Assumptions

**Phase 4 (student response generation)**
- Input: ~400 tokens (task context + output description + benchmark prompt)
- Output: ~250 tokens (max_tokens=512; typical response length)

**Phase 5 (judge evaluation)**
- Input: ~920 tokens (prompt + student response + rubric + eval instructions)
- Output: ~150 tokens (JSON scores per rubric aspect; max_tokens=256)

*Token counts are heuristic estimates (4 chars/token).  Actual costs may vary ±20%.*

---

## Phase 4 — Response Collection

> 5 API students × 2,480 items = **12,400 calls**

| Model | Interface | Calls | Input M-tok | Output M-tok | Price (in/out) | **Cost** |
|-------|-----------|-------|-------------|--------------|----------------|----------|
| gpt-4o | openai | 2,480 | 0.992 | 0.620 | $2.50 / $10.00 | **$8.68** |
| gpt-4o-mini | openai | 2,480 | 0.992 | 0.620 | $0.15 / $0.60 | **$0.52** |
| gpt-3.5-turbo | openai | 2,480 | 0.992 | 0.620 | $0.50 / $1.50 | **$1.43** |
| claude-opus-4-6 | anthropic | 2,480 | 0.992 | 0.620 | $15.00 / $75.00 | **$61.38** |
| claude-sonnet-4-6 | anthropic | 2,480 | 0.992 | 0.620 | $3.00 / $15.00 | **$12.27** |
| qwen2p5-0b5 | huggingface | 2,480 | — | — | free | **$0** |
| qwen2p5-1b5 | huggingface | 2,480 | — | — | free | **$0** |
| smollm2-1b7 | huggingface | 2,480 | — | — | free | **$0** |
| **Phase 4 total** | | **12,400** | | | | **$84.28** |

---

## Phase 5 — Evaluation

> 3 judges × 8 students × 2,480 items = **59,520 calls** (19,840 per judge)

| Judge | Calls | Input M-tok | Output M-tok | Price (in/out) | **Cost** |
|-------|-------|-------------|--------------|----------------|----------|
| gpt-4o | 19,840 | 18.25 | 2.98 | $2.50 / $10.00 | **$75.39** |
| gpt-4o-mini | 19,840 | 18.25 | 2.98 | $0.15 / $0.60 | **$4.53** |
| claude-opus-4-6 | 19,840 | 18.25 | 2.98 | $15.00 / $75.00 | **$496.99** |
| **Phase 5 total** | **59,520** | | | | **$576.91** |

---

## Grand Total — Scenarios

| Scenario | Phase 4 | Phase 5 | **Total** | Notes |
|----------|---------|---------|-----------|-------|
| 🔴 No batch API | $84.28 | $576.91 | **$661.19** | Baseline |
| 🟡 Batch API (50% off OpenAI + Anthropic) | $42.14 | $288.46 | **$330.60** | Add `batch:` block to config |
| 🟢 **Replace claude-opus judge → claude-3-5-haiku** | $84.28 | $106.44 | **$190.72** | See below |
| ✅ **Replace judge + Batch API** | $42.14 | $53.22 | **$95.36** | **Recommended** |

> **Cost driver:** `claude-opus-4-6` as judge accounts for **75%** of total cost ($497 / $661).

---

## Alternative Judge Comparison (Phase 5 only)

| Judge model | 19,840 calls | Phase 5 cost | vs. claude-opus-4-6 |
|------------|--------------|--------------|---------------------|
| claude-opus-4-6 | current | $496.99 | — |
| claude-3-5-sonnet | current | $86.38 | −$410 |
| claude-3-5-haiku | alternative | $26.52 | −$470 |
| gpt-4o | current | $75.39 | −$421 |
| gpt-4o-mini | current | $4.53 | −$492 |

*claude-3-5-haiku at $0.80/$4.00 per 1M tokens is the cheapest high-quality judge.*

---

## Recommendation

**For full paper run (3-judge ensemble required):**

```yaml
# In paper_benchmarks.yaml — replace claude-opus-4-6 judge model with:
- name: claude-haiku-4-6
  interface: anthropic
  parameters:
    model: claude-3-5-haiku-20241022
    temperature: 0.0
    max_tokens: 256
  roles: [judge]

# Add Batch API to experiment block:
experiment:
  batch:
    openai:
      response_collection: true
      evaluation: true
    anthropic:
      response_collection: true
      evaluation: true
```

Estimated cost with haiku judge + batch API: **~$95**

---

## Scaling Table

| Sample size | No batch | With batch + haiku judge |
|-------------|----------|--------------------------|
| 100 per task (400 total) | $107 | $15 |
| 200 per task (800 total) | $213 | $31 |
| **620 per task (2,480 total)** | **$661** | **$95** |
| 1,000 per task (4,000 total) | $1,066 | $153 |

---

## BERTScore Computation (post-experiment)

Running `benchmark/compute_scores.py` after Phase 5 to populate `benchmark_native_score`
requires `bert-score` (PyPI) and torch. Cost: **$0** (local computation).
GPU recommended; ~30 min on RTX 3090 for 2,480 items with distilbert-base-uncased.

---

## Baseline Comparison Script Cost (`benchmark/run_baselines.py`)

| Method | Calls | Cost (200 pairs/task × 4 tasks = 800 calls) |
|--------|-------|----------------------------------------------|
| BERTScore | 800 | $0 (local) |
| G-Eval (GPT-4o) | 800 | ~$1.95 |
| G-Eval (Claude-3.5-Sonnet) | 800 | ~$2.80 |

Recommended: run with `--max-pairs 200` per task for Table 3 baselines.
