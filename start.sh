#!/usr/bin/env bash
# start.sh — Build the React frontend and start the Django backend in one shot.
# Run from the project root: ./start.sh

set -e

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FRONTEND_DIR="$ROOT_DIR/frontend"
BACKEND_DIR="$ROOT_DIR/backend"
PYTHON="$BACKEND_DIR/.venv/bin/python"

# ── Load nvm so `npm` is available ──────────────────────────────────────────
export NVM_DIR="${NVM_DIR:-$HOME/.nvm}"
if [ -s "$NVM_DIR/nvm.sh" ]; then
  # shellcheck source=/dev/null
  source "$NVM_DIR/nvm.sh"
else
  echo "Warning: nvm not found. Trying system npm." >&2
fi

# ── 1. Build the React frontend ──────────────────────────────────────────────
echo "▶  Building React frontend…"
cd "$FRONTEND_DIR"
npm run build
cd "$ROOT_DIR"

# ── 2. Start the Django server ───────────────────────────────────────────────
HOST="${HOST:-127.0.0.1}"
PORT="${PORT:-8000}"

echo "▶  Starting Django server at http://$HOST:$PORT"
"$PYTHON" "$BACKEND_DIR/manage.py" runserver "$HOST:$PORT"
