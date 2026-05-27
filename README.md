# Sugar SDK

<p align="center">
    <img src="/sugar.png" alt="Sugar SDK" />
</p>

Sugar makes Velodrome and Aerodrome devs life sweeter 🍭

> All examples below show the async API. The sync API is identical — drop the `async`/`await` keywords and use `Chain` classes (`OPChain`, `BaseChain`, ...) instead of their `Async*` counterparts.

## Using Sugar

``` bash
pip install git+https://github.com/velodrome-finance/sugar-sdk.git@v0.4.1
```

Take it for a spin on [CodeSandbox](https://codesandbox.io/p/sandbox/sugar-sdk-playground-7c4z7g).

## Claude Code skill

For agentic workflows, this repo ships a self-contained Claude Code skill at
[`.claude/skills/sugar/`](.claude/skills/sugar/SKILL.md). It wraps the `sugar` CLI with
a safety boundary baked in — the agent builds unsigned transactions and surfaces them
for you to sign and broadcast externally; private keys are refused. The bundled
`scripts/sugar-run.sh` handles installation via `uvx`/`pipx`/managed venv on first use,
so the skill works without a global install.

## Quickstart

``` python
from sugar.chains import AsyncBaseChain

async with AsyncBaseChain() as chain:
    for p in (await chain.get_prices(await chain.get_all_tokens()))[:5]:
        print(f"{p.token.symbol} price: {p.price}")
```

Swap `AsyncBaseChain` for `AsyncOPChain`, `AsyncUniChain`, or `AsyncLiskChain` to switch networks.

## CLI

The SDK ships a `sugar` CLI (backed by [python-fire](https://github.com/google/python-fire)) for shell-side use. After install the `sugar` binary is on `PATH`; `python -m sugar` is equivalent.

**The SDK never signs.** Every subcommand returns unsigned transactions as a JSON array of `{from, to, data, value}` dicts on stdout — approvals first, then the main call. `--wallet=0xADDRESS` supplies the `from` field; private keys are refused. Sign and broadcast externally with whatever signer fits your setup.

Discover via `--help`:

``` bash
python -m sugar --help              # list subcommands
python -m sugar deposit --help      # see flags for one
```

``` bash
# preview a basic deposit — amounts in raw wei (default)
python -m sugar deposit --chain=1135 --wallet=0xYou --pool=0xd25711... --amount0=100000000000000 --amount1=1000000000000000000

# same deposit using token decimals — opt in with --use-decimals
python -m sugar deposit --chain=1135 --wallet=0xYou --pool=0xd25711... --amount0=0.0001 --amount1=1 --use-decimals

# list wallet positions
python -m sugar positions --chain=1135 --wallet=0xYou

# withdraw 50% of a basic position
python -m sugar withdraw --chain=1135 --wallet=0xYou --pool=0xd25711... --fraction=0.5

# withdraw + burn a CL position (by id)
python -m sugar withdraw --chain=1135 --wallet=0xYou --position=12345 --burn

# stake an unstaked basic position into its gauge
python -m sugar stake --chain=1135 --wallet=0xYou --pool=0xd25711...

# unstake a CL position (full)
python -m sugar unstake --chain=1135 --wallet=0xYou --position=12345

# claim gauge emissions
python -m sugar claim_emissions --chain=1135 --wallet=0xYou --position=12345

# claim LP fees, unwrap WETH leg to native ETH
python -m sugar claim_fees --chain=1135 --wallet=0xYou --position=12345 --unwrap-native

# list pools — compact by default; --full adds TVL/reserves/fees/gauge/emissions (slower)
python -m sugar pools --chain=1135 --token0=lsk --token1=weth --pool-type=cl --limit=5

# quote a swap (read-only) — returns amount_in/out, derived price, oracle prices, price impact, route
python -m sugar quote --chain=1135 --from-token=lsk --to-token=eth --amount=10 --use-decimals

# preview a swap — returns [approve_tx, swap_tx] (or [swap_tx] for native input)
python -m sugar swap --chain=1135 --wallet=0xYou --from-token=lsk --to-token=eth --amount=10 --use-decimals
```

**Position identification.** `--pool=ADDR` for basic positions (one per wallet per pool, `id=0`); `--position=NFT_ID` for CL positions. The two can be combined to narrow a CL lookup within a specific pool.

**Amounts.** `--amount0` / `--amount1` default to raw wei so `sugar X | jq | sugar Y` chains without scaling pitfalls. Pass `--use-decimals` to interpret them as token units (`--amount0=0.5 --use-decimals` ≈ `0.5 * 10^token.decimals` wei).

**Chaining.** Pipe sugar output into sugar input, or into your signer:

``` bash
# Foundry: sign and broadcast in one step
python -m sugar deposit --chain=1135 --wallet=0xYou --pool=0x... --amount1=1000000000000000 \
  | jq -c '.[]' \
  | while read -r tx; do
      cast send --rpc-url $SUGAR_RPC_URI_1135 --private-key $YOUR_KEY \
        "$(jq -r .to <<<"$tx")" "$(jq -r .data <<<"$tx")" --value "$(jq -r .value <<<"$tx")"
    done

# extract a value from one sugar call, feed into another (wei flows through unchanged)
sugar positions --chain=1135 --wallet=0xYou \
  | jq -r '.[] | select(.id == 6759) | .liquidity'
```

For frontend integrations, hand the unsigned dicts to your wallet provider (MetaMask `eth_sendTransaction`, viem `writeContract`, ethers `sendTransaction`).

RPC config comes from `SUGAR_RPC_URI_<chain_id>` (same env contract as the Python SDK). `--chain` takes a numeric chain id.

Adding new subcommands is just adding methods to the `CLI` class in `sugar/cli.py` — Fire derives the flag layout from the function signature. The `_resolve_pool`, `_find_position`, `_build_quote`, `_addr` helpers in the same file are reusable across actions.

## Pools

``` python
from sugar.chains import AsyncOPChain

async with AsyncOPChain() as chain:
    pools = await chain.get_pools()
    usdc_velo = next(p for p in pools
                     if p.token0.token_address == AsyncOPChain.usdc.token_address
                     and p.token1.token_address == AsyncOPChain.velo.token_address)
    print(f"{usdc_velo.symbol}")
    print(f"Volume: {usdc_velo.token0_volume} {usdc_velo.token0.symbol} | {usdc_velo.token1_volume} {usdc_velo.token1.symbol} | ${usdc_velo.volume}")
    print(f"Fees: {usdc_velo.token0_fees.amount} {usdc_velo.token0.symbol} | {usdc_velo.token1_fees.amount} {usdc_velo.token1.symbol} | ${usdc_velo.total_fees}")
    print(f"TVL: {usdc_velo.reserve0.amount} {usdc_velo.token0.symbol} | {usdc_velo.reserve1.amount} {usdc_velo.token1.symbol} | ${usdc_velo.tvl}")
    print(f"APR: {usdc_velo.apr}%")
```

## Fees and Incentives

Latest epochs across all pools:

``` python
async with AsyncOPChain() as chain:
    epochs = await chain.get_latest_pool_epochs()
    ep = epochs[0]
    print(f"{ep.pool.symbol}  epoch: {ep.epoch_date}")
    print(f"Fees: {' '.join(f'{f.amount} {f.token.symbol}' for f in ep.fees)} (${ep.total_fees})")
    print(f"Incentives: {' '.join(f'{i.amount} {i.token.symbol}' for i in ep.incentives)} (${ep.total_incentives})")
```

For a single pool, use `chain.get_pool_epochs("0x...")`.

## Swaps

The SDK builds; the caller signs and broadcasts. `swap_from_quote` and `swap` both return a list of unsigned tx dicts — `[approve_tx, swap_tx]` for ERC20 input, or `[swap_tx]` for native (or when allowance already covers `amount_in`).

``` python
async with AsyncOPChain(signer_address="0xYou") as op:
    quote = await op.get_quote(from_token=AsyncOPChain.velo, to_token=AsyncOPChain.eth,
                               amount=AsyncOPChain.velo.parse_units(10))
    txs = await op.swap_from_quote(quote)
    # sign & broadcast each tx in order
```

One-shot (quote + build in a single call):

``` python
txs = await op.swap(from_token=AsyncOPChain.velo, to_token=AsyncOPChain.eth,
                    amount=AsyncOPChain.velo.parse_units(10))
```

## Superswaps

Cross-chain swap via Velodrome's superswap infrastructure. Returns a `SuperswapTxs` plan: `plan.txs` is the unsigned-tx list to sign and broadcast in order; `plan.swap_data` is set when a relayer step is required after the last broadcast (cross-chain ICA orchestration).

``` python
from sugar import OPChain, LiskChain, AsyncOPChain, AsyncSuperswap, HTTPSuperswapRelayer

async with AsyncOPChain(signer_address="0xYou") as from_chain:
    plan = await AsyncSuperswap(chain_for_writes=from_chain).swap(
        from_token=OPChain.velo, to_token=LiskChain.lsk,
        amount=OPChain.velo.parse_units(100),
    )
    # sign & broadcast plan.txs in order; capture the final tx hash
    last_tx_hash = "0x..."  # hash of the last broadcasted tx
    if plan.swap_data is not None:
        HTTPSuperswapRelayer().share_calls(**plan.relay_kwargs(commitment_dispatch_tx=last_tx_hash))
```

## Liquidity Deposits

Quote, then deposit. For an existing basic (stable/volatile) pool, supply one side and the router computes the pair:

``` python
async with AsyncOPChain() as op:
    pools = await op.get_pools()
    usdc_velo = next(p for p in pools
                     if p.token0.token_address == AsyncOPChain.usdc.token_address
                     and p.token1.token_address == AsyncOPChain.velo.token_address)
    quote = await op.quote_basic_deposit(usdc_velo, amount_token0=usdc_velo.token0.parse_units(1))
    await op.deposit(quote)
```

Variants:

- **CL pool, existing**: `op.quote_concentrated_deposit(pool, price_lower=8.0, price_upper=12.0, amount_token0=...)`. Pass exactly one amount; the other is derived from the pool's current sqrt price and the tick range.
- **CL pool, uninitialized**: build via `await op.pool_spec(token0=..., token1=..., tick_spacing=N)`, then pass `initial_price=10.0` to the quote. NFPM's `mint` deploys/initializes and mints the position in the same tx.
- **New basic pool**: `await op.pool_spec(token0=..., token1=..., stable=False)` then `quote_basic_deposit(..., amount_token0=X, amount_token1=Y)` — both amounts required (no reserves to rebalance against).

`chain.deposit(...)` accepts `slippage` (default `0.01`) and `delay_in_minutes` (deadline, default `30`). Slippage protects `amountMin` against price movement between quote and execution; tight CL ranges may need a smaller value, volatile basic pools a larger one.

## Positions

``` python
async with AsyncOPChain() as op:
    for p in await op.get_positions():
        print(f"{p.pool.symbol} #{p.id}: liq={p.liquidity} staked={p.staked} -> "
              f"{p.amount_token0} {p.pool.token0.symbol} + {p.amount_token1} {p.pool.token1.symbol}")
```

`Position` amount fields are raw token balances (wei). Combine with `chain.get_prices(...)` for USD display. `get_positions(owner=None)` defaults to the wallet's own address. Fetch positions just-in-time before withdrawing — slippage protects in flight, but a stale snapshot wastes the budget.

## Liquidity Withdrawals

Same dispatcher for basic (router) and CL (NFPM `decreaseLiquidity` + `collect` multicall):

``` python
from sugar.withdraw import Withdrawal

async with AsyncOPChain() as op:
    positions = await op.get_positions()

    await op.withdraw(Withdrawal.from_position(positions[0]))                     # full
    await op.withdraw(Withdrawal.from_position(positions[1], fraction=0.5))       # half
    await op.withdraw(Withdrawal.from_position(positions[2], burn=True))          # CL: close + burn NFT
```

`Withdrawal.from_position(p, *, fraction=1.0, burn=False)` is the spec. `burn=True` is CL-only and requires `fraction=1.0` (NFPM `burn` needs zero liquidity). `fraction=1.0` short-circuits the float scaling so very large V3 liquidity stays exact.

`chain.withdraw(...)` accepts the same `slippage` / `delay_in_minutes` as `deposit`, plus two CL-only knobs:

- `collect=True` *(default)* — when `False`, skips `collect` in the multicall; tokens stay in `tokensOwed` on the NFT for a later sweep.
- `unwrap_native=False` — when `True`, routes `collect` into NFPM and appends `unwrapWETH9` + `sweepToken` so the native leg arrives as ETH. Requires `collect=True` and a pool with a native leg. Basic pools always unwrap via `removeLiquidityETH`.

Tokens land in the wallet passed to the chain context (`signer_address`).

## Staking and Rewards

Each `Position` carries everything you need — gauge address on `position.pool.gauge`, emissions/fees state on the position itself.

``` python
async with AsyncOPChain() as op:
    p = (await op.get_positions())[0]

    await op.stake(p)             # CL: approve NFT → gauge.deposit(tokenId). Basic: approve LP → gauge.deposit(liquidity).
    await op.unstake(p)           # CL: full unstake (NFT returns). Basic: defaults to position.staked; pass amount=N for partial.
    await op.claim_emissions(p)   # gauge emissions
    await op.claim_fees(p)        # CL: nfpm.multicall([collect, optional unwrap+sweep, optional burn]). Basic: pool.claimFees().
    await op.claim_fees(p, burn=True)           # CL only, requires fully drained position
    await op.claim_fees(p, unwrap_native=True)  # CL only, native leg arrives as ETH
```

Validations fail fast: `stake` rejects pools without a gauge or with a killed gauge, CL positions that are already staked, and positions with zero unstaked liquidity. `unstake` rejects positions with zero staked liquidity. `claim_fees(..., burn=True)` rejects positions that still hold liquidity or are staked (NFPM `burn` requires `liquidity == 0` and `tokensOwed == 0`).

## Configuration

Supported chain ids: `10` (OP), `8453` (Base), `130` (Uni), `1135` (Lisk).

Every config field is overridable via env var `SUGAR_<UPPER_CASE_FIELD>_<chain_id>` (e.g. `SUGAR_RPC_URI_10`), or as a kwarg to the chain constructor. The full set lives in [`sugar/config.py`](sugar/config.py); the table below covers the ones you're likely to touch.

| field | default | notes |
|----|----|----|
| `rpc_uri` | chain specific | required for writes; public defaults are rate-limited |
| `swap_slippage` | `0.01` | applied to `amountMin` on swaps |
| `pool_page_size` | `500` | Sugar contract page size for `forSwaps` reads |
| `pagination_limit` | `2000` | upper bound for `paginate` |
| `price_batch_size` | `40` | batched `getManyRates...` chunks; lower if your RPC chokes on big batches |
| `pricing_cache_timeout_seconds` | `5` | TTL on the price oracle cache |
| `threading_max_workers` | `5` | ThreadPoolExecutor size for sync pagination |

Contract addresses (`sugar_contract_addr`, `slipstream_contract_addr`, `nfpm_contract_addr`, `router_contract_addr`, `quoter_contract_addr`, `swapper_contract_addr`, `price_oracle_contract_addr`, `interchain_router_contract_addr`, `bridge_contract_addr`, `bridge_token_addr`, `message_module_contract_addr`) and token lists (`connector_tokens_addrs`, `excluded_tokens_addrs`, `stable_token_addr`, `token_addr`) follow the same env override pattern.

Override in code:

``` python
from sugar.chains import AsyncOPChain

async with AsyncOPChain(rpc_uri="https://myrpc.com") as chain:
    ...
```

## Contributing to Sugar

### Set up

``` bash
python3 -m venv env
source env/bin/activate
pip install -e '.[dev]'
```

### Running tests

Tests live in `tests/` and run under `pytest`:

``` bash
pytest tests/                                    # everything (supersim skipped if :4444 closed)
pytest tests/ -m "not network and not supersim"  # unit only
pytest tests/test_helpers.py -v                  # one file
```

Two markers gate I/O-heavy tests:

- `network` — hits live chain RPCs (set `SUGAR_RPC_URI_<chain_id>` in `.env` or shell)
- `supersim` — requires a local supersim daemon on `127.0.0.1:4444`; auto-skipped via `conftest.py` if the port is closed

`.env` is loaded automatically by `conftest.py`.

### Regenerate ABIs

ABIs live in `sugar/abis`. To regenerate, run `python abis.py` with `ETHERSCAN_API_KEY` set. Source: [Optimistic Etherscan](https://optimistic.etherscan.io/).

## Useful Links

- Sugar contract deployments per chain: [velodrome-finance/sugar/deployments](https://github.com/velodrome-finance/sugar/tree/main/deployments)
- Universal router (referred to as "swapper" in this SDK): [velodrome-finance/universal-router](https://github.com/velodrome-finance/universal-router/tree/main/deployment-addresses)
