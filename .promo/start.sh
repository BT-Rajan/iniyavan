#!/usr/bin/env bash
# Starts a throwaway Zigora server for the promo on $PROMO_PORT, with fresh demo data in $PROMO_WORK (.promo/server.py) and a
# stand-in AI. Stays in the foreground; the promo stops it when it's done. Never touches the real database.
# Python: $PROMO_PYTHON, else the project's venv (as run.sh makes it), else python3, with backend/requirements.txt installed.
set -euo pipefail
PY="${PROMO_PYTHON:-}"
[ -n "$PY" ] || { [ -x venv/bin/python ] && PY=venv/bin/python; } || true
[ -n "$PY" ] || PY=python3
exec "$PY" .promo/server.py
