"""
avm/tell.py - Cross-agent messaging system

Allows agents to send important messages to each other that get
injected into the recipient's next read operation.

Priority levels:
- urgent: Injected into next read of ANY file
- normal: Shown when reading /:inbox or /tell/@me
- low: Only shown when explicitly reading /:inbox

Usage:
    # Write a tell
    echo "important message" > avm/tell/kearsarge?priority=urgent
    echo "fyi" > avm/tell/kearsarge
    echo "message" > avm/tell/@all  # Broadcast

    # Read tells
    cat avm/:inbox              # All unread tells
    cat avm/tell/@me            # Same as /:inbox
    cat avm/tell/@me?mark=read  # Mark all as read
"""

import json
import sqlite3
from datetime import datetime, timezone
from typing import List, Dict, Optional, Any
from dataclasses import dataclass, asdict
from enum import Enum


class TellPriority(Enum):
    URGENT = "urgent"   # Inject into next read
    NORMAL = "normal"   # Show in inbox
    LOW = "low"         # Only explicit inbox read


@dataclass
class Tell:
    """A message from one agent to another"""
    id: int
    from_agent: str
    to_agent: str  # Can be specific agent or "@all"
    content: str
    priority: TellPriority
    created_at: str
    read_at: Optional[str] = None
    expires_at: Optional[str] = None
    ack_required: bool = False
    meta: Dict[str, Any] = None
    
    def __post_init__(self):
        if isinstance(self.priority, str):
            self.priority = TellPriority(self.priority)
        if self.meta is None:
            self.meta = {}
    
    def to_dict(self) -> Dict:
        d = asdict(self)
        d['priority'] = self.priority.value
        return d
    
    def format_header(self) -> str:
        """Format as markdown header for injection"""
        priority_emoji = {
            TellPriority.URGENT: "🔴",
            TellPriority.NORMAL: "🟡", 
            TellPriority.LOW: "⚪"
        }
        emoji = priority_emoji.get(self.priority, "")
        return f"## {emoji} From: {self.from_agent} @ {self.created_at}\n{self.content}"


class TellStore:
    """SQLite storage for tells"""
    
    SCHEMA = """
    CREATE TABLE IF NOT EXISTS tells (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        from_agent TEXT NOT NULL,
        to_agent TEXT NOT NULL,
        content TEXT NOT NULL,
        priority TEXT NOT NULL DEFAULT 'normal',
        created_at TEXT NOT NULL,
        read_at TEXT,
        expires_at TEXT,
        ack_required INTEGER DEFAULT 0,
        meta TEXT DEFAULT '{}'
    );
    
    CREATE INDEX IF NOT EXISTS idx_tells_to_agent ON tells(to_agent);
    CREATE INDEX IF NOT EXISTS idx_tells_read_at ON tells(read_at);
    CREATE INDEX IF NOT EXISTS idx_tells_priority ON tells(priority);
    """
    
    def __init__(self, db_path: str):
        self.db_path = db_path
        self._init_db()
    
    def _init_db(self):
        """Initialize tell tables"""
        with sqlite3.connect(self.db_path) as conn:
            conn.executescript(self.SCHEMA)
    
    def _row_to_tell(self, row: tuple) -> Tell:
        """Convert database row to Tell object"""
        return Tell(
            id=row[0],
            from_agent=row[1],
            to_agent=row[2],
            content=row[3],
            priority=TellPriority(row[4]),
            created_at=row[5],
            read_at=row[6],
            expires_at=row[7],
            ack_required=bool(row[8]),
            meta=json.loads(row[9]) if row[9] else {}
        )
    
    def send(self, from_agent: str, to_agent: str, content: str,
             priority: TellPriority = TellPriority.NORMAL,
             expires_at: str = None, ack_required: bool = False,
             meta: Dict = None) -> Tell:
        """Send a tell to an agent"""
        now = datetime.now(timezone.utc).isoformat()
        meta_json = json.dumps(meta or {})
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                INSERT INTO tells 
                (from_agent, to_agent, content, priority, created_at, expires_at, ack_required, meta)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (from_agent, to_agent, content, priority.value, now, expires_at, int(ack_required), meta_json))
            
            tell_id = cursor.lastrowid
            
            return Tell(
                id=tell_id,
                from_agent=from_agent,
                to_agent=to_agent,
                content=content,
                priority=priority,
                created_at=now,
                expires_at=expires_at,
                ack_required=ack_required,
                meta=meta or {}
            )
    
    def get_unread(self, agent_id: str, priority: TellPriority = None,
                   include_broadcast: bool = True) -> List[Tell]:
        """Get unread tells for an agent"""
        now = datetime.now(timezone.utc).isoformat()
        
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            
            # Build query
            conditions = ["read_at IS NULL"]
            params = []
            
            # Agent filter (including @all broadcasts)
            if include_broadcast:
                conditions.append("(to_agent = ? OR to_agent = '@all')")
            else:
                conditions.append("to_agent = ?")
            params.append(agent_id)
            
            # Priority filter
            if priority:
                conditions.append("priority = ?")
                params.append(priority.value)
            
            # Expiration filter
            conditions.append("(expires_at IS NULL OR expires_at > ?)")
            params.append(now)
            
            query = f"""
                SELECT id, from_agent, to_agent, content, priority, 
                       created_at, read_at, expires_at, ack_required, meta
                FROM tells 
                WHERE {' AND '.join(conditions)}
                ORDER BY 
                    CASE priority 
                        WHEN 'urgent' THEN 0 
                        WHEN 'normal' THEN 1 
                        ELSE 2 
                    END,
                    created_at DESC
            """
            
            rows = conn.execute(query, params).fetchall()
            return [self._row_to_tell(tuple(row)) for row in rows]
    
    def get_urgent_unread(self, agent_id: str) -> List[Tell]:
        """Get only urgent unread tells"""
        return self.get_unread(agent_id, priority=TellPriority.URGENT)
    
    def mark_read(self, tell_ids: List[int]) -> int:
        """Mark tells as read"""
        if not tell_ids:
            return 0
        
        now = datetime.now(timezone.utc).isoformat()
        placeholders = ','.join('?' * len(tell_ids))
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(f"""
                UPDATE tells SET read_at = ?
                WHERE id IN ({placeholders}) AND read_at IS NULL
            """, [now] + tell_ids)
            return cursor.rowcount
    
    def mark_all_read(self, agent_id: str) -> int:
        """Mark all tells for an agent as read"""
        now = datetime.now(timezone.utc).isoformat()
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                UPDATE tells SET read_at = ?
                WHERE (to_agent = ? OR to_agent = '@all') AND read_at IS NULL
            """, (now, agent_id))
            return cursor.rowcount
    
    def get_all(self, agent_id: str, limit: int = 50) -> List[Tell]:
        """Get all tells for an agent (read and unread)"""
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute("""
                SELECT id, from_agent, to_agent, content, priority,
                       created_at, read_at, expires_at, ack_required, meta
                FROM tells
                WHERE to_agent = ? OR to_agent = '@all'
                ORDER BY created_at DESC
                LIMIT ?
            """, (agent_id, limit)).fetchall()
            return [self._row_to_tell(row) for row in rows]
    
    def delete_expired(self) -> int:
        """Delete expired tells"""
        now = datetime.now(timezone.utc).isoformat()
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                DELETE FROM tells WHERE expires_at IS NOT NULL AND expires_at < ?
            """, (now,))
            return cursor.rowcount
    
    def stats(self, agent_id: str = None) -> Dict:
        """Get tell statistics"""
        with sqlite3.connect(self.db_path) as conn:
            if agent_id:
                total = conn.execute("""
                    SELECT COUNT(*) FROM tells WHERE to_agent = ? OR to_agent = '@all'
                """, (agent_id,)).fetchone()[0]
                unread = conn.execute("""
                    SELECT COUNT(*) FROM tells 
                    WHERE (to_agent = ? OR to_agent = '@all') AND read_at IS NULL
                """, (agent_id,)).fetchone()[0]
            else:
                total = conn.execute("SELECT COUNT(*) FROM tells").fetchone()[0]
                unread = conn.execute("SELECT COUNT(*) FROM tells WHERE read_at IS NULL").fetchone()[0]
            
            return {
                "total": total,
                "unread": unread,
                "read": total - unread
            }


def format_tells_for_injection(tells: List[Tell]) -> str:
    """Format tells as a header block for file injection"""
    if not tells:
        return ""
    
    lines = [
        "# ⚠️ UNREAD MESSAGES",
        ""
    ]
    
    for tell in tells:
        lines.append(tell.format_header())
        lines.append("")
    
    lines.append("---")
    lines.append("")
    
    return "\n".join(lines)


def format_inbox(tells: List[Tell], show_read: bool = False) -> str:
    """Format tells for inbox view"""
    if not tells:
        return "# 📬 Inbox\n\nNo messages.\n"
    
    lines = ["# 📬 Inbox", ""]
    
    unread = [t for t in tells if not t.read_at]
    read = [t for t in tells if t.read_at]
    
    if unread:
        lines.append(f"## Unread ({len(unread)})")
        lines.append("")
        for tell in unread:
            lines.append(tell.format_header())
            lines.append("")
    
    if show_read and read:
        lines.append(f"## Read ({len(read)})")
        lines.append("")
        for tell in read[:10]:  # Limit read messages
            lines.append(tell.format_header())
            lines.append("")
    
    return "\n".join(lines)
