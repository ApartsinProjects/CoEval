# CoEval Documentation Plan

**Principle:** Every document answers exactly one question or serves one reader group.
Target size: < 300 lines for focused docs. Reference instead of duplicating.

---

## Document Purpose Matrix

| Document | Answers | Reader | Target size | Action |
|----------|---------|--------|-------------|--------|
| `README.md` | What is CoEval, should I try it? | Everyone | ~150 lines | ✅ Done |
| `docs/README/01-why-coeval.md` | Why is self-evaluation better? | Decision-makers | 50 lines | Minor: add HTML teaser |
| `docs/README/02-features.md` | What can CoEval do? | Evaluating users | 60 lines | Fix: interface count 9→15 |
| `docs/README/03-architecture.md` | How does the 5-phase pipeline work? | Technical users | 100 lines | Keep |
| `docs/README/04-installation.md` | How do I install? | New users | 60 lines | Fix: add 5 new provider SDKs |
| `docs/README/05-quick-start.md` | How do I run my first experiment? | New users | 80 lines | Add: HTML planning example link |
| `docs/README/06-configuration.md` | How do I configure my YAML? | All users | 300 lines | ✅ Done (examples added) |
| `docs/README/07-interfaces.md` | Which provider should I use? | All users | 150 lines | Fix: add azure_ai, 5 new providers |
| `docs/README/08-cli-reference.md` | What does each command do? (summary) | All users | ~100 lines | **REFACTOR**: remove details → link to full ref |
| `docs/README/09-cost-control.md` | How do I control costs? | Cost-conscious | 80 lines | Fix: azure_openai has batch support |
| `docs/README/10-resume-recovery.md` | How do I resume or recover? | All users | 100 lines | Keep |
| `docs/README/11-analytics-reports.md` | What HTML reports can I generate? | Analysts | 100 lines | ✅ Done (HTML links added) |
| `docs/README/12-repository-layout.md` | Where is everything in the repo? | Developers | 100 lines | Fix: add new files |
| `docs/README/13-testing.md` | How do I run tests? | Contributors | 50 lines | Fix: count 557, not 483 |
| `docs/README/14-documentation.md` | Where do I find all the docs? | All users | 80 lines | **UPDATE**: add HTML gallery, new files |
| `docs/tutorial.md` | How does the full workflow feel end-to-end? | Learners | ~700 lines | Minor: trim duplicate ref tables |
| `docs/cli_reference.md` | Complete CLI flag reference | Power users | ~987 lines | Keep (canonical) |
| `docs/running_experiments.md` | How do I run/monitor/recover an experiment? | Operators | ~300 lines | **REFACTOR**: 1475→300 |
| `docs/developer_guide.md` | How is the code structured? | Contributors | ~700 lines | Keep |
| `docs/extracting_benchmarks.md` | How do I export a benchmark? | Advanced users | ~300 lines | ✅ Done |
| `manuals/01_running_experiments.md` | Quick provider setup cheatsheet | Experienced | ~200 lines | Fix: circular ref, purpose |
| `manuals/02_benchmark_experiments.md` | How do I use public benchmarks? | Benchmark users | ~400 lines | ✅ Done |
| `manuals/03_analysis_and_reporting.md` | Deep analysis/metrics reference | Analysts | ~400 lines | ✅ Done (HTML links added) |
| `manuals/04_provider_pricing.md` | What does each provider cost? | Cost-planning | ~200 lines | Fix: add 5 new providers |

---

## Accuracy Fixes Needed (Code vs Docs)

### Interface count: 9 → 15
**Code reality** (`experiments/config.py` VALID_INTERFACES):
```
openai, anthropic, gemini, huggingface, azure_openai, azure_ai, bedrock,
vertex, openrouter, groq, deepseek, mistral, deepinfra, cerebras, benchmark
```
**Docs that say "9 interfaces" or "8 interfaces"** → fix all to "15".

### Batch support: azure_openai has batch
`experiments/interfaces/azure_batch.py` implements Azure OpenAI batch.
`experiments/interfaces/gemini_batch.py` implements Gemini pseudo-batch.
Current interface table should show:

| Interface | Batch |
|-----------|-------|
| `openai` | ✅ OpenAI Batch API (50% off) |
| `anthropic` | ✅ Message Batches API (50% off) |
| `gemini` | ✅ Pseudo-batch (no discount) |
| `azure_openai` | ✅ Azure Batch API (see azure_batch.py) |
| `azure_ai` | ❌ Real-time only |
| `bedrock` | ❌ Real-time only |
| `vertex` | ❌ Real-time only |
| `openrouter` | ❌ Real-time only |
| `huggingface` | ❌ GPU direct |
| groq/deepseek/mistral/deepinfra/cerebras | ❌ Real-time only |
| `benchmark` | N/A (virtual) |

### Test count: 483 → 557
All references to "483 tests" → fix to "557 passing".

### CLI subcommands: 11 exist
`run`, `probe`, `plan`, `status`, `repair`, `describe`, `wizard`, `generate`, `ingest`, `models`, `analyze`.
All docs referencing "11 subcommands" are correct.

### New files added this session (add to docs/README/12-repository-layout.md):
- `benchmark/education.yaml`
- `benchmark/setup_education.py`
- `benchmark/loaders/arc_challenge.py`, `race.py`, `sciq.py`
- `benchmark/configs/arc_challenge_attribute_map.yaml`, `race_attribute_map.yaml`, `sciq_attribute_map.yaml`
- `docs/extracting_benchmarks.md`
- `benchmark/education_description.html`

---

## Refactoring Detail

### `docs/running_experiments.md`: 1475 → ~300 lines

**Keep:**
- § 1 Concept of Operation (brief intro, 20 lines)
- § 3 Quick Start (bash commands only)
- § 5 Phase Modes (table)
- § 8 Quota Control (YAML snippet)
- § 9 Batch Processing (YAML snippet)
- § 10 Model Probe
- § 11 Cost and Time Estimation
- § 13 Use-Case Examples (4 most useful: scratch, resume, add model, dry-run)
- HTML links (add)

**Remove/reference only:**
- § 2 Installation → link to `docs/README/04-installation.md`
- § 4 Configuration Reference → link to `docs/README/06-configuration.md`
- § 6 Storage Folder Format → link to `docs/README/12-repository-layout.md`
- § 7 Prompt Library → link to `docs/README/06-configuration.md`
- § 12 Label Accuracy → link to `docs/README/06-configuration.md`
- § 13.2-13.11 (keep only 13.1, 13.2, 13.5, 13.6 as the most common)
- § 14 Validation Rules → link to `docs/developer_guide.md`
- § 15 CLI Reference → link to `docs/cli_reference.md`
- § 16 FAQ → remove (integrate key Q&A into relevant sections)

### `docs/README/08-cli-reference.md`: 272 → ~100 lines

**Keep:** one-paragraph description + essential flags table per command.
**Remove:** all examples, all worked workflows.
**Add at top:** prominent box → "For full flag reference, examples, and workflows: see `docs/cli_reference.md`"
**Add:** link to `benchmark/education_description.html` under `coeval describe`

### `manuals/01_running_experiments.md`

**Fix:** Line 257 circular self-reference → point to `docs/running_experiments.md#10-resuming-interrupted-runs`
**Add at top:** "This is a condensed provider-setup reference for users already familiar with CoEval. For the complete guide, see `docs/running_experiments.md`."
**Add:** HTML example links at end

---

## HTML Example Links to Add

Files that discuss configs/reports but currently have no HTML links:
- `docs/running_experiments.md` → add planning + report HTML links
- `docs/README/08-cli-reference.md` → add `education_description.html` for `describe`
- `docs/README/05-quick-start.md` → add planning HTML link
- `docs/README/02-features.md` → add report HTML link
- `manuals/01_running_experiments.md` → add sample HTML links
- `manuals/04_provider_pricing.md` → no reports but add planning HTML link

---

*Plan version 1.0 — 2026-03-02*
