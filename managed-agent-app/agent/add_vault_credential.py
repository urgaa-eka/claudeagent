"""
Create a Managed Agents Vault credential for an MCP server, so the hosted agent
can authenticate it. This is the hosted-agent counterpart to
deploy/claude-code/add-mcp.sh: the agent declares the server URL in mcp_servers
(agent/mcp-servers.presets.json); this stores the matching credential, keyed by
that URL. Anthropic injects it at egress -- the token never enters the sandbox.

Two auth types (SDK-verified shapes):
  static_bearer  {type, token, mcp_server_url}            -- a fixed bearer token
  mcp_oauth      {type, access_token, mcp_server_url, ...} -- an OAuth access token

Env:
  ANTHROPIC_API_KEY   required.
  MCP_SERVER_URL      required -- must match the agent's mcp_servers url exactly
                                  (host/scheme case, default port, trailing slash
                                  are normalized; a different path/subdomain is not).
  MCP_TOKEN           required -- the bearer / OAuth access token (never committed).
  VAULT_ID            the vault (vlt_...) to add to; omit to create a new vault.
  AUTH_TYPE           static_bearer (default) | mcp_oauth
  DISPLAY_NAME        optional label (defaults to the URL).

Usage:
  ANTHROPIC_API_KEY=... VAULT_ID=vlt_... \
  MCP_SERVER_URL=https://api.githubcopilot.com/mcp MCP_TOKEN=ghp_... \
  python add_vault_credential.py
  # prints the vault id on stdout -> pass it to the client as VAULT_IDS

Then run the client (or agent/smoke_test.py) with VAULT_IDS set to that vault id.
"""

import os
import sys

from anthropic import Anthropic, APIError


def main() -> int:
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("error: ANTHROPIC_API_KEY is not set", file=sys.stderr)
        return 1

    url = os.environ.get("MCP_SERVER_URL", "").strip()
    token = os.environ.get("MCP_TOKEN", "").strip()
    auth_type = os.environ.get("AUTH_TYPE", "static_bearer").strip()
    vault_id = os.environ.get("VAULT_ID", "").strip()

    if not url or not token:
        print("error: set MCP_SERVER_URL and MCP_TOKEN", file=sys.stderr)
        return 1
    if auth_type not in ("static_bearer", "mcp_oauth"):
        print("error: AUTH_TYPE must be 'static_bearer' or 'mcp_oauth'", file=sys.stderr)
        return 1

    client = Anthropic()
    try:
        if not vault_id:
            vault = client.beta.vaults.create(display_name=os.environ.get("VAULT_NAME", "mcp-credentials"))
            vault_id = vault.id
            print(f"[created vault {vault_id}]", file=sys.stderr)

        if auth_type == "static_bearer":
            auth = {"type": "static_bearer", "token": token, "mcp_server_url": url}
        else:
            auth = {"type": "mcp_oauth", "access_token": token, "mcp_server_url": url}

        cred = client.beta.vaults.credentials.create(
            vault_id=vault_id,
            auth=auth,
            display_name=os.environ.get("DISPLAY_NAME", url),
        )
        print(f"[credential {getattr(cred, 'id', '?')} created in {vault_id} for {url} ({auth_type})]",
              file=sys.stderr)
        print(vault_id)  # stdout: the vault id to pass to the client as VAULT_IDS
    except APIError as exc:
        print(f"[api error {getattr(exc, 'status_code', '?')}: {exc}]", file=sys.stderr)
        return 1
    except Exception as exc:  # noqa: BLE001 - top-level clean exit
        print(f"[fatal: {type(exc).__name__}: {exc}]", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
