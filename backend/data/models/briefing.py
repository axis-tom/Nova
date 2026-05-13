from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional, Dict, Any, List

class BriefingBase(BaseModel):
    """简报基础信息"""
    title: str = Field(..., min_length=1, max_length=200)
    content: str
    source_data: Optional[Dict[str, Any]] = Field(default_factory=dict)  # 原始数据摘要

class BriefingCreate(BriefingBase):
    """创建简报"""
    pass

class BriefingUpdate(BaseModel):
    """更新简报（部分更新）"""
    title: Optional[str] = Field(None, min_length=1, max_length=200)
    content: Optional[str] = None
    source_data: Optional[Dict[str, Any]] = None

class BriefingInDB(BriefingBase):
    """数据库中的简报模型"""
    id: int
    user_id: int
    created_at: datetime
    updated_at: Optional[datetime] = None   # 改为可选，允许 None: datetime

class BriefingOut(BriefingBase):
    """返回给前端的简报模型"""
    id: int
    user_id: int
    created_at: datetime
    updated_at: Optional[datetime] = None   # 改为可选，允许 None: datetime

class BriefingListResponse(BaseModel):
    """简报列表响应（分页）"""
    items: List[BriefingOut]
    total: int
    skip: int
    limit: int

    