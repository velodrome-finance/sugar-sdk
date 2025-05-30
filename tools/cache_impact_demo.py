#!/usr/bin/env python3
"""
Cache impact demonstration script.

This script compares performance differences between:
1. Reusing the same chain instance (cached results)
2. Using fresh chain instances (no cache interference)
"""

import asyncio
import time
from contextlib import contextmanager
from typing import List

from sugar.chains import AsyncOPChain


@contextmanager
def time_it(description: str):
    """Simple timing context manager"""
    print(f"  ⏱️  {description}...", end=" ")
    start = time.perf_counter()
    try:
        yield
    finally:
        duration = time.perf_counter() - start
        print(f"{duration:.4f}s")


async def test_reused_instance():
    """Test with reused chain instance (potential caching)"""
    print("\n🔄 Testing with REUSED chain instance:")
    
    async with AsyncOPChain() as chain:
        # First call - likely slower (cold cache)
        with time_it("get_all_tokens (1st call)"):
            tokens1 = await chain.get_all_tokens()
        
        # Second call - potentially faster (cached)
        with time_it("get_all_tokens (2nd call)"):
            tokens2 = await chain.get_all_tokens()
        
        # Third call - potentially faster (cached)
        with time_it("get_all_tokens (3rd call)"):
            tokens3 = await chain.get_all_tokens()
        
        print(f"    Results: {len(tokens1)}, {len(tokens2)}, {len(tokens3)} tokens")


async def test_fresh_instances():
    """Test with fresh chain instances (no caching)"""
    print("\n🆕 Testing with FRESH chain instances:")
    
    # First call - fresh instance
    async with AsyncOPChain() as chain:
        with time_it("get_all_tokens (fresh #1)"):
            tokens1 = await chain.get_all_tokens()
    
    # Second call - fresh instance
    async with AsyncOPChain() as chain:
        with time_it("get_all_tokens (fresh #2)"):
            tokens2 = await chain.get_all_tokens()
    
    # Third call - fresh instance
    async with AsyncOPChain() as chain:
        with time_it("get_all_tokens (fresh #3)"):
            tokens3 = await chain.get_all_tokens()
    
    print(f"    Results: {len(tokens1)}, {len(tokens2)}, {len(tokens3)} tokens")


async def test_multiple_methods_reused():
    """Test multiple methods with reused instance"""
    print("\n🔄 Multiple methods with REUSED instance:")
    
    async with AsyncOPChain() as chain:
        with time_it("get_all_tokens"):
            tokens = await chain.get_all_tokens()
        
        with time_it("get_pools"):
            pools = await chain.get_pools()
        
        with time_it("get_pools_for_swaps"):
            swap_pools = await chain.get_pools_for_swaps()
        
        print(f"    Results: {len(tokens)} tokens, {len(pools)} pools, {len(swap_pools)} swap pools")


async def test_multiple_methods_fresh():
    """Test multiple methods with fresh instances"""
    print("\n🆕 Multiple methods with FRESH instances:")
    
    # get_all_tokens - fresh instance
    async with AsyncOPChain() as chain:
        with time_it("get_all_tokens"):
            tokens = await chain.get_all_tokens()
    
    # get_pools - fresh instance
    async with AsyncOPChain() as chain:
        with time_it("get_pools"):
            pools = await chain.get_pools()
    
    # get_pools_for_swaps - fresh instance
    async with AsyncOPChain() as chain:
        with time_it("get_pools_for_swaps"):
            swap_pools = await chain.get_pools_for_swaps()
    
    print(f"    Results: {len(tokens)} tokens, {len(pools)} pools, {len(swap_pools)} swap pools")


async def main():
    """Main comparison function"""
    print("🧪 Cache Impact Demonstration")
    print("=" * 50)
    print("This script demonstrates timing differences between:")
    print("• Reusing chain instances (may use cached results)")
    print("• Fresh chain instances (no cache interference)")
    print("=" * 50)
    
    try:
        # Test single method multiple times
        await test_reused_instance()
        await test_fresh_instances()
        
        print("\n" + "="*50)
        
        # Test multiple methods
        await test_multiple_methods_reused()
        await test_multiple_methods_fresh()
        
        print("\n" + "="*50)
        print("📋 ANALYSIS:")
        print("• If reused instances show faster 2nd/3rd calls → caching is happening")
        print("• Fresh instances should show consistent timing → no cache interference")
        print("• Use fresh instances in benchmarks for accurate performance measurement")
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")


if __name__ == "__main__":
    asyncio.run(main())
