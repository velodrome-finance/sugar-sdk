---
name: sugar
description: >-
  Build UNSIGNED Velodrome/Aerodrome (Sugar SDK) DeFi transactions and query
  on-chain data via the `sugar` CLI on Optimism, Base, Unichain, and Lisk.
  Covers swaps, liquidity deposits/withdrawals, staking/unstaking, claiming LP
  fees and gauge emissions, and listing pools/positions. Use whenever the user
  wants to swap tokens, manage LP positions, or inspect pools on
  Velodrome/Aerodrome/Sugar. The CLI only BUILDS transactions — it never signs
  or broadcasts them.
---

# Sugar SDK CLI

The `sugar` CLI turns Velodrome/Aerodrome actions into **unsigned transaction JSON**.

## ⚠️ Safety boundary — read first

**Sugar only BUILDS transactions. It never signs or broadcasts, and neither do you.**

- Every tx-building command prints a JSON array of unsigned `{from, to, data, value}` objects
  (approvals first, then the main call). Nothing is sent on-chain.
- `--wallet` takes a plain **0x address** (the tx `from` field), **never a private key** —
  the CLI actively refuses keys.
- After running a tx command: **present the unsigned JSON to the user** and the copy-paste
  signing commands below. **Do not sign or broadcast** unless the user has a separate signing
  flow/skill and explicitly asks you to use it. Even then, you produce the command; the user runs it.

## Running

Invoke the bundled runner (paths are relative to this skill directory):

```bash
scripts/sugar-run.sh <subcommand> --flag=value ...
```

It auto-detects the easiest runner (`uvx` → `pipx` → managed venv), pinned to sugar-sdk `v0.4.0`.
**The first run downloads dependencies (~30s); later runs are cached.** Diagnostics go to stderr,
so stdout is clean JSON you can pipe into `jq`.

**Always run the preflight once before your first `sugar-run.sh` command** in a session
(detects the runner and reports RPC config). Run it a single time up front, not before every command:

```bash
scripts/sugar-doctor.sh
```

## Config

- **RPC** (optional but recommended): `SUGAR_RPC_URI_<chain_id>`. Each chain has a built-in public
  default, so commands work with nothing set, but public RPCs may rate-limit — set your own for
  reliability. Export it, or put it in a `./.env` (auto-loaded).
- **No private key.** `ETHERSCAN_API_KEY` and `SUGAR_PK` are **not** used by the CLI.

Supported chains (pass the id to `--chain`):

| Chain    | `--chain` |
|----------|-----------|
| Optimism | `10`      |
| Base     | `8453`    |
| Unichain | `130`     |
| Lisk     | `1135`    |

## Commands

Read-only (no wallet needed):
- `pools` — list/filter pools (`--token0`, `--token1`, `--pool-type`, `--limit`, `--full`).
- `positions` — list a wallet's LP positions (`--wallet`/`--owner`).

Tx-building (require `--wallet=0xADDRESS`; output is unsigned):
- `swap` — swap one token for another.
- `deposit` — add liquidity (basic or concentrated/CL pools).
- `withdraw` — remove liquidity from a position.
- `stake` / `unstake` — stake/unstake a position in its gauge.
- `claim_emissions` — claim gauge emissions.
- `claim_fees` — claim accrued LP fees.

`sugar-run.sh <cmd> --help` is authoritative for the exact, version-accurate flags and defaults.
See `reference.md` for orchestration, config, guardrails, and copy-paste examples — including amount
units (wei vs `--use-decimals`) and how to identify positions (`--pool` for basic, `--position` for CL).

## Workflow

1. Identify the **action** and **chain id**. For tx commands, get the user's **wallet address**
   (an address, never a key).
2. Run `scripts/sugar-doctor.sh` first (mandatory, once per session) to confirm the runner and RPC config.
3. Run the command via `scripts/sugar-run.sh ...`.
4. **Read commands:** summarize the JSON for the user.
5. **Tx commands:** show the unsigned tx JSON, then the signing helpers below, and restate that
   nothing was signed or broadcast.

## Signing helpers (templates — you generate, the user runs)

The CLI output is a JSON array of unsigned txs. Sign/broadcast each one externally, in order.

```bash
# Foundry (cast): sign + broadcast each unsigned tx in order
scripts/sugar-run.sh swap --chain=1135 --wallet=0xYou --from-token=lsk --to-token=eth --amount=1 --use-decimals \
  | jq -c '.[]' \
  | while read -r tx; do
      cast send --rpc-url "$SUGAR_RPC_URI_1135" --private-key "$YOUR_KEY" \
        "$(jq -r .to <<<"$tx")" "$(jq -r .data <<<"$tx")" --value "$(jq -r .value <<<"$tx")"
    done
```

- **viem:** pass each `{to, data, value}` to `walletClient.sendTransaction(...)`.
- **ethers:** `signer.sendTransaction({ to, data, value })`.
- **Browser wallet (MetaMask):** hand each dict to `eth_sendTransaction`.
