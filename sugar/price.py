__all__ = ['Price']

from dataclasses import dataclass
from .token import Token

@dataclass(frozen=True)
class Price:
    """Data class for Token Price

    based on:
    https://github.com/velodrome-finance/oracle/blob/main/contracts/VeloOracle.sol
    """

    token: Token
    price: float

    @property
    def pretty_price(self) -> float: return round(self.price, 5)
