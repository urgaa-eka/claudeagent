#!/usr/bin/env bash
#
# Set up the Managed Agent client ON a Samsung S24 Ultra (Android) via Termux.
# This is the Android counterpart to ../deploy.sh (which targets a Linux host).
#
# Run it INSIDE Termux on the phone:
#   bash managed-agent-app/deploy/termux/termux-setup.sh
#
# RUNTIME=python (default) or RUNTIME=node.
set -euo pipefail

RUNTIME="${RUNTIME:-python}"
case "$RUNTIME" in python|node) ;; *) echo "RUNTIME must be python or node" >&2; exit 2 ;; esac

case "${PREFIX:-}" in
  *com.termux*) : ;;
  *) echo "warning: PREFIX ($PREFIX) doesn't look like Termux; continuing anyway." >&2 ;;
esac

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"   # deploy/termux -> app root
cd "$ROOT"

echo "==> Updating Termux packages"
pkg update -y

if [ "$RUNTIME" = "python" ]; then
  echo "==> Installing python"
  pkg install -y python
  cd "$ROOT/python"
  python -m venv .venv
  ./.venv/bin/pip install -U pip
  ./.venv/bin/pip install -r requirements.txt
else
  echo "==> Installing nodejs"
  pkg install -y nodejs
  cd "$ROOT/node"
  npm install --no-audit --no-fund
fi

# Device-local secrets/config (never committed; sourced by ../run.sh at run time).
if [ ! -f "$ROOT/.env" ]; then
  cp "$ROOT/.env.example" "$ROOT/.env"
  chmod 600 "$ROOT/.env"
  echo "NOTE: created $ROOT/.env -- edit it (nano $ROOT/.env) and set at least"
  echo "      ANTHROPIC_API_KEY, plus AGENT_ID / ENVIRONMENT_ID, and (to let the"
  echo "      agent drive this phone) VAULT_IDS."
fi

echo "==> Done. Run the client on the phone with:"
echo "    RUNTIME=$RUNTIME bash $ROOT/deploy/run.sh \"hello from my S24\""
