# S24 MCP bridge

A small MCP server that lets an agent **control the Samsung S24 Ultra**. Running
it and exposing it is what produces the `https://…/mcp` **bridge URL** you plug
into the two device-control planes (`../agent/`, `../deploy/claude-code/`).

Tools: `device_status`, `screenshot`, `tap`, `swipe`, `input_text`, `key_event`,
`launch_app`, `list_packages`, `ui_dump`, `shell`. Transport: Streamable HTTP at
`/mcp`, guarded by a static bearer token.

## How device control works (pick a backend)

Non-root Termux **cannot** inject taps into other apps, so control goes through
`adb` by default:

- **`S24_BACKEND=adb` (default):** run the bridge where `adb` can reach the phone.
  - a laptop: `adb connect <phone-ip>:5555` (Wireless debugging) or USB, then run the bridge there; or
  - in Termux on the phone: enable **Wireless debugging**, `pkg install android-tools`, `adb connect 127.0.0.1:<port>`, then run the bridge.
- **`S24_BACKEND=local`:** rooted phone / `su` — commands run directly on-device.

## Run it

```bash
# in Termux (or on a host with adb):
pkg install -y python            # Termux;  or use your system Python + adb
pip install -r requirements.txt

export S24_BRIDGE_TOKEN="$(openssl rand -hex 24)"   # keep this; it's the bearer token
export S24_BACKEND=adb                               # adb must see the device
python s24_mcp_bridge.py                             # serves http://127.0.0.1:8080/mcp
```

`device_status()` is the quickest check that the bridge reaches the phone.

## Get the public URL (for the hosted agent)

The hosted Managed Agent runs on Anthropic's servers, so the bridge must be
**publicly reachable**. Tunnel it with cloudflared (no account needed for a quick
tunnel):

```bash
# Termux: pkg install cloudflared   |  else see https://github.com/cloudflare/cloudflared
cloudflared tunnel --url http://127.0.0.1:8080
# -> prints https://<random>.trycloudflare.com  ; your bridge URL is that + /mcp
```

Your **bridge URL** is `https://<random>.trycloudflare.com/mcp`.

> Claude Code on a machine that shares the phone's network can instead point
> straight at `http://<phone-ip>:8080/mcp` — no tunnel needed.

## Wire it into the planes

**Plane 1 — Claude Code:**
```bash
../deploy/claude-code/add-mcp.sh s24 https://<random>.trycloudflare.com/mcp "$S24_BRIDGE_TOKEN"
```

**Plane 2 — hosted agent:**
1. Put `https://<random>.trycloudflare.com/mcp` in `../agent/mcp-server.example.json` (`url`) and merge its `mcp_servers` + `mcp_toolset` into the agent.
2. Store the token as a vault credential keyed to that URL:
   ```bash
   ANTHROPIC_API_KEY=… VAULT_ID=vlt_… \
   MCP_SERVER_URL=https://<random>.trycloudflare.com/mcp MCP_TOKEN="$S24_BRIDGE_TOKEN" \
   python ../agent/add_vault_credential.py        # AUTH_TYPE=static_bearer (default)
   ```
3. Run the client / `../agent/smoke_test.py` with `VAULT_IDS=vlt_…`.

## Safety

This bridge grants full device control to whoever holds the token and can reach
the URL. Always set `S24_BRIDGE_TOKEN`, prefer a tunnel with TLS, and rotate the
token / drop the tunnel when you're done. `trycloudflare.com` URLs are public but
unguessable; the bearer token is the real gate.
