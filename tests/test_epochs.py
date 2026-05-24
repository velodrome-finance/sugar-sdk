"""Network tests for get_latest_pool_epochs (async + sync), exercising the
epoch/price-fetching optimization end to end on Base."""
import asyncio

import pytest

from sugar import AsyncBaseChain, BaseChain
from sugar.pool import LiquidityPool, LiquidityPoolEpoch
from sugar.token import Token

pytestmark = pytest.mark.network


@pytest.fixture(scope="module")
def latest_pool_epochs():
    async def run():
        async with AsyncBaseChain() as chain:
            return await chain.get_latest_pool_epochs()
    return asyncio.run(run())


@pytest.fixture(scope="module")
def sync_latest_pool_epochs():
    with BaseChain() as chain:
        return chain.get_latest_pool_epochs()


def test_returns_list_of_epochs(latest_pool_epochs):
    epochs = latest_pool_epochs
    assert isinstance(epochs, list)
    assert len(epochs) > 0
    assert all(isinstance(e, LiquidityPoolEpoch) for e in epochs)


def test_epoch_data_structure(latest_pool_epochs):
    epochs = latest_pool_epochs
    # Base has many pools with epochs; guards against a pagination regression.
    assert len(epochs) > 600, f"expected many epochs (>600), got {len(epochs)}"

    e = epochs[0]
    assert isinstance(e.ts, int) and e.ts > 0
    assert isinstance(e.lp, str) and e.lp.startswith("0x")
    assert isinstance(e.votes, int) and e.votes >= 0
    assert isinstance(e.emissions, int) and e.emissions >= 0
    assert isinstance(e.incentives, list)
    assert isinstance(e.fees, list)


def test_all_epochs_have_valid_pools(latest_pool_epochs):
    # The optimization wires raw epoch -> filtered raw pool -> prepared pool; if the
    # plumbing breaks, pools come back None. Assert every epoch resolved a pool.
    epochs = latest_pool_epochs
    without = [e for e in epochs if e.pool is None]
    assert not without, f"{len(without)}/{len(epochs)} epochs missing pools, e.g. {[e.lp for e in without[:5]]}"
    for e in epochs:
        assert isinstance(e.pool, LiquidityPool)
        assert isinstance(e.pool.token0, Token)
        assert isinstance(e.pool.token1, Token)


def test_total_value_is_substantial(latest_pool_epochs):
    # Live-chain data drifts; keep this low enough to be stable but high enough to
    # catch a pricing/pagination regression that zeroes everything out.
    total = sum(e.total_fees + e.total_incentives for e in latest_pool_epochs)
    assert total > 100_000, f"expected total fees + incentives > $100k, got ${total:,.2f}"


def test_sync_returns_list_of_epochs(sync_latest_pool_epochs):
    epochs = sync_latest_pool_epochs
    assert isinstance(epochs, list)
    assert len(epochs) > 0
    assert all(isinstance(e, LiquidityPoolEpoch) for e in epochs)


def test_sync_matches_async_count(latest_pool_epochs, sync_latest_pool_epochs):
    # Same chain, same read path — counts should agree.
    assert len(sync_latest_pool_epochs) == len(latest_pool_epochs)


def test_requires_async_context():
    async def run():
        chain = AsyncBaseChain()
        with pytest.raises(RuntimeError, match="async with"):
            await chain.get_latest_pool_epochs()
    asyncio.run(run())


def test_sync_requires_context():
    chain = BaseChain()
    with pytest.raises(RuntimeError, match="async with"):
        chain.get_latest_pool_epochs()
