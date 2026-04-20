#!/usr/bin/env bash
# Load `.env.development` into the environment, then exec a command.
# Delegates to with_dev_env.py (stdlib + wingmanem.envfile) so variables are
# visible to Gunicorn and all workers.
#
# Usage (from project root):
#   ./scripts/with_dev_env.sh python web_app.py
#   ./scripts/with_dev_env.sh gunicorn -w 2 -b 127.0.0.1:8000 wsgi:app
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
exec python3 "$ROOT/scripts/with_dev_env.py" "$@"
