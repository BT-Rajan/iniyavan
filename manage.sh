#!/usr/bin/env bash
# User admin CLI. Example: VENV=/apps/engtutor/venv ./manage.sh add --name "Arun" --email arun@x.com
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec "${VENV:-$ROOT/venv}/bin/python" "$ROOT/backend/manage.py" "$@"
