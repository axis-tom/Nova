# backend/repositories/nocodb/conversation_repo.py
from typing import List, Optional, Dict, Any
from backend.repositories.base import BaseRepository
from backend.models.conversation import ConversationInDB, ConversationOut

class ConversationRepository(BaseRepository):
    """对话数据仓库（SQLite 实现）"""
    
    table = "conversations"
    model_in_db = ConversationInDB
    model_out = ConversationOut

    async def get_by_id(self, conv_id: int) -> Optional[ConversationOut]:
        """根据 ID 获取对话"""
        sql = f"SELECT * FROM {self.table} WHERE id = ?"
        row = await self.db.fetch_one(sql, conv_id)
        if row:
            return self.model_out(**dict(row))
        return None

    async def get_by_user(self, user_id: int, skip: int = 0, limit: int = 50) -> List[ConversationOut]:
        """获取用户的所有对话（分页）"""
        sql = f"""
            SELECT * FROM {self.table}
            WHERE user_id = ?
            ORDER BY updated_at DESC
            LIMIT ? OFFSET ?
        """
        rows = await self.db.fetch_all(sql, user_id, limit, skip)
        return [self.model_out(**dict(row)) for row in rows]

    async def get_by_project(self, project_id: int) -> List[ConversationOut]:
        """获取某个项目下的所有对话"""
        sql = f"""
            SELECT * FROM {self.table}
            WHERE project_id = ?
            ORDER BY updated_at DESC
        """
        rows = await self.db.fetch_all(sql, project_id)
        return [self.model_out(**dict(row)) for row in rows]

    async def create(self, user_id: int, project_id: int, name: str,
                     scene_id: Optional[str] = None,
                     model_id: Optional[str] = None) -> ConversationOut:
        """创建对话"""
        sql = f"""
            INSERT INTO {self.table}
            (user_id, project_id, name, scene_id, model_id, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            RETURNING *
        """
        row = await self.db.fetch_one(sql, user_id, project_id, name, scene_id, model_id)
        return self.model_out(**dict(row))

    async def update(self, conv_id: int, data: Dict[str, Any]) -> Optional[ConversationOut]:
        """更新对话（如重命名、修改默认场景/模型）"""
        set_clause = ", ".join([f"{k} = ?" for k in data.keys()])
        values = list(data.values())
        values.append(conv_id)
        sql = f"""
            UPDATE {self.table}
            SET {set_clause}, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            RETURNING *
        """
        row = await self.db.fetch_one(sql, *values)
        if row:
            return self.model_out(**dict(row))
        return None

    async def delete(self, conv_id: int) -> bool:
        """删除对话"""
        sql = f"DELETE FROM {self.table} WHERE id = ?"
        result = await self.db.execute(sql, conv_id)
        return result > 0

    async def delete_by_project(self, project_id: int) -> bool:
        """删除项目下所有对话（通常由项目删除时调用）"""
        sql = f"DELETE FROM {self.table} WHERE project_id = ?"
        await self.db.execute(sql, project_id)
        return True