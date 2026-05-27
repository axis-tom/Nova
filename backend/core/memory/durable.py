"""DurableSession — SQLite 持久化层（实现 StateBackend Protocol）

职责：
1. 会话状态持久化（conversations 表）
2. 消息历史按序存储（messages 表）
3. 支持 agent_id 分区（多 Agent 协作预留）
4. 乐观锁版本控制（version 字段）
"""

import sqlite3
import json
import time
import asyncio
from pathlib import Path
from typing import Dict, Any, Optional, List
from contextlib import asynccontextmanager
from threading import Lock

from backend.config.config import settings


class DurableSession:
    """SQLite 实现的 StateBackend"""

    def __init__(self, db_path: str = None):
        if db_path is None:
            db_path = str(Path(settings.DATA_DIR) / "agent_sessions.sqlite")

        self.db_path = db_path
        self._locks: Dict[str, Lock] = {}  # conv_id -> Lock
        self._init_db()

    def _init_db(self):
        """初始化数据库表结构"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # conversations 表：存储会话状态
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS conversations (
                conv_id     TEXT NOT NULL,
                agent_id    TEXT DEFAULT '__shared__',
                title       TEXT,
                state_json  TEXT,
                version     INTEGER DEFAULT 1,
                created_at  REAL,
                updated_at  REAL,
                PRIMARY KEY (conv_id, agent_id)
            )
        """)

        # messages 表：存储消息历史
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                conv_id     TEXT NOT NULL,
                agent_id    TEXT DEFAULT '__shared__',
                role        TEXT NOT NULL,
                content     TEXT NOT NULL,
                tool_name   TEXT,
                created_at  REAL NOT NULL
            )
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_messages_conv
            ON messages(conv_id, created_at)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_messages_agent
            ON messages(conv_id, agent_id)
        """)

        # analysis_checkpoints 表：存储分析树 checkpoint 快照
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS analysis_checkpoints (
                id              TEXT PRIMARY KEY,
                conversation_id TEXT NOT NULL,
                invocation_id   TEXT NOT NULL,
                agent_name      TEXT NOT NULL,
                dimensions_json TEXT,
                state_json      TEXT,
                summary_json    TEXT,
                created_at      TEXT NOT NULL
            )
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_checkpoints_conv
            ON analysis_checkpoints(conversation_id, created_at)
        """)

        conn.commit()
        conn.close()

    def load_state(
        self,
        conv_id: str,
        agent_id: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """加载会话状态（同步，供 SessionStore 在锁内调用）"""
        agent_id = agent_id or "__shared__"

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute(
            "SELECT state_json, version FROM conversations WHERE conv_id = ? AND agent_id = ?",
            (conv_id, agent_id)
        )
        row = cursor.fetchone()
        conn.close()

        if not row or not row[0]:
            return None

        state_data = json.loads(row[0])
        state_data["__version__"] = row[1]  # 附加版本号供乐观锁使用
        return state_data

    def save_state(
        self,
        conv_id: str,
        state_data: Dict[str, Any],
        agent_id: Optional[str] = None,
        expected_version: Optional[int] = None
    ) -> None:
        """保存会话状态（同步，供 SessionStore 在锁内调用）"""
        agent_id = agent_id or "__shared__"
        now = time.time()

        # 移除内部字段
        state_copy = {k: v for k, v in state_data.items() if not k.startswith("__")}
        state_json = json.dumps(state_copy, ensure_ascii=False)

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # 检查是否已存在
        cursor.execute(
            "SELECT version FROM conversations WHERE conv_id = ? AND agent_id = ?",
            (conv_id, agent_id)
        )
        row = cursor.fetchone()

        if row:
            # 更新现有记录
            current_version = row[0]

            # 乐观锁检查
            if expected_version is not None and current_version != expected_version:
                conn.close()
                raise ValueError(
                    f"Version conflict: expected {expected_version}, got {current_version}"
                )

            new_version = current_version + 1
            cursor.execute(
                """
                UPDATE conversations
                SET state_json = ?, version = ?, updated_at = ?
                WHERE conv_id = ? AND agent_id = ?
                """,
                (state_json, new_version, now, conv_id, agent_id)
            )
        else:
            # 插入新记录
            cursor.execute(
                """
                INSERT INTO conversations (conv_id, agent_id, state_json, version, created_at, updated_at)
                VALUES (?, ?, ?, 1, ?, ?)
                """,
                (conv_id, agent_id, state_json, now, now)
            )

        conn.commit()
        conn.close()

    @asynccontextmanager
    async def lock(self, conv_id: str, timeout: float = 5.0):
        """获取会话写锁（当前实现：threading.Lock，未来可换 Redis 分布式锁）"""
        if conv_id not in self._locks:
            self._locks[conv_id] = Lock()

        lock = self._locks[conv_id]
        acquired = lock.acquire(timeout=timeout)

        if not acquired:
            raise TimeoutError(f"Failed to acquire lock for {conv_id} within {timeout}s")

        try:
            yield
        finally:
            lock.release()

    async def append_message(
        self,
        conv_id: str,
        role: str,
        content: str,
        tool_name: Optional[str] = None,
        agent_id: Optional[str] = None
    ) -> None:
        """追加消息到历史记录"""
        agent_id = agent_id or "__shared__"
        now = time.time()

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute(
            """
            INSERT INTO messages (conv_id, agent_id, role, content, tool_name, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (conv_id, agent_id, role, content, tool_name, now)
        )

        conn.commit()
        conn.close()

    async def get_messages(
        self,
        conv_id: str,
        limit: int = 50,
        agent_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """获取消息历史（按时间倒序）"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        if agent_id:
            cursor.execute(
                """
                SELECT role, content, tool_name, created_at
                FROM messages
                WHERE conv_id = ? AND agent_id = ?
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (conv_id, agent_id, limit)
            )
        else:
            # 查询所有 agent_id 的消息
            cursor.execute(
                """
                SELECT role, content, tool_name, created_at
                FROM messages
                WHERE conv_id = ?
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (conv_id, limit)
            )

        rows = cursor.fetchall()
        conn.close()

        # 转为字典列表，并反转顺序（最早的在前）
        messages = [dict(row) for row in rows]
        messages.reverse()
        return messages

    async def list_conversations(self, limit: int = 20) -> List[Dict[str, Any]]:
        """列出最近的会话"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT conv_id, agent_id, title, updated_at
            FROM conversations
            WHERE agent_id = '__shared__'
            ORDER BY updated_at DESC
            LIMIT ?
            """,
            (limit,)
        )

        rows = cursor.fetchall()
        conn.close()

        return [dict(row) for row in rows]

    async def delete_conversation(self, conv_id: str) -> None:
        """删除会话及其所有消息"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("DELETE FROM conversations WHERE conv_id = ?", (conv_id,))
        cursor.execute("DELETE FROM messages WHERE conv_id = ?", (conv_id,))

        conn.commit()
        conn.close()

    async def cleanup_expired(self, max_age_days: int = 30) -> int:
        """清理过期会话"""
        cutoff = time.time() - (max_age_days * 86400)

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # 查找过期会话
        cursor.execute(
            "SELECT DISTINCT conv_id FROM conversations WHERE updated_at < ?",
            (cutoff,)
        )
        expired_ids = [row[0] for row in cursor.fetchall()]

        # 删除
        for conv_id in expired_ids:
            cursor.execute("DELETE FROM conversations WHERE conv_id = ?", (conv_id,))
            cursor.execute("DELETE FROM messages WHERE conv_id = ?", (conv_id,))

        conn.commit()
        conn.close()

        return len(expired_ids)

    def _cleanup_expired_sync(self, max_age_days: int = 30) -> int:
        """同步版 cleanup_expired，供启动时非 async 上下文调用"""
        cutoff = time.time() - (max_age_days * 86400)

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute(
            "SELECT DISTINCT conv_id FROM conversations WHERE updated_at < ?",
            (cutoff,)
        )
        expired_ids = [row[0] for row in cursor.fetchall()]

        for conv_id in expired_ids:
            cursor.execute("DELETE FROM conversations WHERE conv_id = ?", (conv_id,))
            cursor.execute("DELETE FROM messages WHERE conv_id = ?", (conv_id,))

        conn.commit()
        conn.close()

        return len(expired_ids)


# ── Checkpoint 操作 ──

    def save_checkpoint(
        self,
        checkpoint_id: str,
        conversation_id: str,
        invocation_id: str,
        agent_name: str,
        dimensions_json: str,
        state_json: str,
        summary_json: str,
    ) -> None:
        """保存分析树 checkpoint 快照"""
        from datetime import datetime
        now = datetime.now().isoformat()
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT OR REPLACE INTO analysis_checkpoints
            (id, conversation_id, invocation_id, agent_name, dimensions_json, state_json, summary_json, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (checkpoint_id, conversation_id, invocation_id, agent_name, dimensions_json, state_json, summary_json, now),
        )
        conn.commit()
        conn.close()

    def load_checkpoint(self, checkpoint_id: str) -> Optional[Dict[str, Any]]:
        """加载单个 checkpoint"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM analysis_checkpoints WHERE id = ?", (checkpoint_id,))
        row = cursor.fetchone()
        conn.close()
        if not row:
            return None
        return dict(row)

    def list_checkpoints(self, conversation_id: str) -> List[Dict[str, Any]]:
        """列出某个会话的所有 checkpoints（按时间升序）"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM analysis_checkpoints WHERE conversation_id = ? ORDER BY created_at ASC",
            (conversation_id,),
        )
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]

    def delete_checkpoints_after(
        self, conversation_id: str, invocation_id: str
    ) -> int:
        """删除指定 invocation 之后的所有 checkpoints（用于回溯）"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        # 找到该 invocation 的 created_at
        cursor.execute(
            "SELECT created_at FROM analysis_checkpoints WHERE invocation_id = ?",
            (invocation_id,),
        )
        row = cursor.fetchone()
        if not row:
            conn.close()
            return 0
        cutoff = row[0]
        cursor.execute(
            "DELETE FROM analysis_checkpoints WHERE conversation_id = ? AND created_at > ?",
            (conversation_id, cutoff),
        )
        deleted = cursor.rowcount
        conn.commit()
        conn.close()
        return deleted


# 全局单例
_durable_session: Optional[DurableSession] = None


def get_durable_session() -> DurableSession:
    """获取全局 DurableSession 实例"""
    global _durable_session
    if _durable_session is None:
        _durable_session = DurableSession()
    return _durable_session
