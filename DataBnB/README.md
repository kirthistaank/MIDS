# Databnb

**Summary:**  
This project models Airbnb prices in Los Angeles using listing-level features. The final model explains ~36% of price variation and highlights capacity, room type, estimated occupancy, and amenities such as hot tubs. The report includes diagnostics, **dollar-scale RMSE/MAE** on the holdout set, and an optional **2025 temporal holdout** when the extract has enough rows.

## Layout

| Path | Purpose |
|------|---------|
| [`DataBnB.Rproj`](DataBnB.Rproj) | RStudio project (opens with working directory set to this folder) |
| [`databnb_final.Rmd`](databnb_final.Rmd) | Final report — knit to PDF |
| [`R/airbnb_prep.R`](R/airbnb_prep.R) | `prepare_listings_for_year()` and amenity helpers (sourced by the Rmd) |
| [`data/processed/`](data/processed/) | Place `la-california-airbnb_listings_indetail.zip` here (see below) |
| [`data/raw/`](data/raw/) | Optional: store untouched downloads |
| [`outputs/`](outputs/) | Optional: saved figures or exported tables |

## Data

Add the processed zip (same name as in the original analysis) to:

`data/processed/la-california-airbnb_listings_indetail.zip`

The Rmd reads the CSV member `la-california-airbnb_listings_indetail.csv` from inside that zip. Large data files are **gitignored** by default (see `.gitignore`); keep a short note in your portfolio README about where you obtained the extract (e.g. Inside Airbnb).

## Reproduce

1. Open `DataBnB.Rproj` in RStudio (or `setwd()` to this directory).
2. Install dependencies (recommended: [**renv**](https://rstudio.github.io/renv/)):
   - First-time setup: in R, run `install.packages("renv")` then `renv::init()` to capture packages, or `renv::restore()` if this repo includes an `renv.lock`.
3. Ensure [TinyTeX](https://yihui.org/tinytex/) (or another LaTeX distribution) is installed for PDF output (`tinytex::install_tinytex()` if needed).
4. Knit `databnb_final.Rmd` to PDF.

**Note:** The document uses `set.seed(42)` before the train/test split so results are reproducible.

## Contributors

Thanks to fellow students Carlos Santander and Man Vilailuck for their contributions to this project.
