# Deploying the Managed Agent client to a device

`deploy.sh` pushes this app onto a device over SSH, installs its dependencies
there, and leaves a `run.sh` wrapper you can invoke. It is a **thin, auditable
wrapper around `rsync` + `ssh`** — read it before running.

## Where this runs

Run `deploy.sh` **from your own machine or CI** — wherever the SSH key and a
network route to the device already exist. It cannot be run from an environment
that has no `ssh`/`rsync` client or no key (for example, a sandboxed web
session).

## Prerequisites

- On the machine you run it from: `ssh` and `rsync`, and the private key for the
  device's `deploy` user.
- On the device: `python3` (for the default Python runtime) **or** Node 18+
  (for `--runtime node`), plus write access to the target directory.

## Quickstart

```bash
cd managed-agent-app/deploy

./deploy.sh \
  --host   <your-device-ip-or-hostname> \
  --user   deploy \
  --port   22 \
  --key    ~/.ssh/id_ed25519 \
  --runtime python \
  --smoke  "Hello from the device"
```

> **Note on `203.0.113.10`:** that address (from your original request) is in
> `203.0.113.0/24`, which RFC 5737 reserves for documentation — it does not
> route to a real host. Pass your device's actual address with `--host`.
> `deploy.sh` warns and continues if it sees the placeholder.

Every flag has an env-var equivalent (`HOST`, `SSH_USER`, `PORT`, `SSH_KEY`,
`RUNTIME`, `REMOTE_DIR`, `ENV_FILE`, `SMOKE`), so it drops cleanly into CI.

## What it does

1. `mkdir -p` the remote dir (default `/opt/managed-agent`).
2. `rsync` the app to the device (excludes `.git`, `node_modules`, `.venv`,
   `__pycache__`, and `.env` so device secrets are never overwritten).
3. Installs deps on the device:
   - **python** → creates `python/.venv` and `pip install -r requirements.txt`
   - **node** → `npm install` in `node/`
4. Ensures a device-local `.env` exists (mode `600`), from `.env.example` if
   absent — or uploads yours with `--env-file ./device.env`.
5. Installs the `run.sh` wrapper. With `--smoke "..."`, runs the client once.

## Secrets

Secrets stay **on the device**, in `<remote-dir>/.env` (chmod `600`), and are
loaded at run time — never baked into the image or passed on the command line.
Set at minimum:

```dotenv
ANTHROPIC_API_KEY=sk-ant-...
AGENT_ID=agent_01...          # optional; overrides the placeholder default
ENVIRONMENT_ID=env_01...      # optional; overrides the placeholder default
```

A `--smoke` run with no real key still returns a clean `[api error 401]`, which
proves the install and wiring are correct — then just fill in the real key.

## Running it on the device

```bash
ssh -p 22 -i ~/.ssh/id_ed25519 deploy@<host> \
  'RUNTIME=python /opt/managed-agent/deploy/run.sh "your prompt"'
```

## Optional: run as a systemd service

`managed-agent.service` is a one-shot unit template (the client sends one prompt
and exits). See the comments at the top of that file to install it and, if you
want scheduled runs, pair it with a `.timer`.
