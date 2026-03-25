from pydantic import BaseModel, EmailStr, Field
from datetime import datetime
from typing import Optional

class UserBase(BaseModel):
    """用户基础信息"""
    email: EmailStr
    name: str = Field(..., min_length=1, max_length=50)

class UserCreate(UserBase):
    """创建用户时的输入（含密码）"""
    password: str = Field(..., min_length=6)

class UserUpdate(BaseModel):
    """更新用户信息（部分更新）"""
    name: Optional[str] = Field(None, min_length=1, max_length=50)
    email: Optional[EmailStr] = None

class UserInDB(UserBase):
    """数据库中的用户模型（包含敏感字段）"""
    id: int
    hashed_password: str
    created_at: datetime
    updated_at: datetime

class UserOut(UserBase):
    """返回给前端的用户模型（不含敏感信息）"""
    id: int
    created_at: datetime
    updated_at: datetime