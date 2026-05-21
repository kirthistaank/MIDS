# Zero-Shot vs. Fine-Tuned (v2)

Clinical text classification comparing **zero-shot LLMs** (GPT-4 family via API) with **fine-tuned transformers** (PubMedBERT, T5, Mistral-7B + LoRA) on three healthcare datasets.

**Paper:** [`docs/Zero-Shot vs. Fine-Tuned.pdf`](docs/Zero-Shot%20vs.%20Fine-Tuned.pdf)  
**Prior report:** [`docs/D266_FinalProject_Report.pdf`](docs/D266_FinalProject_Report.pdf) (T5/Mixtral zero-shot experiments; superseded for zero-shot)

---

## What this repo does

| Paradigm | Models | Where |
|----------|--------|--------|
| Zero-shot | GPT-4 / `gpt-4o-mini` / `gpt-4.1-mini` (OpenAI API); optional Mistral-7B-Instruct (local) | `zeroshot/` + `GPT4_zeroshot_*` notebooks |
| Fine-tuned | PubMedBERT, T5-base, Mistral-7B + LoRA | Root `*.ipynb` + `training_data/**/Mistral_*.ipynb` |

v2 replaces the original **T5 prompt-only** zero-shot notebooks (`archieve/T5_zeroshot_*`) with a reproducible **prompt-engineering framework**: domain-specific system prompts, `temperature=0`, short constrained outputs, fuzzy label parsing (`rapidfuzz` / `difflib`), and saved metrics under `Results/`.

---

## Repository layout

```
├── README.md
├── requirements.txt
├── .env-example              # copy to .env (not committed with secrets)
│
├── docs/
│   ├── Zero-Shot vs. Fine-Tuned.pdf
│   └── D266_FinalProject_Report.pdf
│
├── zeroshot/                   # shared zero-shot library
│   ├── prompts.py              # Appendix I prompt templates
│   ├── labels.py               # per-dataset label vocab + CSV paths
│   ├── parsing.py              # coerce_text, validate_prediction
│   ├── classifier.py           # ZeroShotClassifier (OpenAI / Mistral local)
│   └── evaluate.py             # load_split_df, evaluate_zero_shot, mcnemar_test
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
├── Results/                    # zeroshot_predictions_*.csv, confusion matrices
├── training_data/      # bundled train/val/test CSVs
└── archieve/                   # legacy notebooks (incl. T5_zeroshot_*)
```

---

## Zero-shot package (`zeroshot/`)

| Module | Role |
|--------|------|
| `prompts.py` | `MEDICAL_SYSTEM_PROMPT`, `DRUG_SYSTEM_PROMPT`, `MENTAL_HEALTH_PROMPT` |
| `labels.py` | `DATASET_CONFIGS`, ground-truth maps (numeric / string → paper labels) |
| `parsing.py` | `coerce_text()` (NaN-safe), `validate_prediction()` (exact + fuzzy match) |
| `classifier.py` | `ZeroShotClassifier` — OpenAI chat API or 4-bit Mistral local |
| `evaluate.py` | Load CSVs, run batch inference, sklearn metrics, save plots/CSVs |

**Label vocabularies (zero-shot output):**

- **Medical abstracts:** `NEOPLASMS`, `DIGESTIVE`, `NERVOUS`, `CARDIOVASCULAR`, `GENERAL_PATHOLOGICAL`
- **Drug reviews:** `VERY_NEGATIVE` … `VERY_POSITIVE` (mapped from 0–4)
- **Mental health:** `DEPRESSIVE_SPECTRUM`, `ANXIETY_STRESS`, `BIPOLAR_PERSONALITY`, `NORMAL` (from `status_combined`)

---

## Quick start

### 1. Install

```bash
cd Medical_NLP_Zeroshot_vs_Finetune_v2
pip install -r requirements.txt
```

### 2. Configure environment

```bash
cp .env-example .env
```

Edit `.env`:

```bash
OPENAI_API_KEY=sk-...
ZEROSHOT_MODEL=gpt-4o-mini          # or gpt-4.1-mini; use a model your project can access
ZEROSHOT_BASE_DIR=                  # leave empty for auto-detect, or absolute path to this repo root
```

**Important:** `ZEROSHOT_BASE_DIR` must be the **project root** (the folder that contains `zeroshot/` and `training_data/`), not `training_data/` alone. If mis-set, `evaluate.resolve_base_dir()` walks upward until it finds `zeroshot/__init__.py`.

Notebooks load `.env` via `python-dotenv` (see first cells in `GPT4_zeroshot_*` notebooks).

### 3. Run a notebook

Open one of:

- `GPT4_zeroshot_MedicalAbstract_prompt_tests.ipynb`
- `GPT4_zeroshot_Drugreview_prompt_tests.ipynb`
- `GPT4_zeroshot_MentalHealth_prompt_tests.ipynb`

Run all cells. Outputs land in `Results/`:

- `zeroshot_predictions_{dataset}_{split}_openai.csv`
- `zeroshot_confusion_matrix_{dataset}_{split}_openai.png`

### 4. Dry run (fewer API calls)

```bash
export ZEROSHOT_MAX_SAMPLES=50
```

Or set in the notebook before calling `evaluate_zero_shot`.

---

## Environment variables

| Variable | Default | Description |
|----------|---------|-------------|
| `OPENAI_API_KEY` | — | Required for `ZEROSHOT_BACKEND=openai` |
| `ZEROSHOT_MODEL` | `gpt-4o-mini` (notebook) | OpenAI model name; many accounts lack `gpt-4` — use `gpt-4o-mini` or `gpt-4.1-mini` |
| `ZEROSHOT_BACKEND` | `openai` | Set `mistral_local` for GPU inference with Mistral-7B-Instruct |
| `ZEROSHOT_BASE_DIR` | auto (package parent) | Repo root; do not point only at `training_data/` |
| `ZEROSHOT_MAX_SAMPLES` | all rows | Cap samples per split (e.g. `50`) |
| `ZEROSHOT_LOAD_4BIT` | `1` | Use 4-bit quantization for local Mistral |

---

## Programmatic API

```python
import os
from dotenv import load_dotenv

load_dotenv()

from zeroshot.classifier import ZeroShotClassifier
from zeroshot.evaluate import evaluate_zero_shot, load_split_df, resolve_base_dir
from zeroshot.labels import DATASET_CONFIGS

config_key = "drug_review"
config = DATASET_CONFIGS[config_key]
base = resolve_base_dir()

clf = ZeroShotClassifier(
    model=os.getenv("ZEROSHOT_MODEL", "gpt-4o-mini"),
    backend="openai",
    temperature=0.0,
    max_tokens=10,
)

val_df = load_split_df(config, "validation", base)
results = evaluate_zero_shot(
    val_df,
    config_key,
    clf,
    dataset_name="validation",
    results_dir=os.path.join(base, "Results"),
)
print(results["f1_macro"])
```

---

## Bundled data paths

CSV paths are resolved from the **repo root** via `labels.py` (`bundled_val` / `bundled_test`):

| Dataset | Validation | Test |
|---------|------------|------|
| Medical abstracts | `training_data/.../Medical_Abstract/train_medical_abstract (1).csv` | `.../test_medical_abstract (1).csv` |
| Drug reviews | `.../Drug_Review/val (2).csv` | `.../Drug_Review/train.csv` |
| Mental health | `.../Mental_Health/Train_Test_Val_data/val.csv` | `.../test.csv` |

Mental health text column: `statement`. Drug/medical use `text` or `label` as configured in `DatasetConfig`.

`load_split_df()` coerces text with `coerce_text()` and drops empty rows before evaluation.

---

## Fine-tuned experiments

Unchanged from the original D266 project:

- **PubMedBERT** — `PubMedBERT.ipynb`
- **T5** — `T5_*_finetune.ipynb` / `T5_*_Inference.ipynb`
- **Mistral LoRA** — `training_data/**/Mistral_Multiclass*.ipynb`

Run on Colab/Kaggle/local GPU as before; zero-shot does not require a GPU.

---

## Troubleshooting

| Issue | Fix |
|-------|-----|
| `ModuleNotFoundError: matplotlib` | `pip install matplotlib` (only needed when saving confusion matrices) |
| `403` / `model_not_found` for `gpt-4` | Use `gpt-4o-mini` or `gpt-4.1-mini` in `.env`; confirm model access in OpenAI dashboard |
| `FileNotFoundError` for CSV | Set `ZEROSHOT_BASE_DIR` to repo root; restart kernel after changing `.env` |
| `TypeError: 'float' object is not subscriptable` | Restart kernel after pulling latest `zeroshot/` (ensures `classifier.py` + `coerce_text` are loaded, not stale `.pyc`) |
| Stale imports after code changes | **Kernel → Restart**, re-run from top, or `importlib.reload(zeroshot.classifier)` |

---

## Model cost / speed notes

- **`gpt-4o-mini` / `gpt-4.1-mini`:** faster and cheaper; good default for development and large val/test runs.
- **`gpt-4o`:** stronger, higher cost; use on a held-out slice if mini underperforms.
- **`gpt-4`:** paper baseline; requires explicit API access on your OpenAI project.

---

## Citation

See references in [`docs/Zero-Shot vs. Fine-Tuned.pdf`](docs/Zero-Shot%20vs.%20Fine-Tuned.pdf). Prior coursework report: [`docs/D266_FinalProject_Report.pdf`](docs/D266_FinalProject_Report.pdf).

**Authors (paper):** Helen Lu, Kirthi Shanbhag, Monica Martin — UC Berkeley MIDS, D266 Natural Language Processing.
