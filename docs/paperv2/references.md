# CoEval: References for Related Work Section

Verified and supplemented citations for the related work section of the paper:
**"CoEval: A Self-Evaluating LLM Ensemble Framework for Scalable, Attribute-Controlled Benchmark Generation"**

---

## 2.1 LLM Evaluation Benchmarks

**[Srivastava2022]** Aarohi Srivastava et al. (450+ authors across 132 institutions). "Beyond the Imitation Game: Quantifying and Extrapolating the Capabilities of Language Models." *Transactions on Machine Learning Research (TMLR)* (2022). arXiv:2206.04615. https://arxiv.org/abs/2206.04615

> VERIFIED. Title is "Beyond the Imitation Game: Quantifying and Extrapolating the Capabilities of Language Models." Published in TMLR (not a conference), presented also at OpenReview. GitHub: google/BIG-bench. The paper has 450+ authors.

**[Liang2022]** Percy Liang, Rishi Bommasani, Tony Lee, and 47 additional authors. "Holistic Evaluation of Language Models." *Transactions on Machine Learning Research (TMLR)* (2023). arXiv:2211.09110. https://arxiv.org/abs/2211.09110

> VERIFIED. Stanford CRFM paper. Published as TMLR 2023 (submitted Nov 2022). Evaluates 30 models across 42 scenarios with 7 metrics. GitHub: stanford-crfm/helm.

**[Hendrycks2021]** Dan Hendrycks, Collin Burns, Steven Basart, Andy Zou, Mantas Mazeika, Dawn Song, and Jacob Steinhardt. "Measuring Massive Multitask Language Understanding." *Proceedings of the International Conference on Learning Representations (ICLR)* (2021). arXiv:2009.03300. https://arxiv.org/abs/2009.03300

> VERIFIED. 57 tasks, 15,908 multiple-choice questions. Published at ICLR 2021. GitHub: hendrycks/test. HuggingFace: cais/mmlu.

**[White2024]** Colin White, Samuel Dooley, Manley Roberts, Arka Pal, Ben Feuer, Siddhartha Jain, Ravid Shwartz-Ziv, Neel Jain, Khalid Saifullah, and others. "LiveBench: A Challenging, Contamination-Limited LLM Benchmark." *Proceedings of the International Conference on Learning Representations (ICLR)* (2025). arXiv:2406.19314. https://arxiv.org/abs/2406.19314

> VERIFIED. Dynamic benchmark updated with fresh data from math competitions, arXiv papers, and news to resist contamination.

---

## 2.2 LLM-as-Judge

**[Zheng2023]** Lianmin Zheng, Wei-Lin Chiang, Ying Sheng, Siyuan Zhuang, Zhanghao Wu, Yonghao Zhuang, Zi Lin, Zhuohan Li, Dacheng Li, Eric P. Xing, Hao Zhang, Joseph E. Gonzalez, and Ion Stoica. "Judging LLM-as-a-Judge with MT-Bench and Chatbot Arena." *Advances in Neural Information Processing Systems (NeurIPS)*, Datasets and Benchmarks Track (2023). arXiv:2306.05685. https://arxiv.org/abs/2306.05685

> VERIFIED. Introduces MT-Bench and Chatbot Arena. NeurIPS 2023. ACM DL: 10.5555/3666122.3668142. Identifies position, verbosity, and self-enhancement biases in LLM judges.

**[Liu2023geval]** Yang Liu, Dan Iter, Yichong Xu, Shuohang Wang, Ruochen Xu, and Chenguang Zhu. "G-Eval: NLG Evaluation using GPT-4 with Better Human Alignment." *Proceedings of the Conference on Empirical Methods in Natural Language Processing (EMNLP)*, pages 2511–2522 (2023). arXiv:2303.16634. https://arxiv.org/abs/2303.16634

> VERIFIED. EMNLP 2023. Chain-of-thought evaluation framework using GPT-4. ACL Anthology: 2023.emnlp-main.153.

**[Chan2023]** Chi-Min Chan, Weize Chen, Yusheng Su, Jianxuan Yu, Wei Xue, Shanghang Zhang, Jie Fu, and Zhiyuan Liu. "ChatEval: Towards Better LLM-based Evaluators through Multi-Agent Debate." *Proceedings of the International Conference on Learning Representations (ICLR)* (2024). arXiv:2308.07201. https://arxiv.org/abs/2308.07201

> VERIFIED. Multi-agent debate framework for text evaluation. Published at ICLR 2024. GitHub: thunlp/ChatEval. OpenReview: FQepisCUWu.

**[Wang2023pandalm]** Yidong Wang, Zhuohao Yu, Zhengran Zeng, Linyi Yang, Cunxiang Wang, Hao Chen, Chaoya Jiang, Rui Xie, Jindong Wang, Xing Xie, Wei Ye, Shikun Zhang, and Yue Zhang. "PandaLM: An Automatic Evaluation Benchmark for LLM Instruction Tuning Optimization." arXiv preprint (2023). arXiv:2306.05087. https://arxiv.org/abs/2306.05087

> VERIFIED. Note: The correct title is "PandaLM: An Automatic Evaluation Benchmark for LLM Instruction Tuning Optimization" (not "evaluating instructions" as in original citation). Tuned from LLaMA. GitHub: WeOpenML/PandaLM.

**[Li2023autoj]** Junlong Li, Shichao Sun, Weizhe Yuan, Run-Ze Fan, Hai Zhao, and Pengfei Liu. "Generative Judge for Evaluating Alignment." *Proceedings of the International Conference on Learning Representations (ICLR)* (2024). arXiv:2310.05470. https://arxiv.org/abs/2310.05470

> VERIFIED. Auto-J: 13B open-source judge covering 58 real-world scenarios. ICLR 2024. OpenReview: gtkFw6sZGS.

**[Wang2023faireval]** Peiyi Wang, Lei Li, Liang Chen, Zefan Cai, Dawei Zhu, Binghuai Lin, Yunbo Cao, Qi Liu, Tianyu Liu, and Zhifang Sui. "Large Language Models are not Fair Evaluators." *Proceedings of the 62nd Annual Meeting of the Association for Computational Linguistics (ACL)*, Long Papers, pages 8280–8301 (2024). arXiv:2305.17926. https://arxiv.org/abs/2305.17926

> VERIFIED. First submitted May 2023, published at ACL 2024. Identifies positional bias where answer order can manipulate rankings. Proposes calibration framework. GitHub: i-Eval/FairEval.

**[Dubois2024]** Yann Dubois, Balázs Galambosi, Percy Liang, and Tatsunori B. Hashimoto. "Length-Controlled AlpacaEval: A Simple Way to Debias Automatic Evaluators." *Proceedings of the Conference on Language Modeling (COLM)* (2024). arXiv:2404.04475. https://arxiv.org/abs/2404.04475

> VERIFIED. Published at COLM 2024. Regression analysis to control length bias; Spearman correlation with Chatbot Arena improves from 0.94 to 0.98.

---

## 2.3 Synthetic Benchmark Construction

**[Wang2023selfinstruct]** Yizhong Wang, Yeganeh Kordi, Swaroop Mishra, Alisa Liu, Noah A. Smith, Daniel Khashabi, and Hannaneh Hajishirzi. "Self-Instruct: Aligning Language Models with Self-Generated Instructions." *Proceedings of the 61st Annual Meeting of the Association for Computational Linguistics (ACL)*, Volume 1: Long Papers, pages 13484–13508 (2023). arXiv:2212.10560. https://arxiv.org/abs/2212.10560

> VERIFIED. ACL 2023. DOI: 10.18653/v1/2023.acl-long.754. 33% absolute improvement over vanilla GPT-3 on SuperNI. GitHub: yizhongw/self-instruct.

**[Xu2023wizardlm]** Can Xu, Qingfeng Sun, Kai Zheng, Xiubo Geng, Pu Zhao, Jiazhan Feng, Chongyang Tao, Qingwei Lin, and Daxin Jiang. "WizardLM: Empowering Large Language Models to Follow Complex Instructions." *Proceedings of the International Conference on Learning Representations (ICLR)* (2024). arXiv:2304.12244. https://arxiv.org/abs/2304.12244

> VERIFIED. Note: Published at ICLR 2024 (not 2023). Introduces Evol-Instruct for progressive instruction complexity. arXiv first submitted April 2023.

**[Chung2023]** John Chung, Ece Kamar, and Saleema Amershi. "Increasing Diversity While Maintaining Accuracy: Text Data Generation with Large Language Models and Human Interventions." *Proceedings of the 61st Annual Meeting of the Association for Computational Linguistics (ACL)*, Volume 1: Long Papers, pages 575–593 (2023). arXiv:2306.04140. https://arxiv.org/abs/2306.04140

> VERIFIED. ACL 2023. Studies logit suppression and temperature sampling for diversity; proposes human-in-the-loop label correction.

**[Lin2024wildbench]** Bill Yuchen Lin, Yuntian Deng, Khyathi Chandu, Faeze Brahman, Abhilasha Ravichander, Valentina Pyatkin, Nouha Dziri, Ronan Le Bras, and Yejin Choi. "WildBench: Benchmarking LLMs with Challenging Tasks from Real Users in the Wild." arXiv preprint (2024). arXiv:2406.04770. https://arxiv.org/abs/2406.04770

> VERIFIED. 1,024 tasks from real user-chatbot logs. Pearson correlation 0.98 with Chatbot Arena Elo. GitHub: allenai/WildBench.

---

## 2.4 Rubric-Based Evaluation

**[Kim2023prometheus]** Seungone Kim, Jamin Shin, Yejin Cho, Joel Jang, Shayne Longpre, Hwaran Lee, Sangdoo Yun, Seongjin Shin, Sungdong Kim, James Thorne, and Minjoon Seo. "Prometheus: Inducing Fine-grained Evaluation Capability in Language Models." *Proceedings of the International Conference on Learning Representations (ICLR)* (2024). arXiv:2310.08491. https://arxiv.org/abs/2310.08491

> VERIFIED. ICLR 2024 (also NeurIPS 2023 Workshop). Feedback Collection dataset: 1K rubrics, 20K instructions, 100K feedback. Pearson correlation 0.897 with human evaluators. OpenReview: 8euJaTveKw.

**[Kim2024prometheus2]** Seungone Kim, Juyoung Suk, Shayne Longpre, Bill Yuchen Lin, Jamin Shin, Sean Welleck, Graham Neubig, Moontae Lee, Kyungjae Lee, and Minjoon Seo. "Prometheus 2: An Open Source Language Model Specialized in Evaluating Other Language Models." *Proceedings of the Conference on Empirical Methods in Natural Language Processing (EMNLP)*, pages 4334–4353 (2024). arXiv:2405.01535. https://arxiv.org/abs/2405.01535

> VERIFIED. EMNLP 2024. Supports both direct assessment and pairwise ranking. Based on Mistral-7B and Mixtral-8x7B via weight merging. ACL Anthology: 2024.emnlp-main.248.

**[Ye2023flask]** Seonghyeon Ye, Doyoung Kim, Sungdong Kim, Hyeonbin Hwang, Seungone Kim, Yongrae Jo, James Thorne, Juho Kim, and Minjoon Seo. "FLASK: Fine-grained Language Model Evaluation based on Alignment Skill Sets." *Proceedings of the International Conference on Learning Representations (ICLR)*, Spotlight (2024). arXiv:2307.10928. https://arxiv.org/abs/2307.10928

> VERIFIED. ICLR 2024 Spotlight. Decomposes evaluation into 12 skill categories with per-skill rubrics. OpenReview: CYmF38ysDa. GitHub: kaistAI/FLASK.

**[Vu2024flame]** Tu Vu, Kalpesh Krishna, Salaheddin Alzubi, Chris Tar, Manaal Faruqui, and Yun-Hsuan Sung. "Foundational Autoraters: Taming Large Language Models for Better Automatic Evaluation." *Proceedings of the Conference on Empirical Methods in Natural Language Processing (EMNLP)*, pages 17086–17105 (2024). arXiv:2407.10817. https://arxiv.org/abs/2407.10817

> VERIFIED. Google DeepMind / UMass Amherst. FLAMe trained on 100+ quality assessment tasks with 5M+ human judgments. Outperforms GPT-4 and Claude-3 on 8 of 12 autorater benchmarks. ACL Anthology: 2024.emnlp-main.949.

---

## 2.5 Inter-Rater Agreement & Calibration

**[Ribeiro2020]** Marco Tulio Ribeiro, Tongshuang Wu, Carlos Guestrin, and Sameer Singh. "Beyond Accuracy: Behavioral Testing of NLP Models with CheckList." *Proceedings of the 58th Annual Meeting of the Association for Computational Linguistics (ACL)*, pages 4902–4912 (2020). arXiv:2005.04118. https://arxiv.org/abs/2005.04118

> VERIFIED. ACL 2020 Best Paper Award. DOI: 10.18653/v1/2020.acl-main.442. Task-agnostic behavioral testing framework inspired by software engineering. GitHub: marcotcr/checklist.

**[Fabbri2021]** Alexander R. Fabbri, Wojciech Kryściński, Bryan McCann, Caiming Xiong, Richard Socher, and Dragomir Radev. "SummEval: Re-evaluating Summarization Evaluation." *Transactions of the Association for Computational Linguistics (TACL)*, Volume 9, pages 391–409 (2021). arXiv:2007.12626. https://arxiv.org/abs/2007.12626

> VERIFIED. TACL 2021. DOI: 10.1162/tacl_a_00373. Re-evaluates 14 automatic metrics; benchmarks 23 summarization models; releases aligned model outputs and unified evaluation toolkit.

**[Park2024offsetbias]** Junsoo Park, Seungyeon Jwa, Ren Meiying, Daeyoung Kim, and Sanghyuk Choi. "OffsetBias: Leveraging Debiased Data for Tuning Evaluators." *Findings of the Association for Computational Linguistics: EMNLP 2024*, pages 1043–1067 (2024). arXiv:2407.06551. https://arxiv.org/abs/2407.06551

> VERIFIED. EMNLP 2024 Findings. Identifies 6 bias types (length, concreteness, empty reference, content continuation, nested instruction, familiar knowledge). Releases EvalBiasBench and OffsetBias dataset (8.5K instances). GitHub: ncsoft/offsetbias.

**[Shi2024]** Lin Shi, Chiyu Ma, Wenhua Liang, Xingjian Diao, Weicheng Ma, and Soroush Vosoughi. "Judging the Judges: A Systematic Study of Position Bias in LLM-as-a-Judge." arXiv preprint (2024). arXiv:2406.07791. https://arxiv.org/abs/2406.07791

> VERIFIED. Evaluates position bias across 15 LLM judges, 22 tasks, 150,000+ evaluation instances. Introduces three metrics: repetition stability, position consistency, preference fairness.

---

## Additional Recommended Citations (by topic)

### Positional and Verbosity Bias in LLM Judges

**[Wang2023faireval]** (listed above in 2.2) — seminal work on positional bias.

**[Shi2024]** (listed above in 2.5) — systematic study across 15 judges.

### Ensemble Methods / Multi-Agent Evaluation

**[Chan2023]** (listed above in 2.2) — ChatEval multi-agent debate framework.

**[Li2023autoj]** (listed above in 2.2) — Auto-J generative judge.

### Benchmark Contamination / Data Leakage

**[White2024]** (listed above in 2.1) — LiveBench: contamination-limited dynamic benchmark with automatic answer verification.

### Calibration of LLM-as-Judge Systems

**[Dubois2024]** (listed above in 2.2) — Length-Controlled AlpacaEval for debiasing.

**[Park2024offsetbias]** (listed above in 2.5) — OffsetBias debiasing via training data curation.

### Rubric / Fine-Grained Attribute-Based Evaluation

**[Ye2023flask]** (listed above in 2.4) — FLASK 12-skill rubric evaluation.

**[Kim2023prometheus]** (listed above in 2.4) — Prometheus user-defined rubric evaluation.

---

## Complete BibTeX Block

```bibtex
% ============================================================
% 2.1 LLM Evaluation Benchmarks
% ============================================================

@article{srivastava2022beyond,
  title     = {Beyond the Imitation Game: Quantifying and Extrapolating the Capabilities of Language Models},
  author    = {Srivastava, Aarohi and others},
  journal   = {Transactions on Machine Learning Research},
  year      = {2022},
  url       = {https://arxiv.org/abs/2206.04615},
  note      = {arXiv:2206.04615}
}

@article{liang2022holistic,
  title     = {Holistic Evaluation of Language Models},
  author    = {Liang, Percy and Bommasani, Rishi and Lee, Tony and Tsipras, Dimitris and others},
  journal   = {Transactions on Machine Learning Research},
  year      = {2023},
  url       = {https://arxiv.org/abs/2211.09110},
  note      = {arXiv:2211.09110}
}

@inproceedings{hendrycks2021measuring,
  title     = {Measuring Massive Multitask Language Understanding},
  author    = {Hendrycks, Dan and Burns, Collin and Basart, Steven and Zou, Andy and Mazeika, Mantas and Song, Dawn and Steinhardt, Jacob},
  booktitle = {Proceedings of the International Conference on Learning Representations (ICLR)},
  year      = {2021},
  url       = {https://arxiv.org/abs/2009.03300},
  note      = {arXiv:2009.03300}
}

@inproceedings{white2024livebench,
  title     = {{LiveBench}: A Challenging, Contamination-Limited {LLM} Benchmark},
  author    = {White, Colin and Dooley, Samuel and Roberts, Manley and Pal, Arka and Feuer, Ben and Jain, Siddhartha and Shwartz-Ziv, Ravid and Jain, Neel and Saifullah, Khalid and Dey, Sreemanti and others},
  booktitle = {Proceedings of the International Conference on Learning Representations (ICLR)},
  year      = {2025},
  url       = {https://arxiv.org/abs/2406.19314},
  note      = {arXiv:2406.19314}
}

% ============================================================
% 2.2 LLM-as-Judge
% ============================================================

@inproceedings{zheng2023judging,
  title     = {Judging {LLM}-as-a-Judge with {MT}-Bench and Chatbot Arena},
  author    = {Zheng, Lianmin and Chiang, Wei-Lin and Sheng, Ying and Zhuang, Siyuan and Wu, Zhanghao and Zhuang, Yonghao and Lin, Zi and Li, Zhuohan and Li, Dacheng and Xing, Eric P. and Zhang, Hao and Gonzalez, Joseph E. and Stoica, Ion},
  booktitle = {Advances in Neural Information Processing Systems (NeurIPS), Datasets and Benchmarks Track},
  year      = {2023},
  url       = {https://arxiv.org/abs/2306.05685},
  note      = {arXiv:2306.05685}
}

@inproceedings{liu2023geval,
  title     = {{G-Eval}: {NLG} Evaluation using {GPT}-4 with Better Human Alignment},
  author    = {Liu, Yang and Iter, Dan and Xu, Yichong and Wang, Shuohang and Xu, Ruochen and Zhu, Chenguang},
  booktitle = {Proceedings of the Conference on Empirical Methods in Natural Language Processing (EMNLP)},
  pages     = {2511--2522},
  year      = {2023},
  url       = {https://arxiv.org/abs/2303.16634},
  note      = {arXiv:2303.16634}
}

@inproceedings{chan2023chateval,
  title     = {{ChatEval}: Towards Better {LLM}-based Evaluators through Multi-Agent Debate},
  author    = {Chan, Chi-Min and Chen, Weize and Su, Yusheng and Yu, Jianxuan and Xue, Wei and Zhang, Shanghang and Fu, Jie and Liu, Zhiyuan},
  booktitle = {Proceedings of the International Conference on Learning Representations (ICLR)},
  year      = {2024},
  url       = {https://arxiv.org/abs/2308.07201},
  note      = {arXiv:2308.07201}
}

@article{wang2023pandalm,
  title     = {{PandaLM}: An Automatic Evaluation Benchmark for {LLM} Instruction Tuning Optimization},
  author    = {Wang, Yidong and Yu, Zhuohao and Zeng, Zhengran and Yang, Linyi and Wang, Cunxiang and Chen, Hao and Jiang, Chaoya and Xie, Rui and Wang, Jindong and Xie, Xing and Ye, Wei and Zhang, Shikun and Zhang, Yue},
  journal   = {arXiv preprint},
  year      = {2023},
  url       = {https://arxiv.org/abs/2306.05087},
  note      = {arXiv:2306.05087}
}

@inproceedings{li2023autoj,
  title     = {Generative Judge for Evaluating Alignment},
  author    = {Li, Junlong and Sun, Shichao and Yuan, Weizhe and Fan, Run-Ze and Zhao, Hai and Liu, Pengfei},
  booktitle = {Proceedings of the International Conference on Learning Representations (ICLR)},
  year      = {2024},
  url       = {https://arxiv.org/abs/2310.05470},
  note      = {arXiv:2310.05470}
}

@inproceedings{wang2023faireval,
  title     = {Large Language Models are not Fair Evaluators},
  author    = {Wang, Peiyi and Li, Lei and Chen, Liang and Cai, Zefan and Zhu, Dawei and Lin, Binghuai and Cao, Yunbo and Liu, Qi and Liu, Tianyu and Sui, Zhifang},
  booktitle = {Proceedings of the 62nd Annual Meeting of the Association for Computational Linguistics (ACL)},
  pages     = {8280--8301},
  year      = {2024},
  url       = {https://arxiv.org/abs/2305.17926},
  note      = {arXiv:2305.17926; first submitted May 2023}
}

@inproceedings{dubois2024length,
  title     = {Length-Controlled {AlpacaEval}: A Simple Way to Debias Automatic Evaluators},
  author    = {Dubois, Yann and Galambosi, Bal{\'a}zs and Liang, Percy and Hashimoto, Tatsunori B.},
  booktitle = {Proceedings of the Conference on Language Modeling (COLM)},
  year      = {2024},
  url       = {https://arxiv.org/abs/2404.04475},
  note      = {arXiv:2404.04475}
}

% ============================================================
% 2.3 Synthetic Benchmark Construction
% ============================================================

@inproceedings{wang2023selfinstruct,
  title     = {Self-Instruct: Aligning Language Models with Self-Generated Instructions},
  author    = {Wang, Yizhong and Kordi, Yeganeh and Mishra, Swaroop and Liu, Alisa and Smith, Noah A. and Khashabi, Daniel and Hajishirzi, Hannaneh},
  booktitle = {Proceedings of the 61st Annual Meeting of the Association for Computational Linguistics (ACL)},
  pages     = {13484--13508},
  year      = {2023},
  doi       = {10.18653/v1/2023.acl-long.754},
  url       = {https://arxiv.org/abs/2212.10560},
  note      = {arXiv:2212.10560}
}

@inproceedings{xu2023wizardlm,
  title     = {{WizardLM}: Empowering Large Language Models to Follow Complex Instructions},
  author    = {Xu, Can and Sun, Qingfeng and Zheng, Kai and Geng, Xiubo and Zhao, Pu and Feng, Jiazhan and Tao, Chongyang and Lin, Qingwei and Jiang, Daxin},
  booktitle = {Proceedings of the International Conference on Learning Representations (ICLR)},
  year      = {2024},
  url       = {https://arxiv.org/abs/2304.12244},
  note      = {arXiv:2304.12244; first submitted April 2023}
}

@inproceedings{chung2023increasing,
  title     = {Increasing Diversity While Maintaining Accuracy: Text Data Generation with Large Language Models and Human Interventions},
  author    = {Chung, John and Kamar, Ece and Amershi, Saleema},
  booktitle = {Proceedings of the 61st Annual Meeting of the Association for Computational Linguistics (ACL)},
  pages     = {575--593},
  year      = {2023},
  url       = {https://arxiv.org/abs/2306.04140},
  note      = {arXiv:2306.04140}
}

@article{lin2024wildbench,
  title     = {{WildBench}: Benchmarking {LLMs} with Challenging Tasks from Real Users in the Wild},
  author    = {Lin, Bill Yuchen and Deng, Yuntian and Chandu, Khyathi and Brahman, Faeze and Ravichander, Abhilasha and Pyatkin, Valentina and Dziri, Nouha and Le Bras, Ronan and Choi, Yejin},
  journal   = {arXiv preprint},
  year      = {2024},
  url       = {https://arxiv.org/abs/2406.04770},
  note      = {arXiv:2406.04770}
}

% ============================================================
% 2.4 Rubric-Based Evaluation
% ============================================================

@inproceedings{kim2023prometheus,
  title     = {Prometheus: Inducing Fine-grained Evaluation Capability in Language Models},
  author    = {Kim, Seungone and Shin, Jamin and Cho, Yejin and Jang, Joel and Longpre, Shayne and Lee, Hwaran and Yun, Sangdoo and Shin, Seongjin and Kim, Sungdong and Thorne, James and Seo, Minjoon},
  booktitle = {Proceedings of the International Conference on Learning Representations (ICLR)},
  year      = {2024},
  url       = {https://arxiv.org/abs/2310.08491},
  note      = {arXiv:2310.08491}
}

@inproceedings{kim2024prometheus2,
  title     = {Prometheus 2: An Open Source Language Model Specialized in Evaluating Other Language Models},
  author    = {Kim, Seungone and Suk, Juyoung and Longpre, Shayne and Lin, Bill Yuchen and Shin, Jamin and Welleck, Sean and Neubig, Graham and Lee, Moontae and Lee, Kyungjae and Seo, Minjoon},
  booktitle = {Proceedings of the Conference on Empirical Methods in Natural Language Processing (EMNLP)},
  pages     = {4334--4353},
  year      = {2024},
  url       = {https://arxiv.org/abs/2405.01535},
  note      = {arXiv:2405.01535}
}

@inproceedings{ye2023flask,
  title     = {{FLASK}: Fine-grained Language Model Evaluation based on Alignment Skill Sets},
  author    = {Ye, Seonghyeon and Kim, Doyoung and Kim, Sungdong and Hwang, Hyeonbin and Kim, Seungone and Jo, Yongrae and Thorne, James and Kim, Juho and Seo, Minjoon},
  booktitle = {Proceedings of the International Conference on Learning Representations (ICLR)},
  note      = {Spotlight; arXiv:2307.10928},
  year      = {2024},
  url       = {https://arxiv.org/abs/2307.10928}
}

@inproceedings{vu2024flame,
  title     = {Foundational Autoraters: Taming Large Language Models for Better Automatic Evaluation},
  author    = {Vu, Tu and Krishna, Kalpesh and Alzubi, Salaheddin and Tar, Chris and Faruqui, Manaal and Sung, Yun-Hsuan},
  booktitle = {Proceedings of the Conference on Empirical Methods in Natural Language Processing (EMNLP)},
  pages     = {17086--17105},
  year      = {2024},
  url       = {https://arxiv.org/abs/2407.10817},
  note      = {arXiv:2407.10817}
}

% ============================================================
% 2.5 Inter-Rater Agreement & Calibration
% ============================================================

@inproceedings{ribeiro2020beyond,
  title     = {Beyond Accuracy: Behavioral Testing of {NLP} Models with {CheckList}},
  author    = {Ribeiro, Marco Tulio and Wu, Tongshuang and Guestrin, Carlos and Singh, Sameer},
  booktitle = {Proceedings of the 58th Annual Meeting of the Association for Computational Linguistics (ACL)},
  pages     = {4902--4912},
  year      = {2020},
  doi       = {10.18653/v1/2020.acl-main.442},
  url       = {https://arxiv.org/abs/2005.04118},
  note      = {ACL 2020 Best Paper. arXiv:2005.04118}
}

@article{fabbri2021summeval,
  title     = {{SummEval}: Re-evaluating Summarization Evaluation},
  author    = {Fabbri, Alexander R. and Kry{\'s}ci{\'n}ski, Wojciech and McCann, Bryan and Xiong, Caiming and Socher, Richard and Radev, Dragomir},
  journal   = {Transactions of the Association for Computational Linguistics (TACL)},
  volume    = {9},
  pages     = {391--409},
  year      = {2021},
  doi       = {10.1162/tacl_a_00373},
  url       = {https://arxiv.org/abs/2007.12626},
  note      = {arXiv:2007.12626}
}

@inproceedings{park2024offsetbias,
  title     = {{OffsetBias}: Leveraging Debiased Data for Tuning Evaluators},
  author    = {Park, Junsoo and Jwa, Seungyeon and Meiying, Ren and Kim, Daeyoung and Choi, Sanghyuk},
  booktitle = {Findings of the Association for Computational Linguistics: EMNLP 2024},
  pages     = {1043--1067},
  year      = {2024},
  url       = {https://arxiv.org/abs/2407.06551},
  note      = {arXiv:2407.06551}
}

@article{shi2024judging,
  title     = {Judging the Judges: A Systematic Study of Position Bias in {LLM}-as-a-Judge},
  author    = {Shi, Lin and Ma, Chiyu and Liang, Wenhua and Diao, Xingjian and Ma, Weicheng and Vosoughi, Soroush},
  journal   = {arXiv preprint},
  year      = {2024},
  url       = {https://arxiv.org/abs/2406.07791},
  note      = {arXiv:2406.07791}
}
```

---

## Verification Notes & Corrections

The following corrections should be noted relative to the originally requested citations:

1. **BIG-Bench** (Srivastava et al., 2022): VERIFIED. Published in TMLR (not a conference). Over 450 authors. arXiv:2206.04615.

2. **HELM** (Liang et al., 2022): VERIFIED. Published in TMLR 2023 (submitted Nov 2022). arXiv:2211.09110.

3. **MMLU** (Hendrycks et al., 2021): VERIFIED. ICLR 2021. arXiv:2009.03300.

4. **G-Eval** (Liu et al., 2023): VERIFIED. Title is "G-Eval: NLG Evaluation using GPT-4 **with Better Human Alignment**" (original citation omitted the subtitle). EMNLP 2023. arXiv:2303.16634.

5. **MT-Bench** (Zheng et al., 2023): VERIFIED. NeurIPS 2023 Datasets and Benchmarks Track. arXiv:2306.05685.

6. **PandaLM** (Wang et al., 2023): CORRECTION — correct title is "PandaLM: An **Automatic Evaluation Benchmark for LLM Instruction Tuning Optimization**" (not "evaluating instructions"). arXiv:2306.05087.

7. **ChatEval** (Chan et al., 2023): VERIFIED. Full title is "ChatEval: Towards Better LLM-based Evaluators through **Multi-Agent Debate**". Published at ICLR 2024 (not 2023 conference). arXiv:2308.07201.

8. **Self-Instruct** (Wang et al., 2023): VERIFIED. ACL 2023. arXiv:2212.10560.

9. **WizardLM** (Xu et al., 2023): PARTIAL CORRECTION — published at ICLR **2024** (not 2023, though arXiv submitted April 2023). arXiv:2304.12244.

10. **Prometheus** (Kim et al., 2023): VERIFIED. ICLR 2024 (arXiv submitted Oct 2023). arXiv:2310.08491.

11. **CheckList** (Ribeiro et al., 2020): VERIFIED. ACL 2020 Best Paper. arXiv:2005.04118.

12. **SummEval** (Fabbri et al., 2021): VERIFIED. TACL 2021. arXiv:2007.12626.

13. **OffsetBias** (Park et al., 2024): VERIFIED. EMNLP 2024 Findings. arXiv:2407.06551.

14. **Prometheus-2** (Kim et al., 2024): VERIFIED. EMNLP 2024. arXiv:2405.01535.

15. **FLAMe** (Vu et al., 2024): VERIFIED. Full title is "Foundational Autoraters: Taming Large Language Models for Better Automatic Evaluation". EMNLP 2024. arXiv:2407.10817.

---

*Generated: 2026-03-03. All papers verified against arxiv.org, ACL Anthology, and OpenReview.*
