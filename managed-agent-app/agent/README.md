# Connecting the S24 to the agent (device control via MCP)

This is path **(b)**: the Managed Agent *drives* the Samsung S24 Ultra by calling
tools on the phone's **MCP bridge**. In Anthropic's Managed Agents platform the
config is deliberately **split in two** so secrets never live in the reusable
agent definition:

| Half | Where | Holds |
| --- | --- | --- |
| **Which server** to connect to | the **Agent** definition (`mcp_servers` + a `mcp_toolset` tool) | `type`, `name`, `url` — **no auth** |
| **How to authenticate** it | a **Vault**, attached via `vault_ids` at **session create** | the credential, keyed by server URL |

Your two `vlt_…` entries (`samsung-s24-ultra`, `samsung-s24-ultra-mcp`) are the
**Vault** half — Anthropic-managed credentials injected at egress, never exposed
to the sandbox. This repo can't read or verify them (that needs the Managed
Agents API with your key); it just references them by id.

## What you still need to provide

**The S24 MCP bridge's URL** (Streamable HTTP endpoint, e.g.
`https://…/mcp`). The vault authenticates it, but the agent needs the URL to
connect. Put it in `mcp-server.example.json`.

## Wiring (three steps)

**1. Declare the server on the agent.** Merge the two arrays from
`mcp-server.example.json` into your agent (`agent_01…`). Either bake it into your
agent definition, or apply it as a session-local override on an idle session with
`sessions.update(session_id, agent={... mcp_servers, tools ...})`.

**2. Make sure a vault credential is keyed to that exact URL.** The vault→server
match is **by URL** (scheme/host lowercased, default port and trailing slash
ignored; a different path, subdomain, or non-default port breaks it). The
credential type is `static_bearer` (a fixed bearer token — typical for a custom
device bridge) or `mcp_oauth` (auto-refreshed OAuth). This is almost certainly
what `vlt_…samsung-s24-ultra-mcp` already holds — just confirm its
`mcp_server_url` equals the URL you put in step 1.

> ⚠️ **MCP auth tokens ≠ REST API keys.** A hosted MCP server wants an OAuth
> bearer for *its MCP endpoint*, not the underlying service's API key. Confirm
> the vault holds the bridge's MCP token.

**3. Attach the vault(s) when the client opens a session.** The client in this
repo now reads `VAULT_IDS` and passes it to `sessions.create(vault_ids=[…])`:

```bash
# in managed-agent-app/.env  (or exported) -- your real vlt_ ids, comma-separated.
# Keep them here, in the gitignored .env; don't hardcode them into the repo.
VAULT_IDS=vlt_<samsung-s24-ultra-mcp-id>,vlt_<samsung-s24-ultra-id>
```

Then run the client as usual (locally, or on the phone via `deploy/termux/`):

```bash
python main.py "Open Settings and tell me the current battery level."
```

The agent now sees the S24's MCP tools and can call them; each call is routed
through Anthropic's proxy, which injects the vaulted credential at egress.

## Wiring preset servers in bulk

To give the agent the same servers as the Claude Code plane (`deploy/claude-code/add-mcp.sh`),
merge `mcp-servers.presets.json` into the agent — it declares `github`,
`hf-endpoints`, `linear`, `notion`, and `sentry` (keep only what you want). Then
create one Vault credential per server, keyed to its URL, with
`add_vault_credential.py`:

```bash
# one credential per server (token stays in env, never committed):
ANTHROPIC_API_KEY=... VAULT_ID=vlt_... \
MCP_SERVER_URL=https://api.githubcopilot.com/mcp MCP_TOKEN=ghp_... \
python add_vault_credential.py            # prints the vault id

# repeat for each server URL you enabled (AUTH_TYPE=mcp_oauth for OAuth tokens).
# omit VAULT_ID to create a fresh vault; reuse one VAULT_ID for many servers.
```

Then run the client / smoke test with `VAULT_IDS` set to that vault id. Each
credential's `mcp_server_url` must match the agent's `mcp_servers` url (host/scheme
case, default port, and trailing slash are normalized; a different path or
subdomain is not). Same servers, same vault → both planes stay in sync.

> The `vlt_…samsung-s24-ultra*` vaults you already have are the S24 equivalent of
> what `add_vault_credential.py` produces here.

## Verify (smoke test)

Once steps 1–3 are done, confirm the link end-to-end with `smoke_test.py`:

```bash
ANTHROPIC_API_KEY=... AGENT_ID=agent_01... ENVIRONMENT_ID=env_01... \
VAULT_IDS=vlt_<mcp-id>,vlt_<device-id> python smoke_test.py
```

It opens a session with the vault(s) attached, asks the agent to list its tools,
prints any `*mcp*` events, and flags a `session.error` (the tell-tale of a
vault/URL mismatch). A clean run where the agent names the S24 tools = Plane 2 is
live. (With a dummy key it exits on a clean `[api error 401]`, proving the wiring
before you use a real key.)

## Good to know

- **A bad/mismatched credential does not fail session creation.** The session
  starts, then emits a `session.error` describing the MCP auth failure; auth
  retries on the next idle→running transition. So if the phone tools don't
  appear, check for a `session.error` and re-check the URL match in step 2.
- **`vault_ids` is set at session *create* only** — it can't be added via
  `sessions.update()`.
- Only attach the vaults you need. If `vlt_…samsung-s24-ultra` (the non-`-mcp`
  one) is an `environment_variable` credential for a *custom* tool rather than an
  MCP server, it's attached the same way but consumed by that tool, not the
  `mcp_toolset`.
