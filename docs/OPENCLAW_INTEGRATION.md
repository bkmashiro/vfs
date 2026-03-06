# AVM + OpenClaw Integration Plan

## Overview

OpenClaw has a mature plugin system. AVM can integrate as a **memory slot plugin** (like `memory-lancedb`).

## Integration Options

### Option 1: Memory Slot Plugin (Recommended)

Replace `memory-lancedb` with `memory-avm`:

```json5
{
  plugins: {
    slots: {
      memory: "memory-avm"  // Instead of "memory-core" or "memory-lancedb"
    },
    entries: {
      "memory-avm": {
        enabled: true,
        config: {
          dbPath: "~/.local/share/avm/avm.db",
          agentId: "openclaw",
          // Optional: embedding provider
          embedding: {
            provider: "openai",  // or "ollama"
            model: "text-embedding-3-small"
          }
        }
      }
    }
  }
}
```

**Advantages:**
- Automatic lifecycle hooks (auto-recall, auto-capture)
- Single memory slot, no conflicts
- Native integration with OpenClaw's memory system

### Option 2: Agent Tools Plugin

Add AVM as tools without replacing memory:

```json5
{
  plugins: {
    entries: {
      "avm-tools": {
        enabled: true,
        config: {
          dbPath: "~/.local/share/avm/avm.db"
        }
      }
    }
  },
  agents: {
    list: [{
      id: "main",
      tools: {
        allow: ["avm_recall", "avm_remember", "avm_link"]
      }
    }]
  }
}
```

**Advantages:**
- Works alongside existing memory
- Explicit control (agent decides when to use)
- No conflict with `memory-core` or `memory-lancedb`

## Implementation Plan

### Phase 1: Plugin Scaffold

```
@aivmem/openclaw-avm/
├── openclaw.plugin.json   # Manifest
├── package.json
├── index.ts               # Plugin entry
├── tools.ts               # Agent tools
├── hooks.ts               # Lifecycle hooks
└── config.ts              # Schema
```

### Phase 2: Core Integration

**Tools to expose:**

| Tool | Description |
|------|-------------|
| `avm_recall` | Token-aware semantic search |
| `avm_remember` | Store memory with importance |
| `avm_topics` | Discover what's in memory |
| `avm_link` | Create knowledge graph edges |
| `avm_browse` | Navigate memory structure |

**Lifecycle hooks:**

| Hook | Behavior |
|------|----------|
| `beforeAgentRun` | Auto-inject relevant context |
| `afterAgentRun` | Auto-capture important exchanges |

### Phase 3: Memory Slot Mode

Implement `kind: "memory"` for slot-based activation:

```json
{
  "id": "memory-avm",
  "kind": "memory",
  "configSchema": { ... }
}
```

## Plugin Skeleton

```typescript
// index.ts
import { Type } from "@sinclair/typebox";
import type { OpenClawPluginApi } from "openclaw/plugin-sdk";

export default function register(api: OpenClawPluginApi) {
  const config = api.config.plugins?.entries?.["memory-avm"]?.config;
  
  // Initialize AVM (spawn Python process or use MCP)
  const avm = initAVM(config);
  
  // Register tools
  api.registerTool({
    name: "avm_recall",
    description: "Search memories with token budget",
    parameters: Type.Object({
      query: Type.String(),
      maxTokens: Type.Optional(Type.Number()),
    }),
    async execute(_id, params) {
      const result = await avm.recall(params.query, params.maxTokens);
      return { content: [{ type: "text", text: result }] };
    },
  });
  
  api.registerTool({
    name: "avm_remember",
    description: "Store a memory",
    parameters: Type.Object({
      content: Type.String(),
      importance: Type.Optional(Type.Number()),
      tags: Type.Optional(Type.Array(Type.String())),
    }),
    async execute(_id, params) {
      await avm.remember(params.content, params.importance, params.tags);
      return { content: [{ type: "text", text: "Memory stored." }] };
    },
  });
  
  // Register lifecycle hooks for auto-recall/capture
  api.registerHook("agent:beforeRun", async (ctx) => {
    // Inject relevant memories into context
    const memories = await avm.recall(ctx.userMessage, 2000);
    if (memories) {
      ctx.systemPromptSuffix += `\n\n## Relevant Memories\n${memories}`;
    }
  });
}
```

## AVM Backend Options

### Option A: MCP Server

Use existing `avm-mcp` server:

```typescript
import { spawn } from "child_process";

class AVMClient {
  private proc: ChildProcess;
  
  constructor(config) {
    this.proc = spawn("avm-mcp", ["--db", config.dbPath]);
    // Setup JSON-RPC communication
  }
  
  async recall(query: string, maxTokens?: number) {
    return this.call("avm_recall", { query, maxTokens });
  }
}
```

### Option B: Direct Python Bridge

Use `python-bridge` or similar:

```typescript
import { PythonShell } from "python-shell";

const result = await PythonShell.run("avm_bridge.py", {
  args: ["recall", query, maxTokens]
});
```

### Option C: HTTP Server

Run AVM as HTTP service:

```bash
avm serve --port 8765
```

```typescript
const response = await fetch("http://localhost:8765/recall", {
  method: "POST",
  body: JSON.stringify({ query, maxTokens })
});
```

## Distribution

Publish as npm package:

```bash
npm publish @aivmem/openclaw-avm
```

Users install via:

```bash
openclaw plugins install @aivmem/openclaw-avm
```

## Timeline

| Phase | Effort | Description |
|-------|--------|-------------|
| 1 | 1 day | Plugin scaffold + manifest |
| 2 | 2 days | Tools + MCP integration |
| 3 | 1 day | Lifecycle hooks |
| 4 | 1 day | Testing + docs |

**Total: ~5 days**

## Next Steps

1. ✅ Confirm plugin approach (slot vs tools)
2. Create `@aivmem/openclaw-avm` repo
3. Implement MCP bridge
4. Register tools
5. Add lifecycle hooks
6. Publish to npm
