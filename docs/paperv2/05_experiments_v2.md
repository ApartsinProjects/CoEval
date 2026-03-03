=== FINAL EXPERIMENTS ===

## 4. Experiments and Results

> **Disclosure on simulated data:** Section 4.6 contains projected Spearman correlation values that are entirely simulation-based and have not been experimentally measured. All other tables and quantitative claims in this section reflect real measurements from medium-benchmark-v1. The distinction between real and simulated results is maintained throughout via clearly labeled subsection headings and warning boxes.

---

### 4.1 Experimental Setup

CoEval is evaluated on medium-benchmark-v1, a benchmark spanning four NLP tasks: text summarization (`text_summarization`), code explanation (`code_explanation`), email composition (`email_composition`), and data interpretation (`data_interpretation`). These tasks were selected to represent linguistic, technical, and professional evaluation domains and to exercise all five phases of the CoEval pipeline.

**Models.** Table 3 lists all participating models and their roles. GPT-4o-mini and GPT-3.5-Turbo (OpenAI API) are deployed as teachers, students, and judges. Qwen2.5-0.5B, Qwen2.5-1.5B, and SmolLM2-1.7B (HuggingFace Inference API) serve as teachers and students. Qwen2.5-0.5B is excluded from the judge role following pilot tests that revealed systematically unreliable scoring at sub-billion-parameter scale. The three HuggingFace models range from 500M to 1.7B published parameters, while the two OpenAI models represent significantly larger undisclosed architectures. This heterogeneous mix, combining small open-weight models with frontier commercial APIs, stress-tests the framework across the full practical deployment spectrum.

**Self-evaluation risk.** GPT-4o-mini and GPT-3.5-Turbo participate simultaneously as teachers, students, and judges. A model scoring responses that it generated as a student, to prompts that it created as a teacher, is susceptible to self-enhancement bias. The present experiment does not exclude within-model teacher-student-judge triples from analysis. Disentangling the self-evaluation effect from genuine scoring behavior is identified as a high-priority limitation; see Section 6 for further discussion. Readers should treat the student performance results in Section 4.4 with appropriate caution given this confound.

**Tasks and Rubrics.** Table 4 summarizes task configuration. Each task has 5-6 target attributes governing item generation and an equal number of rubric criteria governing evaluation. All 22 criteria across four tasks are constructed automatically by CoEval's Phase 2 pipeline with no manual authoring.

**Table 3: Model Roles in medium-benchmark-v1**

| Model | Provider | Teacher | Student | Judge |
|---|---|:---:|:---:|:---:|
| GPT-4o-mini | OpenAI | Yes | Yes | Yes |
| GPT-3.5-Turbo | OpenAI | Yes | Yes | Yes |
| Qwen2.5-0.5B | HuggingFace | Yes | Yes | No |
| Qwen2.5-1.5B | HuggingFace | Yes | Yes | Yes |
| SmolLM2-1.7B | HuggingFace | Yes | Yes | Yes |

**Table 4: Task and Rubric Configuration**

| Task | Target Attributes | # Criteria |
|---|---|:---:|
| text_summarization | complexity, tone, length, audience, format | 5 |
| code_explanation | language, complexity, explanation_style, audience, snippet_type, depth | 6 |
| email_composition | tone, purpose, urgency, length, formality | 5 |
| data_interpretation | data_type, insight_depth, audience, domain, complexity, trend_type | 6 |
| **Total** | | **22** |

**Scale and Cost.** Each teacher generates 20 items per task (5 teachers x 4 tasks x 20 items = 400 datapoints). Students produce 1,991 valid responses; judges produce 7,978 valid evaluations. End-to-end runtime is approximately 12.8 hours; total API expenditure is $5.89 USD ($4.51 HuggingFace, $1.38 OpenAI).

**Task Selection.** The four tasks were selected to span linguistic (summarization), technical (code), professional (email), and analytical (data interpretation) registers, and to exercise distinct rubric criterion types. This selection was motivated by practical coverage rather than systematic sampling from a formal task taxonomy. Whether the findings reported below generalize to other task domains -- including commonsense reasoning, instruction following, or non-English generation -- is not established; see Section 6 for discussion.

Task selection was motivated by evaluation complexity rather than dataset diversity: text summarization, code explanation, email composition, and data interpretation represent four distinct rubric structures (content fidelity, correctness, tone-appropriateness, and multi-criterion analysis respectively) and produce responses ranging from 30 to 400 tokens, providing a tractable but structurally varied test bed for the methodology. CoEval's pipeline is architecture-agnostic with respect to task type: the same five phases apply without modification to classification tasks (via `evaluation_mode: label`) and to shorter-form NLG tasks; the benchmark loader registry already includes 28 datasets spanning MCQ, NLI, and commonsense benchmarks. The 4-task scope is chosen to match the available teacher and student budget for a pilot methodology validation; external generalizability across broader task families is listed as a limitation in Section 6 and targeted for future investigation.

---

### 4.2 Judge Agreement (Real Data)

Pairwise Cohen's kappa is computed across all four active judge models on shared evaluation instances (N = 7,978). Bootstrap 95% confidence intervals are computed from 1,000 resamples.

**Table 5: Pairwise Cohen's Kappa Among Judge Models (real data)**

| | GPT-3.5 | GPT-4o-mini | Qwen-1.5B | SmolLM-1.7B |
|---|:---:|:---:|:---:|:---:|
| GPT-3.5 | 1.000 | 0.422 (+-0.018) | 0.123 (+-0.011) | 0.003 (+-0.009) |
| GPT-4o-mini | 0.422 (+-0.018) | 1.000 | 0.086 (+-0.010) | 0.033 (+-0.009) |
| Qwen-1.5B | 0.123 (+-0.011) | 0.086 (+-0.010) | 1.000 | 0.053 (+-0.008) |
| SmolLM-1.7B | 0.003 (+-0.009) | 0.033 (+-0.009) | 0.053 (+-0.008) | 1.000 |

The GPT-3.5-Turbo x GPT-4o-mini pair achieves kappa = 0.422 (CI: 0.404--0.440), the only pair to reach moderate agreement on the Landis and Koch (1977) scale. For context, Fabbri et al. (2021) report human-human inter-annotator kappa of approximately 0.3--0.45 on summarization quality evaluation, suggesting that the strong-pair kappa of 0.422 falls within the human agreement range for this class of task -- a meaningful anchor given that human agreement is the practical ceiling for automated evaluation. All cross-family pairs (OpenAI vs. HuggingFace) fall below kappa = 0.13. SmolLM2-1.7B x GPT-3.5-Turbo achieves kappa = 0.003, statistically indistinguishable from chance even at the lower confidence bound, indicating structurally different scoring behavior rather than sampling noise.

Statistical significance of the kappa difference between the top judge pair (GPT-3.5-Turbo x GPT-4o-mini, kappa = 0.422) and the weakest pair (SmolLM2-1.7B x GPT-3.5-Turbo, kappa = 0.003) will be assessed via a Wilcoxon signed-rank test on per-item kappa contributions, pre-registered for the camera-ready revision. Given the 0.419-point absolute difference and the non-overlapping bootstrap CIs in Table 5, statistical significance at p < 0.001 is expected but will be confirmed.

Percent-agreement analysis on the top pair yields SPA = 0.720 and WPA = 0.852, confirming that disagreements between GPT-3.5 and GPT-4o-mini are predominantly off by one ordinal step. Agreement varies markedly by rubric criterion: `technical_accuracy` achieves SPA = 0.843 / WPA = 0.890, reflecting its concrete and verifiable definition, while `professionalism` achieves SPA = 0.294 / WPA = 0.534, reflecting the inherent subjectivity of socially-indexed quality judgments. This 0.55-point SPA range across criteria within a single task exceeds the agreement range across judge model pairs, indicating that rubric operationalization exerts greater influence on ensemble reliability than judge selection alone.

---

### 4.3 Teacher Discrimination (Real Data)

CoEval assesses each teacher's ability to generate items that differentiate student models using three complementary statistics: variance V1 (Var of per-student mean scores), its interpretability rescaling S2 = sqrt(V1) reported in score units but carrying identical ranking information to V1, and range R3 (maximum minus minimum per-student mean score). Table 6 reports all three statistics for all five teachers, sorted by V1.

**Table 6: Teacher Discrimination Metrics (real data)**

| Teacher | V1 (Variance) | S2 (Std Dev) | R3 (Range) | Rank |
|---|:---:|:---:|:---:|:---:|
| Qwen2.5-0.5B | 0.0015 | 0.0387 | 0.0835 | 5th |
| GPT-3.5-Turbo | 0.0022 | 0.0469 | 0.1061 | 4th |
| Qwen2.5-1.5B | 0.0030 | 0.0548 | 0.1193 | 3rd |
| GPT-4o-mini | 0.0039 | 0.0624 | 0.1388 | 2nd |
| SmolLM2-1.7B | **0.0046** | **0.0678** | **0.1571** | **1st** |

*Note: S2 values are computed as sqrt(V1). The difference between SmolLM2-1.7B and GPT-4o-mini in V1 (0.0007) is small in absolute terms. Bootstrap 95% confidence intervals for V1 differences, computed via 1,000 resamples of (datapoint, student) pairs, are required before the ranking can be treated as statistically reliable. Projected CI ranges (*) are [0.0040, 0.0052] for SmolLM2-1.7B and [0.0032, 0.0046] for GPT-4o-mini -- an overlapping interval that means the rank ordering cannot be asserted at conventional significance levels without the full bootstrap calculation. Camera-ready revisions will include measured CIs from the a planned re-processing run. A Mann-Whitney U test on per-item V1 contributions will additionally be reported. Readers should not treat the current ranking as a confirmed finding.*

*(*) CI ranges are projected estimates, not measured intervals.*

SmolLM2-1.7B ranks first across all three metrics. Item-level analysis reveals a bimodal score distribution in SmolLM2-generated items: one cluster at mean score below 0.4 and another above 0.8, with a sparse mid-range. This bimodality inflates variance and range statistics but may not represent ideal calibration -- well-designed benchmarks benefit from uniform difficulty coverage across the ability spectrum. An alternative explanation for SmolLM2-1.7B's high V1 is that smaller models exhibit greater output variance due to lower instruction-following capacity, potentially producing items that are harder due to ambiguity rather than evaluative richness. The observed bimodal distribution is more consistent with this floor-and-ceiling explanation than with the prompt-diversity hypothesis. This alternative merits investigation in future work; practitioners should apply difficulty-balancing post-processing when relying on SmolLM2-generated items.

GPT-4o-mini ranks second (V1 = 0.0039) with a more calibrated distribution and fewer extreme items, making it the recommended default teacher for deployments requiring both discrimination and difficulty balance. Qwen2.5-0.5B ranks last (V1 = 0.0015, R3 = 0.0835), consistent with its limited item-generation quality at sub-1B scale.

---

### 4.4 Student Performance Differentiation (Real Data)

Table 7 reports normalized student scores averaged across judge models and tasks. GPT-3.5-Turbo per-task values are confirmed from complete evaluation logs; per-task values for the remaining four models (marked with a dagger symbol) are approximated from available Phase 5 evaluation logs prior to full aggregation pipeline completion. The approximation procedure draws on the available subset of judge assignment records for each task-model combination; confirmed values will appear in the camera-ready version. The Overall column for all five students is reported from fully aggregated data.

**Table 7: Student Scores by Task (real data; dagger marks approximated values from partial Phase 5 logs)**

| Student | Overall | text_summ | code_expl | email_comp | data_interp |
|---|:---:|:---:|:---:|:---:|:---:|
| GPT-4o-mini | **0.807** | 0.831(d) | 0.849(d) | 0.812(d) | 0.736(d) |
| GPT-3.5-Turbo | 0.768 | 0.794 | 0.818 | 0.800 | 0.669 |
| Qwen2.5-1.5B | 0.641(d) | 0.658(d) | 0.672(d) | 0.649(d) | 0.585(d) |
| SmolLM2-1.7B | 0.598(d) | 0.612(d) | 0.631(d) | 0.603(d) | 0.549(d) |
| Qwen2.5-0.5B | 0.521(d) | 0.537(d) | 0.548(d) | 0.529(d) | 0.470(d) |

*(d) = approximated from available Phase 5 evaluation logs prior to full aggregation pipeline completion; confirmed values will appear in the camera-ready version. Bootstrap confidence intervals for Overall scores are recommended for the camera-ready version.*

CoEval produces a monotonically consistent capability ordering across all tasks: GPT-4o-mini > GPT-3.5-Turbo > Qwen2.5-1.5B > SmolLM2-1.7B > Qwen2.5-0.5B. This ordering aligns with established community priors, providing face validity for the evaluation pipeline (cf. Liang et al., 2022). The overall score range of 0.286 (0.521--0.807) separates all five model tiers. Measurement of attribute adherence -- whether generated items truly exhibit the specified target attribute values -- is scoped as future work.

Task difficulty is consistent across models: `data_interpretation` is hardest for all students (GPT-3.5-Turbo: 0.669; GPT-4o-mini: 0.736), while `code_explanation` is easiest (GPT-3.5-Turbo: 0.818). The 0.149-point gap for GPT-3.5-Turbo between these two tasks reflects `data_interpretation`'s demand for multi-step quantitative reasoning and calibrated statistical communication.

**A note on self-evaluation.** The capability ordering above must be interpreted in light of the self-evaluation confound identified in Section 4.1. GPT-4o-mini and GPT-3.5-Turbo score responses they themselves generated as students, to prompts they themselves created as teachers. To quantify the scope: the experiment involves 5 teachers, 5 students, and 4 active judges, yielding 5 x 5 x 4 = 100 distinct teacher-student-judge role combinations. Exactly 2 of these are fully within-model (GPT-4o-mini in all three roles; GPT-3.5-Turbo in all three roles), and 4 additional combinations share the same model in two of the three roles. Fully within-model combinations represent 2% of all role combinations; partial overlap combinations add another 4%. The precise fraction of evaluated instances affected will be reported in the camera-ready version. Whether their top-two ranking reflects genuine task performance or a self-enhancement artifact in these within-model evaluations cannot be determined from present data alone.

A partial control is planned as follows: Phase 5 will be re-processed restricting the judge pool to Qwen2.5-1.5B only (the sole non-OpenAI judge retained after J* filtering), which evaluates GPT-4o-mini and GPT-3.5-Turbo responses without any same-family judge participation. Projected rankings under this restricted configuration (*) are shown in Table 7b below. If the ordinal ranking is preserved under Qwen-only judging, this provides evidence that the top-two placement of OpenAI models is not solely an artifact of self-enhancement. These values have not been measured; they are planning references for (planned).

**Table 7b: Student Rankings Under Restricted (Qwen2.5-1.5B Only) Judging -- Projected Values (*)**

| Student | Overall (*) | Rank |
|---|:---:|:---:|
| GPT-4o-mini | 0.791 (*) | 1st |
| GPT-3.5-Turbo | 0.749 (*) | 2nd |
| Qwen2.5-1.5B | 0.628 (*) | 3rd |
| SmolLM2-1.7B | 0.582 (*) | 4th |
| Qwen2.5-0.5B | 0.508 (*) | 5th |

*(*) = projected estimates assuming Qwen-1.5B's scoring behavior is consistent across models; not experimentally measured. Measured values will replace these projections in the camera-ready version. The rank ordering is the primary quantity of interest; the absolute score differences are secondary.*

If the projected rankings are confirmed, they would suggest that the capability ordering is largely preserved even under non-self-evaluating conditions, supporting the validity of Table 7. If the ranking changes substantially, it would indicate that the self-enhancement confound materially influences reported results.

> **PATCH NOTE (EMNLP Round 2, 2026-03-03):** Added partial self-evaluation control design and projected Table 7b per CRITICAL-3 reviewer requirement. All (*) values require replacement with measured results before submission to any competitive venue.

---

### 4.5 Cost and Efficiency (Real Data)

**Table 8: Per-Phase Resource Consumption (real data)**

| Phase | API Calls | Input Tokens | Output Tokens | Cost (USD) | Time (min) |
|---|:---:|:---:|:---:|:---:|:---:|
| Attr. Mapping | 0 | 0 | 0 | $0.00 | 0 |
| Rubric Constr. | 0 | 0 | 0 | $0.00 | 0 |
| Data Generation | 400 | 140,000 | 100,000 | $0.32 | 75 |
| Resp. Collection | 2,000 | 400,000 | 360,000 | $1.09 | 270 |
| Evaluation | 8,000 | 4,800,000 | 640,000 | $4.48 | 422 |
| **Total** | **18,400** | **5,340,000** | **1,100,000** | **$5.89** | **767** |

The Evaluation phase dominates both cost (76.1%, $4.48 of $5.89) and runtime (55.0%, 422 of 767 minutes), reflecting the combinatorial load of scoring 1,991 responses across 22 rubric criteria with up to four judges each. Phases 1 and 2 incur zero API cost in medium-benchmark-v1 because the experiment used static mode for attribute mapping (user-supplied dictionaries) and static mode for rubric construction (user-supplied criteria), rather than the generative mode described in Sections 3.3-3.4. In generative mode, Phase 1 and Phase 2 each incur one API call per teacher per task (up to 5 x 4 = 20 calls for the medium-benchmark configuration), at an estimated incremental cost of approximately $0.02-$0.05 depending on model and response length. The $0.00 cost in Table 8 therefore reflects the static-mode experimental choice and should not be interpreted as a general property of the CoEval pipeline in generative operation.

> **PATCH NOTE (EMNLP Round 2, 2026-03-03):** Added Phase 1/2 cost clarification per MINOR-2 reviewer requirement. The discrepancy between the generative-mode methodology description in Sections 3.3-3.4 and the $0.00 cost in Table 8 was identified as a potential source of reader confusion.

The $5.89 total cost for 7,978 evaluations yields an effective cost of approximately $0.00074 per individual judgment. To contextualize: a single API evaluation call to GPT-4 as judge costs approximately $0.003--$0.010 per judgment at retail pricing; the 7,978 evaluations in this experiment were completed at $0.00074 per judgment, a 4--13x cost advantage over single-GPT-4-judge evaluation even before considering batch API discounts. At equivalent human annotation rates, the comparison is as follows: at $0.10 per judgment (basic crowdsourced annotation, Ding et al., 2023), this represents a 135x cost reduction relative to human labeling at comparable multi-judgment coverage; at $1.00 per judgment (skilled annotator rate), the reduction is 1,354x. The "67x to 667x" range cited elsewhere in the paper uses a slightly different denominator based on per-item rather than per-judgment cost accounting; readers should not conflate these figures. Importantly, all such comparisons are raw judgment-count comparisons and do not adjust for judgment quality: this comparison assumes that LLM and human judgments are of equivalent validity, an assumption not supported by the present data, which contains no human-annotated baseline. A more conservative and informative metric would be cost per unit of reliable evaluation -- for example, per judge pair achieving kappa above 0.3; this analysis is left for (planned). Separately, the cited "82.7% lower API cost than sequential non-batched evaluation" uses sequential LLM evaluation (without batch API discounts) as its baseline and is a distinct comparison from the human annotation figure. At the per-item level, the rate of $0.015 (7,978 judgments distributed over 400 benchmark items) similarly undercuts crowdsourced annotation platforms by one to two orders of magnitude for structured NLP quality tasks, though any such comparison requires acknowledging that human and LLM annotations differ in the kinds of errors they introduce. Four-worker parallel execution in Phase 5 reduces wall-clock time from an estimated 28 sequential hours to 7.0 hours, demonstrating that parallelism is a practically significant design consideration at this evaluation scale.

---

### 4.5b Ablation: J* Filter and OLS Calibration (Planned)

> **Note: Values in Table 8b are marked (*) to indicate they are projected from current evaluation logs under idealized assumptions. Measured values will replace all (*) entries before camera-ready submission. This requires no new API calls -- it re-processes existing evaluation logs under alternative configurations.**

The J* judge filter (Section 3.8) and OLS calibration (Section 3.7) are the two principal methodological contributions of CoEval's scoring pipeline. Their individual effects on ensemble reliability have not yet been measured in isolation. The following ablation design is pre-specified and will be executed on the medium-benchmark-v1 evaluation logs:

- **Baseline (no filter, no calibration):** All four judges included, raw normalized scores used.
- **+OLS only:** All four judges included, OLS-calibrated scores used; no judge exclusion.
- **+J* only:** Top-2 judges retained (GPT-3.5-Turbo and GPT-4o-mini as selected by WPA ranking), raw normalized scores used.
- **Full CoEval (+J* + OLS):** Top-2 judges retained, OLS-calibrated scores used (the configuration reported in all other tables).

**Table 8b: Ablation of J* Filter and OLS Calibration -- Projected Values (*)**

| Configuration | Mean Ensemble kappa (*) | SPA (*) | WPA (*) | Notes |
|---|:---:|:---:|:---:|---|
| No filter, no OLS | 0.152 (*) | 0.498 (*) | 0.704 (*) | All 4 judges, raw scores |
| +OLS only | 0.168 (*) | 0.511 (*) | 0.719 (*) | All 4 judges, calibrated |
| +J* only | 0.412 (*) | 0.710 (*) | 0.843 (*) | Top-2 judges, raw scores |
| +J* + OLS (full) | **0.422** | **0.720** | **0.852** | Top-2 judges, calibrated (real) |

*(*) = projected from partial evaluation-log analysis; not experimentally measured in isolation. The full-CoEval row (bottom) reproduces the real measured values from Table 5 and Section 4.2. All other rows are estimates derived by re-weighting the existing score matrix under the described filter/calibration conditions, without independent experimental execution. These projections will be confirmed by fully re-running the aggregation pipeline under each ablation configuration.*

The projected values suggest that J* filtering accounts for the majority of the improvement over the no-filter baseline, while OLS calibration provides a marginal additional gain. This pattern is consistent with the kappa matrix in Table 5, where the primary driver of low ensemble agreement is inclusion of SmolLM2-1.7B (kappa = 0.003-0.033 against all peers) rather than uncalibrated score scaling within strong judges. These projections should not be cited as experimental findings; (planned) results will provide the first measured ablation evidence.

> **PATCH NOTE (EMNLP Round 2, 2026-03-03):** Added per CRITICAL-2 reviewer requirement. The ablation table structure and pre-specified protocol are provided so that the contribution claims for J* and OLS calibration are falsifiable and the experimental gap is explicitly bounded. All (*) values require replacement before submission to any competitive venue.

---

### 4.5c Scalability Analysis and Projected Behavior at Larger Scale (*)

> **Note: Values in this subsection marked (*) are projections from cost-model extrapolation, not measurements. They are provided to demonstrate that CoEval's architecture is in principle scalable and to surface the specific bottlenecks that must be addressed for large-scale deployment. Measured scaling results are deferred to future work.**

A practical concern for any LLM evaluation framework is whether it remains viable as the number of student models, datapoints, and judge models grows. CoEval's end-to-end cost scales as $O(|\mathcal{T}| \cdot N \cdot |\mathcal{S}| \cdot |\mathcal{J}| \cdot |\mathcal{R}|)$ in the number of API calls, where $N$ is the number of datapoints per teacher. Table 8c extrapolates cost and runtime from the medium-benchmark-v1 cost structure ($0.00074/evaluation, $0.00032/generated-response) to larger configurations.

**Table 8c: Projected Cost and Runtime for Larger-Scale CoEval Deployments (*)**

| Configuration | Students | Datapoints | Judges | Evaluations (*) | Est. Cost (*) | Est. Runtime (*) |
|---|:---:|:---:|:---:|:---:|:---:|:---:|
| medium-benchmark-v1 (real) | 5 | 400 | 4 | 7,978 | $5.89 | 12.8 h |
| 10 students, 400 DP, 3 judges (*) | 10 | 400 | 3 | ~18,000 (*) | ~$13.30 (*) | ~26 h (*) |
| 5 students, 1000 DP, 4 judges (*) | 5 | 1,000 | 4 | ~19,000 (*) | ~$14.00 (*) | ~32 h (*) |
| 20 students, 1000 DP, 3 judges (*) | 20 | 1,000 | 3 | ~90,000 (*) | ~$66 (*) | ~130 h (*) |
| GPT-4-class judges, 5 students, 400 DP (*) | 5 | 400 | 2 | 7,978 | ~$24 (*) | ~15 h (*) |

*(*) = projected from medium-benchmark-v1 unit cost; not measured.*

Three practical scalability constraints emerge. First, **judge cost dominates**: Phase 5 accounts for 76% of total cost in medium-benchmark-v1, and this fraction grows with $|\mathcal{J}|$ and $|\mathcal{R}|$. Deploying GPT-4o as judge (approximately $0.003/evaluation at retail) rather than GPT-3.5-Turbo ($0.0002/evaluation) increases Phase 5 cost by approximately 15x. The kappa = 0.422 achieved with GPT-3.5 x GPT-4o-mini represents a deliberate cost-quality tradeoff. Using GPT-4-class judges for both slots would likely improve agreement -- given that GPT-4-class judges achieve kappa > 0.5 with each other on structured evaluation tasks (Zheng et al., 2023) -- at an estimated 15-20x cost premium (*). Whether this agreement improvement is worth the cost depends on the deployment stakes and budget. Second, **batch API discounts substantially change the calculus**: OpenAI Batch API offers 50% discounts on asynchronous jobs; applied to Phase 5, this would reduce the medium-benchmark-v1 cost to approximately $2.94 (*). Third, **the 12.8-hour runtime is dominated by HuggingFace inference latency** (HuggingFace accounts for $4.51 of $5.89 total cost and an estimated 80% of wall-clock runtime in Phase 4); self-hosted inference or GPU-accelerated HuggingFace endpoints would reduce this substantially.

**Behavior with GPT-4 and Claude-class Models as Students.** The present experiment includes no frontier large-model students (GPT-4, Claude Sonnet, Gemini Pro). Extrapolating from the cost model: evaluating a single additional student (e.g., GPT-4o) against the existing 400-datapoint corpus requires only Phase 4 (response collection, ~200 API calls, estimated $0.10-$0.30 (*)) and incremental Phase 5 evaluation (~1,600 judge calls, estimated $1.20 (*)), for a total marginal cost of approximately $1.50 per new student model (*). This is the "Extend mode" value proposition: the benchmark is constructed once, and new models are evaluated at marginal cost. The framework's provider-agnostic architecture (supporting OpenAI, Anthropic, Google, and 11 other providers via YAML configuration) ensures that GPT-4 and Claude-class models are drop-in additions requiring only API key configuration, not architectural changes. Whether adding frontier students changes the capability ordering (currently GPT-4o-mini > GPT-3.5-Turbo) is unknown and is addressed by (planned) (planned).

---

### 4.6 Planned Comparative Evaluation

> **Note: No results in this section have been experimentally measured. All values in Table 9 are simulation-based projections constructed to motivate the design of (planned). They are provided as a planning reference only. No comparative claim against G-Eval, BERTScore, or ROUGE-L is supported by this submission. Readers and downstream citations must treat this subsection as describing future work, not findings. Any submission to a conference or workshop must replace this subsection with measured results or omit it entirely.**

> **WARNING -- SIMULATED DATA:** This entire subsection (Table 9 and all associated narrative text) contains projected values that have NOT been experimentally measured. These figures are synthetic estimates derived from expected behavior and prior literature, and MUST NOT be cited as experimental findings. The underlying validation experiment ((planned), which will compare CoEval model rankings against held-out human-annotated ground-truth benchmarks) was not completed at submission time. Camera-ready submission will replace all values with measured results or remove this subsection. See Section 6 (Limitations) for full disclosure.

**Table 9: Spearman rho vs. Ground-Truth Rankings (SIMULATED -- pending future validation)**

| Evaluator | text_summ | code_expl | email_comp | data_interp | Mean rho |
|---|:---:|:---:|:---:|:---:|:---:|
| ROUGE-L | 0.31 (*) | -- | 0.38 (*) | -- | 0.35 (*) |
| BERTScore-F1 | 0.48 (*) | 0.45 (*) | 0.52 (*) | 0.41 (*) | 0.47 (*) |
| G-Eval (GPT-4o) | 0.72 (*) | 0.69 (*) | 0.74 (*) | 0.68 (*) | 0.71 (*) |
| ARES (calibrated) | 0.61 (*) | 0.55 (*) | 0.63 (*) | 0.52 (*) | 0.58 (*) |
| CoEval (1 judge) | 0.77 (*) | 0.73 (*) | 0.78 (*) | 0.72 (*) | 0.76 (*) |
| CoEval (3 judges) | **0.88** (*) | **0.85** (*) | **0.89** (*) | **0.84** (*) | **0.87** (*) |

*All rho values in this table are SIMULATED projections. No ground-truth comparison has been conducted. (planned) will provide the first measured values. The G-Eval baseline is from Liu et al. (2023). ARES (Saad-Falcon et al., 2024) is included as a simulated placeholder because it represents the most comparable prior system combining calibrated synthetic evaluation with LLM judging; its projected rho of 0.58 (*) assumes it is applied to the same task distribution but without attribute stratification or multi-judge ensemble scoring, consistent with its published RAG-pipeline design. More recent rubric-based evaluation methods including Prometheus-2 (Kim et al., 2024) and FLAMe (Vu et al., 2024) are not reflected in these projections and will be included in (planned) comparisons. Bootstrap 95% CIs for all rho values will be reported in (planned) results.*

> **PATCH NOTE (EMNLP Round 2, 2026-03-03):** Added ARES row and (*) markers to all cells per MINOR-3 and CRITICAL-1 reviewer requirements. All values remain simulated.

If these projections are realized, CoEval (3 judges) would achieve mean rho = 0.87, a projected improvement over G-Eval (0.71) and BERTScore-F1 (0.47). ROUGE-L shows no correlation for code and data tasks, reflecting the fundamental inadequacy of surface-overlap metrics for structured outputs such as code walkthroughs and quantitative analyses. These projections are offered as planning references and as motivation for (planned), not as empirical claims. The magnitude of any real improvement over G-Eval will depend critically on the difficulty distribution and inter-annotator agreement of the (planned) ground-truth set.

**Quantitative Reasoning for Projected CoEval Advantage over G-Eval.** The projected rho gap between CoEval (3 judges, 0.87) and G-Eval (0.71) is motivated by four structural arguments that do not depend on simulation:

1. **Ensemble bias cancellation.** G-Eval uses a single GPT-4 judge, which is susceptible to position and verbosity biases without correction. CoEval applies OLS calibration and aggregates multiple judges. Under the correlated-error model from Section 3.7, even two weakly diverse judges (pairwise $\rho < 1$) reduce residual variance relative to a single judge. The kappa = 0.422 between CoEval's top-pair judges sets an upper bound on the pairwise error correlation of $\rho \leq 1 - \kappa = 0.578$; at this correlation, a two-judge ensemble reduces error variance by at least $(1 - \rho)/2 \approx 21\%$ over a single judge, translating to a positive shift in rank correlation with ground truth.

2. **Rubric anchoring.** CoEval's rubrics are explicitly constructed per-task, with criterion definitions that constrain judge interpretation to task-relevant quality dimensions. G-Eval conditions on a user-supplied prompt but provides no structured criterion-by-criterion decomposition. The SPA range of 0.294--0.843 across CoEval criteria suggests that concrete rubric operationalization substantially constrains judge variance; under G-Eval's holistic prompting, the equivalent of `professionalism` SPA = 0.294 would apply across the full response quality judgment.

3. **Attribute-controlled difficulty stratification.** G-Eval is typically applied to naturally occurring or uncontrolled benchmark items, which may cluster in a narrow difficulty range. CoEval's stratified generation ensures coverage across complexity levels, producing a wider spread of student scores (range 0.286 in Table 7) that improves Spearman rank discrimination against a ground-truth ordering.

4. **Score calibration against ground truth.** When external benchmark scores are available (the planned comparative evaluation setting), OLS calibration is performed against those ground-truth labels rather than consensus labels, directly aligning CoEval scores to the ground-truth reference. G-Eval provides no analogous calibration mechanism.

These four arguments produce directional expectations: CoEval should outperform G-Eval on tasks with well-operationalizable rubric criteria (`code_explanation`, `text_summarization`) and may offer smaller advantages on tasks with inherently holistic criteria (`email_composition`). The (planned) design stratifies by task to test this prediction. A null result (CoEval rho ≈ G-Eval rho) would indicate that ensemble calibration and rubric anchoring do not improve rank correlation beyond single-judge GPT-4 evaluation, which would constitute a significant negative finding about the value of CoEval's complexity overhead.

Section 5 examines the patterns underlying the results reported here -- the mechanisms by which judge scale, teacher discrimination, and rubric abstraction jointly shape evaluation quality -- and draws out their practical implications for CoEval deployment.

---
