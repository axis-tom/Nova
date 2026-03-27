# backend/repositories/nocodb/message_repo.py
from typing import List, Optional, Dict, Any
from backend.repositories.base import BaseRepository
from backend.models.conversation import MessageInDB, MessageOut

class MessageRepository(BaseRepository):
    """消息数据仓库（SQLite 实现）"""
    
    table = "messages"
    model_in_db = MessageInDB
    model_out = MessageOut

    async def get_by_conversation(self, conversation_id: int) -> List[MessageOut]:
        """获取某个对话的所有消息（按时间升序）"""
        sql = f"""
            SELECT * FROM {self.table}
            WHERE conversation_id = ?
            ORDER BY timestamp ASC
        """
        rows = await self.db.fetch_all(sql, conversation_id)
        return [self.model_out(**dict(row)) for row in rows]

    async def create(
        self,
        conversation_id: int,
        user_id: int,
        role: str,
        content: str,
        scene_id: Optional[str] = None,
        function: Optional[str] = None,
        model_id: Optional[str] = None
    ) -> MessageOut:
        """创建一条消息"""
        sql = f"""
            INSERT INTO {self.table}
            (conversation_id, user_id, role, content, scene_id, function, model_id, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            RETURNING *
        """
        row = await self.db.fetch_one(
            sql, conversation_id, user_id, role, content, scene_id, function, model_id
        )
        return self.model_out(**dict(row))

    async def delete_by_conversation(self, conversation_id: int) -> bool:
        """删除某个对话的所有消息"""
        sql = f"DELETE FROM {self.table} WHERE conversation_id = ?"
        await self.db.execute(sql, conversation_id)
        return True