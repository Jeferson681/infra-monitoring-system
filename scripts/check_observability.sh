#!/usr/bin/env bash
set -euo pipefail

# Start the app in background (one short cycle) and validate /health and /metrics
LOG=$(mktemp)
python -m src.main -i 1 -c 0 >"${LOG}" 2>&1 &
PID=$!
trap 'kill ${PID} >/dev/null 2>&1 || true; rm -f "${LOG}"' EXIT

sleep 1
curl -fsS http://127.0.0.1:8000/health || (echo "health failed"; exit 2)
curl -fsS http://127.0.0.1:8000/metrics | head -n 20 || (echo "metrics failed"; exit 2)

echo "OK"
