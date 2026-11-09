#!/bin/sh
set -e

echo "[LeadPulse] Running Alembic database migrations..."
alembic upgrade head

echo "[LeadPulse] Starting Uvicorn server on port ${PORT:-8000}..."
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"

