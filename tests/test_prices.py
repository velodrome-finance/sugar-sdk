"""Network tests for get_prices (async + sync), covering the token-filtering
price path and result alignment on Base."""
import asyncio

import pytest

from sugar import AsyncBaseChain, BaseChain
from sugar.price import Price

pytestmark = pytest.mark.network


@pytest.fixture(scope="module")
def async_tokens_and_prices():
    async def run():
        async with AsyncBaseChain() as chain:
            tokens = await chain.get_all_tokens()
            return tokens, await chain.get_prices(tokens)
    return asyncio.run(run())


@pytest.fixture(scope="module")
def sync_tokens_and_prices():
    with BaseChain() as chain:
        tokens = chain.get_all_tokens()
        return tokens, chain.get_prices(tokens)


def test_prices_align_with_tokens(async_tokens_and_prices):
    tokens, prices = async_tokens_and_prices
    assert isinstance(prices, list)
    assert len(prices) == len(tokens), "one price per input token, in order"
    assert len(tokens) > 40, "should exceed a single price chunk"
    for p in prices:
        assert isinstance(p, Price)
        assert p.price >= 0


def test_native_token_priced(async_tokens_and_prices):
    tokens, prices = async_tokens_and_prices
    assert tokens[0].symbol == "ETH"
    assert 100 < prices[0].price < 100_000


def test_stable_token_near_one(async_tokens_and_prices):
    tokens, prices = async_tokens_and_prices
    idx = next((i for i, t in enumerate(tokens) if t.symbol == "USDC"), None)
    assert idx is not None
    assert 0.95 <= prices[idx].price <= 1.05


def test_prices_cached_within_ttl(async_tokens_and_prices):
    tokens, _ = async_tokens_and_prices

    async def run():
        async with AsyncBaseChain() as chain:
            first = await chain.get_prices(tokens)
            second = await chain.get_prices(tokens)
            return first, second

    first, second = asyncio.run(run())
    assert len(first) == len(second)
    for a, b in zip(first, second):
        assert a.token.token_address == b.token.token_address
        assert a.price == b.price


def test_sync_prices_align_with_tokens(sync_tokens_and_prices):
    tokens, prices = sync_tokens_and_prices
    assert len(prices) == len(tokens)
    assert all(isinstance(p, Price) and p.price >= 0 for p in prices)
    assert tokens[0].symbol == "ETH"
    assert prices[0].price > 100


def test_requires_async_context():
    async def run():
        chain = AsyncBaseChain()
        with pytest.raises(RuntimeError, match="async with"):
            await chain.get_prices([])
    asyncio.run(run())


def test_sync_requires_context():
    chain = BaseChain()
    with pytest.raises(RuntimeError, match="async with"):
        chain.get_prices([])
