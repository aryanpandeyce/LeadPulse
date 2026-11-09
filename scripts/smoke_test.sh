#!/usr/bin/env bash
set -euo pipefail

BACKEND_URL="${1:-${BACKEND_URL:-http://localhost:8000}}"
FRONTEND_URL="${2:-${FRONTEND_URL:-http://localhost:3000}}"

python3 scripts/smoke_test.py --backend-url "$BACKEND_URL" --frontend-url "$FRONTEND_URL"

