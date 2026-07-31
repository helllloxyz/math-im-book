#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
FRONTEND_DIR="$REPO_ROOT/frontend"
VENV_DIR="$REPO_ROOT/.venv"

SERVICE_LABEL="top.mulinfro.math-im-book"
SERVICE_DOMAIN="gui/$(id -u)"
SERVICE_TARGET="$SERVICE_DOMAIN/$SERVICE_LABEL"
SERVICE_PLIST="$HOME/Library/LaunchAgents/$SERVICE_LABEL.plist"

BACKEND_PORT=8016
BACKEND_PID=""
FRONTEND_PID=""
RESTORE_SERVICE=0
CLEANUP_STARTED=0

cleanup() {
  exit_code=$?

  if [[ "$CLEANUP_STARTED" -eq 1 ]]; then
    return
  fi
  CLEANUP_STARTED=1
  trap - EXIT INT TERM

  echo
  echo "Stopping development servers..."

  if [[ -n "$BACKEND_PID" ]]; then
    kill "$BACKEND_PID" 2>/dev/null || true
  fi
  if [[ -n "$FRONTEND_PID" ]]; then
    kill "$FRONTEND_PID" 2>/dev/null || true
  fi

  if [[ -n "$BACKEND_PID" ]]; then
    wait "$BACKEND_PID" 2>/dev/null || true
  fi
  if [[ -n "$FRONTEND_PID" ]]; then
    wait "$FRONTEND_PID" 2>/dev/null || true
  fi

  if [[ "$RESTORE_SERVICE" -eq 1 ]]; then
    echo "Restoring the launchd-managed backend..."
    launchctl bootstrap "$SERVICE_DOMAIN" "$SERVICE_PLIST"
  fi

  exit "$exit_code"
}
trap cleanup EXIT INT TERM

if [[ ! -x "$VENV_DIR/bin/uvicorn" ]]; then
  echo "Backend environment is missing: $VENV_DIR"
  echo "Run: python3.10 -m venv .venv && .venv/bin/pip install -e '.[dev]'"
  exit 1
fi

if [[ ! -x "$FRONTEND_DIR/node_modules/.bin/vite" ]] ||
   [[ ! -x "$FRONTEND_DIR/node_modules/.bin/vue-tsc" ]]; then
  echo "Frontend dependencies are missing. Installing them..."
  (cd "$FRONTEND_DIR" && npm install)
fi

if launchctl print "$SERVICE_TARGET" >/dev/null 2>&1; then
  echo "Stopping the launchd-managed backend on port $BACKEND_PORT..."
  RESTORE_SERVICE=1
  launchctl bootout "$SERVICE_TARGET"
fi

for _ in {1..50}; do
  if ! lsof -nP -iTCP:"$BACKEND_PORT" -sTCP:LISTEN >/dev/null 2>&1; then
    break
  fi
  sleep 0.1
done

if lsof -nP -iTCP:"$BACKEND_PORT" -sTCP:LISTEN >/dev/null 2>&1; then
  echo "Port $BACKEND_PORT is still in use."
  exit 1
fi

echo "Checking frontend types..."
(cd "$FRONTEND_DIR" && ./node_modules/.bin/vue-tsc)

echo "Creating the initial frontend build..."
(cd "$FRONTEND_DIR" && ./node_modules/.bin/vite build)

echo "Starting frontend build watcher..."
(
  cd "$FRONTEND_DIR"
  exec ./node_modules/.bin/vite build --watch --emptyOutDir false
) &
FRONTEND_PID=$!

echo "Starting backend with automatic Python reload..."
(
  cd "$REPO_ROOT"
  export FASTAPI_ENV=development
  export PYTHONPATH="$REPO_ROOT/src"
  #export TRACE_LOCAL_URL=http://localhost:6016/v1
  exec "$VENV_DIR/bin/uvicorn" \
    math_im_book.api.app:create_app \
    --factory \
    --reload \
    --host 127.0.0.1 \
    --port "$BACKEND_PORT"
) &
BACKEND_PID=$!

for _ in {1..100}; do
  if curl -fsS \
    --connect-timeout 1 \
    --max-time 1 \
    "http://127.0.0.1:$BACKEND_PORT/health" >/dev/null 2>&1; then
    echo
    echo "Development services are ready."
    echo "- Public URL: https://mulinfro.top"
    echo "- Local URL:  http://127.0.0.1:$BACKEND_PORT"
    echo "- Python changes reload automatically."
    echo "- Frontend changes rebuild automatically; refresh the browser to see them."
    echo "- Press Ctrl+C to stop and restore the background service."
    echo
    break
  fi

  if ! kill -0 "$BACKEND_PID" 2>/dev/null; then
    echo "Backend stopped before becoming healthy."
    exit 1
  fi
  if ! kill -0 "$FRONTEND_PID" 2>/dev/null; then
    echo "Frontend watcher stopped before the backend became healthy."
    exit 1
  fi

  sleep 0.1
done

if ! curl -fsS \
  --connect-timeout 1 \
  --max-time 1 \
  "http://127.0.0.1:$BACKEND_PORT/health" >/dev/null 2>&1; then
  echo "Backend health check timed out."
  exit 1
fi

while kill -0 "$BACKEND_PID" 2>/dev/null &&
      kill -0 "$FRONTEND_PID" 2>/dev/null; do
  sleep 1
done

echo "A development process stopped unexpectedly."
exit 1
