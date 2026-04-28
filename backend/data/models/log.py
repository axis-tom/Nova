from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional, Dict, Any, Literal, List
from enum import Enum


class LogStatus(str, Enum):
    """日志状态"""
    SUCCESS = "success"
    FAILURE = "failure"

class LogEntryBase(BaseModel):
    """审计日志基础信息"""
    action: str = Field(..., min_length=1, max_length=100)
    details: Dict[str, Any] = Field(default_factory=dict)
    status: LogStatus
    error_msg: Optional[str] = None

class LogEntryCreate(LogEntryBase):
    """创建日志条目"""
    user_id: int
    trace_id: Optional[str] = None

class LogEntryInDB(LogEntryBase):
    """数据库中的日志模型"""
    id: int
    user_id: int
    trace_id: str
    timestamp: datetime

class LogEntryOut(LogEntryBase):
    """返回给前端的日志模型"""
    id: int
    user_id: int
    trace_id: str
    timestamp: datetime

class LogListResponse(BaseModel):
    """日志列表响应（分页）"""
    items: List[LogEntryOut]
    total: int
    skip: int
    limit: int