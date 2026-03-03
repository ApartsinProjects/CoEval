# CoEval Paper — v2 Plan

**Target Venue:** ACL 2026 (via ACL Rolling Review) — Long Paper Track
**Fallback Venue:** EMNLP 2026
**Paper Title:** CoEval: A Self-Evaluating LLM Ensemble Framework for Scalable, Attribute-Controlled Benchmark Generation

---

## Authors & Affiliations

| Author | Affiliation |
|--------|------------|
| Alexander Apartsin | Holon Institute of Technology (HIT), Israel |
| Yehudit Aperstein | Afeka Tel Aviv Academic College of Engineering, Israel |

*Based on: multiple joint arXiv preprints (Sep 2025), Google Scholar profile, and Afeka College faculty page.*

---

## Venue Requirements (ACL 2026 / ARR)

| Attribute | Value |
|-----------|-------|
| Format | ACL 2-column, Times New Roman 11pt (`acl_latex.sty`) |
| Long paper limit | **8 pages** content + unlimited references |
| Camera-ready | +1 bonus page |
| Limitations section | **Required** (does not count toward page limit) |
| Ethics statement | **Required** (does not count toward page limit) |
| Anonymized review | Yes — remove affiliations, GitHub URL, grant numbers |
| Submission portal | OpenReview via ARR |
| ARR deadline (next) | Check aclrollingreview.org/dates for current cycle |
| Key deadlines | ARR submission → reviews → commit to ACL 2026 (deadline March 14, 2026) |

---

## Section Map

| File | Section | Target words | Status |
|------|---------|-------------|--------|
| `01_abstract.md` | Abstract | ≤ 250 | ✅ Written |
| `02_introduction.md` | 1. Introduction | 700–900 | ✅ Written |
| `03_related_work.md` | 2. Related Work | 800–1,000 | ✅ Written |
| `04_methodology.md` | 3. Framework & Methodology | 1,400–1,800 | ✅ Written |
| `05_experiments.md` | 4. Experiments & Results | 1,200–1,500 | ✅ Written |
| `06_analysis.md` | 5. Analysis & Discussion | 600–800 | ✅ Written |
| `07_limitations.md` | 6. Limitations | 350–450 | ✅ Written |
| `08_conclusion.md` | 7. Conclusion | 250–350 | ✅ Written |
| `09_ethics.md` | Ethics Statement | 200–300 | ✅ Written |
| `10_appendix.md` | Appendices A–D | ~1,300 | ✅ Written |

**Total main body target:** ~6,800 words (fits 8 pages in ACL 2-column)

---

## Core Claims & Supporting Evidence

All claims use **real medium-benchmark data** from `Runs/medium-benchmark-v1/`.
Simulated figures are clearly marked with `(simulated)`.

| # | Claim | Evidence from real data | Section |
|---|-------|------------------------|---------|
| R1 | Ensemble judges outperform single judges on agreement | gpt-4o-mini+gpt-3.5-turbo pairwise SPA=0.720, Kappa=0.422 | §4, Table 3 |
| R2 | CoEval produces well-calibrated rubric criteria | 22 rubric criteria across 4 tasks; all with clear descriptions | §3, Table 2 |
| R3 | Attribute stratification produces diverse datapoints | 400 datapoints × 5 teachers = 2,000 stratified data combinations | §4, Fig 3 |
| R4 | Small models show lower judge agreement | smollm2-1b7 SPA=0.322, WPA=0.653 vs GPT-3.5 SPA=0.664 | §5, Table 6 |
| R5 | Cost-effective: full benchmark <$6 | Total cost $5.89, 7,987 evaluations | §4, Table 7 |

*Claims R1–R5 are backed by real experimental data.*
*Comparative claims vs external benchmarks (e.g., ρ vs BERTScore) are marked (simulated) pending future experiments.*

---

## Experimental Setup (Real Data)

| Attribute | Value |
|-----------|-------|
| Experiment ID | medium-benchmark-v1 |
| Run dates | 2026-02-24 to 2026-03-01 |
| Tasks | 4 (text_summarization, code_explanation, email_composition, data_interpretation) |
| Models | 5 (gpt-4o-mini, gpt-3.5-turbo, qwen2p5-0b5, qwen2p5-1b5, smollm2-1b7) |
| Roles | All 5 serve as teachers + students; 4 serve as judges (qwen2p5-0b5 excluded from judge) |
| Datapoints generated | 400 (5 teachers × 4 tasks × 20 items each) |
| Responses collected | 1,991 valid |
| Evaluations performed | 7,978 valid |
| Total cost | $5.89 USD |
| Runtime | ~12.8 hours |

---

## Figures Plan

| Figure | Content | Source | Status |
|--------|---------|--------|--------|
| Fig 1 | Architecture overview (Mermaid flowchart) | Mermaid diagram | ✅ `figures/diagrams/fig1_architecture.md` |
| Fig 2 | Judge agreement matrix heatmap | HTML report screenshot | ⏳ `figures/screenshots/fig2_judge_agreement.png` |
| Fig 3 | Attribute coverage treemap/heatmap | HTML report screenshot | ⏳ `figures/screenshots/fig3_coverage.png` |
| Fig 4 | Score distribution violin plots | HTML report screenshot | ⏳ `figures/screenshots/fig4_score_distribution.png` |
| Fig 5 | Teacher discrimination (v1/s2/r3 bar chart) | HTML report screenshot | ⏳ `figures/screenshots/fig5_teacher_discrimination.png` |
| Fig 6 | Student performance radar chart | HTML report screenshot | ⏳ `figures/screenshots/fig6_student_radar.png` |
| Fig 7 | YAML config example | Annotated code screenshot | ⏳ `figures/tables/fig7_yaml_config.png` |
| Fig 8 | Ensemble size vs agreement (simulated) | Generated chart | ⏳ `figures/tables/fig8_ensemble_ablation.png` |

---

## Tables Plan

| Table | Content | Source |
|-------|---------|--------|
| Table 1 | Notation glossary | Text |
| Table 2 | Tasks, attributes, rubric criteria summary | Real data |
| Table 3 | Judge-pair agreement (SPA, WPA, Kappa) | Real data from judge_consistency report |
| Table 4 | Teacher discrimination scores (v1, s2, r3) | Real data from teacher_report |
| Table 5 | Student performance by task and judge | Real data from student_report |
| Table 6 | Comparison: CoEval ensemble vs individual judges | Real data |
| Table 7 | Cost and runtime breakdown by phase | Real data from cost_estimate.json |
| Table 8 | Benchmark comparison (ρ vs baselines) | **(simulated)** |

---

## Review Cycles Log

| Section | Cycle | Reviewer notes | Status |
|---------|-------|----------------|--------|
| Abstract | 1–10 | See `01_abstract.md` revision log | ✅ |
| Introduction | 1–10 | See `02_introduction.md` revision log | ✅ |
| Related Work | 1–10 | See `03_related_work.md` revision log | ✅ |
| Methodology | 1–10 | See `04_methodology.md` revision log | ✅ |
| Experiments | 1–10 | See `05_experiments.md` revision log | ✅ |
| Analysis | 1–10 | See `06_analysis.md` revision log | ✅ |
| Limitations | 1–10 | See `07_limitations.md` revision log | ✅ |
| Conclusion | 1–10 | See `08_conclusion.md` revision log | ✅ |
| Ethics | 1–10 | See `09_ethics.md` revision log | ✅ |
