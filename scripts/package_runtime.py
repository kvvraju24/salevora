"""Package existing training results for an inference-free hosted dashboard.

Run after training: python scripts/package_runtime.py
The output is deterministic and contains real history, predictions, explanations,
and provenance. No training model, original ZIP, or future target is required.
"""
from pathlib import Path
import gzip
import hashlib
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import pandas as pd
from backend.runtime import DATA, ART, RUNTIME


def package_runtime(destination=RUNTIME):
    destination = Path(destination)
    sources = [DATA / 'train.csv', DATA / 'test.csv', DATA / 'store.csv']
    artifacts = [ART / name for name in ('forecast.csv', 'validation.csv', 'manifest.json', 'quality.json', 'explanations.json')]
    missing = [str(path.relative_to(ROOT)) for path in sources + artifacts if not path.exists()]
    if missing:
        raise RuntimeError('Missing inputs; extract data and run backend.pipeline first: ' + ', '.join(missing))

    manifest = json.loads((ART / 'manifest.json').read_text())
    for path in sources:
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if manifest['source_hashes'].get(path.name) != digest:
            raise RuntimeError(f'{path.name} differs from the trained data. Retrain before packaging.')

    destination.mkdir(parents=True, exist_ok=True)
    files = {}

    def save(name, payload):
        compressed = gzip.compress(payload, compresslevel=9, mtime=0)
        (destination / name).write_bytes(compressed)
        files[name] = {'bytes': len(compressed), 'sha256': hashlib.sha256(compressed).hexdigest()}

    # Only columns consumed by API queries are shipped, but every observation is
    # preserved. Quality findings and model metadata describe the original data.
    columns = ['Store', 'DayOfWeek', 'Date', 'Sales', 'Customers', 'Open', 'Promo']
    train = pd.read_csv(DATA / 'train.csv', usecols=columns)
    train = train.sort_values(['Date', 'Store'])
    save('train.csv.gz', train[columns].to_csv(index=False).encode('utf-8'))
    save('stores.csv.gz', (DATA / 'store.csv').read_bytes())
    for name in ('forecast', 'validation'):
        save(f'{name}.csv.gz', (ART / f'{name}.csv').read_bytes())
    for name in ('manifest', 'quality', 'explanations'):
        save(f'{name}.json.gz', (ART / f'{name}.json').read_bytes())

    snapshot = {
        'schema_version': 1,
        'dataset': manifest['dataset'],
        'history_rows': len(train),
        'history_start': manifest['history_start'],
        'history_end': manifest['history_end'],
        'artifacts_generated_at': manifest['generated_at'],
        'source_hashes': manifest['source_hashes'],
        'files': files,
    }
    (destination / 'snapshot.json').write_text(json.dumps(snapshot, indent=2) + '\n')
    return snapshot


if __name__ == '__main__':
    snapshot = package_runtime()
    size = sum(item['bytes'] for item in snapshot['files'].values())
    print(f'Packaged {snapshot["history_rows"]:,} historical rows and all model results: {size / 1024 / 1024:.2f} MiB')
