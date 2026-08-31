/**
 * Minimal Managed Agents client (TypeScript / Node).
 *
 * Talks to an Anthropic-hosted agent using the beta Sessions API:
 *   1. create a session pinned to an agent + environment
 *   2. open the session event stream
 *   3. send a `user.message` event
 *   4. print `agent.message` text as it streams
 *   5. stop on `session.status_idle`, exit cleanly on errors
 */

import Anthropic from "@anthropic-ai/sdk";

// --- Config -----------------------------------------------------------------
// Replace the two defaults below (or set the matching env vars) before running.
const AGENT_ID = process.env.AGENT_ID ?? "__AGENT_ID__";
const ENVIRONMENT_ID = process.env.ENVIRONMENT_ID ?? "__ENVIRONMENT_ID__";
// Optional: Managed Agents Vault credential id(s) (vlt_...) to attach at session
// create. These authenticate connected MCP servers (e.g. a device bridge) at egress;
// the secret never enters the sandbox. Comma-separated; empty = none attached.
const VAULT_IDS = (process.env.VAULT_IDS ?? "")
  .split(",")
  .map((s) => s.trim())
  .filter(Boolean);

/** Extract text from an event's `content`, tolerating a few shapes. */
function* iterText(content: unknown): Generator<string> {
  if (content == null) return;
  if (typeof content === "string") {
    yield content;
    return;
  }
  if (!Array.isArray(content)) return;
  for (const block of content as Array<any>) {
    if (block?.type === "text" || block?.type == null) {
      if (typeof block?.text === "string" && block.text) yield block.text;
    }
  }
}

async function main(): Promise<number> {
  if (!process.env.ANTHROPIC_API_KEY) {
    console.error("error: ANTHROPIC_API_KEY is not set");
    return 1;
  }

  const prompt =
    process.argv.slice(2).join(" ") ||
    "Hello! Please introduce yourself in one sentence.";

  const client = new Anthropic(); // reads ANTHROPIC_API_KEY from the environment

  try {
    // 1. Create the session. Keeping this inside the try means an auth or
    //    bad-request failure here exits cleanly instead of throwing uncaught.
    const session = await client.beta.sessions.create({
      agent: AGENT_ID,
      environment_id: ENVIRONMENT_ID,
      ...(VAULT_IDS.length ? { vault_ids: VAULT_IDS } : {}),
    });
    console.error(`[session created: ${session.id}]`);

    // 2. Open the event stream, then 3. send the user message into it.
    //    Open the stream BEFORE sending so no early events are missed.
    const stream = await client.beta.sessions.events.stream(session.id);

    await client.beta.sessions.events.send(session.id, {
      events: [
        {
          type: "user.message",
          content: [{ type: "text", text: prompt }],
        },
      ],
    });

    // 4./5. Consume events.
    for await (const event of stream as AsyncIterable<any>) {
      const etype: string | undefined = event?.type;

      if (etype === "agent.message") {
        for (const text of iterText(event.content)) process.stdout.write(text);
      } else if (etype && etype.endsWith(".error")) {
        console.error(`\n[stream error: ${JSON.stringify(event.error ?? event)}]`);
        return 1;
      } else if (etype === "session.status_idle") {
        process.stdout.write("\n"); // trailing newline after streamed text
        console.error(`[done: ${event.stop_reason?.type ?? event.stop_reason}]`);
        break;
      }
    }
  } catch (err) {
    if (err instanceof Anthropic.APIError) {
      console.error(`\n[api error ${err.status ?? "?"}: ${err.message}]`);
      return 1;
    }
    const e = err as Error;
    console.error(`\n[fatal: ${e?.name}: ${e?.message}]`);
    return 1;
  }

  return 0;
}

main().then((code) => process.exit(code));
