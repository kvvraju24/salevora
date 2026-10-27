"""Extract only the expected CSV members from the user-supplied dataset archive."""
from pathlib import Path
from zipfile import ZipFile
root = Path(__file__).resolve().parents[1]
archive = root / 'rossmann-store-sales.zip'
if not archive.exists():
    raise SystemExit('Place rossmann-store-sales.zip in the project root, or train.csv, test.csv and store.csv in data/.')
(root / 'data').mkdir(exist_ok=True)
with ZipFile(archive) as z:
    for name in ['train.csv', 'test.csv', 'store.csv', 'sample_submission.csv']:
        destination = root / 'data' / name
        if not destination.exists():
            destination.write_bytes(z.read(name))
print('Rossmann dataset extracted into data/.')
