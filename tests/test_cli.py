import inspect
from types import SimpleNamespace

import pytest

from sugar.cli import CLI, _addr, _one_side, _route_intermediaries
from sugar.pool import pool_type_label


def test_cli_subcommand_chain_required():
    subcommands = ['deposit', 'positions', 'pools', 'quote', 'withdraw', 'stake', 'unstake', 'claim_emissions', 'claim_fees', 'swap']
    for name in subcommands:
        assert hasattr(CLI, name), f'CLI missing {name}'
        sig = inspect.signature(getattr(CLI, name))
        assert sig.parameters['chain'].default == inspect.Parameter.empty


def test_addr_normalization():
    assert _addr(None) is None
    assert _addr('0xd25711EdfBf747efCE181442Cc1D8F5F8fc8a0D3') == '0xd25711EdfBf747efCE181442Cc1D8F5F8fc8a0D3'
    assert _addr(int('0xd25711EdfBf747efCE181442Cc1D8F5F8fc8a0D3', 16)) == '0xd25711EdfBf747efCE181442Cc1D8F5F8fc8a0D3'


def test_addr_rejects_private_key_shaped_ints():
    with pytest.raises(SystemExit, match='private key'):
        _addr(int('0x' + 'a' * 64, 16))


def test_one_side():
    assert _one_side(100, None, 'ctx') == {'amount_token0': 100}
    with pytest.raises(SystemExit, match='exactly one'):
        _one_side(100, 200, 'ctx')


def test_pool_type_label():
    assert pool_type_label(-1) == 'volatile'
    assert pool_type_label(0) == 'stable'
    assert pool_type_label(1) == 'cl-1'
    assert pool_type_label(200) == 'cl-200'


def test_route_intermediaries_direct_swap_empty():
    """A 1-hop path (direct swap) has no intermediaries between from_token and to_token."""
    pool = SimpleNamespace(token0_address='0xA', token1_address='0xB', lp='0xLP', type=0)
    quote = SimpleNamespace(path=[(pool, False)])
    assert _route_intermediaries(None, quote) == []  # `c` unused when path is direct


def test_route_intermediaries_multi_hop():
    """For an N-pool path, the route lists N-1 intermediate tokens (output of each non-final hop)."""
    p1 = SimpleNamespace(token0_address='0xA', token1_address='0xB', lp='0xLP1', type=-1)
    p2 = SimpleNamespace(token0_address='0xB', token1_address='0xC', lp='0xLP2', type=200)
    quote = SimpleNamespace(path=[(p1, False), (p2, False)])
    fake_chain = SimpleNamespace(get_token=lambda addr: SimpleNamespace(symbol=f'sym{addr}'))
    route = _route_intermediaries(fake_chain, quote)
    assert route == [{'symbol': 'sym0xB', 'address': '0xB', 'lp': '0xLP1', 'type_label': 'volatile'}]
