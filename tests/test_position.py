from types import SimpleNamespace


from sugar.helpers import ADDRESS_ZERO, normalize_address
from sugar.position import Position


def test_position_from_tuple():
    cl_pool = SimpleNamespace(is_cl=True, tick=50)
    basic_pool = SimpleNamespace(is_cl=False, tick=0)
    lp_cl = normalize_address("0x1111111111111111111111111111111111111111")
    lp_basic = normalize_address("0x2222222222222222222222222222222222222222")
    alm_addr = normalize_address("0x3333333333333333333333333333333333333333")
    pools = {lp_cl: cl_pool, lp_basic: basic_pool}

    t_cl = (42, lp_cl, 1000, 500, 100, 200, 50, 75, 10, 20, 5, -100, 100, 12345, 67890, ADDRESS_ZERO, 0, alm_addr)
    p = Position.from_tuple(t_cl, pools, "10", "Optimism")
    assert (p.id, p.liquidity, p.staked) == (42, 1000, 500)
    assert (p.amount_token0, p.amount_token1) == (100, 200)
    assert (p.staked_token0, p.staked_token1) == (50, 75)
    assert (p.unstaked_earned0, p.unstaked_earned1, p.emissions_earned) == (10, 20, 5)
    assert (p.tick_lower, p.tick_upper) == (-100, 100)
    assert (p.sqrt_ratio_lower, p.sqrt_ratio_upper) == (12345, 67890)
    assert p.alm == alm_addr
    assert p.is_cl
    assert p.is_alm
    assert p.is_in_range

    out_low = SimpleNamespace(is_cl=True, tick=-101)
    out_high = SimpleNamespace(is_cl=True, tick=100)
    in_low = SimpleNamespace(is_cl=True, tick=-100)
    for pool, expected in [(out_low, False), (out_high, False), (in_low, True)]:
        p_test = Position.from_tuple(t_cl, {lp_cl: pool}, "10", "Optimism")
        assert p_test.is_in_range == expected

    t_basic = (0, lp_basic, 999, 0, 1000, 2000, 0, 0, 5, 8, 0, 0, 0, 0, 0, ADDRESS_ZERO, 0, ADDRESS_ZERO)
    p = Position.from_tuple(t_basic, pools, "10", "Optimism")
    assert (p.id, p.liquidity) == (0, 999)
    assert not (p.is_cl)
    assert not (p.is_alm)
    assert not (p.is_in_range)

    unknown_lp = normalize_address("0x9999999999999999999999999999999999999999")
    t_unknown = (1, unknown_lp, 100, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, ADDRESS_ZERO, 0, ADDRESS_ZERO)
    assert Position.from_tuple(t_unknown, pools, "10", "Optimism") is None
