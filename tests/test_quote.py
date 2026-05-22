
from sugar.pool import LiquidityPoolForSwap
from sugar.quote import pack_path


def test_pack_path_forward():
    path = [
        (LiquidityPoolForSwap(chain_id="10", chain_name="OP", lp='0xec3d9098BD40ec741676fc04D4bd26BCCF592aa3', type=200, token0_address='0x4200000000000000000000000000000000000006', token1_address='0x6c84a8f1c29108F47a79964b5Fe888D4f4D0dE40'), False),
        (LiquidityPoolForSwap(chain_id="10", chain_name="OP", lp='0x02A130b6D35611bC2D90e20f2ceA45431c0A9a8d', type=-1, token0_address='0x6c84a8f1c29108F47a79964b5Fe888D4f4D0dE40', token1_address='0x7F5c764cBc14f9669B88837ca1490cCa17c31607'), False),
        (LiquidityPoolForSwap(chain_id="10", chain_name="OP", lp='0xf7a73e1995030B0198f8d6e528a1c42ACEf90a4c', type=0, token0_address='0x7F5c764cBc14f9669B88837ca1490cCa17c31607', token1_address='0x9560e827aF36c94D2Ac33a39bCE1Fe78631088Db'), False),
    ]

    rt = pack_path(path)

    assert rt.types == ['address', 'int24', 'address', 'int24', 'address', 'int24', 'address']
    assert rt.values == ['0x4200000000000000000000000000000000000006', 200, '0x6c84a8f1c29108F47a79964b5Fe888D4f4D0dE40', 4194304, '0x7F5c764cBc14f9669B88837ca1490cCa17c31607', 2097152, '0x9560e827aF36c94D2Ac33a39bCE1Fe78631088Db']
    assert rt.encoded.hex() == "42000000000000000000000000000000000000060000c86c84a8f1c29108f47a79964b5fe888d4f4d0de404000007f5c764cbc14f9669b88837ca1490cca17c316072000009560e827af36c94d2ac33a39bce1fe78631088db"


def test_pack_path_reversed_first_hop():
    path = [
        (LiquidityPoolForSwap(chain_id="10", chain_name="OP", lp='0xec3d9098BD40ec741676fc04D4bd26BCCF592aa3', type=200, token0_address='0x4200000000000000000000000000000000000006', token1_address='0x6c84a8f1c29108F47a79964b5Fe888D4f4D0dE40'), True),
        (LiquidityPoolForSwap(chain_id="10", chain_name="OP", lp='0x02A130b6D35611bC2D90e20f2ceA45431c0A9a8d', type=-1, token0_address='0x6c84a8f1c29108F47a79964b5Fe888D4f4D0dE40', token1_address='0x7F5c764cBc14f9669B88837ca1490cCa17c31607'), False),
        (LiquidityPoolForSwap(chain_id="10", chain_name="OP", lp='0xf7a73e1995030B0198f8d6e528a1c42ACEf90a4c', type=0, token0_address='0x7F5c764cBc14f9669B88837ca1490cCa17c31607', token1_address='0x9560e827aF36c94D2Ac33a39bCE1Fe78631088Db'), False),
    ]

    rt = pack_path(path)

    assert rt.types == ['address', 'int24', 'address', 'int24', 'address', 'int24', 'address']
    assert rt.values == ['0x6c84a8f1c29108F47a79964b5Fe888D4f4D0dE40', 200, '0x4200000000000000000000000000000000000006', 4194304, '0x7F5c764cBc14f9669B88837ca1490cCa17c31607', 2097152, '0x9560e827aF36c94D2Ac33a39bCE1Fe78631088Db']
    assert rt.encoded.hex() == "6c84a8f1c29108f47a79964b5fe888d4f4d0de400000c842000000000000000000000000000000000000064000007f5c764cbc14f9669b88837ca1490cca17c316072000009560e827af36c94d2ac33a39bce1fe78631088db"


def test_pack_path_for_swap_v2():
    v2_nodes = [
        (LiquidityPoolForSwap(chain_id="10", chain_name="OP", lp='0xF1046053aa5682b4F9a81b5481394DA16BE5FF6b', type=-1, token0_address='0x9560e827aF36c94D2Ac33a39bCE1Fe78631088Db', token1_address='0x920Cf626a271321C151D027030D5d08aF699456b'), False),
        (LiquidityPoolForSwap(chain_id="10", chain_name="OP", lp='0xF1046053aa5682b4F9a81b5481394DA16BE5FF6b', type=-1, token0_address='0x920Cf626a271321C151D027030D5d08aF699456b', token1_address='0x4200000000000000000000000000000000000042'), False),
    ]

    rt = pack_path(v2_nodes, for_swap=True)
    assert rt.types == ['address', 'bool', 'address', 'bool', 'address']
    assert rt.values == [
        "0x9560e827aF36c94D2Ac33a39bCE1Fe78631088Db",
        False,
        "0x920Cf626a271321C151D027030D5d08aF699456b",
        False,
        "0x4200000000000000000000000000000000000042",
    ]
