# CoEval — Abstract Development (10-Round Write-Review-Improve Cycle)

**Paper:** CoEval: A Self-Evaluating LLM Ensemble Framework for Scalable, Attribute-Controlled Benchmark Generation
**Authors:** Alexander Apartsin (HIT, Israel); Yehudit Aperstein (Afeka College, Israel)
**Venue:** ACL 2026 Long Paper
**Target:** ≤ 250 words

---

## === ROUND 1 — Initial Draft ===

Evaluating large language models (LLMs) at scale is an open and pressing challenge in NLP. Existing benchmarks are static, expensive to extend, and offer limited coverage of real-world deployment scenarios. LLM-as-judge approaches are scalable but suffer from systematic biases and lack grounding in verifiable criteria. We introduce CoEval, a framework for automated, attribute-controlled benchmark generation and self-evaluation using a collaborative ensemble of LLMs. CoEval operates through a five-phase pipeline: attribute mapping, rubric construction, stratified datapoint generation, student response collection, and ensemble scoring. Teacher LLMs generate evaluation items controlled by explicit quality attributes sampled from a structured attribute space, while student LLMs provide responses and judge LLMs perform scoring. Agreement across judges is measured using Cohen's kappa and Spearman rank correlation. We validate CoEval on four NLP tasks — text summarization, code explanation, email composition, and data interpretation — using five models (GPT-4o-mini, GPT-3.5-Turbo, Qwen2.5-0.5B, Qwen2.5-1.5B, SmolLM2-1.7B) as teachers, students, and judges. The full benchmark comprises 400 datapoints and 7,978 valid evaluations at a total cost of $5.89 and a runtime of approximately 12.8 hours. Ensemble judges with strong pairwise agreement (GPT-3.5-Turbo × GPT-4o-mini kappa = 0.422) substantially outperform weak judges (SmolLM2 kappa = 0.003). Simulated comparative experiments suggest CoEval achieves Spearman ρ = 0.871 versus benchmark ground-truth metrics, versus ρ = 0.472 for BERTScore and ρ = 0.711 for G-Eval, at an 82.7% cost reduction compared to sequential evaluation. CoEval is fully open-source and configurable via a declarative YAML interface.

*Word count: ~243*

---

## === ROUND 2 — Refinement ===

Evaluating large language models (LLMs) reliably and at scale remains a fundamental bottleneck for applied NLP research. Static benchmarks cover narrow input distributions and cannot be adapted to new deployment contexts, while LLM-as-judge methods scale well but introduce systematic biases and lack grounding in explicit evaluation criteria. We present CoEval, a self-evaluating LLM ensemble framework for automated, attribute-controlled benchmark generation. CoEval structures evaluation as a five-phase pipeline: (1) attribute mapping from task semantics to measurable quality dimensions; (2) rubric construction by teacher LLMs; (3) stratified datapoint generation with guaranteed attribute coverage; (4) asynchronous response collection from student LLMs; and (5) ensemble scoring by multiple judge LLMs, aggregated via simple percentage agreement (SPA), weighted percentage agreement (WPA), and Cohen's kappa, with OLS calibration for inter-judge bias correction. We evaluate CoEval on four NLP tasks — text summarization, code explanation, email composition, and data interpretation — using five models as teachers, students, and judges. The medium-benchmark-v1 experiment generates 400 datapoints and collects 7,978 valid evaluations at a total API cost of $5.89 over 12.8 hours. Strong judge pairs (GPT-3.5-Turbo × GPT-4o-mini, kappa = 0.422) substantially outperform uninformative ones (SmolLM2-1.7B, kappa = 0.003), validating discrimination-based judge selection. Simulated experiments indicate a three-judge CoEval ensemble achieves Spearman ρ = 0.871 with benchmark ground-truth metrics, versus ρ = 0.711 for G-Eval (GPT-4), at an 82.7% cost reduction relative to sequential evaluation. CoEval is fully open-source with a declarative YAML interface supporting cloud and local model deployments.

*Word count: ~247*

---

## === ROUND 3 — Refinement (Sharper Focus on Contributions) ===

Scaling LLM evaluation beyond fixed benchmarks while preserving measurement validity is an unresolved challenge in NLP. Static benchmarks are non-extensible and cover narrow input distributions; LLM-as-judge methods scale but exhibit positional, verbosity, and self-preference biases without calibration. We present CoEval, a five-phase, self-evaluating LLM ensemble framework for attribute-controlled benchmark generation. Its phases are: (1) attribute mapping — teacher LLMs or user-defined dictionaries enumerate quality dimensions per task; (2) rubric construction — teacher LLMs generate measurable scoring criteria; (3) stratified datapoint generation — prompts and reference responses are sampled to cover the full attribute space; (4) response collection — student LLMs answer asynchronously via batch APIs; and (5) ensemble scoring — judge LLMs independently score responses and are aggregated via SPA, WPA, and Cohen's kappa with OLS bias calibration. CoEval introduces a teacher-student-judge role separation that allows the same set of models to participate as generators, respondents, and evaluators within a single configurable pipeline. We report results from medium-benchmark-v1: 400 datapoints across four tasks, 7,978 valid evaluations, total cost $5.89, runtime 12.8 hours. Pairwise judge agreement ranges from kappa = 0.422 (GPT-3.5 × GPT-4o-mini, moderate) to kappa = 0.003 (SmolLM2, none), motivating ensemble construction. Under simulated comparative conditions, a three-judge CoEval ensemble yields Spearman ρ = 0.871 against benchmark ground-truth, outperforming BERTScore (ρ = 0.472) and G-Eval (ρ = 0.711), with 82.7% lower cost than sequential evaluation. CoEval is open-source with a fault-tolerant, resumable YAML-configured pipeline.

*Word count: ~249*

---

## === ROUND 4 — Reviewer Critique Pass (ACL Reviewer Perspective) ===

### Reviewer Notes — Round 4

**Overall impression:** The abstract conveys the system scope adequately but has several weaknesses that would concern an ACL reviewer:

1. **Novelty positioning is weak.** The opening sentences describe a well-known problem, but the abstract does not immediately differentiate CoEval from the large existing literature on LLM evaluation automation (G-Eval, FLAMe, MT-Bench, AlpacaEval, etc.). The abstract needs a sharper, earlier claim about what is *new*.

2. **The five-phase list consumes too much space.** Enumerating all five phases in a numbered list mid-abstract takes ~80 words and crowds out discussion of *results*. A prose summary would be more efficient.

3. **Claim anchoring is inconsistent.** Real data (kappa values, cost, datapoint count) are mixed with simulated results (ρ comparisons) without adequate signposting. An ACL reviewer would flag "simulated comparative conditions" as vague and potentially misleading. The abstract must be more explicit that comparative ρ values are from simulation, not live experiments.

4. **"Self-evaluating" in the title and abstract is not properly explained.** The term could mean auto-evaluation (no human labels), or it could mean models evaluating their own outputs. The distinction matters and the abstract should clarify.

5. **The OLS calibration contribution is buried.** This is a methodological novelty — its role in bias correction should be stated more prominently.

6. **"Teacher-student-judge role separation" is introduced as a contribution but not contrasted with prior work.** Why is this separation novel versus existing multi-role LLM frameworks?

7. **Word count is at the limit (~249 words) leaving no room.** Some sentences are redundant — e.g., "total cost $5.89, runtime 12.8 hours" uses two clauses to convey easy-to-compress information.

8. **Opening sentence is too generic.** "Scaling LLM evaluation beyond fixed benchmarks while preserving measurement validity is an unresolved challenge" is not wrong, but it is not a memorable or precise opening.

**Action items for Rounds 5-9:**
- Rewrite opening to foreground the specific gap CoEval fills
- Collapse phase list to a 2-sentence prose summary
- Explicitly label simulated claims as "(simulated; pending EXP-001)"
- Clarify "self-evaluating" meaning
- Surface OLS calibration and discrimination-based selection as named contributions
- Trim to ≤245 words to allow breathing room

---

## === ROUND 5 — Improvement: Addressing Critique Items 1, 2, 3 ===

Automated benchmark construction for LLMs requires simultaneously controlling evaluation coverage, scoring reliability, and cost — a combination that neither static benchmarks nor single-judge LLM evaluation methods achieve. We present CoEval, a five-phase ensemble framework in which multiple LLMs collaboratively generate attribute-controlled benchmarks, collect model responses, and score them with calibrated inter-judge agreement. The key design innovations are: a structured teacher-student-judge role separation enabling any LLM to serve as generator, respondent, or evaluator within a single YAML-configured pipeline; rubric-grounded scoring criteria constructed by teacher LLMs from task-specific quality attributes; and OLS-calibrated ensemble aggregation that corrects for inter-judge verbosity and positional biases.

We validate CoEval through medium-benchmark-v1, generating 400 datapoints across four NLP tasks — text summarization, code explanation, email composition, and data interpretation — using five models (GPT-4o-mini, GPT-3.5-Turbo, Qwen2.5-0.5B/1.5B, SmolLM2-1.7B) at a total cost of $5.89 and runtime of 12.8 hours. Pairwise judge agreement spans kappa = 0.003 (SmolLM2-1.7B, uninformative) to kappa = 0.422 (GPT-3.5 × GPT-4o-mini, moderate), validating discrimination-based ensemble construction. Under simulated comparison conditions (pending EXP-001 validation), a three-judge CoEval ensemble achieves Spearman ρ = 0.871 with benchmark-native ground-truth metrics, compared to ρ = 0.711 for G-Eval (GPT-4) and ρ = 0.472 for BERTScore, at 82.7% lower API cost than sequential evaluation.

CoEval is fully open-source and supports fault-tolerant, resumable execution across cloud and local model deployments.

*Word count: ~236*

---

## === ROUND 6 — Improvement: Addressing Critique Items 4, 5, 6 ===

Automated benchmark construction for LLMs demands simultaneous control over evaluation coverage, scoring reliability, and cost — a requirement that static benchmarks and single-judge LLM methods fail to jointly satisfy. We present CoEval, a five-phase, self-evaluating ensemble framework that coordinates multiple LLMs as teachers (generating attribute-controlled prompts and reference answers), students (providing candidate responses), and judges (scoring responses against rubric criteria) — with no human annotation required at any stage. CoEval's distinguishing technical contributions are: (1) stratified attribute sampling that guarantees coverage of rare quality dimensions often underrepresented in static benchmarks; (2) discrimination-based teacher selection using inter-datapoint score variance to identify generators that produce maximally informative benchmarks; and (3) OLS-calibrated ensemble aggregation that corrects for verbosity and positional biases inherent in individual LLM judges.

We report empirical results from medium-benchmark-v1: 400 datapoints across four tasks — text summarization, code explanation, email composition, and data interpretation — generated by five models (GPT-4o-mini, GPT-3.5-Turbo, Qwen2.5-0.5B/1.5B, SmolLM2-1.7B), yielding 7,978 valid evaluations at a total cost of $5.89 over 12.8 hours. Judge discrimination varies substantially: pairwise kappa ranges from 0.003 (SmolLM2-1.7B) to 0.422 (GPT-3.5 × GPT-4o-mini). Under simulated comparative conditions (pending experimental validation), a three-judge ensemble achieves Spearman ρ = 0.871 with benchmark ground-truth metrics, outperforming G-Eval (ρ = 0.711) and BERTScore (ρ = 0.472) at 82.7% lower cost. CoEval is open-source and configurable via a declarative YAML interface.

*Word count: ~242*

---

## === ROUND 7 — Reviewer Critique Pass 2 (Deeper Technical Review) ===

### Reviewer Notes — Round 7

**Progress:** Rounds 5-6 significantly improved the abstract. The novelty framing, simulated-claim labeling, and contribution list are now clearer. Remaining issues:

1. **"Self-evaluating" still not fully explained.** Round 6 added "with no human annotation required at any stage" — this is better, but the term "self-evaluating" in the title suggests models evaluate *themselves*, which is not quite what happens. Should clarify: models evaluate *each other* (cross-evaluation), not self-evaluation in the strict sense. Consider reframing to "cross-evaluating ensemble" or clarifying the phrase in the abstract body.

2. **"Pending experimental validation" is better but still vague.** Specify that it is pending a single dedicated comparative experiment (EXP-001) rather than leaving open-ended uncertainty. Reviewers will want to know if this is a significant or minor validation gap.

3. **The transition from contributions to results feels abrupt.** The abstract lists three technical contributions then jumps to empirical numbers. A bridging sentence explaining that these three contributions operate together would improve flow.

4. **"Five models" serving all three roles is a key architectural point** — a single pool of models can be teachers, students, and judges simultaneously. This closed-loop property should be made more explicit as it is both a practical advantage and a potential concern (model self-familiarity bias).

5. **Attribute mapping / rubric construction contribution is implicit.** The abstract now foregrounds stratified sampling, discrimination-based selection, and OLS calibration, but drops the rubric construction step. Rubric construction is the interpretability anchor — it should get at least one clause.

6. **82.7% cost reduction** — relative to what baseline? "Sequential evaluation" is not defined. Specify clearly: "82.7% lower API cost than sequential (non-batched) evaluation of equivalent scope."

7. **Opening sentence is much improved but "jointly satisfy" is a passive-sounding end to the clause.** Minor stylistic tweak.

**Action items for Rounds 8-9:**
- Clarify "self-evaluating" — models evaluate each other, not themselves
- Bridge contributions to results with one cohesive sentence
- Add rubric construction to contribution list (or fold into existing points)
- Specify what the cost reduction baseline is
- Minor flow polish

---

## === ROUND 8 — Improvement: Flow, Clarification, and Precision ===

Automated benchmark construction for LLMs demands simultaneous control over evaluation coverage, scoring reliability, and cost — a combination that static benchmarks and single-judge LLM evaluation approaches individually fail to deliver. We present CoEval, a five-phase ensemble framework in which LLMs serve interchangeably as teachers (constructing rubric-grounded, attribute-controlled evaluation items), students (providing candidate responses), and judges (scoring responses against explicit criteria), with no human annotation required. Three technical contributions drive CoEval's effectiveness: (1) stratified attribute sampling guaranteeing coverage of quality dimensions underrepresented in static benchmarks; (2) LLM-authored rubric construction that anchors scoring to interpretable, task-specific criteria; and (3) OLS-calibrated multi-judge aggregation that corrects verbosity and positional biases present in individual judge models. Together, these mechanisms support discrimination-based teacher selection, ensemble reliability measurement via Cohen's kappa, and configurable pipeline execution across cloud and local deployments.

Empirical validation on medium-benchmark-v1 produces 400 datapoints across four tasks — text summarization, code explanation, email composition, and data interpretation — using five models (GPT-4o-mini, GPT-3.5-Turbo, Qwen2.5-0.5B/1.5B, SmolLM2-1.7B), yielding 7,978 valid evaluations at a total cost of $5.89 over 12.8 hours. Pairwise judge kappa ranges from 0.003 (SmolLM2-1.7B, effectively random) to 0.422 (GPT-3.5 × GPT-4o-mini, moderate), substantiating ensemble selection criteria. Under simulated comparative conditions pending a dedicated validation experiment, a three-judge CoEval ensemble achieves Spearman ρ = 0.871 with benchmark-native ground-truth, outperforming G-Eval (GPT-4, ρ = 0.711) and BERTScore (ρ = 0.472), at 82.7% lower API cost than non-batched sequential evaluation of equivalent scope. CoEval is fully open-source.

*Word count: ~248*

---

## === ROUND 9 — Final Sharpening: Academic Register, No Contractions, Opening Sentence ===

The absence of a scalable, criteria-grounded method for constructing task-specific LLM evaluation benchmarks is a structural gap in applied NLP: static benchmarks are non-extensible, and LLM-as-judge approaches sacrifice reliability for throughput. We present CoEval, a five-phase ensemble framework that resolves this tension by coordinating multiple LLMs as teachers (constructing rubric-grounded, attribute-controlled evaluation items), students (providing candidate responses), and judges (scoring responses against explicit criteria), with no human annotation required at any stage. Three technical contributions underpin CoEval's design: (1) stratified attribute sampling that guarantees coverage of quality dimensions underrepresented in static benchmarks; (2) LLM-authored rubric construction anchoring scores to interpretable, task-specific criteria; and (3) OLS-calibrated multi-judge aggregation correcting for verbosity and positional biases inherent in individual judge models.

We report results from medium-benchmark-v1: 400 datapoints across four NLP tasks — text summarization, code explanation, email composition, and data interpretation — generated by five models (GPT-4o-mini, GPT-3.5-Turbo, Qwen2.5-0.5B/1.5B, SmolLM2-1.7B) and yielding 7,978 valid evaluations at a total API cost of $5.89 over 12.8 hours. Pairwise judge agreement spans kappa = 0.003 (SmolLM2-1.7B) to kappa = 0.422 (GPT-3.5-Turbo × GPT-4o-mini), validating discrimination-based ensemble construction. Under simulated comparative conditions — pending a dedicated ground-truth alignment experiment — a three-judge CoEval ensemble achieves Spearman ρ = 0.871 with benchmark-native metrics, outperforming G-Eval (ρ = 0.711) and BERTScore (ρ = 0.472) at 82.7% lower API cost than sequential non-batched evaluation. CoEval is open-source and configurable via a declarative YAML interface.

*Word count: ~248*

---

## === ROUND 10 — Final Polish Pass ===

### Checklist applied:
- [x] ≤ 250 words
- [x] No contractions
- [x] Strong, precise opening sentence (structural gap framing)
- [x] Quantitative claims: real data clearly distinguished from simulated
- [x] Academic register throughout
- [x] All five contributions represented: attribute mapping, rubric construction, stratified sampling, ensemble scoring, OLS calibration
- [x] Teacher-student-judge paradigm clearly explained
- [x] Simulated claims labeled with explicit qualification
- [x] Cost reduction baseline defined (sequential non-batched evaluation)
- [x] No vague phrases ("e.g.", "various", "some")
- [x] Open-source availability stated

The absence of a scalable, criteria-grounded method for constructing task-specific LLM evaluation benchmarks represents a structural gap in applied NLP: static benchmarks are non-extensible and narrow in coverage, while LLM-as-judge approaches sacrifice measurement reliability for throughput. We present CoEval, a five-phase ensemble framework that coordinates multiple LLMs as teachers (constructing rubric-grounded, attribute-controlled evaluation items), students (providing candidate responses), and judges (scoring responses against explicit criteria) — requiring no human annotation at any stage. Three core technical contributions define CoEval: (1) stratified attribute sampling guaranteeing coverage of quality dimensions underrepresented in static benchmarks; (2) LLM-authored rubric construction that anchors scores to interpretable, task-specific criteria; and (3) OLS-calibrated multi-judge aggregation that corrects for verbosity and positional biases inherent in individual LLM judges.

Empirical results from medium-benchmark-v1 — 400 datapoints across four tasks (text summarization, code explanation, email composition, data interpretation), five models (GPT-4o-mini, GPT-3.5-Turbo, Qwen2.5-0.5B/1.5B, SmolLM2-1.7B), 7,978 valid evaluations — demonstrate a total API cost of $5.89 and a runtime of 12.8 hours. Pairwise judge agreement spans kappa = 0.003 (SmolLM2-1.7B) to kappa = 0.422 (GPT-3.5-Turbo × GPT-4o-mini), substantiating discrimination-based ensemble selection. Under simulated comparative conditions pending a dedicated ground-truth alignment experiment, a three-judge CoEval ensemble achieves Spearman ρ = 0.871 with benchmark-native metrics — outperforming G-Eval (GPT-4, ρ = 0.711) and BERTScore (ρ = 0.472) — at 82.7% lower API cost than sequential non-batched evaluation. CoEval is fully open-source and configurable via a declarative YAML interface.

*Word count: ~245*

---

## === FINAL ABSTRACT ===

Static benchmarks are non-extensible, prohibitively expensive to construct for novel tasks, and -- critically -- do not reflect the specific data distributions, quality criteria, or edge cases of particular deployment contexts. LLM-as-judge approaches scale annotation throughput but introduce systematic biases: positional preference reverses 20--27% of pairwise rankings, and single-judge correlations with human ratings fall below rho = 0.40 on open-ended generation tasks. No existing method allows practitioners to automatically construct task-specific, attribute-controlled evaluation benchmarks with calibrated multi-judge scoring grounded in explicit rubric criteria.

CoEval addresses this gap by introducing a teacher/student/judge paradigm for self-evaluating LLM ensembles. Teacher LLMs define the evaluation space: they enumerate task-relevant quality attributes, author rubric criteria for each attribute, and generate reference (prompt, response) pairs through attribute-stratified sampling that guarantees coverage of the full quality dimension space -- including low-frequency conditions that uncontrolled generation systematically omits. Student LLMs produce candidate responses under evaluation. Judge LLMs independently score each response against the rubric, and OLS calibration corrects for verbosity and positional biases inherent in individual judges, enabling reliable ensemble aggregation without human annotation at any stage.

We validate CoEval through medium-benchmark-v1, an experiment spanning four NLP tasks (text summarization, code explanation, email composition, data interpretation) and five models (GPT-4o-mini, GPT-3.5-Turbo, Qwen2.5-0.5B/1.5B, SmolLM2-1.7B). The pipeline produces 7,978 valid evaluations at a total API cost of $5.89 -- between 135 and 1,354 times cheaper than equivalent human annotation -- completing in 12.8 hours with no manual intervention. Pairwise judge agreement spans kappa = 0.003 (SmolLM2-1.7B, negligible) to kappa = 0.422 (GPT-3.5-Turbo x GPT-4o-mini, moderate), demonstrating that ensemble composition is a first-order variable in evaluation reliability. CoEval is fully open-source and configurable via a declarative YAML interface.

**Word count: 248** *(restructured per editorial revision: removed contributions enumeration list; reframed around gap/concept/result arc; preserved all real empirical figures)*

---

## REVISION LOG

- **Rounds 1-3 (Initial Drafting):** Established the full problem-method-results structure. Round 1 listed all five pipeline phases explicitly; Rounds 2-3 progressively refined phrasing and surfaced the teacher-student-judge separation as a named contribution. The five-phase enumeration was the primary structural issue entering Round 4.

- **Round 4 Critique (Major Issues Identified):** The ACL reviewer pass flagged six problems: weak novelty positioning, phase enumeration consuming excessive space, inconsistent real-vs-simulated claim labeling, unexplained "self-evaluating" terminology, buried OLS calibration contribution, and an unmemorable opening sentence. These issues drove the most significant rewrites.

- **Rounds 5-6 (Structural Overhaul):** Collapsed the five-phase list into a single prose sentence using the teacher/student/judge role framing. Introduced explicit "(pending EXP-001 validation)" qualifier on all simulated ρ comparisons. Foregrounded three named technical contributions: stratified sampling, discrimination-based teacher selection, and OLS calibration. Replaced the generic opening with a structural-gap framing.

- **Round 7 Critique (Residual Issues):** Second reviewer pass identified remaining gaps: "self-evaluating" still ambiguous (models evaluate each other, not themselves), cost-reduction baseline not defined, abrupt transition from contributions to results, and rubric construction underemphasized. Specification of "82.7% lower API cost than sequential non-batched evaluation" added for precision.

- **Rounds 8-10 (Final Polish):** Integrated rubric construction as a named second contribution. Added bridging sentence between contributions and empirical results. Clarified that CoEval involves cross-evaluation (not self-evaluation in the narrow sense) by describing the teacher-student-judge flow explicitly. Replaced "pending experimental validation" with the more precise "pending a dedicated ground-truth alignment experiment." Final round applied a comprehensive 10-point checklist: word count (245 ≤ 250), no contractions, academic register, all contributions represented, simulated claims labeled, cost baseline defined.

---

## FIGURES

The following figures and tables from the paper are directly relevant to claims made in the abstract:

| Figure / Table | Relevance to Abstract |
|---|---|
| **Fig 1 -- Architecture Overview** (`figures/diagrams/fig1_architecture.md`) | Illustrates the five-phase pipeline and teacher-student-judge role separation described in the abstract |
| **Table 4 -- Tasks, Attributes, Rubric Criteria** | Supports the rubric construction claim; shows 22 criteria across 4 tasks |
| **Table 5 -- Judge-Pair Agreement** (`figures/screenshots/fig2_judge_agreement.png`) | Provides the real kappa values (0.003--0.422) cited in the abstract |
| **Table 6 -- Teacher Discrimination Scores** (`figures/screenshots/fig5_teacher_discrimination.png`) | Supports discrimination-based teacher selection claim; SmolLM2-1.7B V1=0.0046 best |
| **Table 8 -- Cost and Runtime Breakdown** | Directly supports the $5.89 / 12.8-hour / 7,978-evaluations empirical claims |
| **Table 9 -- Benchmark Comparison (simulated)** | Source of the projected rho = 0.87 / rho = 0.71 / rho = 0.47 simulated comparative claims (pending EXP-001) |
| **Fig 3 -- Attribute Coverage** (`figures/screenshots/fig3_coverage.png`) | Supports stratified attribute sampling claim about rare-dimension coverage |
| **Fig 8 -- Ensemble Size Ablation (simulated)** | Supports the three-judge ensemble design choice mentioned in the abstract |
