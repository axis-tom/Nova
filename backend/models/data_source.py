from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional, Dict, Any, Literal
from enum import Enum

class DataSourceType(str, Enum):
    """数据源类型枚举"""
    EMAIL = "email"
    RSS = "rss"
    SOCIAL = "social"
    FINANCIAL = "financial"
    NEWS = "news"

class DataSourceBase(BaseModel):
    """数据源基础信息"""
    name: str = Field(..., min_length=1, max_length=100)
    type: DataSourceType
    config: Dict[str, Any] = Field(default_factory=dict)
    enabled: bool = True

class DataSourceCreate(DataSourceBase):
    """创建数据源"""
    pass

class DataSourceUpdate(BaseModel):
    """更新数据源（部分更新）"""
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    config: Optional[Dict[str, Any]] = None
    enabled: Optional[bool] = None

class DataSourceInDB(DataSourceBase):
    """数据库中的数据源模型"""
    id: int
    user_id: int
    created_at: datetime
    updated_at: datetime

class DataSourceOut(DataSourceBase):
    """返回给前端的数据源模型"""
    id: int
    user_id: int
    created_at: datetime
    updated_at: datetime