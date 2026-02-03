"""
Basic integration tests for Base chain.

Tests use real RPC calls - requires SUGAR_RPC_URI_8453 in .env
"""
import pytest


@pytest.mark.asyncio
class TestBaseChain:
    """Basic tests for Base chain"""

    async def test_get_all_tokens(self, base_chain):
        """Test fetching all tokens from Base chain"""
        tokens = await base_chain.get_all_tokens()

        # Verify we got token data
        assert isinstance(tokens, list)
        assert len(tokens) > 0

        # Check first token structure
        token = tokens[0]
        assert hasattr(token, 'token_address')
        assert hasattr(token, 'symbol')
        assert hasattr(token, 'decimals')

        print(f"Fetched {len(tokens)} tokens from Base chain")

    async def test_get_pools(self, base_chain):
        """Test fetching all pools from Base chain"""
        pools = await base_chain.get_pools()

        # Verify we got pool data
        assert isinstance(pools, list)
        assert len(pools) > 0

        # Verify Base has many pools (validates Phase 1 fix)
        assert len(pools) > 2500, f"Should fetch more than 2500 pools, got {len(pools)}"

        # Check first pool structure
        pool = pools[0]
        assert hasattr(pool, 'lp')
        assert hasattr(pool, 'symbol')
        assert hasattr(pool, 'token0')
        assert hasattr(pool, 'token1')

        print(f"✓ Fetched {len(pools)} pools from Base chain (validates Phase 1 fix)")
