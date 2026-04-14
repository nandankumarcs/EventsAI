#!/usr/bin/env bash
# start.sh — Build the React frontend and start the Django backend in one shot.
# Run from the project root: ./start.sh

set -e

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FRONTEND_DIR="$ROOT_DIR/frontend"
BACKEND_DIR="$ROOT_DIR/backend"
PYTHON="$BACKEND_DIR/.venv/bin/python"
PIP="$BACKEND_DIR/.venv/bin/pip"

MODE="build"
if [ "${1:-}" = "--dev" ]; then
  MODE="dev"
  shift
fi

# ── Load nvm so `npm` is available ──────────────────────────────────────────
export NVM_DIR="${NVM_DIR:-$HOME/.nvm}"
if [ -s "$NVM_DIR/nvm.sh" ]; then
  # shellcheck source=/dev/null
  source "$NVM_DIR/nvm.sh"
else
  echo "Warning: nvm not found. Trying system npm." >&2
fi

# ── 1. Build the React frontend ──────────────────────────────────────────────
cd "$FRONTEND_DIR"

if [ ! -d "$FRONTEND_DIR/node_modules" ]; then
  echo "▶  Installing frontend dependencies…"
  npm ci
fi

VITE_PID=""
cleanup() {
  if [ -n "${VITE_PID:-}" ] && kill -0 "$VITE_PID" >/dev/null 2>&1; then
    kill "$VITE_PID" >/dev/null 2>&1 || true
  fi
}
trap cleanup EXIT

if [ "$MODE" = "dev" ]; then
  echo "▶  Starting React dev server…"
  npm run dev &
  VITE_PID=$!
else
  echo "▶  Building React frontend…"
  npm run build
fi

cd "$ROOT_DIR"

# ── 2. Start the Django server ───────────────────────────────────────────────
HOST="${HOST:-127.0.0.1}"
PORT="${PORT:-8000}"

echo "▶  Starting Django server at http://$HOST:$PORT"
if [ ! -x "$PYTHON" ]; then
  echo "▶  Creating backend virtualenv…"
  python3 -m venv "$BACKEND_DIR/.venv"
  "$PIP" install -r "$BACKEND_DIR/requirements.txt"
fi
"$PYTHON" "$BACKEND_DIR/manage.py" runserver "$HOST:$PORT"
