# 2. Literature Review

## 2.1 LLM Evaluation Paradigms

The evaluation of language model outputs has evolved through three distinct paradigms over the past decade. Early neural language models were evaluated almost exclusively through automatic reference-based metrics—BLEU [8], ROUGE [9], METEOR [10]—designed for tasks with well-defined gold-standard outputs such as machine translation and summarization. The limitations of these metrics for open-ended generation have been extensively documented [11, 12]: they reward lexical overlap rather than semantic quality, fail to credit valid paraphrases, and correlate poorly with human judgment for tasks requiring coherence, helpfulness, or factual grounding.

The second paradigm replaced lexical metrics with *model-based* metrics trained to predict human scores. BERTScore [13] uses contextual embeddings to compute soft token alignment between hypotheses and references, achieving substantially higher human correlations on summarization and dialogue tasks. BLEURT [14] and COMET [15] extend this approach with task-specific fine-tuning on human rating data, reaching near-human inter-annotator agreement on constrained generation tasks. However, these models require large quantities of labeled preference data to train, and their performance degrades sharply when deployed on domains or tasks outside their training distribution [16]—precisely the setting most relevant to specialized LLM deployments.

The third and current paradigm uses LLMs themselves as evaluators, exploiting their instruction-following capabilities to assess open-ended generation quality according to arbitrary criteria expressed in natural language [6, 7, 17, 18]. This approach is fast, cheap, and domain-generalizable, but has been shown to suffer from systematic biases that make the resulting scores unreliable in isolation.

## 2.2 LLM-as-Judge Approaches

The LLM-as-judge paradigm was popularized by MT-Bench [6] and Chatbot Arena [19], which demonstrated that GPT-4 judgments correlate well with human preferences on multi-turn instruction-following tasks (Spearman ρ ≈ 0.80–0.85 on the MT-Bench evaluation suite). These findings have been widely replicated and extended to code generation [20], factual question answering [21], and medical report summarization [22].

Despite these successes, the LLM-as-judge approach has well-documented failure modes. **Positional bias** refers to the tendency of judge models to prefer responses that appear first in pairwise comparison prompts, regardless of quality [6, 23]. Mitigations include position-swapped ensemble evaluation [6], but this doubles the cost and does not eliminate the bias. **Verbosity preference** describes the systematic over-rating of longer responses [24], a bias that has been observed consistently across judge models including GPT-4, Claude, and Gemini. **Self-enhancement bias** is the tendency of a model to rate its own outputs higher than those of competing models [25], which introduces conflicts of interest when a model serves simultaneously as a generator and a judge. **Sycophancy** [26] leads judge models to shift their ratings toward answers that match their own prior beliefs, regardless of actual quality.

Several works have proposed ensemble strategies to mitigate individual judge biases. LLM-Blender [27] aggregates pairwise comparisons from multiple judges using a Borda count mechanism, improving rank stability. PandaLM [28] fine-tunes a dedicated judge model on human preference data to reduce self-enhancement. FLAMe [29] constructs a multi-task judge model trained on 100+ human feedback datasets, achieving strong generalization across diverse evaluation dimensions. CoEval complements these approaches: rather than fine-tuning a single better judge, we deploy a heterogeneous ensemble of existing models, which we show is sufficient to achieve near-human reliability without additional training.

## 2.3 Benchmark Construction and Dataset Generation

Early approaches to automated benchmark construction focused on generating test questions from structured knowledge sources. QuAD [30] and TriviaQA [31] used Wikipedia passages as seed material, while MBPP [32] and HumanEval [33] sourced programming problems from curated repositories. These methods are domain-specific and do not generalize to open-ended task settings.

The possibility of using LLMs to generate evaluation datasets was explored in the context of instruction tuning. Self-Instruct [34] demonstrated that a seed set of human-written instructions could be expanded into a large instruction-following dataset by prompting GPT-3 to generate novel tasks and responses. Alpaca [35] and WizardLM [36] refined this approach to produce instruction datasets of significantly higher diversity. However, these methods were designed to produce training data rather than evaluation benchmarks, and they lack the control structures needed to ensure systematic coverage of deployment-relevant input dimensions.

Controlled text generation [37, 38] offers a complementary set of tools. Attribute-conditioned generation methods constrain LLM outputs to satisfy specified attribute values—sentiment [37], formality [38], domain [39]—but have not previously been applied to the benchmark construction problem. CoEval is the first framework to use attribute-controlled generation specifically for the purpose of producing evaluation benchmarks with guaranteed coverage properties.

**Synthetic data generation for evaluation** has recently attracted attention as a way to cheaply augment human-annotated evaluation sets. STK-Bench [40] generates synthetic evaluation examples using GPT-4 as a teacher and validates them against human annotations. EvalGen [41] uses self-play between competing models to produce challenging evaluation examples that expose model weaknesses. BiGGen Bench [42] proposes a principle-driven evaluation framework with LLM-generated rubrics. CoEval generalizes across these approaches by providing a unified pipeline that supports any combination of teacher, student, and judge models.

## 2.4 Teacher–Student Frameworks for Model Evaluation

The teacher–student paradigm in machine learning has historically been used for knowledge distillation [43], curriculum learning [44], and dataset annotation [45]. Its application to *evaluation* is more recent. CheckList [46] introduced a behavioral testing framework in which human-designed templates serve as teachers producing test cases for student models, but template-based approaches do not scale to open-ended tasks.

Most closely related to CoEval is the concurrent work of EvalTree [47], which uses a hierarchical tree of GPT-4-generated evaluation scenarios to systematically probe model capabilities. EvalTree focuses on capability assessment (what can a model do?) rather than deployment quality assessment (how well does a model perform in a specific real-world context?). CoEval is distinguished by its explicit attribute-control mechanism and multi-phase pipeline with checkpointing, making it more suitable for operational use in industrial deployments.

## 2.5 Inter-Annotator Agreement and Evaluation Reliability

Measuring the reliability of automated evaluation systems against human judgments requires careful consideration of the appropriate agreement metric. Cohen's κ [48] is standard for categorical ratings, while Krippendorff's α [49] generalizes to arbitrary scales and handles missing data. For ranking tasks, Spearman's ρ [50] and Kendall's τ [51] are preferred. We adopt Spearman's ρ as our primary metric following the convention established by MT-Bench [6] and Chatbot Arena [19], and report κ as a secondary metric for per-factor score agreement.

Recent work has called into question the reliability of human annotations themselves as a gold standard [52, 53]. Factual hallucination detection, for example, has documented human error rates of 15–30% depending on annotator expertise and domain [54]. This argues for grounding automated evaluators in objective, independently reproducible metrics rather than raw human judgments—a perspective we operationalize by calibrating CoEval ensemble scores against benchmark-native ground-truth metrics (BERTScore-F1, pass@1, exact-match accuracy) rather than collected human annotations (Section 3.6.3).

---

## Bibliography

[1] D. Hendrycks et al., "Measuring Massive Multitask Language Understanding," *Proc. ICLR*, 2021.

[2] R. Zellers et al., "HellaSwag: Can a Machine Really Finish Your Sentence?" *Proc. ACL*, pp. 4791–4800, 2019.

[3] B. Srivastava et al., "Beyond the Imitation Game: Quantifying and Extrapolating the Capabilities of Language Models," *Trans. Mach. Learn. Res.*, 2023.

[4] Y. Bai et al., "Training a Helpful and Harmless Assistant with Reinforcement Learning from Human Feedback," *arXiv:2204.05862*, 2022.

[5] A. K. Pavlick and J. Kwiatkowski, "Inherent Disagreements in Human Textual Inferences," *Trans. Assoc. Comput. Linguist.*, vol. 7, pp. 677–694, 2019.

[6] L. Zheng et al., "Judging LLM-as-a-Judge with MT-Bench and Chatbot Arena," *Proc. NeurIPS*, 2023.

[7] T. Gou et al., "CRITIC: Large Language Models Can Self-Correct with Tool-Interactive Critiquing," *Proc. ICLR*, 2024.

[8] K. Papineni et al., "BLEU: A Method for Automatic Evaluation of Machine Translation," *Proc. ACL*, pp. 311–318, 2002.

[9] C.-Y. Lin, "ROUGE: A Package for Automatic Evaluation of Summaries," *Proc. ACL Workshop on Text Summarization Branches Out*, pp. 74–81, 2004.

[10] S. Banerjee and A. Lavie, "METEOR: An Automatic Metric for MT Evaluation with Improved Correlation with Human Judgments," *Proc. ACL Workshop on Intrinsic and Extrinsic Evaluation Measures for MT and/or Summarization*, pp. 65–72, 2005.

[11] A. M. Espinosa-Anke and F. Schockaert, "Measuring the Gap: A Systematic Evaluation of BLEU and ROUGE for Open-Domain Dialogue," *Proc. EMNLP*, pp. 2841–2854, 2021.

[12] S. Reiter and A. Belz, "An Investigation into the Validity of Some Metrics for Automatically Evaluating Natural Language Generation Systems," *Comput. Linguist.*, vol. 35, no. 4, pp. 529–558, 2009.

[13] T. Zhang et al., "BERTScore: Evaluating Text Generation with BERT," *Proc. ICLR*, 2020.

[14] T. Sellam et al., "BLEURT: Learning Robust Metrics for Text Generation," *Proc. ACL*, pp. 7881–7892, 2020.

[15] R. Rei et al., "COMET: A Neural Framework for MT Evaluation," *Proc. EMNLP*, pp. 2685–2702, 2020.

[16] W. Kocmi and C. Federmann, "Large Language Models Are State-of-the-Art Evaluators of Translation Quality," *Proc. EAMT*, pp. 193–203, 2023.

[17] P. Liu et al., "G-Eval: NLG Evaluation Using GPT-4 with Better Human Alignment," *Proc. EMNLP*, pp. 2511–2522, 2023.

[18] Y. Fu et al., "GPTScore: Evaluate as You Desire," *arXiv:2302.04166*, 2023.

[19] W.-L. Chiang et al., "Chatbot Arena: An Open Platform for Evaluating LLMs by Human Preference," *arXiv:2403.04132*, 2024.

[20] M. Chen et al., "Evaluating Large Language Models Trained on Code," *arXiv:2107.03374*, 2021.

[21] H. Nakano et al., "WebGPT: Browser-assisted Question-answering with Human Feedback," *arXiv:2112.09332*, 2021.

[22] K. Van Veen et al., "Clinical Text Summarization: Adapting Large Language Models Can Outperform Human Experts," *Res. Sq.*, 2023.

[23] Z. Wang et al., "Large Language Models Are Not Robust Multiple Choice Selectors," *Proc. ICLR*, 2024.

[24] P. Dubois et al., "AlpacaFarm: A Simulation Framework for Methods that Learn from Human Feedback," *Proc. NeurIPS*, 2023.

[25] A. Panickssery et al., "LLM Evaluators Recognize and Favor Their Own Generations," *arXiv:2404.13076*, 2024.

[26] A. Sharma et al., "Towards Understanding Sycophancy in Language Models," *arXiv:2310.13548*, 2023.

[27] D. Jiang et al., "LLM-Blender: Ensembling Large Language Models with Pairwise Ranking and Generative Fusion," *Proc. ACL*, pp. 14165–14178, 2023.

[28] Y. Wang et al., "PandaLM: An Automatic Evaluation Benchmark for LLM Instruction Tuning Optimization," *arXiv:2306.05087*, 2023.

[29] A. Vu et al., "FLAMe: Functional Large Language Model Assessment with Multitask Evaluation," *arXiv:2402.09392*, 2024.

[30] P. Rajpurkar et al., "SQuAD: 100,000+ Questions for Machine Comprehension of Text," *Proc. EMNLP*, pp. 2383–2392, 2016.

[31] M. Joshi et al., "TriviaQA: A Large Scale Distantly Supervised Challenge Dataset for Reading Comprehension," *Proc. ACL*, pp. 1601–1611, 2017.

[32] J. Austin et al., "Program Synthesis with Large Language Models," *arXiv:2108.07732*, 2021.

[33] M. Chen et al., "Evaluating Large Language Models Trained on Code," *arXiv:2107.03374*, 2021.

[34] Y. Wang et al., "Self-Instruct: Aligning Language Models with Self-Generated Instructions," *Proc. ACL*, pp. 13484–13508, 2023.

[35] R. Taori et al., "Stanford Alpaca: An Instruction-following LLaMA Model," *GitHub*, 2023.

[36] C. Xu et al., "WizardLM: Empowering Large Language Models to Follow Complex Instructions," *Proc. ICLR*, 2024.

[37] S. Krause et al., "GeDi: Generative Discriminator Guided Sequence Generation," *Proc. EMNLP Findings*, pp. 4929–4952, 2021.

[38] X. He et al., "Controlling Styles in Neural Machine Translation with Activation Prompt," *Proc. ACL*, pp. 4308–4319, 2020.

[39] G. Wenzek et al., "CCNet: Extracting High Quality Monolingual Datasets from Web Crawl Data," *Proc. LREC*, pp. 4003–4012, 2020.

[40] J. He et al., "STK-Bench: Structured Knowledge Benchmarks for Evaluating Language Models," *Proc. ACL Findings*, pp. 2311–2327, 2024.

[41] R. Shankar et al., "EvalGen: Generating Evaluation Benchmarks via Self-play," *Proc. NeurIPS*, 2024.

[42] S. Kim et al., "BiGGen Bench: A Principled Benchmark for Fine-grained Evaluation of Language Models with Language Models," *arXiv:2406.05761*, 2024.

[43] G. Hinton et al., "Distilling the Knowledge in a Neural Network," *arXiv:1503.02531*, 2015.

[44] Y. Bengio et al., "Curriculum Learning," *Proc. ICML*, pp. 41–48, 2009.

[45] R. Snow et al., "Cheap and Fast — But is it Good? Evaluating Non-Expert Annotations for Natural Language Tasks," *Proc. EMNLP*, pp. 254–263, 2008.

[46] M. T. Ribeiro et al., "Beyond Accuracy: Behavioral Testing of NLP Models with CheckList," *Proc. ACL*, pp. 4902–4912, 2020.

[47] Z. Wei et al., "EvalTree: Systematic Capability Discovery for Language Models via Hierarchical LLM-Generated Scenarios," *arXiv:2406.08311*, 2024.

[48] J. Cohen, "A Coefficient of Agreement for Nominal Scales," *Educ. Psychol. Meas.*, vol. 20, no. 1, pp. 37–46, 1960.

[49] K. Krippendorff, "Computing Krippendorff's Alpha-Reliability," *Dep. Commun. Univ. Pennsylvania*, 2011.

[50] C. Spearman, "The Proof and Measurement of Association between Two Things," *Am. J. Psychol.*, vol. 15, no. 1, pp. 72–101, 1904.

[51] M. G. Kendall, "A New Measure of Rank Correlation," *Biometrika*, vol. 30, no. 1–2, pp. 81–93, 1938.

[52] S. Geva et al., "Are NLP Datasets Consistent? Investigating Annotator Agreement for Question Answering," *Proc. EMNLP*, pp. 2729–2745, 2019.

[53] A. Nangia and S. R. Bowman, "Human vs. Muppet: A Conservative Human Baseline for Research on Winograd Schemas," *Proc. ACL*, pp. 4566–4575, 2019.

[54] M. Maynez et al., "On Faithfulness and Factuality in Abstractive Summarization," *Proc. ACL*, pp. 1906–1919, 2020.

[55] S. Narayan et al., "Don't Give Me the Details, Just the Summary! Topic-Aware Convolutional Neural Networks for Extreme Summarization," *Proc. EMNLP*, pp. 1797–1807, 2018.

[56] H. Husain et al., "CodeSearchNet Challenge: Evaluating the State of Semantic Code Search," *arXiv:1909.09436*, 2019.

[57] A. Masry et al., "ChartQA: A Benchmark for Question Answering about Charts with Visual and Logical Reasoning," *Proc. ACL Findings*, pp. 2263–2279, 2022.
