# AUTOGENERATED! DO NOT EDIT! File to edit: ../src/token.ipynb.

# %% auto 0
__all__ = ['Token']

# %% ../src/token.ipynb 2
from typing import Tuple
from dataclasses import dataclass
from .helpers import normalize_address, float_to_uint256

# %% ../src/token.ipynb 4
@dataclass(frozen=True)
class Token:
    """Data class for Token
    based on: https://github.com/velodrome-finance/sugar/blob/v2/contracts/LpSugar.vy#L17
    """

    chain_id: str
    chain_name: str
    token_address: str
    symbol: str
    decimals: int
    listed: bool
    wrapped_token_address: str = None

    def __eq__(self, other):
        t1, t2 = normalize_address(self.wrapped_token_address or self.token_address), normalize_address(other.wrapped_token_address or other.token_address)
        return  t1 == t2 and self.chain_id == other.chain_id

    def parse_units(self, value: float) -> int:
        """Convert a value to wei/kwei/gwei/mwei based on the token's decimals."""
        return float_to_uint256(value=value, decimals=self.decimals)

    def to_float(self, value: int) -> float:
        """Convert a value from wei/kwei/gwei/mwei to decimal based on the token's decimals."""
        return float(value / 10 ** self.decimals)

    @property
    def is_native(self) -> bool: return self.wrapped_token_address is not None

    @classmethod
    def make_native_token(cls, symbol: str, wrapped_address: str, decimals: int, chain_id: str, chain_name: str) -> "Token":
        return Token(chain_id=chain_id, chain_name=chain_name, token_address=symbol, symbol=symbol, decimals=decimals, listed=True, wrapped_token_address=wrapped_address)

    @classmethod
    def from_tuple(cls, t: Tuple, chain_id: str, chain_name: str) -> "Token":
        (token_address, symbol, decimals, _, listed) = t
        return Token(
            chain_id=chain_id,
            chain_name=chain_name,
            token_address=normalize_address(token_address),
            symbol=symbol,
            decimals=decimals,
            listed=listed,
        )
