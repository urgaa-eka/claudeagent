#!/usr/bin/env bash
#
# add-mcp.sh -- register an HTTP MCP server with Claude Code (the Plane-1 pattern),
# reusable for any server. Thin wrapper around `claude mcp add --transport http`.
#
# Usage:
#   ./add-mcp.sh <preset>                     # a known server (see presets below)
#   ./add-mcp.sh <name> <url> [token]         # any HTTP MCP server
#
# Presets (URL prefilled; each server still needs its own auth):
#   github        https://api.githubcopilot.com/mcp
#   hf-endpoints  https://endpoints.huggingface.co/mcp
#   linear        https://mcp.linear.app/mcp
#   notion        https://mcp.notion.com/mcp
#   sentry        https://mcp.sentry.dev/mcp
#   (anything else needs an explicit <url>, e.g. an S24 device bridge)
#
# Auth: pass a bearer token as the 3rd arg or via MCP_TOKEN env (attached as
#   "Authorization: Bearer <token>"). Prefer `claude mcp login <name>` for OAuth
#   servers. Never commit tokens.
#
# Scope: SCOPE=local (default) | user | project.
#
# Examples:
#   ./add-mcp.sh github
#   MCP_TOKEN=hf_xxx ./add-mcp.sh hf-endpoints
#   SCOPE=user ./add-mcp.sh s24 https://my-bridge.example/mcp "$S24_TOKEN"
set -euo pipefail

SCOPE="${SCOPE:-local}"

preset_url() {
  case "$1" in
    github)       echo "https://api.githubcopilot.com/mcp" ;;
    hf-endpoints) echo "https://endpoints.huggingface.co/mcp" ;;
    linear)       echo "https://mcp.linear.app/mcp" ;;
    notion)       echo "https://mcp.notion.com/mcp" ;;
    sentry)       echo "https://mcp.sentry.dev/mcp" ;;
    *)            echo "" ;;
  esac
}

usage() { sed -n '2,26p' "$0" | sed 's/^#\{0,1\} \{0,1\}//'; }

[ $# -ge 1 ] || { usage; exit 1; }
case "$1" in -h|--help) usage; exit 0 ;; esac

NAME="$1"
URL="${2:-$(preset_url "$NAME")}"
TOKEN="${3:-${MCP_TOKEN:-}}"

[ -n "$URL" ] || { echo "error: no URL for '$NAME' and no matching preset. Usage: ./add-mcp.sh <name> <url> [token]" >&2; exit 1; }
command -v claude >/dev/null 2>&1 || { echo "error: 'claude' CLI not found -- install Claude Code" >&2; exit 1; }
case "$SCOPE" in local|user|project) ;; *) echo "error: SCOPE must be local|user|project" >&2; exit 1 ;; esac

args=(mcp add --transport http --scope "$SCOPE" "$NAME" "$URL")
[ -n "$TOKEN" ] && args+=(--header "Authorization: Bearer ${TOKEN}")

echo "==> claude mcp add '$NAME' -> $URL (scope: $SCOPE)${TOKEN:+, with bearer auth}"
claude "${args[@]}"

echo
echo "==> Status:"
claude mcp get "$NAME" 2>&1 | sed 's/^/    /' || true
echo
echo "Next:"
echo "  - if it says 'Needs authentication' and the server uses OAuth:  claude mcp login $NAME"
echo "  - remove:  claude mcp remove $NAME -s $SCOPE"
