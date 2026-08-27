"""
Minimal Managed Agents client (Python).

Talks to an Anthropic-hosted agent using the beta Sessions API:
  1. create a session pinned to an agent + environment
  2. open the session event stream
  3. send a `user.message` event
  4. print `agent.message` text as it streams
  5. stop on `session.status_idle`, exit cleanly on errors
"""

import os
import sys

from anthropic import Anthropic, APIError

# --- Config -----------------------------------------------------------------
# Replace the two defaults below (or set the matching env vars) before running.
AGENT_ID = os.environ.get("AGENT_ID", "__AGENT_ID__")
ENVIRONMENT_ID = os.environ.get("ENVIRONMENT_ID", "__ENVIRONMENT_ID__")


def _iter_text_blocks(content):
    """Yield text from an event's `content`, tolerating a few shapes."""
    if content is None:
        return
    if isinstance(content, str):
        yield content
        return
    for block in content:
        # SDK model objects expose attributes; raw dicts expose keys.
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

    prompt = " ".join(sys.argv[1:]) or "Hello! Please introduce yourself in one sentence."

    client = Anthropic()  # reads ANTHROPIC_API_KEY from the environment

    try:
        # 1. Create the session. Keeping this inside the try means an auth or
        #    bad-request failure here exits cleanly instead of dumping a traceback.
        session = client.beta.sessions.create(
            agent=AGENT_ID,
            environment_id=ENVIRONMENT_ID,
        )
        print(f"[session created: {session.id}]", file=sys.stderr)

        # 2. Open the event stream, then 3. send the user message into it.
        #    Open the stream BEFORE sending so no early events are missed.
        with client.beta.sessions.events.stream(session.id) as stream:
            client.beta.sessions.events.send(
                session.id,
                events=[
                    {
                        "type": "user.message",
                        "content": [{"type": "text", "text": prompt}],
                    }
                ],
            )

            # 4./5. Consume events.
            for event in stream:
                etype = getattr(event, "type", None)

                if etype == "agent.message":
                    for text in _iter_text_blocks(getattr(event, "content", None)):
                        print(text, end="", flush=True)

                elif etype and etype.endswith(".error"):
                    print(f"\n[stream error: {getattr(event, 'error', event)}]", file=sys.stderr)
                    return 1

                elif etype == "session.status_idle":
                    print()  # trailing newline after streamed text
                    stop = getattr(event, "stop_reason", None)
                    print(f"[done: {getattr(stop, 'type', stop)}]", file=sys.stderr)
                    break

    except KeyboardInterrupt:
        print("\n[interrupted]", file=sys.stderr)
        return 130
    except APIError as exc:
        # Auth / rate-limit / bad-request etc. from the Anthropic API.
        status = getattr(exc, "status_code", "?")
        print(f"\n[api error {status}: {exc}]", file=sys.stderr)
        return 1
    except Exception as exc:  # noqa: BLE001 - top-level clean exit
        print(f"\n[fatal: {type(exc).__name__}: {exc}]", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
