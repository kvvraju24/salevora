"""Integration checks against source data, exported predictions, and model artifacts."""
from io import StringIO
import json
import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient
from backend.app import app
from backend.pipeline import ART, DATA, features, fit_history, read_data

@pytest.fixture(scope='module')
def client():
    with TestClient(app) as c:
        yield c


def test_overview_reconciles_to_source(client):
    raw = pd.read_csv(DATA / 'train.csv', dtype={'StateHoliday': str})
    expected = raw[(raw.Date >= '2015-06-20') & (raw.Date <= '2015-07-31')]
    response = client.get('/api/overview?days=42').json()
    assert response['revenue'] == int(expected.Sales.sum())
    assert response['customers'] == int(expected.Customers.sum())
    assert sum(r['value'] for r in response['series']) == response['revenue']
    assert sum(r['customers'] for r in response['series']) == response['customers']
    assert response['stores'] == 1115


def test_store_filter_and_period_change(client):
    a = client.get('/api/overview?store=1&days=28').json()
    b = client.get('/api/overview?store=1&days=42').json()
    assert a['stores'] == b['stores'] == 1
    assert len(a['series']) == 28 and len(b['series']) == 42
    assert a['revenue'] < b['revenue']
    assert a['top_stores'][0]['Store'] == 1


@pytest.mark.parametrize('model', ['XGBoost', 'Ridge', 'Baseline'])
def test_forecast_export_and_summary_agree(client, model):
    query = f'store=1&horizon=42&model={model}'
    d = client.get('/api/forecast?' + query).json()
    response = client.get('/api/forecast/export?' + query)
    csv = pd.read_csv(StringIO(response.text))
    assert len(csv) == 42
    assert csv.Store.unique().tolist() == [1]
    assert csv.Date.min() == '2015-08-01' and csv.Date.max() == '2015-09-11'
    assert csv.PredictedSales.sum() == pytest.approx(d['total'])
    assert d['series'][-1]['cumulative'] == pytest.approx(d['total'])
    assert (csv.loc[csv.Open == 0, 'PredictedSales'] == 0).all()
    assert csv.PredictedSales.ge(0).all()
    assert all(r['range'] == [0, 0] for r in d['series'] if not r['open_stores'])


def test_network_forecast_scope_and_no_misleading_confidence_band(client):
    d = client.get('/api/forecast?horizon=14').json()
    assert d['stores'] == 856
    assert len(d['series']) == 14
    assert d['range_radius'] is None
    assert all('range' not in r for r in d['series'])


@pytest.mark.parametrize('path,status', [
    ('/api/overview?store=99999', 404), ('/api/forecast?store=2', 404),
    ('/api/forecast?horizon=100', 422), ('/api/forecast?model=Imaginary', 422),
    ('/api/overview?days=0', 422), ('/api/explain?store=2',404),
    ('/api/overview?days=30', 422), ('/api/stores?days=179', 422),
])
def test_invalid_or_unavailable_requests(client, path, status):
    assert client.get(path).status_code == status



def test_scores_reconcile_to_predictions_and_dates(client):
    v = pd.read_csv(ART / 'validation.csv')
    m = client.get('/api/meta').json()
    assert v.Date.min() > m['fitting_end']
    assert v.Date.min() == m['validation_start']
    assert v.Date.max() == m['validation_end']
    assert len(v) == 46830
    result = client.get('/api/models').json()
    for row in result['metrics']:
        p, y = v[row['model']].to_numpy(), v.Sales.to_numpy()
        expected = np.abs(p-y).sum()/y.sum()
        assert row['wape'] == pytest.approx(expected)
    assert 'Customers' not in m['features'] and 'Sales' not in m['features']


def test_target_derived_features_do_not_read_holdout_targets():
    train, _, stores = read_data()
    fitting = train[train.Date <= '2015-06-19'].copy()
    holdout = train[train.Date > '2015-06-19'].head(1000).copy()
    history = fit_history(fitting)
    before = features(holdout, stores, history)
    holdout['Sales'] = 999999999
    holdout['Customers'] = 999999999
    after = features(holdout, stores, history)
    pd.testing.assert_frame_equal(before, after)
    assert history['cutoff'] == '2015-06-19'


def test_shap_additivity_and_prediction_agreement(client):
    e = client.get('/api/explain?store=1').json()['local']
    raw = e['base_value'] + sum(r['value'] for r in e['contributions'])
    assert np.expm1(raw) == pytest.approx(e['prediction'], rel=2e-5)
    forecast = client.get('/api/forecast?store=1').json()
    same_date = next(r for r in forecast['series'] if r['date'] == e['date'])
    assert e['prediction'] == pytest.approx(same_date['prediction'])


def test_missing_data_and_coverage_audit(client):
    q = client.get('/api/quality').json()
    assert q['actual_rows'] == 1017209
    assert q['duplicates'] == q['missing_sales'] == q['negative_sales'] == 0
    assert q['expected_rows'] - q['actual_rows'] == 33121
    assert q['unknown_future_open'] == 11
    assert sum(r['rows'] for r in q['monthly_coverage']) == q['actual_rows']
    assert q['zero_sales'] == q['closed_rows'] + q['open_zero_sales']


def test_store_analytics_network_reconciles(client):
    d = client.get('/api/stores?days=42').json()
    o = client.get('/api/overview?days=42').json()
    assert len(d['stores']) == 1115
    assert sum(s['revenue'] for s in d['stores']) == o['revenue']
    assert sum(s['forecast_available'] for s in d['stores']) == 856
