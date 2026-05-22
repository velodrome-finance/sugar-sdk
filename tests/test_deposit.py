from types import SimpleNamespace

import pytest

from sugar.deposit import DepositQuote


def test_deposit_quote_construction_and_guards():
    basic_pool = SimpleNamespace(is_cl=False)
    cl_pool = SimpleNamespace(is_cl=True, type=200,
                              token0=SimpleNamespace(decimals=18),
                              token1=SimpleNamespace(decimals=6))

    q = DepositQuote(pool=basic_pool, amount_token0=1_000, amount_token1=2_000)
    assert q.tick_lower == None
    assert q.sqrt_price_x96 == 0

    with pytest.raises(Exception):
        DepositQuote(pool=basic_pool, amount_token0=1, amount_token1=1, tick_lower=0, tick_upper=200)
    with pytest.raises(Exception):
        DepositQuote(pool=basic_pool, amount_token0=1, amount_token1=1, sqrt_price_x96=1)

    q = DepositQuote(pool=cl_pool, amount_token0=10**18, amount_token1=2*10**9, tick_lower=-200, tick_upper=200)
    assert q.tick_lower < q.tick_upper
    with pytest.raises(Exception):
        DepositQuote(pool=cl_pool, amount_token0=1, amount_token1=1)
    with pytest.raises(Exception):
        DepositQuote(pool=cl_pool, amount_token0=1, amount_token1=1, tick_lower=10, tick_upper=10)
    with pytest.raises(Exception):
        DepositQuote(pool=cl_pool, amount_token0=1, amount_token1=1, tick_lower=1, tick_upper=2)
