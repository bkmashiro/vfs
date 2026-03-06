#!/usr/bin/env python3
"""
A/B Benchmark: File Read vs AVM Recall

Compares token usage between:
- Method A: Read all memory files directly
- Method B: Use AVM recall to get relevant context

Usage:
    python scripts/ab_benchmark.py
"""

import os
import json
import tempfile
from pathlib import Path
from dataclasses import dataclass
from typing import List, Dict

from avm import AVM
from avm.telemetry import get_telemetry


def count_tokens(text: str) -> int:
    """Estimate token count (rough: ~4 chars per token for mixed content)."""
    return len(text) // 4


@dataclass
class BenchmarkResult:
    method: str
    query: str
    tokens_used: int
    content_chars: int
    latency_ms: float


# Test memories (simulating accumulated agent knowledge)
MEMORIES = [
    # Trading rules
    ("RSI超过70时考虑减仓，低于30时考虑加仓", ["trading", "rsi"], 0.9),
    ("MACD金叉配合成交量放大是买入信号", ["trading", "macd"], 0.8),
    ("止损设在-3%，止盈设在+5%", ["trading", "risk"], 0.9),
    ("突破阻力位后回踩确认是好的入场点", ["trading", "entry"], 0.7),
    ("趋势交易顺势而为，不要抄底摸顶", ["trading", "trend"], 0.8),
    
    # Market observations
    ("BTC突破52000，RSI 72超买区域", ["market", "btc"], 0.6),
    ("ETH/BTC汇率走弱，山寨季可能结束", ["market", "eth"], 0.5),
    ("美联储6月可能降息25bp", ["market", "macro"], 0.7),
    ("NVDA财报超预期，AI需求强劲", ["market", "stocks"], 0.6),
    ("黄金突破2000美元，避险情绪升温", ["market", "gold"], 0.5),
    
    # Lessons learned
    ("追高FOMO导致亏损15%，以后要等回调", ["lessons", "mistakes"], 0.9),
    ("过度杠杆爆仓一次，现在最多用3倍", ["lessons", "risk"], 1.0),
    ("没有止损导致单笔亏损过大", ["lessons", "mistakes"], 0.9),
    ("分批建仓比一次性买入风险更低", ["lessons", "entry"], 0.8),
    ("情绪化交易是大敌，要遵守计划", ["lessons", "psychology"], 0.9),
    
    # Random notes (noise)
    ("今天天气不错，适合出门", ["random"], 0.1),
    ("晚餐吃了火锅，很好吃", ["random"], 0.1),
    ("买了新键盘，打字很舒服", ["random"], 0.1),
    ("看了一部电影，推荐指数4/5", ["random"], 0.1),
    ("健身房跑步30分钟", ["random"], 0.1),
]

# Test queries (using searchable keywords)
QUERIES = [
    "BTC RSI",
    "risk trading",
    "mistakes lessons",
    "trend MACD",
    "macro fed",
]


def setup_memories(avm: AVM, file_dir: Path, agent_id: str) -> None:
    """Set up test memories in both AVM and files."""
    agent = avm.agent_memory(agent_id)
    
    for content, tags, importance in MEMORIES:
        # Save to AVM
        agent.remember(content, tags=tags, importance=importance)
        
        # Save to file
        filename = f"{tags[0]}_{len(list(file_dir.glob('*.md')))}.md"
        filepath = file_dir / filename
        filepath.write_text(f"# {tags[0].title()}\n\n{content}\n\nTags: {', '.join(tags)}")


def method_a_file_read(file_dir: Path, query: str) -> BenchmarkResult:
    """Method A: Read all files and include in context."""
    import time
    start = time.perf_counter()
    
    all_content = []
    for f in sorted(file_dir.glob("*.md")):
        all_content.append(f.read_text())
    
    combined = "\n---\n".join(all_content)
    latency = (time.perf_counter() - start) * 1000
    
    return BenchmarkResult(
        method="file_read",
        query=query,
        tokens_used=count_tokens(combined),
        content_chars=len(combined),
        latency_ms=latency
    )


def method_b_avm_recall(avm: AVM, query: str, agent_id: str, max_tokens: int = 300) -> BenchmarkResult:
    """Method B: Use AVM recall to get relevant context."""
    import time
    start = time.perf_counter()
    
    agent = avm.agent_memory(agent_id)
    result = agent.recall(query, max_tokens=max_tokens)
    
    latency = (time.perf_counter() - start) * 1000
    
    return BenchmarkResult(
        method="avm_recall",
        query=query,
        tokens_used=count_tokens(result),
        content_chars=len(result),
        latency_ms=latency
    )


def main():
    import time as _time
    print("=" * 60)
    print("A/B Benchmark: File Read vs AVM Recall")
    print("=" * 60)
    
    # Setup with unique agent ID
    avm = AVM()
    agent_id = f"bench_{int(_time.time())}"
    
    with tempfile.TemporaryDirectory() as tmpdir:
        file_dir = Path(tmpdir)
        
        print(f"\n1. Setting up {len(MEMORIES)} test memories...")
        print(f"   Agent ID: {agent_id}")
        setup_memories(avm, file_dir, agent_id)
        print(f"   ✓ AVM: {len(MEMORIES)} memories stored")
        print(f"   ✓ Files: {len(list(file_dir.glob('*.md')))} files created")
        
        # Run benchmarks
        print(f"\n2. Running {len(QUERIES)} queries...\n")
        
        results_a = []
        results_b = []
        
        for query in QUERIES:
            # Method A
            result_a = method_a_file_read(file_dir, query)
            results_a.append(result_a)
            
            # Method B
            result_b = method_b_avm_recall(avm, query, agent_id, max_tokens=300)
            results_b.append(result_b)
            
            print(f"   Query: '{query}'")
            print(f"   📁 File: {result_a.tokens_used} tokens ({result_a.latency_ms:.1f}ms)")
            print(f"   🧠 AVM:  {result_b.tokens_used} tokens ({result_b.latency_ms:.1f}ms)")
            savings = (1 - result_b.tokens_used / result_a.tokens_used) * 100 if result_a.tokens_used > 0 else 0
            print(f"   💰 Savings: {savings:.1f}%\n")
        
        # Summary
        print("=" * 60)
        print("3. Summary")
        print("=" * 60)
        
        total_a = sum(r.tokens_used for r in results_a)
        total_b = sum(r.tokens_used for r in results_b)
        avg_latency_a = sum(r.latency_ms for r in results_a) / len(results_a)
        avg_latency_b = sum(r.latency_ms for r in results_b) / len(results_b)
        
        print(f"\n📁 Method A (File Read):")
        print(f"   Total tokens: {total_a}")
        print(f"   Avg latency: {avg_latency_a:.2f}ms")
        
        print(f"\n🧠 Method B (AVM Recall):")
        print(f"   Total tokens: {total_b}")
        print(f"   Avg latency: {avg_latency_b:.2f}ms")
        
        overall_savings = (1 - total_b / total_a) * 100 if total_a > 0 else 0
        print(f"\n💰 Overall Token Savings: {overall_savings:.1f}%")
        print(f"   ({total_a - total_b} tokens saved across {len(QUERIES)} queries)")
        
        # Cost estimate (assuming $0.15 per 1M input tokens for Claude)
        cost_per_token = 0.15 / 1_000_000
        cost_saved = (total_a - total_b) * cost_per_token
        
        print(f"\n💵 Estimated Cost Savings:")
        print(f"   Per query set: ${cost_saved:.6f}")
        print(f"   Per 1000 queries: ${cost_saved * 200:.4f}")
        print(f"   Per 100k queries: ${cost_saved * 20000:.2f}")
        
        print("\n✓ Benchmark complete!")


if __name__ == "__main__":
    main()
