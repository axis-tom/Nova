from fastapi import APIRouter, Depends
from typing import List
from backend.data.models.scene import SceneOut
from backend.api.routes.auth import get_current_user
from backend.data.repositories.postgreSQL.scene_repo import SceneRepository
from backend.data.database import get_db
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/scenes", tags=["场景商店"])

@router.get("/", response_model=List[SceneOut])
async def get_installed_scenes(
    current_user = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取当前用户已安装的场景"""
    repo = SceneRepository(db)
    return await repo.get_by_user(current_user.id)

@router.get("/available", response_model=List[SceneOut])
async def get_available_scenes(
    current_user = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取所有可用场景（商店）"""
    repo = SceneRepository(db)
    return await repo.get_all_available(current_user.id)

@router.post("/install/{scene_id}")
async def install_scene(
    scene_id: str,
    current_user = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """安装场景（添加到用户已安装列表）"""
    repo = SceneRepository(db)
    return await repo.install(current_user.id, scene_id)