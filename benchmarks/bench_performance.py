#!/usr/bin/env python3
"""AVM Performance Benchmark"""
import time
import tempfile
import os
from pathlib import Path

def setup():
    """Setup benchmark environment"""
    tmpdir = tempfile.mkdtemp()
    os.environ['XDG_DATA_HOME'] = tmpdir
    
    from avm import AVM
    avm = AVM(agent_id="bench")
    return avm, tmpdir

def bench_write(avm, n=100):
    """Benchmark write operations"""
    start = time.perf_counter()
    for i in range(n):
        avm.write(f"/memory/bench/file{i}.md", f"Content {i}\n" * 10)
    elapsed = time.perf_counter() - start
    return n / elapsed  # ops/sec

def bench_read(avm, n=100):
    """Benchmark read operations"""
    # Ensure files exist
    for i in range(n):
        path = f"/memory/bench/read{i}.md"
        if not avm.read(path):
            avm.write(path, f"Read content {i}")
    
    start = time.perf_counter()
    for i in range(n):
        avm.read(f"/memory/bench/read{i}.md")
    elapsed = time.perf_counter() - start
    return n / elapsed

def bench_list(avm, n=50):
    """Benchmark list operations"""
    start = time.perf_counter()
    for _ in range(n):
        avm.list("/memory/bench", limit=100)
    elapsed = time.perf_counter() - start
    return n / elapsed

def bench_search(avm, n=20):
    """Benchmark search operations"""
    start = time.perf_counter()
    for i in range(n):
        avm.search(f"content {i}", limit=10)
    elapsed = time.perf_counter() - start
    return n / elapsed

def bench_recall(avm, n=10):
    """Benchmark recall operations"""
    from avm.agent_memory import AgentMemory
    mem = AgentMemory(avm, "bench")
    
    # Write some memories
    for i in range(20):
        mem.remember(f"Memory about topic {i} with details", title=f"Topic {i}")
    
    start = time.perf_counter()
    for i in range(n):
        mem.recall(f"topic {i % 20}", max_tokens=500)
    elapsed = time.perf_counter() - start
    return n / elapsed

def main():
    print("=" * 50)
    print("AVM Performance Benchmark")
    print("=" * 50)
    
    avm, tmpdir = setup()
    
    results = {}
    
    print("\n[1/5] Write benchmark (100 ops)...")
    results['write'] = bench_write(avm, 100)
    print(f"      {results['write']:.1f} ops/sec")
    
    print("\n[2/5] Read benchmark (100 ops)...")
    results['read'] = bench_read(avm, 100)
    print(f"      {results['read']:.1f} ops/sec")
    
    print("\n[3/5] List benchmark (50 ops)...")
    results['list'] = bench_list(avm, 50)
    print(f"      {results['list']:.1f} ops/sec")
    
    print("\n[4/5] Search benchmark (20 ops)...")
    results['search'] = bench_search(avm, 20)
    print(f"      {results['search']:.1f} ops/sec")
    
    print("\n[5/5] Recall benchmark (10 ops)...")
    results['recall'] = bench_recall(avm, 10)
    print(f"      {results['recall']:.1f} ops/sec")
    
    print("\n" + "=" * 50)
    print("Summary")
    print("=" * 50)
    for op, rate in results.items():
        print(f"  {op:10} {rate:8.1f} ops/sec")
    
    # Cleanup
    import shutil
    shutil.rmtree(tmpdir, ignore_errors=True)

if __name__ == "__main__":
    main()
