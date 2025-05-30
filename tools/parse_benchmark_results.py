#!/usr/bin/env python3
"""
Parse focused benchmark output and create GitHub-friendly markdown tables.
"""

import re
import sys
from typing import Dict, List, Tuple


def parse_focused_benchmark_output(content: str) -> List[Dict[str, any]]:
    """Parse the focused benchmark output text"""
    results = []
    
    # Pattern to match benchmark summary lines like:
    # "  OP     async : 0.3103s (avg of 3 runs)"
    pattern = r'\s+(\w+)\s+(\w+)\s+:\s+(\d+\.\d+)s\s+\(avg of \d+ runs\)'
    
    lines = content.split('\n')
    current_method = None
    
    for line in lines:
        # Check for method headers like "🔸 get_all_tokens"
        method_match = re.match(r'🔸\s+(\w+)', line)
        if method_match:
            current_method = method_match.group(1)
            continue
        
        # Check for result lines
        if current_method:
            result_match = re.match(pattern, line)
            if result_match:
                chain = result_match.group(1)
                exec_type = result_match.group(2)
                time_val = float(result_match.group(3))
                
                results.append({
                    'method_name': current_method,
                    'chain_type': chain,
                    'execution_type': exec_type,
                    'execution_time': time_val
                })
    
    return results


def create_performance_table(results: List[Dict[str, any]]) -> str:
    """Create a comprehensive performance comparison table"""
    
    if not results:
        return "No benchmark results found.\n"
    
    # Group by method for easier comparison
    methods = {}
    for result in results:
        method = result['method_name']
        if method not in methods:
            methods[method] = []
        methods[method].append(result)
    
    output = "## 📊 Performance Comparison\n\n"
    
    for method_name, method_results in sorted(methods.items()):
        output += f"### {method_name}\n\n"
        output += "| Chain | Type | Time (s) | Relative Performance |\n"
        output += "|-------|------|----------|---------------------|\n"
        
        # Sort by execution time to show fastest first
        method_results.sort(key=lambda x: x['execution_time'])
        fastest_time = method_results[0]['execution_time']
        
        for i, result in enumerate(method_results):
            chain = result['chain_type']
            exec_type = result['execution_type']
            time_val = result['execution_time']
            
            if i == 0:
                relative = "🥇 **Fastest**"
            else:
                multiplier = time_val / fastest_time
                diff_pct = ((time_val - fastest_time) / fastest_time) * 100
                relative = f"{multiplier:.1f}x slower (+{diff_pct:.1f}%)"
            
            output += f"| {chain} | {exec_type} | {time_val:.3f} | {relative} |\n"
        
        output += "\n"
    
    return output


def create_async_vs_sync_table(results: List[Dict[str, any]]) -> str:
    """Create async vs sync comparison tables"""
    
    # Group by chain
    chains = {}
    for result in results:
        chain = result['chain_type']
        if chain not in chains:
            chains[chain] = {}
        
        method = result['method_name']
        if method not in chains[chain]:
            chains[chain][method] = {}
        
        chains[chain][method][result['execution_type']] = result['execution_time']
    
    output = "## ⚡ Async vs Sync Performance\n\n"
    
    for chain_name, chain_data in sorted(chains.items()):
        output += f"### {chain_name} Chain\n\n"
        output += "| Method | Async | Sync | Winner | Performance Difference |\n"
        output += "|--------|-------|------|--------|------------------------|\n"
        
        for method_name, method_data in sorted(chain_data.items()):
            if 'async' in method_data and 'sync' in method_data:
                async_time = method_data['async']
                sync_time = method_data['sync']
                
                if async_time < sync_time:
                    winner = "**Async**"
                    diff_pct = ((sync_time - async_time) / async_time) * 100
                    diff_text = f"{diff_pct:.1f}% faster"
                else:
                    winner = "**Sync**"
                    diff_pct = ((async_time - sync_time) / sync_time) * 100
                    diff_text = f"{diff_pct:.1f}% faster"
                
                output += f"| {method_name} | {async_time:.3f}s | {sync_time:.3f}s | {winner} | {diff_text} |\n"
        
        output += "\n"
    
    return output


def create_fastest_methods_table(results: List[Dict[str, any]]) -> str:
    """Create table of fastest methods overall"""
    
    output = "## 🏆 Fastest Methods Overall\n\n"
    output += "| Rank | Method | Chain | Type | Time (s) |\n"
    output += "|------|--------|-------|------|----------|\n"
    
    # Sort all results by execution time
    sorted_results = sorted(results, key=lambda x: x['execution_time'])
    
    for i, result in enumerate(sorted_results[:10], 1):  # Top 10
        method = result['method_name']
        chain = result['chain_type']
        exec_type = result['execution_type']
        time_val = result['execution_time']
        
        rank_emoji = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"{i}."
        output += f"| {rank_emoji} | {method} | {chain} | {exec_type} | {time_val:.3f} |\n"
    
    output += "\n"
    return output


def main():
    """Main function"""
    if len(sys.argv) != 2:
        print("Usage: python parse_benchmark_results.py <benchmark_output_file>")
        sys.exit(1)
    
    output_file = sys.argv[1]
    
    try:
        with open(output_file, 'r') as f:
            content = f.read()
        
        results = parse_focused_benchmark_output(content)
        
        if not results:
            print("No benchmark results found in the output file.")
            sys.exit(1)
        
        print("# 🎯 Sugar SDK Performance Benchmark Results\n")
        print(create_performance_table(results))
        print(create_async_vs_sync_table(results))
        print(create_fastest_methods_table(results))
        
        print("---")
        print("*Results generated from focused benchmark with fresh chain instances*")
        
    except FileNotFoundError:
        print(f"Error: Could not find file {output_file}")
        sys.exit(1)
    except Exception as e:
        print(f"Error parsing results: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
