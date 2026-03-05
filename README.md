# VFS - AI Virtual Filesystem

让 AI Bot 通过文件路径读写结构化知识。配置驱动，支持自定义 provider 和权限规则。

## 安装

```bash
pip install -e .
```

## 快速开始

```python
from vfs import VFS

vfs = VFS()

# 读写
vfs.write("/memory/lesson1.md", "# 交易教训\n\nRSI>70要谨慎")
node = vfs.read("/memory/lesson1.md")

# 搜索
results = vfs.search("RSI")

# 关联
vfs.link("/memory/lesson1.md", "/market/indicators/NVDA.md", "related_to")
```

## 核心功能

### 1. 配置驱动

```yaml
# config.yaml
providers:
  - pattern: "/live/positions*"
    type: alpaca_positions
    ttl: 60
  - pattern: "/live/indicators/*"
    type: technical_indicators
    ttl: 300

permissions:
  - pattern: "/memory/*"
    access: rw
  - pattern: "/live/*"
    access: ro

default_access: ro
```

```python
vfs = VFS(config_path="config.yaml")
```

### 2. 联动检索

语义搜索 + 全文搜索 + 图扩展，返回相关节点：

```python
# 启用语义搜索（可选）
vfs.enable_embedding(model="text-embedding-3-small")
vfs.embed_all()

# 联动检索
result = vfs.retrieve("NVDA风险", expand_graph=True)
for node in result.nodes:
    print(f"{result.get_source(node.path)} {node.path}")

# 🎯 /market/indicators/NVDA.md  (语义匹配)
# 📝 /memory/lessons/nvda.md     (关键词匹配)
# 🔗 /market/indicators/AMD.md   (图扩展)
```

### 3. 动态文档合成

将多个相关节点聚合成一个结构化文档：

```python
doc = vfs.synthesize("NVDA风险分析")
print(doc)
```

输出：
```markdown
# NVDA风险分析 (auto-generated)

## 技术指标
> 🎯 来源: `/market/indicators/NVDA.md`
RSI: 72 (超买警告), MACD: 死叉形成中

## 历史经验
> 📝 来源: `/memory/lessons/nvda.md`
上次RSI>70后回调15%

## 关联标的
> 🔗 来源: `/market/indicators/AMD.md`
AMD RSI: 65, 走势相关性0.85
```

### 4. Agent Memory

Token 可控的记忆检索，支持多 agent 隔离：

```python
memory = vfs.agent_memory("akashi")

# 写入记忆
memory.remember(
    "RSI超过70时要谨慎，上次NVDA跌了15%",
    importance=0.8,
    tags=["trading", "risk"]
)

# Token 可控的检索
context = memory.recall(
    "NVDA风险",
    max_tokens=4000,
    strategy="balanced"  # importance/recency/relevance/balanced
)
print(context)
```

输出：
```markdown
## Relevant Memory (2 items, ~150 tokens)

[/memory/private/akashi/nvda_lesson.md] (0.85) RSI超过70时要谨慎，上次NVDA跌了15%

[/memory/shared/trading/risk_rules.md] (0.72) 单票仓位不超过15%，必设止损

---
*Tokens: ~150/4000 | Strategy: balanced | Query: "NVDA风险"*
```

#### 路径结构

```
/memory/private/{agent_id}/*   # 私有记忆
/memory/shared/{namespace}/*   # 共享空间
```

#### 评分策略

| 策略 | 说明 |
|------|------|
| `importance` | 按节点重要性 (0-1) |
| `recency` | 按最近访问时间（指数衰减，半衰期1周） |
| `relevance` | 按语义/关键词相关性 |
| `balanced` | 加权综合（默认：relevance 0.5 + importance 0.3 + recency 0.2） |

## CLI

```bash
# 读写
vfs read /memory/lesson1.md
vfs write /memory/lesson1.md "内容"

# 搜索
vfs search "RSI"
vfs retrieve "NVDA风险" --depth 2

# 动态文档
vfs synthesize "NVDA风险分析"

# Agent Memory
vfs recall "RSI" --agent akashi --max-tokens 2000
vfs remember --agent akashi -c "教训内容" -i 0.8 --tags "trading"
vfs memory-stats --agent akashi

# 关联
vfs links /memory/lesson1.md
vfs link /a.md /b.md related_to

# 管理
vfs list /memory
vfs history /memory/lesson1.md
vfs refresh /live/indicators/*
vfs config
vfs stats
```

## Provider 类型

| 类型 | 说明 |
|------|------|
| `alpaca_positions` | Alpaca 持仓 |
| `alpaca_orders` | Alpaca 订单 |
| `technical_indicators` | 技术指标 (Yahoo Finance) |
| `news` | 新闻 (RSS) |
| `watchlist` | 自选股 |
| `memory` | 本地记忆 |
| `http_json` | 通用 HTTP JSON |

### 自定义 Provider

```python
from vfs import VFS, register_provider_type
from vfs.providers.base import BaseProvider

class MyProvider(BaseProvider):
    def fetch(self, path: str, params: dict) -> str:
        return f"# Data for {path}\n\nCustom content here"

register_provider_type("my_provider", MyProvider)

# 在配置中使用
# providers:
#   - pattern: "/custom/*"
#     type: my_provider
```

## 配置示例

### Trading Bot

```yaml
# trading_bot.yaml
providers:
  - pattern: "/live/positions*"
    type: alpaca_positions
    ttl: 60
    params:
      api_key: ${ALPACA_API_KEY}
      api_secret: ${ALPACA_API_SECRET}

  - pattern: "/live/indicators/*"
    type: technical_indicators
    ttl: 300

permissions:
  - pattern: "/memory/private/*"
    access: rw
  - pattern: "/memory/shared/*"
    access: rw
  - pattern: "/live/*"
    access: ro

retrieval:
  default_max_tokens: 4000
  scoring_weights:
    importance: 0.3
    recency: 0.2
    relevance: 0.5
```

### Home Assistant

```yaml
# home_assistant.yaml
providers:
  - pattern: "/devices/*"
    type: http_json
    ttl: 30
    params:
      base_url: ${HA_URL}/api/states
      headers:
        Authorization: "Bearer ${HA_TOKEN}"

  - pattern: "/automations/*"
    type: memory
    ttl: 0

permissions:
  - pattern: "/devices/*"
    access: ro
  - pattern: "/automations/*"
    access: rw
```

## 架构

```
┌─────────────────────────────────────────────────────┐
│                      VFS API                        │
│  read() write() search() retrieve() synthesize()   │
├─────────────────────────────────────────────────────┤
│                   AgentMemory                       │
│  recall() remember() share() (token-aware)         │
├─────────────────────────────────────────────────────┤
│                    Retriever                        │
│  Semantic + FTS + Graph Expansion + Synthesis       │
├─────────────────────────────────────────────────────┤
│                   VFSConfig                         │
│  Providers / Permissions / YAML loading             │
├─────────────────────────────────────────────────────┤
│                   VFSStore                          │
│  SQLite + FTS5 + Diff Tracking                      │
├──────────────────────┬──────────────────────────────┤
│      KVGraph         │        EmbeddingStore        │
│  Adjacency List      │   Cosine Similarity Search   │
├──────────────────────┴──────────────────────────────┤
│                    Providers                        │
│  Alpaca | Indicators | News | HTTP | Memory | ...   │
└─────────────────────────────────────────────────────┘
```

## 版本

- **v0.4.0** - Agent Memory (token-aware recall)
- **v0.3.0** - Linked Retrieval + Document Synthesis
- **v0.2.0** - Config-driven providers/permissions
- **v0.1.0** - Core VFS (read/write/search/links)

## License

MIT
