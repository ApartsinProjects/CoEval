# CoEval — Academic Paper Plan

**Last Updated:** 2026-03-01
**Target Venue:** ACL 2026 long paper (EMNLP 2026 as fallback)
**Paper Title:** CoEval: A Self-Evaluating LLM Ensemble Framework for Scalable, Attribute-Controlled Benchmark Generation

---

## 1. Target Venue & Submission Requirements

| Attribute | Value |
|-----------|-------|
| Primary venue | ACL 2026 main conference (long paper track) |
| Fallback venue | EMNLP 2026 |
| Page limit | 8 pages content + unlimited references (ACL format) |
| Bonus pages | +1 page camera-ready; +2 pages for review response |
| LaTeX style | `acl2026.sty` (two-column, Times New Roman 11pt) |
| Submission portal | OpenReview (ACL 2026) |
| Anonymous review | Yes — remove author names, institutional affiliations, direct GitHub links |
| Ethics statement | **Required** — must address data, bias, and misuse risks |
| Reproducibility checklist | Required at submission |
| Recommended sections | Introduction, Related Work, Method, Experiments, Analysis, Limitations, Conclusion, Ethics |

---

## 2. Paper Architecture

### 2.1 Section Map & Word Limits

| § | Title | Target words | Current status |
|---|-------|-------------|---------------|
| Abstract | — | ≤250 | ✅ Written (~245 words) — needs final proofread |
| 1 | Introduction | 700–900 | ✅ Written (~820 words) — solid, needs contributions list review |
| 2 | Related Work | 800–1,000 | ✅ Written (~950 words) — good, 57 refs; verify all baselines cited |
| 3 | Framework & Methodology | 1,400–1,800 | ✅ Written (~1,650 words) — add Table of Notation |
| 4 | Experiments & Results | 1,200–1,500 | ✅ Written (~1,400 words) — placeholder numbers need review |
| 5 | Analysis & Discussion | 600–800 | ✅ Written (bias, efficiency, ablation prose) |
| 6 | Limitations | 350–450 | ✅ Written |
| 7 | Conclusion | 250–350 | ✅ Written |
| Ethics | — | 200–300 | ✅ Written |
| App A | Notation Table | ~200 | ✅ Written |
| App B | Example Rubrics | ~300 | ✅ Written |
| App C | Full YAML Config | ~200 | ✅ Written |
| App D | Extended Results | ~600 | ✅ Written |

**Total main body target: ~6,800 words (fits 8 pages in ACL 2-column format)**

---

## 3. Core Claims (Testable Propositions)

The paper rests on five falsifiable claims that must each be supported by at least one table or figure:

| Claim | Evidence | Section |
|-------|----------|---------|
| **R1 Correlation** | ρ = 0.871 (CoEval-3J) vs ρ = 0.760 (best single-model) vs ρ = 0.472 (BERTScore) | Table 3, Fig 1 |
| **R2 Ranking agreement** | Kendall τ = 1.0 between CoEval rankings and benchmark-native rankings | Table 5 |
| **R3 Coverage** | ACR: 0.961 (CoEval) vs 0.431 (random); RAR: 81.7% vs 12.4% | Table 4, Fig 2 |
| **R4 Bias mitigation** | PFR: 2.9% (CoEval ensemble) vs 23.4%–27.1% (individual judges) | Table 9, Fig 6 |
| **R5 Efficiency** | 82.7% cost reduction; 11.6× throughput vs sequential benchmark eval | Table 11, Fig 7 |

---

## 4. Experimental Design

### 4.1 Tasks & Datasets

| Task ID | Task | Benchmark | N items | GT metric |
|---------|------|-----------|---------|-----------|
| text_summarization | Text Summarization | XSum [55] | 620 | BERTScore-F1 |
| code_explanation | Code Explanation | HumanEval + CodeSearchNet [33,56] | 620 | pass@1 |
| email_composition | Email Composition | Reference corpus | 620 | BERTScore-F1 |
| data_interpretation | Data Interpretation | ChartQA [57] | 620 | Exact-match acc |

### 4.2 Models

| Role | Models |
|------|--------|
| Teacher | Claude Opus 4.6, GPT-4o (generative mode); benchmark datasets (benchmark-sourced mode) |
| Student | GPT-4o, Claude Sonnet 4.6, Gemini 1.5 Pro, Llama-3-70B, Llama-3-8B, Qwen2-7B, Mistral-7B, Phi-3-mini |
| Judge | Claude Opus 4.6, GPT-4o, Gemini 1.5 Pro (3-judge ensemble) |

### 4.3 Baselines

| Baseline | Description | Expected ρ |
|----------|-------------|-----------|
| BERTScore-F1 | Token-level embedding similarity | ~0.47 |
| G-Eval (GPT-4o, single) | LLM-as-judge, no calibration | ~0.74 |
| G-Eval (Claude, single) | LLM-as-judge, best single | ~0.76 |
| PandaLM | Fine-tuned judge model | ~0.70 |
| FLAMe | Multi-factor ensemble, no attribute control | ~0.78 |
| **CoEval (3J)** | Our method (full ensemble + calibration) | **0.871** |

---

## 5. Figures Plan

| Figure | Type | Caption (summary) | Data source | Status |
|--------|------|------------------|-------------|--------|
| Fig 1 | Architecture diagram | Five-phase pipeline with role icons (T/S/J) | conceptual | ✅ Generated |
| Fig 2 | Grouped bar chart | Spearman ρ per task: BERTScore vs G-Eval vs CoEval | Table 3 | ✅ Generated |
| Fig 3 | Side-by-side heatmap | Attribute coverage: random vs CoEval stratified | Table 4 / §4.3 | ✅ Generated |
| Fig 4 | Scatter (ACR vs ρ) | Coverage → reliability: Pearson r = 0.81 | §4.3.2 | ✅ Generated |
| Fig 5 | Radar chart | Top-4 students across rubric dimensions (code task) | Table 5 / §4.4.2 | ✅ Generated |
| Fig 6 | Line chart | ρ vs ensemble size (1J, 2J, 3J) with CI bands | Table 6 | ✅ Generated |
| Fig 7 | Scatter + LOESS | Verbosity bias: score vs length for judges vs CoEval | §4.6.2 | ✅ Generated |
| Fig 8 | Time-series ICC | Rubric drift: individual judges vs calibrated ensemble | §4.8.3 | ✅ Generated |

All figures generated as PNG with 300 DPI into `paper/figures/`.

---

## 6. Literature Review Plan

### 6.1 Core Themes & Organization

The literature review (§2) follows five thematic sub-sections, each 160–200 words:

| Sub-section | Theme | Key citations |
|-------------|-------|--------------|
| 2.1 | LLM Evaluation Paradigms (evolution) | BIG-Bench, HELM, MMLU, HellaSwag |
| 2.2 | LLM-as-Judge Approaches (biases) | G-Eval, MT-Bench, PandaLM, ChatEval, OffsetBias |
| 2.3 | Benchmark Construction (synthetic data) | Self-Instruct, WizardLM, BELLE, EvolInstruct |
| 2.4 | Teacher-Student Frameworks | CheckList, EvalTree, Prometheus, knowledge distillation |
| 2.5 | Inter-Annotator Agreement | Cohen's κ, Krippendorff's α, Spearman ρ, ICC |

**Coverage gap CoEval fills:** No prior work simultaneously addresses *attribute-controlled generation*, *multi-judge calibrated ensemble*, and *benchmark-grounded validation* in a single unified pipeline.

### 6.2 Literature Review Organization Principles

1. **Chronological within themes** — earlier work first; show progression
2. **Compare-and-contrast framing** — each paragraph sets up a limitation that CoEval addresses
3. **No orphaned citations** — every citation in §2 must appear in at least one comparison table or be directly referenced in a claim in §4
4. **Completeness check** — all 5 baselines used in Table 3 must be cited and characterized in §2

---

## 7. Methodology Plan

### 7.1 What §3 Must Cover (in order)

| Sub-section | Content | Length |
|-------------|---------|--------|
| 3.1 Overview | High-level pipeline + role diagram | 200w |
| 3.2 Notation | Formal definitions: T, S, J, D, R, E | 150w (+ Table of Notation) |
| 3.3 Phase 1: Attribute Mapping | Generative + static modes; merging/deduplication | 200w |
| 3.4 Phase 2: Rubric Construction | Generative + benchmark-grounded; factor definitions | 200w |
| 3.5 Phase 3: Datapoint Generation | Stratified sampling; benchmark-sourced mode | 250w |
| 3.6 Phase 4: Response Collection | Async batching; fault tolerance; extend mode | 150w |
| 3.7 Phase 5: Ensemble Scoring | Scoring protocol; calibration; positional bias mitigation | 250w |
| 3.8 Robust Filtering | J*, T*, D* selection; consistency threshold θ | 200w |
| 3.9 Fault Tolerance | Phase-level + item-level resume; meta.json | 150w |

### 7.2 Depth & Length Guidance

- **Don't over-explain** the YAML config format — one example box in Appendix B is sufficient
- **Do formalize** the scoring aggregation with notation (Equation 1–4 expected)
- **Calibration** (§3.7): explain α, β parameters; cite the calibration set size (200 items)
- **Sampling** (§3.5): include the stratified sampling algorithm as a numbered Algorithm block

---

## 8. Review Rounds (Tracked)

### Round 1 — Structural Consistency (complete)
- [x] All claims in §1.3 traceable to Table or Figure in §4
- [x] Notation in §3 matches symbols used in §4
- [x] All five baselines in Table 3 cited in §2

### Round 2 — Numerical Consistency (complete)
- [x] Monotonically increasing ρ with ensemble size: 0.760 → 0.821 → 0.871 ✓
- [x] ACR monotonically increasing: 0.431 < 0.489 < 0.883 < 0.961 < 0.978 ✓
- [x] Positional flip rate: all < 5% after mitigation ✓
- [x] Cost reduction: ($45.80 − $7.94) / $45.80 = 82.7% ✓
- [x] Throughput ratio: 256 / 22 = 11.6× ✓

### Round 3 — Academic Writing Quality (complete)
- [x] Abstract ≤ 250 words ✓ (245 words)
- [x] No contractions ("don't", "it's") in main body
- [x] Citations as `\citet{}`/`\citep{}` consistently
- [x] Each paragraph: topic sentence → evidence → implication
- [x] Limitations section: 4+ distinct limitations identified
- [x] Ethics: covers data rights, model biases, misuse risks (≥200 words)

---

## 9. Pending Before Submission

- [ ] **Replace fictitious numbers with real experimental results** (all Table 3–11 values are illustrative)
- [ ] **Run actual experiments**: configure CoEval with benchmark-sourced mode on XSum/CodeSearchNet/AESLC/ChartQA; collect real ρ values
- [ ] **Implement benchmark metrics**: BERTScore-F1, pass@1, exact-match in analysis pipeline
- [ ] **Obtain real baseline comparison data**: run G-Eval, BERTScore, FLAMe on same items
- [ ] **Generate figures from real data** (currently generated from illustrative data)
- [ ] **Add actual GitHub URL** (remove "URL anonymized for review" placeholder before camera-ready)
- [ ] **Proofread bibliography** for DOI consistency and venue formatting
- [ ] **Verify anonymization** before submission (no institutional affiliations in main body)

---

*This plan was generated on 2026-03-01 and reflects the current state of the paper draft.*
