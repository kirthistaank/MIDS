# Medical NLP: Zero-Shot vs. Fine-Tuned (v2)

**A systematic evaluation of encoder, decoder, and LLM architectures for single-label clinical text classification**

This repository is an **updated version of our D266 final project**, revised in response to feedback from our professor—most notably a reproducible GPT-4 zero-shot framework, clearer methodology, and consolidated code under `zeroshot/`.

| | |
|---|---|
| **Course** | UC Berkeley MIDS — D266 Natural Language Processing |
| **Authors** | Helen Lu, Kirthi Shanbhag, Monica Martin |
| **Affiliation** | UC Berkeley School of Information |
| **Paper (PDF)** | [`docs/Zero-Shot vs. Fine-Tuned.pdf`](docs/Zero-Shot%20vs.%20Fine-Tuned.pdf) |
| **Paper (full text)** | [`docs/Zero-Shot vs. Fine-Tuned.md`](docs/Zero-Shot%20vs.%20Fine-Tuned.md) |
| **Prior work** | [`Medical_NLP_Zeroshot_vs_Finetune`](../Medical_NLP_Zeroshot_vs_Finetune/) (D266 final report; T5/Mixtral zero-shot) |

---

## Table of contents

1. [Overview](#1-overview)
2. [Research questions and contributions](#2-research-questions-and-contributions)
3. [Evolution: v1 → v2](#3-evolution-v1--v2)
4. [Datasets](#4-datasets)
5. [Methodology](#5-methodology)
6. [Models compared](#6-models-compared)
7. [Results summary (paper)](#7-results-summary-paper)
8. [Repository structure](#8-repository-structure)
9. [The `zeroshot` package](#9-the-zeroshot-package)
10. [Notebooks guide](#10-notebooks-guide)
11. [Installation and configuration](#11-installation-and-configuration)
12. [Running experiments](#12-running-experiments)
13. [Outputs and artifacts](#13-outputs-and-artifacts)
14. [Team contributions](#14-team-contributions)
15. [Troubleshooting](#15-troubleshooting)
16. [References and citation](#16-references-and-citation)

---

## 1. Overview

Healthcare text is heterogeneous: literature abstracts, patient drug reviews, and mental-health forum posts each demand different linguistic and clinical reasoning. This project asks a practical deployment question:

> **When should you fine-tune a smaller transformer versus using a zero-shot LLM with prompt engineering?**

We study **single-label classification** on three real-world, **imbalanced** clinical NLP tasks:

| Dataset | Task | Classes |
|---------|------|---------|
| Medical abstracts (HuggingFace) | Disease category from abstract text | 5 |
| Drug reviews (Kaggle / bundled CSV) | Sentiment / efficacy (1–5 stars → 5 buckets) | 5 |
| Mental health EDS (HuggingFace) | DSM-5-TR–aligned diagnostic screening | 4 |

We compare:

- **Zero-shot:** GPT-4 (API) with structured prompts; optional Mistral-7B-Instruct (local)
- **Fine-tuned:** PubMedBERT (encoder), T5-base (encoder–decoder), Mistral-7B + LoRA (decoder)

**Headline finding (paper):** Domain-specific fine-tuned encoders (especially PubMedBERT) achieve strong F1 (roughly **0.63–0.97** per task), while zero-shot LLMs offer rapid deployment without labeled data (F1 roughly **0.48–0.71**) at higher latency and API cost.

This repository (**v2**) is the **implementation companion** to the updated paper. It adds a reusable Python package (`zeroshot/`) and GPT-4 evaluation notebooks; fine-tuning notebooks are carried over from the original D266 project.

---

## 2. Research questions and contributions

### Research objectives

1. **Architectural comparison** — Encoder (PubMedBERT), encoder–decoder (T5), and decoder-only (Mistral-7B + LoRA) under shared data conditions.
2. **Zero-shot methodology** — Reproducible prompt framework with constraint-based outputs and validation.
3. **Production considerations** — Accuracy, inference latency, memory footprint, and API cost.

### What v2 contributes in code

- **`zeroshot/`** — Shared library for prompts, label mapping, OpenAI/Mistral inference, and evaluation metrics.
- **`GPT4_zeroshot_*_prompt_tests.ipynb`** — End-to-end zero-shot runs per dataset.
- **Documented paths** — Bundled CSVs under `training_data/` with automatic project-root resolution.
- **`Results/`** — Prediction CSVs and confusion matrices from zero-shot runs.

---

## 3. Evolution: v1 → v2

| Aspect | v1 (`Medical_NLP_Zeroshot_vs_Finetune`) | v2 (this repo) |
|--------|----------------------------------------|----------------|
| Primary paper | D266 final project report | `Zero-Shot vs. Fine-Tuned.pdf` |
| Zero-shot approach | T5-base natural-language prompts; Mixtral exploratory | **GPT-4 API** + Appendix I prompts |
| Zero-shot code | Inline in `archieve/T5_zeroshot_*` notebooks | **`zeroshot/`** Python package |
| Fine-tuning | PubMedBERT, T5, Mistral LoRA | **Same notebooks** (copied) |
| Label parsing | Digit extraction from T5 outputs | **Constraint + fuzzy match** on category names |

Legacy T5 zero-shot notebooks remain in `archieve/` for historical comparison only.

---

## 4. Datasets

### 4.1 Medical abstracts

- **Source:** HuggingFace medical abstract classification corpus (bundled CSVs in repo).
- **Labels (paper / zero-shot):** `NEOPLASMS`, `DIGESTIVE`, `NERVOUS`, `CARDIOVASCULAR`, `GENERAL_PATHOLOGICAL`.
- **Preprocessing:** Multi-label instances reduced via random tie-breaking; stratified train/val/test splits; known train/test distribution shift (noted in paper).
- **Bundled files:**
  - `training_data/training_data/Medical_Abstract/train_medical_abstract (1).csv` (used as validation proxy in zero-shot notebooks)
  - `.../test_medical_abstract (1).csv`

### 4.2 Drug reviews

- **Source:** Patient drug reviews with ratings; text often concatenates `review | drug_name | condition`.
- **Labels (zero-shot):** `VERY_NEGATIVE`, `NEGATIVE`, `NEUTRAL`, `POSITIVE`, `VERY_POSITIVE` (mapped from numeric 0–4).
- **Preprocessing:** HTML/special-character cleaning; severe class imbalance (1:12 ratio in paper).
- **Bundled files:**
  - `.../Drug_Review/val (2).csv` — validation
  - `.../Drug_Review/train.csv` — test split in current zero-shot config

### 4.3 Mental health

- **Source:** Mental health–related text (EDS-style posts).
- **Labels:** Consolidated to four DSM-5-TR–aligned categories: `DEPRESSIVE_SPECTRUM`, `ANXIETY_STRESS`, `BIPOLAR_PERSONALITY`, `NORMAL`.
- **Preprocessing:** Hybrid random over/undersampling to 16,040 samples per class (paper); text column `statement`, labels in `status_combined`.
- **Bundled files:**
  - `.../Mental_Health/Train_Test_Val_data/val.csv`
  - `.../Mental_Health/Train_Test_Val_data/test.csv`
  - `train_balanced.csv`, `Combined Data.csv` for fine-tuning / EDA

### 4.4 Class imbalance handling (paper)

| Dataset | Strategy |
|---------|----------|
| Medical abstracts | Random tie-break for multi-label; stratified sampling |
| Drug reviews | Cleaning + rich concatenated input; class buckets 0–4 |
| Mental health | DSM-5-TR collapse; hybrid resampling to balanced classes |

---

## 5. Methodology

### 5.1 Baseline

**Logistic regression + TF-IDF** (`max_features=10,000`, n-grams 1–2) — non-neural lower bound.

| Dataset | Macro F1 (baseline) |
|---------|---------------------|
| Medical abstracts | 0.54 |
| Drug reviews | 0.55 |
| Mental health | 0.93 |

### 5.2 Zero-shot framework (Section III, paper)

Three design elements:

1. **Expert persona conditioning** — Domain-specific system prompts (biomedical classifier, pharmacovigilance analyst, clinical psychologist).
2. **Constrained output formatting** — `temperature=0`, `max_tokens=10`, single label only.
3. **Label definitions with decision boundaries** — Explicit category lists in each prompt.

**Pipeline (implemented in `zeroshot/`):**

```
CSV row → coerce_text() → build prompt (prompts.py)
        → OpenAI chat API or Mistral local (classifier.py)
        → validate_prediction() fuzzy match (parsing.py)
        → sklearn metrics + confusion matrix (evaluate.py)
```

**Prompt templates** live in `zeroshot/prompts.py` (`MEDICAL_SYSTEM_PROMPT`, `DRUG_SYSTEM_PROMPT`, `MENTAL_HEALTH_PROMPT`).

### 5.3 Fine-tuning (Section IV, paper)

| Model | HuggingFace ID | Notes |
|-------|----------------|-------|
| PubMedBERT | `microsoft/BiomedNLP-PubMedBERT-base-uncased-abstract` | 3 epochs, LR 2e-5, stratified k-fold for medical abstracts |
| T5-base | `t5-base` | Text-to-text: input text → label token; 128 max length |
| Mistral-7B + LoRA | `mistralai/Mistral-7B-Instruct-v0.3` | 4-bit quantization, LoRA r=16, ~134MB adapters |

See respective notebooks for full hyperparameters.

---

## 6. Models compared

| Paradigm | Model | Role in project |
|----------|-------|-----------------|
| Baseline | TF-IDF + logistic regression | Lower bound |
| Zero-shot | GPT-4 / `gpt-4o-mini` / `gpt-4.1-mini` | API baseline (v2 code) |
| Zero-shot | Mistral-7B-Instruct (local) | Cost-efficient alternative |
| Fine-tuned | PubMedBERT | Biomedical encoder |
| Fine-tuned | T5-base | Encoder–decoder classification |
| Fine-tuned | Mistral-7B + LoRA | Parameter-efficient decoder |

---

## 7. Results summary (paper)

*Macro F1 unless noted. Full tables in the PDF.*

### Table 3 — Cross-model comparison (macro F1 by dataset)

| Model | Medical abstracts | Drug reviews | Mental health | Avg. inference |
|-------|-------------------|--------------|---------------|----------------|
| Logistic regression | 0.54 | 0.55 | 0.93 | ~2 ms |
| Zero-shot GPT-4 | 0.56 | 0.60 | 0.71 | ~850 ms (API) |
| Zero-shot Mistral-7B | 0.51 | 0.53 | 0.64 | ~120 ms |
| T5-base (fine-tuned) | 0.64 | 0.49 | 0.97 | ~15 ms |
| PubMedBERT (fine-tuned) | 0.63 | 0.66 | 0.97 | ~8 ms |
| Mistral-7B + LoRA | 0.48 | 0.70 | 0.92 | ~95 ms |

### Table 2 — Zero-shot detail (GPT-4 vs Mistral-7B-ZS)

Includes accuracy, macro/weighted F1, average confidence, and estimated cost per 1K samples. GPT-4 shows better calibration; Mistral-7B-ZS reaches ~85% of GPT-4 performance at ~1.4% of cost (paper).

### Practical guidance (Section 6)

**Prefer fine-tuning when:**

- Domain-specific terminology matters (e.g., PubMedBERT on abstracts).
- Classes are imbalanced and mutually exclusive.
- Low latency and fixed label set are required.

**Prefer zero-shot when:**

- No labeled data (cold start).
- Labels change frequently.
- Prototyping task feasibility before annotation spend.

**Prompt engineering:** Structured constraints improved zero-shot consistency by ~15% vs. free-form prompts (paper).

### Reproduced artifacts in this repo

Zero-shot prediction exports (OpenAI backend) under `Results/`:

- `zeroshot_predictions_medical_abstract_{validation,test}_openai.csv`
- `zeroshot_predictions_drug_review_{validation,test}_openai.csv`
- Matching `zeroshot_confusion_matrix_*.png` when evaluation completes

Mental health zero-shot outputs are produced by running `GPT4_zeroshot_MentalHealth_prompt_tests.ipynb` (large val/test sets; API cost and runtime apply).

---

## 8. Repository structure

```
Medical_NLP_Zeroshot_vs_Finetune_v2/
│
├── README.md                 # Concise quick-start
├── README_2.md               # This document (full project reference)
├── requirements.txt
├── .env-example              # Template for secrets (copy → .env)
│
├── docs/
│   └── Zero-Shot vs. Fine-Tuned.pdf
│
├── zeroshot/                   # Zero-shot library (v2)
│   ├── __init__.py
│   ├── prompts.py
│   ├── labels.py
│   ├── parsing.py
│   ├── classifier.py
│   └── evaluate.py
│
├── GPT4_zeroshot_MedicalAbstract_prompt_tests.ipynb
├── GPT4_zeroshot_Drugreview_prompt_tests.ipynb
├── GPT4_zeroshot_MentalHealth_prompt_tests.ipynb
│
├── PubMedBERT.ipynb
├── T5_medicalAbstract_finetune.ipynb
├── T5_MedicalAbstract_Inference.ipynb
├── T5_drugreview_finetune.ipynb
├── T5_drugreview_inference.ipynb
├── T5_MentalHealth_finetune&Inference.ipynb
│
├── Results/                  # Zero-shot metrics exports
├── training_data/    # Bundled CSVs + Mistral/T5 sub-notebooks
│   └── training_data/
│       ├── Medical_Abstract/
│       ├── Drug_Review/
│       └── Mental_Health/
│
└── archieve/                 # Legacy experiments (T5_zeroshot_*, EDA, etc.)
    └── README.md
```

---

## 9. The `zeroshot` package

### Module reference

| File | Purpose |
|------|---------|
| `prompts.py` | Paper Appendix I prompt strings; `DOMAIN_PROMPTS` keyed by dataset |
| `labels.py` | `DATASET_CONFIGS`, label vocabularies, numeric/string → paper label maps, bundled CSV relative paths |
| `parsing.py` | `coerce_text()` — safe string conversion (NaN, None, floats); `validate_prediction()` — exact + fuzzy label match |
| `classifier.py` | `ZeroShotClassifier` — OpenAI Chat Completions or 4-bit Mistral-7B-Instruct |
| `evaluate.py` | `resolve_base_dir()`, `canonical_project_root()`, `load_split_df()`, `evaluate_zero_shot()`, `mcnemar_test()` |

### `DATASET_CONFIGS` keys

- `medical_abstract`
- `drug_review`
- `mental_health`

### Ground-truth mapping examples

**Drug reviews (numeric → zero-shot label):**

| CSV `label` | Zero-shot label |
|-------------|-----------------|
| 0 | VERY_NEGATIVE |
| 1 | NEGATIVE |
| 2 | NEUTRAL |
| 3 | POSITIVE |
| 4 | VERY_POSITIVE |

**Mental health (`status_combined` → zero-shot label):**

| CSV value | Zero-shot label |
|-----------|-----------------|
| Anxiety/Stress | ANXIETY_STRESS |
| Bipolar/Personality | BIPOLAR_PERSONALITY |
| Depressive_Spectrum | DEPRESSIVE_SPECTRUM |
| Normal | NORMAL |

---

## 10. Notebooks guide

### Zero-shot (start here for v2)

| Notebook | `CONFIG_KEY` | Typical runtime |
|----------|--------------|-----------------|
| `GPT4_zeroshot_MedicalAbstract_prompt_tests.ipynb` | `medical_abstract` | Moderate (thousands of API calls) |
| `GPT4_zeroshot_Drugreview_prompt_tests.ipynb` | `drug_review` | Moderate |
| `GPT4_zeroshot_MentalHealth_prompt_tests.ipynb` | `mental_health` | Long (9k+ val rows) |

Each notebook:

1. Loads `.env` via `python-dotenv`
2. Adds project root to `sys.path`
3. Builds `ZeroShotClassifier` from `ZEROSHOT_MODEL` / `ZEROSHOT_BACKEND`
4. Loads val/test via `load_split_df()`
5. Calls `evaluate_zero_shot()` → writes to `Results/`

### Fine-tuning (from original project)

| Notebook | Task |
|----------|------|
| `PubMedBERT.ipynb` | Medical abstracts — encoder fine-tune |
| `T5_medicalAbstract_finetune.ipynb` / `T5_MedicalAbstract_Inference.ipynb` | Medical abstracts — T5 |
| `T5_drugreview_finetune.ipynb` / `T5_drugreview_inference.ipynb` | Drug reviews — T5 |
| `T5_MentalHealth_finetune&Inference.ipynb` | Mental health — T5 |
| `training_data/**/Mistral_Multiclass*.ipynb` | Mistral-7B LoRA per domain |
| `training_data/**/Baseline_*.ipynb` | Baselines (logistic, few-shot Mistral) |

### Legacy (archived)

`archieve/T5_zeroshot_*` — superseded by GPT-4 framework; kept for comparison only.

---

## 11. Installation and configuration

### Requirements

- Python 3.9+
- **Zero-shot:** `openai`, `pandas`, `scikit-learn`, `python-dotenv`, `tqdm`, `matplotlib` (for plots), optional `rapidfuzz`
- **Fine-tuning:** `torch`, `transformers`, `datasets`, `accelerate`, `peft`, `bitsandbytes` (GPU)
- **Optional stats:** `statsmodels` (McNemar test)

```bash
cd Medical_NLP_Zeroshot_vs_Finetune_v2
pip install -r requirements.txt
```

### Environment file

```bash
cp .env-example .env
```

Edit `.env`:

```bash
OPENAI_API_KEY=your_key_here
ZEROSHOT_MODEL=gpt-4o-mini
# Optional: absolute path to THIS repo root (folder containing zeroshot/)
ZEROSHOT_BASE_DIR=
```

| Variable | Description |
|----------|-------------|
| `OPENAI_API_KEY` | Required for OpenAI backend |
| `ZEROSHOT_MODEL` | e.g. `gpt-4o-mini`, `gpt-4.1-mini`; paper uses `gpt-4` where API access allows |
| `ZEROSHOT_BACKEND` | `openai` (default) or `mistral_local` |
| `ZEROSHOT_BASE_DIR` | Repo root only — **not** `training_data/` alone |
| `ZEROSHOT_MAX_SAMPLES` | Integer cap for quick tests (e.g. `50`) |
| `ZEROSHOT_LOAD_4BIT` | `1` for 4-bit Mistral (default) |

**Path resolution:** `canonical_project_root()` walks upward from any subfolder until it finds `zeroshot/__init__.py`, so misconfigured `ZEROSHOT_BASE_DIR` is often auto-corrected.

**Security:** Never commit `.env` or paste API keys into notebooks; use `load_dotenv()` only.

---

## 12. Running experiments

### A. Zero-shot via notebook (recommended)

```bash
jupyter notebook GPT4_zeroshot_Drugreview_prompt_tests.ipynb
```

Run all cells. Restart kernel after changing `.env` or updating `zeroshot/` source.

### B. Zero-shot via Python

```python
import os
from dotenv import load_dotenv

load_dotenv()

from zeroshot.classifier import ZeroShotClassifier
from zeroshot.evaluate import evaluate_zero_shot, load_split_df, resolve_base_dir
from zeroshot.labels import DATASET_CONFIGS

key = "drug_review"
cfg = DATASET_CONFIGS[key]
base = resolve_base_dir()

clf = ZeroShotClassifier(
    model=os.getenv("ZEROSHOT_MODEL", "gpt-4o-mini"),
    backend="openai",
    temperature=0.0,
    max_tokens=10,
)

df = load_split_df(cfg, "validation", base)
out = evaluate_zero_shot(
    df, key, clf,
    dataset_name="validation",
    max_samples=int(os.getenv("ZEROSHOT_MAX_SAMPLES", "0")) or None,
    results_dir=os.path.join(base, "Results"),
)
print(f"Macro F1: {out['f1_macro']:.4f}")
```

### C. Fine-tuning

Open the relevant `T5_*` or `PubMedBERT.ipynb` on **GPU** (Colab, Kaggle, or local). Data paths in those notebooks may still reference Google Drive (`d266/FinalProject/`); adjust `base_dir` or copy bundled CSVs to match.

### D. Cost-conscious development

1. Set `ZEROSHOT_MAX_SAMPLES=50` in `.env`.
2. Use `gpt-4o-mini` or `gpt-4.1-mini` instead of `gpt-4`.
3. Validate on **validation** split before full **test**.

---

## 13. Outputs and artifacts

### `Results/` (zero-shot)

| Pattern | Contents |
|---------|----------|
| `zeroshot_predictions_{dataset}_{split}_openai.csv` | `text`, `true_label`, `predicted_label`, `raw_output`, `correct` |
| `zeroshot_confusion_matrix_{dataset}_{split}_openai.png` | Sklearn confusion matrix plot |

### `evaluate_zero_shot()` return dict

- `accuracy`, `f1_macro`, `f1_weighted`, `precision`, `recall`
- `y_true`, `y_pred`
- `confusion_matrix_path`, `predictions_path`

### Fine-tuned outputs

Checkpoints and figures are written per notebook (often Colab Drive paths). See individual notebooks for `output_dir` settings.

---

## 14. Team contributions

### Paper (`Zero-Shot vs. Fine-Tuned.pdf`)

| Author | Contributions |
|--------|----------------|
| **Kirthi Shanbhag** | Zero-shot evaluation framework, prompt engineering, statistical analysis, paper writing, GPT-4 / Mistral inference pipelines |
| **Helen Lu** | PubMedBERT fine-tuning, medical abstracts analysis, baselines, stratified sampling, results interpretation |
| **Monica Martin** | Mistral-7B LoRA, mental health preprocessing, DSM-5-TR consolidation, hybrid resampling, efficiency profiling |

### Original D266 project (v1 repo)

Additional early work on T5 fine-tuning, drug-review EDA, dataset sourcing, and Mixtral experiments — see [`Medical_NLP_Zeroshot_vs_Finetune/README.md`](../Medical_NLP_Zeroshot_vs_Finetune/README.md).

### Contact

- Helen Lu — helen_lu@ischool.berkeley.edu  
- Kirthi Shanbhag — kirthi_shanbhag@berkeley.edu  
- Monica Martin — monicaj_martin@ischool.berkeley.edu  

---

## 15. Troubleshooting

| Symptom | Likely cause | Fix |
|---------|--------------|-----|
| `403` / `model_not_found` for `gpt-4` | Project lacks GPT-4 access | Use `gpt-4o-mini` or `gpt-4.1-mini` in `.env` |
| `FileNotFoundError` for CSV | Wrong `ZEROSHOT_BASE_DIR` | Point to repo root; restart kernel |
| Triple `training_data` in path | Base dir set to data subfolder | Use `canonical_project_root` (automatic in latest `evaluate.py`) |
| `TypeError: 'float' object is not subscriptable` | NaN text or stale `classifier.pyc` | Pull latest code; **restart kernel**; ensure `zeroshot/classifier.py` exists |
| `ModuleNotFoundError: matplotlib` | Plotting optional dep missing | `pip install matplotlib` |
| `ModuleNotFoundError: zeroshot.classifier` | Deleted `classifier.py` + old cache | Restore from repo; delete `zeroshot/__pycache__/classifier.*.pyc` |
| Very slow mental health run | ~9k+ API calls per split | Use `ZEROSHOT_MAX_SAMPLES`; run val before test |
| High API bill | Full test sets with GPT-4 | Use mini model; sample rows first |

---

## 16. References and citation

### Primary report

```text
Lu, H., Shanbhag, K., & Martin, M. (2025).
Zero-Shot vs. Fine-Tuned: A Systematic Evaluation of Encoder, Decoder,
and LLM Architectures for Clinical Text Classification.
UC Berkeley MIDS, D266 Natural Language Processing.
```

PDF: [`docs/Zero-Shot vs. Fine-Tuned.pdf`](docs/Zero-Shot%20vs.%20Fine-Tuned.pdf)

### Related literature (from project)

- Zhang et al. (2025). *Do BERT-Like Bidirectional Models Still Perform Better on Text Classification in the Era of LLMs?* arXiv:2505.18215  
- Bucher et al. (2024). *Fine-Tuned 'Small' LLMs Still Significantly Outperform Zero-Shot Generative AI Models in Text Classification.* arXiv:2406.08660  
- Vajjala et al. (2025). *Text Classification in the LLM Era – Where do we stand?* arXiv:2502.11830  
- Zhuo et al. (2024). *Navigating Prompt Complexity for Zero-Shot Classification.* arXiv:2305.14310  

### Prior coursework artifact

D266 final project report and T5/Mixtral zero-shot code: [`../Medical_NLP_Zeroshot_vs_Finetune/`](../Medical_NLP_Zeroshot_vs_Finetune/)

---

## Quick links

| Document | Use when |
|----------|----------|
| **README_2.md** (this file) | Full project context, methods, results, team |
| **README.md** | Short setup and daily development |
| **Paper (`.md` / PDF)** | Full technical report and formal tables |
| **`.env-example`** | First-time API configuration |

---

*Last updated for repository layout and `zeroshot/` implementation as of v2 (GPT-4 zero-shot framework).*
