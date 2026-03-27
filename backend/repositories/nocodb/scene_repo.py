# backend/repositories/nocodb/scene_repo.py
from typing import List, Dict, Any
from backend.repositories.base import BaseRepository
from backend.models.scene import SceneOut

class SceneRepository(BaseRepository):
    """场景数据仓库（用户已安装场景）"""
    
    table = "user_scenes"  # 用户已安装场景表

    async def get_by_user(self, user_id: int) -> List[SceneOut]:
        """获取用户已安装的场景列表"""
        sql = f"""
            SELECT s.* FROM scenes s
            JOIN {self.table} us ON s.id = us.scene_id
            WHERE us.user_id = ?
        """
        rows = await self.db.fetch_all(sql, user_id)
        # 注意：需要预先定义 scenes 表（场景定义），这里简化处理
        return [SceneOut(**dict(row)) for row in rows]

    async def get_all_available(self, user_id: int) -> List[SceneOut]:
        """获取所有可用场景（商店）"""
        # 假设 scenes 表包含所有场景定义
        sql = "SELECT * FROM scenes"
        rows = await self.db.fetch_all(sql)
        # 获取用户已安装的ID集合
        installed_ids = set()
        if user_id:
            installed_sql = f"SELECT scene_id FROM {self.table} WHERE user_id = ?"
            installed_rows = await self.db.fetch_all(installed_sql, user_id)
            installed_ids = {row["scene_id"] for row in installed_rows}
        scenes = []
        for row in rows:
            s = dict(row)
            s["installed"] = s["id"] in installed_ids
            scenes.append(SceneOut(**s))
        return scenes

    async def install(self, user_id: int, scene_id: str) -> bool:
        """安装场景（添加到用户已安装表）"""
        sql = f"""
            INSERT INTO {self.table} (user_id, scene_id, installed_at)
            VALUES (?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(user_id, scene_id) DO NOTHING
        """
        result = await self.db.execute(sql, user_id, scene_id)
        return result > 0