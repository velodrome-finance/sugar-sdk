__all__ = ['QUOTER_STABLE_POOL_FILLER', 'QUOTER_VOLATILE_POOL_FILLER',
           'NEW_SLIPSTREAM_FACTORY_BITMASK', 'OLD_SLIPSTREAM_FACTORY_BITMASK',
           'PreparedRoute', 'pack_path', 'QuoteInput', 'Quote',
           'SuperswapQuote']

from functools import reduce
from typing import List, Union, Tuple, Optional
from eth_abi.packed import encode_packed
from dataclasses import dataclass
from .token import Token
from .pool import LiquidityPoolForSwap

# magic numbers
QUOTER_STABLE_POOL_FILLER, QUOTER_VOLATILE_POOL_FILLER = 2097152, 4194304
# CL pool factory bitmasks OR'd into the tick spacing so the mixed-route
# quoter can resolve the pool against the right slipstream factory.
NEW_SLIPSTREAM_FACTORY_BITMASK = 0x080000
OLD_SLIPSTREAM_FACTORY_BITMASK = 0x100000

@dataclass
class PreparedRoute:
    types: List[str]; values: List[Union[str, int, bool]]

    @property
    def encoded(self) -> bytes: return encode_packed(self.types, self.values)

def pack_path(path: List[Tuple[LiquidityPoolForSwap, bool]], for_swap: bool = False,
              slipstream_factory_addr: Optional[str] = None,
              old_slipstream_factory_addr: Optional[str] = None) -> PreparedRoute:
    # Factory addresses come from ChainSettings (already normalized via make_settings)
    # and pool.factory is normalized in LiquidityPoolForSwap.from_tuple, so direct
    # string equality is safe here without re-normalization on the hot path.
    is_v2_swap = for_swap and any(pool.is_basic for pool, _ in path)
    types, values = reduce(lambda s, pool: s + pool, [["address", "int24"] for i in range(len(path))], []) + ["address"], []
    for node in path:
        pool, reversed = node
        token0, token1 = pool.token0_address if not reversed else pool.token1_address, pool.token1_address if not reversed else pool.token0_address
        if pool.type > 0:
            if slipstream_factory_addr and pool.factory == slipstream_factory_addr: filler = pool.type | NEW_SLIPSTREAM_FACTORY_BITMASK
            elif old_slipstream_factory_addr and pool.factory == old_slipstream_factory_addr: filler = pool.type | OLD_SLIPSTREAM_FACTORY_BITMASK
            else: filler = pool.type
        else: filler =  QUOTER_STABLE_POOL_FILLER if pool.is_stable else QUOTER_VOLATILE_POOL_FILLER
        if len(values) == 0: values = [token0, filler, token1]
        else: values += [filler, token1]

    if is_v2_swap:
        types = list(map(lambda t: "bool" if t == "int24" else t, types))
        for i in range(len(values)):
            if values[i] == QUOTER_STABLE_POOL_FILLER: values[i] = True
            elif values[i] == QUOTER_VOLATILE_POOL_FILLER: values[i] = False

    return PreparedRoute(types=types, values=values)
  

@dataclass
class QuoteInput:
    from_token: Token; to_token: Token; path: List[Tuple[LiquidityPoolForSwap, bool]]; amount_in: int
    slipstream_factory_addr: Optional[str] = None
    old_slipstream_factory_addr: Optional[str] = None

    def to_tuple(self) -> tuple: return (self.from_token, self.to_token, tuple(self.path), self.amount_in, self.amount_out)

    @staticmethod
    def from_tuple(t: tuple) -> "QuoteInput":
        from_token, to_token, path, amount_in, amount_out = t
        return QuoteInput(from_token=from_token, to_token=to_token, path=list(path), amount_in=amount_in, amount_out=amount_out)

    @property
    def route(self) -> PreparedRoute:
        return pack_path(self.path,
                         slipstream_factory_addr=self.slipstream_factory_addr,
                         old_slipstream_factory_addr=self.old_slipstream_factory_addr)

    @property
    def route_for_swap(self) -> PreparedRoute:
        return pack_path(self.path, for_swap=True,
                         slipstream_factory_addr=self.slipstream_factory_addr,
                         old_slipstream_factory_addr=self.old_slipstream_factory_addr)

@dataclass
class Quote:
    input: QuoteInput; amount_out: int

    @property
    def from_token(self) -> Token: return self.input.from_token
    @property
    def to_token(self) -> Token: return self.input.to_token
    @property
    def path(self) -> List[Tuple[LiquidityPoolForSwap, bool]]: return self.input.path
    @property
    def amount_in(self) -> int: return self.input.amount_in

@dataclass(frozen=True)
class SuperswapQuote:
    from_token: Token
    to_token: Token
    from_bridge_token: Token
    to_bridge_token: Token
    amount_in: int
    origin_quote: Optional[Quote] = None
    destination_quote: Optional[Quote] = None

    @property
    def amount_out(self) -> int:
        return self.destination_quote.amount_out if self.destination_quote else self.bridged_amount

    @staticmethod
    def bridge_quote(from_token: Token, to_token: Token, amount: int) -> 'SuperswapQuote':
        return SuperswapQuote(from_token=from_token, to_token=to_token, from_bridge_token=from_token, to_bridge_token=to_token, amount_in=amount)

    @staticmethod
    def calc_bridged_amount(from_token: Token, from_bridge_token: Token, amount: int, origin_quote: Optional[Quote] = None) -> int:
        if from_token != from_bridge_token:
            assert origin_quote is not None, "origin_quote must be set"
            return origin_quote.amount_out
        else: return amount

    @property
    def bridged_amount(self) -> int: 
        return SuperswapQuote.calc_bridged_amount(
            from_token=self.from_token,
            from_bridge_token=self.from_bridge_token, amount=self.amount_in, origin_quote=self.origin_quote
        )

    @property
    def is_bridge(self) -> bool: return self.from_token == self.from_bridge_token and self.to_token == self.to_bridge_token
