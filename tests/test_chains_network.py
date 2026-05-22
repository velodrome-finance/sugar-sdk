import asyncio

import pytest

from sugar.chains import (
    AsyncBaseChain,
    AsyncLiskChain,
    AsyncOPChain,
    AsyncUniChain,
    BaseChain,
    LiskChain,
    OPChain,
    UniChain,
)


pytestmark = pytest.mark.network


SYNC_CHAINS = [OPChain, BaseChain, UniChain, LiskChain]
ASYNC_CHAINS = [AsyncOPChain, AsyncBaseChain, AsyncUniChain, AsyncLiskChain]
CHAIN_IDS = ["op", "base", "uni", "lisk"]


def _check_reads(c):
    tokens = c.get_all_tokens()
    assert tokens, "no tokens returned"
    assert any(t.is_native for t in tokens), "no native token"
    pools = c.get_pools()
    assert pools, "no pools returned"
    assert pools[0].chain_id == c.chain_id


async def _check_reads_async(c):
    tokens = await c.get_all_tokens()
    assert tokens, "no tokens returned"
    assert any(t.is_native for t in tokens), "no native token"
    pools = await c.get_pools()
    assert pools, "no pools returned"
    assert pools[0].chain_id == c.chain_id


@pytest.mark.parametrize("chain_cls", SYNC_CHAINS, ids=CHAIN_IDS)
def test_chain_reads_sync(chain_cls):
    with chain_cls() as c:
        _check_reads(c)


@pytest.mark.parametrize("chain_cls", ASYNC_CHAINS, ids=CHAIN_IDS)
def test_chain_reads_async(chain_cls):
    async def run():
        async with chain_cls() as c:
            await _check_reads_async(c)
    asyncio.run(run())


# Catches Position.from_tuple drift (e.g. the Sugar contract adding a field) against a
# real chain. The wallet below has a known mix of basic + CL positions on Lisk — if the
# tuple shape changes, the parse returns None and this test fails loud.
_LISK_KNOWN_WALLET = "0x892ff98a46e5bd141E2D12618f4B2Fe6284debac"


def test_position_parse_against_live_chain():
    with LiskChain(signer_address=_LISK_KNOWN_WALLET) as c:
        positions = c.get_positions()
        assert positions, f"wallet {_LISK_KNOWN_WALLET} has no positions or parser dropped them all"
        # Spot-check a CL position deserializes cleanly (has all expected fields).
        cl = next((p for p in positions if p.pool.is_cl), None)
        if cl is not None:
            assert cl.tick_lower is not None
            assert cl.tick_upper is not None
            assert cl.sqrt_ratio_lower is not None
            assert cl.sqrt_ratio_upper is not None
            assert hasattr(cl, "alm")
