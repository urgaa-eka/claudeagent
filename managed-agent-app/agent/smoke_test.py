"""
Smoke test for the hosted-agent device link (Plane 2).

Opens a Managed Agents session with the S24 vault(s) attached and checks whether
the agent can see the Samsung S24 MCP tools. It:

  - creates a session with vault_ids (the credential half of the MCP wiring),
  - asks the agent to enumerate its tools,
  - prints any `*mcp*` events it observes,
  - loudly surfaces any `*.error` event -- the usual signal that a vault
    credential is NOT keyed to the MCP server URL (see agent/README.md, step 2).

Env: ANTHROPIC_API_KEY, AGENT_ID, ENVIRONMENT_ID, VAULT_IDS (comma-separated),
     optional PROMPT. Exits 0 on a clean run, 1 on error.

Run:  ANTHROPIC_API_KEY=... AGENT_ID=agent_01... ENVIRONMENT_ID=env_01... \
      VAULT_IDS=vlt_...,vlt_... python smoke_test.py
"""

import os
import sys

from anthropic import Anthropic, APIError

AGENT_ID = os.environ.get("AGENT_ID", "__AGENT_ID__")
ENVIRONMENT_ID = os.environ.get("ENVIRONMENT_ID", "__ENVIRONMENT_ID__")
VAULT_IDS = [v.strip() for v in os.environ.get("VAULT_IDS", "").split(",") if v.strip()]
PROMPT = os.environ.get(
    "PROMPT",
    "List every tool you can call, one per line. Then state explicitly whether "
    "you have tools that control a Samsung S24 Ultra device, and if so, name them.",
)


def _text_blocks(content):
    if content is None:
        return
    if isinstance(content, str):
        yield content
        return
    for block in content:
        btype = getattr(block, "type", None) or (block.get("type") if isinstance(block, dict) else None)
        if btype in ("text", None):
            text = getattr(block, "text", None)
            if text is None and isinstance(block, dict):
                text = block.get("text")
            if text:
                yield text


def main() -> int:
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("error: ANTHROPIC_API_KEY is not set", file=sys.stderr)
        return 1
    if not VAULT_IDS:
        print("warning: VAULT_IDS is empty -- the S24 credential won't be attached, "
              "so the agent won't see the device tools.", file=sys.stderr)

    client = Anthropic()
    saw_mcp = False
    saw_error = False

    try:
        create_kwargs = {"agent": AGENT_ID, "environment_id": ENVIRONMENT_ID}
        if VAULT_IDS:
            create_kwargs["vault_ids"] = VAULT_IDS
        session = client.beta.sessions.create(**create_kwargs)
        print(f"[session {session.id} created; vaults: {VAULT_IDS or 'none'}]", file=sys.stderr)

        with client.beta.sessions.events.stream(session.id) as stream:
            client.beta.sessions.events.send(
                session.id,
                events=[{"type": "user.message", "content": [{"type": "text", "text": PROMPT}]}],
            )
            for event in stream:
                etype = getattr(event, "type", "") or ""
                if etype == "agent.message":
                    for text in _text_blocks(getattr(event, "content", None)):
                        print(text, end="", flush=True)
                elif "mcp" in etype:
                    saw_mcp = True
                    print(f"\n[mcp event: {etype}]", file=sys.stderr)
                elif etype.endswith(".error"):
                    saw_error = True
                    print(f"\n[session error: {getattr(event, 'error', event)}]", file=sys.stderr)
                elif etype == "session.status_idle":
                    print()
                    break
    except APIError as exc:
        print(f"\n[api error {getattr(exc, 'status_code', '?')}: {exc}]", file=sys.stderr)
        return 1
    except Exception as exc:  # noqa: BLE001 - top-level clean exit
        print(f"\n[fatal: {type(exc).__name__}: {exc}]", file=sys.stderr)
        return 1

    print("\n--- smoke result ---", file=sys.stderr)
    print(f"  mcp events seen:    {saw_mcp}", file=sys.stderr)
    print(f"  session.error seen: {saw_error}", file=sys.stderr)
    if saw_error:
        print("  -> a session.error usually means the vault credential isn't keyed to the "
              "MCP server URL. Re-check agent/README.md step 2 (URL match).", file=sys.stderr)
        return 1
    print("  -> if the agent listed the S24 tools above and there was no error, Plane 2 is live.",
          file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
