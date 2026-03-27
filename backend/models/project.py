# backend/models/project.py
from pydantic import BaseModel
from datetime import datetime
from typing import Optional, List

class ProjectBase(BaseModel):
    name: str

class ProjectCreate(ProjectBase):
    pass

class ProjectUpdate(BaseModel):
    name: Optional[str] = None

class ProjectInDB(ProjectBase):
    id: int
    user_id: int
    created_at: datetime
    updated_at: datetime

class ProjectOut(ProjectBase):
    id: int
    children: List['ConversationOut'] = []

# 树形结构响应
class TreeNode(BaseModel):
    id: int
    name: str
    type: str  # "project" or "conversation"
    children: List['TreeNode'] = []

TreeNode.model_rebuild()

# 解决循环引用
from backend.models.conversation import ConversationOut
ProjectOut.update_forward_refs()
TreeNode.update_forward_refs()