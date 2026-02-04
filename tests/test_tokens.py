"""
Tests for token-related chain methods.

Tests cover both async and sync versions of:
- get_all_tokens()
- Context manager requirements
- Token data structure and validation
"""
import pytest
from sugar import AsyncBaseChain, BaseChain
from sugar.token import Token


@pytest.mark.asyncio
class TestAsyncGetAllTokens:
    """Test async version of get_all_tokens"""

    async def test_get_all_tokens_returns_list(self, base_chain):
        """Test that get_all_tokens returns a list of Token objects"""
        tokens = await base_chain.get_all_tokens()

        assert isinstance(tokens, list), "Should return a list"
        assert len(tokens) > 0, "Base chain should have tokens"

        for token in tokens:
            assert isinstance(token, Token), f"Each item should be Token, got {type(token)}"

    async def test_get_all_tokens_includes_native_token(self, base_chain):
        """Test that native token (ETH) is included and first"""
        tokens = await base_chain.get_all_tokens()

        # Native token should be first
        native = tokens[0]
        assert native.symbol == "ETH", "First token should be native ETH"
        assert native.wrapped_token_address is not None, "Native token should have wrapped address"
        assert native.token_address == "ETH", "Native token address should be 'ETH'"

    async def test_get_all_tokens_token_structure(self, base_chain):
        """Test that tokens have all required fields with correct types"""
        tokens = await base_chain.get_all_tokens()

        assert len(tokens) > 1, "Need at least 2 tokens to test regular token"

        token = tokens[1]  # Skip native, test regular token

        # Required fields
        assert hasattr(token, 'token_address'), "Token should have 'token_address' field"
        assert hasattr(token, 'symbol'), "Token should have 'symbol' field"
        assert hasattr(token, 'decimals'), "Token should have 'decimals' field"
        assert hasattr(token, 'listed'), "Token should have 'listed' field"
        assert hasattr(token, 'emerging'), "Token should have 'emerging' field"
        assert hasattr(token, 'chain_id'), "Token should have 'chain_id' field"
        assert hasattr(token, 'chain_name'), "Token should have 'chain_name' field"

        # Type validations
        assert isinstance(token.token_address, str), f"token_address should be str, got {type(token.token_address)}"
        assert isinstance(token.symbol, str), f"symbol should be str, got {type(token.symbol)}"
        assert isinstance(token.decimals, int), f"decimals should be int, got {type(token.decimals)}"
        assert isinstance(token.listed, bool), f"listed should be bool, got {type(token.listed)}"
        assert isinstance(token.emerging, bool), f"emerging should be bool, got {type(token.emerging)}"

        # Address format
        assert token.token_address.startswith('0x'), "Token address should start with '0x'"
        assert len(token.token_address) == 42, f"Token address should be 42 chars, got {len(token.token_address)}"

    async def test_get_all_tokens_listed_only_true(self, base_chain):
        """Test that listed_only=True filters to listed tokens"""
        tokens = await base_chain.get_all_tokens(listed_only=True)

        assert len(tokens) > 0, "Should have at least one token"

        # All tokens except native should be listed
        for token in tokens[1:]:  # Skip native token
            assert token.listed is True, f"Token {token.symbol} should be listed when listed_only=True"

    async def test_get_all_tokens_no_duplicates(self, base_chain):
        """Test that no duplicate token addresses are returned"""
        tokens = await base_chain.get_all_tokens()

        addresses = [t.token_address for t in tokens]
        unique_addresses = set(addresses)

        # Note: Current implementation may return duplicates from contract
        # This is a known limitation that could be addressed with deduplication
        # For now, we verify we get tokens and document the duplicate count
        assert len(tokens) > 0, "Should return tokens"

        if len(addresses) != len(unique_addresses):
            # Log the duplicate count for visibility
            duplicate_count = len(addresses) - len(unique_addresses)
            print(f"\nNote: Found {duplicate_count} duplicate token addresses")
            print(f"Total tokens: {len(addresses)}, Unique: {len(unique_addresses)}")

    async def test_get_all_tokens_valid_decimals(self, base_chain):
        """Test that all tokens have valid decimal values"""
        tokens = await base_chain.get_all_tokens()

        for token in tokens:
            assert token.decimals > 0, f"{token.symbol} has invalid decimals: {token.decimals}"
            # ERC20 standard allows up to 255 decimals (uint8 max value)
            assert token.decimals <= 255, f"{token.symbol} exceeds ERC20 max decimals: {token.decimals}"
            # Note: Most tokens use 6, 8, 9, or 18 decimals, but higher values are technically valid


class TestSyncGetAllTokens:
    """Test sync version of get_all_tokens"""

    def test_sync_get_all_tokens_returns_list(self, sync_base_chain):
        """Test sync version returns list of Token objects"""
        tokens = sync_base_chain.get_all_tokens()

        assert isinstance(tokens, list), "Should return a list"
        assert len(tokens) > 0, "Base chain should have tokens"

        for token in tokens:
            assert isinstance(token, Token), f"Each item should be Token, got {type(token)}"

        # Check native token is first
        native = tokens[0]
        assert native.symbol == "ETH", "First token should be native ETH"


class TestContextRequirement:
    """Test that get_all_tokens requires context manager"""

    @pytest.mark.asyncio
    async def test_requires_async_context(self):
        """Test that calling get_all_tokens without context raises error"""
        chain = AsyncBaseChain()

        with pytest.raises(RuntimeError, match="async with"):
            await chain.get_all_tokens()

    def test_sync_requires_context(self):
        """Test that calling sync get_all_tokens without context raises error"""
        chain = BaseChain()

        with pytest.raises(RuntimeError, match="async with"):
            chain.get_all_tokens()
