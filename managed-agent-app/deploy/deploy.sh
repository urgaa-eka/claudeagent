#!/usr/bin/env bash
#
# Deploy the Managed Agent client to a device over SSH (key auth).
#
# Runs on YOUR machine (or CI) -- wherever the SSH key and a network route to
# the device live. It copies the app, installs its dependencies on the device,
# and installs a small run.sh wrapper. Secrets (ANTHROPIC_API_KEY, AGENT_ID,
# ENVIRONMENT_ID) live in an env file ON THE DEVICE and are never baked in.
#
# Usage:
#   ./deploy.sh --host 198.51.100.7 --user deploy --port 22 \
#               --key ~/.ssh/id_ed25519 [--runtime python|node] \
#               [--remote-dir /opt/managed-agent] [--env-file ./device.env] \
#               [--smoke "hello"]
#
# Every flag also has an env-var form: HOST, SSH_USER, PORT, SSH_KEY,
# RUNTIME, REMOTE_DIR, ENV_FILE, SMOKE.
set -euo pipefail

HOST="${HOST:-203.0.113.10}"
SSH_USER="${SSH_USER:-deploy}"
PORT="${PORT:-22}"
SSH_KEY="${SSH_KEY:-$HOME/.ssh/id_ed25519}"
RUNTIME="${RUNTIME:-python}"
REMOTE_DIR="${REMOTE_DIR:-/opt/managed-agent}"
ENV_FILE="${ENV_FILE:-}"
SMOKE="${SMOKE:-}"

die() { echo "error: $*" >&2; exit 1; }

while [ $# -gt 0 ]; do
  case "$1" in
    --host)       HOST="$2"; shift 2;;
    --user)       SSH_USER="$2"; shift 2;;
    --port)       PORT="$2"; shift 2;;
    --key)        SSH_KEY="$2"; shift 2;;
    --runtime)    RUNTIME="$2"; shift 2;;
    --remote-dir) REMOTE_DIR="$2"; shift 2;;
    --env-file)   ENV_FILE="$2"; shift 2;;
    --smoke)      SMOKE="$2"; shift 2;;
    -h|--help)    sed -n '2,20p' "$0" | sed 's/^# \{0,1\}//'; exit 0;;
    *)            die "unknown argument: $1 (try --help)";;
  esac
done

case "$RUNTIME" in python|node) ;; *) die "--runtime must be 'python' or 'node'";; esac

APP_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
[ -d "$APP_ROOT/$RUNTIME" ] || die "no '$RUNTIME' folder under $APP_ROOT"

command -v rsync >/dev/null 2>&1 || die "rsync not found on this machine"
command -v ssh   >/dev/null 2>&1 || die "ssh not found on this machine"
[ -f "$SSH_KEY" ] || die "SSH key not found: $SSH_KEY (pass --key)"

if [ "$HOST" = "203.0.113.10" ]; then
  echo "WARNING: 203.0.113.10 is a reserved documentation IP (RFC 5737) and does not route." >&2
  echo "         Pass your real device address with --host <ip-or-hostname>." >&2
fi

SSH_OPTS=(-p "$PORT" -i "$SSH_KEY" -o StrictHostKeyChecking=accept-new -o ConnectTimeout=10)
remote() { ssh "${SSH_OPTS[@]}" "${SSH_USER}@${HOST}" "$@"; }

echo "==> Deploying '$RUNTIME' client to ${SSH_USER}@${HOST}:${REMOTE_DIR} (port ${PORT})"
remote "mkdir -p '$REMOTE_DIR'"

echo "==> Syncing files"
rsync -az --delete \
  -e "ssh ${SSH_OPTS[*]}" \
  --exclude '.git' --exclude 'node_modules' --exclude '.venv' \
  --exclude '__pycache__' --exclude '*.pyc' --exclude '.env' \
  "$APP_ROOT/" "${SSH_USER}@${HOST}:${REMOTE_DIR}/"

echo "==> Installing dependencies ($RUNTIME) on the device"
if [ "$RUNTIME" = "python" ]; then
  remote "cd '$REMOTE_DIR/python' && python3 -m venv .venv && ./.venv/bin/pip install -q -U pip && ./.venv/bin/pip install -q -r requirements.txt"
else
  remote "cd '$REMOTE_DIR/node' && npm install --no-audit --no-fund"
fi

# Secrets live only on the device.
if [ -n "$ENV_FILE" ]; then
  [ -f "$ENV_FILE" ] || die "--env-file not found: $ENV_FILE"
  echo "==> Uploading env file to $REMOTE_DIR/.env (mode 600)"
  scp "${SSH_OPTS[@]}" "$ENV_FILE" "${SSH_USER}@${HOST}:${REMOTE_DIR}/.env"
  remote "chmod 600 '$REMOTE_DIR/.env'"
else
  remote "test -f '$REMOTE_DIR/.env' || { cp '$REMOTE_DIR/.env.example' '$REMOTE_DIR/.env' && chmod 600 '$REMOTE_DIR/.env' && echo 'NOTE: created $REMOTE_DIR/.env from template -- edit it and set ANTHROPIC_API_KEY (+ AGENT_ID / ENVIRONMENT_ID).'; }"
fi

remote "chmod +x '$REMOTE_DIR/deploy/run.sh'"

echo "==> Done. Run it on the device with:"
echo "    ssh -p $PORT -i $SSH_KEY ${SSH_USER}@${HOST} 'RUNTIME=$RUNTIME $REMOTE_DIR/deploy/run.sh \"your prompt\"'"

if [ -n "$SMOKE" ]; then
  echo "==> Smoke test on the device (prompt: $SMOKE)"
  remote "RUNTIME=$RUNTIME '$REMOTE_DIR/deploy/run.sh' '$SMOKE'" \
    || echo "(non-zero exit -- a clean '[api error 401]' still proves the wiring; set a real ANTHROPIC_API_KEY in $REMOTE_DIR/.env)" >&2
fi
