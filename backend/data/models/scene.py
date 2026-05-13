from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional

class SceneBase(BaseModel):
    """场景基础信息"""
    name: str = Field(..., min_length=1, max_length=50)
    description: Optional[str] = None
    icon: Optional[str] = None
    is_installed: bool = False  # 用户是否安装

class SceneCreate(SceneBase):
    pass

class SceneUpdate(BaseModel):
    """更新场景（部分更新）"""
    name: Optional[str] = None
    description: Optional[str] = None
    icon: Optional[str] = None
    is_installed: Optional[bool] = None

class SceneInDB(SceneBase):
    """数据库中的场景模型（用于存储用户安装的场景）"""
    id: int
    user_id: int
    created_at: datetime

class SceneOut(SceneBase):
    """返回给前端的场景模型"""
    id: int
    installed: bool  # 是否已安装（可基于用户关联表判断）