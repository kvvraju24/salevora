"""Reproducible Rossmann training, holdout evaluation, and forecast artifacts.

Run from the repository root: .venv/bin/python -m backend.pipeline
All target-derived features are fitted exclusively on each fitting partition.
"""
import hashlib
import json
import time
from datetime import datetime, timezone
import joblib
import numpy as np
import pandas as pd
import xgboost as xgb
from sklearn.compose import ColumnTransformer
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sklearn.linear_model import Ridge
from sklearn.pipeline import make_pipeline
from backend.runtime import ROOT, DATA, ART, MODELS, read_data, metrics

FEATURE_LABELS = {
    'Store': 'Store identity', 'DayOfWeek': 'Day of week', 'Promo': 'Promotion',
    'SchoolHoliday': 'School holiday', 'StateHoliday': 'Public holiday',
    'StoreType': 'Store format', 'Assortment': 'Assortment',
    'CompetitionDistance': 'Competitor distance', 'CompetitionMonths': 'Competition age',
    'Promo2': 'Recurring promotion', 'Promo2Active': 'Recurring promo active',
    'Year': 'Year', 'Month': 'Month', 'Day': 'Day of month', 'Week': 'Week of year',
    'Trend': 'Time trend', 'MonthSin': 'Annual seasonality (sin)',
    'MonthCos': 'Annual seasonality (cos)', 'StoreMean': 'Historical store revenue',
    'WeekdayMean': 'Store weekday pattern', 'PromoMean': 'Store promotion pattern',
}


def fit_history(train):
    recent = train[(train.Date > train.Date.max() - pd.Timedelta(days=365)) & (train.Open == 1) & (train.Sales > 0)]
    return {
        'global': float(recent.Sales.mean()),
        'store': recent.groupby('Store').Sales.mean(),
        'weekday': recent.groupby(['Store', 'DayOfWeek']).Sales.mean(),
        'promo': recent.groupby(['Store', 'DayOfWeek', 'Promo']).Sales.mean(),
        'cutoff': str(train.Date.max().date()),
    }


def features(rows, stores, history):
    d = rows.merge(stores, on='Store', how='left', validate='many_to_one')
    f = pd.DataFrame(index=d.index)
    for col in ['Store', 'DayOfWeek', 'Promo', 'SchoolHoliday']:
        f[col] = d[col].astype(float)
    f['StateHoliday'] = d.StateHoliday.map({'0': 0, 'a': 1, 'b': 2, 'c': 3}).fillna(0)
    f['StoreType'] = d.StoreType.map({'a': 0, 'b': 1, 'c': 2, 'd': 3}).fillna(-1)
    f['Assortment'] = d.Assortment.map({'a': 0, 'b': 1, 'c': 2}).fillna(-1)
    f['CompetitionDistance'] = d.CompetitionDistance.fillna(-1)
    competition_months = ((d.Date.dt.year - d.CompetitionOpenSinceYear) * 12 + d.Date.dt.month - d.CompetitionOpenSinceMonth)
    f['CompetitionMonths'] = competition_months.clip(lower=0).fillna(-1)
    f['Promo2'] = d.Promo2
    month_names = d.Date.dt.month.map({1: 'Jan', 2: 'Feb', 3: 'Mar', 4: 'Apr', 5: 'May', 6: 'Jun', 7: 'Jul', 8: 'Aug', 9: 'Sept', 10: 'Oct', 11: 'Nov', 12: 'Dec'})
    promo_started = (d.Date.dt.year * 100 + d.Date.dt.isocalendar().week.astype(int)) >= (d.Promo2SinceYear.fillna(9999) * 100 + d.Promo2SinceWeek.fillna(99))
    f['Promo2Active'] = [int(active and month in str(interval).split(',')) for month, interval, active in zip(month_names, d.PromoInterval, promo_started)]
    for name, vals in [('Year', d.Date.dt.year), ('Month', d.Date.dt.month), ('Day', d.Date.dt.day), ('Week', d.Date.dt.isocalendar().week)]:
        f[name] = vals.astype(float)
    f['Trend'] = (d.Date - pd.Timestamp('2013-01-01')).dt.days
    f['MonthSin'] = np.sin(2 * np.pi * d.Date.dt.dayofyear / 365.25)
    f['MonthCos'] = np.cos(2 * np.pi * d.Date.dt.dayofyear / 365.25)
    f['StoreMean'] = d.Store.map(history['store']).fillna(history['global'])
    f['WeekdayMean'] = history['weekday'].reindex(pd.MultiIndex.from_frame(d[['Store', 'DayOfWeek']])).to_numpy()
    f['WeekdayMean'] = f.WeekdayMean.fillna(f.StoreMean)
    f['PromoMean'] = history['promo'].reindex(pd.MultiIndex.from_frame(d[['Store', 'DayOfWeek', 'Promo']])).to_numpy()
    f['PromoMean'] = f.PromoMean.fillna(f.WeekdayMean)
    return f.astype('float32')


def train_models(rows, f):
    mask = (rows.Open.to_numpy() == 1) & (rows.Sales.to_numpy() > 0)
    X, y = f.loc[mask], np.log1p(rows.loc[mask, 'Sales'])
    boost = xgb.XGBRegressor(n_estimators=360, max_depth=7, learning_rate=0.055,
                             subsample=0.85, colsample_bytree=0.9, min_child_weight=12,
                             objective='reg:squarederror', tree_method='hist', n_jobs=4, random_state=42)
    started = time.time()
    boost.fit(X, y)
    timings = {'XGBoost': round(time.time() - started, 2)}
    cat = ['Store', 'DayOfWeek', 'StateHoliday', 'StoreType', 'Assortment', 'Month']
    numeric = [c for c in f if c not in cat]
    transform = ColumnTransformer([('category', OneHotEncoder(handle_unknown='ignore'), cat), ('numeric', StandardScaler(), numeric)])
    ridge = make_pipeline(transform, Ridge(alpha=20, solver='lsqr'))
    started = time.time()
    ridge.fit(X, y)
    timings['Ridge'] = round(time.time() - started, 2)
    timings['Baseline'] = 0.0
    return boost, ridge, timings


def predict(rows, f, boost, ridge):
    result = rows[['Store', 'Date', 'Open', 'Promo']].copy().reset_index(drop=True)
    opened = rows.Open.fillna(1).to_numpy() != 0
    for name, pred in [('XGBoost', np.expm1(boost.predict(f))), ('Ridge', np.expm1(ridge.predict(f))), ('Baseline', f.PromoMean.to_numpy())]:
        result[name] = np.where(opened, np.maximum(pred, 0), 0)
    return result


def main():
    ART.mkdir(exist_ok=True)
    started = time.time()
    train, test, stores = read_data()
    cutoff = train.Date.max() - pd.Timedelta(days=42)
    fitting, validation = train[train.Date <= cutoff].reset_index(drop=True), train[train.Date > cutoff].reset_index(drop=True)
    print(f'Loaded {len(train):,} observations / {len(stores):,} stores. Holdout: {validation.Date.min().date()}–{validation.Date.max().date()}', flush=True)
    hist = fit_history(fitting)
    X, V = features(fitting, stores, hist), features(validation, stores, hist)
    print('Training holdout models…', flush=True)
    boost, ridge, timings = train_models(fitting, X)
    predictions = predict(validation, V, boost, ridge)
    predictions['Sales'] = validation.Sales
    predictions.to_csv(ART / 'validation.csv', index=False)
    scores = [{'model': name, **metrics(predictions.Sales, predictions[name]), 'fit_seconds': timings[name]} for name in MODELS]
    print(json.dumps(scores, indent=2), flush=True)
    # Empirical 80% absolute-error ranges by model on the held-out observations.
    residuals = {name: float(np.quantile(np.abs(predictions.loc[predictions.Open == 1, 'Sales'] - predictions.loc[predictions.Open == 1, name]), 0.8)) for name in MODELS}
    print('Refitting on full history for forward forecasts…', flush=True)
    final_history = fit_history(train)
    full_X, future_X = features(train, stores, final_history), features(test, stores, final_history)
    final_boost, final_ridge, final_timings = train_models(train, full_X)
    future = predict(test, future_X, final_boost, final_ridge)
    future['Id'] = test.Id
    future.to_csv(ART / 'forecast.csv', index=False)
    final_boost.save_model(ART / 'xgboost.ubj')
    joblib.dump({'ridge': final_ridge, 'history': final_history, 'feature_names': list(full_X)}, ART / 'ridge_and_features.joblib')
    print('Computing exact Tree SHAP explanations…', flush=True)
    sample = future_X.loc[test.Open.fillna(1) == 1].sample(n=min(1000, int(test.Open.fillna(1).sum())), random_state=42)
    shap = final_boost.get_booster().predict(xgb.DMatrix(sample), pred_contribs=True)
    importance = [{'feature': c, 'label': FEATURE_LABELS[c], 'importance': float(v)} for c, v in zip(full_X.columns, np.abs(shap[:, :-1]).mean(axis=0))]
    importance.sort(key=lambda r: r['importance'], reverse=True)
    local_indices = test[test.Open.fillna(1) == 1].groupby('Store', sort=True).head(1).index
    local_X = future_X.loc[local_indices]
    local_shap = final_boost.get_booster().predict(xgb.DMatrix(local_X), pred_contribs=True)
    local = {}
    for idx, values in zip(local_indices, local_shap):
        row = test.loc[idx]
        contributions = [{'feature': c, 'label': FEATURE_LABELS[c], 'value': float(v), 'input': float(future_X.loc[idx, c])} for c, v in zip(full_X.columns, values[:-1])]
        local[str(row.Store)] = {'date': str(row.Date.date()), 'store': int(row.Store), 'base_value': float(values[-1]), 'prediction': float(future.loc[idx, 'XGBoost']), 'contributions': sorted(contributions, key=lambda r: abs(r['value']), reverse=True)}
    (ART / 'explanations.json').write_text(json.dumps({'global': importance, 'sample_size': len(sample), 'local': local}))
    missing = []
    for name, df in [('Sales history', train), ('Store metadata', stores), ('Future schedule', test)]:
        for col in df:
            n = int(df[col].isna().sum())
            if n:
                missing.append({'table': name, 'field': col, 'missing': n, 'total': len(df), 'percent': n / len(df) * 100})
    quality = {
        'missing': missing, 'duplicates': int(train.duplicated(['Store', 'Date']).sum()),
        'negative_sales': int((train.Sales < 0).sum()), 'zero_sales': int((train.Sales == 0).sum()),
        'closed_rows': int((train.Open == 0).sum()), 'open_zero_sales': int(((train.Open == 1) & (train.Sales == 0)).sum()),
        'expected_rows': int(train.Store.nunique() * (train.Date.max() - train.Date.min()).days + train.Store.nunique()),
        'actual_rows': len(train), 'missing_sales': int(train.Sales.isna().sum()),
        'monthly_coverage': [{'month': str(month), 'rows': int(len(g)), 'stores': int(g.Store.nunique())} for month, g in train.groupby(train.Date.dt.to_period('M'))],
        'unknown_future_open': int(test.Open.isna().sum()),
    }
    manifest = {
        'generated_at': datetime.now(timezone.utc).isoformat(), 'dataset': 'Rossmann Store Sales',
        'history_start': str(train.Date.min().date()), 'history_end': str(train.Date.max().date()),
        'train_rows': len(train), 'store_count': len(stores), 'forecast_store_count': int(test.Store.nunique()),
        'forecast_start': str(test.Date.min().date()), 'forecast_end': str((test.Date.min() + pd.Timedelta(days=41)).date()),
        'schedule_end': str(test.Date.max().date()), 'validation_start': str(validation.Date.min().date()),
        'validation_end': str(validation.Date.max().date()), 'fitting_end': str(cutoff.date()),
        'fitting_rows': len(fitting), 'validation_rows': len(validation), 'metrics': scores,
        'error_ranges': residuals, 'final_fit_seconds': final_timings,
        'features': list(full_X), 'seed': 42, 'duration_seconds': round(time.time() - started, 2),
        'source_hashes': {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in [DATA / 'train.csv', DATA / 'test.csv', DATA / 'store.csv']},
    }
    (ART / 'quality.json').write_text(json.dumps(quality))
    (ART / 'manifest.json').write_text(json.dumps(manifest, indent=2))
    print(f'Pipeline complete in {manifest["duration_seconds"]}s', flush=True)

if __name__ == '__main__':
    main()
