"""Read-only analytics API backed by reproducible local model artifacts."""
from contextlib import asynccontextmanager
from functools import lru_cache
import json
from typing import Literal
import numpy as np
import pandas as pd
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import Response
from fastapi.staticfiles import StaticFiles
if __package__:
    from backend.runtime import ROOT, read_serving_data, metrics, MODELS
else:  # Vercel's backend-root service imports app:app directly.
    from runtime import ROOT, read_serving_data, metrics, MODELS


@asynccontextmanager
async def lifespan(app):
    for name, value in read_serving_data().items():
        setattr(app.state, name, value)
    app.state.forecast_ids = set(app.state.forecast.Store.unique())
    for fn in [overview, forecast, store_analytics, model_comparison]:
        fn.cache_clear()
    yield

app = FastAPI(title='Salevora • Sales & Revenue Forecasting', version='1.1.0', lifespan=lifespan)

# Periods offered by the dashboard. Accepting only these keeps the in-process
# cache effective and stops scripted sweeps over thousands of uncached queries.
ALLOWED_DAYS = (28, 42, 90, 180)

APP_CSP = ("default-src 'self'; script-src 'self'; "
           "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
           "font-src 'self' https://fonts.gstatic.com; img-src 'self' data:; connect-src 'self'; "
           "object-src 'none'; base-uri 'self'; form-action 'self'; frame-ancestors 'none'")
API_CSP = "default-src 'none'; frame-ancestors 'none'"


@app.middleware('http')
async def security_headers(request, call_next):
    response = await call_next(request)
    headers = response.headers
    headers.setdefault('X-Content-Type-Options', 'nosniff')
    headers.setdefault('Referrer-Policy', 'strict-origin-when-cross-origin')
    headers.setdefault('X-Frame-Options', 'DENY')
    headers.setdefault('Permissions-Policy', 'camera=(), microphone=(), geolocation=()')
    path = request.url.path
    if path.startswith('/api/'):
        headers.setdefault('Content-Security-Policy', API_CSP)
    elif not path.startswith(('/docs', '/redoc', '/openapi.json')):
        # Swagger UI and ReDoc load their own CDN assets, so they keep FastAPI's defaults.
        headers.setdefault('Content-Security-Policy', APP_CSP)
    return response


def records(df):
    return json.loads(df.to_json(orient='records', date_format='iso'))


def validate_store(store, forecast_only=False):
    if store and store not in set(app.state.stores.Store):
        raise HTTPException(404, 'Store not found')
    if forecast_only and store and store not in app.state.forecast_ids:
        raise HTTPException(404, 'This store has history but no supplied future schedule. Select one of the 856 forecast stores.')


def validate_days(days):
    if days not in ALLOWED_DAYS:
        raise HTTPException(422, 'days must be one of 28, 42, 90 or 180')


def selected(df, store):
    return df[df.Store == store] if store else df


def daily(df, value='Sales'):
    d = df.groupby('Date', as_index=False)[value].sum()
    return [{'date': str(r.Date.date()), 'value': float(getattr(r, value))} for r in d.itertuples()]


@app.get('/api/health')
def health():
    return {'status': 'ready', 'dataset_as_of': app.state.manifest['history_end'], 'artifacts_built_at': app.state.manifest['generated_at']}


@app.get('/api/meta')
def meta():
    return {**app.state.manifest, 'stores': [{'id': int(r.Store), 'type': r.StoreType.upper(), 'forecast': r.Store in app.state.forecast_ids} for r in app.state.stores.itertuples()]}


@app.get('/api/overview')
@lru_cache(maxsize=64)
def overview(store: int = Query(0, ge=0), days: int = Query(42, ge=7, le=180)):
    validate_days(days)
    validate_store(store)
    t = selected(app.state.train, store)
    end = t.Date.max()
    start = end - pd.Timedelta(days=days - 1)
    current = t[t.Date >= start]
    previous = t[(t.Date < start) & (t.Date >= start - pd.Timedelta(days=days))]
    rev, prev = float(current.Sales.sum()), float(previous.Sales.sum())
    by_store = current.groupby('Store').agg(revenue=('Sales', 'sum'), customers=('Customers', 'sum'), open_days=('Open', 'sum'), observations=('Date', 'count')).reset_index()
    by_store['daily_average'] = by_store.revenue / by_store.observations
    by_store = by_store.merge(app.state.stores[['Store', 'StoreType']], on='Store')
    by_store = by_store.sort_values('revenue', ascending=False)
    weekday = current.groupby('DayOfWeek').agg(revenue=('Sales', 'mean')).reset_index()
    series = daily(current)
    prior_series = daily(previous)
    customers_by_date = current.groupby('Date').Customers.sum()
    for idx, item in enumerate(series):
        item['customers'] = int(customers_by_date.loc[pd.Timestamp(item['date'])])
        item['previous'] = prior_series[idx]['value'] if idx < len(prior_series) else None
    return {'revenue': rev, 'growth': (rev / prev - 1) if prev else None,
            'customers': int(current.Customers.sum()), 'daily_average': rev / days,
            'stores': int(current.Store.nunique()), 'open_rate': float(current.Open.mean()),
            'start': str(start.date()), 'end': str(end.date()), 'series': series,
            'top_stores': records(by_store.head(5)), 'low_stores': records(by_store.tail(5).sort_values('revenue')),
            'weekday': records(weekday), 'previous_revenue': prev, 'observed_rows': len(current), 'previous_rows': len(previous),
            'promo_share': float(current.loc[current.Promo == 1, 'Sales'].sum() / rev) if rev else 0}


def forecast_rows(store, horizon):
    validate_store(store, forecast_only=True)
    f = selected(app.state.forecast, store)
    return f[f.Date < f.Date.min() + pd.Timedelta(days=horizon)].copy()


@app.get('/api/forecast')
@lru_cache(maxsize=64)
def forecast(store: int = Query(0, ge=0), horizon: int = Query(42, ge=7, le=42), model: Literal['XGBoost', 'Ridge', 'Baseline'] = 'XGBoost'):
    f = forecast_rows(store, horizon)
    by_day = f.groupby('Date', as_index=False).agg(prediction=(model, 'sum'), open_stores=('Open', lambda v: v.fillna(1).sum()))
    by_day['cumulative'] = by_day.prediction.cumsum()
    # Only individual-store empirical ranges are exposed. Summing bounds would imply
    # an unjustified aggregate coverage guarantee in the presence of correlated errors.
    radius = app.state.manifest['error_ranges'][model]
    series = []
    for r in by_day.itertuples():
        item = {'date': str(r.Date.date()), 'prediction': float(r.prediction), 'cumulative': float(r.cumulative), 'open_stores': int(r.open_stores)}
        if store:
            item['range'] = [max(0, float(r.prediction) - radius), float(r.prediction) + radius] if r.open_stores else [0, 0]
        series.append(item)
    ids = f.Store.unique()
    t = app.state.train
    comparison = t[(t.Store.isin(ids)) & (t.Date > t.Date.max() - pd.Timedelta(days=horizon))]
    total, historical = float(f[model].sum()), float(comparison.Sales.sum())
    weekly = f.copy()
    weekly['week'] = ((weekly.Date - f.Date.min()).dt.days // 7) + 1
    weekly = weekly.groupby('week', as_index=False).agg(prediction=(model, 'sum'))
    ranking = f.groupby('Store', as_index=False)[model].sum().rename(columns={model: 'prediction'}).sort_values('prediction', ascending=False)
    return {'series': series, 'total': total, 'daily_average': total / horizon, 'stores': len(ids), 'model': model,
            'start': str(f.Date.min().date()), 'end': str(f.Date.max().date()), 'horizon': horizon,
            'previous_total': historical, 'change': total / historical - 1 if historical else None,
            'weekly': records(weekly), 'top_stores': records(ranking.head(8)),
            'range_radius': radius if store else None, 'range_note': 'Historical 80th-percentile absolute error on open store-days; indicative, not a calibrated future confidence interval.'}


@app.get('/api/forecast/export')
def export_forecast(store: int = Query(0, ge=0), horizon: int = Query(42, ge=7, le=42), model: Literal['XGBoost', 'Ridge', 'Baseline'] = 'XGBoost'):
    df = forecast_rows(store, horizon)[['Id', 'Store', 'Date', 'Open', 'Promo', model]].rename(columns={model: 'PredictedSales'})
    df['Model'] = model
    return Response(df.to_csv(index=False), media_type='text/csv', headers={'Content-Disposition': f'attachment; filename="salevora-{model.lower()}-{horizon}d.csv"'})


@app.get('/api/stores')
@lru_cache(maxsize=64)
def store_analytics(store: int = Query(0, ge=0), days: int = Query(42, ge=7, le=180)):
    validate_days(days)
    validate_store(store)
    t = app.state.train
    current = t[t.Date > t.Date.max() - pd.Timedelta(days=days)]
    previous = t[(t.Date <= t.Date.max() - pd.Timedelta(days=days)) & (t.Date > t.Date.max() - pd.Timedelta(days=days * 2))]
    summary = current.groupby('Store', as_index=False).agg(revenue=('Sales', 'sum'), customers=('Customers', 'sum'), open_days=('Open', 'sum'))
    prev = previous.groupby('Store').Sales.sum()
    summary['previous'] = summary.Store.map(prev)
    summary['growth'] = np.where(summary.previous > 0, summary.revenue / summary.previous - 1, np.nan)
    summary['revenue_per_open_day'] = summary.revenue / summary.open_days.replace(0, np.nan)
    summary = summary.merge(app.state.stores[['Store', 'StoreType', 'Assortment', 'CompetitionDistance']], on='Store')
    summary['forecast_available'] = summary.Store.isin(app.state.forecast_ids)
    scope = selected(current, store)
    open_scope = scope[scope.Open == 1]
    promo = open_scope.groupby('Promo', as_index=False).agg(average=('Sales', 'mean'), observations=('Sales', 'size'))
    types = current.merge(app.state.stores[['Store', 'StoreType']], on='Store').groupby('StoreType', as_index=False).agg(revenue=('Sales', 'sum'), stores=('Store', 'nunique'))
    return {'stores': records(summary.sort_values('revenue', ascending=False)), 'promo': records(promo), 'types': records(types),
            'history': daily(scope), 'selected_store': store, 'days': days,
            'promo_note': 'Observed association among open store-days. Different weekdays, seasons, and stores can affect the comparison; this is not a causal lift estimate.'}


@app.get('/api/models')
@lru_cache(maxsize=64)
def model_comparison(store: int = Query(0, ge=0)):
    validate_store(store)
    v = selected(app.state.validation, store)
    series = v.groupby('Date', as_index=False)[['Sales', *MODELS]].sum()
    rows = []
    for r in series.itertuples():
        rows.append({'date': str(r.Date.date()), 'actual': float(r.Sales), **{m: float(getattr(r, m)) for m in MODELS}})
    per_store = v.groupby('Store').apply(lambda g: pd.Series({'wape': np.abs(g.Sales - g.XGBoost).sum() / g.Sales.sum() if g.Sales.sum() else np.nan}), include_groups=False).reset_index()
    return {'metrics': [{'model': m, **metrics(v.Sales, v[m]), 'fit_seconds': next(x['fit_seconds'] for x in app.state.manifest['metrics'] if x['model'] == m)} for m in MODELS],
            'series': rows, 'worst_stores': records(per_store.sort_values('wape', ascending=False).head(8)),
            'start': app.state.manifest['validation_start'], 'end': app.state.manifest['validation_end'], 'rows': len(v)}


@app.get('/api/explain')
def explain(store: int = Query(0, ge=0)):
    validate_store(store, forecast_only=True)
    e = app.state.explanations
    chosen = str(store) if store else next(iter(e['local']))
    return {'global': e['global'], 'sample_size': e['sample_size'], 'local': e['local'][chosen],
            'units': 'log(1 + sales)', 'method': 'Exact Tree SHAP via XGBoost pred_contribs',
            'scope': 'Global importance uses 1,000 sampled open future store-days. Local explanation uses the selected store’s first scheduled open day.'}


@app.get('/api/quality')
def quality():
    return {**app.state.quality, 'manifest': app.state.manifest}

# Production build and API share an origin; the development server proxies /api.
DIST = ROOT / 'frontend' / 'dist'
if DIST.exists():
    app.mount('/', StaticFiles(directory=DIST, html=True), name='frontend')
