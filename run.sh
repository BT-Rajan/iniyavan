#!/usr/bin/env bash
# Installs deps, builds the UI and (re)starts Eng Tutor under pm2.
# Usage: ./run.sh            (uses ./venv, created if missing)
#        VENV=/apps/engtutor/venv ./run.sh
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP=engtutor
VENV="${VENV:-$ROOT/venv}"
cd "$ROOT"

[ -f .env ] || { echo "Missing $ROOT/.env. Copy .env.example to .env and fill it in."; exit 1; }
grep -q '^APP_NAME=' .env || { printf '\nAPP_NAME="Eng Tutor"\n' >> .env; echo "Added APP_NAME to .env (edit it to rename the app)."; }
if ! grep -Eq '^JWT_SECRET=.{32,}' .env || grep -Eq '^JWT_SECRET=.*(change-me|generate-with)' .env; then
  sed -i '/^JWT_SECRET=/d' .env; printf 'JWT_SECRET=%s\n' "$(python3 -c 'import secrets; print(secrets.token_hex(32))')" >> .env
  echo "Generated a new JWT_SECRET in .env (everyone has to sign in again once)."
fi
command -v pm2 >/dev/null || { echo "pm2 is not installed or not on PATH."; exit 1; }
command -v npm >/dev/null || { echo "npm is not installed or not on PATH."; exit 1; }

echo "==> Python dependencies"
[ -x "$VENV/bin/python" ] || python3 -m venv "$VENV"
"$VENV/bin/pip" install -q -r backend/requirements.txt

echo "==> Frontend build"
(cd frontend && { npm ci --no-audit --no-fund || npm install --no-audit --no-fund; } && npm run build)

"$VENV/bin/python" backend/manage.py check || echo "!! No admin account yet. Create one: ./manage.sh admin --email you@example.com"

echo "==> pm2"
pm2 describe "$APP" >/dev/null 2>&1 && pm2 delete "$APP" >/dev/null
pm2 start backend/run.py --name "$APP" --interpreter "$VENV/bin/python" --cwd "$ROOT"
pm2 save >/dev/null

HOST=$(sed -n 's/^HOST=//p' .env | tail -1); PORT=$(sed -n 's/^PORT=//p' .env | tail -1)
echo "==> Eng Tutor is up at http://${HOST:-0.0.0.0}:${PORT:-5252}   (logs: pm2 logs $APP)"
