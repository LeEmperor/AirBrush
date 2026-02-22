#!/usr/bin/env bash
set -euo pipefail

# Run both WebXR HTTPS page server + FastAPI/WebSocket server (TLS)
# Usage:
#   chmod +x run_all.sh
#   ./run_all.sh
#
# Assumptions:
# - serve_https.py exists and runs an HTTPS server for your WebXR webpage
# - key.pem and cert.pem exist in the same directory (or adjust paths)
# - FastAPI app is at server:app

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

KEY_FILE="key.pem"
CERT_FILE="cert.pem"

if [[ ! -f "$KEY_FILE" ]]; then
  echo "ERROR: Missing $KEY_FILE in $SCRIPT_DIR"
  exit 1
fi

if [[ ! -f "$CERT_FILE" ]]; then
  echo "ERROR: Missing $CERT_FILE in $SCRIPT_DIR"
  exit 1
fi

# Track background PIDs so we can stop everything on exit.
PIDS=()

cleanup() {
  echo ""
  echo "Shutting down..."
  for pid in "${PIDS[@]:-}"; do
    if kill -0 "$pid" 2>/dev/null; then
      kill "$pid" 2>/dev/null || true
    fi
  done

  # Give them a moment to exit gracefully, then force-kill if needed.
  sleep 0.5
  for pid in "${PIDS[@]:-}"; do
    if kill -0 "$pid" 2>/dev/null; then
      kill -9 "$pid" 2>/dev/null || true
    fi
  done
}

trap cleanup EXIT INT TERM

echo "Starting HTTPS page server (WebXR)..."
python serve_https.py &
PIDS+=("$!")
echo "  -> PID ${PIDS[-1]}"

echo "Starting FastAPI (uvicorn) with TLS on 0.0.0.0:8081..."
uvicorn server:app \
  --host 0.0.0.0 \
  --port 8081 \
  --ssl-keyfile "$KEY_FILE" \
  --ssl-certfile "$CERT_FILE" &
PIDS+=("$!")
echo "  -> PID ${PIDS[-1]}"

echo ""
echo "Both servers are running."
echo "Press Ctrl+C to stop."
echo ""

# Wait on both processes (if either exits, script exits and cleanup runs).
wait "${PIDS[0]}" "${PIDS[1]}"