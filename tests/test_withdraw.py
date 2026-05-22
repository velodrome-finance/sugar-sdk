from types import SimpleNamespace

import pytest

from sugar.withdraw import Withdrawal


def test_withdrawal_construction_guards():
    basic_pool = SimpleNamespace(is_cl=False)
    cl_pool = SimpleNamespace(is_cl=True)

    w = Withdrawal(pool=basic_pool, liquidity=100, amount_token0=10, amount_token1=20)
    assert (w.position_id, w.burn) == (None, False)
    w = Withdrawal(pool=cl_pool, liquidity=100, amount_token0=10, amount_token1=20, position_id=42)
    assert w.position_id == 42
    with pytest.raises(Exception):
        Withdrawal(pool=cl_pool, liquidity=100, amount_token0=10, amount_token1=20)
    with pytest.raises(Exception):
        Withdrawal(pool=basic_pool, liquidity=100, amount_token0=10, amount_token1=20, position_id=1)
    with pytest.raises(Exception):
        Withdrawal(pool=basic_pool, liquidity=0, amount_token0=10, amount_token1=20)
    with pytest.raises(Exception):
        Withdrawal(pool=basic_pool, liquidity=-1, amount_token0=10, amount_token1=20)
    with pytest.raises(Exception):
        Withdrawal(pool=basic_pool, liquidity=100, amount_token0=10, amount_token1=20, burn=True)


def test_withdrawal_from_position():
    basic_pool = SimpleNamespace(is_cl=False)
    cl_pool = SimpleNamespace(is_cl=True)

    basic_pos = SimpleNamespace(is_cl=False, liquidity=100, pool=basic_pool, id=0,
                                amount_token0=1_000_000, amount_token1=2_000_000)
    cl_pos = SimpleNamespace(is_cl=True, liquidity=1000, pool=cl_pool, id=42,
                             amount_token0=1_000_000, amount_token1=2_000_000)

    w = Withdrawal.from_position(basic_pos)
    assert (w.liquidity, w.amount_token0, w.amount_token1, w.position_id, w.burn) == (100, 1_000_000, 2_000_000, None, False)

    w = Withdrawal.from_position(cl_pos)
    assert (w.liquidity, w.amount_token0, w.amount_token1, w.position_id, w.burn) == (1000, 1_000_000, 2_000_000, 42, False)

    huge_pos = SimpleNamespace(is_cl=True, liquidity=10**30, pool=cl_pool, id=1,
                               amount_token0=10**30, amount_token1=2*10**30)
    w = Withdrawal.from_position(huge_pos)
    assert w.liquidity == 10**30
    assert w.amount_token0 == 10**30
    assert w.amount_token1 == 2*10**30

    w = Withdrawal.from_position(cl_pos, fraction=0.5)
    assert (w.liquidity, w.amount_token0, w.amount_token1) == (500, 500_000, 1_000_000)

    w = Withdrawal.from_position(cl_pos, burn=True)
    assert w.burn
    with pytest.raises(Exception):
        Withdrawal.from_position(cl_pos, fraction=0.5, burn=True)
    with pytest.raises(Exception):
        Withdrawal.from_position(cl_pos, fraction=0.999, burn=True)
    with pytest.raises(Exception):
        Withdrawal.from_position(basic_pos, burn=True)

    with pytest.raises(Exception):
        Withdrawal.from_position(cl_pos, fraction=0)
    with pytest.raises(Exception):
        Withdrawal.from_position(cl_pos, fraction=1.1)
    with pytest.raises(Exception):
        Withdrawal.from_position(cl_pos, fraction=-0.1)

    empty_pos = SimpleNamespace(is_cl=True, liquidity=0, pool=cl_pool, id=1, amount_token0=10, amount_token1=20)
    with pytest.raises(Exception):
        Withdrawal.from_position(empty_pos)

    tiny = SimpleNamespace(is_cl=True, liquidity=10, pool=cl_pool, id=1, amount_token0=10, amount_token1=20)
    with pytest.raises(Exception):
        Withdrawal.from_position(tiny, fraction=0.001)

    one_sided = SimpleNamespace(is_cl=True, liquidity=1000, pool=cl_pool, id=1, amount_token0=0, amount_token1=2_000_000)
    w = Withdrawal.from_position(one_sided)
    assert (w.amount_token0, w.amount_token1) == (0, 2_000_000)
