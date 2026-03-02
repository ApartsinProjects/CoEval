# CoEval Paper — TODO & Improvement Ideas

This document tracks open items for writing, experimentation, results, figures, and the framework concept itself.

---

## Writing & Presentation

- [ ] **Replace figure placeholders** with actual rendered figures (matplotlib/seaborn). Each placeholder in `04_results.md` has a ASCII spec; convert to real plots.
- [ ] **Add figure captions** to all figures in the paper (currently only described inline).
- [ ] **Add a formal Notation table** (Section 3.1) listing all symbols used throughout the paper.
- [ ] **Expand Section 5 (Limitations)** — not yet written. Must include: cost dependency on closed-source APIs, limited language coverage (currently English-only), failure modes at very low datapoint budgets.
- [ ] **Write Section 6 (Conclusion)** — not yet written.
- [ ] **Proofread bibliography** — verify all IEEE citation numbers are consistent across all sections (01_introduction.md uses [1]–[7], 02_literature_review.md uses [1]–[54]; ensure shared references use the same number).
- [ ] **Add an Appendix** with: full YAML configuration reference, full rubric examples for each domain, example (prompt, reference, student response) triples from each domain.
- [ ] **Tighten abstract** — currently 292 words; target 250 for NeurIPS/ACL limits.
- [ ] **Check venue formatting requirements** — ACL 2026 and NeurIPS 2026 both use specific LaTeX templates; convert MD to LaTeX before submission.
- [ ] **Add ethics statement** — required by ACL and NeurIPS. Must address: use of proprietary models, potential misuse of benchmark-grounded automated evaluation to obscure failure modes not captured by existing benchmarks, and environmental cost of large-scale LLM evaluation.
- [ ] **Update domain acronym list** — replace CS/MT/LS/CE/FA with TS/CE/EC/DI (text summarization, code explanation, email composition, data interpretation) consistently across all sections.
- [ ] **Add Section 3 benchmark loader docs** — write a brief description of the HuggingFace `datasets`-based loader mechanism and the per-benchmark `attribute_map.yaml` schema.
- [ ] **Update bibliography** — add citations [55] XSum, [56] CodeSearchNet, [57] ChartQA to `02_literature_review.md` bibliography section and ensure numbering is consistent with `03_methodology.md`.

---

## Real Data & Experiments to Run

- [ ] **Run actual experiments** — all numbers in `04_results.md` are fictional placeholders. Replace with real results from CoEval benchmark-sourced runs.
- [ ] **Benchmark dataset integration** — download and preprocess held-out splits of XSum, HumanEval/CodeSearchNet, ChartQA, and a reference email corpus; write benchmark loaders emitting CoEval-compatible JSONL (see Section 3.4.4 spec).
- [ ] **Benchmark metric computation** — implement ROUGE-L/BERTScore-F1 for summarization and email tasks, pass@1 / functional correctness for code, exact-match for ChartQA; integrate metric outputs as the ground-truth column for ρ computation.
- [ ] **Calibration holdout set** — draw 200-item calibration set from benchmark validation splits with known benchmark-metric scores; run two-parameter (α, β) calibration fitting per judge.
- [ ] **Baseline runs** — implement and run BERTScore, G-Eval (GPT-4o), G-Eval (Claude), PandaLM, FLAMe on the same evaluation set; ensure all baselines are compared against benchmark-native metrics (Table 3).
- [ ] **Positional bias measurement** — run all judges on both orderings of the same (A, B) pair and compute flip rates (Table 9).
- [ ] **Verbosity bias analysis** — compute Pearson r between response length and score per judge and ensemble (Figure 6); compare against BERTScore/pass@k to confirm length-agnostic calibration.
- [ ] **Rubric drift analysis** — compute rolling ICC(3,1) over 600-item batches, comparing drift against benchmark metric ordering consistency (Figure 8).
- [ ] **Sampling strategy ablation** — run random / frequency-weighted / CoEval stratified sampling at fixed budget N=620, compute ACR and ρ (Table 7 / updated).
- [ ] **Judge count ablation** — run all 7 subsets of a 3-judge pool; compute ρ vs. benchmark metrics (Table 6).
- [ ] **Calibration ablation** — compare none / shift-only / full calibration (Table 8).
- [ ] **Cost measurement** — instrument the pipeline to log per-run API costs; compute cost for sequential benchmark eval baseline (Table 11).

---

## Figures to Create (Real)

- [ ] **Fig 1**: Grouped bar chart — ρ by method and domain. Data from Table 3.
- [ ] **Fig 2**: Side-by-side heatmaps — attribute coverage, uncontrolled vs. CoEval. Use `complaint_handling` task with 6 target × 4 nuanced attributes.
- [ ] **Fig 3**: Scatter plot — ACR vs. ρ across 120 benchmark generation experiments. Run the 120 experiments with varied settings.
- [ ] **Fig 4**: Radar chart — top-4 student models across 5 rubric dimensions for medical triage. Data from per-factor scoring.
- [ ] **Fig 5**: Line chart — ensemble size vs. ρ with 95% CI. Data from Table 6 + 4-judge extension.
- [ ] **Fig 6**: Scatter plot — response length vs. quality score, per judge and ensemble. Data from verbosity bias analysis.
- [ ] **Fig 7**: Log-log line chart — pipeline wall time vs. datapoints for 3 concurrency levels. Instrument and benchmark.
- [ ] **Fig 8**: Rolling ICC time series — rubric drift over 600-item batch. Data from drift analysis.
- [ ] **Fig 9 (new)**: Cost-reliability Pareto frontier — scatter of (cost, ρ) for all methods, showing CoEval on frontier.
- [ ] **Fig 10 (new)**: Confusion matrix / ranking heatmap — pairwise student model ranking agreement between CoEval and humans.

---

## Concept & Framework Improvements

- [ ] **Multi-turn evaluation** — current pipeline evaluates single-turn responses; extend to multi-turn dialogue assessment where context matters.
- [ ] **Dynamic rubric refinement** — allow rubric to evolve mid-campaign based on early scoring patterns (e.g., add a factor if judges frequently note a quality dimension not in the rubric).
- [ ] **Adversarial datapoint generation** — add a Phase 3 variant where the teacher explicitly generates adversarial prompts designed to expose model weaknesses.
- [ ] **Cross-lingual support** — extend attribute mapping and generation to multilingual domains; requires multilingual judge calibration.
- [ ] **Active learning integration** — prioritize datapoint generation for (student, attribute) combinations where model uncertainty is highest, reducing budget needed for reliable ranking.
- [ ] **Online/streaming mode** — run Phase 5 scoring incrementally as Phase 4 responses come in, rather than waiting for full Phase 4 completion.
- [ ] **Judge distillation** — after running the full ensemble, distill a single cheap judge model using the ensemble scores as supervision, enabling fast evaluation at lower cost for future runs.
- [ ] **Calibration without holdout** — investigate self-calibration using consistency constraints (a judge should rank A > B consistently regardless of ordering) rather than requiring a labeled holdout set.
- [ ] **Semantic deduplication in Phase 3** — current deduplication uses MinHash; explore semantic embedding-based deduplication to catch paraphrase duplicates.
- [ ] **Structured output validation** — add JSON Schema validation for judge outputs to catch malformed responses earlier.
- [ ] **Confidence-weighted voting** — instead of equal ensemble weights, use per-judge confidence scores (e.g., judge self-reported uncertainty) as weighting in the weighted median.

---

## Infrastructure & Codebase

- [ ] **LangSmith / W&B integration** — add optional observability hooks to log all API calls, latencies, and costs to experiment tracking platforms.
- [ ] **Async Phase 3** — Phase 3 generation is currently synchronous per batch; convert to async for better throughput with multiple teachers.
- [ ] **CLI UX improvements** — add `coeval status <experiment-id>` command that prints a table showing phase completion and per-task progress.
- [ ] **Config validation error messages** — current error messages reference internal variable names; make them more user-friendly.
- [ ] **Docker image** — publish a pre-built Docker image with all dependencies for easy deployment.
- [ ] **Documentation site** — convert YAML config reference and tutorial notebooks to a Sphinx or MkDocs site.
- [ ] **Benchmark registry** — add ability to publish and load benchmarks to/from a central registry so researchers can share evaluation sets.
