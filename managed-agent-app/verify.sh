#!/usr/bin/env bash
#
# verify.sh -- run the whole kit's checks. Exits non-zero if anything fails.
# Optional steps (pytest, tsc, auth-boundary) skip gracefully when their tooling
# or a key isn't present, so this is safe to run anywhere.
#
#   ./verify.sh              # static checks + tests
#   AUTH_SMOKE=1 ./verify.sh # also hit the live endpoint with a dummy key (needs
#                            #   anthropic installed + network; expects a clean 401)
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"
fail=0
step() { echo; echo "== $* =="; }
ok()   { echo "  ok: $*"; }
bad()  { echo "  FAIL: $*"; fail=1; }

PYS="python/main.py agent/smoke_test.py agent/add_vault_credential.py"
SHS="deploy/deploy.sh deploy/run.sh deploy/termux/termux-setup.sh \
     deploy/claude-code/add-s24-mcp.sh deploy/claude-code/add-mcp.sh verify.sh"

step "python: py_compile"
for f in $PYS; do python3 -m py_compile "$f" && ok "$f" || bad "$f"; done

step "bash: syntax (-n)"
for f in $SHS; do bash -n "$f" && ok "$f" || bad "$f"; done

step "json: validity"
for f in agent/*.json; do
  python3 -c "import json,sys; json.load(open(sys.argv[1]))" "$f" && ok "$f" || bad "$f"
done

step "pytest (skips if pytest/anthropic absent)"
if python3 -c "import pytest" 2>/dev/null; then
  python3 -m pytest -q tests/ && ok "tests" || bad "tests"
else
  echo "  skip: pytest not installed"
fi

step "typescript: tsc --noEmit (skips if npm absent)"
if command -v npm >/dev/null 2>&1; then
  ( cd node && npm install --no-audit --no-fund >/dev/null 2>&1 && npx --yes tsc --noEmit ) \
    && ok "node/index.ts" || bad "node/index.ts"
else
  echo "  skip: npm not found"
fi

if [ "${AUTH_SMOKE:-0}" = "1" ]; then
  step "auth boundary: dummy key -> expect clean 401"
  if python3 -c "import anthropic" 2>/dev/null; then
    out="$(cd python && ANTHROPIC_API_KEY=sk-ant-dummy AGENT_ID=agent_x ENVIRONMENT_ID=env_x \
           python3 main.py "ping" 2>&1)"
    echo "$out" | grep -q "api error 401" && ok "reached endpoint, clean 401" \
      || bad "expected a clean 401 (got: $out)"
  else
    echo "  skip: anthropic not installed"
  fi
fi

echo
if [ "$fail" = 0 ]; then echo "== ALL CHECKS PASSED =="; else echo "== SOME CHECKS FAILED =="; fi
exit "$fail"
