# Academic projects (MIDS)

This folder collects **course and portfolio projects** from the UC Berkeley Master of Information and Data Science (MIDS) track. Each subdirectory is self-contained: open its README for data setup, dependencies, and how to reproduce results.

---

## [CountyLevel_PovertyPrediction_InCalifornia](CountyLevel_PovertyPrediction_InCalifornia/)

**Theme:** Supervised learning on small-area socioeconomic data.

Predicts **county-level average poverty rate** in California using U.S. Census **ACS** 5-year estimates merged with the state **CalFresh Program Reach Index (PRI)**. The main artifact is `PovertyPrediction_RandomForest.ipynb`: ETL (optional rebuild from Excel), a **global-mean baseline**, and a **RandomForestRegressor** with cross-validation, hold-out metrics (MSE, MAE, R²), and feature importances.

- **Data:** Packaged summary at `Data/pri_poverty_summary.csv`; optional raw Excel under `Data/raw/` to regenerate.
- **Stack:** Python, Jupyter, `requirements.txt` in project root.
- **Run:** `pip install -r requirements.txt` then open the notebook from the project directory.

---

## [DataBnB](DataBnB/)

**Theme:** Regression and interpretable pricing drivers.

**Databnb** models **Airbnb nightly prices in Los Angeles** from listing-level features (capacity, room type, estimated occupancy, parsed amenities, reviews, etc.). The final write-up is Quarto/R Markdown style in `databnb_final.Rmd` (knit to PDF); preprocessing lives in `R/airbnb_prep.R`. The report targets recent listings (2024 primary frame; optional 2025 temporal holdout when data allow), with diagnostics and **dollar-scale RMSE/MAE** on holdout data.

- **Data:** Place `la-california-airbnb_listings_indetail.zip` under `data/processed/` (CSV inside the zip as documented in the project README).
- **Stack:** R, RStudio project `DataBnB.Rproj`; LaTeX/TinyTeX for PDF.
- **Contributors:** Carlos Santander, Kirthi Shanbhag, Man Vilailuck.

---

## [Global_US_DisasterTrendsAnalysis](Global_US_DisasterTrendsAnalysis/)

**Theme:** Exploratory analytics on disaster occurrence, impact, and geography.

Analyzes **global and U.S. disaster** records (EM-DAT–style public extract and related state-level frequency data) to compare regions, disaster types, timing (including seasonal definitions for storms and the U.S. Southeast), people affected, and economic damage. Research questions span climate and readiness narratives, regional resilience, and Florida / southeastern coastal patterns.

- **Entry notebook:** `Project2_DisasterData_Final.ipynb`.
- **Data:** `public_emdat_Global_techNnatural.csv`, `state_freq_data.csv` (and related files as noted in the project readme).
- **Stack:** Python 3, NumPy, pandas, Matplotlib/Seaborn; shared constants in `config.py`; `requirements.txt` for installs.
- **Contributors:** Niyanthri Naresh, Krishna Tummalapalli, and Kirthi Shanbhag (per project readme).

---

## [Medical_NLP_Zeroshot_vs_Finetune](Medical_NLP_Zeroshot_vs_Finetune/)

**Theme:** Health-related text classification — zero-shot LLMs vs. supervised transformers.

Course work on **single-label medical and health text classification**, comparing **prompt-based / zero-shot** use of large language models with **fine-tuned** architectures. Experiments span **medical abstracts**, **drug reviews**, and **mental-health** text using models such as **PubMedBERT**, **T5** (fine-tuning and inference notebooks at the repo root), and zero-shot / Mixtral-style workflows documented in the project report (with older prompt experiments under `archieve/`).

- **Key notebooks:** `PubMedBERT.ipynb`, `T5_*_finetune.ipynb`, `T5_*_Inference.ipynb`, `T5_MentalHealth_finetune&Inference.ipynb` (see subdirectory README for full layout).
- **Stack:** PyTorch, Hugging Face `transformers` / `datasets`, scikit-learn; typically run on GPU (Colab/Kaggle/local).
- **Team:** Helen Lu, Kirthi Shanbhag, Monica Martin (per project README).

---

## Suggested navigation

| If you want… | Start here |
|--------------|------------|
| California poverty + program reach features | [CountyLevel_PovertyPrediction_InCalifornia](CountyLevel_PovertyPrediction_InCalifornia/README.md) |
| LA Airbnb price modeling (R report) | [DataBnB](DataBnB/README.md) |
| Disaster trends / EM-DAT-style EDA | [Global_US_DisasterTrendsAnalysis](Global_US_DisasterTrendsAnalysis/readme.md) |
| Medical NLP: BERT / T5 / LLM comparison | [Medical_NLP_Zeroshot_vs_Finetune](Medical_NLP_Zeroshot_vs_Finetune/README.md) |

Each linked README is the source of truth for paths, data licenses, and exact reproduction steps.
