# Sugar SDK

<p align="center">  
    <img src="/sugar.png" alt="Sugar SDK" />
</p>

Sugar makes Velodrome and Aerodrome devs life sweeter 🍭

## Contents

- [Using Sugar](#using-sugar)
- [Base Quickstart](#base-quickstart)
- [OP Quickstart](#op-quickstart)
- [CLI](#cli)
- [Pools](#pools)
- [Fees and Incentives](#fees-and-incentives)
- [Swaps](#swaps)
- [Liquidity Deposits](#liquidity-deposits)
- [Positions](#positions)
- [Liquidity Withdrawals](#liquidity-withdrawals)
- [Staking and Rewards](#staking-and-rewards)
- [Configuration](#configuration)
- [Contributing to Sugar](#contributing-to-sugar)
- [Useful Links](#useful-links)

## Using Sugar

``` bash
pip install git+https://github.com/velodrome-finance/sugar-sdk.git@v0.3.1
```

You can take it for a spin on
[CodeSandbox](https://codesandbox.io/p/sandbox/sugar-sdk-playground-7c4z7g)

## Base Quickstart

Getting started with Sugar on Base network:

``` python
from sugar.chains import BaseChain, AsyncBaseChain

# async version
async with AsyncBaseChain() as chain:
    prices = await chain.get_prices(await chain.get_all_tokens())
    for p in prices[:5]:
        print(f"{p.token.symbol} price: {p.price}")

# sync version
with BaseChain() as chain:
    for p in chain.get_prices(chain.get_all_tokens())[:5]:
        print(f"{p.token.symbol} price: {p.price}")
```

## OP Quickstart

Getting started with Sugar on OP network:

``` python
from sugar.chains import AsyncOPChain, OPChain

async with AsyncOPChain() as chain:
    prices = await chain.get_prices(await chain.get_all_tokens())
    for p in prices[:5]:
        print(f"{p.token.symbol} price: {p.price}")

with OPChain() as chain:
    for p in chain.get_prices(chain.get_all_tokens())[:5]:
        print(f"{p.token.symbol} price: {p.price}")
```

## CLI

The SDK ships a `sugar` CLI (backed by [python-fire](https://github.com/google/python-fire)) for shell-side use. After install the `sugar` binary is on `PATH`; `python -m sugar` works equivalently.

Discover via `--help`:

``` bash
python -m sugar --help              # list subcommands
python -m sugar deposit --help      # see flags for one
```

**Dry-run is the default.** Every action returns the unsigned transaction(s) without broadcasting. Pass `--broadcast` to sign and send.

``` bash
# preview (dry-run) — returns the unsigned tx(s)
python -m sugar deposit --chain=10 --pool=0xd25711... --amount0=0.0001 --amount1=1

# same call with --broadcast — returns the receipt
python -m sugar deposit --chain=10 --pool=0xd25711... --amount0=0.0001 --amount1=1 --broadcast
```

Wallet signer is read from `SUGAR_PK`; RPC from `SUGAR_RPC_URI_<chain_id>` (same env contract as the Python SDK). `--chain` takes a numeric chain id.

Adding new subcommands is just adding methods to the `CLI` class in `sugar/cli.py` — Fire derives the flag layout from the function signature. The `_resolve_pool` and `_build_quote` helpers in the same file are reusable across actions.

## Pools

Getting information about pools:

``` python
from sugar.chains import AsyncOPChain, OPChain

async with AsyncOPChain() as chain:
    pools = await chain.get_pools()
    usdc_velo = next(iter([p for p in pools if p.token0.token_address == OPChain.usdc.token_address and p.token1.token_address == OPChain.velo.token_address]), None)
    print(f"{usdc_velo.symbol}")
    print("-----------------------")
    print(f"Volume: {usdc_velo.token0_volume} {usdc_velo.token0.symbol} | {usdc_velo.token1_volume} {usdc_velo.token1.symbol} | ${usdc_velo.volume}")
    print(f"Fees: {usdc_velo.token0_fees.amount} {usdc_velo.token0.symbol} | {usdc_velo.token1_fees.amount} {usdc_velo.token1.symbol} | ${usdc_velo.total_fees}")
    print(f"TVL: {usdc_velo.reserve0.amount} {usdc_velo.token0.symbol} | {usdc_velo.reserve1.amount} {usdc_velo.token1.symbol} | ${usdc_velo.tvl}")
    print(f"APR: {usdc_velo.apr}%")

with OPChain() as chain:
    pools = chain.get_pools()
    usdc_velo = next(iter([p for p in pools if p.token0.token_address == OPChain.usdc.token_address and p.token1.token_address == OPChain.velo.token_address]), None)
    print(f"{usdc_velo.symbol}")
    print("-----------------------")
    print(f"Volume: {usdc_velo.token0_volume} {usdc_velo.token0.symbol} | {usdc_velo.token1_volume} {usdc_velo.token1.symbol} | ${usdc_velo.volume}")
    print(f"Fees: {usdc_velo.token0_fees.amount} {usdc_velo.token0.symbol} | {usdc_velo.token1_fees.amount} {usdc_velo.token1.symbol} | ${usdc_velo.total_fees}")
    print(f"TVL: {usdc_velo.reserve0.amount} {usdc_velo.token0.symbol} | {usdc_velo.reserve1.amount} {usdc_velo.token1.symbol} | ${usdc_velo.tvl}")
    print(f"APR: {usdc_velo.apr}%")
```

## Fees and Incentives

To get information for the latest epochs across all the pools:

``` python
async with AsyncOPChain() as chain:
    epochs = await chain.get_latest_pool_epochs()
    ep = epochs[0]
    print(f"{ep.pool.symbol}")
    print(f"Epoch date: {ep.epoch_date}")
    print(f"Fees: {' '.join([f'{fee.amount} {fee.token.symbol}' for fee in ep.fees])} {ep.total_fees}")
    print(f"Incentives: {' '.join([f'{incentive.amount} {incentive.token.symbol}' for incentive in ep.incentives])} {ep.total_incentives}")
```

You can also get epochs for a specific pool using its address:

``` python
async with AsyncOPChain() as chain:
    epochs = await chain.get_pool_epochs("0x7A7f1187c4710010DB17d0a9ad3fcE85e6ecD90a")
    ep = epochs[0]
    print(f"{ep.pool.symbol}")
    print(f"Epoch date: {ep.epoch_date}")
    print(f"Fees: {' '.join([f'{fee.amount} {fee.token.symbol}' for fee in ep.fees])} {ep.total_fees}")
    print(f"Incentives: {' '.join([f'{incentive.amount} {incentive.token.symbol}' for incentive in ep.incentives])} {ep.total_incentives}")
```

## Swaps

Get a quote and swap:

``` python
from sugar.chains import AsyncOPChain

async with AsyncOPChain() as op:
    quote = await op.get_quote(from_token=AsyncOPChain.velo, to_token=AsyncOPChain.eth, amount=AsyncOPChain.velo.parse_units(10))
    if not quote:
        # no quote found 
    # check quote.amount_out
    await op.swap_from_quote(quote)
```

“I am Feeling lucky” swap:

``` python
from sugar.chains import AsyncOPChain

async with AsyncOPChain() as op:
    await op.swap(from_token=velo, to_token=eth, amount=velo.parse_units(10))
```

## Superswaps

```python
from sugar import OPChain, LiskChain, Superswap

superswap = Superswap()
quote = superswap.get_super_quote(from_token=OPChain.velo, to_token=LiskChain.lsk, amount=OPChain.velo.parse_units(100))
superswap.swap_from_quote(quote)

# feeling lucky Superswap
Superswap().swap(from_token=OPChain.velo, to_token=LiskChain.lsk, amount=OPChain.velo.parse_units(100))
```

As always, async version is also available

```python
from sugar import OPChain, LiskChain, AsyncSuperswap

superswap = AsyncSuperswap()
quote = await superswap.get_super_quote(from_token=OPChain.velo, to_token=LiskChain.lsk, amount=OPChain.velo.parse_units(100))
await superswap.swap_from_quote(quote)

# feeling lucky Superswap
await AsyncSuperswap().swap(from_token=OPChain.velo, to_token=LiskChain.lsk, amount=OPChain.velo.parse_units(100))
```

## Liquidity Deposits

Add liquidity to a basic (stable/volatile) pool. Quote, then deposit — the
router computes the optimal pairing from whichever side you supply. Sync and
async variants are symmetric:

``` python
from sugar.chains import AsyncOPChain, OPChain

# async version
async with AsyncOPChain() as op:
    pools = await op.get_pools()
    usdc_velo = next(p for p in pools if p.token0.token_address == AsyncOPChain.usdc.token_address and p.token1.token_address == AsyncOPChain.velo.token_address)
    quote = await op.quote_basic_deposit(usdc_velo, amount_token0=usdc_velo.token0.parse_units(1))
    await op.deposit(quote)

# sync version
with OPChain() as op:
    pools = op.get_pools()
    usdc_velo = next(p for p in pools if p.token0.token_address == OPChain.usdc.token_address and p.token1.token_address == OPChain.velo.token_address)
    quote = op.quote_basic_deposit(usdc_velo, amount_token0=usdc_velo.token0.parse_units(1))
    op.deposit(quote)
```

Add liquidity to a concentrated (CL) pool. Pass the price range as floats
(token1 per token0) and supply exactly one amount — the other is derived
on-chain from the pool's current sqrt price and the chosen tick range:

``` python
from sugar.chains import AsyncOPChain

async with AsyncOPChain() as op:
    pools = await op.get_pools()
    cl_usdc_velo = next(p for p in pools if p.is_cl
                        and p.token0.token_address == AsyncOPChain.usdc.token_address
                        and p.token1.token_address == AsyncOPChain.velo.token_address)

    quote = await op.quote_concentrated_deposit(
        cl_usdc_velo, price_lower=8.0, price_upper=12.0,
        amount_token0=cl_usdc_velo.token0.parse_units(10),
    )
    print(f"ticks [{quote.tick_lower}, {quote.tick_upper}] -> {quote.amount_token0} + {quote.amount_token1}")

    await op.deposit(quote)
```

Depositing into an uninitialized CL pool — either a not-yet-deployed pool
(build the spec via `chain.pool_spec(..., tick_spacing=N)`) or one deployed
without liquidity. Pass `initial_price` (a float, token1 per token0); NFPM's
`mint` deploys and/or initializes the pool in the same tx as the position mint:

``` python
new_pool = await op.pool_spec(token0=AsyncOPChain.usdc, token1=AsyncOPChain.velo, tick_spacing=100)
quote = await op.quote_concentrated_deposit(
    new_pool, price_lower=8.0, price_upper=12.0,
    amount_token0=new_pool.token0.parse_units(10),
    initial_price=10.0,
)
await op.deposit(quote)
```

Deploying a brand-new basic (stable/volatile) pool — `chain.pool_spec`
fetches the basic factory address from `router.defaultFactory()` for you.
Since a new pool has no reserves, the router can't rebalance — supply both
amounts upfront:

``` python
new_pool = await op.pool_spec(token0=AsyncOPChain.usdc, token1=AsyncOPChain.velo, stable=False)
quote = await op.quote_basic_deposit(
    new_pool,
    amount_token0=new_pool.token0.parse_units(10),
    amount_token1=new_pool.token1.parse_units(100),
)
await op.deposit(quote)
```

`chain.deposit(...)` accepts `slippage` (default `0.01`) and
`delay_in_minutes` (deadline; default `30`). Slippage applies to
`amount{0,1}Min` on the on-chain call — your protection against price
movement between quote and execution. Tight CL ranges may need a smaller
slippage; volatile basic pools may need a larger one.

## Positions

List positions owned by an address. The Sugar contract returns one paginated
view across basic + CL pools, including current-price amounts, accrued fees,
and (for CL) tick bounds:

``` python
from sugar.chains import AsyncOPChain

async with AsyncOPChain() as op:
    for p in await op.get_positions():
        print(f"{p.pool.symbol} #{p.id}: liq={p.liquidity} staked={p.staked} -> {p.amount_token0} {p.pool.token0.symbol} + {p.amount_token1} {p.pool.token1.symbol}")
```

Amount fields on `Position` are raw token balances (wei-level uints). For USD
display, combine with `chain.get_prices(...)` and the pool's `token0/1`.
`chain.get_positions(owner=None)` defaults to the wallet's own address; fetch
positions just-in-time before withdrawing (the on-chain price may move between
calls — slippage protects, but a stale snapshot wastes the budget).

## Liquidity Withdrawals

Withdraw from any position via the same dispatcher; basic pools go through
the router, CL positions through NFPM `decreaseLiquidity` + `collect`
bundled in a multicall:

``` python
from sugar.chains import AsyncOPChain
from sugar.withdraw import Withdrawal

async with AsyncOPChain() as op:
    positions = await op.get_positions()

    # full withdrawal of the first position
    w = Withdrawal.from_position(positions[0])
    await op.withdraw(w)

    # partial: withdraw half of another position
    w = Withdrawal.from_position(positions[1], fraction=0.5)
    await op.withdraw(w)

    # full close + clean up the NFT in one tx (CL only)
    w = Withdrawal.from_position(positions[2], burn=True)
    await op.withdraw(w)
```

`Withdrawal.from_position(p, *, fraction=1.0, burn=False)` carries the
withdrawal spec. `burn=True` (CL only) appends `nfpm.burn(token_id)` to the
multicall to clean up the empty NFT; `from_position` rejects `burn=True` with
`fraction != 1.0` (partial closes leave the NFT non-empty). `fraction=1.0`
short-circuits the float scaling, so very large V3 liquidity values stay
exact.

`chain.withdraw` takes the same `slippage` and `delay_in_minutes` kwargs as
`chain.deposit`, plus:

- `collect: bool = True` *(CL)* — when `False`, the multicall skips `collect`; tokens stay in `tokensOwed` on the NFT for a later sweep.
- `unwrap_native: bool = False` *(CL)* — when `True`, the multicall routes `collect` into NFPM and appends `unwrapWETH9` + `sweepToken` so the native leg arrives as ETH (not WETH); requires `collect=True` and a pool with a native leg. Basic pools already unwrap via `removeLiquidityETH`.

Tokens always land in the calling wallet (`self.account.address`).

## Staking and Rewards

Each `Position` carries everything needed to stake, unstake, and claim — the
gauge address lives on `position.pool.gauge`, and emissions / fees state is on
the position itself.

``` python
from sugar.chains import AsyncOPChain

async with AsyncOPChain() as op:
    positions = await op.get_positions()
    p = positions[0]

    # Stake the unstaked portion into the gauge.
    # CL: approves the NFT to the gauge, then gauge.deposit(tokenId).
    # Basic: approves the LP token, then gauge.deposit(position.liquidity).
    await op.stake(p)

    # Withdraw from the gauge.
    # CL: full unstake (the NFT returns to the wallet).
    # Basic: defaults to position.staked; pass `amount=N` to unstake a partial amount.
    await op.unstake(p)

    # Claim accrued gauge emissions for this position.
    await op.claim_emissions(p)

    # Claim accrued LP trading fees.
    # CL: nfpm.multicall([collect, optional unwrap+sweep, optional burn]).
    # Basic: pool.claimFees(). burn / unwrap_native are CL-only and ignored on basic.
    await op.claim_fees(p)
    await op.claim_fees(p, burn=True)               # CL only, requires fully drained position
    await op.claim_fees(p, unwrap_native=True)      # CL only, native leg arrives as ETH
```

Validations are fail-fast: `stake` rejects pools without a gauge or with a
killed gauge, CL positions that are already staked, and positions with zero
unstaked liquidity. `unstake` rejects positions with zero staked liquidity.
`claim_fees(..., burn=True)` rejects positions that still hold liquidity or
are staked (NFPM's `burn` requires `liquidity == 0` and `tokensOwed == 0`).

## Configuration

Full list of configuration parameters for Sugar. Chain IDs can be found
[here](https://chainlist.org/). Sugar uses decimal versions: Base is
`8453`, OP is `10`.

| config | env | default value |
|----|----|----|
| native_token_symbol |  | ETH |
| native_token_decimals |  | 18 |
| wrapped_native_token_addr | `SUGAR_WRAPPED_NATIVE_TOKEN_ADDR_<CHAIN_ID>` | chain specific |
| rpc_uri | `SUGAR_RPC_URI_<CHAIN_ID>` | chain specific |
| sugar_contract_addr | `SUGAR_CONTRACT_ADDR_<CHAIN_ID>` | chain specific |
| slipstream_contract_addr | `SUGAR_SLIPSTREAM_CONTRACT_ADDR_<CHAIN_ID>` | chain specific |
| nfpm_contract_addr | `SUGAR_NFPM_CONTRACT_ADDR` | chain specific |
| price_oracle_contract_addr | `SUGAR_PRICE_ORACLE_ADDR_<CHAIN_ID>` | chain specific |
| router_contract_addr | `SUGAR_ROUTER_CONTRACT_ADDR_<CHAIN_ID>` | chain specific |
| swapper_contract_addr | `SUGAR_ROUTER_SWAPPER_CONTRACT_ADDR_<CHAIN_ID>` | chain specific |
| swap_slippage | `SUGAR_SWAP_SLIPPAGE_<CHAIN_ID>` | 0.01 |
| token_addr | `SUGAR_TOKEN_ADDR_<CHAIN_ID>` | chain specific |
| stable_token_addr | `SUGAR_STABLE_TOKEN_ADDR_<CHAIN_ID>` | chain specific |
| connector_tokens_addrs | `SUGAR_CONNECTOR_TOKENS_ADDRS_<CHAIN_ID>` | chain specific |
| excluded_tokens_addrs | `SUGAR_EXCLUDED_TOKENS_ADDRS_<CHAIN_ID>` | chain specific |
| price_batch_size | `SUGAR_PRICE_BATCH_SIZE` | 40 |
| price_threshold_filter | `SUGAR_PRICE_THRESHOLD_FILTER` | 10 |
| interchain_router_contract_addr | `SUGAR_INTERCHAIN_ROUTER_CONTRACT_ADDR_<CHAIN_ID>` | chain specific |
| bridge_contract_addr | `SUGAR_BRIDGE_CONTRACT_ADDR_<CHAIN_ID>` | chain specific |
| bridge_token_addr | `SUGAR_BRIDGE_TOKEN_ADDR_<CHAIN_ID>` | chain specific |
| message_module_contract_addr | `SUGAR_MESSAGE_MODULE_CONTRACT_ADDR_<CHAIN_ID>` | chain specific |
| pool_page_size | `SUGAR_POOL_PAGE_SIZE` | 500 |
| pools_count_upper_bound | `POOLS_COUNT_UPPER_BOUND_<CHAIN_ID>` | 2500 |
| pagination_limit | `SUGAR_PAGINATION_LIMIT` | 2000 |
| pricing_cache_timeout_seconds | `SUGAR_PRICING_CACHE_TIMEOUT_SECONDS_<CHAIN_ID>` | 5 |
| threading_max_workers | `SUGAR_THREADING_MAX_WORKERS_<CHAIN_ID>` | 5 |

In order to write to Sugar contracts, you need to set your wallet
private key using env var `SUGAR_PK`

You can override specific settings in 2 ways:

- by setting corresponding env var: `SUGAR_RPC_URI_10=https://myrpc.com`
- in code:

``` python
from sugar.chains import OPChain

async with OPChain(rpc_uri="https://myrpc.com") as chain:
    ...
```

## Contributing to Sugar

### Set up and activate python virtual env

``` bash
python3 -m venv env
source env/bin/activate
```

### Install dependencies

``` bash
pip install nbdev pre-commit
pip install -e '.[dev]'
```

### Install pre-commit hooks for nbdev prep and cleanup

``` bash
pre-commit install
```

### Regenerate ABIs if needed

ABIs for contracts are stored inside `sugar/abis` dir. To regenerate
them, use `abis.py` script (make sure you have `ETHERSCAN_API_KEY` env
var set). We use [Optimistic
Etherscan](https://optimistic.etherscan.io/).

## Useful Links

- keep an eye on the latest sugar contract deployment for your favorite
  chain
  [here](https://github.com/velodrome-finance/sugar/tree/main/deployments)
- latest universal router contract (referred to as "swapper" in this sdk) deployment can be found [here](https://github.com/velodrome-finance/universal-router/tree/main/deployment-addresses)

## Chores and random release related gymnastics

- getting one file diff for LLM ingestion (skipping notebooks and ABIs):
    `git diff main YOUR_NEW_BRANCH --output=YOUR_NEW_BRANCH.diff ':(exclude)src/*.ipynb' ':(exclude)sugar/_modidx.py' ':(exclude)sugar/abis/*.json'`
