"""
Tests for Phase 2: Adaptive Batch Sizing

Tests the calculate_optimal_batch_size() method and updated pagination logic.
"""
import pytest
from sugar.config import make_base_chain_settings
from sugar.chains import CommonChain


class TestAdaptiveBatchSizing:
    """Tests for adaptive batch size calculation"""

    def test_calculate_optimal_batch_size_small_chain(self):
        """Test optimal batch size for small chains (e.g., Lisk with ~100 pools)"""
        settings = make_base_chain_settings()
        chain = CommonChain(settings)

        # Small chain: 100 pools
        # 100 / 90 = 1.11, clamped to min_size (10)
        optimal = chain.calculate_optimal_batch_size(100)
        assert optimal == 10, f"Small chain should use min_size (10), got {optimal}"

    def test_calculate_optimal_batch_size_medium_chain(self):
        """Test optimal batch size for medium chains (e.g., OP with ~2500 pools)"""
        settings = make_base_chain_settings()
        chain = CommonChain(settings)

        # Medium chain: 2500 pools
        # 2500 / 90 = 27.77 = 27
        optimal = chain.calculate_optimal_batch_size(2500)
        assert optimal == 27, f"Medium chain should use ~27, got {optimal}"
        assert 10 <= optimal <= 300, "Should be within min/max bounds"

    def test_calculate_optimal_batch_size_large_chain(self):
        """Test optimal batch size for large chains (e.g., Base with ~9000 pools)"""
        settings = make_base_chain_settings()
        chain = CommonChain(settings)

        # Large chain: 9000 pools
        # 9000 / 90 = 100, but clamped to max_size (300)
        optimal = chain.calculate_optimal_batch_size(9000)
        assert optimal == 100, f"Large chain should use 100, got {optimal}"

    def test_calculate_optimal_batch_size_very_large_chain(self):
        """Test optimal batch size caps at max_size for very large chains"""
        settings = make_base_chain_settings()
        chain = CommonChain(settings)

        # Very large chain: 30000 pools
        # 30000 / 90 = 333, clamped to max_size (300)
        optimal = chain.calculate_optimal_batch_size(30000)
        assert optimal == 300, f"Very large chain should use max_size (300), got {optimal}"

    def test_calculate_optimal_batch_size_targets_90_calls(self):
        """Test that optimal sizing targets approximately 90 calls"""
        settings = make_base_chain_settings()
        chain = CommonChain(settings)

        # For 8100 pools: 8100 / 90 = 90 pools per batch
        optimal = chain.calculate_optimal_batch_size(8100)
        num_calls = 8100 / optimal
        assert 80 <= num_calls <= 100, f"Should target ~90 calls, got {num_calls}"

    def test_get_pool_paginator_uses_optimal_sizing(self):
        """Test that get_pool_paginator uses optimal sizing when pool_count provided"""
        settings = make_base_chain_settings()
        chain = CommonChain(settings)

        # With 2700 pools: optimal = 2700 / 90 = 30
        batches = list(chain.get_pool_paginator(batch_size=1, pool_count=2700, use_optimal_sizing=True))

        # Extract all (offset, limit) tuples
        all_tuples = batches[0]

        # Check that limit is 30 (optimal) not 500 (default pool_page_size)
        first_offset, first_limit = all_tuples[0]
        assert first_limit == 30, f"Should use optimal size (30), got {first_limit}"

    def test_get_pool_paginator_backwards_compatible(self):
        """Test that use_optimal_sizing=False uses old pool_page_size"""
        settings = make_base_chain_settings()
        chain = CommonChain(settings)

        # With optimal sizing disabled, should use pool_page_size (500)
        batches = list(chain.get_pool_paginator(batch_size=1, pool_count=2700, use_optimal_sizing=False))

        all_tuples = batches[0]
        first_offset, first_limit = all_tuples[0]
        assert first_limit == 500, f"Should use pool_page_size (500), got {first_limit}"

    def test_get_pool_paginator_without_pool_count_uses_defaults(self):
        """Test that paginator without pool_count uses default settings"""
        settings = make_base_chain_settings()
        chain = CommonChain(settings)

        # Without pool_count, should use pool_page_size regardless of use_optimal_sizing
        batches = list(chain.get_pool_paginator(batch_size=1, pool_count=None, use_optimal_sizing=True))

        all_tuples = batches[0]
        first_offset, first_limit = all_tuples[0]
        assert first_limit == 500, f"Without pool_count, should use pool_page_size (500), got {first_limit}"

    def test_optimal_sizing_reduces_calls_for_large_chains(self):
        """Test that optimal sizing reduces number of RPC calls for large chains"""
        settings = make_base_chain_settings()
        chain = CommonChain(settings)

        # Base chain: ~9000 pools
        # Old way: 9000 / 500 = 18 calls
        # New way: 9000 / 100 = 90 calls (actually more efficient use of multicall)
        batches_old = list(chain.get_pool_paginator(batch_size=1, pool_count=9000, use_optimal_sizing=False))
        batches_new = list(chain.get_pool_paginator(batch_size=1, pool_count=9000, use_optimal_sizing=True))

        old_limit = batches_old[0][0][1]
        new_limit = batches_new[0][0][1]

        assert new_limit < old_limit, f"Optimal sizing should adjust batch size: {new_limit} vs {old_limit}"
        assert new_limit == 100, f"For 9000 pools, optimal should be 100, got {new_limit}"

    def test_optimal_sizing_increases_batch_for_small_chains(self):
        """Test that optimal sizing uses minimum for very small chains"""
        settings = make_base_chain_settings()
        chain = CommonChain(settings)

        # Small chain: 50 pools
        # 50 / 90 = 0.55, but clamped to min_size (10)
        optimal = chain.calculate_optimal_batch_size(50)
        assert optimal == 10, f"Should use min_size for very small chains, got {optimal}"
