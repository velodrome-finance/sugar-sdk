# Sugar CLI — command reference

Run every command through the skill's runner: `scripts/sugar-run.sh <command> --flag=value ...`.

**`sugar-run.sh <command> --help` is the source of truth for exact flags, defaults, and per-command
rules** — it's generated from the SDK's `cli.py` docstrings, travels with the installed version, and
can't drift. This doc deliberately does **not** repeat the flag list; it covers only what `--help`
can't: shared conventions, cross-command orchestration, guardrails, and copy-paste examples. If the
two ever disagree, trust `--help`.

Tx-building commands return a JSON **array of unsigned transactions** (`{from, to, data, value}`),
approvals first then the main call. **Nothing is signed or broadcast.** `superswap` exists in the
SDK but is **not** exposed by the CLI — do not offer it.

## Conventions not shown by `--help`

- **Chain ids** (`--chain`): `10` Optimism, `8453` Base, `130` Unichain, `1135` Lisk.
- **Identifying a position**: `--pool=LP_ADDRESS` for **basic** pools (one position per wallet per
  pool, `id=0`); `--position=NFT_ID` for **CL** pools; combine them to narrow a CL lookup to one pool.
  `--position=0` is ambiguous on its own — pass `--pool` too.
- **Amounts are raw wei by default** so output pipes cleanly through `jq` back into other commands;
  add `--use-decimals` to pass token units instead.

## Cross-command orchestration & guardrails

- A **staked** position must be **unstaked** before you can `claim_fees` on it.
- ALM-managed positions are **not** supported by the staking/claim commands — use the ALM contract directly.
- `--wallet` is a plain `0x` **address** (the tx `from`), never a private key — the CLI refuses keys.
- Tx output is an ordered array (approvals first, then the main call) — sign/broadcast **in order**.

## Examples (one per command; run `<command> --help` for the full flag list)

```bash
# read-only
scripts/sugar-run.sh pools     --chain=1135 --token0=lsk --token1=weth --pool-type=cl --limit=5
scripts/sugar-run.sh positions --chain=1135 --wallet=0xYou

# swap — returns an array [approve_tx, swap_tx]
scripts/sugar-run.sh swap --chain=1135 --wallet=0xYou --from-token=lsk --to-token=eth --amount=10 --use-decimals

# deposit — existing pool (--pool) OR new/derived (--token0 --token1 --pool-type); basic vs CL rules in --help
scripts/sugar-run.sh deposit --chain=1135 --wallet=0xYou --pool=0xd25711... --amount0=0.0001 --amount1=1 --use-decimals

# withdraw — by --pool (basic) or --position (CL)
scripts/sugar-run.sh withdraw --chain=1135 --wallet=0xYou --pool=0xd25711... --fraction=0.5
scripts/sugar-run.sh withdraw --chain=1135 --wallet=0xYou --position=12345 --burn

# gauge staking + claims
scripts/sugar-run.sh stake           --chain=1135 --wallet=0xYou --pool=0xd25711...
scripts/sugar-run.sh unstake         --chain=1135 --wallet=0xYou --position=12345
scripts/sugar-run.sh claim_emissions --chain=1135 --wallet=0xYou --pool=0xd25711...
scripts/sugar-run.sh claim_fees      --chain=1135 --wallet=0xYou --position=12345
```

## Config & overrides

- If a public default RPC rate-limits, set `SUGAR_RPC_URI_<chain_id>` and retry.
- Override the installed version with `SUGAR_SDK_REF=<git-ref>` (default `v0.4.0`), or point at an
  existing binary with `SUGAR_BIN=/path/to/sugar`.
