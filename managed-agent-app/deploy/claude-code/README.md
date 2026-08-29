# Let Claude Code drive the S24 (`claude mcp`)

This is the **Claude Code plane**: register the S24 Ultra's MCP bridge with the
Claude Code CLI so the assistant you talk to in your terminal gains the phone's
tools. It is fully separate from the hosted-agent path in `../../agent/`:

|  | Claude Code plane (here) | Hosted-agent plane (`../../agent/`) |
| --- | --- | --- |
| Who drives the phone | the `claude` CLI you run locally | your Managed Agent `agent_01…` |
| Config store | Claude Code MCP config (`claude mcp …`) | agent `mcp_servers` + session `vault_ids` |
| Auth | bearer header or `claude mcp login` OAuth | the `vlt_…` vault, injected at egress |
| Uses `vlt_…` vaults? | **No** | Yes |

## Prerequisites

- Claude Code **≥ 2.1** (`claude --version`).
- A network route from your machine to the bridge's Streamable-HTTP endpoint.
- The bridge's URL and (if it uses static auth) a bearer token.

## Add it

```bash
export S24_MCP_URL='https://<your-s24-bridge>/mcp'
export S24_MCP_TOKEN='<bridge-bearer-token>'      # omit if the bridge uses OAuth
SCOPE=user ./add-s24-mcp.sh                        # user = available in all your projects
```

That wraps the exact CLI call:

```bash
claude mcp add --transport http --scope user samsung-s24-ultra \
  https://<your-s24-bridge>/mcp --header "Authorization: Bearer <token>"
```

**Scopes:** `local` (this project only, default), `user` (all your projects),
`project` (checked into `.mcp.json` and shared with the repo — don't put secrets
in headers at this scope).

**OAuth bridges:** skip `S24_MCP_TOKEN`, add the server, then `claude mcp login
samsung-s24-ultra`.

## Add any MCP server (`add-mcp.sh`)

`add-s24-mcp.sh` is the S24-specific convenience; `add-mcp.sh` is the general,
reusable version — register **any** HTTP MCP server, with presets for common ones:

```bash
./add-mcp.sh github                              # preset URL
MCP_TOKEN=hf_xxx ./add-mcp.sh hf-endpoints       # preset + bearer token
SCOPE=user ./add-mcp.sh s24 https://<bridge>/mcp "$S24_TOKEN"   # any server
./add-mcp.sh --help
```

| Preset | URL | Typical auth |
| --- | --- | --- |
| `github` | `https://api.githubcopilot.com/mcp` | OAuth / PAT |
| `hf-endpoints` | `https://endpoints.huggingface.co/mcp` | HF token (bearer) or `claude mcp login` |
| `linear` | `https://mcp.linear.app/mcp` | OAuth |
| `notion` | `https://mcp.notion.com/mcp` | OAuth |
| `sentry` | `https://mcp.sentry.dev/mcp` | OAuth |

Anything not in the table just needs an explicit `<url>` (e.g. your S24 bridge).
Token via 3rd arg or `MCP_TOKEN` env — never committed. `SCOPE` = `local`
(default) / `user` / `project`. After adding, the script prints `claude mcp get
<name>`; a `Needs authentication` status means run `claude mcp login <name>` (or
re-add with a bearer header).

## Verify

```bash
claude mcp get samsung-s24-ultra     # details + health check
claude mcp list                      # all servers
# inside a session:  /mcp            # lists the phone's tools; then just ask Claude to use them
```

## Notes

- **Can't be done from this sandbox.** This remote session has no route to your
  phone, and `claude mcp add` configures *your local* Claude Code, not this
  session. Run it where you actually use Claude Code.
- **Token hygiene:** the token is passed via `S24_MCP_TOKEN` and attached as a
  header — it isn't written into this repo. Avoid `--scope project` with a header
  token, since that scope is meant to be committed.
