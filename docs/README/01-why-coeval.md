# Why CoEval

[← README](../../README.md) · [Features →](02-features.md)

---

Evaluating LLMs rigorously is expensive, fragile, and time-consuming. The standard workflow — writing one-off scripts, managing API keys by hand, retrying crashed jobs, paying for duplicate work, and stitching together ad-hoc comparison tables — does not scale beyond a single researcher or a single model.

CoEval was built to change that.

## The Problem Space

Every serious LLM evaluation project eventually hits the same walls:

- **Prompt brittleness** — a prompt tuned for GPT-4o produces garbage from Llama. Evaluation results reflect prompt engineering choices, not model quality.
- **Rubric subjectivity** — hand-written scoring criteria are inconsistent, hard to version, and impossible to audit.
- **Single-judge bias** — one judge model introduces systematic scoring biases that compound across thousands of evaluations.
- **Cost unpredictability** — a poorly scoped run can burn hundreds of dollars before you know it went wrong.
- **Fragile pipelines** — a single API timeout at hour three means starting over, paying again, getting different outputs.
- **No reproducibility** — notebooks and ad-hoc scripts accumulate state that cannot be re-run cleanly six months later.
- **Vendor dependency** — code written for the OpenAI SDK must be rewritten to test Anthropic, Google, or an open-source model.

## The CoEval Solution

| Problem | CoEval Solution |
|---------|----------------|
| Evaluation logic scattered across notebooks | Single declarative YAML drives every phase |
| Hardcoded prompts biased toward a single model | Automated attribute and rubric generation, model-specific prompt overrides |
| High API bills with no visibility | Pre-run cost estimation with Batch API discounts (up to 50% off) |
| Crashed runs require starting over | Granular resume at task × model × record level |
| Judge bias from single-model evaluation | Configurable multi-judge ensembles with consistency metrics |
| No insight into what went wrong | 8 interactive HTML reports, JSONL audit trail, repair tooling |
| Vendor lock-in | 15+ interfaces — cloud, local, virtual benchmark |
| Manual comparison across dozens of models | Kendall τ ranking, Spearman ρ correlation, differentiation scores |

## Who CoEval Is For

**LLM developers** stress-testing a fine-tune against frontier baselines before shipping.

**ML engineers** validating a RAG pipeline across diverse task dimensions and input distributions.

**Researchers** producing reproducible, publication-grade benchmarks that can be re-run by reviewers.

**Platform teams** running recurring evaluation suites across model versions with full cost and quality auditability.

**Practitioners** who need to compare open-source and proprietary models on their specific task without rebuilding evaluation infrastructure each time.

---

[← README](../../README.md) · [Features →](02-features.md)
