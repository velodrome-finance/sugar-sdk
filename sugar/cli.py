__all__ = ['CLI', 'main']

import fire, json
from dotenv import find_dotenv, load_dotenv
from dataclasses import asdict
from .chains import get_chain
from .deposit import DepositQuote
from .pool import pool_type_label
from .withdraw import Withdrawal
from .helpers import ADDRESS_ZERO, normalize_address

def _addr(v):
    """Normalize an address (handles Fire's hex-int parsing of `0x...`). Refuses anything > 160 bits."""
    if v is None: return None
    if isinstance(v, int):
        if v.bit_length() > 160: raise SystemExit('address too large (looks like a private key); the SDK never accepts private keys')
        v = '0x' + format(v, '040x')
    return normalize_address(v)

def _require_token(c, ref, label='token'):
    """Resolve `ref` (address or symbol) to a Token via the chain context, raising SystemExit if missing."""
    t = c.get_token(ref)
    if t is None: raise SystemExit(f'{label} not found: {ref}')
    return t

def _new_pool_spec(c, token0, token1, pool_type, tick_spacing):
    t0, t1 = _require_token(c, token0, 'token0'), _require_token(c, token1, 'token1')
    pool_type = str(pool_type).lower()
    if pool_type == 'cl':
        if tick_spacing is None: raise SystemExit('--pool-type cl requires --tick-spacing N')
        return c.pool_spec(t0, t1, tick_spacing=int(tick_spacing))
    if pool_type in ('stable', 'volatile'):
        if tick_spacing is not None: raise SystemExit('--tick-spacing is CL-only')
        return c.pool_spec(t0, t1, stable=(pool_type == 'stable'))
    raise SystemExit(f'invalid --pool-type: {pool_type} (expected cl/stable/volatile)')

def _resolve_pool(c, *, pool=None, token0=None, token1=None, pool_type=None, tick_spacing=None):
    """--pool ADDR (existing) XOR (--token0 --token1 --pool-type [--tick-spacing]) (new). token0/token1 accept address or symbol."""
    pool = _addr(pool)
    if pool is not None:
        if any(x is not None for x in (token0, token1, pool_type, tick_spacing)):
            raise SystemExit('--pool cannot be combined with --token0/--token1/--pool-type/--tick-spacing')
        p = c.get_pool_by_address(pool)
        if p is None: raise SystemExit(f'pool {pool} not found')
        return p
    if not token0 or not token1 or not pool_type:
        raise SystemExit('new pool requires --token0, --token1, and --pool-type {cl,stable,volatile}')
    return _new_pool_spec(c, token0, token1, pool_type, tick_spacing)

def _one_side(a0, a1, ctx):
    """Return the `amount_tokenN` kwarg for whichever side is set, raising if both/neither."""
    if (a0 is None) == (a1 is None): raise SystemExit(f'{ctx} requires exactly one of --amount0 / --amount1')
    return {'amount_token0': a0} if a0 is not None else {'amount_token1': a1}

def _build_quote(c, p, *, amount0, amount1, price_lower, price_upper, tick_lower, tick_upper, initial_price, use_decimals=False):
    """Resolve a DepositQuote for either basic or CL, new or existing pool.

    Amounts default to raw wei (chainable with CLI output). Pass `use_decimals=True` to interpret
    `amount0`/`amount1` as decimal token units (e.g. `0.5` → `0.5 * 10^token.decimals`)."""
    is_new = p.lp == ADDRESS_ZERO
    def _amt(v, tok): return None if v is None else (tok.parse_units(float(v)) if use_decimals else int(v))
    a0, a1 = _amt(amount0, p.token0), _amt(amount1, p.token1)
    if p.is_cl:
        kwargs = _one_side(a0, a1, 'CL deposit')
        if is_new and initial_price is None: raise SystemExit('new CL pool requires --initial-price')
        if initial_price is not None: kwargs['initial_price'] = float(initial_price)
        if tick_lower is not None or tick_upper is not None:
            kwargs['tick_lower'], kwargs['tick_upper'] = tick_lower, tick_upper
        else:
            kwargs['price_lower'] = float(price_lower) if price_lower is not None else None
            kwargs['price_upper'] = float(price_upper) if price_upper is not None else None
        return c.quote_concentrated_deposit(p, **kwargs)
    if any(x is not None for x in (price_lower, price_upper, tick_lower, tick_upper, initial_price)):
        raise SystemExit('basic deposits do not accept CL flags')
    if is_new:
        if a0 is None or a1 is None: raise SystemExit('new basic pool requires both --amount0 and --amount1')
        return DepositQuote(pool=p, amount_token0=a0, amount_token1=a1)
    return c.quote_basic_deposit(p, **_one_side(a0, a1, 'existing basic pool deposit'))

def _position_dict(p):
    """Compact dict for CLI output: asdict + the pool flattened to identity + token metadata."""
    return {**asdict(p),
            'pool': {'symbol': p.pool.symbol, 'lp': p.pool.lp, 'is_cl': p.pool.is_cl,
                     'token0': {'symbol': p.pool.token0.symbol, 'decimals': p.pool.token0.decimals},
                     'token1': {'symbol': p.pool.token1.symbol, 'decimals': p.pool.token1.decimals}}}

def _resolve_quote(c, from_token, to_token, amount, use_decimals):
    """Resolve tokens, parse amount (wei or decimals), fetch a quote. Raises SystemExit on any missing piece."""
    ft, tt = _require_token(c, from_token, 'from-token'), _require_token(c, to_token, 'to-token')
    amt = ft.parse_units(float(amount)) if use_decimals else int(amount)
    q = c.get_quote(from_token=ft, to_token=tt, amount=amt)
    if q is None: raise SystemExit(f'no quote found for {ft.symbol} -> {tt.symbol}')
    return q

def _oracle_prices(c, from_token, to_token):
    """USD prices for from/to. Brackets with native+stable (oracle needs them). `(None, None)` on failure."""
    native, stable = c.get_token(c.settings.native_token_symbol), c.get_token(c.settings.stable_token_addr)
    tokens = list({t.token_address: t for t in [from_token, to_token, native, stable] if t}.values())
    try:
        m = {p.token.token_address: p.price for p in c.get_prices(tokens)}
        return m.get(from_token.token_address), m.get(to_token.token_address)
    except (KeyError, AttributeError): return None, None

def _route_intermediaries(c, q):
    """Hop outputs between from_token and to_token, exclusive. Empty for a direct swap."""
    if len(q.path) <= 1: return []
    out = []
    for pool, reversed_ in q.path[:-1]:
        addr = pool.token0_address if reversed_ else pool.token1_address
        t = c.get_token(addr)
        out.append({
            'symbol': t.symbol if t else None, 'address': addr,
            'lp': pool.lp, 'type_label': pool_type_label(pool.type),
        })
    return out

def _quote_dict(q, from_price_usd=None, to_price_usd=None, route=None):
    """Quote → JSON. `price_impact` sign: positive = pool worse than oracle."""
    ft, tt = q.from_token, q.to_token
    in_dec, out_dec = ft.to_float(q.amount_in), tt.to_float(q.amount_out)
    # impact = (oracle-expected out - actual out) / oracle-expected out; positive = cost to trader
    impact = None
    if from_price_usd and to_price_usd:
        est_out = in_dec * from_price_usd / to_price_usd
        impact = (est_out - out_dec) / est_out if est_out else None
    return {
        'from_token': {'symbol': ft.symbol, 'address': ft.token_address, 'decimals': ft.decimals},
        'to_token': {'symbol': tt.symbol, 'address': tt.token_address, 'decimals': tt.decimals},
        'amount_in': q.amount_in, 'amount_out': q.amount_out,
        'amount_in_decimal': in_dec, 'amount_out_decimal': out_dec,
        'price': out_dec / in_dec if in_dec else 0,
        'from_price_usd': from_price_usd, 'to_price_usd': to_price_usd,
        'price_impact': impact,
        'price_impact_pct': impact * 100 if impact is not None else None,
        'route': route or [],
    }

def _pool_dict(p, full: bool):
    """Compact = LiquidityPoolForSwap asdict + derived is_cl/is_stable/type_label (asdict strips @property).
    Full = LiquidityPool flattened (nested Token/Amount → primitives)."""
    if not full: return {**asdict(p), 'is_cl': p.is_cl, 'is_stable': p.is_stable, 'type_label': pool_type_label(p.type)}
    return {
        'chain_id': p.chain_id, 'chain_name': p.chain_name,
        'lp': p.lp, 'symbol': p.symbol, 'type': p.type, 'type_label': pool_type_label(p.type),
        'is_cl': p.is_cl, 'is_stable': p.is_stable, 'pool_fee': p.pool_fee, 'tvl': p.tvl,
        'token0': {'symbol': p.token0.symbol, 'address': p.token0.token_address, 'decimals': p.token0.decimals},
        'token1': {'symbol': p.token1.symbol, 'address': p.token1.token_address, 'decimals': p.token1.decimals},
        'reserve0': p.reserve0.as_float, 'reserve1': p.reserve1.as_float,
        'gauge': p.gauge, 'gauge_alive': p.gauge_alive,
        'weekly_emissions': p.weekly_emissions.as_float,
    }

def _find_position(c, *, pool=None, position=None):
    """Find a wallet position. CL: --position=NFT_ID. Basic: --pool=LP_ADDR. --position=0 needs --pool."""
    pool = _addr(pool)
    if pool is None and position is None:
        raise SystemExit('requires --pool (basic) or --position (CL)')
    tid = int(position) if position is not None else 0
    if tid == 0 and pool is None:
        raise SystemExit('--position=0 is ambiguous (every basic position has id=0); pass --pool too')
    match = next((p for p in c.get_positions() if p.id == tid and (pool is None or p.pool.lp.lower() == pool.lower())), None)
    if match is None: raise SystemExit('position not found')
    return match

class CLI:
    """Sugar SDK command-line interface.

    Always outputs JSON-shaped unsigned transactions. The SDK never signs.
    --wallet=0xADDRESS supplies the `from` field; sign + broadcast externally.

    Examples:
        # preview a basic deposit
        python -m sugar deposit --chain=1135 --wallet=0xYou --pool=0x... --amount1=0.001

        # list wallet positions
        python -m sugar positions --chain=1135 --wallet=0xYou

        # withdraw 50% of a basic position
        python -m sugar withdraw --chain=1135 --wallet=0xYou --pool=0x... --fraction=0.5"""

    def deposit(self, *, chain: int, wallet: str, pool: str = None,
                token0: str = None, token1: str = None, pool_type: str = None, tick_spacing=None,
                amount0=None, amount1=None,
                price_lower=None, price_upper=None, tick_lower=None, tick_upper=None,
                initial_price=None, slippage: float = 0.01, deadline_minutes: float = 30,
                use_decimals: bool = False):
        """Deposit liquidity. Returns unsigned tx(s); sign + broadcast externally.

        Pool: target an existing pool with --pool=0xLP, or a new/derived pool with
        --token0 --token1 --pool-type {cl,stable,volatile} (CL also needs --tick-spacing). The two
        modes are mutually exclusive.

        Basic pools: pass --amount0 and/or --amount1 (a brand-new basic pool needs both); CL-only
        flags (--price-*, --tick-*, --initial-price) are rejected.
        CL pools: pass exactly one of --amount0/--amount1, plus a range as --price-lower/--price-upper
        or --tick-lower/--tick-upper; a new/uninitialized CL pool also needs --initial-price.

        Amounts (--amount0, --amount1) default to raw wei — pipes back into other sugar calls.
        Pass --use-decimals to interpret amounts as token units (e.g. `--amount0=0.5 --use-decimals`)."""
        with get_chain(str(chain), signer_address=_addr(wallet)) as c:
            p = _resolve_pool(c, pool=pool, token0=token0, token1=token1,
                              pool_type=pool_type, tick_spacing=tick_spacing)
            q = _build_quote(c, p, amount0=amount0, amount1=amount1,
                             price_lower=price_lower, price_upper=price_upper,
                             tick_lower=tick_lower, tick_upper=tick_upper,
                             initial_price=initial_price, use_decimals=use_decimals)
            return c.deposit(q, delay_in_minutes=deadline_minutes, slippage=slippage)

    def positions(self, *, chain: int, wallet: str = None, owner: str = None):
        """List positions for --owner (defaults to --wallet). One of --wallet/--owner is required."""
        target = _addr(owner) or _addr(wallet)
        if target is None: raise SystemExit('positions requires --wallet or --owner')
        with get_chain(str(chain), signer_address=target) as c:
            return [_position_dict(p) for p in c.get_positions()]

    def pools(self, *, chain: int, token0: str = None, token1: str = None,
              pool_type: str = None, full: bool = False, limit: int = None):
        """List pools on `--chain`. Compact view by default; --full adds TVL/reserves/fees/gauge/emissions (slower).
        Filter by --token0 / --token1 (symbol or 0x address; when both given, pools must contain both,
        order-independent) and --pool-type (cl|stable|volatile). --limit caps result count."""
        type_preds = {'cl': lambda t: t > 0, 'stable': lambda t: t == 0, 'volatile': lambda t: t == -1}
        if pool_type is not None and pool_type not in type_preds:
            raise SystemExit(f'invalid --pool-type: {pool_type} (expected cl/stable/volatile)')
        type_match = type_preds[pool_type] if pool_type else (lambda _t: True)
        with get_chain(str(chain)) as c:
            def _resolve(ref):
                if ref is None: return None
                t = c.get_token(ref)
                if t is None: raise SystemExit(f'token not found: {ref}')
                return t.token_address.lower()
            wanted = {a for a in (_resolve(token0), _resolve(token1)) if a}
            pools = c.get_pools() if full else c.get_pools_for_swaps()
            addrs = ((lambda p: {p.token0.token_address.lower(), p.token1.token_address.lower()}) if full
                     else (lambda p: {p.token0_address.lower(), p.token1_address.lower()}))
            out = [p for p in pools if wanted.issubset(addrs(p)) and type_match(p.type)]
            if limit is not None: out = out[:limit]
            return [_pool_dict(p, full) for p in out]

    def withdraw(self, *, chain: int, wallet: str, pool: str = None, position: int = None,
                 fraction: float = 1.0, burn: bool = False, collect: bool = True,
                 unwrap_native: bool = False, slippage: float = 0.01,
                 deadline_minutes: float = 30):
        """Withdraw a position. Identify by --pool (basic) or --position (CL). --fraction defaults to
        1.0 (100%). --burn removes the drained position; --collect (default true) also collects owed
        fees; --unwrap-native returns native ETH instead of WETH."""
        with get_chain(str(chain), signer_address=_addr(wallet)) as c:
            p = _find_position(c, pool=pool, position=position)
            w = Withdrawal.from_position(p, fraction=float(fraction), burn=burn)
            return c.withdraw(w, delay_in_minutes=deadline_minutes, slippage=slippage,
                              collect=collect, unwrap_native=unwrap_native)

    def stake(self, *, chain: int, wallet: str, pool: str = None, position: int = None):
        """Stake an unstaked position into the pool's gauge."""
        with get_chain(str(chain), signer_address=_addr(wallet)) as c:
            return c.stake(_find_position(c, pool=pool, position=position))

    def unstake(self, *, chain: int, wallet: str, pool: str = None, position: int = None,
                amount: int = None):
        """Unstake from the pool's gauge. CL: full only. Basic: pass --amount (raw wei) for a partial unstake."""
        with get_chain(str(chain), signer_address=_addr(wallet)) as c:
            return c.unstake(_find_position(c, pool=pool, position=position), amount=amount)

    def claim_emissions(self, *, chain: int, wallet: str, pool: str = None, position: int = None):
        """Claim gauge emissions for a staked position."""
        with get_chain(str(chain), signer_address=_addr(wallet)) as c:
            return c.claim_emissions(_find_position(c, pool=pool, position=position))

    def claim_fees(self, *, chain: int, wallet: str, pool: str = None, position: int = None,
                   burn: bool = False, unwrap_native: bool = False):
        """Claim LP fees. CL: NFPM multicall (collect + optional --unwrap-native/--burn). Basic: pool.claimFees().
        A staked position must be unstaked before its fees can be claimed."""
        with get_chain(str(chain), signer_address=_addr(wallet)) as c:
            return c.claim_fees(_find_position(c, pool=pool, position=position),
                                burn=burn, unwrap_native=unwrap_native)

    def quote(self, *, chain: int, from_token: str, to_token: str, amount, use_decimals: bool = False):
        """Quote a swap (read-only — no wallet required). Returns from/to tokens, amount_in/out
        (raw wei + decimal), derived effective price, oracle spot prices, price impact vs oracle
        (positive = pool worse than oracle), and route intermediaries. Same token/amount semantics
        as `swap`: --from-token / --to-token accept address or symbol; --amount defaults to raw wei
        (pass --use-decimals to interpret as token units)."""
        with get_chain(str(chain)) as c:
            q = _resolve_quote(c, from_token, to_token, amount, use_decimals)
            from_price, to_price = _oracle_prices(c, q.from_token, q.to_token)
            return _quote_dict(q, from_price_usd=from_price, to_price_usd=to_price, route=_route_intermediaries(c, q))

    def swap(self, *, chain: int, wallet: str, from_token: str, to_token: str, amount,
             slippage: float = None, use_decimals: bool = False):
        """Swap `from_token` → `to_token` for `amount`. Returns `[approve_tx, swap_tx]` (approval omitted for native or sufficient allowance).

        --from-token / --to-token accept either a 0x address or a symbol (e.g. ETH, LSK).
        --amount defaults to raw wei; pass --use-decimals to interpret as token units."""
        with get_chain(str(chain), signer_address=_addr(wallet)) as c:
            return c.swap_from_quote(_resolve_quote(c, from_token, to_token, amount, use_decimals), slippage=slippage)

def main():
    load_dotenv(find_dotenv(usecwd=True))
    fire.Fire(CLI, name='sugar', serialize=lambda x: json.dumps(x, indent=2, default=str))
