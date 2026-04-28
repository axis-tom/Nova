from fastapi import APIRouter, Depends, HTTPException
from typing import List
from backend.models.scene import SceneOut, SceneCreate, SceneUpdate
from backend.foundation.communication.api.v1.auth import get_current_user          # 统一使用backend.communication.api.v1.auth中的依赖
from backend.models.user import UserOut                  # 依赖返回 UserOut 对象
from backend.repositories.nocodb.scene_repo import SceneRepository

router = APIRouter(prefix="/scenes", tags=["场景商店"])

@router.get("/", response_model=List[SceneOut])
async def get_installed_scenes(
    current_user = Depends(get_current_user),
    repo: SceneRepository = Depends(),
):
    """获取当前用户已安装的场景"""
    return await repo.get_by_user(current_user.id)

@router.get("/available", response_model=List[SceneOut])
async def get_available_scenes(
    current_user = Depends(get_current_user),
    repo: SceneRepository = Depends(),
):
    """获取所有可用场景（商店）"""
    return await repo.get_all_available(current_user.id)

@router.post("/install/{scene_id}")
async def install_scene(
    scene_id: str,
    current_user = Depends(get_current_user),
    repo: SceneRepository = Depends(),
):
    """安装场景（添加到用户已安装列表）"""
    return await repo.install(current_user.id, scene_id)
