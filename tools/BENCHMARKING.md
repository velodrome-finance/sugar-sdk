# Sugar SDK Chain Benchmarking Tools

This directory contains comprehensive benchmarking scripts for testing the performance of Sugar SDK chain methods across OP and Base chains.

## 🎯 Key Features

- **Fresh Instance Benchmarking**: Each method call uses a fresh chain instance to avoid cached results affecting timing measurements
- **Comprehensive Coverage**: Tests all main chain methods including `get_all_tokens`, `get_pools`, `get_prices`, `get_quote`, etc.
- **Multi-Chain Support**: Benchmarks both OP and Base chains
- **Async/Sync Comparison**: Tests both async and sync versions for performance comparison
- **Statistical Analysis**: Provides detailed statistics including mean, median, min, max, and standard deviation
- **Export Capabilities**: Results can be exported to JSON for further analysis

## Scripts Overview

### 1. `quick_test.py` - Quick Verification
A lightweight script to quickly verify that the chain methods are working correctly before running full benchmarks.

```bash
python quick_test.py
```

**What it tests:**
- Basic async and sync chain connectivity
- Core methods: `get_all_tokens`, `get_prices`, `get_pools`, `get_pool_by_address`
- Uses existing timing utilities (`time_it`, `atime_it`)

### 2. `focused_benchmark.py` - Core Method Benchmarking ⭐
A focused benchmarking script that tests all main chain methods with clean output and comparison. **Uses fresh chain instances for each method call.**

```bash
python focused_benchmark.py
```

**Methods benchmarked:**
- `get_all_tokens` - Retrieve all available tokens
- `get_prices` - Get token prices
- `get_pools` - Get all liquidity pools  
- `get_pools_for_swaps` - Get pools optimized for swapping
- `get_pool_by_address` - Get specific pool by address
- `get_pool_epochs` - Get historical pool data
- `get_latest_pool_epochs` - Get latest epoch data
- `get_quote` - Get swap quotes

**Features:**
- Tests both async and sync versions
- **Fresh chain instance for each method call** (no cache interference)
- Compares OP vs Base chain performance
- Clean summary output with performance comparisons
- Error handling and reporting

### 3. `benchmark_chains.py` - Comprehensive Benchmarking ⭐
A comprehensive benchmarking script with detailed statistics and multiple runs. **Uses fresh chain instances for each method call.**

```bash
python benchmark_chains.py
```

**Features:**
- Multiple runs for statistical analysis (configurable)
- **Fresh chain instance for each method call** (accurate timing)
- Detailed timing statistics (min, max, mean, median, std dev)
- Success rate tracking
- Comprehensive reporting
- JSON export with full details
- Performance ranking and comparison

### 4. `cache_impact_demo.py` - Cache Impact Demonstration 🧪
Demonstrates the difference between reused and fresh chain instances to show why fresh instances are important for accurate benchmarking.

```bash
python cache_impact_demo.py
```

**Features:**
- Shows timing differences between cached vs fresh calls
- Educational tool for understanding cache impact
- Validates the need for fresh instances in benchmarking
- Side-by-side comparison of different approaches
- Detailed timing statistics (min, max, mean, median, std dev)
- Success rate tracking
- Comprehensive reporting
- JSON export with full details
- Performance ranking and comparison

## Chain Types Tested

### OP Chain (Optimism)
- `AsyncOPChain` - Async implementation
- `OPChain` - Sync implementation

### Base Chain
- `AsyncBaseChain` - Async implementation  
- `BaseChain` - Sync implementation
