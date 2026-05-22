import asyncio
import os

import pytest

from sugar import LiskChain, OPChain
from sugar.chains import (
    AsyncBaseChain,
    AsyncBaseChainSimnet,
    AsyncLiskChainSimnet,
    AsyncOPChain,
    AsyncOPChainSimnet,
    BaseChainSimnet,
    LiskChainSimnet,
    OPChainSimnet,
    get_async_simnet_chain_from_token,
    get_simnet_chain_from_token,
)
from sugar.superswap import AsyncSuperswap, MockSuperswapRelayer, Superswap


pytestmark = pytest.mark.supersim


_SUPERSWAP_SPECS = [
    (OPChain.velo, LiskChain.lsk, OPChain.velo.parse_units(10), True),
    (OPChain.velo, LiskChain.o_usdt, OPChain.velo.parse_units(10), False),
    (OPChain.o_usdt, LiskChain.lsk, OPChain.o_usdt.parse_units(10), True),
    (OPChain.o_usdt, LiskChain.o_usdt, OPChain.o_usdt.parse_units(10), False),
    (LiskChain.o_usdt, OPChain.o_usdt, LiskChain.o_usdt.parse_units(10), False),
    (LiskChain.eth, OPChain.velo, LiskChain.eth.parse_units(1), True),
    (LiskChain.lsk, OPChain.eth, LiskChain.lsk.parse_units(100), True),
]


def test_sugar_pk_set():
    assert os.getenv("SUGAR_PK") is not None


async def _async_simnet_rpc():
    async with AsyncOPChainSimnet() as op:
        assert "127.0.0.1" in op.settings.rpc_uri
    async with AsyncBaseChainSimnet() as base:
        assert "127.0.0.1" in base.settings.rpc_uri
    async with AsyncLiskChainSimnet() as lisk:
        assert "127.0.0.1" in lisk.settings.rpc_uri


def test_simnet_rpc_uri():
    asyncio.run(_async_simnet_rpc())
    with OPChainSimnet() as op:
        assert "127.0.0.1" in op.settings.rpc_uri
    with BaseChainSimnet() as base:
        assert "127.0.0.1" in base.settings.rpc_uri
    with LiskChainSimnet() as lisk:
        assert "127.0.0.1" in lisk.settings.rpc_uri


async def _async_token_balances():
    async with AsyncOPChainSimnet() as simnet:
        assert await simnet.get_token_balance(AsyncOPChainSimnet.velo) == 1000000000000000000000
        assert await simnet.get_token_balance(AsyncOPChainSimnet.eth) == 10000000000000000000000


def test_token_balances_async():
    asyncio.run(_async_token_balances())


def test_token_balances_sync():
    with OPChainSimnet() as simnet:
        assert simnet.get_token_balance(OPChainSimnet.velo) == 1000000000000000000000
        assert simnet.get_token_balance(OPChainSimnet.eth) == 10000000000000000000000


def test_unsupported_chain_pair():
    with OPChainSimnet() as op_sim:
        from_token, to_token = AsyncOPChain.velo, AsyncBaseChain.aero
        error = None
        try:
            Superswap(chain_for_writes=op_sim, relayer=MockSuperswapRelayer()).swap(
                from_token, to_token, amount=from_token.parse_units(20)
            )
        except ValueError as e:
            error = e
        assert str(error) == "Superswap only supports ['OP', 'Lisk', 'Uni']. Got OP -> Base"


def test_superswap_sync():
    for from_token, to_token, amount, requires_relay in _SUPERSWAP_SPECS:
        with get_simnet_chain_from_token(from_token) as from_sim:
            relayer = MockSuperswapRelayer()
            tx = Superswap(chain_for_writes=from_sim, relayer=relayer).swap(
                from_token, to_token, amount=amount, slippage=0.1
            )
            assert tx.startswith("0x")
            if not requires_relay:
                assert relayer.get_call_count() == 0
                continue
            assert relayer.get_call_count() == 1
            last_call = relayer.get_last_call()
            assert isinstance(last_call["salt"], str)
            assert isinstance(last_call["origin_domain"], int)


async def _async_superswap_runner():
    for from_token, to_token, amount, requires_relay in _SUPERSWAP_SPECS:
        async with get_async_simnet_chain_from_token(from_token) as from_sim:
            relayer = MockSuperswapRelayer()
            tx = await AsyncSuperswap(chain_for_writes=from_sim, relayer=relayer).swap(
                from_token, to_token, amount=amount, slippage=0.1
            )
            assert tx.startswith("0x")
            if not requires_relay:
                assert relayer.get_call_count() == 0
                continue
            assert relayer.get_call_count() == 1
            last_call = relayer.get_last_call()
            assert isinstance(last_call["salt"], str)
            assert isinstance(last_call["origin_domain"], int)


def test_superswap_async():
    asyncio.run(_async_superswap_runner())
