import inspect

import pytest

from sugar.cli import CLI, _addr, _one_side


def test_cli_subcommand_chain_required():
    subcommands = ['deposit', 'positions', 'withdraw', 'stake', 'unstake', 'claim_emissions', 'claim_fees', 'swap']
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
