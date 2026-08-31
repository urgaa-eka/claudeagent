"""
S24 MCP bridge — a small Model Context Protocol server that controls a Samsung
S24 Ultra (Android), exposed over Streamable HTTP with a static bearer token.

It is reached by an Anthropic Managed Agent (Sessions API `mcp_servers` + a vault
`static_bearer` credential) and/or by Claude Code (`claude mcp add`). Running it
and tunnelling it (cloudflared) is what produces the `https://…/mcp` URL you plug
into both planes — see README.md.

Device control shells out to `adb` by default (S24_BACKEND=adb): run it where
`adb` can reach the phone — a laptop on USB / `adb connect`, or in Termux on the
phone itself after enabling wireless debugging (`adb connect 127.0.0.1:…`).
S24_BACKEND=local runs the commands directly (rooted Termux / `su`), since plain
non-root Termux cannot inject input into other apps.

Env:
  S24_BRIDGE_TOKEN   bearer token required on every request (STRONGLY recommended)
  S24_BRIDGE_HOST    bind host (default 127.0.0.1)
  S24_BRIDGE_PORT    bind port (default 8080)
  S24_BACKEND        adb (default) | local
  S24_ADB_SERIAL     optional `adb -s <serial>` target
"""

import os
import shlex
import subprocess
import sys

from mcp.server.fastmcp import FastMCP, Image

HOST = os.environ.get("S24_BRIDGE_HOST", "127.0.0.1")
PORT = int(os.environ.get("S24_BRIDGE_PORT", "8080"))
TOKEN = os.environ.get("S24_BRIDGE_TOKEN", "")
BACKEND = os.environ.get("S24_BACKEND", "adb")
ADB_SERIAL = os.environ.get("S24_ADB_SERIAL", "")
TIMEOUT = int(os.environ.get("S24_CMD_TIMEOUT", "30"))

mcp = FastMCP("s24-bridge", host=HOST, port=PORT)

# Common Android keyevent names -> keycodes (accepted by key_event alongside ints).
KEYCODES = {
    "HOME": 3, "BACK": 4, "CALL": 5, "ENDCALL": 6, "DPAD_UP": 19, "DPAD_DOWN": 20,
    "DPAD_LEFT": 21, "DPAD_RIGHT": 22, "DPAD_CENTER": 23, "VOLUME_UP": 24,
    "VOLUME_DOWN": 25, "POWER": 26, "CAMERA": 27, "TAB": 61, "SPACE": 62,
    "ENTER": 66, "DEL": 67, "MENU": 82, "SEARCH": 84, "APP_SWITCH": 187,
    "MOVE_HOME": 122, "MOVE_END": 123,
}


def _device_argv(cmd: str, binary: bool = False) -> list[str]:
    """Build the argv that runs `cmd` on the device for the chosen backend."""
    if BACKEND == "adb":
        base = ["adb"] + (["-s", ADB_SERIAL] if ADB_SERIAL else [])
        # exec-out streams raw bytes (needed for screencap); shell for text.
        return base + (["exec-out", cmd] if binary else ["shell", cmd])
    # local backend: run through the device's own shell.
    return ["sh", "-c", cmd]


def _run(cmd: str) -> str:
    """Run a device command, return stdout; raise with stderr on failure."""
    proc = subprocess.run(_device_argv(cmd), capture_output=True, text=True, timeout=TIMEOUT)
    if proc.returncode != 0:
        raise RuntimeError((proc.stderr or proc.stdout or "command failed").strip())
    return proc.stdout


@mcp.tool()
def device_status() -> dict:
    """Read-only: report model, Android version, screen size, and battery. Good first call to confirm the bridge reaches the device."""
    model = _run("getprop ro.product.model").strip()
    release = _run("getprop ro.build.version.release").strip()
    size = _run("wm size").strip()
    batt = _run("dumpsys battery")
    level = plugged = status = None
    for line in batt.splitlines():
        k, _, v = line.strip().partition(":")
        if k == "level":
            level = v.strip()
        elif k == "status":
            status = v.strip()
        elif k == "plugged":
            plugged = v.strip()
    return {
        "model": model,
        "android_version": release,
        "screen_size": size.replace("Physical size:", "").strip(),
        "battery_level": level,
        "battery_status": status,
        "battery_plugged": plugged,
        "backend": BACKEND,
    }


@mcp.tool()
def screenshot() -> Image:
    """Read-only: capture the current screen and return it as a PNG image."""
    proc = subprocess.run(_device_argv("screencap -p", binary=True), capture_output=True, timeout=TIMEOUT)
    if proc.returncode != 0:
        raise RuntimeError((proc.stderr.decode("utf-8", "replace") or "screencap failed").strip())
    return Image(data=proc.stdout, format="png")


@mcp.tool()
def tap(x: int, y: int) -> str:
    """Action: tap the screen at pixel coordinates (x, y). Use screenshot()/ui_dump() to find coordinates first."""
    _run(f"input tap {int(x)} {int(y)}")
    return f"tapped ({x}, {y})"


@mcp.tool()
def swipe(x1: int, y1: int, x2: int, y2: int, duration_ms: int = 300) -> str:
    """Action: swipe from (x1, y1) to (x2, y2) over duration_ms milliseconds (e.g. to scroll or drag)."""
    _run(f"input swipe {int(x1)} {int(y1)} {int(x2)} {int(y2)} {int(duration_ms)}")
    return f"swiped ({x1},{y1})->({x2},{y2}) in {duration_ms}ms"


@mcp.tool()
def input_text(text: str) -> str:
    """Action: type text into the focused field. Spaces are sent as %s; some symbols may need a key_event instead."""
    _run(f"input text {shlex.quote(text.replace(' ', '%s'))}")
    return f"typed {len(text)} chars"


@mcp.tool()
def key_event(key: str) -> str:
    """Action: send a key event. `key` is a keycode number or a name (e.g. HOME, BACK, ENTER, APP_SWITCH, VOLUME_UP)."""
    code = KEYCODES.get(key.upper()) if not key.isdigit() else int(key)
    if code is None:
        raise ValueError(f"unknown key '{key}'. Known names: {', '.join(sorted(KEYCODES))}, or a numeric keycode.")
    _run(f"input keyevent {code}")
    return f"key_event {key} ({code})"


@mcp.tool()
def launch_app(package: str, activity: str = "") -> str:
    """Action: launch an app by package name (e.g. com.android.settings). Optionally pass an explicit activity."""
    if activity:
        out = _run(f"am start -n {shlex.quote(package + '/' + activity)}")
    else:
        out = _run(f"monkey -p {shlex.quote(package)} -c android.intent.category.LAUNCHER 1")
    return out.strip() or f"launched {package}"


@mcp.tool()
def list_packages(name_filter: str = "", third_party_only: bool = False) -> list[str]:
    """Read-only: list installed package names, optionally filtered by substring; set third_party_only to skip system apps."""
    cmd = "pm list packages" + (" -3" if third_party_only else "") + (f" {shlex.quote(name_filter)}" if name_filter else "")
    return sorted(line.replace("package:", "").strip() for line in _run(cmd).splitlines() if line.strip())


@mcp.tool()
def ui_dump() -> str:
    """Read-only: dump the current UI hierarchy as uiautomator XML — use it to find element text and bounds (coordinates) for tap/swipe."""
    return _run("uiautomator dump /sdcard/window_dump.xml >/dev/null 2>&1; cat /sdcard/window_dump.xml")


@mcp.tool()
def shell(command: str) -> str:
    """Action / escape hatch: run an arbitrary device shell command and return its stdout. Powerful — prefer the specific tools above when they fit."""
    return _run(command)


# --- bearer-token auth over the Streamable HTTP app -------------------------
from starlette.middleware.base import BaseHTTPMiddleware  # noqa: E402
from starlette.responses import JSONResponse  # noqa: E402


class BearerAuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        if TOKEN and request.headers.get("authorization") != f"Bearer {TOKEN}":
            return JSONResponse({"error": "unauthorized"}, status_code=401)
        return await call_next(request)


def build_app():
    app = mcp.streamable_http_app()
    app.add_middleware(BearerAuthMiddleware)
    return app


if __name__ == "__main__":
    if not TOKEN:
        print("WARNING: S24_BRIDGE_TOKEN is not set — the bridge is UNAUTHENTICATED. "
              "Set it before exposing the bridge to any network.", file=sys.stderr)
    import uvicorn

    print(f"[s24-bridge] serving http://{HOST}:{PORT}/mcp  (backend={BACKEND})", file=sys.stderr)
    uvicorn.run(build_app(), host=HOST, port=PORT)
