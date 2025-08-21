Poverty Prediction Using Random Forest Regression
Overview
This project predicts poverty rates at the county level using data from the American Community Survey (ACS) 5-Year Estimates. The goal is to build a machine learning model that estimates poverty indicators to assist in social and economic analysis.

Data Description
Dataset: ACS 2019 (and other years where applicable) 5-Year Estimates.

Features include demographics, education levels, employment status, and other socio-economic indicators by county.

Target variable: Poverty Rate Index (PRI) and poverty-related metrics for various age groups.

Methodology
Data Loading and Preprocessing:
Combined datasets are cleaned and merged. Feature engineering includes selecting significant predictors.

Exploratory Data Analysis (EDA):
Visual exploration using seaborn, matplotlib, and plotly to understand feature distributions and correlations.

![Example Distribution Plot](./images/eda_distributionrelation Heatmap](./images/eda_correlation

Used Random Forest Regressor from scikit-learn with cross-validation and train/test splits.

Model hyperparameters tuned to optimize performance.

Baseline comparison with ElasticNet regression.

Evaluation Metrics:

Mean Squared Error (MSE)

Mean Absolute Error (MAE)

R^2 Score (Coefficient of determination)

Feature Importance:

Assessed impact of variables on the model using permutation importance.

![Feature Importance Plot](./images/feature_import

The Random Forest model achieved strong predictive accuracy, with low MSE and robust R^2 scores on test data.

Key predictors included education level indicators, unemployment rates, and demographic distributions.

Visualizations helped identify counties with higher poverty risk and better informed socio-economic interventions.

Conclusions
This data-driven approach with Random Forest regression successfully estimates poverty metrics, demonstrating the value of machine learning in public policy and economic planning.

How to Run
Clone the repo.

Install dependencies listed in requirements.txt (e.g., scikit-learn, pandas, matplotlib, seaborn, plotly).

Run the Jupyter notebook to reproduce analysis and visuals.

Acknowledgments
Data sourced from the American Community Survey (ACS) 5-Year Estimates.


