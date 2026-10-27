#!/usr/bin/env bash
# Build and serve the app and API together at http://127.0.0.1:8000.
set -euo pipefail
cd "$(dirname "$0")"
if [[ ! -x .venv/bin/python ]]; then
  if command -v python3.11 >/dev/null 2>&1; then
    python3.11 -m venv .venv
  else
    python3 -m venv .venv
  fi
  .venv/bin/python -m pip install -r backend/requirements.txt
fi
if [[ "${1:-}" == "--retrain" || ! -f backend/runtime_data/snapshot.json ]]; then
  .venv/bin/python -m pip install -r backend/requirements-training.txt
  if [[ ! -f data/train.csv ]]; then
    .venv/bin/python scripts/extract_data.py
  fi
  .venv/bin/python -m backend.pipeline
  .venv/bin/python scripts/package_runtime.py
fi
if [[ ! -d frontend/node_modules ]]; then
  npm --prefix frontend ci
fi
npm --prefix frontend run build
exec .venv/bin/uvicorn backend.app:app --host 127.0.0.1 --port "${PORT:-8000}"
