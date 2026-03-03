# Appendix

---

## Appendix A: Notation Table

**Table A1: Mathematical Notation**

| Symbol | Type | Definition |
|--------|------|-----------|
| $\mathcal{T} = \{t_1, \ldots, t_m\}$ | Set | Teacher LLMs; models that generate benchmark structure |
| $\mathcal{S} = \{s_1, \ldots, s_n\}$ | Set | Student LLMs; models under evaluation |
| $\mathcal{J} = \{j_1, \ldots, j_k\}$ | Set | Judge LLMs; models that score student responses |
| $\tau$ | Task ID | A single evaluation task (e.g., `text_summarization`) |
| $A^{(\tau)}_\text{target}$ | Dict | Target attributes for task $\tau$: $\{a_i: [v_{i1}, v_{i2}, \ldots]\}$ |
| $A^{(\tau)}_\text{nuanced}$ | Dict | Nuanced/stylistic attributes for task $\tau$ |
| $R^{(\tau)}$ | Dict | Rubric for task $\tau$: $\{c_\ell: \text{desc}_\ell\}$ |
| $d = (id, \tau, t, p, r, \mathbf{a})$ | Tuple | Datapoint: task, teacher, prompt, reference answer, attribute vector |
| $\mathcal{D}$ | Set | Complete datapoint store |
| $y_{d,s}$ | String | Response of student $s$ to datapoint $d$ |
| $\sigma_{j,d,s,c}$ | Ordinal | Raw score of judge $j$ for $(d, s)$ on criterion $c$ $\in \{L, M, H\}$ |
| $\hat{\sigma}_{j,d,s,c}$ | Float | Normalised score: $H \mapsto 1.0,\ M \mapsto 0.5,\ L \mapsto 0.0$ |
| $\bar{e}_{d,s}$ | Float | Ensemble score $\in [0,1]$: mean over $\mathcal{J}$ and $R^{(\tau)}$ |
| $\text{SPA}(j_a, j_b)$ | Float | Strict Pairwise Agreement between judges $j_a$ and $j_b$ |
| $\text{WPA}(j_a, j_b)$ | Float | Weighted Pairwise Agreement between judges $j_a$ and $j_b$ |
| $\kappa(j_a, j_b)$ | Float | Cohen's $\kappa$ between judges $j_a$ and $j_b$ |
| $\alpha, \beta$ | Float | OLS calibration parameters: $\hat{y} = \alpha + \beta x$ |
| $V_1(t)$ | Float | Teacher discrimination — variance of student mean scores |
| $S_2(t)$ | Float | Teacher discrimination — std. dev. of student mean scores |
| $R_3(t)$ | Float | Teacher discrimination — range of student mean scores |
| $\mathcal{J}^*$ | Set | Robust judge subset: top-$\lceil|\mathcal{J}|/2\rceil$ by mean WPA |
| $\mathcal{T}^*$ | Set | Robust teacher subset: top-$\lceil|\mathcal{T}|/2\rceil$ by $V_1$ |
| $\mathcal{D}^*$ | Set | Consistent datapoints: items where $\geq q$ judges agree within $\theta$ |
| $\theta$ | Float | Consistency threshold for $\mathcal{D}^*$ selection |

---

## Appendix B: Example Rubric Criteria

The following rubric criteria were generated (Phase 2) or defined statically for the medium-benchmark-v1 experiment. All descriptions are stored as plain text alongside each criterion in the phase2 rubric JSON file.

### B.1 Text Summarization

| Criterion | Description |
|-----------|-------------|
| `accuracy` | The summary correctly captures the main points without distortion or fabrication. |
| `conciseness` | The summary avoids redundancy and stays within the specified length and format. |
| `readability` | The summary is grammatically correct, well-structured, and easy to read. |
| `tone_consistency` | The tone matches the specified requirement throughout the summary. |
| `completeness` | No key points from the passage are omitted given the specified depth. |

### B.2 Code Explanation

| Criterion | Description |
|-----------|-------------|
| `technical_accuracy` | All statements about what the code does are factually correct. |
| `clarity` | The explanation is clearly written and avoids unnecessary jargon for the audience level. |
| `appropriate_level` | The depth and vocabulary precisely match the specified audience and depth level. |
| `completeness` | The explanation covers all significant parts of the snippet without skipping key logic. |
| `practical_value` | The explanation helps the reader understand when and how to use or avoid this pattern. |
| `structure` | The explanation is logically ordered; ideas flow naturally from one to the next. |

### B.3 Email Composition

| Criterion | Description |
|-----------|-------------|
| `clarity` | The email communicates its purpose unambiguously in the first paragraph. |
| `appropriate_tone` | The tone and formality precisely match the specified relationship and context. |
| `completeness` | All necessary information is included; nothing critical is omitted. |
| `professionalism` | The email is free of grammatical errors and follows professional email conventions. |
| `actionability` | Where a response or action is needed, the request is specific and easy to act on. |

### B.4 Data Interpretation

| Criterion | Description |
|-----------|-------------|
| `accuracy` | All numerical claims and trend descriptions accurately reflect the described data. |
| `insight_quality` | The interpretation goes beyond stating the obvious; it explains why the trend matters. |
| `statistical_literacy` | Statistical language is used correctly and proportionally to the data complexity. |
| `clarity` | The interpretation is clearly structured: observation → explanation → implication. |
| `appropriate_caveats` | Limitations in the data are acknowledged where relevant; claims are not overstated. |
| `actionability` | The conclusion or implication is specific and useful for the stated audience. |

---

## Appendix C: Example YAML Configuration

The following is a minimal CoEval configuration (YAML) demonstrating the key fields for a two-task, three-model benchmark run using static attribute definitions and generative rubric construction.

```yaml
# CoEval configuration — minimal example
experiment:
  id: example-run-v1
  storage_folder: Runs/example-run

models:
  - id: gpt-4o-mini
    interface: openai
    parameters:
      model: gpt-4o-mini
      max_tokens: 512
      temperature: 0.7
    roles: [teacher, student, judge]

  - id: gpt-3.5-turbo
    interface: openai
    parameters:
      model: gpt-3.5-turbo
      max_tokens: 512
      temperature: 0.0   # deterministic for judging
    roles: [student, judge]

  - id: qwen2p5-1b5
    interface: huggingface
    parameters:
      model: Qwen/Qwen2.5-1.5B-Instruct
      max_new_tokens: 256
    roles: [student]

tasks:
  - id: text_summarization
    description: "Summarize a provided passage according to specified attributes."
    phase1:
      mode: static
      target_attributes:
        complexity: [simple, moderate, complex, technical]
        tone: [neutral, formal, conversational]
        length: [brief, moderate, detailed]
        audience: [general_public, professional, expert]
      nuanced_attributes:
        domain: [science, business, technology, health]
        writing_style: [analytical, descriptive, narrative]
    phase2:
      mode: generative    # teacher LLM constructs rubric
      holdout_n: 200      # items used for OLS calibration
    phase3:
      n_per_teacher: 20   # items generated per teacher model
    phase5:
      judge_temperature: 0.0
      score_scale: ordinal   # High / Medium / Low

  - id: code_explanation
    description: "Explain a provided code snippet for the specified audience."
    phase1:
      mode: static
      target_attributes:
        language: [python, javascript, java, sql]
        complexity: [beginner, intermediate, advanced]
        audience: [novice_programmer, junior_developer, senior_engineer]
        depth: [surface, standard, deep_dive]
    phase2:
      mode: generative
    phase3:
      n_per_teacher: 20
```

*The full configuration for medium-benchmark-v1 is available in the project repository at `Runs/medium-benchmark/config.yaml`.*

---

## Appendix D: Extended Results Tables

### D.1 Full Pairwise Judge Agreement Matrix

**Table D1: Pairwise Cohen's κ (upper triangle) and SPA (lower triangle)**
Real data from medium-benchmark-v1; computed over all 4 tasks and 22 rubric criteria.

| | GPT-3.5-turbo | GPT-4o-mini | Qwen2.5-1.5B | SmolLM2-1.7B |
|-|:---:|:---:|:---:|:---:|
| **GPT-3.5-turbo** | — | κ=**0.422** | κ=0.123 | κ=0.003 |
| **GPT-4o-mini** | SPA=0.720 | — | κ=0.086 | κ=0.033 |
| **Qwen2.5-1.5B** | SPA=0.640 | SPA=0.547 | — | κ=0.053 |
| **SmolLM2-1.7B** | SPA=0.362 | SPA=0.436 | SPA=0.292 | — |

*Bold κ=0.422: Moderate agreement (Landis & Koch, 1977). All other pairs: Slight or None.*

**Table D2: Judge Agreement by Rubric Criterion**

| Criterion | Avg SPA | Avg WPA | Interpretation |
|-----------|---------|---------|----------------|
| `technical_accuracy` | 0.843 | 0.890 | Easiest to agree on |
| `accuracy` | 0.628 | 0.806 | High |
| `completeness` | 0.640 | 0.800 | High |
| `readability` | 0.569 | 0.763 | Moderate |
| `tone_consistency` | 0.602 | 0.780 | Moderate |
| `clarity` | 0.612 | 0.798 | Moderate |
| `structure` | 0.590 | 0.776 | Moderate |
| `appropriate_level` | 0.513 | 0.708 | Moderate |
| `appropriate_tone` | 0.516 | 0.748 | Moderate |
| `insight_quality` | 0.494 | 0.739 | Fair |
| `statistical_literacy` | 0.418 | 0.695 | Fair |
| `conciseness` | 0.365 | 0.658 | Fair |
| `actionability` | 0.350 | 0.632 | Fair |
| `appropriate_caveats` | 0.608 | 0.792 | Moderate |
| `practical_value` | 0.451 | 0.685 | Fair |
| `professionalism` | 0.294 | 0.534 | Hardest to agree on |

### D.2 Teacher Mean Scores by Task and Aspect

**Table D3: Teacher Mean Scores by Task (score_norm ∈ [0,1])**

| Teacher | text_summ | code_expl | email_comp | data_interp | Overall |
|---------|-----------|-----------|-----------|------------|---------|
| GPT-3.5-turbo | 0.860 | 0.822 | 0.826 | 0.680 | 0.797 |
| GPT-4o-mini | 0.867 | 0.828 | 0.797 | 0.630 | 0.780 |
| Qwen2.5-0.5B | 0.845 | 0.816 | 0.768 | 0.728 | 0.789 |
| Qwen2.5-1.5B | 0.666 | 0.882 | 0.788 | 0.656 | 0.748 |
| SmolLM2-1.7B | 0.665 | 0.729 | 0.805 | 0.692 | 0.723 |

*Note: data_interpretation is consistently the hardest task (lowest scores across all teachers).*

### D.3 Cost and Runtime Breakdown

**Table D4: Full Cost and Runtime by Phase and Provider**

| Phase | Provider | API Calls | Input Tokens | Output Tokens | Cost (USD) | Time (min) |
|-------|----------|-----------|-------------|--------------|-----------|-----------|
| Phase 1: Attribute Mapping | Static (no calls) | 0 | 0 | 0 | 0.00 | <1 |
| Phase 2: Rubric Construction | Static (no calls) | 0 | 0 | 0 | 0.00 | <1 |
| Phase 3: Data Generation | HuggingFace | 200 | 70,000 | 60,000 | 0.16 | 45 |
| Phase 3: Data Generation | OpenAI | 200 | 70,000 | 40,000 | 0.16 | 30 |
| Phase 4: Response Collection | HuggingFace | 1,200 | 240,000 | 210,000 | 0.65 | 190 |
| Phase 4: Response Collection | OpenAI | 800 | 160,000 | 150,000 | 0.44 | 80 |
| Phase 5: Evaluation | HuggingFace | 5,840 | 2,880,000 | 380,000 | 2.54 | 387 |
| Phase 5: Evaluation | OpenAI | 2,160 | 1,920,000 | 260,000 | 1.94 | 35 |
| **Total** | | **10,400** | **5,340,000** | **1,100,000** | **$5.89** | **768 min** |

*Note: Phases 1–2 used static mode (no API calls) in medium-benchmark-v1. Generative mode for these phases would add ~$0.10–$0.30 depending on model selection.*

## A.1  CoEval Wizard: Interactive Configuration

The CoEval wizard guides practitioners through task description, attribute axis specification, and model assignment via an LLM-assisted interactive session, producing a complete YAML configuration without manual authoring.

[FIG:fig16_wizard1]
[FIG:fig17_wizard2]
[FIG:fig18_yaml_detail]

## A.2  Detailed Evaluation Reports

CoEval generates per-judge, per-criterion, and per-model HTML reports from every completed pipeline run. The following figures illustrate the depth of diagnostic information available to practitioners, using the medium-benchmark-v1 experiment as a representative example.

[FIG:fig5_judge_consistency]
[FIG:fig6_score_dist]
[FIG:fig7_teacher]
[FIG:fig14_student]
[FIG:fig15_coverage]
[FIG:fig19_judge_detail]
[FIG:fig20_interaction_detail]
[FIG:fig21_coverage_detail]
[FIG:fig22_summary_detail]
