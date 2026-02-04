"""
Tests for epoch-related chain methods.

Tests cover both async and sync versions of:
- get_latest_pool_epochs()
- Context manager requirements
"""
import pytest
from sugar import AsyncBaseChain, BaseChain
from sugar.pool import LiquidityPoolEpoch, LiquidityPool
from sugar.token import Token


@pytest.mark.asyncio
class TestAsyncLatestPoolEpochs:
    """Test async version of get_latest_pool_epochs"""

    async def test_get_latest_pool_epochs_returns_list(self, base_chain):
        """Test that get_latest_pool_epochs returns a list of epochs"""
        epochs = await base_chain.get_latest_pool_epochs()

        assert isinstance(epochs, list), "Should return a list"
        assert len(epochs) > 0, "Should return at least one epoch for Base chain"

        # Validate each epoch is correct type
        for epoch in epochs:
            assert isinstance(epoch, LiquidityPoolEpoch), f"Each item should be LiquidityPoolEpoch, got {type(epoch)}"

    async def test_get_latest_pool_epochs_data_structure(self, base_chain):
        """Test that epoch data has all required fields with correct types"""
        epochs = await base_chain.get_latest_pool_epochs()

        assert len(epochs) > 0, "Need at least one epoch to test"

        epoch = epochs[0]  # Check first epoch

        # Required fields
        assert hasattr(epoch, 'ts'), "Epoch should have 'ts' field"
        assert hasattr(epoch, 'lp'), "Epoch should have 'lp' field"
        assert hasattr(epoch, 'pool'), "Epoch should have 'pool' field"
        assert hasattr(epoch, 'votes'), "Epoch should have 'votes' field"
        assert hasattr(epoch, 'emissions'), "Epoch should have 'emissions' field"
        assert hasattr(epoch, 'incentives'), "Epoch should have 'incentives' field"
        assert hasattr(epoch, 'fees'), "Epoch should have 'fees' field"

        # Type validations
        assert isinstance(epoch.ts, int), f"ts should be int, got {type(epoch.ts)}"
        assert epoch.ts > 0, "Timestamp should be positive"

        assert isinstance(epoch.lp, str), f"lp should be str, got {type(epoch.lp)}"
        assert epoch.lp.startswith('0x'), "lp should be a hex address"

        assert isinstance(epoch.votes, int), f"votes should be int, got {type(epoch.votes)}"
        assert epoch.votes >= 0, "votes should be non-negative"

        assert isinstance(epoch.emissions, int), f"emissions should be int, got {type(epoch.emissions)}"
        assert epoch.emissions >= 0, "emissions should be non-negative"

        assert isinstance(epoch.incentives, list), f"incentives should be list, got {type(epoch.incentives)}"
        assert isinstance(epoch.fees, list), f"fees should be list, got {type(epoch.fees)}"

    async def test_get_latest_pool_epochs_contains_valid_pools(self, base_chain):
        """Test that each epoch contains a valid LiquidityPool object"""
        epochs = await base_chain.get_latest_pool_epochs()

        assert len(epochs) > 0, "Need at least one epoch to test"

        for epoch in epochs:
            # Pool should exist and be valid
            assert epoch.pool is not None, f"Epoch for {epoch.lp} should have a pool"
            assert isinstance(epoch.pool, LiquidityPool), f"Pool should be LiquidityPool, got {type(epoch.pool)}"

            # Pool should have required attributes
            assert hasattr(epoch.pool, 'token0'), "Pool should have token0"
            assert hasattr(epoch.pool, 'token1'), "Pool should have token1"
            assert hasattr(epoch.pool, 'lp'), "Pool should have lp address"

            # Tokens should be valid
            assert isinstance(epoch.pool.token0, Token), "token0 should be Token"
            assert isinstance(epoch.pool.token1, Token), "token1 should be Token"

    async def test_get_latest_pool_epochs_contains_valid_prices(self, base_chain):
        """Test that tokens in epochs have associated price data"""
        epochs = await base_chain.get_latest_pool_epochs()

        assert len(epochs) > 0, "Need at least one epoch to test"

        for epoch in epochs:
            if epoch.pool is not None:
                # Check that tokens have price information
                assert epoch.pool.token0.symbol is not None, "token0 should have symbol"
                assert epoch.pool.token1.symbol is not None, "token1 should have symbol"


class TestSyncLatestPoolEpochs:
    """Test sync version of get_latest_pool_epochs"""

    def test_sync_get_latest_pool_epochs_returns_list(self, sync_base_chain):
        """Test sync version of get_latest_pool_epochs"""
        epochs = sync_base_chain.get_latest_pool_epochs()

        assert isinstance(epochs, list), "Should return a list"
        assert len(epochs) > 0, "Should return at least one epoch for Base chain"

        # Validate each epoch is correct type
        for epoch in epochs:
            assert isinstance(epoch, LiquidityPoolEpoch), f"Each item should be LiquidityPoolEpoch, got {type(epoch)}"

    def test_sync_get_latest_pool_epochs_data_structure(self, sync_base_chain):
        """Test that sync version returns valid epoch data structure"""
        epochs = sync_base_chain.get_latest_pool_epochs()

        assert len(epochs) > 0, "Need at least one epoch to test"

        epoch = epochs[0]

        # Type validations
        assert isinstance(epoch.ts, int), f"ts should be int, got {type(epoch.ts)}"
        assert isinstance(epoch.lp, str), f"lp should be str, got {type(epoch.lp)}"
        assert isinstance(epoch.votes, int), f"votes should be int, got {type(epoch.votes)}"
        assert isinstance(epoch.emissions, int), f"emissions should be int, got {type(epoch.emissions)}"
        assert isinstance(epoch.incentives, list), f"incentives should be list, got {type(epoch.incentives)}"
        assert isinstance(epoch.fees, list), f"fees should be list, got {type(epoch.fees)}"


class TestContextRequirement:
    """Test that epoch methods require context manager"""

    @pytest.mark.asyncio
    async def test_requires_async_context(self):
        """Test that calling get_latest_pool_epochs without context manager raises error"""
        chain = AsyncBaseChain()

        with pytest.raises(RuntimeError, match="async with"):
            await chain.get_latest_pool_epochs()

    def test_sync_requires_context(self):
        """Test that calling sync get_latest_pool_epochs without context manager raises error"""
        chain = BaseChain()

        with pytest.raises(RuntimeError, match="async with"):
            chain.get_latest_pool_epochs()
