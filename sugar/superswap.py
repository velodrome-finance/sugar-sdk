__all__ = ['domains_abi', 'supported_chains', 'get_domain_async', 'get_domain', 'SuperswapRelayer', 'HTTPSuperswapRelayer',
           'MockSuperswapRelayer', 'SuperswapCommon', 'Superswap', 'AsyncSuperswap', 'SuperswapTxs']

import json, requests
from dataclasses import dataclass
from .swap import build_super_swap_data, SuperSwapData, setup_planner, SuperSwapDataInput
from .token import Token
from .quote import SuperswapQuote
from .helpers import get_salt, serialize_ica_calls
from .config import hyperlane_relay_url, hyperlane_relayers
from .chains import (
    AsyncChain, AsyncOPChain, Chain, OPChain,
    get_async_chain_from_token, get_async_simnet_chain_from_token,
    get_chain_from_token, get_simnet_chain_from_token,
)
from typing import List, Dict, Optional, Union
from abc import ABC, abstractmethod


@dataclass
class SuperswapTxs:
    """Output of a Superswap build. SDK never broadcasts — caller signs `txs` and submits in order.

    `swap_data` is set only when a relayer step is required after broadcast (cross-chain ICA orchestration).
    The caller uses `plan.relay_kwargs(commitment_dispatch_tx)` to assemble the args for `relayer.share_calls(...)`."""
    txs: List[Dict]
    swap_data: Optional[SuperSwapData]

    def relay_kwargs(self, commitment_dispatch_tx: str) -> Dict:
        """Return kwargs ready to splat into `relayer.share_calls(...)`. Only valid when `swap_data is not None`."""
        return {
            "calls": serialize_ica_calls(self.swap_data.calls),
            "salt": self.swap_data.salt,
            "commitment_dispatch_tx": commitment_dispatch_tx,
            "origin_domain": self.swap_data.origin_domain,
        }

domains_abi = [
    {
        "name": "domains",
        "type": "function",
        "stateMutability": "view",
        "inputs": [
            {
                "name": "",
                "type": "uint256"
            }
        ],
        "outputs": [
            {
                "name": "domain",
                "type": "uint256"
            }
        ]
    }
]

# TODO: remove this when domains are supported on all chains
async def get_domain_async(chain_id: int) -> int:
    # TODO: remove chain_id arg when all chains support domains
    async with AsyncOPChain() as op:
        contract = op.web3.eth.contract(address=op.settings.message_module_contract_addr, abi=domains_abi)
        domain = await contract.functions.domains(chain_id).call()
        # TODO: remove fallback to chain_id when all chains support domains
        return domain if domain != 0 else int(chain_id)

def get_domain(chain_id: int) -> int:
    # TODO: remove chain_id arg when all chains support domains
    with OPChain() as op:
        contract = op.web3.eth.contract(address=op.settings.message_module_contract_addr, abi=domains_abi)
        domain = contract.functions.domains(chain_id).call()
        # TODO: remove fallback to chain_id when all chains support domains
        return domain if domain != 0 else int(chain_id)

class SuperswapRelayer(ABC):
    @abstractmethod
    def share_calls(self, calls: List[dict], salt: str, commitment_dispatch_tx: str, origin_domain: int) -> None:
        """Share calls with the relayer."""
        pass

# TODO: add helper to inspect tx using https://explorer.hyperlane.xyz/?search

class HTTPSuperswapRelayer(SuperswapRelayer):
    def share_calls(self, calls: List[dict], salt: str, commitment_dispatch_tx: str, origin_domain: int) -> None:
        body = json.dumps({
            'commitmentDispatchTx': commitment_dispatch_tx,
            'originDomain': origin_domain,
            'calls': calls,
            'salt': salt,
            'relayers': hyperlane_relayers
        })
        resp = requests.post(hyperlane_relay_url, headers={'Content-Type': 'application/json'}, data=body)
        if not resp.ok:
            raise RuntimeError(f"Hyperlane relay failed: {resp.status_code} {resp.text}")

class MockSuperswapRelayer(SuperswapRelayer):
    def __init__(self):
        self.call_count = 0

    def share_calls(self, calls: List[dict], salt: str, commitment_dispatch_tx: str, origin_domain: int) -> None:
        self.call_count += 1

    def get_call_count(self) -> int:
        return self.call_count

supported_chains = ["OP", "Lisk", "Uni"]

class SuperswapCommon:
    def check_chain_support(self, from_token: Token, to_token: Token) -> None:
        """Check if the given tokens are supported for superswap."""
        from_chain, to_chain = get_async_chain_from_token(from_token), get_async_chain_from_token(to_token)
        if from_chain.name not in supported_chains or to_chain.name not in supported_chains:
            raise ValueError(f"Superswap only supports {supported_chains}. Got {from_chain.name} -> {to_chain.name}")

    def prepare_super_swap(
        self, 
        quote: SuperswapQuote,
        from_chain: Union[Chain, AsyncChain], to_chain: Union[Chain, AsyncChain],
        user_ica_address: str, user_ICA_balance: int, origin_domain: int, destination_domain: int,
        origin_hook: str, slippage: float, bridge_fee: int, xchain_fee: int, salt: Optional[str] = None
    ):
        swap_data = build_super_swap_data(SuperSwapDataInput.build(
            quote=quote,
            account=from_chain.signer_address,
            user_ICA=user_ica_address,
            user_ICA_balance=user_ICA_balance,
            origin_domain=origin_domain,
            origin_bridge=from_chain.settings.bridge_contract_addr,
            origin_hook=origin_hook,
            origin_ICA_router=from_chain.settings.interchain_router_contract_addr,
            destination_ICA_router=to_chain.settings.interchain_router_contract_addr,
            destination_router=to_chain.settings.swapper_contract_addr,
            destination_domain=destination_domain,
            slippage=slippage,
            swapper_contract_addr=to_chain.settings.swapper_contract_addr,
            salt=salt if salt else get_salt(),
            bridge_fee=bridge_fee,
            xchain_fee=xchain_fee,
        ))
        origin_planner = setup_planner(
            quote=quote.origin_quote,
            slippage=slippage,
            # money goes to the universal router (aka swapper) for bridging
            account=from_chain.settings.swapper_contract_addr, 
            router_address=from_chain.settings.swapper_contract_addr
        ) if quote.origin_quote else None

        cmds, inputs = "", [] 

        if origin_planner:
            cmds += origin_planner.commands
            inputs.extend(origin_planner.inputs)
        if swap_data.destination_planner:
            cmds += swap_data.destination_planner.commands.replace("0x", "") if cmds != "" else swap_data.destination_planner.commands
            inputs.extend(swap_data.destination_planner.inputs)

        return cmds, inputs, swap_data

    def prepare_write(self, quote: SuperswapQuote, total_fee: int) -> tuple[int, int]:
        value = quote.amount_in
        # TODO: extend this to proper native token support
        message_fee = value + total_fee if quote.from_token.wrapped_token_address else total_fee
        return value, message_fee

class Superswap(SuperswapCommon):
    def __init__(self, relayer: Optional[SuperswapRelayer] = None, chain_for_writes: Optional[Chain] = None):
        """`chain_for_writes` carries the signer for the on-chain ops. If it's a `*ChainSimnet` instance, all
        read-side chain contexts opened internally also bind to supersim (auto-detected via `is_simnet`)."""
        self.chain_for_writes, self.relayer = chain_for_writes, relayer or HTTPSuperswapRelayer()

    @property
    def _chain_factory(self):
        return get_simnet_chain_from_token if getattr(self.chain_for_writes, "is_simnet", False) else get_chain_from_token

    def bridge_from_quote(self, quote: SuperswapQuote) -> SuperswapTxs:
        assert quote.is_bridge, "bridge_from_quote can only be used for bridge quotes"
        self.check_chain_support(quote.from_token, quote.to_token)
        chain = self.chain_for_writes or self._chain_factory(quote.from_token)
        if not chain.signer_address: raise ValueError("Cannot bridge without a signer. Pass signer_address to the chain constructor.")
        from_token, to_token, amount = quote.from_token, quote.to_token, quote.amount_in
        with chain:
            txs = chain._internal_bridge_token(from_token, to_token, amount, get_domain(int(to_token.chain_id)))
            return SuperswapTxs(txs=txs, swap_data=None)

    def swap(self, from_token: Token, to_token: Token, amount: int, slippage: Optional[float] = None) -> SuperswapTxs:
        self.check_chain_support(from_token, to_token)
        quote = self.get_super_quote(from_token=from_token, to_token=to_token, amount=amount)

        if not quote: raise ValueError(f"No quote found for {from_token} -> {to_token}")

        return self.swap_from_quote(quote=quote, slippage=slippage)

    def get_super_quote(self, from_token: Token, to_token: Token, amount: int) -> Optional[SuperswapQuote]:
        q = None
        with self._chain_factory(from_token) as from_chain, self._chain_factory(to_token) as to_chain:
            from_bridge_token, to_bridge_token = from_chain.get_bridge_token(), to_chain.get_bridge_token()

            # are we bridging?
            if from_token == from_bridge_token and to_token == to_bridge_token:
                q = SuperswapQuote.bridge_quote(from_token=from_token, to_token=to_token, amount=amount)       
            else:
                o_q, d_q = None, None
                # we only need origin quote if we don't start with bridge token
                if from_token != from_bridge_token:
                    o_q = from_chain.get_quote(from_token, from_bridge_token, amount=amount)
                    if o_q is None: return None

                # we need destination quote if we don't end with bridge token
                if to_token != to_bridge_token:
                    # include bridge token balance of userICA as superswap will always use any existing bridge token balance as part of the swap
                    destination_domain = get_domain(int(to_chain.chain_id))
                    user_ica_address = from_chain.get_remote_interchain_account(destination_domain)
                    user_ica_bridge_balance = to_chain.get_token_balance(token=to_bridge_token, owner_address=user_ica_address)

                    b_a = SuperswapQuote.calc_bridged_amount(from_token, from_bridge_token, amount, o_q) + user_ica_bridge_balance
                    d_q = to_chain.get_quote(to_bridge_token, to_token, amount=b_a)
                    if d_q is None: return None

                q = SuperswapQuote(from_token=from_token,to_token=to_token, from_bridge_token=from_bridge_token, to_bridge_token=to_bridge_token,
                    amount_in=amount, origin_quote=o_q, destination_quote=d_q)
        return q

    def swap_from_quote(self, quote: SuperswapQuote, slippage: Optional[float] = None, salt: Optional[str] = None) -> SuperswapTxs:
        self.check_chain_support(quote.from_token, quote.to_token)

        if quote.is_bridge: return self.bridge_from_quote(quote)

        from_token, to_token = quote.from_token, quote.to_token
        write_signer = self.chain_for_writes.signer_address if self.chain_for_writes else None

        with self._chain_factory(from_token, signer_address=write_signer) as from_chain, self._chain_factory(to_token) as to_chain:
            if not from_chain.signer_address: raise ValueError("Cannot superswap without a signer. Pass a chain_for_writes with signer_address.")
            
            slippage = slippage if slippage is not None else from_chain.settings.swap_slippage
            
            # TODO: use chain.get_domain() when all chains support domains
            origin_domain = get_domain(int(from_chain.chain_id))
            destination_domain = get_domain(int(to_chain.chain_id))
            user_ica_address= from_chain.get_remote_interchain_account(destination_domain)
            # TODO: switch to get_bridge_fee without explicit domain ID when all chains support domains
            bridge_fee = from_chain.get_bridge_fee(destination_domain)
            xchain_fee = from_chain.get_xchain_fee(destination_domain) if quote.to_token != quote.to_bridge_token else 0           
            total_fee = bridge_fee + xchain_fee

            cmds, inputs, swap_data = self.prepare_super_swap(
                quote,
                from_chain=from_chain, to_chain=to_chain,
                user_ica_address=user_ica_address, user_ICA_balance=to_chain.get_user_ica_balance(user_ica_address),
                origin_domain=origin_domain, destination_domain=destination_domain,
                origin_hook=from_chain.get_ica_hook(),
                slippage=slippage,
                bridge_fee=bridge_fee,
                xchain_fee=xchain_fee,
                salt=salt
            )
            return self.write(quote, cmds=cmds, inputs=inputs, swap_data=swap_data, total_fee=total_fee)

    def write(self, quote: SuperswapQuote, swap_data: SuperSwapData, cmds: str, inputs: List[bytes], total_fee: int) -> SuperswapTxs:
        chain = self.chain_for_writes or self._chain_factory(quote.from_token)
        value, message_fee = self.prepare_write(quote, total_fee)
        with chain:
            approval_tx = chain.set_token_allowance(quote.from_token, chain.settings.swapper_contract_addr, value)
            main = chain.build_tx(chain.swapper.functions.execute(*[cmds, inputs]), value=message_fee)
            txs = [t for t in (approval_tx, main) if t is not None]
            return SuperswapTxs(txs=txs, swap_data=swap_data if swap_data.needs_relay else None)

class AsyncSuperswap(SuperswapCommon):
    def __init__(self, relayer: Optional[SuperswapRelayer] = None, chain_for_writes: Optional[AsyncChain] = None):
        """`chain_for_writes` carries the signer. If it's an `Async*ChainSimnet` instance, all read-side contexts
        opened internally also bind to supersim (auto-detected via `is_simnet`)."""
        self.chain_for_writes, self.relayer = chain_for_writes, relayer or HTTPSuperswapRelayer()

    @property
    def _chain_factory(self):
        return get_async_simnet_chain_from_token if getattr(self.chain_for_writes, "is_simnet", False) else get_async_chain_from_token

    async def bridge_from_quote(self, quote: SuperswapQuote) -> SuperswapTxs:
        assert quote.is_bridge, "bridge_from_quote can only be used for bridge quotes"
        self.check_chain_support(quote.from_token, quote.to_token)
        chain = self.chain_for_writes or self._chain_factory(quote.from_token)
        if not chain.signer_address: raise ValueError("Cannot bridge without a signer. Pass signer_address to the chain constructor.")
        from_token, to_token, amount = quote.from_token, quote.to_token, quote.amount_in
        async with chain:
            txs = await chain._internal_bridge_token(from_token, to_token, amount, await get_domain_async(int(to_token.chain_id)))
            return SuperswapTxs(txs=txs, swap_data=None)

    async def swap(self, from_token: Token, to_token: Token, amount: int, slippage: Optional[float] = None) -> SuperswapTxs:
        self.check_chain_support(from_token, to_token)
        quote = await self.get_super_quote(from_token=from_token, to_token=to_token, amount=amount)

        if not quote: raise ValueError(f"No quote found for {from_token} -> {to_token}")

        return await self.swap_from_quote(quote=quote, slippage=slippage)

    async def get_super_quote(self, from_token: Token, to_token: Token, amount: int) -> Optional[SuperswapQuote]:
        q = None
        async with self._chain_factory(from_token) as from_chain, self._chain_factory(to_token) as to_chain:
            from_bridge_token, to_bridge_token = await from_chain.get_bridge_token(), await to_chain.get_bridge_token()

            # are we bridging?
            if from_token == from_bridge_token and to_token == to_bridge_token:
                q = SuperswapQuote.bridge_quote(from_token=from_token, to_token=to_token, amount=amount)
            else:
                o_q, d_q = None, None
                # we only need origin quote if we don't start with bridge token
                if from_token != from_bridge_token:
                    o_q = await from_chain.get_quote(from_token, from_bridge_token, amount=amount)
                    if o_q is None: return None

                # we need destination quote if we don't end with bridge token
                if to_token != to_bridge_token:
                    # include bridge token balance of userICA as superswap will always use any existing bridge token balance as part of the swap
                    destination_domain = await get_domain_async(int(to_chain.chain_id))
                    user_ica_address = await from_chain.get_remote_interchain_account(destination_domain)
                    user_ica_bridge_balance = await to_chain.get_token_balance(token=to_bridge_token, owner_address=user_ica_address)

                    b_a = SuperswapQuote.calc_bridged_amount(from_token, from_bridge_token, amount, o_q) + user_ica_bridge_balance
                    d_q = await to_chain.get_quote(to_bridge_token, to_token, amount=b_a)
                    if d_q is None: return None

                q = SuperswapQuote(from_token=from_token, to_token=to_token, from_bridge_token=from_bridge_token, to_bridge_token=to_bridge_token,
                    amount_in=amount, origin_quote=o_q, destination_quote=d_q)

        return q

    async def swap_from_quote(self, quote: SuperswapQuote, slippage: Optional[float] = None, salt: Optional[str] = None) -> SuperswapTxs:
        self.check_chain_support(quote.from_token, quote.to_token)

        if quote.is_bridge: return await self.bridge_from_quote(quote)

        from_token, to_token = quote.from_token, quote.to_token
        write_signer = self.chain_for_writes.signer_address if self.chain_for_writes else None

        async with self._chain_factory(from_token, signer_address=write_signer) as from_chain, self._chain_factory(to_token) as to_chain:
            if not from_chain.signer_address: raise ValueError("Cannot superswap without a signer. Pass a chain_for_writes with signer_address.")
            
            slippage = slippage if slippage is not None else from_chain.settings.swap_slippage
            
            # TODO: use chain.get_domain() when all chains support domains
            origin_domain = await get_domain_async(int(from_chain.chain_id))
            destination_domain = await get_domain_async(int(to_chain.chain_id))
            user_ica_address = await from_chain.get_remote_interchain_account(destination_domain)
            # TODO: switch to get_bridge_fee without explicit domain ID when all chains support domains
            bridge_fee = await from_chain.get_bridge_fee(destination_domain)
            xchain_fee = await from_chain.get_xchain_fee(destination_domain) if quote.to_token != quote.to_bridge_token else 0
            total_fee = bridge_fee + xchain_fee

            cmds, inputs, swap_data = self.prepare_super_swap(
                quote,
                from_chain=from_chain, to_chain=to_chain,
                user_ica_address=user_ica_address, user_ICA_balance=await to_chain.get_user_ica_balance(user_ica_address),
                origin_domain=origin_domain, destination_domain=destination_domain,
                origin_hook=await from_chain.get_ica_hook(),
                slippage=slippage,
                bridge_fee=bridge_fee,
                xchain_fee=xchain_fee,
                salt=salt
            )

            return await self.write(quote, cmds=cmds, inputs=inputs, swap_data=swap_data, total_fee=total_fee)

    async def write(self, quote: SuperswapQuote, swap_data: SuperSwapData, cmds: str, inputs: List[bytes], total_fee: int) -> SuperswapTxs:
        chain = self.chain_for_writes or self._chain_factory(quote.from_token)
        value, message_fee = self.prepare_write(quote, total_fee)
        async with chain:
            approval_tx = await chain.set_token_allowance(quote.from_token, chain.settings.swapper_contract_addr, value)
            main = chain.build_tx(chain.swapper.functions.execute(*[cmds, inputs]), value=message_fee)
            txs = [t for t in (approval_tx, main) if t is not None]
            return SuperswapTxs(txs=txs, swap_data=swap_data if swap_data.needs_relay else None)
