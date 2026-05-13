# backend/models/model_folder.py
from pydantic import BaseModel
from datetime import datetime
from typing import Optional, List

class ModelFolderBase(BaseModel):
    name: str
    parent_id: Optional[int] = None

class ModelFolderCreate(ModelFolderBase):
    pass

class ModelFolderUpdate(BaseModel):
    name: Optional[str] = None

class ModelFolderInDB(ModelFolderBase):
    id: int
    user_id: int
    created_at: datetime
    updated_at: datetime

class ModelFolderOut(ModelFolderBase):
    id: int
    children: List['ModelFolderOut'] = []

# 解决循环引用
ModelFolderOut.model_rebuild()


# backend/models/model.py
class ModelBase(BaseModel):
    name: str
    version: Optional[str] = None
    size: Optional[str] = None
    description: Optional[str] = None

class ModelCreate(ModelBase):
    folder_id: int

class ModelUpdate(ModelBase):
    pass

class ModelInDB(ModelBase):
    id: int
    folder_id: int
    user_id: int
    created_at: datetime

class ModelOut(ModelBase):
    id: int
    folder_id: int