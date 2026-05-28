__all__ = ['original_format_batched_response', 'T', 'safe_format_batched_response', 'require_context', 'require_async_context',
           'CommonChain', 'AsyncChain', 'Chain', 'OPChainCommon', 'AsyncOPChain', 'OPChain', 'BaseChainCommon',
           'AsyncBaseChain', 'BaseChain', 'LiskChainCommon', 'AsyncLiskChain', 'LiskChain', 'UniChainCommon',
           'AsyncUniChain', 'UniChain', 'LiskChainSimnet', 'AsyncLiskChainSimnet',
           'AsyncUniChainSimnet', 'UniChainSimnet',
           'ModeChainCommon', 'AsyncModeChain', 'ModeChain',
           'FraxtalChainCommon', 'AsyncFraxtalChain', 'FraxtalChain',
           'InkChainCommon', 'AsyncInkChain', 'InkChain',
           'SoneiumChainCommon', 'AsyncSoneiumChain', 'SoneiumChain',
           'SuperseedChainCommon', 'AsyncSuperseedChain', 'SuperseedChain',
           'CeloChainCommon', 'AsyncCeloChain', 'CeloChain',
           'get_chain', 'get_async_chain',
           'get_simnet_chain', 'get_async_simnet_chain', 'get_chain_from_token', 'get_async_chain_from_token',
           'get_simnet_chain_from_token', 'get_async_simnet_chain_from_token']

import asyncio
from concurrent.futures import ThreadPoolExecutor, as_completed
from functools import wraps, lru_cache
from async_lru import alru_cache
from cachetools import cached, TTLCache
from typing import List, TypeVar, Callable, Optional, Tuple, Dict
from web3 import Web3, HTTPProvider, AsyncWeb3, AsyncHTTPProvider
from web3.eth.async_eth import AsyncContract
from web3.eth import Contract
from web3.manager import RequestManager, RequestBatcher
from .config import ChainSettings, make_op_chain_settings, make_base_chain_settings, make_uni_chain_settings, make_lisk_chain_settings
from .config import make_mode_chain_settings, make_fraxtal_chain_settings, make_ink_chain_settings
from .config import make_soneium_chain_settings, make_superseed_chain_settings, make_celo_chain_settings
from .config import XCHAIN_GAS_LIMIT_UPPERBOUND
from .helpers import normalize_address, MAX_UINT128, apply_slippage, get_future_timestamp, ADDRESS_ZERO, chunk, Pair
from .helpers import find_all_paths, to_bytes32, price_to_tick, nearest_tick, sqrt_ratio_x96_from_price
from .abi import get_abi
from .token import Token
from .pool import LiquidityPool, LiquidityPoolForSwap, LiquidityPoolEpoch
from .position import Position
from .withdraw import Withdrawal
from .price import Price
from .deposit import DepositQuote
from .quote import QuoteInput, Quote
from .swap import setup_planner

# monkey patching how web3 handles errors in batched requests
# re: https://github.com/ethereum/web3.py/issues/3657
original_format_batched_response = RequestManager._format_batched_response
def safe_format_batched_response(*args):
    try: return original_format_batched_response(*args)
    except Exception as e: return e
RequestManager._format_batched_response = safe_format_batched_response

T = TypeVar('T')

def require_context(f: Callable[..., T]) -> Callable[..., T]:
    @wraps(f)
    def wrapper(self: 'CommonChain', *args, **kwargs) -> T:
        if not self._in_context: raise RuntimeError("Chain methods can only be accessed within 'async with' block")
        return f(self, *args, **kwargs)
    return wrapper

def require_async_context(f: Callable[..., T]) -> Callable[..., T]:
    @wraps(f)
    async def wrapper(self: 'CommonChain', *args, **kwargs) -> T:
        if not self._in_context: raise RuntimeError("Chain methods can only be accessed within 'async with' block")
        return await f(self, *args, **kwargs)
    return wrapper

class CommonChain:
    is_simnet: bool = False  # simnet subclasses override to True; Superswap reads this to pick the simnet factory for read-side contexts

    @property
    def chain_id(self) -> str: return self.settings.chain_id

    @property
    def name(self) -> str: return self.settings.chain_name

    pools: Optional[List[LiquidityPool]] = None
    pools_for_swap: Optional[List[LiquidityPoolForSwap]] = None

    def __init__(self, settings: ChainSettings, **kwargs):
        self.settings, self._in_context = settings, False
        sa = kwargs.get("signer_address")
        self.signer_address: str = normalize_address(sa) if sa else ""

        if "pools" in kwargs: self.pools = kwargs["pools"]
        if "pools_for_swap" in kwargs: self.pools_for_swap = kwargs["pools_for_swap"] 
    
    def prepare_set_token_allowance_contract(self, token: Token, contract_wrapper):
        return contract_wrapper(address=token.wrapped_token_address or token.token_address, abi=get_abi("erc20"))

    @require_context
    def build_tx(self, tx, value: int = 0):
        """Return an unsigned tx dict (`{from, to, data, value}`). SDK never signs or broadcasts."""
        if not self.signer_address: raise ValueError("build_tx requires signer_address (pass to Chain constructor)")
        return {"from": self.signer_address, "to": tx.address, "data": tx._encode_transaction_data(), "value": value}

    @require_context
    def _nfpm(self, pool):
        """Return the NFPM contract for `pool`, raising if the pool has no NFPM address."""
        if not pool.nfpm or pool.nfpm == ADDRESS_ZERO: raise ValueError(f"pool {pool.symbol} has no NFPM address")
        return self.web3.eth.contract(address=normalize_address(pool.nfpm), abi=get_abi("nfpm"))

    def _build_nfpm_cleanup_calls(self, nfpm, pool, position_id, *, unwrap_native: bool, burn: bool):
        """NFPM multicall payload: collect → optional (unwrapWETH9 + sweepToken) → optional burn."""
        native = self.settings.wrapped_native_token_addr
        if unwrap_native and pool.token0.token_address != native and pool.token1.token_address != native:
            raise ValueError("unwrap_native: pool has no native leg")
        recipient = ADDRESS_ZERO if unwrap_native else self.signer_address
        calls = [nfpm.encode_abi("collect", args=[(position_id, recipient, MAX_UINT128, MAX_UINT128)])]
        if unwrap_native:
            other = pool.token1.token_address if pool.token0.token_address == native else pool.token0.token_address
            calls.append(nfpm.encode_abi("unwrapWETH9", args=[0, self.signer_address]))
            calls.append(nfpm.encode_abi("sweepToken", args=[other, 0, self.signer_address]))
        if burn: calls.append(nfpm.encode_abi("burn", args=[position_id]))
        return calls
    
    def prepare_tokens(self, tokens: List[Tuple], listed_only: bool) -> List[Token]:
        native = Token.make_native_token(self.settings.native_token_symbol,
                                         self.settings.wrapped_native_token_addr,
                                         self.settings.native_token_decimals,
                                         chain_id=self.chain_id,
                                         chain_name=self.name)
        ts = list(map(lambda t: Token.from_tuple(t, chain_id=self.chain_id, chain_name=self.name), tokens))
        return [native] + (list(filter(lambda t: t.listed, ts)) if listed_only else ts)
    
    def find_token_by_address(self, tokens: List[Token], address: str) -> Optional[Token]:
        address = normalize_address(address)
        return next((t for t in tokens if t.token_address == address), None)

    def _get_bridge_token(self, tokens: List[Token]) -> Token:
        connector = next((t for t in tokens if t.token_address == self.settings.bridge_token_addr), None)
        if not connector: raise ValueError(f"Superswap bridge token not found on {self.name} chain.")
        return connector

    def _prepare_prices(self, tokens: List[Token], rates: List[int]) -> Dict[str, int]:
        # token_address => normalized rate
        result = {}
        # rates are returned multiplied by eth decimals + the difference in decimals to eth
        # we want them all normalized to 18 decimals
        for cnt, rate in enumerate(rates):
            t, eth_decimals = tokens[cnt], self.settings.native_token_decimals
            if t.decimals == eth_decimals: nr = rate
            elif t.decimals < eth_decimals: nr = rate // (10 ** (eth_decimals - t.decimals))
            else: nr = rate * (10 ** (t.decimals - eth_decimals))
            result[t.token_address] = nr
        return result

    def prepare_prices(self, tokens: List[Token], prices: List[int]) -> List[Price]:
        """Get prices for tokens in target stable token"""
        eth_decimals = self.settings.native_token_decimals
        # all rates in EHT: token => rate
        rates_in_eth = self._prepare_prices(tokens, prices)
        eth_rate, usd_rate = rates_in_eth[self.settings.native_token_symbol], rates_in_eth[self.settings.stable_token_addr]
        # this gives us the price of 1 eth in usd with 18 decimals precision
        eth_usd_price = (eth_rate * 10 ** eth_decimals) // usd_rate
        # finally convert to prices in terms of stable
        return [Price(token=t, price=(rates_in_eth[t.token_address] * eth_usd_price // 10 ** eth_decimals) / 10 ** eth_decimals) for t in tokens]
    
    def prepare_pools(self, pools: List[Tuple], tokens: List[Token], prices: List[Price]) -> List[LiquidityPool]:
        tokens, prices = {t.token_address: t for t in tokens}, {price.token.token_address: price for price in prices}
        return list(filter(lambda p: p is not None, map(lambda p: LiquidityPool.from_tuple(p, tokens, prices, chain_id=self.chain_id, chain_name=self.name), pools)))
    
    def prepare_pools_for_swap(self, pools: List[Tuple]) -> List[LiquidityPoolForSwap]:
        return list(map(lambda p: LiquidityPoolForSwap.from_tuple(p, chain_id=self.chain_id, chain_name=self.name), pools))

    def prepare_pool_epochs(self, epochs: List[Tuple], pools: List[LiquidityPool], tokens: List[Token], prices: List[Price]) -> List[LiquidityPoolEpoch]:
        tokens, prices, pools = {t.token_address: t for t in tokens}, {price.token.token_address: price for price in prices}, {p.lp: p for p in pools}
        return list(map(lambda p: LiquidityPoolEpoch.from_tuple(p, pools, tokens, prices), epochs))

    def prepare_positions(self, raw: List[Tuple], pools: List[LiquidityPool]) -> List[Position]:
        pools_d = {p.lp: p for p in pools}
        return list(filter(None, [Position.from_tuple(p, pools_d, self.chain_id, self.name) for p in raw]))
    
    def filter_pools_for_swap(self, pools: List[LiquidityPoolForSwap], from_token: Token, to_token: Token) -> List[LiquidityPoolForSwap]:
        match_tokens = set(self.settings.connector_tokens_addrs + [from_token.token_address, to_token.token_address])
        return list(filter(lambda p: p.token0_address in match_tokens or p.token1_address in match_tokens, pools))
    
    def paths_to_pools(self, pools: List[LiquidityPoolForSwap], paths: List[List[Tuple]]) -> List[LiquidityPoolForSwap]:
        pools_dict = {p.lp: p for p in pools}
        return [list(map(lambda p: pools_dict[p[2]], path)) for path in paths]

    def prepare_quote_batch(self, from_token: Token, to_token: Token, batcher: RequestBatcher, pools: List[List[LiquidityPoolForSwap]], amount_in: int, paths: List[List[Tuple]]):
        inputs = []
        for i, path in enumerate(paths):
            p = [(p, p.token0_address != path[i][0]) for i, p in enumerate(pools[i])]
            q = QuoteInput(from_token=from_token, to_token=to_token, amount_in=amount_in, path=p,
                           slipstream_factory_addr=self.settings.slipstream_factory_addr,
                           old_slipstream_factory_addr=self.settings.old_slipstream_factory_addr)
            batcher.add(self.quoter.functions.quoteExactInput(q.route.encoded, amount_in))
            inputs.append(q)
        return batcher, inputs

    def prepare_quotes(self, quote_inputs: List[QuoteInput], responses):
        if len(responses) != len(quote_inputs): raise ValueError(f"Number of responses {len(responses)} does not match number of quote inputs {len(quote_inputs)}")
        quotes = []
        for i, r in enumerate(responses):
            if isinstance(r, Exception): continue
            else: quotes.append(Quote(input=quote_inputs[i], amount_out=r[0]))
        return quotes
    
    def get_paths_for_quote(self, from_token: Token, to_token: Token, pools: List[LiquidityPoolForSwap], exclude_tokens: List[str]) -> List[List[Tuple]]:
        exclude_tokens_set = set(map(lambda t: normalize_address(t), exclude_tokens))

        if from_token.token_address in exclude_tokens: exclude_tokens_set.remove(from_token.token_address)
        if to_token.token_address in exclude_tokens: exclude_tokens_set.remove(to_token.token_address)

        pairs = [Pair(p.token0_address, p.token1_address, p.lp) for p in pools]
        paths = find_all_paths(pairs, from_token.wrapped_token_address or from_token.token_address, to_token.wrapped_token_address or to_token.token_address)
        # filter out paths with excluded tokens
        return list(filter(lambda p: len(set(map(lambda t: t[0], p)) & exclude_tokens_set) == 0, paths))

    def calculate_optimal_batch_size(self, pool_count: int) -> int:
        """Per-batch page size targeting ~target_calls reads, clamped to [min, max]."""
        target_calls = self.settings.pool_pagination_target_calls
        min_size, max_size = self.settings.pool_pagination_min_size, self.settings.pool_pagination_max_size
        return max(min_size, min(pool_count // target_calls, max_size))

    def get_pool_paginator(self, pool_count: int, batch_size: int = 5) -> List[List[Tuple]]:
        upper_bound, limit = pool_count + 10, self.calculate_optimal_batch_size(pool_count)
        return chunk(list(map(lambda x: (x, limit), list(range(0, upper_bound, limit)))), batch_size)

    def get_price_connectors(self) -> List[str]:
        """Oracle routing tokens + stable (so stable-paired tokens still resolve)."""
        return list(dict.fromkeys(self.settings.connector_tokens_addrs + [self.settings.stable_token_addr]))

    def get_price_request_tokens(self, tokens: List[Token]) -> List[Token]:
        """Native/listed/emerging tokens only, deduped by address."""
        return list({t.token_address: t for t in tokens if t.is_native or t.listed or t.emerging}.values())

    def get_latest_epoch_price_tokens(self, epochs: List[Tuple], raw_pools: List[Tuple], tokens: List[Token]) -> List[Token]:
        """Tokens the latest-epoch view prices: stable, native, per-pool token0/1/emissions, per-reward."""
        tokens_by_address = {t.token_address: t for t in tokens}
        needed = {self.settings.stable_token_addr}
        native = next((t for t in tokens if t.is_native), None)
        if native is not None: needed.add(native.token_address)
        for pool in raw_pools:
            needed.update([normalize_address(pool[7]), normalize_address(pool[10]), normalize_address(pool[20])])
        for epoch in epochs:
            needed.update(normalize_address(addr) for addr, _ in epoch[4])
            needed.update(normalize_address(addr) for addr, _ in epoch[5])
        return [t for addr, t in tokens_by_address.items()
                if addr in needed and (t.is_native or t.listed or t.emerging)]

    def prepare_price_batcher(self, tokens: List[Token], batch: RequestBatcher):
        batches = chunk(tokens, self.settings.price_batch_size)
        for b in batches:
            batch.add(self.prices.functions.getManyRatesToEthWithCustomConnectors(
                list(map(lambda t: t.wrapped_token_address or t.token_address, b)),
                False, # use wrappers
                self.settings.connector_tokens_addrs,
                10 # threshold_filter
            ))
        return batch

class AsyncChain(CommonChain):
    web3: AsyncWeb3
    sugar: AsyncContract
    slipstream: AsyncContract
    router: AsyncContract
    prices: AsyncContract
    quoter: AsyncContract
    swapper: AsyncContract

    async def __aenter__(self):
        """Async context manager entry"""
        self._in_context = True
        self.web3 = AsyncWeb3(AsyncHTTPProvider(self.settings.rpc_uri))
        self.sugar = self.web3.eth.contract(address=self.settings.sugar_contract_addr, abi=get_abi("sugar"))
        self.sugar_rewards = self.web3.eth.contract(address=self.settings.sugar_rewards_contract_addr, abi=get_abi("sugar_rewards"))
        self.slipstream = self.web3.eth.contract(address=self.settings.slipstream_contract_addr, abi=get_abi("slipstream"))
        self.prices = self.web3.eth.contract(address=self.settings.price_oracle_contract_addr, abi=get_abi("price_oracle"))
        self.router = self.web3.eth.contract(address=self.settings.router_contract_addr, abi=get_abi("router"))
        self.quoter = self.web3.eth.contract(address=self.settings.quoter_contract_addr, abi=get_abi("quoter"))
        self.swapper = self.web3.eth.contract(address=self.settings.swapper_contract_addr, abi=get_abi("swapper"))
        if hasattr(self.settings, "interchain_router_contract_addr"):
            # TODO: clean this up when interchain jazz is fully implemented
            self.ica_router = self.web3.eth.contract(address=self.settings.interchain_router_contract_addr, abi=get_abi("interchain_router"))

        # set up caching for price oracle
        self._get_prices = alru_cache(ttl=self.settings.pricing_cache_timeout_seconds)(self._get_prices)

        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        self._in_context = False
        await self.web3.provider.disconnect()
        return None

    async def apaginate(self, f: Callable):
        pool_count = await self.get_pool_count()
        async def process_batch(batch: List[Tuple]):
            async with self.web3.batch_requests() as batcher:
                for offset, limit in batch: batcher.add(f(limit, offset))
                return sum(await batcher.async_execute(), [])
        return sum(await asyncio.gather(*[process_batch(batch) for batch in self.get_pool_paginator(pool_count)]), [])

    @require_async_context
    @alru_cache(maxsize=None)
    async def get_pool_count(self) -> int:
        """Pool count, cached per chain instance."""
        return await self.sugar.functions.count().call()

    @require_async_context
    async def get_bridge_fee(self, domain: int) -> int:
        contract = self.web3.eth.contract(address=self.settings.bridge_contract_addr, abi=get_abi("bridge_get_fee"))
        return await contract.functions.quoteGasPayment(domain).call()

    @require_async_context
    async def _internal_bridge_token(self, from_token: Token, destination_token: Token, amount: int, domain: int):
        # XX: marking this API as "internal" for now
        # TODO: remove destination_domain when get domain API stabilizes and use destination_token instead
        c = self.web3.eth.contract(address=self.settings.bridge_contract_addr, abi=get_abi("bridge_transfer_remote"))
        approval_tx = await self.set_token_allowance(from_token, self.settings.bridge_contract_addr, amount)
        transfer_tx = self.build_tx(c.functions.transferRemote(domain, to_bytes32(self.signer_address), amount), value=await self.get_bridge_fee(domain))
        return [t for t in (approval_tx, transfer_tx) if t is not None]
    
    @require_async_context
    async def get_xchain_fee(self, destination_domain: int) -> int:
        return await self.ica_router.functions.quoteGasForCommitReveal(destination_domain, XCHAIN_GAS_LIMIT_UPPERBOUND).call()

    @require_async_context
    async def get_remote_interchain_account(self, destination_domain: int):
        abi = [{
            "name": "getRemoteInterchainAccount",
            "type": "function",
            "stateMutability": "view",
            "inputs": [
                {
                    "name": "",
                    "type": "uint32"
                },
                {
                    "name": "",
                    "type": "address"
                },
                {
                    "name": "",
                    "type": "bytes32"
                }
            ],
            "outputs": [
                {
                "name": "userICA",
                "type": "address"
                }
            ]
        }]
        contract = self.web3.eth.contract(address=self.settings.interchain_router_contract_addr, abi=abi)
        return await contract.functions.getRemoteInterchainAccount(
            destination_domain,
            self.settings.swapper_contract_addr,
            to_bytes32(self.signer_address),
        ).call()

    @require_async_context
    async def balance_of(self, token_address: str, owner_address: str) -> int:
        """Get token balance for given owner"""
        token_contract = self.web3.eth.contract(address=token_address, abi=get_abi("erc20"))
        return await token_contract.functions.balanceOf(owner_address).call()

    @require_async_context
    async def get_ica_hook(self): return await self.ica_router.functions.hook().call()

    @require_async_context
    async def get_user_ica_balance(self, user_ica: str) -> int: 
        return await self.balance_of(token_address=self.settings.bridge_token_addr, owner_address=user_ica)

    @require_async_context
    @alru_cache(maxsize=None)
    async def get_all_tokens(self, listed_only: bool = False) -> List[Token]:
        def get_tokens(limit, offset): return self.sugar.functions.tokens(limit, offset, ADDRESS_ZERO, [])
        return self.prepare_tokens(await self.apaginate(get_tokens), listed_only)
    
    @require_async_context
    async def get_token(self, ref) -> Optional[Token]:
        """Resolve a token by 0x address, symbol (case-insensitive), or int (hex address as integer). Returns None if not found."""
        if not ref: return None
        if isinstance(ref, int): ref = '0x' + format(ref, '040x')
        tokens = await self.get_all_tokens()
        if ref.startswith("0x"): return self.find_token_by_address(tokens, ref)
        return next((t for t in tokens if t.symbol.lower() == ref.lower()), None)
    
    @require_async_context
    async def get_pool_by_address(self, address: str) -> Optional[LiquidityPool]:
        """Find a pool by LP address (case-insensitive). Returns None if not found."""
        return next((p for p in await self.get_pools() if p.lp.lower() == address.lower()), None)

    @require_async_context
    async def get_token_balance(self, token: Token, owner_address: Optional[str] = None) -> int:
        # TODO: consider moving to native token wording just like velo app does
        owner_address = owner_address or self.signer_address
        if not owner_address: raise ValueError("Owner address is required to get token balance")
        if token.wrapped_token_address: return await self.web3.eth.get_balance(owner_address)
        return await self.balance_of(token_address=token.token_address, owner_address=owner_address)

    @require_async_context
    async def get_bridge_token(self) -> Token: return self._get_bridge_token(await self.get_all_tokens())

    async def _get_prices(self, tokens: Tuple[Token], max_retries: int = 3) -> List[int]:
        """Batched oracle reads, filtered to priceable tokens. Result is mapped back to input order (filtered tokens get 0)."""
        request_tokens = self.get_price_request_tokens(list(tokens))
        chunks = list(chunk(request_tokens, self.settings.price_batch_size))
        async def _exec(cs):
            async with self.web3.batch_requests() as b:
                for c in cs:
                    b.add(self.prices.functions.getManyRatesToEthWithCustomConnectors(
                        [t.wrapped_token_address or t.token_address for t in c],
                        False, self.get_price_connectors(), self.settings.price_threshold_filter))
                return await b.async_execute()
        results = await _exec(chunks) if chunks else []
        for _ in range(max_retries):
            failed = [i for i, r in enumerate(results) if not isinstance(r, list)]
            if not failed: break
            retry = await _exec([chunks[i] for i in failed])
            for j, i in enumerate(failed): results[i] = retry[j]
        bad = [(i, r) for i, r in enumerate(results) if not isinstance(r, list)]
        if bad:
            i, e = bad[0]
            raise RuntimeError(f"price oracle batch failed: {len(bad)}/{len(results)} chunks unresolved after {max_retries} retries (chunk #{i}: {type(e).__name__}: {e})")
        rates = {t.token_address: r for c, rs in zip(chunks, results) for t, r in zip(c, rs)}
        return [rates.get(t.token_address, 0) for t in tokens]

    @require_async_context
    async def get_prices(self, tokens: List[Token]) -> List[Price]:
        """Get prices for tokens in target stable token"""
        return self.prepare_prices(tokens, await self._get_prices(tuple(tokens)))

    @alru_cache(maxsize=None)
    async def get_raw_pools(self, for_swaps: bool):
        def get_all(limit, offset): return self.sugar.functions.all(limit, offset, 0)
        return await self.apaginate(self.sugar.functions.forSwaps if for_swaps else get_all)
    
    @require_async_context
    async def get_pools(self, for_swaps: bool = False) -> List[LiquidityPool]:
        pools = await self.get_raw_pools(for_swaps)
        if not for_swaps:
            tokens = await self.get_all_tokens()
            return self.prepare_pools(pools, tokens, await self.get_prices(tokens))
        else: return self.prepare_pools_for_swap(pools)

    @require_async_context
    @alru_cache(maxsize=None)
    async def get_pool_epochs(self, lp: str, offset: int = 0, limit: int = 10) -> List[LiquidityPoolEpoch]:
        tokens, pools = await self.get_all_tokens(listed_only=False), await self.get_pools()
        prices = await self.get_prices(tokens)
        r = await self.sugar_rewards.functions.epochsByAddress(limit, offset, normalize_address(lp)).call()
        return self.prepare_pool_epochs(r, pools, tokens, prices)

    @require_async_context
    @alru_cache(maxsize=None)
    async def get_latest_pool_epochs(self) -> List[LiquidityPoolEpoch]:
        raw_epochs = await self.apaginate(self.sugar_rewards.functions.epochsLatest)
        if not raw_epochs: return []
        tokens = await self.get_all_tokens(listed_only=False)
        epoch_lp_addresses = {normalize_address(epoch[1]) for epoch in raw_epochs}
        raw_pools = [p for p in await self.get_raw_pools(False) if normalize_address(p[0]) in epoch_lp_addresses]
        prices = await self.get_prices(self.get_latest_epoch_price_tokens(raw_epochs, raw_pools, tokens))
        pools = self.prepare_pools(raw_pools, tokens, prices)
        return self.prepare_pool_epochs(raw_epochs, pools, tokens, prices)
    
    @require_async_context
    async def get_pools_for_swaps(self) -> List[LiquidityPoolForSwap]: return await self.get_pools(for_swaps=True)

    @require_async_context
    async def _get_quotes_for_paths(self, from_token: Token, to_token: Token, amount_in: int, pools: List[LiquidityPoolForSwap], paths: List[List[Tuple]]) -> List[Optional[Quote]]:
        path_pools = self.paths_to_pools(pools, paths)
        async with self.web3.batch_requests() as batch:
            batch, inputs = self.prepare_quote_batch(from_token, to_token, batch, path_pools, amount_in, paths)
            return self.prepare_quotes(inputs, await batch.async_execute())

    @require_async_context
    async def get_quote(self, from_token: Token, to_token: Token, amount: int, filter_quotes: Optional[Callable[[Quote], bool]] = None) -> Optional[Quote]:
        pools = self.filter_pools_for_swap(from_token=from_token, to_token=to_token, pools=await self.get_pools_for_swaps())
        paths = self.get_paths_for_quote(from_token, to_token, pools, self.settings.excluded_tokens_addrs)
        quotes = sum(await asyncio.gather(*[self._get_quotes_for_paths(from_token, to_token, amount, pools, paths) for paths in chunk(paths, 500)]), [])
        quotes = list(filter(lambda q: q is not None, quotes))
        if filter_quotes is not None: quotes = list(filter(filter_quotes, quotes))
        return max(quotes, key=lambda q: q.amount_out) if len(quotes) > 0 else None
    
    @require_async_context
    async def swap(self, from_token: Token, to_token: Token, amount: int, slippage: Optional[float] = None):
        q = await self.get_quote(from_token, to_token, amount=amount)
        if not q: raise ValueError("No quotes found")
        return await self.swap_from_quote(q, slippage=slippage)
        
    @require_async_context
    async def swap_from_quote(self, quote: Quote, slippage: Optional[float] = None):
        """Build txs for a swap. Pools always route WETH, so the input side has two shapes:
        - **Native (ETH)**: amount goes as `msg.value`; the swapper wraps to WETH internally. No approval.
        - **WETH / ERC20**: requires the swapper to have an ERC20 allowance for `amount_in`; `value=0`.

        Returns `[approve_tx, swap_tx]` for ERC20 input, or `[swap_tx]` for native (or when allowance already covers `amount_in`)."""
        swapper, from_token = self.settings.swapper_contract_addr, quote.from_token
        slippage = slippage if slippage is not None else self.settings.swap_slippage
        planner = setup_planner(quote=quote, slippage=slippage, account=self.signer_address, router_address=swapper,
                                slipstream_factory_addr=self.settings.slipstream_factory_addr,
                                old_slipstream_factory_addr=self.settings.old_slipstream_factory_addr)
        execute = self.swapper.functions.execute(planner.commands, planner.inputs)
        if from_token.wrapped_token_address:  # native: swapper wraps msg.value to WETH
            return [await self.build_tx(execute, value=quote.input.amount_in)]
        # ERC20 (incl. WETH): approve the wrapped token to the swapper, then execute with value=0
        approval_tx = await self.set_token_allowance(from_token, swapper, quote.input.amount_in)
        main = await self.build_tx(execute)
        return [t for t in (approval_tx, main) if t is not None]

    @require_async_context
    async def _approve_if_needed(self, erc20, spender: str, amount: int):
        """Approve `spender` for `amount` on `erc20` if current allowance < amount. Returns None when already sufficient."""
        if (await erc20.functions.allowance(self.signer_address, spender).call()) >= amount: return None
        return self.build_tx(erc20.functions.approve(spender, amount))

    @require_async_context
    async def _collect_approvals(self, pool, target_addr, a0, a1):
        """Set ERC20 allowances for non-native legs of `pool` to `target_addr`. Returns (txs, is_native0, is_native1)."""
        native = self.settings.wrapped_native_token_addr
        is_native0 = pool.token0.token_address == native
        is_native1 = pool.token1.token_address == native
        txs = []
        if not is_native0:
            tx = await self.set_token_allowance(pool.token0, target_addr, a0)
            if tx is not None: txs.append(tx)
        if not is_native1:
            tx = await self.set_token_allowance(pool.token1, target_addr, a1)
            if tx is not None: txs.append(tx)
        return txs, is_native0, is_native1

    @require_async_context
    async def set_token_allowance(self, token: Token, addr: str, amount: int):
        return await self._approve_if_needed(self.prepare_set_token_allowance_contract(token, self.web3.eth.contract), addr, amount)

    @require_async_context
    async def check_token_allowance(self, token: Token, addr: str) -> int:
        token_contract = self.web3.eth.contract(address=token.wrapped_token_address or token.token_address, abi=get_abi("erc20"))
        return await token_contract.functions.allowance(self.signer_address, addr).call()

    @require_async_context
    async def pool_spec(self, token0: Token, token1: Token, *,
                        tick_spacing: Optional[int] = None,
                        stable: Optional[bool] = None) -> LiquidityPool:
        """Build a not-yet-deployed pool spec for `chain.deposit`. CL: pass `tick_spacing`.
        Basic: pass `stable=True/False`. For basic pools the basic factory address is fetched
        from `router.defaultFactory()`."""
        basic_factory = await self.router.functions.defaultFactory().call() if stable is not None else None
        return LiquidityPool.for_creation(self.settings, token0, token1,
                                          tick_spacing=tick_spacing, stable=stable,
                                          basic_factory_addr=basic_factory)

    @require_async_context
    async def quote_basic_deposit(self, pool: LiquidityPool, *,
                                  amount_token0: Optional[int] = None,
                                  amount_token1: Optional[int] = None) -> DepositQuote:
        """Quote a basic-pool deposit.

        Existing pool: supply exactly one of `amount_token0` / `amount_token1`; the router
        computes the optimal pairing. New pool (built via `chain.pool_spec`): supply both
        amounts — there are no reserves to rebalance against, so we skip the on-chain quote."""
        if pool.is_cl: raise ValueError("quote_basic_deposit requires a basic pool")
        if pool.lp == ADDRESS_ZERO:
            if amount_token0 is None or amount_token1 is None:
                raise ValueError("new basic pool requires both amount_token0 and amount_token1")
            return DepositQuote(pool=pool, amount_token0=amount_token0, amount_token1=amount_token1)
        if (amount_token0 is None) == (amount_token1 is None): raise ValueError("supply exactly one of amount_token0 / amount_token1")
        a_desired = amount_token0 if amount_token0 is not None else MAX_UINT128
        b_desired = amount_token1 if amount_token1 is not None else MAX_UINT128
        [a0, a1, _] = await self.router.functions.quoteAddLiquidity(
            pool.token0.token_address, pool.token1.token_address, pool.is_stable,
            pool.factory, a_desired, b_desired,
        ).call()
        return DepositQuote(pool=pool, amount_token0=a0, amount_token1=a1)

    @require_async_context
    async def quote_concentrated_deposit(self, pool: LiquidityPool,
                                         price_lower: Optional[float] = None, price_upper: Optional[float] = None, *,
                                         tick_lower: Optional[int] = None, tick_upper: Optional[int] = None,
                                         amount_token0: Optional[int] = None,
                                         amount_token1: Optional[int] = None,
                                         initial_price: Optional[float] = None) -> DepositQuote:
        """Quote a CL deposit. Range can be given as prices (snapped to nearest ticks) or as raw ticks.
        Supply exactly one of `amount_token0` / `amount_token1`; the other is derived via
        slipstream.estimateAmount0/1. For an uninitialized pool, supply `initial_price`."""
        if not pool.is_cl: raise ValueError("quote_concentrated_deposit requires a CL pool")
        if (amount_token0 is None) == (amount_token1 is None): raise ValueError("supply exactly one of amount_token0 / amount_token1")

        has_price = price_lower is not None or price_upper is not None
        has_tick = tick_lower is not None or tick_upper is not None
        if has_price == has_tick: raise ValueError("supply (price_lower, price_upper) XOR (tick_lower, tick_upper)")
        if has_tick:
            if tick_lower is None or tick_upper is None: raise ValueError("supply both tick_lower and tick_upper")
            tl, tu = int(tick_lower), int(tick_upper)
        else:
            if price_lower is None or price_upper is None: raise ValueError("supply both price_lower and price_upper")
            snap = lambda p: nearest_tick(price_to_tick(p, pool.token0.decimals, pool.token1.decimals), pool.type)
            tl, tu = snap(price_lower), snap(price_upper)

        if pool.sqrt_ratio == 0:
            if initial_price is None: raise ValueError("uninitialized pool requires initial_price")
            sqrt_ratio = sqrt_ratio_x96_from_price(initial_price, pool.token0.decimals, pool.token1.decimals)
            sqrt_price_x96 = sqrt_ratio
        else:
            if initial_price is not None: raise ValueError("initial_price only applies to uninitialized pools")
            sqrt_ratio, sqrt_price_x96 = pool.sqrt_ratio, 0

        if amount_token0 is not None:
            a1 = await self.slipstream.functions.estimateAmount1(amount_token0, pool.lp, sqrt_ratio, tl, tu).call()
            return DepositQuote(pool=pool, amount_token0=amount_token0, amount_token1=a1,
                                tick_lower=tl, tick_upper=tu, sqrt_price_x96=sqrt_price_x96)
        a0 = await self.slipstream.functions.estimateAmount0(amount_token1, pool.lp, sqrt_ratio, tl, tu).call()
        return DepositQuote(pool=pool, amount_token0=a0, amount_token1=amount_token1,
                            tick_lower=tl, tick_upper=tu, sqrt_price_x96=sqrt_price_x96)

    @require_async_context
    async def deposit(self, quote: DepositQuote, delay_in_minutes: float = 30, slippage: float = 0.01):
        """Execute a deposit. Dispatches on `quote.pool.is_cl` — basic uses the router, CL uses NFPM mint."""
        if quote.pool.is_cl: return await self._deposit_concentrated(quote, delay_in_minutes, slippage)
        return await self._deposit_basic(quote, delay_in_minutes, slippage)

    @require_async_context
    async def _deposit_basic(self, quote: DepositQuote, delay_in_minutes: float, slippage: float):
        pool, router_addr = quote.pool, self.settings.router_contract_addr
        a0, a1 = quote.amount_token0, quote.amount_token1

        # native-token legs are sent as msg.value via addLiquidityETH — no ERC20 approval needed for those
        is_native0 = pool.token0.token_address == self.settings.wrapped_native_token_addr
        is_native1 = pool.token1.token_address == self.settings.wrapped_native_token_addr
        if not is_native0:
            await self.set_token_allowance(pool.token0, router_addr, a0)
        if not is_native1:
            await self.set_token_allowance(pool.token1, router_addr, a1)

        # if token 0 is native, use addLiquidityETH instead of standard addLiquidity
        if pool.token0.token_address == self.settings.wrapped_native_token_addr:
            params = [pool.token1.token_address, pool.is_stable, a1, apply_slippage(a1, slippage),
                      apply_slippage(a0, slippage), self.signer_address, get_future_timestamp(delay_in_minutes)]
            return await self.build_tx(self.router.functions.addLiquidityETH(*params), value=a0)

        # token 1 is native, use addLiquidityETH instead of standard addLiquidity
        if pool.token1.token_address == self.settings.wrapped_native_token_addr:
            params = [pool.token0.token_address, pool.is_stable, a0, apply_slippage(a0, slippage),
                      apply_slippage(a1, slippage), self.signer_address, get_future_timestamp(delay_in_minutes)]
            return await self.build_tx(self.router.functions.addLiquidityETH(*params), value=a1)

        params = [pool.token0.token_address, pool.token1.token_address, pool.is_stable, a0, a1,
                  apply_slippage(a0, slippage), apply_slippage(a1, slippage),
                  self.signer_address, get_future_timestamp(delay_in_minutes)]
        return await self.build_tx(self.router.functions.addLiquidity(*params))

    @require_async_context
    async def _deposit_concentrated(self, quote: DepositQuote, delay_in_minutes: float, slippage: float):
        pool = quote.pool
        nfpm = self._nfpm(pool)
        a0, a1 = quote.amount_token0, quote.amount_token1
        txs, is_native0, is_native1 = await self._collect_approvals(pool, nfpm.address, a0, a1)

        params = [(
            pool.token0.token_address, pool.token1.token_address, pool.type,
            quote.tick_lower, quote.tick_upper, a0, a1,
            apply_slippage(a0, slippage), apply_slippage(a1, slippage),
            self.signer_address, get_future_timestamp(delay_in_minutes), quote.sqrt_price_x96,
        )]

        if is_native0 or is_native1:
            mint_calldata = nfpm.encode_abi("mint", args=params)
            refund_calldata = nfpm.encode_abi("refundETH", args=[])
            main = self.build_tx(nfpm.functions.multicall([mint_calldata, refund_calldata]), value=a0 if is_native0 else a1)
        else:
            main = self.build_tx(nfpm.functions.mint(*params))
        return [*txs, main]
    @require_async_context
    async def get_positions(self, owner: Optional[str] = None) -> List[Position]:
        """List positions owned by `owner` (defaults to self.signer_address). Uses Sugar's
        paginated `positions(limit, offset, account)` reader."""
        owner = owner or self.signer_address
        def get_p(limit, offset): return self.sugar.functions.positions(limit, offset, owner)
        return self.prepare_positions(await self.apaginate(get_p), await self.get_pools())

    @require_async_context
    async def withdraw(self, withdrawal: Withdrawal, delay_in_minutes: float = 30, slippage: float = 0.01, collect: bool = True, unwrap_native: bool = False):
        """Execute a withdrawal. Dispatches on `withdrawal.pool.is_cl`."""
        if withdrawal.pool.is_cl: return await self._withdraw_concentrated(withdrawal, delay_in_minutes, slippage, collect, unwrap_native)
        return await self._withdraw_basic(withdrawal, delay_in_minutes, slippage)

    @require_async_context
    async def _withdraw_basic(self, w: Withdrawal, delay_in_minutes: float, slippage: float):
        pool = w.pool
        router_addr = self.settings.router_contract_addr
        a0_min, a1_min = apply_slippage(w.amount_token0, slippage), apply_slippage(w.amount_token1, slippage)
        deadline = get_future_timestamp(delay_in_minutes)
        native = self.settings.wrapped_native_token_addr

        lp = self.web3.eth.contract(address=normalize_address(pool.lp), abi=get_abi("erc20"))
        approval_tx = await self._approve_if_needed(lp, router_addr, w.liquidity)

        if pool.token0.token_address == native or pool.token1.token_address == native:
            is_native0 = pool.token0.token_address == native
            other_addr = pool.token1.token_address if is_native0 else pool.token0.token_address
            other_min, native_min = (a1_min, a0_min) if is_native0 else (a0_min, a1_min)
            params = [other_addr, pool.is_stable, w.liquidity, other_min, native_min, self.signer_address, deadline]
            main = self.build_tx(self.router.functions.removeLiquidityETH(*params))
        else:
            params = [pool.token0.token_address, pool.token1.token_address, pool.is_stable, w.liquidity, a0_min, a1_min, self.signer_address, deadline]
            main = self.build_tx(self.router.functions.removeLiquidity(*params))
        return [t for t in (approval_tx, main) if t is not None]

    @require_async_context
    async def _withdraw_concentrated(self, w: Withdrawal, delay_in_minutes: float, slippage: float, collect: bool, unwrap_native: bool):
        pool = w.pool
        nfpm = self._nfpm(pool)
        a0_min, a1_min = apply_slippage(w.amount_token0, slippage), apply_slippage(w.amount_token1, slippage)
        deadline = get_future_timestamp(delay_in_minutes)

        if (w.burn or unwrap_native) and not collect:
            raise ValueError("burn / unwrap_native require collect=True")
        decrease_args = (w.position_id, w.liquidity, a0_min, a1_min, deadline)
        if not collect:
            return [self.build_tx(nfpm.functions.decreaseLiquidity(decrease_args))]
        calls = [nfpm.encode_abi("decreaseLiquidity", args=[decrease_args])] + \
                self._build_nfpm_cleanup_calls(nfpm, pool, w.position_id, unwrap_native=unwrap_native, burn=w.burn)
        return [self.build_tx(nfpm.functions.multicall(calls))]
    @require_async_context
    async def stake(self, position: Position):
        """Stake `position`'s unstaked liquidity into the pool's gauge."""
        if position.is_alm: raise ValueError("ALM-managed position; not supported (use the ALM contract)")
        pool = position.pool
        if not pool.gauge or pool.gauge == ADDRESS_ZERO: raise ValueError(f"pool {pool.symbol} has no gauge")
        if not pool.gauge_alive: raise ValueError(f"gauge for {pool.symbol} is not active")
        gauge_addr = normalize_address(pool.gauge)
        gauge = self.web3.eth.contract(address=gauge_addr, abi=get_abi("gauge_basic" if not pool.is_cl else "gauge_cl"))
        if pool.is_cl:
            if position.staked > 0: raise ValueError(f"CL position #{position.id} is already staked")
            if position.liquidity == 0: raise ValueError(f"CL position #{position.id} has no liquidity to stake")
            nfpm = self._nfpm(pool)
            approval_tx = self.build_tx(nfpm.functions.approve(gauge_addr, position.id))
            main = self.build_tx(gauge.functions.deposit(position.id))
        else:
            if position.liquidity == 0: raise ValueError(f"no LP to stake for {pool.symbol}")
            lp = self.web3.eth.contract(address=normalize_address(pool.lp), abi=get_abi("erc20"))
            approval_tx = await self._approve_if_needed(lp, gauge_addr, position.liquidity)
            main = self.build_tx(gauge.functions.deposit(position.liquidity))
        return [t for t in (approval_tx, main) if t is not None]

    @require_async_context
    async def unstake(self, position: Position, *, amount: Optional[int] = None):
        """Withdraw from the pool's gauge. CL: full only; basic: pass `amount` for partial."""
        if position.is_alm: raise ValueError("ALM-managed position; not supported (use the ALM contract)")
        pool = position.pool
        if not pool.gauge or pool.gauge == ADDRESS_ZERO: raise ValueError(f"pool {pool.symbol} has no gauge")
        gauge = self.web3.eth.contract(address=normalize_address(pool.gauge), abi=get_abi("gauge_basic" if not pool.is_cl else "gauge_cl"))
        if pool.is_cl:
            if position.staked == 0: raise ValueError(f"CL position #{position.id} is not staked")
            tx = gauge.functions.withdraw(position.id)
        else:
            amount = position.staked if amount is None else amount
            if amount <= 0: raise ValueError("no staked LP to withdraw")
            if amount > position.staked: raise ValueError(f"unstake amount {amount} > staked {position.staked}")
            tx = gauge.functions.withdraw(amount)
        return [self.build_tx(tx)]

    @require_async_context
    async def claim_emissions(self, position: Position):
        """Claim gauge emissions for the position."""
        if position.is_alm: raise ValueError("ALM-managed position; not supported (use the ALM contract)")
        pool = position.pool
        if not pool.gauge or pool.gauge == ADDRESS_ZERO: raise ValueError(f"pool {pool.symbol} has no gauge")
        gauge_addr = normalize_address(pool.gauge)
        gauge = self.web3.eth.contract(address=gauge_addr, abi=get_abi("gauge_cl" if pool.is_cl else "gauge_basic"))
        tx = gauge.functions.getReward(position.id if pool.is_cl else self.signer_address)
        return [self.build_tx(tx)]

    @require_async_context
    async def claim_fees(self, position: Position, *, burn: bool = False, unwrap_native: bool = False):
        """Claim accrued LP fees. CL: NFPM multicall (collect → optional unwrap/burn). Basic: `pool.claimFees()`."""
        if position.is_alm: raise ValueError("ALM-managed position; not supported (use the ALM contract)")
        if position.staked > 0: raise ValueError("position is staked; unstake first to claim fees")
        pool = position.pool
        if pool.is_cl:
            if burn and position.liquidity > 0:
                raise ValueError("burn requires liquidity == 0; drain via withdraw first")
            nfpm = self._nfpm(pool)
            calls = self._build_nfpm_cleanup_calls(nfpm, pool, position.id, unwrap_native=unwrap_native, burn=burn)
            return [self.build_tx(nfpm.functions.multicall(calls))]
        pool_contract = self.web3.eth.contract(address=normalize_address(pool.lp), abi=get_abi("pool_basic"))
        return [self.build_tx(pool_contract.functions.claimFees())]

class Chain(CommonChain):
    web3: Web3
    sugar: Contract
    router: Contract
    slipstream: Contract
    prices: Contract
    quoter: Contract
    swapper: Contract

    def __enter__(self):
        """Sync context manager entry"""
        self._in_context = True
        self.web3 = Web3(HTTPProvider(self.settings.rpc_uri))
        self.sugar = self.web3.eth.contract(address=self.settings.sugar_contract_addr, abi=get_abi("sugar"))
        self.sugar_rewards = self.web3.eth.contract(address=self.settings.sugar_rewards_contract_addr, abi=get_abi("sugar_rewards"))
        self.slipstream = self.web3.eth.contract(address=self.settings.slipstream_contract_addr, abi=get_abi("slipstream"))
        self.prices = self.web3.eth.contract(address=self.settings.price_oracle_contract_addr, abi=get_abi("price_oracle"))
        self.router = self.web3.eth.contract(address=self.settings.router_contract_addr, abi=get_abi("router"))
        self.quoter = self.web3.eth.contract(address=self.settings.quoter_contract_addr, abi=get_abi("quoter"))
        self.swapper = self.web3.eth.contract(address=self.settings.swapper_contract_addr, abi=get_abi("swapper"))

        if hasattr(self.settings, "interchain_router_contract_addr"):
            # TODO: clean this up when interchain jazz is fully implemented
            self.ica_router = self.web3.eth.contract(address=self.settings.interchain_router_contract_addr, abi=get_abi("interchain_router"))

        # set up caching for price oracle
        self._get_prices = cached(TTLCache(ttl=self.settings.pricing_cache_timeout_seconds, maxsize=self.settings.price_batch_size * 10))(self._get_prices)

        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Sync context manager exit"""
        self._in_context = False
        return None
    
    def paginate(self, f: Callable):
        pool_count = self.get_pool_count()
        results, batches = [], self.get_pool_paginator(pool_count)

        def process_batch(batch: List[Tuple]):
            with self.web3.batch_requests() as batcher:
                for offset, limit in batch: batcher.add(f(limit, offset))
                return sum(batcher.execute(), [])

        
        with ThreadPoolExecutor(max_workers=self.settings.threading_max_workers) as executor:
            future_to_batch = {
                executor.submit(process_batch, batch): batch
                for batch in batches
            }
            for future in as_completed(future_to_batch):
                try: results.extend(future.result())
                except Exception as e:
                    print(f"Error processing path chunk: {e}")
                    continue

        return results

    @require_context
    @lru_cache(maxsize=None)
    def get_pool_count(self) -> int:
        """Pool count, cached per chain instance."""
        return self.sugar.functions.count().call()

    @require_context
    def get_bridge_fee(self, domain: int) -> int:
        contract = self.web3.eth.contract(address=self.settings.bridge_contract_addr, abi=get_abi("bridge_get_fee"))
        return contract.functions.quoteGasPayment(domain).call()
    
    @require_context
    def _internal_bridge_token(self, from_token: Token, destination_token: Token, amount: int, domain: int):
        # XX: marking this API as "internal" for now
        # TODO: remove destination_domain when get domain API stabilizes and use destination_token instead
        c = self.web3.eth.contract(address=self.settings.bridge_contract_addr, abi=get_abi("bridge_transfer_remote"))
        approval_tx = self.set_token_allowance(from_token, self.settings.bridge_contract_addr, amount)
        transfer_tx = self.build_tx(c.functions.transferRemote(domain, to_bytes32(self.signer_address), amount), value=self.get_bridge_fee(domain))
        return [t for t in (approval_tx, transfer_tx) if t is not None]

    @require_context
    def get_xchain_fee(self, destination_domain: int) -> int:
        return self.ica_router.functions.quoteGasForCommitReveal(destination_domain, XCHAIN_GAS_LIMIT_UPPERBOUND).call()

    @require_context
    def get_remote_interchain_account(self, destination_domain: int):
        abi = [{
            "name": "getRemoteInterchainAccount",
            "type": "function",
            "stateMutability": "view",
            "inputs": [
                {
                    "name": "",
                    "type": "uint32"
                },
                {
                    "name": "",
                    "type": "address"
                },
                {
                    "name": "",
                    "type": "bytes32"
                }
            ],
            "outputs": [
                {
                "name": "userICA",
                "type": "address"
                }
            ]
        }]
        contract = self.web3.eth.contract(address=self.settings.interchain_router_contract_addr, abi=abi)
        return contract.functions.getRemoteInterchainAccount(
            destination_domain,
            self.settings.swapper_contract_addr,
            to_bytes32(self.signer_address),
        ).call()

    @require_context
    def get_ica_hook(self): return self.ica_router.functions.hook().call()

    @require_context
    def get_user_ica_balance(self, user_ica: str) -> int:
        return self.balance_of(token_address=self.settings.bridge_token_addr, owner_address=user_ica)

    @require_context
    def _approve_if_needed(self, erc20, spender: str, amount: int):
        """Approve `spender` for `amount` on `erc20` if current allowance is below `amount`. Returns None when already sufficient."""
        if erc20.functions.allowance(self.signer_address, spender).call() >= amount: return None
        return self.build_tx(erc20.functions.approve(spender, amount))

    @require_context
    def set_token_allowance(self, token: Token, addr: str, amount: int):
        return self._approve_if_needed(self.prepare_set_token_allowance_contract(token, self.web3.eth.contract), addr, amount)

    @require_context
    @lru_cache(maxsize=None)
    def get_all_tokens(self, listed_only: bool = False) -> List[Token]:
        def get_tokens(limit, offset): return self.sugar.functions.tokens(limit, offset, ADDRESS_ZERO, [])
        return self.prepare_tokens(self.paginate(get_tokens), listed_only)

    @require_context
    def get_token(self, ref) -> Optional[Token]:
        """Resolve a token by 0x address, symbol (case-insensitive), or int (hex address as integer). Returns None if not found."""
        if not ref: return None
        if isinstance(ref, int): ref = '0x' + format(ref, '040x')
        tokens = self.get_all_tokens()
        if ref.startswith("0x"): return self.find_token_by_address(tokens, ref)
        return next((t for t in tokens if t.symbol.lower() == ref.lower()), None)
    
    @require_context
    def get_pool_by_address(self, address: str) -> Optional[LiquidityPool]:
        """Find a pool by LP address (case-insensitive). Returns None if not found."""
        return next((p for p in self.get_pools() if p.lp.lower() == address.lower()), None)

    @require_context
    def balance_of(self, token_address: str, owner_address: str) -> int:
        """Get token balance for given owner"""
        token_contract = self.web3.eth.contract(address=token_address, abi=get_abi("erc20"))
        return token_contract.functions.balanceOf(owner_address).call()
    
    @require_context
    def get_token_balance(self, token: Token, owner_address: Optional[str] = None) -> int:
        # TODO: consider moving to native token wording just like velo app does
        owner_address = owner_address or self.signer_address
        if not owner_address: raise ValueError("Owner address is required to get token balance")
        if token.wrapped_token_address: return self.web3.eth.get_balance(owner_address)
        return self.balance_of(token_address=token.token_address, owner_address=owner_address)

    @require_context
    def get_bridge_token(self) -> Token: return self._get_bridge_token(self.get_all_tokens())

    def _get_prices(self, tokens: Tuple[Token], max_retries: int = 3) -> List[int]:
        """Batched oracle reads, filtered to priceable tokens. Result is mapped back to input order (filtered tokens get 0)."""
        request_tokens = self.get_price_request_tokens(list(tokens))
        chunks = list(chunk(request_tokens, self.settings.price_batch_size))
        def _exec(cs):
            with self.web3.batch_requests() as b:
                for c in cs:
                    b.add(self.prices.functions.getManyRatesToEthWithCustomConnectors(
                        [t.wrapped_token_address or t.token_address for t in c],
                        False, self.get_price_connectors(), self.settings.price_threshold_filter))
                return b.execute()
        results = _exec(chunks) if chunks else []
        for _ in range(max_retries):
            failed = [i for i, r in enumerate(results) if not isinstance(r, list)]
            if not failed: break
            retry = _exec([chunks[i] for i in failed])
            for j, i in enumerate(failed): results[i] = retry[j]
        bad = [(i, r) for i, r in enumerate(results) if not isinstance(r, list)]
        if bad:
            i, e = bad[0]
            raise RuntimeError(f"price oracle batch failed: {len(bad)}/{len(results)} chunks unresolved after {max_retries} retries (chunk #{i}: {type(e).__name__}: {e})")
        rates = {t.token_address: r for c, rs in zip(chunks, results) for t, r in zip(c, rs)}
        return [rates.get(t.token_address, 0) for t in tokens]

    @require_context
    def get_prices(self, tokens: List[Token]) -> List[Price]:
        """Get prices for tokens in target stable token"""
        return self.prepare_prices(tokens, self._get_prices(tuple(tokens)))
    
    @lru_cache(maxsize=None)
    def get_raw_pools(self, for_swaps: bool):
        def get_all(limit, offset): return self.sugar.functions.all(limit, offset, 0)
        return self.paginate(self.sugar.functions.forSwaps if for_swaps else get_all)

    @require_context
    def get_pools(self, for_swaps: bool = False) -> List[LiquidityPool]:
        pools = self.get_raw_pools(for_swaps)
        if not for_swaps:
            tokens = self.get_all_tokens(listed_only=False)
            return self.prepare_pools(pools, tokens, self.get_prices(tokens))
        else: return self.prepare_pools_for_swap(pools)

    @require_context
    def get_pools_for_swaps(self) -> List[LiquidityPoolForSwap]: return self.get_pools(for_swaps=True)

    @require_context
    @lru_cache(maxsize=None)
    def get_pool_epochs(self, lp: str, offset: int = 0, limit: int = 10) -> List[LiquidityPoolEpoch]:
        tokens, pools = self.get_all_tokens(listed_only=False), self.get_pools()
        prices = self.get_prices(tokens)
        r = self.sugar_rewards.functions.epochsByAddress(limit, offset, normalize_address(lp)).call()
        return self.prepare_pool_epochs(r, pools, tokens, prices)

    @require_context
    @lru_cache(maxsize=None)
    def get_latest_pool_epochs(self) -> List[LiquidityPoolEpoch]:
        raw_epochs = self.paginate(self.sugar_rewards.functions.epochsLatest)
        if not raw_epochs: return []
        tokens = self.get_all_tokens(listed_only=False)
        epoch_lp_addresses = {normalize_address(epoch[1]) for epoch in raw_epochs}
        raw_pools = [p for p in self.get_raw_pools(False) if normalize_address(p[0]) in epoch_lp_addresses]
        prices = self.get_prices(self.get_latest_epoch_price_tokens(raw_epochs, raw_pools, tokens))
        pools = self.prepare_pools(raw_pools, tokens, prices)
        return self.prepare_pool_epochs(raw_epochs, pools, tokens, prices)

    @require_context
    def _get_quotes_for_paths(self, from_token: Token, to_token: Token, amount_in: int, pools: List[LiquidityPoolForSwap], paths: List[List[Tuple]]) -> List[Optional[Quote]]:
        path_pools = self.paths_to_pools(pools, paths)
        with self.web3.batch_requests() as batch:
            batch, inputs = self.prepare_quote_batch(from_token, to_token, batch, path_pools, amount_in, paths)
            return self.prepare_quotes(inputs, batch.execute())
    
    @require_context
    def get_quote(self, from_token: Token, to_token: Token, amount: int, filter_quotes: Optional[Callable[[Quote], bool]] = None) -> Optional[Quote]:
        pools = self.filter_pools_for_swap(from_token=from_token, to_token=to_token, pools=self.get_pools_for_swaps())
        paths = self.get_paths_for_quote(from_token, to_token, pools, self.settings.excluded_tokens_addrs)
        path_chunks = list(chunk(paths, 500))

        def get_quotes_for_chunk(paths_chunk):
            return self._get_quotes_for_paths(from_token, to_token, amount, pools, paths_chunk)
        
        all_quotes = []
        
        with ThreadPoolExecutor(max_workers=self.settings.threading_max_workers) as executor:
            # Submit all chunk processing tasks
            future_to_chunk = {
                executor.submit(get_quotes_for_chunk, chunk_paths): chunk_paths 
                for chunk_paths in path_chunks
            }
            
            # Collect results as they complete
            for future in as_completed(future_to_chunk):
                try:
                    all_quotes.extend(future.result())
                except Exception as e:
                    print(f"Error processing path chunk: {e}")
                    continue

        # Filter out None quotes
        all_quotes = [q for q in all_quotes if q is not None]
    
        if filter_quotes is not None:  all_quotes = list(filter(filter_quotes, all_quotes))

        return max(all_quotes, key=lambda q: q.amount_out) if len(all_quotes) > 0 else None
    
    @require_context
    def swap(self, from_token: Token, to_token: Token, amount: int, slippage: Optional[float] = None):
        q = self.get_quote(from_token, to_token, amount=amount)
        if not q: raise ValueError("No quotes found")
        return self.swap_from_quote(q, slippage=slippage)
        
    @require_context
    def swap_from_quote(self, quote: Quote, slippage: Optional[float] = None):
        """Build txs for a swap. Pools always route WETH, so the input side has two shapes:
        - **Native (ETH)**: amount goes as `msg.value`; the swapper wraps to WETH internally. No approval.
        - **WETH / ERC20**: requires the swapper to have an ERC20 allowance for `amount_in`; `value=0`.

        Returns `[approve_tx, swap_tx]` for ERC20 input, or `[swap_tx]` for native (or when allowance already covers `amount_in`)."""
        swapper, from_token = self.settings.swapper_contract_addr, quote.from_token
        slippage = slippage if slippage is not None else self.settings.swap_slippage
        planner = setup_planner(quote=quote, slippage=slippage, account=self.signer_address, router_address=swapper,
                                slipstream_factory_addr=self.settings.slipstream_factory_addr,
                                old_slipstream_factory_addr=self.settings.old_slipstream_factory_addr)
        execute = self.swapper.functions.execute(planner.commands, planner.inputs)
        if from_token.wrapped_token_address:  # native: swapper wraps msg.value to WETH
            return [self.build_tx(execute, value=quote.input.amount_in)]
        # ERC20 (incl. WETH): approve the wrapped token to the swapper, then execute with value=0
        approval_tx = self.set_token_allowance(from_token, swapper, quote.input.amount_in)
        main = self.build_tx(execute)
        return [t for t in (approval_tx, main) if t is not None]
    @require_context
    def pool_spec(self, token0: Token, token1: Token, *,
                  tick_spacing: Optional[int] = None,
                  stable: Optional[bool] = None) -> LiquidityPool:
        """Build a not-yet-deployed pool spec for `chain.deposit`. CL: pass `tick_spacing`.
        Basic: pass `stable=True/False`. For basic pools the basic factory address is fetched
        from `router.defaultFactory()`."""
        basic_factory = self.router.functions.defaultFactory().call() if stable is not None else None
        return LiquidityPool.for_creation(self.settings, token0, token1,
                                          tick_spacing=tick_spacing, stable=stable,
                                          basic_factory_addr=basic_factory)

    @require_context
    def quote_basic_deposit(self, pool: LiquidityPool, *,
                            amount_token0: Optional[int] = None,
                            amount_token1: Optional[int] = None) -> DepositQuote:
        """Quote a basic-pool deposit.

        Existing pool: supply exactly one of `amount_token0` / `amount_token1`; the router
        computes the optimal pairing. New pool (built via `chain.pool_spec`): supply both
        amounts — there are no reserves to rebalance against, so we skip the on-chain quote."""
        if pool.is_cl: raise ValueError("quote_basic_deposit requires a basic pool")
        if pool.lp == ADDRESS_ZERO:
            if amount_token0 is None or amount_token1 is None:
                raise ValueError("new basic pool requires both amount_token0 and amount_token1")
            return DepositQuote(pool=pool, amount_token0=amount_token0, amount_token1=amount_token1)
        if (amount_token0 is None) == (amount_token1 is None): raise ValueError("supply exactly one of amount_token0 / amount_token1")
        a_desired = amount_token0 if amount_token0 is not None else MAX_UINT128
        b_desired = amount_token1 if amount_token1 is not None else MAX_UINT128
        [a0, a1, _] = self.router.functions.quoteAddLiquidity(
            pool.token0.token_address, pool.token1.token_address, pool.is_stable,
            pool.factory, a_desired, b_desired,
        ).call()
        return DepositQuote(pool=pool, amount_token0=a0, amount_token1=a1)

    @require_context
    def quote_concentrated_deposit(self, pool: LiquidityPool,
                                   price_lower: Optional[float] = None, price_upper: Optional[float] = None, *,
                                   tick_lower: Optional[int] = None, tick_upper: Optional[int] = None,
                                   amount_token0: Optional[int] = None,
                                   amount_token1: Optional[int] = None,
                                   initial_price: Optional[float] = None) -> DepositQuote:
        """Quote a CL deposit. Range can be given as prices (snapped to nearest ticks) or as raw ticks.
        Supply exactly one of `amount_token0` / `amount_token1`; the other is derived via
        slipstream.estimateAmount0/1. For an uninitialized pool, supply `initial_price`."""
        if not pool.is_cl: raise ValueError("quote_concentrated_deposit requires a CL pool")
        if (amount_token0 is None) == (amount_token1 is None): raise ValueError("supply exactly one of amount_token0 / amount_token1")

        has_price = price_lower is not None or price_upper is not None
        has_tick = tick_lower is not None or tick_upper is not None
        if has_price == has_tick: raise ValueError("supply (price_lower, price_upper) XOR (tick_lower, tick_upper)")
        if has_tick:
            if tick_lower is None or tick_upper is None: raise ValueError("supply both tick_lower and tick_upper")
            tl, tu = int(tick_lower), int(tick_upper)
        else:
            if price_lower is None or price_upper is None: raise ValueError("supply both price_lower and price_upper")
            snap = lambda p: nearest_tick(price_to_tick(p, pool.token0.decimals, pool.token1.decimals), pool.type)
            tl, tu = snap(price_lower), snap(price_upper)

        if pool.sqrt_ratio == 0:
            if initial_price is None: raise ValueError("uninitialized pool requires initial_price")
            sqrt_ratio = sqrt_ratio_x96_from_price(initial_price, pool.token0.decimals, pool.token1.decimals)
            sqrt_price_x96 = sqrt_ratio
        else:
            if initial_price is not None: raise ValueError("initial_price only applies to uninitialized pools")
            sqrt_ratio, sqrt_price_x96 = pool.sqrt_ratio, 0

        if amount_token0 is not None:
            a1 = self.slipstream.functions.estimateAmount1(amount_token0, pool.lp, sqrt_ratio, tl, tu).call()
            return DepositQuote(pool=pool, amount_token0=amount_token0, amount_token1=a1,
                                tick_lower=tl, tick_upper=tu, sqrt_price_x96=sqrt_price_x96)
        a0 = self.slipstream.functions.estimateAmount0(amount_token1, pool.lp, sqrt_ratio, tl, tu).call()
        return DepositQuote(pool=pool, amount_token0=a0, amount_token1=amount_token1,
                            tick_lower=tl, tick_upper=tu, sqrt_price_x96=sqrt_price_x96)

    @require_context
    @require_context
    def _collect_approvals(self, pool, target_addr, a0, a1):
        """Set ERC20 allowances for non-native legs of `pool` to `target_addr`.

        Returns (approval_txs, is_native0, is_native1). `approval_txs` is empty in live mode."""
        native = self.settings.wrapped_native_token_addr
        is_native0 = pool.token0.token_address == native
        is_native1 = pool.token1.token_address == native
        txs = []
        if not is_native0:
            tx = self.set_token_allowance(pool.token0, target_addr, a0)
            if tx is not None: txs.append(tx)
        if not is_native1:
            tx = self.set_token_allowance(pool.token1, target_addr, a1)
            if tx is not None: txs.append(tx)
        return txs, is_native0, is_native1

    @require_context
    def deposit(self, quote: DepositQuote, delay_in_minutes: float = 30, slippage: float = 0.01):
        """Execute a deposit. Dispatches on `quote.pool.is_cl` — basic uses the router, CL uses NFPM mint."""
        if quote.pool.is_cl: return self._deposit_concentrated(quote, delay_in_minutes, slippage)
        return self._deposit_basic(quote, delay_in_minutes, slippage)

    @require_context
    def _deposit_basic(self, quote: DepositQuote, delay_in_minutes: float, slippage: float):
        pool, router_addr = quote.pool, self.settings.router_contract_addr
        a0, a1 = quote.amount_token0, quote.amount_token1
        deadline = get_future_timestamp(delay_in_minutes)
        txs, is_native0, is_native1 = self._collect_approvals(pool, router_addr, a0, a1)

        if is_native0 or is_native1:
            other_addr = pool.token1.token_address if is_native0 else pool.token0.token_address
            other_amt, native_amt = (a1, a0) if is_native0 else (a0, a1)
            params = [other_addr, pool.is_stable, other_amt, apply_slippage(other_amt, slippage),
                      apply_slippage(native_amt, slippage), self.signer_address, deadline]
            main = self.build_tx(self.router.functions.addLiquidityETH(*params), value=native_amt)
        else:
            params = [pool.token0.token_address, pool.token1.token_address, pool.is_stable, a0, a1,
                      apply_slippage(a0, slippage), apply_slippage(a1, slippage), self.signer_address, deadline]
            main = self.build_tx(self.router.functions.addLiquidity(*params))
        return [*txs, main]

    @require_context
    def _deposit_concentrated(self, quote: DepositQuote, delay_in_minutes: float, slippage: float):
        pool = quote.pool
        nfpm = self._nfpm(pool)
        a0, a1 = quote.amount_token0, quote.amount_token1
        txs, is_native0, is_native1 = self._collect_approvals(pool, nfpm.address, a0, a1)

        params = [(
            pool.token0.token_address, pool.token1.token_address, pool.type,
            quote.tick_lower, quote.tick_upper, a0, a1,
            apply_slippage(a0, slippage), apply_slippage(a1, slippage),
            self.signer_address, get_future_timestamp(delay_in_minutes), quote.sqrt_price_x96,
        )]

        if is_native0 or is_native1:
            mint_calldata = nfpm.encode_abi("mint", args=params)
            refund_calldata = nfpm.encode_abi("refundETH", args=[])
            main = self.build_tx(nfpm.functions.multicall([mint_calldata, refund_calldata]), value=a0 if is_native0 else a1)
        else:
            main = self.build_tx(nfpm.functions.mint(*params))
        return [*txs, main]
    @require_context
    def get_positions(self, owner: Optional[str] = None) -> List[Position]:
        """List positions owned by `owner` (defaults to self.signer_address). Uses Sugar's
        paginated `positions(limit, offset, account)` reader."""
        owner = owner or self.signer_address
        def get_p(limit, offset): return self.sugar.functions.positions(limit, offset, owner)
        return self.prepare_positions(self.paginate(get_p), self.get_pools())

    @require_context
    def withdraw(self, withdrawal: Withdrawal, delay_in_minutes: float = 30, slippage: float = 0.01,
                 collect: bool = True, unwrap_native: bool = False):
        """Execute a withdrawal. Dispatches on `withdrawal.pool.is_cl`."""
        if withdrawal.pool.is_cl:
            return self._withdraw_concentrated(withdrawal, delay_in_minutes, slippage, collect, unwrap_native)
        return self._withdraw_basic(withdrawal, delay_in_minutes, slippage)

    @require_context
    def _withdraw_basic(self, w: Withdrawal, delay_in_minutes: float, slippage: float):
        pool = w.pool
        router_addr = self.settings.router_contract_addr
        a0_min, a1_min = apply_slippage(w.amount_token0, slippage), apply_slippage(w.amount_token1, slippage)
        deadline = get_future_timestamp(delay_in_minutes)
        native = self.settings.wrapped_native_token_addr

        lp = self.web3.eth.contract(address=normalize_address(pool.lp), abi=get_abi("erc20"))
        approval_tx = self._approve_if_needed(lp, router_addr, w.liquidity)

        if pool.token0.token_address == native or pool.token1.token_address == native:
            is_native0 = pool.token0.token_address == native
            other_addr = pool.token1.token_address if is_native0 else pool.token0.token_address
            other_min, native_min = (a1_min, a0_min) if is_native0 else (a0_min, a1_min)
            params = [other_addr, pool.is_stable, w.liquidity, other_min, native_min, self.signer_address, deadline]
            main = self.build_tx(self.router.functions.removeLiquidityETH(*params))
        else:
            params = [pool.token0.token_address, pool.token1.token_address, pool.is_stable, w.liquidity, a0_min, a1_min, self.signer_address, deadline]
            main = self.build_tx(self.router.functions.removeLiquidity(*params))
        return [t for t in (approval_tx, main) if t is not None]

    @require_context
    def _withdraw_concentrated(self, w: Withdrawal, delay_in_minutes: float, slippage: float,
                               collect: bool, unwrap_native: bool):
        pool = w.pool
        nfpm = self._nfpm(pool)
        a0_min, a1_min = apply_slippage(w.amount_token0, slippage), apply_slippage(w.amount_token1, slippage)
        deadline = get_future_timestamp(delay_in_minutes)

        if (w.burn or unwrap_native) and not collect:
            raise ValueError("burn / unwrap_native require collect=True")
        decrease_args = (w.position_id, w.liquidity, a0_min, a1_min, deadline)
        if not collect:
            main = self.build_tx(nfpm.functions.decreaseLiquidity(decrease_args))
        else:
            calls = [nfpm.encode_abi("decreaseLiquidity", args=[decrease_args])] + \
                    self._build_nfpm_cleanup_calls(nfpm, pool, w.position_id, unwrap_native=unwrap_native, burn=w.burn)
            main = self.build_tx(nfpm.functions.multicall(calls))
        return [main]
    @require_context
    def stake(self, position: Position):
        """Stake `position`'s unstaked liquidity into the pool's gauge."""
        if position.is_alm: raise ValueError("ALM-managed position; not supported (use the ALM contract)")
        pool = position.pool
        if not pool.gauge or pool.gauge == ADDRESS_ZERO: raise ValueError(f"pool {pool.symbol} has no gauge")
        if not pool.gauge_alive: raise ValueError(f"gauge for {pool.symbol} is not active")
        gauge_addr = normalize_address(pool.gauge)
        gauge = self.web3.eth.contract(address=gauge_addr, abi=get_abi("gauge_basic" if not pool.is_cl else "gauge_cl"))
        if pool.is_cl:
            if position.staked > 0: raise ValueError(f"CL position #{position.id} is already staked")
            if position.liquidity == 0: raise ValueError(f"CL position #{position.id} has no liquidity to stake")
            nfpm = self._nfpm(pool)
            approval_tx = self.build_tx(nfpm.functions.approve(gauge_addr, position.id))
            main = self.build_tx(gauge.functions.deposit(position.id))
        else:
            if position.liquidity == 0: raise ValueError(f"no LP to stake for {pool.symbol}")
            lp = self.web3.eth.contract(address=normalize_address(pool.lp), abi=get_abi("erc20"))
            approval_tx = self._approve_if_needed(lp, gauge_addr, position.liquidity)
            main = self.build_tx(gauge.functions.deposit(position.liquidity))
        return [t for t in (approval_tx, main) if t is not None]

    @require_context
    def unstake(self, position: Position, *, amount: Optional[int] = None):
        """Withdraw from the pool's gauge. CL: full only; basic: pass `amount` for partial."""
        if position.is_alm: raise ValueError("ALM-managed position; not supported (use the ALM contract)")
        pool = position.pool
        if not pool.gauge or pool.gauge == ADDRESS_ZERO: raise ValueError(f"pool {pool.symbol} has no gauge")
        gauge = self.web3.eth.contract(address=normalize_address(pool.gauge), abi=get_abi("gauge_basic" if not pool.is_cl else "gauge_cl"))
        if pool.is_cl:
            if position.staked == 0: raise ValueError(f"CL position #{position.id} is not staked")
            tx = gauge.functions.withdraw(position.id)
        else:
            amount = position.staked if amount is None else amount
            if amount <= 0: raise ValueError("no staked LP to withdraw")
            if amount > position.staked: raise ValueError(f"unstake amount {amount} > staked {position.staked}")
            tx = gauge.functions.withdraw(amount)
        return [self.build_tx(tx)]

    @require_context
    def claim_emissions(self, position: Position):
        """Claim gauge emissions for the position."""
        if position.is_alm: raise ValueError("ALM-managed position; not supported (use the ALM contract)")
        pool = position.pool
        if not pool.gauge or pool.gauge == ADDRESS_ZERO: raise ValueError(f"pool {pool.symbol} has no gauge")
        gauge_addr = normalize_address(pool.gauge)
        gauge = self.web3.eth.contract(address=gauge_addr, abi=get_abi("gauge_cl" if pool.is_cl else "gauge_basic"))
        return [self.build_tx(gauge.functions.getReward(position.id if pool.is_cl else self.signer_address))]

    @require_context
    def claim_fees(self, position: Position, *, burn: bool = False, unwrap_native: bool = False):
        """Claim accrued LP fees. CL: NFPM multicall (collect → optional unwrap/burn). Basic: `pool.claimFees()`."""
        if position.is_alm: raise ValueError("ALM-managed position; not supported (use the ALM contract)")
        if position.staked > 0: raise ValueError("position is staked; unstake first to claim fees")
        pool = position.pool
        if pool.is_cl:
            if burn and position.liquidity > 0:
                raise ValueError("burn requires liquidity == 0; drain via withdraw first")
            nfpm = self._nfpm(pool)
            calls = self._build_nfpm_cleanup_calls(nfpm, pool, position.id, unwrap_native=unwrap_native, burn=burn)
            tx = nfpm.functions.multicall(calls)
        else:
            pool_contract = self.web3.eth.contract(address=normalize_address(pool.lp), abi=get_abi("pool_basic"))
            tx = pool_contract.functions.claimFees()
        return [self.build_tx(tx)]

_op_settings = make_op_chain_settings()

class OPChainCommon():
    usdc: Token = Token(chain_id=_op_settings.chain_id, chain_name=_op_settings.chain_name,
                        token_address='0x0b2C639c533813f4Aa9D7837CAf62653d097Ff85', symbol='USDC',
                        decimals=6, listed=True, wrapped_token_address=None)
    velo: Token = Token(chain_id=_op_settings.chain_id, chain_name=_op_settings.chain_name,
                        token_address='0x9560e827aF36c94D2Ac33a39bCE1Fe78631088Db', symbol='VELO', decimals=18, listed=True, wrapped_token_address=None)
    eth: Token = Token(chain_id=_op_settings.chain_id, chain_name=_op_settings.chain_name,
                       token_address='ETH', symbol='ETH', decimals=18, listed=True, wrapped_token_address='0x4200000000000000000000000000000000000006') 
    o_usdt: Token = Token(chain_id=_op_settings.chain_id, chain_name=_op_settings.chain_name,
                         token_address='0x1217BfE6c773EEC6cc4A38b5Dc45B92292B6E189', symbol='oUSDT',
                         decimals=6, listed=True, wrapped_token_address=None)

class AsyncOPChain(AsyncChain, OPChainCommon):
    def __init__(self, **kwargs): super().__init__(make_op_chain_settings(**kwargs), **kwargs)

class OPChain(Chain, OPChainCommon):
    def __init__(self, **kwargs): super().__init__(make_op_chain_settings(**kwargs), **kwargs)

_base_settings = make_base_chain_settings()

class BaseChainCommon():
    usdc: Token = Token(chain_id=_base_settings.chain_id, chain_name=_base_settings.chain_name,
                        token_address='0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913', symbol='USDC', decimals=6, listed=True, wrapped_token_address=None)
    aero: Token = Token(chain_id=_base_settings.chain_id, chain_name=_base_settings.chain_name,
                        token_address='0x940181a94A35A4569E4529A3CDfB74e38FD98631', symbol='AERO', decimals=18, listed=True, wrapped_token_address=None)
    eth: Token = Token(chain_id=_base_settings.chain_id, chain_name=_base_settings.chain_name,
                       token_address='ETH', symbol='ETH', decimals=18, listed=True, wrapped_token_address='0x4200000000000000000000000000000000000006')
    
class AsyncBaseChain(AsyncChain, BaseChainCommon):
    def __init__(self, **kwargs): super().__init__(make_base_chain_settings(**kwargs), **kwargs)

class BaseChain(Chain, BaseChainCommon):
    def __init__(self, **kwargs): super().__init__(make_base_chain_settings(**kwargs), **kwargs)

class LiskChainCommon():
    o_usdt: Token = Token(chain_id='1135', chain_name='Lisk', token_address='0x1217BfE6c773EEC6cc4A38b5Dc45B92292B6E189', symbol='oUSDT', decimals=6, listed=True, wrapped_token_address=None)
    lsk: Token = Token(chain_id='1135', chain_name='Lisk', token_address='0xac485391EB2d7D88253a7F1eF18C37f4242D1A24', symbol='LSK', decimals=18, listed=True, wrapped_token_address=None)
    eth: Token = Token(chain_id='1135', chain_name='Lisk', token_address='ETH', symbol='ETH', decimals=18, listed=True, wrapped_token_address='0x4200000000000000000000000000000000000006')
    usdt: Token = Token(chain_id='1135', chain_name='Lisk', token_address='0x05D032ac25d322df992303dCa074EE7392C117b9', symbol='USDT', decimals=6, listed=True, wrapped_token_address=None)

class AsyncLiskChain(AsyncChain, LiskChainCommon):
    def __init__(self, **kwargs): super().__init__(make_lisk_chain_settings(**kwargs), **kwargs)

class LiskChain(Chain, LiskChainCommon):
    def __init__(self, **kwargs): super().__init__(make_lisk_chain_settings(**kwargs), **kwargs)

class UniChainCommon():
    eth: Token = Token(chain_id='130', chain_name='Uni', token_address='ETH', symbol='ETH', decimals=18, listed=True, wrapped_token_address='0x4200000000000000000000000000000000000006')
    o_usdt: Token = Token(chain_id='130', chain_name='Uni', token_address='0x1217BfE6c773EEC6cc4A38b5Dc45B92292B6E189', symbol='oUSDT', decimals=6, listed=True, wrapped_token_address=None)
    usdc: Token = Token(chain_id='130', chain_name='Uni', token_address='0x078D782b760474a361dDA0AF3839290b0EF57AD6', symbol='USDC', decimals=6, listed=True, wrapped_token_address=None)
    
class AsyncUniChain(AsyncChain, UniChainCommon):
    def __init__(self, **kwargs): super().__init__(make_uni_chain_settings(**kwargs), **kwargs)

class UniChain(Chain, UniChainCommon):
    def __init__(self, **kwargs): super().__init__(make_uni_chain_settings(**kwargs), **kwargs)

class LiskChainSimnet(LiskChain):
    is_simnet = True
    def __init__(self,  **kwargs): super().__init__(rpc_uri="http://127.0.0.1:4445", threading_max_workers=1, **kwargs)

class AsyncLiskChainSimnet(AsyncLiskChain):
    is_simnet = True
    def __init__(self,  **kwargs): super().__init__(rpc_uri="http://127.0.0.1:4445", threading_max_workers=1, **kwargs)

class AsyncUniChainSimnet(AsyncUniChain):
    is_simnet = True
    def __init__(self,  **kwargs): super().__init__(rpc_uri="http://127.0.0.1:4446", threading_max_workers=1, **kwargs)

class UniChainSimnet(UniChain):
    is_simnet = True
    def __init__(self,  **kwargs): super().__init__(rpc_uri="http://127.0.0.1:4446", threading_max_workers=1, **kwargs)

class ModeChainCommon():
    eth: Token = Token(chain_id='34443', chain_name='Mode', token_address='ETH', symbol='ETH', decimals=18, listed=True, wrapped_token_address='0x4200000000000000000000000000000000000006')
    o_usdt: Token = Token(chain_id='34443', chain_name='Mode', token_address='0x1217BfE6c773EEC6cc4A38b5Dc45B92292B6E189', symbol='oUSDT', decimals=6, listed=True, wrapped_token_address=None)
    usdc: Token = Token(chain_id='34443', chain_name='Mode', token_address='0xd988097fb8612cc24eec14542bc03424c656005f', symbol='USDC', decimals=6, listed=True, wrapped_token_address=None)

class AsyncModeChain(AsyncChain, ModeChainCommon):
    def __init__(self, **kwargs): super().__init__(make_mode_chain_settings(**kwargs), **kwargs)

class ModeChain(Chain, ModeChainCommon):
    def __init__(self, **kwargs): super().__init__(make_mode_chain_settings(**kwargs), **kwargs)

class FraxtalChainCommon():
    frax: Token = Token(chain_id='252', chain_name='Fraxtal', token_address='FRAX', symbol='FRAX', decimals=18, listed=True, wrapped_token_address='0xfc00000000000000000000000000000000000006')
    o_usdt: Token = Token(chain_id='252', chain_name='Fraxtal', token_address='0x1217BfE6c773EEC6cc4A38b5Dc45B92292B6E189', symbol='oUSDT', decimals=6, listed=True, wrapped_token_address=None)
    frxusd: Token = Token(chain_id='252', chain_name='Fraxtal', token_address='0xfc00000000000000000000000000000000000001', symbol='frxUSD', decimals=18, listed=True, wrapped_token_address=None)

class AsyncFraxtalChain(AsyncChain, FraxtalChainCommon):
    def __init__(self, **kwargs): super().__init__(make_fraxtal_chain_settings(**kwargs), **kwargs)

class FraxtalChain(Chain, FraxtalChainCommon):
    def __init__(self, **kwargs): super().__init__(make_fraxtal_chain_settings(**kwargs), **kwargs)

class InkChainCommon():
    eth: Token = Token(chain_id='57073', chain_name='Ink', token_address='ETH', symbol='ETH', decimals=18, listed=True, wrapped_token_address='0x4200000000000000000000000000000000000006')
    o_usdt: Token = Token(chain_id='57073', chain_name='Ink', token_address='0x1217BfE6c773EEC6cc4A38b5Dc45B92292B6E189', symbol='oUSDT', decimals=6, listed=True, wrapped_token_address=None)
    usdc: Token = Token(chain_id='57073', chain_name='Ink', token_address='0xf1815bd50389c46847f0bda824ec8da914045d14', symbol='USDC', decimals=6, listed=True, wrapped_token_address=None)

class AsyncInkChain(AsyncChain, InkChainCommon):
    def __init__(self, **kwargs): super().__init__(make_ink_chain_settings(**kwargs), **kwargs)

class InkChain(Chain, InkChainCommon):
    def __init__(self, **kwargs): super().__init__(make_ink_chain_settings(**kwargs), **kwargs)

class SoneiumChainCommon():
    eth: Token = Token(chain_id='1868', chain_name='Soneium', token_address='ETH', symbol='ETH', decimals=18, listed=True, wrapped_token_address='0x4200000000000000000000000000000000000006')
    o_usdt: Token = Token(chain_id='1868', chain_name='Soneium', token_address='0x1217BfE6c773EEC6cc4A38b5Dc45B92292B6E189', symbol='oUSDT', decimals=6, listed=True, wrapped_token_address=None)
    usdc: Token = Token(chain_id='1868', chain_name='Soneium', token_address='0xba9986d2381edf1da03b0b9c1f8b00dc4aacc369', symbol='USDC', decimals=6, listed=True, wrapped_token_address=None)

class AsyncSoneiumChain(AsyncChain, SoneiumChainCommon):
    def __init__(self, **kwargs): super().__init__(make_soneium_chain_settings(**kwargs), **kwargs)

class SoneiumChain(Chain, SoneiumChainCommon):
    def __init__(self, **kwargs): super().__init__(make_soneium_chain_settings(**kwargs), **kwargs)

class SuperseedChainCommon():
    eth: Token = Token(chain_id='5330', chain_name='Superseed', token_address='ETH', symbol='ETH', decimals=18, listed=True, wrapped_token_address='0x4200000000000000000000000000000000000006')
    o_usdt: Token = Token(chain_id='5330', chain_name='Superseed', token_address='0x1217BfE6c773EEC6cc4A38b5Dc45B92292B6E189', symbol='oUSDT', decimals=6, listed=True, wrapped_token_address=None)
    usdc: Token = Token(chain_id='5330', chain_name='Superseed', token_address='0xc316c8252b5f2176d0135ebb0999e99296998f2e', symbol='USDC', decimals=6, listed=True, wrapped_token_address=None)

class AsyncSuperseedChain(AsyncChain, SuperseedChainCommon):
    def __init__(self, **kwargs): super().__init__(make_superseed_chain_settings(**kwargs), **kwargs)

class SuperseedChain(Chain, SuperseedChainCommon):
    def __init__(self, **kwargs): super().__init__(make_superseed_chain_settings(**kwargs), **kwargs)

class CeloChainCommon():
    celo: Token = Token(chain_id='42220', chain_name='Celo', token_address='0x471ece3750da237f93b8e339c536989b8978a438', symbol='CELO', decimals=18, listed=True, wrapped_token_address=None)
    o_usdt: Token = Token(chain_id='42220', chain_name='Celo', token_address='0x1217BfE6c773EEC6cc4A38b5Dc45B92292B6E189', symbol='oUSDT', decimals=6, listed=True, wrapped_token_address=None)
    usdt: Token = Token(chain_id='42220', chain_name='Celo', token_address='0x48065fbbe25f71c9282ddf5e1cd6d6a887483d5e', symbol='USDT', decimals=6, listed=True, wrapped_token_address=None)
    weth: Token = Token(chain_id='42220', chain_name='Celo', token_address='0xd221812de1bd094f35587ee8e174b07b6167d9af', symbol='WETH', decimals=18, listed=True, wrapped_token_address=None)

class AsyncCeloChain(AsyncChain, CeloChainCommon):
    def __init__(self, **kwargs): super().__init__(make_celo_chain_settings(**kwargs), **kwargs)

class CeloChain(Chain, CeloChainCommon):
    def __init__(self, **kwargs): super().__init__(make_celo_chain_settings(**kwargs), **kwargs)

def get_chain(chain_id: str, **kwargs) -> Chain:
    if chain_id == '10': return OPChain(**kwargs)
    elif chain_id == '8453': return BaseChain(**kwargs)
    elif chain_id == '130': return UniChain(**kwargs)
    elif chain_id == '1135': return LiskChain(**kwargs)
    elif chain_id == '34443': return ModeChain(**kwargs)
    elif chain_id == '252': return FraxtalChain(**kwargs)
    elif chain_id == '57073': return InkChain(**kwargs)
    elif chain_id == '1868': return SoneiumChain(**kwargs)
    elif chain_id == '5330': return SuperseedChain(**kwargs)
    elif chain_id == '42220': return CeloChain(**kwargs)
    else: raise ValueError(f"Unsupported chain ID: {chain_id}")

def get_async_chain(chain_id: str, **kwargs) -> AsyncChain:
    if chain_id == '10': return AsyncOPChain(**kwargs)
    elif chain_id == '8453': return AsyncBaseChain(**kwargs)
    elif chain_id == '130': return AsyncUniChain(**kwargs)
    elif chain_id == '1135': return AsyncLiskChain(**kwargs)
    elif chain_id == '34443': return AsyncModeChain(**kwargs)
    elif chain_id == '252': return AsyncFraxtalChain(**kwargs)
    elif chain_id == '57073': return AsyncInkChain(**kwargs)
    elif chain_id == '1868': return AsyncSoneiumChain(**kwargs)
    elif chain_id == '5330': return AsyncSuperseedChain(**kwargs)
    elif chain_id == '42220': return AsyncCeloChain(**kwargs)
    else: raise ValueError(f"Unsupported chain ID: {chain_id}")

def get_simnet_chain(chain_id: str, **kwargs) -> Chain:
    if chain_id == '130': return UniChainSimnet(**kwargs)
    elif chain_id == '1135': return LiskChainSimnet(**kwargs)
    else: raise ValueError(f"Unsupported simnet chain ID: {chain_id} (supported: 130, 1135)")

def get_async_simnet_chain(chain_id: str, **kwargs) -> AsyncChain:
    if chain_id == '130': return AsyncUniChainSimnet(**kwargs)
    elif chain_id == '1135': return AsyncLiskChainSimnet(**kwargs)
    else: raise ValueError(f"Unsupported simnet chain ID: {chain_id} (supported: 130, 1135)")

def get_chain_from_token(t: Token, **kwargs) -> Chain: return get_chain(t.chain_id, **kwargs)
def get_async_chain_from_token(t: Token, **kwargs) -> AsyncChain: return get_async_chain(t.chain_id, **kwargs)
def get_simnet_chain_from_token(t: Token, **kwargs) -> Chain: return get_simnet_chain(t.chain_id, **kwargs)
def get_async_simnet_chain_from_token(t: Token, **kwargs) -> AsyncChain: return get_async_simnet_chain(t.chain_id, **kwargs)

