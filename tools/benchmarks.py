#!/usr/bin/env python3
"""
Run benchmarks on clean instances of Sugar SDK chains (no cache)
"""

import asyncio
import statistics
import time
from contextlib import contextmanager
from dataclasses import dataclass
from typing import List, Optional

from sugar.chains import AsyncOPChain, OPChain, AsyncBaseChain, BaseChain


@dataclass
class MethodResult:
    """Result of a single method benchmark"""
    method_name: str
    chain_type: str
    execution_type: str
    execution_time: float
    success: bool
    error: Optional[str] = None


class FocusedBenchmarker:
    """Focused benchmarking with fresh instances"""
    
    def __init__(self, num_runs: int = 3):
        self.num_runs = num_runs
        self.results: List[MethodResult] = []
        
    @contextmanager
    def time_method(self, method_name: str, chain_type: str, execution_type: str):
        """Time a method execution with error handling"""
        start_time = time.perf_counter()
        error = None
        success = True
        
        try:
            yield
        except Exception as e:
            error = str(e)
            success = False
        finally:
            end_time = time.perf_counter()
            execution_time = end_time - start_time
            
            result = MethodResult(
                method_name=method_name,
                chain_type=chain_type,
                execution_type=execution_type,
                execution_time=execution_time,
                success=success,
                error=error
            )
            self.results.append(result)
            
            status = "✓" if success else "✗"
            print(f"  {status} {method_name}: {execution_time:.4f}s")
            if error:
                print(f"    Error: {error}")
    
    async def benchmark_async_methods(self, chain_class, chain_name: str, methods: List[str]):
        """Benchmark specific async methods with fresh instances"""
        print(f"\n📊 Async {chain_name} Chain")
        
        for run in range(self.num_runs):
            print(f"  Run {run + 1}/{self.num_runs}")
            
            # Store shared data between method calls
            tokens = None
            pools = None
            
            for method in methods:
                if method == "get_all_tokens":
                    async with chain_class() as chain:
                        with self.time_method(method, chain_name, "async"):
                            tokens = await chain.get_all_tokens()
                
                elif method == "get_pools":
                    async with chain_class() as chain:
                        with self.time_method(method, chain_name, "async"):
                            pools = await chain.get_pools()
                
                elif method == "get_prices" and tokens:
                    async with chain_class() as chain:
                        with self.time_method(method, chain_name, "async"):
                            await chain.get_prices(tokens)
                
                elif method == "get_pools_for_swaps":
                    async with chain_class() as chain:
                        with self.time_method(method, chain_name, "async"):
                            await chain.get_pools_for_swaps()
                
                elif method == "get_quote" and tokens and len(tokens) >= 2:
                    from_token = tokens[0]
                    to_token = next((t for t in tokens[1:5] if t.token_address != from_token.token_address), None)
                    if to_token:
                        async with chain_class() as chain:
                            with self.time_method(method, chain_name, "async"):
                                await chain.get_quote(from_token, to_token, 1.0)
                
                elif method == "get_pool_by_address" and pools and len(pools) > 0:
                    pool_address = pools[0].lp
                    async with chain_class() as chain:
                        with self.time_method(method, chain_name, "async"):
                            await chain.get_pool_by_address(pool_address)
                
                elif method == "get_latest_pool_epochs":
                    async with chain_class() as chain:
                        with self.time_method(method, chain_name, "async"):
                            await chain.get_latest_pool_epochs()
                
                elif method == "get_pool_epochs" and pools and len(pools) > 0:
                    pool_address = pools[0].lp
                    async with chain_class() as chain:
                        with self.time_method(method, chain_name, "async"):
                            await chain.get_pool_epochs(pool_address)
    
    def benchmark_sync_methods(self, chain_class, chain_name: str, methods: List[str]):
        """Benchmark specific sync methods with fresh instances"""
        print(f"\n📊 Sync {chain_name} Chain")
        
        for run in range(self.num_runs):
            print(f"  Run {run + 1}/{self.num_runs}")
            
            # Store shared data between method calls
            tokens = None
            pools = None
            
            for method in methods:
                if method == "get_all_tokens":
                    with chain_class() as chain:
                        with self.time_method(method, chain_name, "sync"):
                            tokens = chain.get_all_tokens()
                
                elif method == "get_pools":
                    with chain_class() as chain:
                        with self.time_method(method, chain_name, "sync"):
                            pools = chain.get_pools()
                
                elif method == "get_prices" and tokens:
                    with chain_class() as chain:
                        with self.time_method(method, chain_name, "sync"):
                            chain.get_prices(tokens)
                
                elif method == "get_pools_for_swaps":
                    with chain_class() as chain:
                        with self.time_method(method, chain_name, "sync"):
                            chain.get_pools_for_swaps()
                
                elif method == "get_quote" and tokens and len(tokens) >= 2:
                    from_token = tokens[0]
                    to_token = next((t for t in tokens[1:5] if t.token_address != from_token.token_address), None)
                    if to_token:
                        with chain_class() as chain:
                            with self.time_method(method, chain_name, "sync"):
                                chain.get_quote(from_token, to_token, 1.0)
                
                elif method == "get_pool_by_address" and pools and len(pools) > 0:
                    pool_address = pools[0].lp
                    with chain_class() as chain:
                        with self.time_method(method, chain_name, "sync"):
                            chain.get_pool_by_address(pool_address)
                
                elif method == "get_latest_pool_epochs":
                    with chain_class() as chain:
                        with self.time_method(method, chain_name, "sync"):
                            chain.get_latest_pool_epochs()
                
                elif method == "get_pool_epochs" and pools and len(pools) > 0:
                    pool_address = pools[0].lp
                    with chain_class() as chain:
                        with self.time_method(method, chain_name, "sync"):
                            chain.get_pool_epochs(pool_address)
    
    def print_summary(self):
        """Print a clean summary of results"""
        print(f"\n{'='*60}")
        print("BENCHMARK SUMMARY")
        print('='*60)
        
        # Group results by method and calculate statistics
        method_stats = {}
        
        for result in self.results:
            if not result.success:
                continue
                
            key = (result.method_name, result.chain_type, result.execution_type)
            if key not in method_stats:
                method_stats[key] = []
            method_stats[key].append(result.execution_time)
        
        # Print results organized by method
        methods = sorted(set(result.method_name for result in self.results if result.success))
        
        for method in methods:
            print(f"\n🔸 {method}")
            print("-" * 50)
            
            # Collect data for this method
            method_data = []
            for (m, chain, exec_type), times in method_stats.items():
                if m == method:
                    mean_time = statistics.mean(times)
                    method_data.append((chain, exec_type, mean_time, len(times)))
            
            # Sort and display
            method_data.sort(key=lambda x: x[2])  # Sort by mean time
            
            for chain, exec_type, mean_time, count in method_data:
                print(f"  {chain:<6} {exec_type:<6}: {mean_time:.4f}s (avg of {count} runs)")
        
        # Overall comparison
        print(f"\n🏆 FASTEST OVERALL")
        print("-" * 50)
        
        all_averages = []
        for (method, chain, exec_type), times in method_stats.items():
            mean_time = statistics.mean(times)
            all_averages.append((mean_time, f"{chain} {exec_type} {method}"))
        
        all_averages.sort()
        for i, (time_val, description) in enumerate(all_averages[:5], 1):
            print(f"  {i}. {description}: {time_val:.4f}s")


async def main():
    """Main focused benchmarking function"""
    print("🎯 Focused Sugar SDK Chain Benchmarking")
    print("Using fresh chain instances for each method call")
    print("=" * 60)
    
    # Key methods to benchmark
    key_methods = [
        "get_all_tokens",
        "get_pools", 
        "get_prices",
        "get_quote",
        "get_pools_for_swaps",
        "get_latest_pool_epochs",
        "get_pool_epochs"
    ]
    
    benchmarker = FocusedBenchmarker(num_runs=3)
    
    try:
        # Benchmark OP chains
        await benchmarker.benchmark_async_methods(AsyncOPChain, "OP", key_methods)
        benchmarker.benchmark_sync_methods(OPChain, "OP", key_methods)
        
        # Benchmark Base chains
        await benchmarker.benchmark_async_methods(AsyncBaseChain, "Base", key_methods)
        benchmarker.benchmark_sync_methods(BaseChain, "Base", key_methods)
        
    except KeyboardInterrupt:
        print("\n❌ Benchmarking interrupted by user")
    except Exception as e:
        print(f"\n❌ Benchmarking failed with error: {e}")
    
    # Print summary
    benchmarker.print_summary()
    
    print(f"\n✅ Focused benchmarking completed! Total successful tests: {len([r for r in benchmarker.results if r.success])}")


if __name__ == "__main__":
    asyncio.run(main())
