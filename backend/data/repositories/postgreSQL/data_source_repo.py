from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete
from typing import Optional, List, Dict, Any
from backend.data.models.db import DataSource
from backend.data.models.data_source import DataSourceCreate, DataSourceUpdate, DataSourceInDB

class DataSourceRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get(self, source_id: int, user_id: int) -> DataSourceInDB | None:
        result = await self.db.execute(
            select(DataSource).where(DataSource.id == source_id, DataSource.user_id == user_id)
        )
        ds = result.scalar_one_or_none()
        if ds:
            return DataSourceInDB.model_validate(ds, from_attributes=True)
        return None

    async def list(self, user_id: int, skip: int = 0, limit: int = 100, filters: Optional[Dict] = None) -> List[DataSourceInDB]:
        query = select(DataSource).where(DataSource.user_id == user_id).offset(skip).limit(limit)
        # 可扩展 filters 处理（如按 type 过滤）
        if filters:
            for key, value in filters.items():
                if hasattr(DataSource, key):
                    query = query.where(getattr(DataSource, key) == value)
        result = await self.db.execute(query)
        sources = result.scalars().all()
        return [DataSourceInDB.model_validate(s, from_attributes=True) for s in sources]

    async def create(self, user_id: int, data: DataSourceCreate) -> DataSourceInDB:
        # data 已包含处理后的 config（敏感字段已加密）
        ds = DataSource(
            user_id=user_id,
            name=data.name,
            type=data.type,
            config=data.config,
            enabled=data.enabled,
        )
        self.db.add(ds)
        await self.db.commit()
        await self.db.refresh(ds)
        return DataSourceInDB.model_validate(ds, from_attributes=True)

    async def update(self, source_id: int, user_id: int, data: DataSourceUpdate) -> DataSourceInDB | None:
        # 先获取现有记录
        existing = await self.get(source_id, user_id)
        if not existing:
            return None
        update_dict = data.model_dump(exclude_unset=True)
        if not update_dict:
            return existing
        # 注意：config 字段需要合并更新，此处简单覆盖，可根据需求调整
        if "config" in update_dict:
            # 合并 config
            merged_config = {**existing.config, **update_dict["config"]}
            update_dict["config"] = merged_config
        stmt = update(DataSource).where(DataSource.id == source_id, DataSource.user_id == user_id).values(**update_dict).returning(DataSource)
        result = await self.db.execute(stmt)
        await self.db.commit()
        updated = result.scalar_one_or_none()
        if updated:
            return DataSourceInDB.model_validate(updated, from_attributes=True)
        return None

    async def delete(self, source_id: int, user_id: int) -> bool:
        stmt = delete(DataSource).where(DataSource.id == source_id, DataSource.user_id == user_id)
        result = await self.db.execute(stmt)
        await self.db.commit()
        return result.rowcount > 0

    async def count(self, user_id: int, filters: Optional[Dict] = None) -> int:
        query = select(DataSource).where(DataSource.user_id == user_id)
        if filters:
            for key, value in filters.items():
                if hasattr(DataSource, key):
                    query = query.where(getattr(DataSource, key) == value)
        result = await self.db.execute(query)
        return len(result.scalars().all())
    
    async def update_last_collected(self, source_id: int, user_id: int, collected_at: datetime) -> bool:
        """更新数据源的最后采集时间"""
        stmt = update(DataSource).where(
            DataSource.id == source_id,
            DataSource.user_id == user_id
        ).values(last_collected_at=collected_at)
        result = await self.db.execute(stmt)
        await self.db.commit()
        return result.rowcount > 0