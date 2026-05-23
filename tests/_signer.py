"""Test-only signer. Signs each unsigned tx dict and broadcasts in order, waiting on each receipt.
The SDK itself never sees a private key — production callers sign outside the SDK boundary."""
from typing import Dict, List

from eth_account import Account
from web3 import HTTPProvider, Web3


def sign_and_broadcast(txs: List[Dict], private_key: str, rpc_url: str, timeout: int = 60) -> List[str]:
    acct = Account.from_key(private_key)
    w3 = Web3(HTTPProvider(rpc_url))
    if not w3.is_connected(): raise RuntimeError(f"could not connect to {rpc_url}")
    chain_id = w3.eth.chain_id
    hashes: List[str] = []
    for unsigned in txs:
        tx = {
            "from": acct.address,
            "to": Web3.to_checksum_address(unsigned["to"]),
            "data": unsigned["data"],
            "value": int(unsigned["value"]),
            "nonce": w3.eth.get_transaction_count(acct.address),
            "chainId": chain_id,
            "gasPrice": Web3.to_wei(1, "gwei"),
        }
        tx["gas"] = w3.eth.estimate_gas(tx)
        signed = acct.sign_transaction(tx)
        h = w3.eth.send_raw_transaction(signed.raw_transaction)
        hashes.append(h.to_0x_hex())
        receipt = w3.eth.wait_for_transaction_receipt(h, timeout=timeout)
        if receipt.status != 1: raise RuntimeError(f"tx {hashes[-1]} reverted (status=0)")
    return hashes
