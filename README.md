# Sugar SDK

<p align="center">  
    <img src="/sugar.png" alt="Awesome CursorRules" />
</p>

Sugar makes Velodrome and Aerodrome devs life sweeter 🍭

## Contents

- [Using Sugar](#using-sugar)
- [Base Quickstart](#base-quickstart)
- [OP Quickstart](#op-quickstart)
- [Pools](#pools)
- [Fees and Incentives](#fees-and-incentives)
- [Swaps](#swaps)
- [Configuration](#configuration)
- [Contributing to Sugar](#contributing-to-sugar)
- [Useful Links](#useful-links)

## Using Sugar

``` bash
pip install git+https://github.com/velodrome-finance/sugar-sdk.git@v0.2.3
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
