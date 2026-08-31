"""
Resolve the Firebase service-account key used by the S24 direct-cloud runtime.

The daemon that polls Firestore (`commandQueue` / `currentDirectCloudRuntime`)
has to find its Admin SDK key on whichever machine it happens to run on: a
Windows laptop, a Linux host, or Termux on the phone itself. A hardcoded list of
absolute Windows paths breaks the other two, and a fixed spelling of the
filename breaks on Android, whose filesystem is case-sensitive --
`serviceAccountkey.json` and `serviceAccountKey.json` are two different files
there and the same file on Windows.

`resolve_service_account_key()` searches, first match wins:

  1. an explicit path passed by the caller (authoritative -- a missing explicit
     path raises rather than falling through to a different key)
  2. $EKA_SERVICE_ACCOUNT_KEY, $FIREBASE_SERVICE_ACCOUNT_PATH, then
     $GOOGLE_APPLICATION_CREDENTIALS
  3. per-platform config dirs, the calling script's own directory, and the CWD
  4. the legacy hardcoded paths, so an existing install keeps working

Inside a directory, names are matched case-folded, and the Firebase console's
own download name (`<project>-firebase-adminsdk-<id>.json`) is accepted too, so
a key saved straight from the console is found without being renamed first.

Nothing here reads or logs the private key. `describe_key()` returns only the
non-secret identifying fields, which is enough to confirm you have the right
project without putting the credential on a terminal or in a log.
"""

from __future__ import annotations

import json
import os
import stat
from pathlib import Path

__all__ = [
    "CredentialsNotFound",
    "ENV_VARS",
    "KEY_FILENAMES",
    "KEY_GLOBS",
    "candidate_paths",
    "describe_key",
    "resolve_service_account_key",
    "search_dirs",
]

# Checked before any filesystem guess, highest priority first.
# EKA_SERVICE_ACCOUNT_KEY is this daemon's own override. FIREBASE_SERVICE_ACCOUNT_PATH
# is the name the Kailash deployment already uses, so a machine that runs both
# needs only one variable set. GOOGLE_APPLICATION_CREDENTIALS is the Google-standard
# name, last so pointing it at another project's key does not hijack this daemon.
ENV_VARS = (
    "EKA_SERVICE_ACCOUNT_KEY",
    "FIREBASE_SERVICE_ACCOUNT_PATH",
    "GOOGLE_APPLICATION_CREDENTIALS",
)

# Accepted exact names, in canonical casing so they read correctly in the
# candidate list and the not-found error. Comparison is case-folded at the
# point of use, so any casing on disk still matches.
KEY_FILENAMES = ("serviceAccountKey.json", "service-account-key.json")

# The Firebase console downloads keys as <project>-firebase-adminsdk-<id>.json.
KEY_GLOBS = ("*firebase-adminsdk*.json",)

# Machine-specific paths from the original hardcoded candidate list. Searched
# last, only so an existing install keeps working; prefer $EKA_SERVICE_ACCOUNT_KEY.
LEGACY_WINDOWS_PATHS = (
    r"C:\eka-11m\serviceAccountKey.json",
    r"C:\Users\abcom\Go4Garage\Eka Runner\serviceAccountKey.json",
)

# Fields safe to surface: everything in a key file except private_key(_id).
SAFE_FIELDS = ("type", "project_id", "client_email", "client_id")


class CredentialsNotFound(FileNotFoundError):
    """No service-account key was found in any candidate location."""


def _is_windows() -> bool:
    return os.name == "nt"


def search_dirs(env=None, home=None) -> list[Path]:
    """Directories scanned for a key, in priority order.

    Platform-appropriate config dirs first, then the plain `~/eka-runner` drop
    that works the same on every OS.
    """
    env = os.environ if env is None else env
    home = Path(env.get("HOME") or Path.home()) if home is None else Path(home)

    dirs: list[Path] = []
    if _is_windows():
        for var in ("APPDATA", "LOCALAPPDATA"):
            root = env.get(var)
            if root:
                dirs.append(Path(root) / "eka-runner")
        # The layout the daemon has been using on the laptop.
        dirs.append(home / "Go4Garage" / "Eka Runner")
    else:
        xdg = env.get("XDG_CONFIG_HOME")
        dirs.append(Path(xdg) / "eka-runner" if xdg else home / ".config" / "eka-runner")
        # On Android, shared storage is the usual hand-off point into Termux.
        dirs.append(Path("/sdcard/eka-runner"))

    dirs.append(home / "eka-runner")
    return dirs


def candidate_paths(explicit=None, env=None, script_dir=None, home=None) -> list[Path]:
    """Every concrete path checked, in order, before directory globbing.

    Deterministic and filesystem-free, so the search order can be asserted in
    tests without staging a whole directory tree.
    """
    env = os.environ if env is None else env
    paths: list[Path] = []

    if explicit:
        paths.append(Path(explicit).expanduser())

    for var in ENV_VARS:
        value = env.get(var)
        if value:
            paths.append(Path(value).expanduser())

    dirs = list(search_dirs(env=env, home=home))
    if script_dir:
        dirs.append(Path(script_dir))
    dirs.append(Path.cwd())

    for directory in dirs:
        for name in KEY_FILENAMES:
            paths.append(directory / name)

    if _is_windows():
        paths.extend(Path(p) for p in LEGACY_WINDOWS_PATHS)

    # Preserve order while dropping the duplicates the dir lists can produce.
    seen: set[str] = set()
    unique: list[Path] = []
    for path in paths:
        key = os.path.normcase(str(path))
        if key not in seen:
            seen.add(key)
            unique.append(path)
    return unique


def _match_in_dir(directory: Path) -> Path | None:
    """First key-shaped file in `directory`, matched case-insensitively."""
    try:
        entries = sorted(directory.iterdir())
    except OSError:
        # Missing, unreadable, or not a directory -- all just mean "no match".
        return None

    wanted = {name.casefold() for name in KEY_FILENAMES}
    for entry in entries:
        if entry.name.casefold() in wanted and entry.is_file():
            return entry
    for entry in entries:
        folded = entry.name.casefold()
        if entry.is_file() and any(Path(folded).match(g) for g in KEY_GLOBS):
            return entry
    return None


def resolve_service_account_key(
    explicit=None, env=None, script_dir=None, home=None, require=True
):
    """Return the path to the service-account key, or None when `require` is False.

    An `explicit` path is authoritative: if it is given and missing, this raises
    rather than searching on, so a typo can never silently resolve to a different
    project's key. Otherwise checks `candidate_paths()` in order, then scans each
    search directory for a case-insensitive or console-named match.
    """
    if explicit:
        # An explicit path is an instruction, not a hint. Falling through to the
        # search when it is missing would quietly authenticate against whatever
        # other key happens to be on the machine -- a different Firebase project.
        chosen = Path(explicit).expanduser()
        if chosen.is_file():
            return chosen
        if not require:
            return None
        raise CredentialsNotFound(
            f"Service-account key not found at the explicitly requested path: {chosen}"
        )

    tried: list[Path] = []

    for path in candidate_paths(env=env, script_dir=script_dir, home=home):
        tried.append(path)
        if path.is_file():
            return path

    dirs = list(search_dirs(env=env, home=home))
    if script_dir:
        dirs.append(Path(script_dir))
    dirs.append(Path.cwd())
    for directory in dirs:
        found = _match_in_dir(directory)
        if found is not None:
            return found

    if not require:
        return None

    listing = "\n".join(f"  - {p}" for p in tried)
    raise CredentialsNotFound(
        "No Firebase service-account key found. Checked:\n"
        f"{listing}\n"
        f"...and scanned {', '.join(str(d) for d in dirs)} for a "
        "case-insensitive or *firebase-adminsdk*.json match.\n\n"
        "Fix by either setting EKA_SERVICE_ACCOUNT_KEY=/path/to/key.json, or "
        "downloading a fresh key from the Firebase console (Project Settings -> "
        "Service accounts -> Generate new private key) into ~/eka-runner/."
    )


def describe_key(path) -> dict:
    """Non-secret summary of a key file, for confirming you have the right one.

    Never returns `private_key` or `private_key_id`. Raises ValueError if the
    file is not a well-formed service-account key.
    """
    path = Path(path)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"{path} is not valid JSON: {exc}") from exc

    if not isinstance(data, dict):
        raise ValueError(f"{path} is not a JSON object")
    if data.get("type") != "service_account":
        raise ValueError(
            f"{path} has type={data.get('type')!r}; expected 'service_account'. "
            "This looks like a client config, not an Admin SDK key."
        )
    if not data.get("private_key"):
        raise ValueError(f"{path} has no private_key field")

    summary = {field: data.get(field) for field in SAFE_FIELDS}
    summary["private_key_present"] = True
    summary["path"] = str(path)
    summary["world_readable"] = _world_readable(path)
    return summary


def _world_readable(path: Path) -> bool:
    """True when group/other can read the key (POSIX only; always False on Windows)."""
    if _is_windows():
        return False
    try:
        mode = path.stat().st_mode
    except OSError:
        return False
    return bool(mode & (stat.S_IRGRP | stat.S_IROTH))


if __name__ == "__main__":
    # `python firebase_credentials.py` -- locate and describe the key, no secrets.
    import sys

    try:
        found = resolve_service_account_key()
    except CredentialsNotFound as exc:
        print(exc, file=sys.stderr)
        raise SystemExit(1)

    print(f"found: {found}")
    try:
        info = describe_key(found)
    except ValueError as exc:
        print(f"warning: {exc}", file=sys.stderr)
        raise SystemExit(1)

    for field in SAFE_FIELDS:
        print(f"  {field}: {info[field]}")
    if info["world_readable"]:
        print("  WARNING: key is group/other readable; run chmod 600 on it")
