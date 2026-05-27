#!/usr/bin/env bash
# Run the `sugar` CLI (Velodrome/Aerodrome sugar-sdk) without requiring a global install.
#
# Detects the easiest available runner and execs `sugar` with the args you pass through.
# Stdout is left clean (the CLI's JSON) — all diagnostics go to stderr — so output pipes
# straight into `jq` or a signer.
#
# Usage:   sugar-run.sh <subcommand> [--flags...]
# Example: sugar-run.sh pools --chain=1135 --limit=3
#
# Overrides:
#   SUGAR_BIN       path to a `sugar` binary you already have (skips detection)
#   SUGAR_SDK_REF   git ref/tag to install (default: v0.4.1)
set -euo pipefail

SUGAR_SDK_REF="${SUGAR_SDK_REF:-v0.4.1}"
SPEC="git+https://github.com/velodrome-finance/sugar-sdk.git@${SUGAR_SDK_REF}"

log() { printf '%s\n' "sugar-run: $*" >&2; }

if [ "$#" -eq 0 ]; then
  log "no subcommand given. Try: sugar-run.sh --help"
fi

# 1. Explicit override.
if [ -n "${SUGAR_BIN:-}" ]; then
  log "using SUGAR_BIN=$SUGAR_BIN"
  exec "$SUGAR_BIN" "$@"
fi

# 2. uvx — ephemeral, pinned, cached after first run. Preferred.
if command -v uvx >/dev/null 2>&1; then
  log "running via uvx (ref $SUGAR_SDK_REF); first run downloads deps, then cached"
  exec uvx --from "$SPEC" sugar "$@"
fi

# 3. pipx run — similar ephemeral semantics.
if command -v pipx >/dev/null 2>&1; then
  log "running via pipx run (ref $SUGAR_SDK_REF); first run downloads deps, then cached"
  exec pipx run --spec "$SPEC" sugar "$@"
fi

# 4. Fallback: a cached venv we manage ourselves.
PY="$(command -v python3 || command -v python || true)"
if [ -n "$PY" ]; then
  VENV="${XDG_CACHE_HOME:-$HOME/.cache}/sugar-sdk-cli/venv-${SUGAR_SDK_REF}"
  if [ ! -x "$VENV/bin/sugar" ]; then
    log "no uvx/pipx found; building cached venv at $VENV (one-time)"
    "$PY" -m venv "$VENV" >&2
    "$VENV/bin/python" -m pip install --quiet --upgrade pip >&2
    "$VENV/bin/python" -m pip install --quiet "$SPEC" >&2
  else
    log "using cached venv at $VENV"
  fi
  exec "$VENV/bin/sugar" "$@"
fi

log "ERROR: need one of uvx, pipx, or python3 to run the sugar CLI."
log "Install uv (recommended): https://docs.astral.sh/uv/  — then re-run."
exit 1
