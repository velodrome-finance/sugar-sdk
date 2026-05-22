import asyncio

import pytest

from sugar.chains import AsyncLiskChain, AsyncOPChain
from sugar.superswap import AsyncSuperswap, Superswap


pytestmark = pytest.mark.network


async def _async_super_quote():
    from_token, to_token = AsyncOPChain.o_usdt, AsyncLiskChain.o_usdt
    amount = from_token.parse_units(1)
    quote = await AsyncSuperswap().get_super_quote(from_token=from_token, to_token=to_token, amount=amount)
    assert quote.is_bridge
    assert quote.amount_out == AsyncLiskChain.o_usdt.parse_units(1)


def test_super_quote_async():
    asyncio.run(_async_super_quote())


def test_super_quote_sync():
    from_token, to_token = AsyncOPChain.o_usdt, AsyncLiskChain.o_usdt
    amount = from_token.parse_units(1)
    quote = Superswap().get_super_quote(from_token=from_token, to_token=to_token, amount=amount)
    assert quote.is_bridge
