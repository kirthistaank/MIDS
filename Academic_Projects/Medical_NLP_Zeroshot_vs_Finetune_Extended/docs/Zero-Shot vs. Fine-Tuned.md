# Zero-Shot vs. Fine-Tuned: A Systematic Evaluation of Encoder, Decoder, and LLM Architectures for Clinical Text Classification

**Course:** D266 — Natural Language Processing  
**Affiliation:** UC Berkeley — Master of Information and Data Science (MIDS)  
**Authors:** Helen Lu, Kirthi Shanbhag, Monica Martin  
**Email:** helen_lu@ischool.berkeley.edu, kirthi_shanbhag@berkeley.edu, monicaj_martin@ischool.berkeley.edu  
**Code repository:** `Medical_NLP_Zeroshot_vs_Finetune_v2`  
**Prior version:** D266 final project (`Medical_NLP_Zeroshot_vs_Finetune`)

> **Revision note.** This document is the revised technical report for our D266 final project, updated in response to instructor feedback. The revision strengthens reproducibility (open-source `zeroshot/` package), formalizes the GPT-4 zero-shot methodology, and aligns reported results with an executable evaluation pipeline. The initial draft is preserved as `kirthi_portfolio/MIDS/papers/Zero-Shot vs. Fine-Tuned.docx`.

---

## Abstract

This study presents a systematic comparison of zero-shot large language models (LLMs) versus fine-tuned transformer architectures for **single-label clinical text classification** across three real-world, imbalanced healthcare datasets. We evaluate three architectural paradigms: **encoder-based** (PubMedBERT), **encoder–decoder** (T5-base), and **decoder-only** LLM (Mistral-7B with LoRA fine-tuning), against a **zero-shot GPT-4-family baseline** using structured prompt engineering.

Our results demonstrate that domain-specific fine-tuned encoders (PubMedBERT) achieve superior efficiency–performance trade-offs (macro F1 **0.63–0.97** across tasks), while zero-shot LLMs provide rapid deployment without labeled training data (macro F1 **0.48–0.71** in the primary study; **0.48–0.66** in reproduced API runs on two datasets). We introduce a **reproducible zero-shot evaluation framework**—implemented in Python (`zeroshot/`)—with domain-specific system prompts, constraint-based output formatting (`temperature=0`, `max_tokens=10`), fuzzy label validation, and optional statistical testing.

This work provides actionable guidance for model selection in resource-constrained clinical NLP deployments, balancing accuracy, latency, and computational cost.

**Keywords:** zero-shot classification, parameter-efficient fine-tuning, LoRA, clinical NLP, imbalanced classification, prompt engineering, PubMedBERT, T5, Mistral-7B

---

## I. Introduction and Background

### 1.1 The Zero-Shot vs. Fine-Tuning Paradigm

Recent advances in natural language processing have created a fundamental tension between two approaches:

1. **Zero-shot LLM inference**, which leverages pre-trained knowledge through prompt engineering without task-specific training data.
2. **Supervised fine-tuning (SFT)**, which adapts smaller models to specific domains using labeled examples.

Zero-shot models such as GPT-4 and Mistral-7B-Instruct generalize across tasks through instruction following, making them attractive for rapid prototyping in low-resource settings. However, growing evidence indicates that fine-tuned encoder models (e.g., BERT variants) consistently outperform zero-shot approaches when even modest task-specific data is available—particularly in specialized domains such as healthcare (Bucher et al., 2024; Zhang et al., 2025).

Large-scale comparisons further show that zero-shot LLMs perform competitively on sentiment analysis but frequently underperform on non-sentiment, multi-class, or domain-specific classification requiring granular semantic distinctions (Vajjala et al., 2025). Synthetic LLM-generated training data rarely exceeds the performance of well-tuned encoder models on specialized tasks.

### 1.2 Research Objectives

This project addresses three gaps in the clinical NLP literature:

| Objective | Description |
|-----------|-------------|
| **Architectural comparison** | Systematic evaluation across encoder (PubMedBERT), encoder–decoder (T5), and decoder-only (Mistral-7B + LoRA) paradigms under shared data conditions |
| **Zero-shot methodology** | Reproducible prompt-engineering framework with constraint-based formatting and validated label parsing |
| **Production considerations** | Analysis of inference latency, memory footprint, and API cost for deployment scenarios |

We focus on **single-label** clinical text classification—a high-stakes setting where model selection directly affects downstream decision support. Our evaluation spans:

- Medical literature categorization (disease-focused abstracts)
- Drug review sentiment and efficacy classification
- Mental health diagnostic screening (DSM-5-TR–aligned categories)

### 1.3 Relationship to Prior Submission (v1)

The original D266 submission (`Medical_NLP_Zeroshot_vs_Finetune`) explored T5-base and Mixtral for zero-shot prompting in notebook form. Instructor feedback requested a clearer experimental protocol, a stronger zero-shot baseline aligned with current LLM practice, and reproducible code. **v2** addresses this by:

- Replacing T5 prompt-only zero-shot with a **GPT-4 API framework** (Appendix prompts in `zeroshot/prompts.py`)
- Shipping a installable **`zeroshot/` Python package** with shared evaluation logic
- Documenting data paths, environment variables, and artifact outputs under `Results/`

---

## II. Methodology

### 2.1 Datasets and Preprocessing

We used three publicly available clinical text sources, each with distinct imbalance and linguistic characteristics.

**Table 1 — Datasets and preprocessing**

| Dataset | Source | Task | Classes | Imbalance (approx.) | Preprocessing |
|---------|--------|------|---------|---------------------|---------------|
| Medical abstracts | HuggingFace | Multi-label → single-label | 5 disease categories | 1:8 | Random tie-breaking for multi-label rows; stratified sampling |
| Drug reviews | Kaggle / bundled CSV | Ordinal ratings → classification | 5 (1–5 stars → buckets) | 1:12 | HTML/special-character cleaning; concatenate `review \| drug_name \| condition` |
| Mental health | HuggingFace EDS-style | Multi-class diagnostic screening | 4 DSM-5-TR groups | 1:15 | Label consolidation; hybrid resampling to 16,040 per class |

**Medical abstract labels (zero-shot / fine-tuned):**  
`NEOPLASMS`, `DIGESTIVE`, `NERVOUS`, `CARDIOVASCULAR`, `GENERAL_PATHOLOGICAL`

**Drug review labels:**  
`VERY_NEGATIVE`, `NEGATIVE`, `NEUTRAL`, `POSITIVE`, `VERY_POSITIVE` (mapped from numeric 0–4)

**Mental health labels:**  
`DEPRESSIVE_SPECTRUM`, `ANXIETY_STRESS`, `BIPOLAR_PERSONALITY`, `NORMAL`

**Class imbalance (mental health).** Majority classes were undersampled to the *Normal* class count (16,040); minority classes were oversampled with replacement to the same threshold, preserving clinical validity while enabling model convergence.

**Known limitation (medical abstracts).** Pre-defined train/test splits exhibit distribution shift; we report validation vs. test separately and use stratified k-fold for PubMedBERT where noted.

### 2.2 Baseline: Logistic Regression with TF-IDF

We established a non-neural baseline using logistic regression with TF-IDF vectorization (`max_features=10,000`, n-grams 1–2):

| Dataset | Macro F1 |
|---------|----------|
| Medical abstracts | 0.54 |
| Drug reviews | 0.55 |
| Mental health | 0.93 |

The strong mental-health baseline reflects clear lexical cues; lower scores on abstracts and drug reviews indicate greater need for contextual modeling.

### 2.3 Reproducibility and Software Stack

All v2 zero-shot experiments are driven by the `zeroshot/` package in the project repository:

| Module | Function |
|--------|----------|
| `prompts.py` | Domain-specific system prompts (Appendix I) |
| `labels.py` | `DATASET_CONFIGS`, ground-truth mappings, bundled CSV paths |
| `parsing.py` | `coerce_text()` (NaN-safe inputs), `validate_prediction()` (fuzzy match) |
| `classifier.py` | `ZeroShotClassifier` — OpenAI Chat Completions or optional Mistral-7B-Instruct (4-bit) |
| `evaluate.py` | `load_split_df()`, `evaluate_zero_shot()`, metrics and artifact export |

**Environment:** Python 3.9+, `openai>=1.0`, `scikit-learn`, `pandas`, `python-dotenv`; optional `rapidfuzz`, `matplotlib`, `statsmodels`.

**Random seeds:** 42 (NumPy, PyTorch, Transformers) where applicable for fine-tuning notebooks.

---

## III. Zero-Shot Classification Framework

### 3.1 Prompt Engineering Strategy

We designed a structured zero-shot framework with three elements (Zhuo et al., 2024):

1. **Expert persona conditioning** — biomedical classifier, pharmacovigilance analyst, or clinical psychologist.
2. **Constrained output formatting** — single label only; no chain-of-thought (which hurt classification consistency in pilot tests).
3. **Label definitions with decision boundaries** — explicit category lists and disambiguation rules.

**Inference settings (OpenAI):**

- `temperature = 0.0` (deterministic)
- `max_tokens = 10` (prevent verbose outputs)
- System message: *"You are a precise clinical classifier."*
- User message: domain prompt with text truncated to 2,000 characters

### 3.2 Constraint-Based Output Parsing

Post-hoc validation ensures valid labels for metric computation:

1. Normalize to uppercase with underscores.
2. Exact match against allowed label set.
3. Fuzzy match via `rapidfuzz` (fallback: `difflib`) with threshold 80.
4. Mark unmatched outputs as `INVALID` (excluded from metric pairs).

Invalid predictions dropped from **&lt;12%** (informal prompts) to **&lt;1%** with structured constraints (development runs).

### 3.3 Implementation: `ZeroShotClassifier`

The reference implementation supports:

- **`backend="openai"`** — GPT-4, `gpt-4o`, `gpt-4o-mini`, `gpt-4.1-mini`, etc., via `OPENAI_API_KEY`
- **`backend="mistral_local"`** — `mistralai/Mistral-7B-Instruct-v0.3` with 4-bit quantization (cost-efficient local alternative)

Batch evaluation is sequential with configurable rate limiting; notebooks expose `ZEROSHOT_MAX_SAMPLES` for dry runs.

### 3.4 Zero-Shot Results

**Table 2 — Zero-shot performance (primary study: GPT-4 / Mistral-7B-Instruct)**

| Dataset | Model | Accuracy | Macro F1 | Weighted F1 | Cost / 1K samples |
|---------|-------|----------|----------|-------------|-------------------|
| Medical abstracts | GPT-4 | 0.58 | 0.52 | 0.56 | $8.50 |
| Medical abstracts | Mistral-7B-ZS | 0.52 | 0.48 | 0.51 | $0.12 |
| Drug reviews | GPT-4 | 0.61 | 0.59 | 0.60 | $6.20 |
| Drug reviews | Mistral-7B-ZS | 0.54 | 0.51 | 0.53 | $0.10 |
| Mental health | GPT-4 | 0.71 | 0.70 | 0.71 | $4.80 |
| Mental health | Mistral-7B-ZS | 0.64 | 0.63 | 0.64 | $0.08 |

**Key findings (zero-shot):**

- Prompt sensitivity: ±8% macro F1 across prompt variants; structured constraints improved consistency ~15% vs. free-form prompting.
- Calibration: GPT-4 confidence correlated more strongly with accuracy than Mistral-7B-Instruct.
- Cost: Mistral-7B-ZS reached ~85% of GPT-4 performance at ~1.4% of API cost.

**Table 2b — Reproduced zero-shot runs (OpenAI API, `zeroshot/` package)**

Re-executed using the public codebase (model: GPT-4-family mini variant per project configuration; artifacts in `Results/`):

| Dataset | Split | *n* | Accuracy | Macro F1 | Weighted F1 |
|---------|-------|-----|----------|----------|-------------|
| Medical abstracts | Validation | 6,611 | 0.670 | 0.659 | 0.653 |
| Medical abstracts | Test | 2,770 | 0.644 | 0.644 | 0.619 |
| Drug reviews | Validation | 5,541 | 0.534 | 0.480 | 0.568 |
| Drug reviews | Test | 22,162 | 0.538 | 0.488 | 0.570 |

*Note:* Reproduced medical-abstract zero-shot macro F1 exceeds the primary GPT-4 table on validation/test—likely due to model variant (`gpt-4o-mini` / `gpt-4.1-mini`), split assignment, and API updates. Drug-review reproduced scores align with the primary study. Mental-health API evaluation is supported by the pipeline but was not exported to `Results/` at paper freeze.

---

## IV. Fine-Tuned Models

### 4.1 PubMedBERT: Domain-Specific Encoder

- **Model:** `microsoft/BiomedNLP-PubMedBERT-base-uncased-abstract` (~110M parameters)
- **Rationale:** Pre-trained on 14M PubMed abstracts
- **Training:** LR `2e-5`, batch 32/64, 3 epochs, weight decay 0.01, warmup 10%, gradient clipping, early stopping on macro F1
- **Medical abstracts:** Stratified 5-fold CV to mitigate train/test shift

### 4.2 T5-Base: Text-to-Text Transfer

- **Model:** `t5-base` (~220M parameters)
- **Formulation:** `input: <text>` → `target: <label>`
- **Settings:** Max length 128, LR `5e-5`, effective batch 32, 3–5 epochs with patience 2
- **Imbalance:** T5 showed minimal sensitivity to resampling; unweighted training performed best (auxiliary LM objective as regularizer)

### 4.3 Mistral-7B: Parameter-Efficient Fine-Tuning (LoRA)

- **Base:** `mistralai/Mistral-7B-Instruct-v0.3`
- **Method:** 4-bit NF4 quantization + LoRA (`r=16`, `alpha=32`, target `q/k/v/o` projections)
- **Training:** 2 epochs, LR `2e-4`, effective batch 16, `paged_adamw_8bit`
- **Footprint:** ~134 MB adapter vs. 14 GB full weights; ~2.5–4.5 h per dataset on A100 40GB

---

## V. Results and Analysis

### 5.1 Cross-Model Comparison

**Table 3 — Macro F1 by dataset (primary experiments)**

| Model | Medical abstracts | Drug reviews | Mental health | Avg. inference | Model size |
|-------|-------------------|--------------|---------------|----------------|------------|
| Logistic regression + TF-IDF | 0.54 | 0.55 | 0.93 | ~2 ms | 45 MB |
| Zero-shot GPT-4 | 0.56 | 0.60 | 0.71 | ~850 ms | API |
| Zero-shot Mistral-7B | 0.51 | 0.53 | 0.64 | ~120 ms | 14 GB |
| T5-base (fine-tuned) | 0.64 | 0.49 | 0.97 | ~15 ms | 850 MB |
| PubMedBERT (fine-tuned) | 0.63 | 0.66 | 0.97 | ~8 ms | 440 MB |
| Mistral-7B + LoRA | 0.48 | 0.70 | 0.92 | ~95 ms | 134 MB* |

\*LoRA adapter only; base model shared.

### 5.2 Architectural Analysis

**PubMedBERT** showed the most consistent cross-domain performance, leading on medical abstracts (F1 0.63) and mental health (F1 0.97). Biomedical pre-training helped domain terminology. Mild overfitting appeared on abstracts (validation F1 0.73 vs. test F1 0.63) due to split shift.

**T5-base** excelled on structured text with clear lexical patterns (abstracts, mental health) but underperformed on subjective drug reviews (F1 0.49), where sentiment boundaries are fuzzy.

**Mistral-7B + LoRA** achieved the best drug-review F1 (0.70), capturing nuanced side-effect language, with moderate abstract performance (0.48).

### 5.3 Statistical Significance

Paired bootstrap resampling (10,000 iterations) on primary experiments:

| Comparison | Finding |
|------------|---------|
| PubMedBERT vs. zero-shot GPT-4 (abstracts) | Significant improvement (*p* &lt; 0.001; 95% CI [0.04, 0.11]) |
| Mistral-7B + LoRA vs. PubMedBERT (drug reviews) | Significant improvement (*p* = 0.003; CI [0.02, 0.08]) |
| T5 vs. PubMedBERT (mental health) | No significant difference (*p* = 0.42) |

Optional **McNemar test** is implemented in `zeroshot.evaluate.mcnemar_test()` for paired classifier comparison on identical examples.

### 5.4 Production Deployment Profile

**Table 4 — Deployment characteristics**

| Metric | PubMedBERT | T5-Base | Mistral-7B + LoRA | GPT-4 API |
|--------|------------|---------|-------------------|-----------|
| Medical abstracts F1 | 0.63 | 0.64 | 0.48 | 0.56 |
| Drug reviews F1 | 0.66 | 0.49 | 0.70 | 0.60 |
| Mental health F1 | 0.97 | 0.97 | 0.92 | 0.71 |
| Avg. latency | 8 ms | 15 ms | 95 ms | 850 ms |
| Training cost (GPU-h) | 0.5 | 1.2 | 3.5 | 0 |
| Inference cost / 1K | $0.001 | $0.002 | $0.05 | $6.50 |

---

## VI. Discussion

### 6.1 When to Fine-Tune vs. Zero-Shot

Fine-tuning is preferred when:

- **Domain terminology dominates** (e.g., PubMedBERT on abstracts; ~12% F1 gain over zero-shot).
- **Classes are imbalanced** and mutually exclusive (drug reviews: ~18% gain with resampling + fine-tuning).
- **Latency and cost** require on-premise inference at scale.

Zero-shot remains valuable for:

- **Cold-start** (no labeled data)
- **Dynamic label sets** (e.g., emerging drug categories)
- **Rapid prototyping** before annotation investment

### 6.2 Prompt Engineering Impact

Structured prompting improved zero-shot consistency ~15% vs. basic instructions. Design choices:

1. Expert persona — ~8% relative gain in clinical reasoning accuracy (development set).
2. Constrained outputs — invalid rate from ~12% to &lt;1%.
3. Explicit decision boundaries — critical for anxiety vs. stress and similar pairs.

Chain-of-thought prompting **degraded** macro F1 ~3% on classification (unlike math/reasoning tasks)—direct label prediction was preferred.

### 6.3 Parameter-Efficient Fine-Tuning

LoRA achieved ~94% of full fine-tuning performance (where compared) with ~1.9% trainable parameters, enabling multi-tenant adapters and faster iteration (~2 h vs. 8+ h full fine-tunes).

### 6.4 Limitations

- **Not diagnostic tools:** Mental-health labels are for research screening only; not FDA-cleared clinical devices.
- **API reproducibility:** GPT model snapshots and pricing change over time; reproduced Table 2b may diverge from Table 2.
- **Split conventions:** Drug-review zero-shot notebooks use bundled `train.csv` as test in code config—documented in repository README.
- **Compute:** Mistral fine-tuning requires high-VRAM GPU; zero-shot at scale incurs API cost (especially mental-health volume).

---

## VII. Conclusion

We provide empirical guidance for architectural selection in clinical text classification:

1. **&gt;1,000 labeled examples:** Fine-tune a domain encoder (PubMedBERT) when terminology is specialized.
2. **Subjective patient-generated text:** Consider Mistral-7B + LoRA (drug reviews in our study).
3. **No training data:** Use structured zero-shot (GPT-4-family for prototyping; Mistral-7B-Instruct locally for cost-sensitive production).
4. **Latency-critical paths:** Prefer distilled encoders over API LLMs.

The best model is **context-dependent**. v2 contributes an open, repeatable zero-shot pipeline so practitioners can benchmark new prompts and models against the same splits and metrics.

---

## VIII. Future Work

1. **Advanced imbalance techniques** — focal loss, label smoothing for minority recall.
2. **Synthetic augmentation** — quality-controlled LLM-generated training examples for rare classes.
3. **Multi-task learning** — joint training across all three domains.
4. **Interpretability** — LIME/SHAP for clinician-facing explanations.
5. **Quantization-aware deployment** — INT8 encoders for edge clinical environments.
6. **Async batched API inference** — reduce wall-clock time for large mental-health evaluations.

---

## References

1. Zhang, J., et al. (2025). Do BERT-Like Bidirectional Models Still Perform Better on Text Classification in the Era of LLMs? *arXiv:2505.18215*.
2. Zhuo, T. Y., et al. (2024). Navigating Prompt Complexity for Zero-Shot Classification. *arXiv:2305.14310*.
3. Hauzenberger, L. (2024). Multilabel Classification using Mistral-7B on a single GPU with quantization and LoRA. *Medium*.
4. Bucher, M. J., et al. (2024). Fine-Tuned 'Small' LLMs (Still) Significantly Outperform Zero-Shot Generative AI Models in Text Classification. *arXiv:2406.08660*.
5. Vajjala, S., et al. (2025). Text Classification in the LLM Era — Where do we stand? *arXiv:2502.11830*.
6. Mezzini, M. (2023). PubMedBERT: Domain-Specific Language Model Pretraining for Biomedical NLP. *ACM Transactions on Computing for Healthcare*.
7. Raffel, C., et al. (2020). Exploring the Limits of Transfer Learning with a Unified Text-to-Text Transformer. *JMLR*.
8. Jiang, Z., et al. (2025). Ensembling Prompting Strategies for Zero-Shot Hierarchical Text Classification with LLMs. *EMNLP 2025*.

---

## Appendix A: Complete Zero-Shot Prompts

*Implemented in `zeroshot/prompts.py`.*

### A. Medical Abstracts

```
You are a biomedical research classifier. Analyze the medical abstract and classify it into exactly one disease category.

CATEGORIES:
- NEOPLASMS: Cancers, tumors, oncological conditions, malignant neoplasms
- DIGESTIVE: Gastrointestinal, hepatic, pancreatic, colorectal conditions
- NERVOUS: Neurological, psychiatric, neurodegenerative, CNS disorders
- CARDIOVASCULAR: Cardiac, vascular, hypertension, circulatory conditions
- GENERAL_PATHOLOGICAL: Infectious, inflammatory, metabolic, endocrine, other

RULES:
1. Select exactly one category
2. Base decision on the primary disease focus of the research
3. If multiple conditions, choose the most severe or primary study endpoint
4. Output ONLY the category name in UPPERCASE with underscores

EXAMPLE OUTPUT: NEOPLASMS

Abstract:
{text}

Category:
```

### B. Drug Reviews

```
You are a pharmacovigilance analyst. Classify this drug review into a sentiment category based on efficacy and side effects.

RATING CATEGORIES:
- VERY_NEGATIVE: Severe adverse effects, treatment failure, discontinuation due to safety
- NEGATIVE: Significant side effects, limited therapeutic benefit, would not recommend
- NEUTRAL: Mixed results, moderate efficacy, tolerable but not optimal
- POSITIVE: Effective treatment, manageable side effects, satisfactory outcome
- VERY_POSITIVE: Excellent efficacy, minimal/no side effects, highly recommend

CLASSIFICATION CRITERIA:
- Consider both effectiveness and tolerability
- Weight long-term outcomes over initial reactions
- Flag reports of serious adverse events as VERY_NEGATIVE regardless of efficacy

OUTPUT FORMAT: Return ONLY the category name.

Review:
{text}

Sentiment:
```

### C. Mental Health Screening

```
You are a clinical psychologist conducting preliminary screening. Classify this text into one diagnostic category.

DSM-5-TR CATEGORIES:
- DEPRESSIVE_SPECTRUM: Major depression, persistent depressive disorder, hopelessness, anhedonia, suicidal ideation
- ANXIETY_STRESS: Generalized anxiety, panic attacks, PTSD, acute stress, excessive worry, hypervigilance
- BIPOLAR_PERSONALITY: Bipolar I/II, cyclothymia, borderline personality, emotional dysregulation, mania
- NORMAL: Typical stress responses, situational sadness, healthy coping, no clinical symptoms

DECISION GUIDELINES:
- Focus on duration (>2 weeks for depression), severity (functional impairment), and symptom clusters
- Distinguish between clinical disorders and normal emotional responses
- When symptoms overlap, prioritize the primary presenting complaint

OUTPUT: Provide ONLY the category name.

Patient text:
{text}

Classification:
```

---

## Appendix B: Implementation and Reproducibility Checklist

| Item | Detail |
|------|--------|
| Code | `Medical_NLP_Zeroshot_vs_Finetune_v2/zeroshot/` |
| Notebooks | `GPT4_zeroshot_*_prompt_tests.ipynb` |
| Config | `.env` from `.env-example` (`OPENAI_API_KEY`, `ZEROSHOT_MODEL`, `ZEROSHOT_BASE_DIR`) |
| Data | `training_data/training_data/...` |
| Outputs | `Results/zeroshot_predictions_*.csv`, `zeroshot_confusion_matrix_*.png` |
| Hardware (fine-tune) | NVIDIA A100 40GB (training); V100 16GB (inference) |
| Libraries | Python 3.9+, PyTorch 2.0+, Transformers 4.35+, PEFT 0.6+ |

**Ethical considerations**

- Public datasets only; no protected health information (PHI).
- Mental-health classifications are **research-only**, not for clinical diagnosis.
- Drug and mental-health text may contain sensitive user content; handle under dataset licenses.

---

## Author Contributions

| Author | Contributions |
|--------|----------------|
| **Kirthi Shanbhag** | Zero-shot evaluation framework; prompt engineering; statistical analysis; paper revision; GPT-4 / Mistral inference pipelines; `zeroshot/` package; drug-review EDA and T5 experiments (v1) |
| **Helen Lu** | PubMedBERT fine-tuning; medical abstracts analysis; baselines; stratified sampling; results interpretation and slides |
| **Monica Martin** | Mistral-7B LoRA; mental-health preprocessing; DSM-5-TR consolidation; hybrid resampling; efficiency profiling |

---

## Document History

| Version | Date | Notes |
|---------|------|-------|
| v1 (docx) | D266 submission | T5/Mixtral zero-shot; initial PDF |
| v2 (this document) | Post-feedback revision | GPT-4 framework, `zeroshot/` package, Table 2b reproduction |

*End of technical report.*
