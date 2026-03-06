#!/usr/bin/env python3
"""
Real bot benchmark (FTS mode, no embedding API needed).

Usage:
    python scripts/real_bot_test.py
"""

import os
import sys
from pathlib import Path

from avm import AVM
from avm.telemetry import get_telemetry

def main():
    print("=== AVM Real Bot Benchmark (FTS Mode) ===\n")
    
    # Initialize AVM (no embedding)
    print("1. Initializing AVM...")
    avm = AVM()
    
    # Create agent
    agent_id = "benchmark-bot"
    agent = avm.agent_memory(agent_id)
    print(f"   ✓ Agent: {agent_id}")
    
    # Sample data (realistic agent memories)
    memories = [
        ("BTC突破52000阻力位，RSI显示超买，短期可能回调", ["crypto", "btc", "technical"], 0.8),
        ("ETH gas费用降到10 gwei以下，适合进行DeFi操作", ["crypto", "eth", "gas"], 0.6),
        ("NVDA财报超预期，AI芯片需求强劲，股价创新高", ["stocks", "nvda", "earnings"], 0.9),
        ("美联储可能在6月降息，市场风险偏好升温", ["macro", "fed", "rates"], 0.7),
        ("RSI超过70时考虑减仓，低于30时考虑加仓，这是基本策略", ["rules", "rsi", "trading"], 0.8),
        ("止损设在-3%，止盈设在+5%是合理的风险收益比", ["rules", "risk", "trading"], 0.9),
        ("DeFi协议TVL回升到500亿美元，市场信心恢复中", ["crypto", "defi", "tvl"], 0.5),
        ("MACD金叉配合成交量放大是经典买入信号", ["technical", "macd", "signals"], 0.7),
        ("关注周五非农数据，超预期可能导致美元走强", ["macro", "nfp", "calendar"], 0.6),
        ("Layer2解决方案如Arbitrum降低了以太坊使用成本", ["crypto", "eth", "layer2"], 0.5),
        ("SOL生态复苏，meme币热度带动链上活跃度", ["crypto", "sol", "meme"], 0.4),
        ("黄金突破2000美元，避险情绪上升", ["macro", "gold", "commodities"], 0.6),
        ("A股北向资金连续净流入，外资看好中国市场", ["stocks", "china", "flows"], 0.5),
        ("日元贬值到150，日本央行可能干预汇市", ["macro", "forex", "jpy"], 0.7),
        ("OpenAI发布GPT-5，AI概念股全线上涨", ["stocks", "ai", "news"], 0.8),
    ]
    
    # Write memories
    print(f"\n2. Writing {len(memories)} memories...")
    for content, tags, importance in memories:
        result = agent.remember(content, tags=tags, importance=importance)
        print(f"   ✓ {content[:35]}...")
    
    # Test recalls with different queries
    print("\n3. Testing recall (FTS)...")
    queries = [
        ("BTC技术分析", 300),
        ("风险管理规则", 200),
        ("宏观经济", 400),
        ("交易信号", 300),
        ("ETH gas", 200),
    ]
    
    telem = get_telemetry()
    
    for query, max_tokens in queries:
        result = agent.recall(query, max_tokens=max_tokens)
        print(f"\n   Query: '{query}' (max {max_tokens} tokens)")
        print(f"   Result: {len(result)} chars")
        # Show first line of result
        first_line = result.split('\n')[0][:60]
        print(f"   Preview: {first_line}...")
    
    # Show telemetry
    print("\n" + "=" * 50)
    print("4. Telemetry Report")
    print("=" * 50)
    
    stats = telem.stats(agent=agent_id)
    print(f"\nTotal operations: {stats['total_ops']}")
    for op, data in stats['by_op'].items():
        latency = f"{data['avg_latency_ms']:.2f}" if data['avg_latency_ms'] else "-"
        print(f"  {op}: {data['count']} calls, avg {latency}ms")
    
    print("\nToken Savings:")
    savings = telem.token_savings(agent=agent_id)
    print(f"  Recalls: {savings['recalls']}")
    print(f"  Tokens returned: {savings['tokens_returned']}")
    print(f"  Tokens available: {savings['tokens_available']}")
    print(f"  Tokens saved: {savings['tokens_saved']}")
    print(f"  Savings: {savings['savings_pct']}%")
    
    print("\nRecent Operations (last 5):")
    entries = telem.query(agent=agent_id, limit=5)
    for e in entries:
        status = "✓" if e['success'] else "✗"
        tokens = f"{e['tokens_in'] or '-'}/{e['tokens_out'] or '-'}"
        latency = f"{e['latency_ms']:.1f}ms" if e['latency_ms'] else "-"
        print(f"  {status} {e['op']:10} tokens={tokens:10} {latency}")
    
    print("\n✓ Benchmark complete!")

if __name__ == "__main__":
    main()
