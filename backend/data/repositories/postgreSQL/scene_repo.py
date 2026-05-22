from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from typing import List, Optional
from backend.data.models.db import Scene, UserScene
from backend.data.models.scene import SceneOut

class SceneRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_user(self, user_id: int) -> List[SceneOut]:
        """获取用户已安装的场景列表（通过关联表）"""
        result = await self.db.execute(
            select(Scene)
            .join(UserScene, Scene.id == UserScene.scene_id)
            .where(UserScene.user_id == user_id)
        )
        scenes = result.scalars().all()
        return [SceneOut.model_validate(s, from_attributes=True) for s in scenes]

    async def get_all_available(self, user_id: int) -> List[SceneOut]:
        """获取所有可用场景（商店），并标记是否已安装"""
        # 获取所有场景定义
        result = await self.db.execute(select(Scene))
        all_scenes = result.scalars().all()

        # 获取用户已安装的场景 ID
        installed_result = await self.db.execute(
            select(UserScene.scene_id).where(UserScene.user_id == user_id)
        )
        installed_ids = {row[0] for row in installed_result}

        scenes = []
        for s in all_scenes:
            scene_dict = {**s.__dict__, "installed": s.id in installed_ids}
            scenes.append(SceneOut.model_validate(scene_dict, from_attributes=True))
        return scenes

    async def install(self, user_id: int, scene_id: str) -> bool:
        """安装场景（添加到用户已安装表）"""
        # 检查是否已安装
        existing = await self.db.execute(
            select(UserScene).where(
                UserScene.user_id == user_id,
                UserScene.scene_id == scene_id
            )
        )
        if existing.scalar_one_or_none():
            return False

        user_scene = UserScene(user_id=user_id, scene_id=scene_id)
        self.db.add(user_scene)
        await self.db.commit()
        return True

    async def uninstall(self, user_id: int, scene_id: str) -> bool:
        """卸载场景"""
        stmt = delete(UserScene).where(
            UserScene.user_id == user_id,
            UserScene.scene_id == scene_id
        )
        result = await self.db.execute(stmt)
        await self.db.commit()
        return result.rowcount > 0