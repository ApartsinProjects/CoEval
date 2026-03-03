# CoEval Paper v2 — Assembly Guide

## Status Overview

| Section | File | Status | Word Count | Cycles Done |
|---------|------|--------|-----------|------------|
| Abstract | `01_abstract.md` | ✅ Complete | 245 words | 10 |
| Introduction | `02_introduction.md` | ✅ Complete | 702 words | 10 |
| Related Work | `03_related_work.md` | ✅ Complete | 960 words | 10 |
| Methodology | `04_methodology.md` | ✅ Complete | 1,649 words | 10 |
| Experiments | `05_experiments.md` | ✅ Complete | ~1,260 words | 10 |
| Analysis & Discussion | `06_analysis_conclusion.md` | ✅ Complete | 775 words | 10 |
| Limitations | `06_analysis_conclusion.md` | ✅ Complete | 430 words | 10 |
| Conclusion | `06_analysis_conclusion.md` | ✅ Complete | 290 words | 10 |
| Ethics Statement | `06_analysis_conclusion.md` | ✅ Complete | 265 words | 10 |
| Appendix A–D | `10_appendix.md` | ✅ Complete | ~1,300 words | — |
| References | `references.md` | ✅ Complete | 23 BibTeX entries | — |
| Figures catalogue | `figures/FIGURES_CATALOGUE.md` | ✅ Complete | — | — |
| Experiment backlog | `experiment_backlog.md` | ✅ Complete | — | — |
| Paper plan | `00_plan.md` | ✅ Complete | — | — |
| Figure gen script | `scripts/generate_paper_figures.py` | ✅ Complete | — | — |

---

## Paper Assembly Order

When merging into a single camera-ready LaTeX file:

```
1. Title + Author Block
2. Abstract (from 01_abstract.md — FINAL ABSTRACT section)
3. §1 Introduction (from 02_introduction.md — FINAL INTRODUCTION section)
4. §2 Related Work (from 03_related_work.md — FINAL RELATED WORK section)
5. §3 Framework & Methodology (from 04_methodology.md — FINAL METHODOLOGY section)
6. §4 Experiments & Results (from 05_experiments.md — FINAL EXPERIMENTS section)
7. §5 Analysis & Discussion (from 06_analysis_conclusion.md — FINAL §5 section)
8. §6 Limitations* (from 06_analysis_conclusion.md — FINAL §6 section)
9. §7 Conclusion (from 06_analysis_conclusion.md — FINAL §7 section)
10. Ethics Statement* (from 06_analysis_conclusion.md — FINAL Ethics section)
11. References (from references.md — BibTeX block)
12. Appendix A: Notation (from 10_appendix.md — App A)
13. Appendix B: Example Rubrics (from 10_appendix.md — App B)
14. Appendix C: YAML Config (from 10_appendix.md — App C)
15. Appendix D: Extended Results (from 10_appendix.md — App D)
```

*Sections 8 and 10 do not count toward the 8-page limit in ACL format.

---

## Authors for Title Block

```latex
\author{
  Alexander Apartsin \\
  Holon Institute of Technology \\
  Holon, Israel \\
  \texttt{apartsin@hit.ac.il} \And
  Yehudit Aperstein \\
  Afeka Tel Aviv Academic College of Engineering \\
  Tel Aviv, Israel \\
  \texttt{aperstein@afeka.ac.il}
}
```

*Note: For anonymous review submission, replace author block with \anon{} placeholder per ARR guidelines.*

---

## Key Figures to Include in Main Paper (8-page limit)

Priority order for the 8-page constraint:

| Priority | Figure | Section | Justification |
|----------|--------|---------|---------------|
| P1 | Fig 1 — Architecture diagram | §3.1 | Essential for understanding pipeline |
| P1 | Table 3 — Judge agreement matrix | §4.1 | Core contribution validation |
| P1 | Table 4 — Teacher discrimination | §4.2 | Novel V1/S2/R3 contribution |
| P1 | Table 7 — Cost breakdown | §4.4 | Efficiency claim |
| P1 | Table 8 — Benchmark comparison (simulated) | §4.5 | Primary claim (mark simulated) |
| P2 | Fig 17 — κ heatmap | §4.1 | Visual of judge agreement |
| P2 | Fig 18 — Teacher discrimination bar | §4.2 | Visual of teacher metrics |
| P2 | Fig 14 — Ensemble ablation (simulated) | §4.1 | Ensemble size effect |
| P3 | Fig 2 — Teacher-student-judge (Gemini) | §1 | Conceptual overview |
| P3 | Table 5 — Student performance | §4.3 | Student ranking evidence |

---

## Pre-Submission Checklist

### Content
- [ ] All (simulated) labels present on Table 8, Fig 14, Fig 15, Fig 16
- [ ] experiment_backlog.md updated with actual run dates when EXP-001 completes
- [ ] All ρ comparisons replaced with real values from EXP-001
- [ ] Author affiliations verified correct
- [ ] GitHub URL added (currently anonymized)

### Format (ACL 2-column)
- [ ] 8 pages main body (not counting Limitations, Ethics, References, Appendix)
- [ ] Limitations section present and ≥ 350 words
- [ ] Ethics statement present and ≥ 200 words
- [ ] All figures have captions with (simulated) note where applicable
- [ ] Responsible NLP checklist completed on OpenReview
- [ ] Two-way anonymization: no affiliations, no direct GitHub links in main body

### Technical
- [ ] All BibTeX entries verified with correct venue, year, authors
- [ ] Equation numbering consistent (Eq 1–4 in §3)
- [ ] All tables referenced in text before they appear
- [ ] Algorithm 1 (stratified sampling) properly formatted
- [ ] Cohen's κ thresholds cited as (Landis & Koch, 1977)
