from typing import Any


from sugar.config import make_base_chain_settings, make_op_chain_settings


def test_settings_basic():
    def no_env(key: str, default: Any) -> Any: return default

    op_settings = make_op_chain_settings(get_env=no_env)
    base_settings = make_base_chain_settings(get_env=no_env)

    assert op_settings.chain_id == "10"
    assert "optimism" in op_settings.rpc_uri
    assert type(op_settings.connector_tokens_addrs) is list
    assert len(op_settings.connector_tokens_addrs) > 1
    assert type(op_settings.excluded_tokens_addrs) is list
    assert len(op_settings.excluded_tokens_addrs) > 1
    assert op_settings.chain_id != base_settings.chain_id
    assert op_settings.swap_slippage == 0.01


def test_settings_env_overrides():
    def env(key: str, default: Any) -> Any:
        return {
            "SUGAR_RPC_URI_10": "https://super-optimism-mainnet.wallet.coinbase.com",
            "SUGAR_SWAP_SLIPPAGE_10": "0.05",
        }.get(key, default)

    op_settings = make_op_chain_settings(get_env=env)
    assert op_settings.rpc_uri == "https://super-optimism-mainnet.wallet.coinbase.com"
    assert op_settings.swap_slippage == 0.05

    op_settings = make_op_chain_settings(get_env=env, rpc_uri="https://mirror-optimism-mainnet.wallet.coinbase.com")
    assert op_settings.rpc_uri == "https://mirror-optimism-mainnet.wallet.coinbase.com"
    assert type(op_settings.connector_tokens_addrs) is list
    assert len(op_settings.connector_tokens_addrs) > 1

    s = make_op_chain_settings(get_env=env, swap_slippage=0.1, hello="word")
    assert not hasattr(s, "hello")
