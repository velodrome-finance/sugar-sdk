__all__ = ['Position']

from dataclasses import dataclass
from typing import Tuple, Dict, Optional
from .helpers import normalize_address, ADDRESS_ZERO
from .pool import LiquidityPool

@dataclass(frozen=True)
class Position:
    """User's position in a pool, returned by `chain.get_positions(owner)`.

    Mirrors Sugar's `positions(limit, offset, account)` reader output. Amount
    fields are raw token amounts (wei-level uints) — for USD display, combine
    with `chain.get_prices(...)` and the pool's `token0/1`. For CL, `id` is the
    NFT tokenId; for basic pools `id` is 0 and tick / sqrt fields are unused.
    """
    chain_id: str
    chain_name: str
    # NFT tokenId for CL; 0 for basic
    id: int
    pool: LiquidityPool
    # unstaked liquidity (LP tokens for basic, V3 L for CL)
    liquidity: int
    # gauge-staked liquidity
    staked: int
    # raw token amounts (wei-level uints) at the pool's current price
    amount_token0: int
    amount_token1: int
    staked_token0: int
    staked_token1: int
    # accrued, unclaimed fees
    unstaked_earned0: int
    unstaked_earned1: int
    # accrued, unclaimed gauge emissions (in `pool.emissions_token` units)
    emissions_earned: int
    # CL tick bounds (0 for basic)
    tick_lower: int
    tick_upper: int
    sqrt_ratio_lower: int
    sqrt_ratio_upper: int
    # ALM contract managing this position; ADDRESS_ZERO if not ALM-managed
    alm: str

    @property
    def is_cl(self) -> bool: return self.pool.is_cl

    @property
    def is_alm(self) -> bool: return self.alm != ADDRESS_ZERO

    @property
    def is_in_range(self) -> bool:
        """For CL positions, True iff the pool's current tick is within [tick_lower, tick_upper).
        Always False for basic pools (the concept doesn't apply)."""
        return self.pool.is_cl and self.tick_lower <= self.pool.tick < self.tick_upper

    @classmethod
    def from_tuple(cls, t: Tuple, pools: Dict[str, LiquidityPool],
                   chain_id: str, chain_name: str) -> Optional["Position"]:
        # Sugar positions() tuple shape:
        # 0  id              uint256        # NFT tokenId (CL) or 0 (basic)
        # 1  lp              address
        # 2  liquidity       uint256
        # 3  staked          uint256
        # 4  amount0         uint256
        # 5  amount1         uint256
        # 6  staked0         uint256
        # 7  staked1         uint256
        # 8  unstaked_earned0  uint256
        # 9  unstaked_earned1  uint256
        # 10 emissions_earned  uint256
        # 11 tick_lower      int24
        # 12 tick_upper      int24
        # 13 sqrt_ratio_lower  uint160
        # 14 sqrt_ratio_upper  uint160
        # 15 locker          address
        # 16 unlocks_at      uint32
        # 17 alm             address
        lp = normalize_address(t[1])
        pool = pools.get(lp)
        if pool is None: return None
        return Position(
            chain_id=chain_id, chain_name=chain_name,
            id=t[0], pool=pool,
            liquidity=t[2], staked=t[3],
            amount_token0=t[4], amount_token1=t[5],
            staked_token0=t[6], staked_token1=t[7],
            unstaked_earned0=t[8], unstaked_earned1=t[9],
            emissions_earned=t[10],
            tick_lower=t[11], tick_upper=t[12],
            sqrt_ratio_lower=t[13], sqrt_ratio_upper=t[14],
            alm=normalize_address(t[17]),
        )
