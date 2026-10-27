"""Deployment checks: source parity, isolated startup, and download limits."""
import os
import shutil
import subprocess
import sys

from fastapi.testclient import TestClient

from backend.app import app
from backend.runtime import ROOT, RUNTIME


def test_packaged_snapshot_preserves_dashboard_results(monkeypatch):
    # Include the longest supported comparison window and each model so a
    # smaller deployment package cannot silently truncate history or forecasts.
    paths = [
        '/api/meta', '/api/overview?days=180', '/api/overview?store=1&days=28',
        '/api/stores?days=180', '/api/stores?store=1&days=42',
        '/api/models', '/api/models?store=1', '/api/explain?store=1', '/api/quality',
        *[f'/api/forecast?horizon=42&model={model}' for model in ('XGBoost', 'Ridge', 'Baseline')],
        '/api/forecast?store=1&horizon=42',
    ]
    monkeypatch.setenv('SALEVORA_DATA_MODE', 'source')
    with TestClient(app) as client:
        expected = {path: client.get(path).json() for path in paths}
    monkeypatch.setenv('SALEVORA_DATA_MODE', 'snapshot')
    with TestClient(app) as client:
        for path in paths:
            response = client.get(path)
            assert response.status_code == 200, path
            assert response.json() == expected[path], path
        for model in ('XGBoost', 'Ridge', 'Baseline'):
            export = client.get(f'/api/forecast/export?horizon=42&model={model}')
            assert export.status_code == 200
            assert len(export.content) < 4_500_000  # Vercel function response limit.
            assert len(export.text.splitlines()) == 856 * 42 + 1


def test_backend_service_starts_without_original_data_or_ml_packages(tmp_path):
    # Reproduce the service root after Vercel excludes local data/model files.
    for filename in ('app.py', 'runtime.py'):
        shutil.copy2(ROOT / 'backend' / filename, tmp_path / filename)
    shutil.copytree(RUNTIME, tmp_path / 'runtime_data')
    script = '''
import importlib.abc
import sys

class BlockTrainingPackages(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split('.')[0] in {'xgboost', 'sklearn', 'scipy', 'joblib'}:
            raise ImportError('Training dependency imported by API: ' + fullname)

sys.meta_path.insert(0, BlockTrainingPackages())
from fastapi.testclient import TestClient
from app import app
with TestClient(app) as client:
    for path in ('/api/health', '/api/overview', '/api/forecast', '/api/stores', '/api/models', '/api/explain', '/api/quality'):
        response = client.get(path)
        assert response.status_code == 200, (path, response.text)
    assert client.get('/api/meta').json()['train_rows'] == 1017209
print('Standalone backend passed with training imports blocked')
'''
    environment = dict(os.environ)
    environment.pop('SALEVORA_DATA_MODE', None)
    environment.pop('PYTHONPATH', None)
    result = subprocess.run([sys.executable, '-c', script], cwd=tmp_path, env=environment,
                            capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, result.stdout + result.stderr


def test_incomplete_snapshot_fails_at_startup(tmp_path, monkeypatch):
    import backend.runtime as runtime
    import pytest

    # A partial deployment must not serve a misleading mix of dataset versions.
    shutil.copy2(RUNTIME / 'snapshot.json', tmp_path / 'snapshot.json')
    monkeypatch.setattr(runtime, 'RUNTIME', tmp_path)
    monkeypatch.setenv('SALEVORA_DATA_MODE', 'snapshot')
    with pytest.raises(RuntimeError, match='incomplete or corrupt'):
        runtime.read_serving_data()


def test_security_headers_and_supported_periods(monkeypatch):
    # Runs from the committed snapshot alone, so CI can check it without the original archive.
    monkeypatch.setenv('SALEVORA_DATA_MODE', 'snapshot')
    with TestClient(app) as client:
        api = client.get('/api/health')
        assert api.status_code == 200
        assert api.headers['x-content-type-options'] == 'nosniff'
        assert api.headers['x-frame-options'] == 'DENY'
        assert "default-src 'none'" in api.headers['content-security-policy']
        docs = client.get('/docs')
        assert docs.status_code == 200
        assert 'content-security-policy' not in docs.headers  # Swagger UI loads CDN assets.
        for days in (28, 42, 90, 180):
            assert client.get(f'/api/overview?days={days}').status_code == 200
        assert client.get('/api/overview?days=30').status_code == 422
        assert client.get('/api/stores?days=179').status_code == 422
