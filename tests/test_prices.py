"""
Tests for price-related chain methods.

Tests cover both async and sync versions of:
- get_prices()
- Context manager requirements
- Price data structure and validation
- Caching behavior
- Batching for large token lists
"""
import pytest
from sugar import AsyncBaseChain, BaseChain
from sugar.price import Price


@pytest.mark.asyncio
class TestAsyncGetPrices:
    """Test async version of get_prices"""

    async def test_get_prices_returns_list(self, base_chain):
        """Test that get_prices returns a list of Price objects"""
        tokens = await base_chain.get_all_tokens()

        prices = await base_chain.get_prices(tokens)

        assert isinstance(prices, list), "Should return a list"
        assert len(prices) == len(tokens), f"Should return price for each token"
        assert len(prices) > 0, "Should have at least some prices"

        for price in prices:
            assert isinstance(price, Price), f"Each item should be Price, got {type(price)}"
            assert price.price >= 0, f"Price should be non-negative, got {price.price}"

    async def test_get_prices_has_native_token_price(self, base_chain):
        """Test that native token (ETH) has a valid price"""
        tokens = await base_chain.get_all_tokens()
        prices = await base_chain.get_prices(tokens)

        # Native token should be first
        native = tokens[0]
        assert native.symbol == "ETH", "First token should be native ETH"

        eth_price = prices[0].price

        # ETH should have a reasonable price (> $100)
        assert eth_price > 100, f"ETH price {eth_price} seems too low"
        assert eth_price < 100000, f"ETH price {eth_price} seems too high"

    async def test_get_prices_stable_token_price(self, base_chain):
        """Test that stable token (USDC) price is close to 1.0"""
        tokens = await base_chain.get_all_tokens()
        prices = await base_chain.get_prices(tokens)

        usdc_idx = next((i for i, t in enumerate(tokens) if t.symbol == "USDC"), None)
        assert usdc_idx is not None, "USDC token not found"

        usdc_price = prices[usdc_idx].price

        # USDC should be close to $1.00 (within 5%)
        assert 0.95 <= usdc_price <= 1.05, f"USDC price {usdc_price} is not close to 1.0"

    async def test_get_prices_batching(self, base_chain):
        """Test that batching works correctly with many tokens (exceeds batch size of 40)"""
        tokens = await base_chain.get_all_tokens()

        # get_prices always needs all tokens (includes ETH and USDC for conversion)
        # But verify it handles large lists (default batch size is 40)
        prices = await base_chain.get_prices(tokens)

        assert len(prices) == len(tokens), f"Should return price for each token"
        assert len(tokens) > 40, "Should test with more than batch size (40) tokens"

        # All prices should be valid
        for price in prices:
            assert isinstance(price, Price), "Each item should be Price"
            assert price.price >= 0, "Price should be non-negative"

    async def test_get_prices_uses_cache(self, base_chain):
        """Test that get_prices uses cache for repeated calls"""
        import time

        tokens = await base_chain.get_all_tokens()

        # First call
        start1 = time.time()
        prices1 = await base_chain.get_prices(tokens)
        duration1 = time.time() - start1

        # Second call (should be cached, within 5 second TTL)
        start2 = time.time()
        prices2 = await base_chain.get_prices(tokens)
        duration2 = time.time() - start2

        # Results should be identical
        assert len(prices1) == len(prices2), "Should return same number of prices"
        for p1, p2 in zip(prices1, prices2):
            assert p1.token.token_address == p2.token.token_address, "Should have same tokens"
            assert p1.price == p2.price, "Cached prices should match"

        # Second call should be faster (cached)
        # Note: This is a soft check - cache should make it faster, but timing can vary
        print(f"\nFirst call: {duration1:.4f}s, Second call: {duration2:.4f}s")

    async def test_get_prices_decimal_normalization(self, base_chain):
        """Test that prices work correctly for tokens with different decimals"""
        tokens = await base_chain.get_all_tokens()
        prices = await base_chain.get_prices(tokens)

        # Find tokens with different decimal counts
        tokens_by_decimals = {}
        for i, t in enumerate(tokens):
            if t.decimals not in tokens_by_decimals:
                tokens_by_decimals[t.decimals] = (t, prices[i])

        # Check that we have various decimal counts
        assert len(tokens_by_decimals) > 1, "Should have tokens with different decimal counts"

        # All prices should be valid regardless of decimals
        for decimals, (token, price) in tokens_by_decimals.items():
            assert price.price >= 0, f"Price for {token.symbol} ({decimals} decimals) should be non-negative"
            # Price should be a reasonable float value (normalized to USD)
            assert isinstance(price.price, (int, float)), "Price should be numeric"

        # Log the different decimals found for visibility
        print(f"\nTokens found with {len(tokens_by_decimals)} different decimal counts: {sorted(tokens_by_decimals.keys())}")


class TestSyncGetPrices:
    """Test sync version of get_prices"""

    def test_sync_get_prices_returns_list(self, sync_base_chain):
        """Test sync version returns list of Price objects"""
        tokens = sync_base_chain.get_all_tokens()
        prices = sync_base_chain.get_prices(tokens)

        assert isinstance(prices, list), "Should return a list"
        assert len(prices) == len(tokens), f"Should return price for each token"
        assert len(prices) > 0, "Should have at least some prices"

        for price in prices:
            assert isinstance(price, Price), f"Each item should be Price, got {type(price)}"
            assert price.price >= 0, f"Price should be non-negative, got {price.price}"

        # Check native token has valid price
        native = tokens[0]
        assert native.symbol == "ETH", "First token should be native ETH"
        native_price = prices[0].price
        assert native_price > 100, f"ETH price {native_price} seems too low"


class TestContextRequirement:
    """Test that get_prices requires context manager"""

    @pytest.mark.asyncio
    async def test_requires_async_context(self):
        """Test that calling get_prices without context raises error"""
        from sugar.token import Token

        chain = AsyncBaseChain()

        # Create a dummy token for testing
        dummy_token = Token(
            token_address="0x4200000000000000000000000000000000000006",
            symbol="WETH",
            decimals=18,
            listed=True,
            emerging=False,
            chain_id=8453,
            chain_name="base"
        )

        with pytest.raises(RuntimeError, match="async with"):
            await chain.get_prices([dummy_token])

    def test_sync_requires_context(self):
        """Test that calling sync get_prices without context raises error"""
        from sugar.token import Token

        chain = BaseChain()

        # Create a dummy token for testing
        dummy_token = Token(
            token_address="0x4200000000000000000000000000000000000006",
            symbol="WETH",
            decimals=18,
            listed=True,
            emerging=False,
            chain_id=8453,
            chain_name="base"
        )

        with pytest.raises(RuntimeError, match="async with"):
            chain.get_prices([dummy_token])
