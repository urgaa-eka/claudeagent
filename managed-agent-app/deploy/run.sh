#!/usr/bin/env bash
# Run the Managed Agent client on the device. Sources .env for secrets.
#
# Usage:  RUNTIME=python|node  run.sh  "your prompt"
# (installed at <remote-dir>/deploy/run.sh by deploy.sh)
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RUNTIME="${RUNTIME:-python}"

# Load device-local secrets/config if present (ANTHROPIC_API_KEY, AGENT_ID, ...).
if [ -f "$ROOT/.env" ]; then
  set -a; . "$ROOT/.env"; set +a
fi

case "$RUNTIME" in
  python) exec "$ROOT/python/.venv/bin/python" "$ROOT/python/main.py" "$@" ;;
  node)   cd "$ROOT/node" && exec npm start --silent -- "$@" ;;
  *)      echo "unknown RUNTIME: $RUNTIME (use 'python' or 'node')" >&2; exit 2 ;;
esac
