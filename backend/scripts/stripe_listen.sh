#!/usr/bin/env bash
# Kept for macOS/Linux muscle memory; the real logic is in stripe_listen.py (works on Windows too).
# Run from backend/:  ./scripts/stripe_listen.sh
set -euo pipefail
cd "$(dirname "$0")/.."
PY=.venv/bin/python; [[ -x "$PY" ]] || PY=.venv/Scripts/python; [[ -x "$PY" || -f "$PY.exe" ]] || PY=python3
exec "$PY" scripts/stripe_listen.py
