# backend/repositories/nocodb/project_repo.py
from typing import List, Optional, Dict, Any
from backend.repositories.base import BaseRepository
from backend.models.project import ProjectInDB, ProjectOut

class ProjectRepository(BaseRepository):
    """项目数据仓库（SQLite 实现）"""
    
    table = "projects"
    model_in_db = ProjectInDB
    model_out = ProjectOut

    async def get_by_user(self, user_id: int) -> List[ProjectOut]:
        """获取用户的所有项目"""
        sql = f"SELECT * FROM {self.table} WHERE user_id = ? ORDER BY created_at DESC"
        rows = await self.db.fetch_all(sql, user_id)
        return [self.model_out(**dict(row)) for row in rows]

    async def get_by_id(self, project_id: int) -> Optional[ProjectOut]:
        """根据 ID 获取项目"""
        sql = f"SELECT * FROM {self.table} WHERE id = ?"
        row = await self.db.fetch_one(sql, project_id)
        if row:
            return self.model_out(**dict(row))
        return None

    async def create(self, user_id: int, name: str) -> ProjectOut:
        """创建项目"""
        sql = f"""
            INSERT INTO {self.table} (user_id, name, created_at, updated_at)
            VALUES (?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            RETURNING *
        """
        row = await self.db.fetch_one(sql, user_id, name)
        return self.model_out(**dict(row))

    async def update(self, project_id: int, data: Dict[str, Any]) -> Optional[ProjectOut]:
        """更新项目（如重命名）"""
        set_clause = ", ".join([f"{k} = ?" for k in data.keys()])
        values = list(data.values())
        values.append(project_id)
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

    async def delete(self, project_id: int) -> bool:
        """删除项目"""
        sql = f"DELETE FROM {self.table} WHERE id = ?"
        result = await self.db.execute(sql, project_id)
        return result > 0