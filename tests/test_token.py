from sugar.token import Token


def test_token_equality():
    usdc = Token(chain_id="10", chain_name="OP", token_address='0x0b2C639c533813f4Aa9D7837CAf62653d097Ff85', symbol='USDC', decimals=6, listed=True, wrapped_token_address=None)
    velo = Token(chain_id="10", chain_name="OP", token_address='0x9560e827aF36c94D2Ac33a39bCE1Fe78631088Db', symbol='VELO', decimals=18, listed=True, wrapped_token_address=None)
    another_velo = Token(chain_id="10", chain_name="OP", token_address='0x9560e827aF36c94D2Ac33a39bCE1Fe78631088Db'.lower(), symbol='VELO', decimals=18, listed=True, wrapped_token_address=None)
    velo_poser = Token(chain_id="101", chain_name="OOPS", token_address='0x9560e827aF36c94D2Ac33a39bCE1Fe78631088Db', symbol='VELO', decimals=18, listed=True, wrapped_token_address=None)
    eth = Token(chain_id="10", chain_name="OP", token_address='ETH', symbol='ETH', decimals=18, listed=True, wrapped_token_address='0x4200000000000000000000000000000000000006')

    assert usdc != velo, "USDC and VELO should not be equal"
    assert velo == another_velo, "VELO and another VELO should be equal"
    assert velo == velo, "VELO and VELO should be equal"
    assert velo != velo_poser, "VELO and VELO poser should not be equal"
    assert velo != eth, "VELO and ETH should not be equal"


def test_token_from_tuple_captures_emerging():
    # Sugar's token tuple: (address, symbol, decimals, account_balance, listed, emerging)
    addr = '0x9560e827aF36c94D2Ac33a39bCE1Fe78631088Db'
    listed = Token.from_tuple((addr, 'VELO', 18, 0, True, False), chain_id="10", chain_name="OP")
    emerging = Token.from_tuple((addr, 'NEW', 18, 0, False, True), chain_id="10", chain_name="OP")
    assert listed.emerging is False
    assert emerging.emerging is True


def test_token_emerging_defaults_false():
    t = Token(chain_id="10", chain_name="OP", token_address='0x0b2C639c533813f4Aa9D7837CAf62653d097Ff85', symbol='USDC', decimals=6, listed=True)
    assert t.emerging is False
