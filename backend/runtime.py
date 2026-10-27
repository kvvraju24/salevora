"""Shared data and scoring helpers, with no model-training dependencies.

The hosted API reads a compressed, immutable snapshot of the real observations
and precomputed predictions. Training continues to use the original CSV files.
"""
from pathlib import Path
import gzip
import hashlib
import json
import os

import numpy as np
import pandas as pd

BACKEND = Path(__file__).resolve().parent
ROOT = BACKEND.parent
DATA, ART = ROOT / 'data', BACKEND / 'artifacts'
RUNTIME = BACKEND / 'runtime_data'
MODELS = ['XGBoost', 'Ridge', 'Baseline']


def read_data():
    """Read original inputs for local analysis and model training."""
    train = pd.read_csv(DATA / 'train.csv', dtype={'StateHoliday': str}, parse_dates=['Date'])
    test = pd.read_csv(DATA / 'test.csv', dtype={'StateHoliday': str}, parse_dates=['Date'])
    stores = pd.read_csv(DATA / 'store.csv')
    return train.sort_values(['Date', 'Store']).reset_index(drop=True), test.sort_values(['Date', 'Store']).reset_index(drop=True), stores


def metrics(actual, predicted):
    y, p = np.asarray(actual, float), np.asarray(predicted, float)
    nonzero = y > 0
    error = y - p
    return {'mae': float(np.mean(np.abs(error))), 'rmse': float(np.sqrt(np.mean(error ** 2))),
            'rmspe': float(np.sqrt(np.mean((error[nonzero] / y[nonzero]) ** 2))) if nonzero.any() else None,
            'wape': float(np.sum(np.abs(error)) / np.sum(y)) if np.sum(y) else None,
            'bias': float(np.sum(p - y) / np.sum(y)) if np.sum(y) else None,
            'rows': len(y)}


def read_serving_data():
    """Prefer local source files; use the packaged snapshot on a deployment.

    SALEVORA_DATA_MODE=snapshot explicitly exercises the deployed data path.
    A snapshot includes every historical store-day, preserving all API filters.
    """
    mode = os.environ.get('SALEVORA_DATA_MODE', 'auto')
    if mode not in {'auto', 'source', 'snapshot'}:
        raise RuntimeError('SALEVORA_DATA_MODE must be auto, source, or snapshot')
    source_files = [DATA / name for name in ('train.csv', 'test.csv', 'store.csv')]
    artifact_files = [ART / name for name in ('forecast.csv', 'validation.csv', 'manifest.json', 'quality.json', 'explanations.json')]
    source_available = all(path.exists() for path in source_files + artifact_files)
    if mode == 'source' or (mode == 'auto' and source_available):
        if not source_available:
            raise RuntimeError('Source data or model artifacts are missing. Run the extraction and training pipeline.')
        train, _, stores = read_data()
        return {
            'train': train, 'stores': stores,
            'forecast': pd.read_csv(ART / 'forecast.csv', parse_dates=['Date']),
            'validation': pd.read_csv(ART / 'validation.csv', parse_dates=['Date']),
            **{name: json.loads((ART / f'{name}.json').read_text()) for name in ('manifest', 'quality', 'explanations')},
        }

    index_path = RUNTIME / 'snapshot.json'
    if not index_path.exists():
        raise RuntimeError('Serving snapshot is missing. Run: python scripts/package_runtime.py')
    index = json.loads(index_path.read_text())
    if index['schema_version'] != 1:
        raise RuntimeError('Unsupported serving snapshot version')
    # Verify committed files so an incomplete or mixed-generation bundle cannot
    # silently serve forecasts against a different history or manifest.
    for name, metadata in index['files'].items():
        path = RUNTIME / name
        if not path.exists() or hashlib.sha256(path.read_bytes()).hexdigest() != metadata['sha256']:
            raise RuntimeError(f'Serving snapshot is incomplete or corrupt: {name}')
    frames = {
        name: pd.read_csv(RUNTIME / f'{name}.csv.gz', parse_dates=['Date'] if name != 'stores' else None)
        for name in ('train', 'stores', 'forecast', 'validation')
    }
    for name in ('manifest', 'quality', 'explanations'):
        with gzip.open(RUNTIME / f'{name}.json.gz', 'rt', encoding='utf-8') as stream:
            frames[name] = json.load(stream)
    return frames
