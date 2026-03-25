from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

router = APIRouter(prefix="/data-sources", tags=["数据源"])

class DataSourceBase(BaseModel):
    name: str
    type: str  # email, rss, social, financial, etc.
    config: dict  # 连接配置，如 { "email": "xxx", "password": "xxx" }
    enabled: bool = True

class DataSourceCreate(DataSourceBase):
    pass

class DataSourceOut(DataSourceBase):
    id: int
    user_id: int
    created_at: datetime
    updated_at: datetime

# 模拟数据存储
fake_data_sources = []
next_id = 1

@router.post("/", response_model=DataSourceOut, status_code=status.HTTP_201_CREATED)
async def create_data_source(data_source: DataSourceCreate, user_id: int = 1):  # 实际应从 token 获取
    global next_id
    now = datetime.utcnow()
    new_ds = DataSourceOut(
        id=next_id,
        user_id=user_id,
        **data_source.dict(),
        created_at=now,
        updated_at=now
    )
    fake_data_sources.append(new_ds)
    next_id += 1
    return new_ds

@router.get("/", response_model=List[DataSourceOut])
async def list_data_sources(user_id: int = 1):
    return [ds for ds in fake_data_sources if ds.user_id == user_id]

@router.get("/{ds_id}", response_model=DataSourceOut)
async def get_data_source(ds_id: int, user_id: int = 1):
    for ds in fake_data_sources:
        if ds.id == ds_id and ds.user_id == user_id:
            return ds
    raise HTTPException(status_code=404, detail="Data source not found")

@router.put("/{ds_id}", response_model=DataSourceOut)
async def update_data_source(ds_id: int, update: DataSourceBase, user_id: int = 1):
    for idx, ds in enumerate(fake_data_sources):
        if ds.id == ds_id and ds.user_id == user_id:
            updated = ds.copy(update=update.dict())
            updated.updated_at = datetime.utcnow()
            fake_data_sources[idx] = updated
            return updated
    raise HTTPException(status_code=404, detail="Data source not found")

@router.delete("/{ds_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_data_source(ds_id: int, user_id: int = 1):
    for idx, ds in enumerate(fake_data_sources):
        if ds.id == ds_id and ds.user_id == user_id:
            fake_data_sources.pop(idx)
            return
    raise HTTPException(status_code=404, detail="Data source not found")