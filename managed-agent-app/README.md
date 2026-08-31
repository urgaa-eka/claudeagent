# Managed Agent — minimal client

A tiny, runnable client for an Anthropic-hosted **Managed Agent**, using the
beta **Sessions API**. It creates a session pinned to your agent + environment,
opens the event stream, sends one user message, and prints the agent's reply as
it streams — then stops when the turn goes idle.

Two self-contained entry points are included; use whichever you like:

| Language   | Entry point       | Manifest                          |
| ---------- | ----------------- | --------------------------------- |
| Python     | `python/main.py`  | `python/requirements.txt`         |
| TypeScript | `node/index.ts`   | `node/package.json` + `tsconfig`  |

## 1. Set your IDs

The scaffold ships with **placeholder** IDs. Point it at your Managed Agent by
either editing the two marked constants, or (preferred) setting environment
variables / a `.env` file — the code reads the env vars as overrides:

```bash
cp .env.example .env
# then edit .env:
#   AGENT_ID=agent_01...        # your agent id
#   ENVIRONMENT_ID=env_01...    # your sandbox/compute environment id
```

- Python: `python/main.py`, lines 19–20 (`AGENT_ID` / `ENVIRONMENT_ID`).
- TypeScript: `node/index.ts`, lines 16–17.

The `ANTHROPIC_API_KEY` is **never** baked in — it's read from the environment
at runtime.

## 2. Version requirements

The Sessions API (`client.beta.sessions.*`) is new and **absent from older
SDKs**. The manifests already pin versions that have it:

- Python: `anthropic>=1.1.0` (0.6x and earlier have no `beta.sessions`).
- Node: `@anthropic-ai/sdk>=0.121.0` (0.65.x and earlier have no sessions
  resource).

If a run errors with `beta.sessions is undefined` / `AttributeError` /
`Property 'sessions' does not exist`, the installed SDK is too old — upgrade it
(`pip install -U anthropic`, `npm install @anthropic-ai/sdk@latest`).

## 3. Run it

```bash
export ANTHROPIC_API_KEY=sk-ant-...   # PowerShell: $env:ANTHROPIC_API_KEY="sk-ant-..."

# Python
cd python
pip install -r requirements.txt
python main.py "your prompt here"

# TypeScript (Node 18+)
cd node
npm install
npm start -- "your prompt here"
```

With no argument, each client sends a default "introduce yourself" prompt.

> On modern Debian/Ubuntu/WSL a bare `pip install` may fail with
> `externally-managed-environment`. Use a virtualenv rather than
> `--break-system-packages`:
> ```bash
> python3 -m venv .venv && source .venv/bin/activate
> pip install -r requirements.txt
> ```

## Deploy & connect a device

- **Run this client on a Linux host** → `deploy/` (`deploy.sh`, SSH + rsync).
- **Run this client on a phone (Android/Termux)** → `deploy/termux/`.
- **Build the device's MCP bridge** — the server that exposes the `…/mcp` URL and
  controls the phone (screenshot, tap, swipe, type, launch apps, …) → `bridge/`.
- **Let that device be *controlled* via MCP** — two separate planes:
  - by your **hosted Managed Agent** (`agent_01…`, using the `vlt_…` vaults) → `agent/`
  - by **Claude Code itself** (`claude mcp`) → `deploy/claude-code/`

## Verify the kit

One command runs every check:

```bash
./verify.sh                 # py_compile, bash -n, JSON validity, pytest, tsc --noEmit
AUTH_SMOKE=1 ./verify.sh    # also hits the live endpoint with a dummy key (expects a clean 401)
```

Optional steps (pytest, `tsc`, the auth probe) skip gracefully when their tooling
or a key isn't present, so it's safe to run anywhere. Unit tests live in `tests/`
(`pip install pytest` to run them).

Or use the **Makefile** — `make help` lists everything:

```bash
make install    # python venv (+ pytest) and node modules
make run        # run the client (RUNTIME=python|node PROMPT="...")
make verify     # the full check suite above
make deploy DEPLOY_ARGS="--host 1.2.3.4 --key ~/.ssh/id_ed25519"
make clean
```

## How it works

The client implements the Sessions API flow end to end:

1. **Create** — `sessions.create(agent=<id>, environment_id=<id>)` returns a
   session with an `.id`. (Kept inside the try/except so an auth or bad-request
   error exits cleanly with `[api error 401: ...]` instead of a raw traceback.)
2. **Stream** — `sessions.events.stream(session.id)` opens the event stream
   **before** sending, so no early events are missed.
3. **Send** — `sessions.events.send(session.id, events=[{ type: "user.message",
   content: [{ type: "text", text: ... }] }])`.
4. **Consume** — for each `agent.message`, print its text blocks as they arrive;
   any `*.error` event is reported and exits non-zero.
5. **Stop** — on `session.status_idle`, print a trailing newline and stop; its
   `stop_reason.type` says why the turn ended (`end_turn`, `requires_action`,
   `budget_reached`, ...).

Other events (`session.status_running`, `agent.thinking`, `agent.tool_use`,
`session.usage`, ...) are safely ignored by this minimal loop.
