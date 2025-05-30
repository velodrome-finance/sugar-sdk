#!/usr/bin/env python3
"""
Quick test script to verify chain method benchmarking works.

This script runs a subset of methods to quickly verify the benchmarking setup
before running the full comprehensive tests.
"""

import asyncio
import time
from sugar.chains import AsyncOPChain, OPChain
from sugar.helpers import time_it, atime_it


async def test_async_methods():
    """Test key async methods with timing"""
    print("🔍 Testing Async OP Chain Methods")
    print("-" * 40)
    
    async with AsyncOPChain() as chain:
        # Test get_all_tokens
        async with atime_it("get_all_tokens"):
            tokens = await chain.get_all_tokens()
        print(f"   Found {len(tokens)} tokens")
        
        # Test get_prices
        async with atime_it("get_prices"):
            prices = await chain.get_prices(tokens[:10])  # Test with first 10 tokens
        print(f"   Got prices for {len(prices)} tokens")
        
        # Test get_pools
        async with atime_it("get_pools"):
            pools = await chain.get_pools()
        print(f"   Found {len(pools)} pools")
        
        # Test get_pool_by_address
        if pools:
            first_pool = pools[0]
            async with atime_it("get_pool_by_address"):
                pool = await chain.get_pool_by_address(first_pool.lp)
            print(f"   Retrieved pool: {pool.symbol if pool else 'None'}")


def test_sync_methods():
    """Test key sync methods with timing"""
    print("\n🔍 Testing Sync OP Chain Methods")
    print("-" * 40)
    
    with OPChain() as chain:
        # Test get_all_tokens
        with time_it("get_all_tokens"):
            tokens = chain.get_all_tokens()
        print(f"   Found {len(tokens)} tokens")
        
        # Test get_prices
        with time_it("get_prices"):
            prices = chain.get_prices(tokens[:10])  # Test with first 10 tokens
        print(f"   Got prices for {len(prices)} tokens")
        
        # Test get_pools
        with time_it("get_pools"):
            pools = chain.get_pools()
        print(f"   Found {len(pools)} pools")
        
        # Test get_pool_by_address
        if pools:
            first_pool = pools[0]
            with time_it("get_pool_by_address"):
                pool = chain.get_pool_by_address(first_pool.lp)
            print(f"   Retrieved pool: {pool.symbol if pool else 'None'}")


async def main():
    """Main test function"""
    print("🚀 Quick Chain Method Test")
    print("=" * 50)
    
    try:
        await test_async_methods()
        test_sync_methods()
        print("\n✅ All tests completed successfully!")
        
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
