# County-level poverty prediction (California)

Predicts **average county poverty rate** using features derived from the U.S. Census Bureau **American Community Survey (ACS)** 5-year estimates and the California **CalFresh Program Reach Index (PRI)**. The analysis lives in `PovertyPrediction_RandomForest.ipynb`.

## Problem setup

- **Target (`y`):** `Average Poverty Rate` (county-level mean across pooled ACS years in the notebook).
- **Features (`X`):** `Average PRI`, age-structure shares, share without a high-school diploma, unemployment-related fields, etc. (see the notebook after the merge step).
- **Note:** PRI is an **input feature**, not the regression target. The README previously mixed those roles; the notebook is authoritative.

## Data

- ACS tables: 2019–2021 5-year estimates (poverty and related covariates), combined in the notebook.
- PRI: California Department of Social Services CalFresh reach index, merged by county and year.
- Shipped artifact: `Data/pri_poverty_summary.csv` (county-level summary used for modeling). The notebook can regenerate this file when you run the full pipeline.

## Methodology (high level)

1. Load and clean ACS + PRI, aggregate to county-level summaries.
2. **Baseline:** predict every county’s poverty rate with the **global mean** of `y` (constant predictor).
3. **Model:** `RandomForestRegressor` with **K-fold cross-validation** on a train split; a final model is fit on the training split for hold-out metrics.
4. **Metrics:** MSE, MAE, R² on train and test splits; built-in **feature importances** from the final random forest.

The notebook does **not** currently fit ElasticNet or permutation importance; those were removed from the narrative here to match the code.

## Limitations

- Only **~58 California counties** after dropping statewide rows: small *n* means **high variance** in cross-validation and test metrics; interpret differences between folds cautiously.
- Spatial correlation between counties is not modeled explicitly.
- Strong correlation between PRI and poverty can make coefficients/feature rankings easier to interpret than “causal” effect sizes.

## How to run

1. Create a virtual environment (recommended).
2. From this directory (`CountyLevel_PovertyPrediction_InCalifornia`):

   ```bash
   pip install -r requirements.txt
   jupyter notebook PovertyPrediction_RandomForest.ipynb
   ```

3. Run **all cells in order** (or at least from data load through the CSV export) so `Data/pri_poverty_summary.csv` exists before the modeling section.

**Working directory:** Run Jupyter with the project folder as the current working directory so paths like `Data/pri_poverty_summary.csv` resolve correctly.

## Acknowledgments

Data: U.S. Census Bureau ACS 5-year estimates; California PRI as cited in the notebook.
