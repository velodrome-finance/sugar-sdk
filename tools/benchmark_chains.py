#!/usr/bin/env python3
"""
Comprehensive benchmarking script for sugar-sdk chain methods.

This script benchmarks all main chain methods across OP and Base chains,
including both async and sync versions for comparison.

Methods benchmarked:
- get_all_tokens
- get_pools  
- get_prices
- get_quote
- get_pool_by_address
- get_latest_pool_epochs
- get_pool_epochs
- get_pools_for_swaps
"""

import asyncio
import statistics
import time
from contextlib import contextmanager
from dataclasses import dataclass
from typing import List, Dict, Any, Optional, Callable
import json
from datetime import datetime

from sugar.chains import AsyncOPChain, OPChain, AsyncBaseChain, BaseChain
from sugar.helpers import time_it, atime_it

@dataclass
class BenchmarkResult:
    """Result of a single benchmark run"""
    method_name: str
    chain_type: str
    execution_type: str  # 'async' or 'sync'
    execution_time: float
    success: bool
    error: Optional[str] = None
    result_size: Optional[int] = None
    result_description: Optional[str] = None


@dataclass
class BenchmarkSummary:
    """Summary statistics for multiple benchmark runs"""
    method_name: str
    chain_type: str
    execution_type: str
    min_time: float
    max_time: float
    mean_time: float
    median_time: float
    std_dev: float
    success_rate: float
    total_runs: int


class ChainBenchmarker:
    """Main benchmarking class for chain methods"""
    
    def __init__(self, num_runs: int = 3):
        self.num_runs = num_runs
        self.results: List[BenchmarkResult] = []
        
    def add_result(self, result: BenchmarkResult):
        """Add a benchmark result"""
        self.results.append(result)
        
    @contextmanager
    def benchmark_context(self, method_name: str, chain_type: str, execution_type: str):
        """Context manager for timing and error handling"""
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
            
            result = BenchmarkResult(
                method_name=method_name,
                chain_type=chain_type,
                execution_type=execution_type,
                execution_time=execution_time,
                success=success,
                error=error
            )
            self.add_result(result)
            
            status = "✓" if success else "✗"
            print(f"{status} {chain_type} {execution_type} {method_name}: {execution_time:.4f}s")
            if error:
                print(f"  Error: {error}")
    
    async def benchmark_async_chain_methods(self, chain_class, chain_name: str):
        """Benchmark all async chain methods"""
        print(f"\n=== Benchmarking Async {chain_name} Chain ===")
        
        for run in range(self.num_runs):
            print(f"\nRun {run + 1}/{self.num_runs}")
            
            # Store shared data between method calls
            tokens = None
            pools = None
            
            # get_all_tokens - fresh chain instance
            async with chain_class() as chain:
                with self.benchmark_context("get_all_tokens", chain_name, "async"):
                    tokens = await chain.get_all_tokens()
                    
                if tokens:
                    self.results[-1].result_size = len(tokens)
                    self.results[-1].result_description = f"{len(tokens)} tokens"
            
            # get_prices (depends on tokens) - fresh chain instance
            if tokens:
                async with chain_class() as chain:
                    with self.benchmark_context("get_prices", chain_name, "async"):
                        prices = await chain.get_prices(tokens)
                        
                    if prices:
                        self.results[-1].result_size = len(prices)
                        self.results[-1].result_description = f"{len(prices)} prices"
            
            # get_pools - fresh chain instance
            async with chain_class() as chain:
                with self.benchmark_context("get_pools", chain_name, "async"):
                    pools = await chain.get_pools()
                    
                if pools:
                    self.results[-1].result_size = len(pools)
                    self.results[-1].result_description = f"{len(pools)} pools"
            
            # get_pools_for_swaps - fresh chain instance
            async with chain_class() as chain:
                with self.benchmark_context("get_pools_for_swaps", chain_name, "async"):
                    swap_pools = await chain.get_pools_for_swaps()
                    
                if swap_pools:
                    self.results[-1].result_size = len(swap_pools)
                    self.results[-1].result_description = f"{len(swap_pools)} swap pools"
            
            # get_pool_by_address (using first pool if available) - fresh chain instance
            if pools and len(pools) > 0:
                pool_address = pools[0].lp
                async with chain_class() as chain:
                    with self.benchmark_context("get_pool_by_address", chain_name, "async"):
                        pool = await chain.get_pool_by_address(pool_address)
                        
                    if pool:
                        self.results[-1].result_description = f"Pool: {pool.symbol}"
            
            # get_latest_pool_epochs - fresh chain instance
            async with chain_class() as chain:
                with self.benchmark_context("get_latest_pool_epochs", chain_name, "async"):
                    epochs = await chain.get_latest_pool_epochs()
                    
                if epochs:
                    self.results[-1].result_size = len(epochs)
                    self.results[-1].result_description = f"{len(epochs)} epochs"
            
            # get_pool_epochs (using first pool if available) - fresh chain instance
            if pools and len(pools) > 0:
                pool_address = pools[0].lp
                async with chain_class() as chain:
                    with self.benchmark_context("get_pool_epochs", chain_name, "async"):
                        pool_epochs = await chain.get_pool_epochs(pool_address, 0, 5)
                        
                    if pool_epochs:
                        self.results[-1].result_size = len(pool_epochs)
                        self.results[-1].result_description = f"{len(pool_epochs)} pool epochs"
            
            # get_quote (if we have tokens) - fresh chain instance
            if tokens and len(tokens) >= 2:
                from_token = tokens[0]  # Usually native token
                to_token = next((t for t in tokens[1:5] if t.token_address != from_token.token_address), None)
                
                if to_token:
                    async with chain_class() as chain:
                        with self.benchmark_context("get_quote", chain_name, "async"):
                            quote = await chain.get_quote(from_token, to_token, 1.0)
                            
                        if quote:
                            self.results[-1].result_description = f"Quote: {quote.amount_in} → {quote.amount_out}"
    
    def benchmark_sync_chain_methods(self, chain_class, chain_name: str):
        """Benchmark all sync chain methods"""
        print(f"\n=== Benchmarking Sync {chain_name} Chain ===")
        
        for run in range(self.num_runs):
            print(f"\nRun {run + 1}/{self.num_runs}")
            
            # Store shared data between method calls
            tokens = None
            pools = None
            
            # get_all_tokens - fresh chain instance
            with chain_class() as chain:
                with self.benchmark_context("get_all_tokens", chain_name, "sync"):
                    tokens = chain.get_all_tokens()
                    
                if tokens:
                    self.results[-1].result_size = len(tokens)
                    self.results[-1].result_description = f"{len(tokens)} tokens"
            
            # get_prices (depends on tokens) - fresh chain instance
            if tokens:
                with chain_class() as chain:
                    with self.benchmark_context("get_prices", chain_name, "sync"):
                        prices = chain.get_prices(tokens)
                        
                    if prices:
                        self.results[-1].result_size = len(prices)
                        self.results[-1].result_description = f"{len(prices)} prices"
            
            # get_pools - fresh chain instance
            with chain_class() as chain:
                with self.benchmark_context("get_pools", chain_name, "sync"):
                    pools = chain.get_pools()
                    
                if pools:
                    self.results[-1].result_size = len(pools)
                    self.results[-1].result_description = f"{len(pools)} pools"
            
            # get_pools_for_swaps - fresh chain instance
            with chain_class() as chain:
                with self.benchmark_context("get_pools_for_swaps", chain_name, "sync"):
                    swap_pools = chain.get_pools_for_swaps()
                    
                if swap_pools:
                    self.results[-1].result_size = len(swap_pools)
                    self.results[-1].result_description = f"{len(swap_pools)} swap pools"
            
            # get_pool_by_address (using first pool if available) - fresh chain instance
            if pools and len(pools) > 0:
                pool_address = pools[0].lp
                with chain_class() as chain:
                    with self.benchmark_context("get_pool_by_address", chain_name, "sync"):
                        pool = chain.get_pool_by_address(pool_address)
                        
                    if pool:
                        self.results[-1].result_description = f"Pool: {pool.symbol}"
            
            # get_latest_pool_epochs - fresh chain instance
            with chain_class() as chain:
                with self.benchmark_context("get_latest_pool_epochs", chain_name, "sync"):
                    epochs = chain.get_latest_pool_epochs()
                    
                if epochs:
                    self.results[-1].result_size = len(epochs)
                    self.results[-1].result_description = f"{len(epochs)} epochs"
            
            # get_pool_epochs (using first pool if available) - fresh chain instance
            if pools and len(pools) > 0:
                pool_address = pools[0].lp
                with chain_class() as chain:
                    with self.benchmark_context("get_pool_epochs", chain_name, "sync"):
                        pool_epochs = chain.get_pool_epochs(pool_address, 0, 5)
                        
                    if pool_epochs:
                        self.results[-1].result_size = len(pool_epochs)
                        self.results[-1].result_description = f"{len(pool_epochs)} pool epochs"
            
            # get_quote (if we have tokens) - fresh chain instance
            if tokens and len(tokens) >= 2:
                from_token = tokens[0]  # Usually native token
                to_token = next((t for t in tokens[1:5] if t.token_address != from_token.token_address), None)
                
                if to_token:
                    with chain_class() as chain:
                        with self.benchmark_context("get_quote", chain_name, "sync"):
                            quote = chain.get_quote(from_token, to_token, 1.0)
                            
                        if quote:
                            self.results[-1].result_description = f"Quote: {quote.amount_in} → {quote.amount_out}"
    
    def calculate_summaries(self) -> List[BenchmarkSummary]:
        """Calculate summary statistics for all benchmarks"""
        summaries = []
        
        # Group results by method, chain, and execution type
        groups = {}
        for result in self.results:
            key = (result.method_name, result.chain_type, result.execution_type)
            if key not in groups:
                groups[key] = []
            groups[key].append(result)
        
        # Calculate statistics for each group
        for (method_name, chain_type, execution_type), group_results in groups.items():
            successful_results = [r for r in group_results if r.success]
            
            if successful_results:
                times = [r.execution_time for r in successful_results]
                summary = BenchmarkSummary(
                    method_name=method_name,
                    chain_type=chain_type,
                    execution_type=execution_type,
                    min_time=min(times),
                    max_time=max(times),
                    mean_time=statistics.mean(times),
                    median_time=statistics.median(times),
                    std_dev=statistics.stdev(times) if len(times) > 1 else 0.0,
                    success_rate=len(successful_results) / len(group_results),
                    total_runs=len(group_results)
                )
            else:
                # All runs failed
                summary = BenchmarkSummary(
                    method_name=method_name,
                    chain_type=chain_type,
                    execution_type=execution_type,
                    min_time=0.0,
                    max_time=0.0,
                    mean_time=0.0,
                    median_time=0.0,
                    std_dev=0.0,
                    success_rate=0.0,
                    total_runs=len(group_results)
                )
            
            summaries.append(summary)
        
        return summaries
    
    def print_summary_report(self):
        """Print a comprehensive summary report"""
        summaries = self.calculate_summaries()
        
        print("\n" + "="*80)
        print("BENCHMARK SUMMARY REPORT")
        print("="*80)
        
        # Group by method for easier comparison
        methods = set(s.method_name for s in summaries)
        
        for method in sorted(methods):
            print(f"\n📊 {method.upper()}")
            print("-" * 60)
            
            method_summaries = [s for s in summaries if s.method_name == method]
            
            # Create comparison table
            print(f"{'Chain':<10} {'Type':<6} {'Mean':<8} {'Min':<8} {'Max':<8} {'Success':<8}")
            print("-" * 60)
            
            for summary in sorted(method_summaries, key=lambda x: (x.chain_type, x.execution_type)):
                success_pct = f"{summary.success_rate*100:.0f}%"
                print(f"{summary.chain_type:<10} {summary.execution_type:<6} "
                      f"{summary.mean_time:<8.3f} {summary.min_time:<8.3f} "
                      f"{summary.max_time:<8.3f} {success_pct:<8}")
        
        # Overall comparison
        print(f"\n🏆 PERFORMANCE COMPARISON")
        print("-" * 60)
        
        # Compare async vs sync for each chain/method
        chain_types = set(s.chain_type for s in summaries)
        
        for chain in sorted(chain_types):
            print(f"\n{chain} Chain - Async vs Sync Performance:")
            
            chain_summaries = [s for s in summaries if s.chain_type == chain and s.success_rate > 0]
            
            for method in sorted(set(s.method_name for s in chain_summaries)):
                async_summary = next((s for s in chain_summaries 
                                    if s.method_name == method and s.execution_type == 'async'), None)
                sync_summary = next((s for s in chain_summaries 
                                   if s.method_name == method and s.execution_type == 'sync'), None)
                
                if async_summary and sync_summary:
                    ratio = sync_summary.mean_time / async_summary.mean_time
                    faster = "async" if ratio > 1 else "sync"
                    print(f"  {method:<20} Async: {async_summary.mean_time:.3f}s  "
                          f"Sync: {sync_summary.mean_time:.3f}s  "
                          f"({faster} {abs(ratio-1)*100:.1f}% faster)")
        
        # Method ranking
        print(f"\n⚡ FASTEST METHODS (by mean execution time)")
        print("-" * 60)
        
        all_successful = [s for s in summaries if s.success_rate > 0]
        fastest = sorted(all_successful, key=lambda x: x.mean_time)
        
        for i, summary in enumerate(fastest[:10], 1):
            print(f"{i:2d}. {summary.chain_type} {summary.execution_type} "
                  f"{summary.method_name}: {summary.mean_time:.3f}s")
    
    def export_results(self, filename: str = None):
        """Export detailed results to JSON"""
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"chain_benchmark_results_{timestamp}.json"
        
        # Convert results to dict format
        results_data = {
            "benchmark_info": {
                "timestamp": datetime.now().isoformat(),
                "num_runs": self.num_runs,
                "total_tests": len(self.results)
            },
            "detailed_results": [
                {
                    "method_name": r.method_name,
                    "chain_type": r.chain_type,
                    "execution_type": r.execution_type,
                    "execution_time": r.execution_time,
                    "success": r.success,
                    "error": r.error,
                    "result_size": r.result_size,
                    "result_description": r.result_description
                }
                for r in self.results
            ],
            "summary_statistics": [
                {
                    "method_name": s.method_name,
                    "chain_type": s.chain_type,
                    "execution_type": s.execution_type,
                    "min_time": s.min_time,
                    "max_time": s.max_time,
                    "mean_time": s.mean_time,
                    "median_time": s.median_time,
                    "std_dev": s.std_dev,
                    "success_rate": s.success_rate,
                    "total_runs": s.total_runs
                }
                for s in self.calculate_summaries()
            ]
        }
        
        with open(filename, 'w') as f:
            json.dump(results_data, f, indent=2)
        
        print(f"\n📄 Results exported to: {filename}")


async def main():
    """Main benchmarking function"""
    print("🚀 Starting Sugar SDK Chain Benchmarking")
    print("=" * 60)
    
    benchmarker = ChainBenchmarker(num_runs=3)
    
    try:
        # Benchmark OP chains
        await benchmarker.benchmark_async_chain_methods(AsyncOPChain, "OP")
        benchmarker.benchmark_sync_chain_methods(OPChain, "OP")
        
        # Benchmark Base chains  
        await benchmarker.benchmark_async_chain_methods(AsyncBaseChain, "Base")
        benchmarker.benchmark_sync_chain_methods(BaseChain, "Base")
        
    except KeyboardInterrupt:
        print("\n❌ Benchmarking interrupted by user")
    except Exception as e:
        print(f"\n❌ Benchmarking failed with error: {e}")
    
    # Generate reports
    benchmarker.print_summary_report()
    benchmarker.export_results()
    
    print(f"\n✅ Benchmarking completed! Total tests run: {len(benchmarker.results)}")


if __name__ == "__main__":
    asyncio.run(main())
