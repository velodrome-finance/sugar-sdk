
from sugar.chains import (
    AsyncBaseChain,
    AsyncLiskChain,
    AsyncOPChain,
    AsyncUniChain,
    BaseChain,
    LiskChain,
    OPChain,
    UniChain,
    get_async_chain,
    get_async_simnet_chain,
    get_chain,
    get_simnet_chain,
)


def test_chain_id_and_name_sync():
    with BaseChain() as base:
        assert base.chain_id == "8453"
        assert base.name == "Base"
    with OPChain() as op:
        assert op.chain_id == "10"
        assert op.name == "OP"
    with UniChain() as uni:
        assert uni.chain_id == "130"
        assert uni.name == "Uni"
    with LiskChain() as lisk:
        assert lisk.chain_id == "1135"
        assert lisk.name == "Lisk"


async def _async_chain_id_and_name():
    async with AsyncBaseChain() as base:
        assert base.chain_id == "8453"
        assert base.name == "Base"
    async with AsyncOPChain() as op:
        assert op.chain_id == "10"
        assert op.name == "OP"
    async with AsyncUniChain() as uni:
        assert uni.chain_id == "130"
        assert uni.name == "Uni"
    async with AsyncLiskChain() as lisk:
        assert lisk.chain_id == "1135"
        assert lisk.name == "Lisk"


def test_chain_id_and_name_async():
    import asyncio
    asyncio.run(_async_chain_id_and_name())


def test_factory_functions():
    for cid in ("10", "8453", "130", "1135"):
        assert get_chain(cid)
        assert get_async_chain(cid)
    for cid in ("10", "8453", "1135"):
        assert get_simnet_chain(cid)
        assert get_async_simnet_chain(cid)


async def _async_settings_rpc_uri():
    async with AsyncOPChain() as op:
        assert op.settings.rpc_uri != "https://mainnet.base.org"
    async with AsyncBaseChain() as base:
        assert base.settings.rpc_uri != "https://optimism-mainnet.wallet.coinbase.com"
    async with AsyncUniChain() as uni:
        assert uni.settings.rpc_uri != "https://unichain.drpc.org"
    async with AsyncLiskChain() as lisk:
        assert lisk.settings.rpc_uri != "https://lisk.drpc.org"


def test_settings_rpc_uri_override_check():
    import asyncio
    asyncio.run(_async_settings_rpc_uri())
