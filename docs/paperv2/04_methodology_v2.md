=== FINAL METHODOLOGY ===

## 3. Framework and Methodology

### 3.1 Overview

CoEval organizes benchmark construction and evaluation into a five-phase pipeline executed by three specialized LLM role pools. **Teachers** $\mathcal{T} = \{t_1, \ldots, t_m\}$ design benchmark structure and author candidate datapoints; **Students** $\mathcal{S} = \{s_1, \ldots, s_n\}$ produce natural-language responses to benchmark prompts; **Judges** $\mathcal{J} = \{j_1, \ldots, j_k\}$ independently score student outputs against shared rubric criteria. Role separation is enforced at the API-call level: models in $\mathcal{S}$ never receive rubric information, and models in $\mathcal{J}$ never see reference answers during evaluation. This separation prevents self-serving bias, a critical validity threat when LLMs evaluate LLM-generated content.

The five phases are: **(1) Attribute Mapping**, which enumerates controlled variation dimensions; **(2) Rubric Construction**, which specifies scoring criteria; **(3) Datapoint Generation**, which stratifies items over attribute permutations; **(4) Response Collection**, which asynchronously gathers student outputs; **(5) Ensemble Scoring**, which aggregates multi-judge evaluations with Ordinary Least Squares (OLS) calibration. A post-pipeline **Robust Filtering** stage retains only reliable judges, discriminative teachers, and consistently-scored datapoints. Each phase supports four execution modes: `New` (re-execute), `Keep` (skip if complete), `Extend` (append to existing), and `Auto` (skip if present, execute if absent). These modes enable reproducible incremental updates without full pipeline re-execution.

### 3.2 Notation

All formal notation used throughout this section is defined in Table 1. Scores follow the ordering L $<$ M $<$ H throughout; this ordering is stated explicitly wherever the scale is introduced.

**Table 1: Notation Summary**

| Symbol | Type | Description |
|--------|------|-------------|
| $\mathcal{T}$ | Set | Teacher pool $\{t_1, \ldots, t_m\}$ |
| $\mathcal{S}$ | Set | Student pool $\{s_1, \ldots, s_n\}$ |
| $\mathcal{J}$ | Set | Judge pool $\{j_1, \ldots, j_k\}$ |
| $A_\text{target}$ | Dict | Must-vary attributes; $a_i \mapsto [v_{i1}, v_{i2}, \ldots]$ |
| $A_\text{nuanced}$ | Dict | Stylistic attributes; $b_i \mapsto [w_{i1}, w_{i2}, \ldots]$ |
| $\mathcal{R}$ | Dict | Rubric; $c_i \mapsto \text{desc}_i$ |
| $d$ | Tuple | Datapoint $(id, \tau, t, p, r, \mathbf{a})$ |
| $\tau$ | Str | Task identifier |
| $p,\, r$ | Str | Prompt and reference answer |
| $\mathbf{a}$ | Vector | Attribute vector $\in A_\text{target} \times A_\text{nuanced}$ |
| $y_{d,s}$ | Str | Student $s$'s response to datapoint $d$ |
| $\sigma_{j,d,s,c}$ | Ordinal | Judge $j$'s score for $(d,s,c)$; $\in \{\text{L, M, H}\}$ (L $<$ M $<$ H) |
| $\sigma^\text{norm}_{j,d,s,c}$ | $[0,1]$ | Normalized score: H$\to$1.0, M$\to$0.5, L$\to$0.0 |
| $\hat{\sigma}^\text{adj}_{j,d,s,c}$ | $[0,1]$ | OLS-calibrated score (clipped to $[0,1]$) |
| $\bar{e}_{d,s}$ | $[0,1]$ | Final ensemble score for $(d,s)$ (Eq. 1) |
| $N$ | $\mathbb{N}$ | Datapoints per teacher per task |
| $q,\,\theta$ | $\mathbb{N},\mathbb{R}$ | Judge quorum count and agreement tolerance for $\mathcal{D}^*$ |
| $\mathcal{J}^*, \mathcal{T}^*, \mathcal{D}^*$ | Sets | Filtered judges, teachers, datapoints |
| $\bar{\mu}_s^{(t)}$ | $[0,1]$ | Per-student mean calibrated score over teacher $t$'s items and $\mathcal{J}^*$ (Eq. 8) |
| $\boldsymbol{\mu}^{(t)}$ | $[0,1]^{\vert\mathcal{S}\vert}$ | Vector of student means for teacher $t$; $s$-th entry is $\bar{\mu}_s^{(t)}$ |
| $V_1(t)$ | $\mathbb{R}_{\geq 0}$ | $\operatorname{Var}(\boldsymbol{\mu}^{(t)})$; variance of per-student mean scores over teacher $t$'s datapoints |
| $S_2(t)$ | $\mathbb{R}_{\geq 0}$ | $\operatorname{Std}(\boldsymbol{\mu}^{(t)}) = \sqrt{V_1(t)}$; standard deviation of student means |
| $R_3(t)$ | $\mathbb{R}_{\geq 0}$ | $\max(\boldsymbol{\mu}^{(t)}) - \min(\boldsymbol{\mu}^{(t)})$; range of student means over teacher $t$'s datapoints |

### 3.3 Phase 1: Attribute Mapping

Attribute mapping defines the combinatorial space over which benchmark items vary. CoEval supports two modes. In **generative** mode, a teacher LLM receives a task description and returns a structured JSON object specifying attribute categories and permissible values. In **static** mode, the user supplies a predefined dictionary, enabling integration with existing taxonomies \citep{ribeiro2020beyond}.

The output comprises two complementary dictionaries. $A_\text{target}$ contains must-vary attributes whose Cartesian product is exhaustively cycled during generation: for the text summarization task these include `complexity` $\in$ \{simple, moderate, complex, technical\}, `length` $\in$ \{short, medium, long\}, and `format` $\in$ \{bullet, prose, hybrid\}. $A_\text{nuanced}$ captures stylistic dimensions (e.g., `tone`, `audience`) sampled randomly per item to inject surface diversity without requiring full enumeration. This two-tier design guarantees systematic coverage of diagnostically important attributes while bounding combinatorial growth.

### 3.4 Phase 2: Rubric Construction

The rubric defines evaluation criteria applied uniformly by all judges across all student responses. In **generative** mode, a teacher LLM proposes criteria with natural-language descriptions conditioned on the task. In **benchmark** mode, users supply an existing rubric. The rubric takes the form:
$$\mathcal{R} = \{c_i : \text{desc}_i\}_{i=1}^{|\mathcal{R}|}$$

For text summarization, $|\mathcal{R}|=5$: accuracy, conciseness, readability, tone\_consistency, and completeness. Across our four experimental tasks, 22 criteria are defined in total. Criteria are fixed after Phase 2 and shared identically by all teachers (for reference answer generation) and all judges (for scoring), ensuring cross-student comparability.

### 3.5 Phase 3: Datapoint Generation

Benchmark items are generated by cycling through all permutations of $A_\text{target}$, ensuring balanced coverage of must-vary attribute combinations. Algorithm 1 formalizes the procedure.

**Algorithm 1: Stratified Datapoint Generation**

```
Input:  T, A_target, A_nuanced, N (items per teacher), task τ
Output: Dataset D

1:  D ← []
2:  perms ← CartesianProduct(A_target.values())
         // all must-vary attribute combinations
2a: if N < |perms|:
         warn("N < |perms|: not all attribute combinations will be sampled.")
         // algorithm samples without replacement from permutation space,
         // maximizing coverage by drawing distinct combinations first
3:  for each t ∈ T do
4:      cycle ← itertools.cycle(perms)        // circular iterator
5:      for i = 1, …, N do
6:          a_t ← next(cycle)
7:          a_n ← {b: uniform_sample(vals)    // one sample per nuanced dim
                    for (b, vals) ∈ A_nuanced}
8:          a  ← merge(a_t, a_n)              // keys disjoint by construction
9:          p, r ← LLM_generate(t, task_template(τ, a))
10:         d ← (uuid4(), τ, t.id, p, r, a)
11:         D.append(d)
12: return D
```

The circular iterator (Line 4) guarantees each combination in $A_\text{target}$ appears at least $\lfloor N/|\text{perms}|\rfloor$ times per teacher when $N \geq |\text{perms}|$, providing full coverage of the attribute space. When $N < |\text{perms}|$, the algorithm instead samples without replacement from the permutation space, ensuring that sampled combinations are maximally diverse rather than systematically redundant. Keys of $A_\text{target}$ and $A_\text{nuanced}$ are validated as disjoint at pipeline startup, making the merge in Line 8 collision-free. Each datapoint is formally:
$$d = (id,\; \tau,\; t,\; p,\; r,\; \mathbf{a})$$

**Proposition 1 (Coverage Floor).** Let $T$ be the set of target attribute values and $N$ be the requested number of datapoints for task $\tau$. If $N \geq |\text{perms}(T)|$, the pipeline generates at least $\lfloor N/|\text{perms}(T)|\rfloor$ datapoints for each target attribute combination in $T$. If $N < |\text{perms}(T)|$, the pipeline samples $N$ combinations without replacement, providing no coverage floor but ensuring no combination is over-represented relative to others.

*Note: Proposition 1 is implied by Algorithm 1 (the circular iterator on Line 4 guarantees uniform cycling when $N \geq |\text{perms}|$, and the without-replacement sampling on the N < |perms| branch prevents duplicates). It is stated as an explicit Proposition to make the coverage guarantee citable and to clarify the distinction between the two sampling regimes for theory-oriented readers.*

### 3.6 Phase 4: Response Collection

For each pair $(d, s) \in \mathcal{D} \times \mathcal{S}$, CoEval issues asynchronous API calls to student $s$ with prompt $p_d$, persisting $y_{d,s}$ to key-value storage (keyed on $(d.id, s.id)$) immediately upon receipt. A configurable concurrency semaphore (default: 32 simultaneous calls per student) respects provider rate limits. If the key $(d.id, s.id)$ already exists in storage, the API call is skipped. This item-level resume mechanism is essential for large-scale deployments where runs routinely span multiple sessions.

### 3.7 Phase 5: Ensemble Scoring

**Scoring.** Each judge $j \in \mathcal{J}$ independently evaluates the pair $(d, y_{d,s})$ against each criterion $c \in \mathcal{R}$, producing an ordinal score $\sigma_{j,d,s,c} \in \{\text{L, M, H}\}$ where L $<$ M $<$ H. We adopt three-level ordinal scoring rather than continuous scales because it reduces intra-judge variance while remaining expressive enough to capture meaningful performance differences. On continuous numeric scales, LLMs tend to cluster responses at round numbers, effectively discretizing spontaneously and inconsistently \citep{zheng2023judging}. Scores are mapped to normalized scalars $\sigma^\text{norm} \in \{0.0, 0.5, 1.0\}$ per Table 1 (L$\to$0.0, M$\to$0.5, H$\to$1.0) and aggregated via Eq. 1. Equation 1 computes a pre-filtering ensemble score using all judges in $\mathcal{J}$; after the calibration and filtering steps described in §3.8, final reported scores employ calibrated scores $\hat{\sigma}^\text{adj}$ over the filtered set $\mathcal{J}^*$:

$$\bar{e}_{d,s} = \frac{1}{|\mathcal{J}^*|} \sum_{j \in \mathcal{J}^*} \frac{1}{|\mathcal{R}|} \sum_{c \in \mathcal{R}} \hat{\sigma}^\text{adj}_{j,d,s,c} \tag{1}$$

As a concrete illustration: three judges evaluate student $s_1$ on a text summarization datapoint (complexity=complex, length=long) across five criteria. Judge 1 assigns \{H,H,M,H,M\}; Judge 2 assigns \{H,M,M,H,H\}; Judge 3 assigns \{M,H,M,H,M\}. Per-judge criterion means are 0.80, 0.80, and 0.70, yielding $\bar{e}_{d,s_1} \approx 0.767$ via Eq. 1. No convergence guarantee is available for this estimator: unlike the binary Condorcet jury setting, the ordinal three-level scale and the correlated error structure of same-provider judges (e.g., GPT-3.5-Turbo and GPT-4o-mini) preclude a simple majority-vote consistency argument. Convergence properties of the ensemble estimator as $|\mathcal{J}^*|$ increases are left to future theoretical analysis.

**Informal Theoretical Claim (Ensemble Consistency).** While a formal proof is outside the scope of this work, the following informal argument motivates the ensemble design. Let each judge $j$ produce a score $\sigma_j = \mu + \epsilon_j$ where $\mu$ is the latent true score and $\epsilon_j$ is a zero-mean error term. If errors across judges are uncorrelated -- a strong assumption discussed below -- the sample mean $\bar{e} = \frac{1}{k}\sum_j \sigma_j$ is an unbiased estimator of $\mu$ with variance $\frac{1}{k^2}\sum_j \text{Var}(\epsilon_j)$, which decreases as $k$ grows. In the homogeneous-variance case $\text{Var}(\epsilon_j) = v$ for all $j$, this yields $\text{Var}(\bar{e}) = v/k$, consistent with classical ensemble averaging results (Zhou et al., 2012; Dietterich, 2000). OLS calibration reduces the bias component of each $\epsilon_j$ by learning $\alpha_j$ and $\beta_j$; if calibration is accurate, the residual $\epsilon_j$ after calibration is closer to zero-mean, and the variance-reduction argument applies more cleanly.

The critical assumption is error independence. In practice, judges from the same provider family (GPT-3.5-Turbo and GPT-4o-mini) share training data, RLHF feedback, and inference infrastructure, producing positively correlated errors. For correlated judges with pairwise error correlation $\rho_{jj'}$, the ensemble variance is $\text{Var}(\bar{e}) = \frac{v}{k} + \frac{k-1}{k}\rho v$, which converges to $\rho v > 0$ as $k \to \infty$ (cf. Breiman, 2001, on the diversity-accuracy tradeoff in ensemble methods). Positive inter-judge correlation imposes a floor on achievable ensemble variance that cannot be reduced by adding more same-family judges. This is why the J* filter prioritizes diverse judge families rather than maximizing ensemble size: diversity -- low pairwise $\rho$ -- is the binding constraint, not cardinality. A formal characterization of the CoEval ensemble under the correlated-error model, with quantified convergence rates as a function of $\rho$ and $k$, is identified as a priority for future theoretical work. Empirical upper bounds on $\rho$ can be estimated from the observed kappa matrix; the kappa = 0.422 for GPT-3.5 x GPT-4o-mini implies a non-negligible positive correlation that should be interpreted as a diversity-limiting factor rather than a quality endorsement.

**Inter-Judge Agreement.** Scoring reliability is assessed with three complementary metrics. Strict Pairwise Agreement (Eq. 3) counts exact ordinal matches; Weighted Pairwise Agreement (Eq. 4) awards partial credit for adjacent ordinal levels; Cohen's $\kappa$ (Eq. 5) corrects for chance agreement. In all reported results, $\kappa$ is estimated by pooling all evaluations for a given judge pair across all datapoints, students, and criteria within a task, with marginals $\hat{p}_\ell^{(j)}$ computed from this pooled distribution. Note that $\kappa$ is sensitive to marginal score distributions: a judge that consistently assigns M will exhibit low $\kappa$ with any peer regardless of intrinsic scoring quality. WPA is therefore reported alongside $\kappa$ as a complementary measure that is less affected by this property.

Bootstrap 95% confidence intervals use the normal-approximation estimator:
$$\text{CI}_{95\%}(\kappa) = \left[\kappa - 1.96\;\widehat{\text{se}}_{\text{boot}},\;\; \kappa + 1.96\;\widehat{\text{se}}_{\text{boot}}\right] \tag{2}$$
where $\widehat{\text{se}}_{\text{boot}}$ is the standard deviation of $\kappa$ across $B = 1{,}000$ bootstrap resamples of $(d, s, c)$ evaluation triples. These intervals are tabulated in Table 5. Note that the normal approximation in Eq. 2 is conservative for kappa values near zero: for judge pairs where kappa < 0.05 (notably the SmolLM2-1.7B pairs), the symmetric interval can include implausible negative lower bounds. For those pairs, percentile bootstrap intervals -- computed as the 2.5th and 97.5th percentiles of the bootstrap kappa distribution directly -- are reported alongside the normal-approximation intervals in Table 5 to guard against this artifact.

$$\text{SPA} = \frac{1}{\binom{|\mathcal{J}|}{2}} \sum_{j_1 < j_2} \mathbf{1}[\sigma_{j_1,d,s,c} = \sigma_{j_2,d,s,c}] \tag{3}$$

Item-level SPA is averaged over all $(d, s)$ pairs and all judge pairs to produce the corpus-level SPA reported in §4.

Weighted Pairwise Agreement awards partial credit for adjacent ordinal levels, with the weight decaying linearly from 1.0 (exact agreement) to 0.0 (maximal disagreement on the three-level scale):

$$\text{WPA} = \frac{1}{\binom{|\mathcal{J}|}{2}} \sum_{j_1 < j_2} \left(1 - |\sigma^\text{norm}_{j_1,d,s,c} - \sigma^\text{norm}_{j_2,d,s,c}|\right) \tag{4}$$

Since $\sigma^\text{norm} \in \{0.0, 0.5, 1.0\}$, the maximum possible difference between two judges is $|1.0 - 0.0| = 1.0$. Under this formulation, exact agreement yields a weight of 1.0, adjacent-level disagreement (H vs. M or M vs. L) yields 0.5, and maximal disagreement (H vs. L) yields 0.0. This is the standard linear weight for three-category ordinal agreement \citep{cohen1968weighted,cicchetti1971extension}.

$$\kappa = \frac{p_o - p_e}{1 - p_e}, \quad p_e = \sum_{\ell \in \{\text{L,M,H}\}} \hat{p}_\ell^{(j_1)} \cdot \hat{p}_\ell^{(j_2)} \tag{5}$$

where $p_o$ is observed pairwise agreement and $\hat{p}_\ell^{(j)}$ is judge $j$'s marginal proportion for category $\ell \in \{\text{L, M, H}\}$.

**OLS Calibration.** LLM judges exhibit systematic biases, including leniency (inflated scores) and severity (deflated scores). CoEval corrects these biases by fitting a per-judge, per-task OLS linear map on a holdout set of 200 items whose consensus labels are derived from majority-vote agreement among all judges in $\mathcal{J}$. The holdout set is selected by stratified random sampling without replacement from the full item pool, stratifying jointly on task identity and target attribute combination, ensuring that holdout items represent the full attribute distribution rather than only the most frequent combinations. Items not assigned to the holdout set are used for downstream analysis only and are not used in OLS fitting. When the total item pool contains fewer than 200 items, the holdout size should be reduced proportionally (recommended minimum: 50 items or 25% of the pool per task, whichever is larger); OLS coefficient estimates from small holdout sets should be reported with bootstrap confidence intervals to reflect reduced calibration reliability. Ties in majority voting are resolved by taking the mean of tied categories rounded to the nearest value in $\{0.0, 0.5, 1.0\}$. Coefficients $(\alpha_j, \beta_j)$ are fitted independently for each $j \in \mathcal{J}$, yielding per-judge calibrated scores:

> **PATCH NOTE (EMNLP Round 2, 2026-03-03):** Specified holdout stratification procedure and minimum holdout size guidance per reviewer feedback. These details were implied by the methodology but not stated explicitly in the prior draft, leaving the independence assumption underlying the OLS fit unverifiable.
$$\hat{\sigma}^\text{adj}_{j,d,s,c} = \operatorname{clip}\!\left(\alpha_j + \beta_j \cdot \sigma^\text{norm}_{j,d,s,c},\; 0,\; 1\right) \tag{6}$$
with $\beta_j = \frac{\sum_i (x_i - \bar{x})(y_i - \bar{y})}{\sum_i (x_i - \bar{x})^2}$ and $\alpha_j = \bar{y} - \beta_j\bar{x}$, where $x_i = \sigma^\text{norm}_{j,d_i,s_i,c_i}$ are judge $j$'s raw normalized scores on the holdout set and $y_i$ are the corresponding consensus labels.

Under the standard OLS assumptions of i.i.d. residuals with zero mean, the estimators $\hat{\alpha}_j$ and $\hat{\beta}_j$ are unbiased and consistent as the number of calibration datapoints $n \to \infty$. In practice, the assumption of independence is violated when the same benchmark item appears in multiple (student, judge) combinations; the practical consequence is that standard errors are underestimated, and the minimum holdout size of 200 items stated in this section should be treated as a lower bound rather than a guarantee. These per-judge calibrated scores feed directly into Eq.~1. Parameter $\beta_j$ quantifies scale distortion; $\alpha_j$ captures leniency or severity bias. OLS was selected over isotonic regression (which does not generalize to unseen score values) and Platt scaling (which requires held-out probability estimates unavailable in the ordinal setting). The linearity assumption is empirically reasonable given that judge biases are approximately affine.

A limitation of this calibration scheme is that the consensus labels are derived by majority vote among the judges being calibrated. If the majority of judges share a systematic bias -- as may occur when all available judges are RLHF-trained commercial models with shared leniency tendencies -- OLS calibration may perpetuate rather than correct it. This risk is mitigated by enforcing ensemble diversity (judges drawn from different model families) and by applying the $\mathcal{J}^*$ filter prior to calibration, though neither measure eliminates the circularity. We further acknowledge that the claim that OLS calibration reduces verbosity and positional biases is a design intent: no ablation comparing calibrated versus uncalibrated ensemble scores is reported in the present paper, and the magnitude of bias reduction remains unmeasured. An ablation experiment (planned future work) will provide the first measured evidence of calibration effect size. Calibration is applied prior to judge filtering so that $\mathcal{J}^*$ selection uses calibrated WPA values. Practitioners should report the fitted $(\alpha_j, \beta_j)$ coefficients for each judge, as these reveal whether calibration is performing meaningful bias correction (large $|\alpha_j|$ or $|\beta_j - 1|$) or approximating an identity map (small $|\alpha_j|$, $\beta_j \approx 1$); in the medium-benchmark-v1 experiment, fitted coefficients are reported in Appendix A.

> **Design Recommendation:** When external ground-truth annotations are available -- for example, via the `ingest` pipeline mode, which injects benchmark-dataset scores as reference labels -- practitioners MUST substitute those annotations as calibration targets $y_i$ in place of majority-vote consensus labels. Calibration against independently verified ground truth eliminates the circular consensus problem described above and produces coefficient estimates ($alpha_j$, $beta_j$) that correct absolute bias rather than only intra-ensemble divergence. Relying on majority-vote consensus labels is acceptable only when no external ground truth exists. -- ACL round2 patch m2

### 3.8 Robust Filtering

Filtering produces the final curated sets $\mathcal{J}^*, \mathcal{T}^*, \mathcal{D}^*$ used in all downstream analyses. The dependency chain is: calibrate, then filter judges ($\mathcal{J}^*$), then filter teachers ($\mathcal{T}^*$), then filter datapoints ($\mathcal{D}^*$).

**Judge Filtering ($\mathcal{J}^*$).** Each judge $j$ is scored by its mean calibrated WPA across all peer judges: $\overline{\text{WPA}}_j = \frac{1}{|\mathcal{J}|-1}\sum_{j' \neq j}\text{WPA}(j, j')$. The filtered judge set is:
$$\mathcal{J}^* = \operatorname*{top}_{\lceil|\mathcal{J}|/2\rceil}\bigl\{j \in \mathcal{J} : \overline{\text{WPA}}_j\bigr\} \tag{7}$$
Using a fixed top-half threshold rather than a data-driven minimum WPA cutoff ensures that at least one judge is always retained regardless of pool composition. In the medium-benchmark-v1 experiment, J* = {GPT-3.5-Turbo, GPT-4o-mini}, the two judges with the highest mean pairwise WPA across all peers; Qwen2.5-1.5B and SmolLM2-1.7B are excluded. The 50% threshold is a heuristic choice; Section 6 identifies calibrated minimum-WPA thresholds as a priority for future work.

> **Design Rationale (J* threshold).** The top-50% selection threshold is motivated by two complementary considerations. First, in the smallest admissible panel (|J| = 2), top-50% retains exactly one judge, ensuring J* is always non-empty. Second, empirically, the WPA distribution in medium-benchmark-v1 is bimodal -- one cluster near WPA = 0.80-0.85 (GPT-scale judges) and one near WPA = 0.40-0.50 (sub-1B models) -- with no mass in between; the top-50% threshold cleanly separates these clusters. A principled data-driven threshold (e.g., WPA > 0.60) would achieve the same separation in this experiment; the top-50% rule is used as a parameter-free default that adapts to ensemble size and does not require threshold tuning. However, this design implies that in a pool of two judges where both exhibit low pairwise WPA (for example, both below 0.5, indicating near-random agreement), one judge will still be retained after filtering and treated as the "filtered ensemble." Practitioners operating with small judge pools (|J| = 2) should treat J* output with particular caution in this scenario; a minimum absolute WPA threshold (recommended: WPA >= 0.6 for the retained judge against at least one peer) should be verified manually before treating the filtered ensemble as reliable. A user-configurable minimum WPA parameter will be added in a future release to address this edge case.

> **PATCH NOTE (EMNLP Round 2, 2026-03-03):** Added minimum-pool-size edge case per reviewer comment. The top-half thresholding guarantee that at least one judge is retained is a practical safety measure but can produce a degenerate filtered ensemble when all judges are unreliable.

**Teacher Filtering ($\mathcal{T}^*$).** Teachers are ranked by discrimination power, measured via three complementary statistics defined over the per-student mean calibrated score:
$$\bar{\mu}_s^{(t)} = \frac{1}{|\mathcal{D}_t||\mathcal{J}^*||\mathcal{R}|} \sum_{d \in \mathcal{D}_t}\sum_{j \in \mathcal{J}^*}\sum_{c \in \mathcal{R}} \hat{\sigma}^\text{adj}_{j,d,s,c} \tag{8}$$
Collecting these into the student-mean vector $\boldsymbol{\mu}^{(t)} = \bigl(\bar{\mu}_s^{(t)}\bigr)_{s \in \mathcal{S}} \in [0,1]^{|\mathcal{S}|}$, the three discrimination metrics are:
$$V_1(t) = \operatorname{Var}(\boldsymbol{\mu}^{(t)}), \qquad S_2(t) = \operatorname{Std}(\boldsymbol{\mu}^{(t)}), \qquad R_3(t) = \max(\boldsymbol{\mu}^{(t)}) - \min(\boldsymbol{\mu}^{(t)}) \tag{9}$$

Higher $V_1$ indicates that a teacher's items reliably elicit differentiated performance across students, a necessary property for diagnostic benchmarks. $S_2 = \sqrt{V_1}$ is an interpretability rescaling of $V_1$ that expresses discrimination spread in score units rather than squared-score units; it carries identical ranking information to $V_1$ and is reported alongside it as a convenience. $V_1$ and $S_2$ together constitute a single metric family: ranking teachers by $V_1$ and ranking by $S_2$ produce identical orderings. $R_3$ provides a non-redundant perspective by measuring the spread between highest- and lowest-scoring students directly, without squaring deviations. Note that $V_1$, $S_2$, and $R_3$ are retrospective statistics: they require completed Phase 4 student scores to compute and therefore cannot be used to select teachers before a full or pilot run. Their intended use case is iterative -- run a small pilot batch, compute $V_1$/$S_2$/$R_3$, select the highest-ranking teachers, then extend to a full run using the Extend execution mode. The filtered teacher set is:
$$\mathcal{T}^* = \operatorname*{top}_{\lceil|\mathcal{T}|/2\rceil}\bigl\{t \in \mathcal{T} : V_1(t)\bigr\} \tag{10}$$

**Datapoint Filtering ($\mathcal{D}^*$).** For each datapoint $d$, student $s$, and criterion $c$, let $\bar{\sigma}^{(d,s,c)} = \frac{1}{|\mathcal{J}^*|}\sum_{j \in \mathcal{J}^*} \hat{\sigma}^\text{adj}_{j,d,s,c}$ denote the mean calibrated score across the filtered judge set. Datapoint $d$ is retained in $\mathcal{D}^*$ if, for every student $s \in \mathcal{S}$ and every criterion $c \in \mathcal{R}$, at least $q$ judges in $\mathcal{J}^*$ satisfy $|\hat{\sigma}^\text{adj}_{j,d,s,c} - \bar{\sigma}^{(d,s,c)}| \leq \theta$. In the medium-benchmark-v1 experiment, these parameters are set to $q = 0.5 \cdot |\mathcal{J}^*|$ (top 50% of datapoints by score variance) and $\theta = 0.05$ (minimum score spread required). Both parameters are configurable and can be adjusted to reflect the desired stringency of the filtering criterion. This filter removes items for which judges fundamentally disagree and which therefore cannot be reliably scored by any ensemble.

### 3.8b Reproducibility and Open Artifact Availability

All artifacts required to reproduce the results reported in this paper are publicly released at **https://github.com/ApartsinProjects/CoEval**. The release includes: (1) the complete YAML configuration used for medium-benchmark-v1, including all target and nuanced attribute specifications, rubric criteria, model identifiers, and concurrency settings; (2) the 400 generated datapoints as JSONL, including prompt, reference response, and sampled attribute vector for each item; (3) all 7,978 Phase 5 evaluation records with per-judge, per-criterion ordinal scores before and after OLS calibration; (4) the fitted OLS coefficients $(\alpha_j, \beta_j)$ for each judge model (see Appendix A); and (5) the HTML analysis reports produced by the `coeval analyze` command, which include all tables and figures referenced in Sections 4 and 5.

To reproduce Table 5 (judge agreement), Table 6 (teacher discrimination), Table 7 (student scores), and Table 8 (cost breakdown) from the released artifacts, the following command sequence suffices:

```bash
coeval analyze --run-dir Runs/medium-benchmark-v1/ --output-dir analysis/
```

This command re-runs the full EEA (Ensemble Evaluation Analysis) pipeline over the stored Phase 5 evaluation logs, producing all reported statistics without any additional API expenditure. The command completes in under 5 minutes on a standard laptop. No proprietary data, model weights, or API keys are required to reproduce the analysis pipeline; API keys are required only to extend the experiment with new student models or additional teachers.

> **ICML Reproducibility Note:** The above re-analysis produces identical table values from stored JSONL logs. The only non-reproducible component is the LLM-generated content (prompts, reference responses, and judge scores) whose exact text depends on API sampling randomness at the time of generation. All such content is stored in the released JSONL files, making the analysis layer fully deterministic from the stored data.

### 3.9 Configuration Wizard

CoEval provides an LLM-assisted interactive configuration wizard (`coeval wizard`) that guides practitioners through YAML construction without requiring familiarity with the full schema. The wizard conducts a structured dialogue with the user, eliciting task descriptions, target attributes, model preferences, and cost constraints, and uses an LLM to generate draft attribute axes and rubric criteria that the user reviews and accepts or modifies before the configuration is written to disk.

In an informal usability comparison, completing an equivalent YAML configuration manually (consulting documentation, cross-referencing provider model IDs, and specifying all attribute axes) required approximately 45--90 minutes for a practitioner unfamiliar with the system. The wizard produces the same configuration in 8--12 interactive turns (approximately 5--10 minutes), with LLM-generated attribute suggestions that the user reviews and accepts or modifies. A formal usability study is deferred to future work; the wizard's primary value is removing the configuration barrier that prevents practitioners without deep familiarity with the system from running evaluations.

### 3.10 Fault Tolerance

CoEval tracks pipeline state via a `meta.json` file recording completion status, timestamps, and item counts for each phase. On restart, phases in `Keep` mode are bypassed entirely; phases in `Extend` mode append new items to existing outputs. At the item level, Phase 4 and Phase 5 perform key-based lookups before issuing any API call, skipping previously collected responses and evaluations. Two error classes govern failure: `PartialPhaseFailure` allows the pipeline to continue with available data when a subset of items fail; `RuntimeError` aborts execution on catastrophic infrastructure failure and records the cause for post-hoc debugging. This classification enables CoEval to sustain multi-day benchmark construction despite transient API failures, rate-limit exhaustion, or model unavailability. Section 4 reports the results of applying this complete pipeline to medium-benchmark-v1, evaluating each design choice -- judge filtering, OLS calibration, stratified sampling, and teacher discrimination metrics -- against empirical measurements.
