#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

if [[ ! -f .env ]]; then
  cp .env.example .env
fi

cd backend
alembic upgrade head
python -m app.seed --with-odds
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
