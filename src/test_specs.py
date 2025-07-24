from sugar import OPChain, LiskChain

# (from_token, to_token, amount, requires_relay)[]
superswap_tests_specs = [
    (OPChain.velo, LiskChain.lsk, OPChain.velo.parse_units(10), True),
    (OPChain.velo, LiskChain.o_usdt, OPChain.velo.parse_units(10), False),
    (OPChain.o_usdt, LiskChain.lsk, OPChain.o_usdt.parse_units(10), True),
    (OPChain.o_usdt, LiskChain.o_usdt, OPChain.o_usdt.parse_units(10), False),
    (LiskChain.o_usdt, OPChain.o_usdt, LiskChain.o_usdt.parse_units(10), False),
    (LiskChain.eth, OPChain.velo, LiskChain.eth.parse_units(1), True),
    (LiskChain.lsk, OPChain.eth, LiskChain.lsk.parse_units(100), True),
]
