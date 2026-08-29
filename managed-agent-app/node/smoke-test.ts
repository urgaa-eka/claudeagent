/**
 * Smoke test for the hosted-agent device link (Plane 2) — the TypeScript twin of
 * agent/smoke_test.py. Opens a Managed Agents session with the S24 vault(s)
 * attached and checks the agent can see the MCP tools; it prints any `*mcp*`
 * events and loudly surfaces any `*.error` (the tell-tale of a vault credential
 * not keyed to the MCP server URL — see agent/README.md, step 2).
 *
 * Env: ANTHROPIC_API_KEY, AGENT_ID, ENVIRONMENT_ID, VAULT_IDS (comma-separated),
 *      optional PROMPT. Exits 0 on a clean run, 1 on error.
 *
 * Run:  cd node && npm run smoke        (or: npx tsx smoke-test.ts)
 */
import Anthropic from "@anthropic-ai/sdk";

const AGENT_ID = process.env.AGENT_ID ?? "__AGENT_ID__";
const ENVIRONMENT_ID = process.env.ENVIRONMENT_ID ?? "__ENVIRONMENT_ID__";
const VAULT_IDS = (process.env.VAULT_IDS ?? "")
  .split(",")
  .map((s) => s.trim())
  .filter(Boolean);
const PROMPT =
  process.env.PROMPT ??
  "List every tool you can call, one per line. Then state explicitly whether you " +
    "have tools that control a Samsung S24 Ultra device, and if so, name them.";

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
  if (VAULT_IDS.length === 0) {
    console.error(
      "warning: VAULT_IDS is empty -- the S24 credential won't be attached, so the agent won't see the device tools.",
    );
  }

  const client = new Anthropic();
  let sawMcp = false;
  let sawError = false;

  try {
    const session = await client.beta.sessions.create({
      agent: AGENT_ID,
      environment_id: ENVIRONMENT_ID,
      ...(VAULT_IDS.length ? { vault_ids: VAULT_IDS } : {}),
    });
    console.error(
      `[session ${session.id} created; vaults: ${VAULT_IDS.length ? VAULT_IDS.join(",") : "none"}]`,
    );

    const stream = await client.beta.sessions.events.stream(session.id);
    await client.beta.sessions.events.send(session.id, {
      events: [{ type: "user.message", content: [{ type: "text", text: PROMPT }] }],
    });

    for await (const event of stream as AsyncIterable<any>) {
      const etype: string = event?.type ?? "";
      if (etype === "agent.message") {
        for (const text of iterText(event.content)) process.stdout.write(text);
      } else if (etype.includes("mcp")) {
        sawMcp = true;
        console.error(`\n[mcp event: ${etype}]`);
      } else if (etype.endsWith(".error")) {
        sawError = true;
        console.error(`\n[session error: ${JSON.stringify(event.error ?? event)}]`);
      } else if (etype === "session.status_idle") {
        process.stdout.write("\n");
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

  console.error("\n--- smoke result ---");
  console.error(`  mcp events seen:    ${sawMcp}`);
  console.error(`  session.error seen: ${sawError}`);
  if (sawError) {
    console.error(
      "  -> a session.error usually means the vault credential isn't keyed to the MCP server URL. Re-check agent/README.md step 2 (URL match).",
    );
    return 1;
  }
  console.error("  -> if the agent listed the S24 tools above and there was no error, Plane 2 is live.");
  return 0;
}

main().then((code) => process.exit(code));
