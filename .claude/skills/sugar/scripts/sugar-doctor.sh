#!/usr/bin/env bash
# Preflight check for the sugar CLI skill: which runner will be used, and whether
# RPC config is in place. Read-only and informational — changes nothing.
#
# Usage: sugar-doctor.sh
set -euo pipefail

SUGAR_SDK_REF="${SUGAR_SDK_REF:-v0.4.1}"

echo "🍭 sugar CLI doctor (ref ${SUGAR_SDK_REF})"
echo "----------------------------------------"

# --- Runner detection (mirror sugar-run.sh order) ---
echo "Runner:"
if [ -n "${SUGAR_BIN:-}" ]; then
  echo "  • SUGAR_BIN override → $SUGAR_BIN"
elif command -v uvx >/dev/null 2>&1; then
  echo "  • uvx (recommended; pinned + cached). First run downloads deps."
elif command -v pipx >/dev/null 2>&1; then
  echo "  • pipx run (pinned + cached). First run downloads deps."
elif command -v python3 >/dev/null 2>&1 || command -v python >/dev/null 2>&1; then
  echo "  • managed venv fallback under \${XDG_CACHE_HOME:-~/.cache}/sugar-sdk-cli/. First run installs deps."
else
  echo "  ✗ none found. Install uv (https://docs.astral.sh/uv/), pipx, or python3."
fi
echo

# --- RPC config per supported chain ---
echo "RPC config (SUGAR_RPC_URI_<chain_id>) — optional; public defaults exist but may rate-limit:"
print_rpc() {
  local id="$1" name="$2" var="SUGAR_RPC_URI_$1"
  if [ -n "${!var:-}" ]; then
    echo "  ✓ $name ($id): \$$var set"
  else
    echo "  – $name ($id): \$$var unset → using built-in public default"
  fi
}
print_rpc 10   "Optimism"
print_rpc 8453 "Base"
print_rpc 130  "Unichain"
print_rpc 1135 "Lisk"
echo

# --- .env note ---
if [ -f "./.env" ]; then
  echo "✓ ./.env present (auto-loaded by the CLI)."
else
  echo "– No ./.env in this directory. You can export vars or create ./.env (SUGAR_RPC_URI_<id>=...)."
fi
echo

# --- Signing boundary reminder ---
echo "No private key needed: the CLI only BUILDS unsigned transactions and refuses private keys."
echo "  --wallet takes a plain 0x ADDRESS (the tx 'from' field) — never a key."
echo "  ETHERSCAN_API_KEY / SUGAR_PK are NOT used by the CLI at runtime."
