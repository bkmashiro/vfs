# AVM Deployment Guide

Deploy AVM for real AI agents in production.

## Quick Start

### 1. Install

```bash
pip install avm

# Or from source
git clone https://github.com/aivmem/avm.git
cd avm
pip install -e .
```

### 2. Basic Usage

```python
from avm import AVM

avm = AVM()
agent = avm.agent_memory("my-agent")

# Store memory
agent.remember("Important insight", importance=0.9)

# Recall
result = agent.recall("insights", max_tokens=500)
```

## Deployment Options

### A. Python Integration

Direct integration in your agent code:

```python
from avm import AVM
from avm.agent_memory import AgentMemory, MemoryConfig

# Initialize
avm = AVM()

# Configure agent memory
config = MemoryConfig(
    duplicate_check=True,
    duplicate_threshold=0.7,
)
agent = AgentMemory(avm, "agent-id", config=config)

# Use in your agent
agent.remember("User prefers dark mode")
context = agent.recall("user preferences")
```

### B. FUSE Mount (Filesystem Access)

Mount AVM as a filesystem for shell/editor access:

```bash
# Requirements
# macOS: brew install macfuse (approve in System Settings)
# Linux: apt install fuse3

# Mount
avm-mount mount /path/to/mount --daemon

# Use with shell
echo "Note content" > /path/to/mount/memory/note.md
cat /path/to/mount/memory/note.md

# Virtual nodes
cat /path/to/mount/memory/note.md:meta
cat /path/to/mount/:search?q=keyword

# Stop
avm-mount stop /path/to/mount
```

### C. MCP Server (Model Context Protocol)

For LLM tool integration:

```bash
# Start MCP server
avm-mcp --user agent-name

# In your MCP client config:
{
  "mcpServers": {
    "avm": {
      "command": "avm-mcp",
      "args": ["--user", "my-agent"]
    }
  }
}
```

## Configuration

### Database Location

Default: `~/.local/share/vfs/avm.db`

Override:
```python
from avm.config import AVMConfig

config = AVMConfig(db_path="/custom/path/avm.db")
avm = AVM(config=config)
```

Or via environment:
```bash
export AVM_DB_PATH=/custom/path/avm.db
```

### Multi-Agent Setup

```python
avm = AVM()

# Each agent gets isolated private namespace
alice = avm.agent_memory("alice")
bob = avm.agent_memory("bob")

# Private memories (only visible to owner)
alice.remember("Alice's secret", namespace="private")

# Shared memories (visible to all agents)
alice.remember("Team decision", namespace="shared")
bob.recall("team")  # Can see shared memory
```

## Production Considerations

### 1. Database Backup

```bash
# SQLite db location
ls ~/.local/share/vfs/avm.db

# Simple backup
cp ~/.local/share/vfs/avm.db ~/backups/avm-$(date +%Y%m%d).db
```

### 2. Performance

- **Embedding**: Enable for semantic search (requires OpenAI API key or local model)
- **Caching**: Built-in LRU cache for frequent reads
- **Batch writes**: Use transactions for bulk operations

```python
# Enable embedding for better search
from avm.embedding import OpenAIEmbedding

avm.enable_embedding(backend=OpenAIEmbedding())
avm.embeend_all()  # Index existing content
```

### 3. Monitoring

```python
# Get statistics
stats = avm.stats()
print(f"Nodes: {stats['total_nodes']}")
print(f"Edges: {stats['total_edges']}")
```

### 4. OpenClaw Integration

Mount to agent workspace:

```bash
# In agent config
avm-mount mount ~/.openclaw/workspace-{agent}/avm --daemon --db ~/.local/share/avm/{agent}.db
```

Agent can then use standard file operations:
```python
# Agent writes directly
with open("avm/memory/session.md", "w") as f:
    f.write("Session notes...")

# Or via virtual nodes
os.system('cat "avm/:recall?q=previous%20session"')
```

## Troubleshooting

### FUSE not working

```bash
# macOS: Check system extension
# System Settings → Privacy & Security → Allow macfuse

# Check mount status
avm-mount status

# Force unmount
avm-mount stop /path/to/mount
```

### Database locked

```bash
# Only one process should write at a time
# Check for stale connections
lsof ~/.local/share/vfs/avm.db
```

### Memory not persisting

```python
# Ensure proper flush
agent.remember("content")  # Auto-persists

# Check database
avm.stats()  # Should show nodes
```

## API Reference

See full documentation: https://github.com/aivmem/avm/wiki
