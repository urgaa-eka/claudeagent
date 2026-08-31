#!/usr/bin/env bash
#
# Register the Samsung S24 Ultra MCP bridge with Claude Code ITSELF, so this CLI
# (not the hosted Managed Agent) can call the phone's tools.
#
# Run on the machine where you use Claude Code, with a network route to the bridge.
# Requires Claude Code >= 2.1 (uses `claude mcp add --transport http`).
#
# The bridge token is read from S24_MCP_TOKEN (env) so it never lands in this repo
# or your shell history.
#
#   IMPORTANT: this path does NOT use the vlt_ Managed Agents vaults. Those apply
#   only to the hosted-agent path (../../agent/). Here the token goes straight to
#   Claude Code's own MCP config.
set -euo pipefail

NAME="${NAME:-samsung-s24-ultra}"
URL="${S24_MCP_URL:-}"
SCOPE="${SCOPE:-local}"   # local (this project) | user (all your projects) | project (shared via .mcp.json)

[ -n "$URL" ] || { echo "error: set S24_MCP_URL to the bridge's Streamable-HTTP endpoint, e.g. https://<host>/mcp" >&2; exit 1; }
command -v claude >/dev/null 2>&1 || { echo "error: 'claude' CLI not found -- install Claude Code first" >&2; exit 1; }
case "$SCOPE" in local|user|project) ;; *) echo "error: SCOPE must be local|user|project" >&2; exit 1;; esac

args=(mcp add --transport http --scope "$SCOPE" "$NAME" "$URL")
[ -n "${S24_MCP_TOKEN:-}" ] && args+=(--header "Authorization: Bearer ${S24_MCP_TOKEN}")

echo "==> Registering MCP server '$NAME' -> $URL (scope: $SCOPE)${S24_MCP_TOKEN:+, with bearer auth}"
claude "${args[@]}"

echo
echo "==> Verify:"
echo "    claude mcp get $NAME     # details + health check"
echo "    claude mcp list          # all configured servers"
echo "    # then, inside a Claude Code session:  /mcp   (shows the phone's tools)"
echo
echo "If the bridge uses OAuth instead of a static bearer, omit S24_MCP_TOKEN and run:"
echo "    claude mcp login $NAME"
