# Running the client ON the Samsung S24 Ultra (Android / Termux)

This is path **(a)**: the Managed Agent *client* runs on the phone itself. Android
isn't a Linux server (no sshd/systemd, no system Python), so this uses
[Termux](https://termux.dev) instead of `../deploy.sh`.

> Path **(b)** — letting the agent *control* the phone as a device via its MCP
> bridge — is separate and lives in `../../agent/`. You can do (a), (b), or both.

## 1. Install Termux

Install Termux from **F-Droid** or GitHub releases (the Play Store build is
outdated). Open it and update: `pkg update -y`.

## 2. Get the app onto the phone

Pick one:

- **git** (if the repo is reachable): `pkg install -y git && git clone <repo-url>`
- **tarball**: download `managed-agent-app.tar.gz`, then in Termux:
  ```bash
  termux-setup-storage           # grant storage access (one-time)
  cp ~/storage/downloads/managed-agent-app.tar.gz .
  tar xzf managed-agent-app.tar.gz
  ```

## 3. Set up + run

```bash
bash managed-agent-app/deploy/termux/termux-setup.sh          # RUNTIME=node for the TS client
nano managed-agent-app/.env                                   # set ANTHROPIC_API_KEY, AGENT_ID, ENVIRONMENT_ID
RUNTIME=python bash managed-agent-app/deploy/run.sh "hello from my S24"
```

`termux-setup.sh` installs the runtime, creates a `.venv` (or runs `npm install`),
and seeds `managed-agent-app/.env` (chmod 600) from the template. `run.sh` sources
that `.env` and launches the client — the same wrapper the Linux deploy uses.

## Notes

- **Keep it awake / background:** `pkg install -y termux-services`, or run under
  `tmux`, so the client isn't killed when the screen locks. Android may still
  aggressively suspend background apps — disable battery optimization for Termux.
- **Auth boundary check:** with a dummy `ANTHROPIC_API_KEY`, a run prints a clean
  `[api error 401]` — that confirms the install works; then set your real key.
- **Shebangs:** always launch the scripts with `bash <script>` (Termux paths
  differ from `/usr/bin`), as shown above.
