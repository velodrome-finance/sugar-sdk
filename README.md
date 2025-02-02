# Sugar SDK


<!-- WARNING: THIS FILE WAS AUTOGENERATED! DO NOT EDIT! -->

## Using Sugar

``` bash
pip install git+https://github.com/velodrome-finance/sugar-sdk
```

**TODO**: push to pypi

``` python
# load env
from dotenv import load_dotenv
load_dotenv()
```

    True

## Aero quickstart

``` python
from sugar.token import Token
from sugar.price import Price
from sugar.config import SugarConfig

SugarConfig.aero()

# listing first 5 tokens for brevity

(await Token.get_all_tokens())[:5]

# let's grab aero token and figure out what it's worth

aero = [t for t in await Token.get_all_listed_tokens() if t.symbol == 'AERO']
await Price.get_prices(aero)
```

    [Price(token=Token(token_address='0x940181a94A35A4569E4529A3CDfB74e38FD98631', symbol='AERO', decimals=18, listed=True), price=0.0)]

# Velo quickstart

``` python
from sugar.token import Token
from sugar.price import Price
from sugar.config import SugarConfig

SugarConfig.velo()

# listing first 5 tokens for brevity
(await Token.get_all_tokens())[:5]

# let's grab velo token and figure out what it's worth

velo = [t for t in await Token.get_all_listed_tokens() if t.symbol == 'VELO']
await Price.get_prices(velo)
```

    [Price(token=Token(token_address='0x9560e827aF36c94D2Ac33a39bCE1Fe78631088Db', symbol='VELO', decimals=18, listed=True), price=0.070724)]

## Deposits

In order to deposit, make sure spender’s account’s private key is
provided via `SUGAR_PK` env var. Here’s how you can deposit
[vAMM-USDC/AERO](https://aerodrome.finance/deposit?token0=0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913&token1=0x940181a94A35A4569E4529A3CDfB74e38FD98631&type=-1)

``` python

from sugar.config import SugarConfig
from sugar.pool import LiquidityPool

SugarConfig.aero()

pools = list(filter(lambda x: "vAMM-USDC" in x.symbol and "AERO" in x.symbol, await LiquidityPool.get_pools()))

# 0.02 USDC 
deposit = Deposit(pools[0], 0.02)
await deposit.deposit()
```

### Configuration

Sugar configuration is available through `sugar.config` module. Here’s
what default config looks like

``` python
from sugar.config import  SugarConfig

SugarConfig.get_config()
```

    SugarConfig(rpc_uri='https://optimism-mainnet.wallet.coinbase.com', sugar_contract_addr='0x3B919747B46B13CFfd9f16629cFf951C0b7ea1e2', price_oracle_contract_addr='0x59114D308C6DE4A84F5F8cD80485a5481047b99f', token_addr='0x9560e827aF36c94D2Ac33a39bCE1Fe78631088Db', stable_token_addr='0x7F5c764cBc14f9669B88837ca1490cCa17c31607', connector_tokens_addrs=['0x9560e827aF36c94D2Ac33a39bCE1Fe78631088Db', '0x4200000000000000000000000000000000000042', '0x4200000000000000000000000000000000000006', '0x9Bcef72be871e61ED4fBbc7630889beE758eb81D', '0x2E3D870790dC77A83DD1d18184Acc7439A53f475', '0x8c6f28f2F1A3C87F0f938b96d27520d9751ec8d9', '0x1F32b1c2345538c0c6f582fCB022739c4A194Ebb', '0xbfD291DA8A403DAAF7e5E9DC1ec0aCEaCd4848B9', '0xc3864f98f2a61A7cAeb95b039D031b4E2f55e0e9', '0x9485aca5bbBE1667AD97c7fE7C4531a624C8b1ED', '0xDA10009cBd5D07dd0CeCc66161FC93D7c9000da1', '0x73cb180bf0521828d8849bc8CF2B920918e23032', '0x6806411765Af15Bddd26f8f544A34cC40cb9838B', '0x6c2f7b6110a37b3B0fbdd811876be368df02E8B0', '0xc5b001DC33727F8F26880B184090D3E252470D45', '0x6c84a8f1c29108F47a79964b5Fe888D4f4D0dE40', '0xc40F949F8a4e094D1b49a23ea9241D289B7b2819', '0x94b008aA00579c1307B0EF2c499aD98a8ce58e58', '0x0b2C639c533813f4Aa9D7837CAf62653d097Ff85'], protocol_name='velo', price_batch_size=40, pagination_limit=2000, web3=<web3.main.AsyncWeb3 object>)

Sugar can be configured using env variables:

| config | env | default value |
|----|----|----|
| rpc_uri | `SUGAR_RPC_URI` | https://optimism-mainnet.wallet.coinbase.com |
| sugar_contract_addr | `SUGAR_CONTRACT_ADDR` | 0x3B919747B46B13CFfd9f16629cFf951C0b7ea1e2 |
| price_oracle_contract_addr | `SUGAR_PRICE_ORACLE_ADDR` | 0xcA97e5653d775cA689BED5D0B4164b7656677011 |
| token_addr | `SUGAR_TOKEN_ADDR` | 0x9560e827aF36c94D2Ac33a39bCE1Fe78631088Db |
| stable_token_addr | `SUGAR_STABLE_TOKEN_ADDR` | 0x7F5c764cBc14f9669B88837ca1490cCa17c31607 |
| connector_tokens_addrs | `SUGAR_CONNECTOR_TOKENS_ADDRS` | 0x9560e827aF36c94D2Ac33a39bCE1Fe78631088Db,0x4200000000000000000000000000000000000042,0x4200000000000000000000000000000000000006,0x9bcef72be871e61ed4fbbc7630889bee758eb81d,0x2e3d870790dc77a83dd1d18184acc7439a53f475,0x8c6f28f2f1a3c87f0f938b96d27520d9751ec8d9,0x1f32b1c2345538c0c6f582fcb022739c4a194ebb,0xbfd291da8a403daaf7e5e9dc1ec0aceacd4848b9,0xc3864f98f2a61a7caeb95b039d031b4e2f55e0e9,0x9485aca5bbbe1667ad97c7fe7c4531a624c8b1ed,0xDA10009cBd5D07dd0CeCc66161FC93D7c9000da1,0x73cb180bf0521828d8849bc8cf2b920918e23032,0x6806411765af15bddd26f8f544a34cc40cb9838b,0x6c2f7b6110a37b3b0fbdd811876be368df02e8b0,0xc5b001dc33727f8f26880b184090d3e252470d45,0x6c84a8f1c29108f47a79964b5fe888d4f4d0de40,0xc40f949f8a4e094d1b49a23ea9241d289b7b2819,0x94b008aa00579c1307b0ef2c499ad98a8ce58e58,0x0b2c639c533813f4aa9d7837caf62653d097ff85 |
| price_batch_size | `SUGAR_PRICE_BATCH_SIZE` | 40 |
| protocol_name | `SUGAR_PROTOCOL_NAME` | velo |
| pagination_limit | `SUGAR_PAGINATION_LIMIT` | 2000 |

## Contributing to Sugar

### Set up and acivate python virtual env

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
