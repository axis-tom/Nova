from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional, List, Literal
from enum import Enum

class MessageRole(str, Enum):
    """消息角色"""
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"

class MessageBase(BaseModel):
    """消息基础信息"""
    role: MessageRole
    content: str = Field(..., min_length=1)

class MessageCreate(MessageBase):
    """创建消息（用户输入）"""
    pass

class MessageInDB(MessageBase):
    """数据库中的消息模型"""
    id: int
    user_id: int
    conversation_id: str
    timestamp: datetime

class MessageOut(MessageBase):
    """返回给前端的消息模型"""
    id: int
    conversation_id: str
    timestamp: datetime

class ConversationCreate(BaseModel):
    """创建会话"""
    message: str

class ConversationResponse(BaseModel):
    """会话响应"""
    reply: str
    conversation_id: str

class ConversationHistoryResponse(BaseModel):
    """会话历史响应"""
    messages: List[MessageOut]
    conversation_id: str
    user_id: int

class ConversationUpdate(BaseModel):
    """更新会话的请求模型（例如修改标题）"""
    title: Optional[str] = Field(None, description="会话标题")
    # 可添加其他可更新字段

class ConversationOut(BaseModel):
    """会话的响应模型（用于列表或详情）"""
    id: str  # 会话ID（字符串或整数）
    type: str = "conversation"
    user_id: int
    title: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    # 可选：包含最后一条消息等

class ConversationInDB(BaseModel):
    id: int
    user_id: int
    created_at: datetime
    updated_at: datetime