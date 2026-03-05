# AI Virtual Filesystem (VFS)

让 AI Agent 通过文件路径读写结构化知识。

```
Bot ←→ vfs read/write ←→ VFSStore ←→ SQLite + FTS5
                              ↓
                         Providers
                    (Alpaca, Yahoo, RSS)
```

## 设计理念

- **对 Bot 接口是"文件"**：路径 + 内容，简单直观
- **内部是结构化存储**：SQLite + FTS5 + 关系图
- **权限硬编码**：`/memory` 可写，`/research` `/live` 只读
- **TTL 缓存**：`/live` 路径自动刷新过期数据
- **版本追踪**：每次写入保存 diff

## 安装

```bash
cd ~/.openclaw/workspace/vfs
pip install -e .

# 验证安装
vfs stats
```

## 使用

### 读取

```bash
# 读取 live 数据（自动刷新过期缓存）
vfs read /live/positions.md

# 强制刷新
vfs read /live/positions.md --refresh

# 读取 memory
vfs read /memory/lessons/001.md
```

### 写入

```bash
# 写入 memory（仅 /memory/* 可写）
vfs write /memory/lesson.md --content "今天学到了..."

# 从文件写入
vfs write /memory/report.md --file ./report.md

# 从 stdin 写入
echo "内容" | vfs write /memory/note.md
```

### 搜索

```bash
# 全文搜索
vfs search "能源板块超卖"

# 限制结果数
vfs search "RSI" --limit 5
```

### 关系图

```bash
# 查看关联
vfs links /research/MSFT.md

# 添加关联
vfs link /research/MSFT.md /research/AAPL.md --type peer

# 关联类型：peer, parent, citation, derived, related
```

### 其他

```bash
# 列出节点
vfs list /memory

# 查看历史
vfs history /memory/lesson.md

# 存储统计
vfs stats
```

## 路径设计

| 前缀 | 说明 | 权限 | TTL |
|------|------|------|-----|
| `/live` | 实时数据 | 只读 | 有 |
| `/research` | 静态研报 | 只读 | 无 |
| `/memory` | Bot 记忆 | 读写 | 无 |
| `/links` | 关系索引 | 只读 | 无 |

## 架构

```
Bot ←→ VFS CLI ←→ VFSStore ←→ SQLite
                     ↓
              ┌──────┴──────┐
              │   nodes     │ ← 节点内容
              │   nodes_fts │ ← FTS5 全文索引
              │   edges     │ ← 关系图
              │   diffs     │ ← 变更历史
              │   embeddings│ ← 向量（预留）
              └─────────────┘
```

## Provider

- `AlpacaPositionsProvider`: 从 Alpaca 获取持仓数据 → `/live/positions.md`
- `MemoryProvider`: Bot 记忆区 → `/memory/*`

## Providers

| Provider | 路径 | 数据源 | TTL |
|----------|------|--------|-----|
| AlpacaPositionsProvider | `/live/positions.md` | Alpaca API | 60s |
| AlpacaOrdersProvider | `/live/orders.md` | Alpaca API | 30s |
| TechnicalIndicatorsProvider | `/live/indicators/AAPL.md` | Yahoo Finance | 300s |
| NewsProvider | `/live/news/market.md` | RSS (Yahoo, CoinDesk) | 600s |
| WatchlistProvider | `/live/watchlist.md` | Yahoo Finance | 300s |
| MemoryProvider | `/memory/*` | Bot 写入 | - |

### 技术指标

```bash
vfs read /live/indicators/NVDA.md
```

输出包括：
- RSI (14) + 超买/超卖信号
- MACD + 金叉/死叉
- SMA/EMA 移动平均线
- 布林带 + %B
- ATR 波动率

### 自选股概览

```bash
vfs read /live/watchlist.md        # 默认（SPY, QQQ, AAPL...）
vfs read /live/watchlist/tech.md   # 科技股
vfs read /live/watchlist/crypto.md # 加密相关股
```

## 批量操作

```bash
# 导入目录
vfs import ./reports --prefix /research --pattern "**/*.md"

# 导出所有节点
vfs export / --output backup.json

# 自动发现关系
vfs auto-link --by symbol
```

## Python API

```python
from vfs import VFSStore, VFSNode

store = VFSStore()

# 读取
node = store.get_node("/memory/lesson.md")
print(node.content)

# 写入
new_node = VFSNode(path="/memory/new.md", content="Hello")
store.put_node(new_node)

# 搜索
results = store.search("RSI oversold")
for node, score in results:
    print(f"{node.path}: {score}")

# 关系
store.add_edge("/research/AAPL.md", "/research/MSFT.md", EdgeType.PEER)
links = store.get_links("/research/AAPL.md")
```

## 测试

```bash
pytest tests/ -v
# 33 passed
```

## TODO

- [ ] sqlite-vec 向量语义搜索
- [ ] 更多 provider（财报、宏观数据）
- [ ] MCP server 接入
- [ ] 过期数据自动清理
