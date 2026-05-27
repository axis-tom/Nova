from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional


class ConversationCreate(BaseModel):
    """创建对话请求"""
    project_id: int
    name: str
    scene_id: Optional[str] = None
    model_id: Optional[str] = None


class ConversationUpdate(BaseModel):
    """更新对话"""
    name: Optional[str] = None
    scene_id: Optional[str] = None
    model_id: Optional[str] = None


class ConversationResponse(BaseModel):
    """会话响应"""
    reply: str
    conversation_id: str


class MessageOut(BaseModel):
    """返回给前端的消息模型"""
    id: int
    conversation_id: int
    user_id: int
    role: str
    content: str
    timestamp: Optional[datetime] = None
    scene_id: Optional[str] = None
    function: Optional[str] = None
    model_id: Optional[str] = None

    class Config:
        from_attributes = True


class MessageInDB(BaseModel):
    """数据库中的消息模型"""
    id: int
    user_id: int
    conversation_id: int
    timestamp: datetime

    class Config:
        from_attributes = True


class ConversationOut(BaseModel):
    """返回给前端的对话模型"""
    id: int
    user_id: int
    project_id: Optional[int] = None
    name: str
    scene_id: Optional[str] = None
    model_id: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class ConversationInDB(BaseModel):
    """数据库中的对话模型"""
    id: int
    user_id: int
    project_id: Optional[int] = None
    name: str
    scene_id: Optional[str] = None
    model_id: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True