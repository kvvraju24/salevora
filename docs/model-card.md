# Northstar model card

## Intended use

Historical portfolio analysis and demonstration of store-level sales forecasting on the Rossmann archive. Not an operational replenishment, pricing, financial planning, or SKU forecasting system.

## Evaluation design

A single chronological holdout spans June 20–July 31, 2015. The fitting period ends June 19, 2015. The holdout is never used to fit models or historical-mean features. All three approaches share 46,830 evaluation rows.

XGBoost and Ridge fit positive sales on open days after `log1p` transformation. Their predictions are transformed with `expm1`, clipped to zero, and set to zero on scheduled closed days. The historic baseline uses mean open, positive sales from the fitting partition’s last 365 days, grouped by store/weekday/promotion with progressively broader fallbacks.

XGBoost: 360 estimators, depth 7, learning rate 0.055, subsample 0.85, column sample 0.9, minimum child weight 12, histogram trees, seed 42. Ridge: alpha 20, one-hot categorical inputs, standardized numeric features, LSQR solver. Full-fit models are trained separately after holdout evaluation.

## Metrics

- **MAE:** mean absolute prediction error over all store-days.
- **RMSE:** square root of mean squared error over all store-days.
- **RMSPE:** square root of mean squared percentage error, excluding actual zero sales.
- **WAPE:** sum of absolute errors divided by sum of actual sales, including closed days.
- **Bias:** sum(prediction − actual) divided by sum(actual); positive means overprediction.

| Model | MAE | RMSE | RMSPE | WAPE | Bias |
| --- | ---: | ---: | ---: | ---: | ---: |
| XGBoost | 545.48 | 843.28 | 13.27% | 9.09% | +2.19% |
| Ridge | 723.02 | 1,233.69 | 17.15% | 12.04% | +0.22% |
| Baseline | 589.20 | 944.68 | 13.84% | 9.82% | +0.10% |

Values above are the full-network validation results produced by this run. Store-filtered dashboard values are recalculated over that store’s validation rows.

## Feature provenance and missing values

21 features use Store, calendar date, known promotions and holidays, store format/assortment, competition distance and age, recurring-promotion status, and training-partition historical means. Actual Customers and Sales are not predictor columns. Historical target means are fitted on training rows (not out-of-fold within training), so training-fit performance is intentionally not reported. Holdout metrics are computed only on future dates.

Three stores lack competition distance; unknown distance and competition age use −1. Missing recurring-promotion fields produce no active recurring promotion. Eleven future Open values are assumed open and disclosed in the quality page. Scheduled closures receive zero predictions. Fifty-four observed open zero-sales days are excluded from fitting but remain in evaluation when they occur in the holdout.

The 33,121 absent store-days are not fabricated or filled with zero. The source has a reduced store cohort during the second half of 2014. Growth reports compare observed totals, and the overview discloses unequal record counts when the selected comparison periods differ in coverage.

## Explanations

[Native XGBoost prediction documentation](https://xgboost.readthedocs.io/en/stable/prediction.html) and [the Python API reference](https://xgboost.readthedocs.io/en/stable/python/python_api.html) describe `pred_contribs`, which returns Tree SHAP feature contributions and a bias column.

Global importance is mean absolute SHAP over 1,000 seeded open forecast observations. Per-store explanations use the first scheduled open forecast date. Contributions are in **log(1 + sales)**. Bias plus contributions reconstructs that raw output; applying `expm1` gives the predicted sales. SHAP values are not currency amounts or causal effects. The app shows the base and predicted revenue in sales units and labels the contribution chart separately.

## Uncertainty and limitations

- Individual-store ranges add/subtract the holdout’s 80th-percentile absolute open-day error for the selected model. They are **indicative historical error ranges**, not calibrated 80% future confidence intervals.
- The same holdout is used for evaluation and error-range estimation. There is no separate calibration set or rolling-origin validation.
- No aggregate confidence interval is shown, because errors across stores can be correlated.
- No future actuals are supplied. Production error, drift, and forecast calibration cannot be measured.
- A single holdout does not establish performance across seasons. There is no hyperparameter search, holiday-specific validation, causal promotion estimation, or fairness assessment.
- Log-target regression is not explicitly corrected for retransformation bias. Model bias is reported.
- Store identity and historical means make this a known-store forecasting model. New-store generalization is not evaluated.
- Promotions and holidays are assumed known from the supplied schedule. Results depend on their accuracy.
- Revenue is reported in dataset sales units; no currency is assumed. There is no inventory, SKU, product-price, or competitor-sales modeling.

## Reproducibility

Run `python -m backend.pipeline` from the project root. `manifest.json` records source SHA-256 hashes, feature names, seed, split dates, all scores, duration, and build timestamp. Model artifacts, forecasts, and explanations are saved locally; no private source data leaves the machine. Restart the API after any rebuild.

Promising extensions: rolling-origin evaluation, a distinct calibration period, lag features with carefully maintained horizon semantics, grouped uncertainty estimation, scheduled ingestion, and post-deployment monitoring once new actuals exist.
