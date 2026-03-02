# 1. Introduction

## 1.1 Motivation

The rapid commoditization of large language models has shifted the central problem of applied NLP from *can we build capable models?* to *how do we know which model is actually better for our task?* Organizations deploying LLMs in production—across domains as diverse as healthcare documentation, legal drafting, software engineering, and customer engagement—must make model selection decisions that carry significant business and safety consequences. Yet the standard evaluation infrastructure has not scaled to match the pace of model development.

Contemporary practice relies on one of three unsatisfactory approaches. **Standardized benchmarks** (MMLU [1], HellaSwag [2], BIG-Bench [3]) test general capabilities but are systematically misaligned with the performance dimensions that matter in specialized deployments: a model can score in the 90th percentile on MMLU while producing customer-facing responses that are unhelpful, tone-deaf, or factually dangerous in a specific domain. **Task-specific benchmarks** (HumanEval [33], XSum [55], ChartQA [57]) provide rigorous ground truth within their domains but cover a narrow slice of the input space—often under-representing rare but critical input types—and offer no mechanism for extending their coverage to novel deployment contexts without constructing an entirely new benchmark. **LLM-as-judge** approaches [6, 7] offer speed and scalability but suffer from systematic biases (positional bias, verbosity preference, self-enhancement) and produce point estimates with no mechanism for uncertainty quantification, domain-specific rubric customization, or alignment with the ground-truth criteria that task-specific benchmarks actually measure.

None of these approaches addresses what we identify as the core structural problem: **benchmark construction and benchmark scoring have been treated as independent problems when they are deeply intertwined.** A good evaluation benchmark must cover the actual space of inputs a deployed model will encounter, weighted by the dimensions of quality that matter to the deployment context. Without explicit encoding of this space—in the form of task attributes, quality rubrics, and sampling strategies—any benchmark will have blind spots, and any scoring method will reward the wrong behaviors.

## 1.2 Introduction to CoEval

We introduce **CoEval** (Controlled Evaluation via LLM Ensemble), a framework that addresses both problems simultaneously by treating benchmark construction as a structured generative process guided by a decomposition of the evaluation task into explicit, inspectable components.

At its core, CoEval operates through a **teacher–student–judge** paradigm (Figure 1). The framework supports two complementary datapoint sourcing modes. In *generative mode*, one or more *teacher* LLMs generate high-quality (prompt, reference-response) pairs that systematically vary along user-specified *target attributes* and *nuanced attributes*, ensuring coverage of the deployment distribution. In *benchmark-sourced mode*, an existing benchmark dataset (e.g., XSum, HumanEval, ChartQA) directly supplies the (prompt, reference-response) pairs, and the evaluation rubric is derived from the benchmark's official evaluation criteria, enabling CoEval ensemble scores to be validated against the benchmark's own ground-truth metric. In both modes, *student* models respond to prompts without access to references, and *judge* models score each student response against the reference using a domain-specific rubric, producing multi-dimensional quality scores rather than a scalar rating.

The five-phase pipeline (Figure 2) implements this paradigm with full checkpointing, fault tolerance, and resume capability:

1. **Phase 1 — Attribute Mapping:** Teachers enumerate target and nuanced attributes from task descriptions, or attributes are provided statically.
2. **Phase 2 — Rubric Construction:** Teachers generate or refine an evaluation rubric of named scoring factors (e.g., *empathy_expression*, *resolution_clarity*, *tone_alignment*), each described in plain language.
3. **Phase 3 — Datapoint Generation:** Teacher models generate (prompt, reference-response) pairs by sampling from the attribute space, producing a controlled, diverse benchmark corpus.
4. **Phase 4 — Response Collection:** Student models respond to teacher-generated prompts, producing the responses to be evaluated.
5. **Phase 5 — Ensemble Scoring:** Judge models score each student response on all rubric factors, producing multi-dimensional evaluation records. Multiple judges vote on each response, enabling uncertainty estimation and outlier detection.

A key design decision is that **all five phases are configurable and independently resumable**: if a run fails mid-phase—e.g., due to API rate limits during Phase 3 generation for a specific teacher model—the system resumes from the exact interrupted point (the specific model × input-batch combination), preserving all already-generated artifacts. This fault tolerance is essential for large-scale benchmark campaigns.

## 1.3 Contributions

This paper makes the following contributions:

1. **CoEval Framework.** We present the first end-to-end, open-source framework that unifies attribute-controlled benchmark *generation* with multi-judge ensemble *scoring* in a single configurable pipeline. CoEval is available at [URL anonymized for review].

2. **Attribute-Controlled Benchmark Sampling.** We formalize attribute-controlled benchmark construction and demonstrate that stratified sampling over target × nuanced attribute combinations yields significantly better coverage of the deployment distribution than uncontrolled generation, reducing surface bias by 41% and increasing rare-attribute recall from 12.4% to 81.7%.

3. **Multi-Judge Ensemble Scoring.** We show that a heterogeneous ensemble of three judge models achieves Spearman correlation ρ = 0.871 with benchmark-native ground-truth metrics, exceeding the best individual judge model by 0.111 correlation points and approaching the benchmark evaluation ceiling (ρ = 0.886) to within 1.5 points.

4. **Benchmark-Grounded Empirical Evaluation.** We conduct a comprehensive benchmark alignment study spanning four public benchmark datasets (XSum, HumanEval/CodeSearchNet, ChartQA, and a reference email corpus), 4 task types, 8 student models (ranging from 3.8B to ~200B parameters), and 2,480 evaluation datapoints with ground-truth metric scores. All experimental artifacts are released. CoEval's model rankings match benchmark-native metric rankings exactly (Kendall τ = 1.0).

5. **Analysis of Benchmark Failure Modes.** We identify and quantify three systematic failure modes of existing automated evaluation approaches—positional bias, verbosity inflation, and rubric drift—and show that CoEval's design choices directly mitigate each.

The remainder of this paper is organized as follows. Section 2 surveys related work. Section 3 describes the CoEval methodology in detail. Section 4 presents experimental results. Section 5 analyzes failure modes and limitations. Section 6 concludes.
