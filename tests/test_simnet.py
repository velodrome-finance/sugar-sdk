import asyncio
import os

import pytest
from eth_account import Account

from sugar import LiskChain, UniChain
from sugar.chains import (
    AsyncBaseChain,
    AsyncLiskChainSimnet,
    AsyncOPChain,
    LiskChainSimnet,
    get_async_simnet_chain_from_token,
    get_simnet_chain_from_token,
)
from sugar.superswap import AsyncSuperswap, MockSuperswapRelayer, Superswap

from tests._signer import sign_and_broadcast


pytestmark = pytest.mark.supersim


# Wallet derived from SUGAR_PK (same key as honey.yaml wallet so funding lines up).
HONEY_PK = os.environ["SUGAR_PK"]
HONEY_WALLET = Account.from_key(HONEY_PK).address


# All specs source from Lisk (the chain honey can seed reliably). Uni is destination-only — Uni-side
# ERC20 funding is hard without anvil_setStorageAt, so we avoid Uni-source swaps. The reverse-direction
# bridge case (Uni→Lisk) is symmetric on-chain to the Lisk→Uni one we cover; the SDK paths it exercises
# are identical, just with bridge contract addresses flipped.
_SUPERSWAP_SPECS = [
    # native ETH → native ETH (anvil-funded both sides; no token seed needed)
    (LiskChain.eth, UniChain.eth, LiskChain.eth.parse_units(0.001), True),
    # ERC20 → non-bridge ERC20 (relay needed for destination swap)
    (LiskChain.lsk, UniChain.usdc, LiskChain.lsk.parse_units(10), True),
    # ERC20 → bridge ERC20 (no relay; destination is the bridge token itself)
    (LiskChain.lsk, UniChain.o_usdt, LiskChain.lsk.parse_units(10), False),
    # bridge token → bridge token (pure bridge path, no relay)
    (LiskChain.o_usdt, UniChain.o_usdt, LiskChain.o_usdt.parse_units(10), False),
]


def test_token_balances_async():
    """Canary: honey provisioned the simnet wallet with LSK + ETH. Floor is "non-zero" — earlier swap broadcasts in the same supersim session can deplete the original 1000-LSK seed."""
    async def run():
        async with AsyncLiskChainSimnet(signer_address=HONEY_WALLET) as simnet:
            assert await simnet.get_token_balance(AsyncLiskChainSimnet.lsk) > 0
            assert await simnet.get_token_balance(AsyncLiskChainSimnet.eth) > 0
    asyncio.run(run())


def test_token_balances_sync():
    with LiskChainSimnet(signer_address=HONEY_WALLET) as simnet:
        assert simnet.get_token_balance(LiskChainSimnet.lsk) > 0
        assert simnet.get_token_balance(LiskChainSimnet.eth) > 0


def test_unsupported_chain_pair():
    """SDK guard test — Superswap raises on unsupported chain pairs (Base isn't in supported_chains)."""
    with LiskChainSimnet(signer_address=HONEY_WALLET) as lisk_sim:
        with pytest.raises(ValueError, match="Superswap only supports"):
            Superswap(chain_for_writes=lisk_sim, relayer=MockSuperswapRelayer()).swap(
                AsyncOPChain.velo, AsyncBaseChain.aero, amount=AsyncOPChain.velo.parse_units(20)
            )


@pytest.mark.parametrize(
    "from_token,to_token,amount,requires_relay",
    _SUPERSWAP_SPECS,
    ids=[f"{ft.chain_name}.{ft.symbol}->{tt.chain_name}.{tt.symbol}" for ft, tt, _, _ in _SUPERSWAP_SPECS],
)
def test_superswap_sync(from_token, to_token, amount, requires_relay):
    with get_simnet_chain_from_token(from_token, signer_address=HONEY_WALLET) as from_sim:
        relayer = MockSuperswapRelayer()
        plan = Superswap(chain_for_writes=from_sim, relayer=relayer).swap(
            from_token, to_token, amount=amount, slippage=0.1
        )
        tx_hashes = sign_and_broadcast(plan.txs, HONEY_PK, from_sim.settings.rpc_uri)
        assert (plan.swap_data is not None) == requires_relay
        if plan.swap_data is not None:
            relayer.share_calls(**plan.relay_kwargs(commitment_dispatch_tx=tx_hashes[-1]))
            assert relayer.get_call_count() == 1
        else:
            assert relayer.get_call_count() == 0


def test_superswap_async():
    """One async broadcast end-to-end — proves the AsyncSuperswap event-loop wiring. Sync path
    above covers the spec matrix; async shares all logic via SuperswapCommon and just adds awaits."""
    from_token, to_token, amount = LiskChain.lsk, UniChain.usdc, LiskChain.lsk.parse_units(10)

    async def run():
        async with get_async_simnet_chain_from_token(from_token, signer_address=HONEY_WALLET) as from_sim:
            relayer = MockSuperswapRelayer()
            plan = await AsyncSuperswap(chain_for_writes=from_sim, relayer=relayer).swap(
                from_token, to_token, amount=amount, slippage=0.1
            )
            tx_hashes = sign_and_broadcast(plan.txs, HONEY_PK, from_sim.settings.rpc_uri)
            assert plan.swap_data is not None  # this spec needs relay
            relayer.share_calls(**plan.relay_kwargs(commitment_dispatch_tx=tx_hashes[-1]))
            assert relayer.get_call_count() == 1
    asyncio.run(run())
