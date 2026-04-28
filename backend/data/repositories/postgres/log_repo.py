from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete, and_
from typing import Optional, List
from datetime import datetime
from backend.data.models.db import Log
from backend.data.models.log import LogEntryOut, LogEntryCreate, LogStatus

class LogRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get(self, log_id: int, user_id: int) -> Optional[LogEntryOut]:
        result = await self.db.execute(
            select(Log).where(Log.id == log_id, Log.user_id == user_id)
        )
        log = result.scalar_one_or_none()
        if log:
            return LogEntryOut.model_validate(log, from_attributes=True)
        return None

    async def list(
        self,
        user_id: int,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        action: Optional[str] = None,
        skip: int = 0,
        limit: int = 50
    ) -> List[LogEntryOut]:
        conditions = [Log.user_id == user_id]
        if start_time:
            conditions.append(Log.timestamp >= start_time)
        if end_time:
            conditions.append(Log.timestamp <= end_time)
        if action:
            conditions.append(Log.action == action)

        query = select(Log).where(and_(*conditions)).order_by(Log.timestamp.desc()).offset(skip).limit(limit)
        result = await self.db.execute(query)
        logs = result.scalars().all()
        return [LogEntryOut.model_validate(l, from_attributes=True) for l in logs]

    async def create(self, data: LogEntryCreate) -> LogEntryOut:
        log = Log(
            user_id=data.user_id,
            action=data.action,
            details=data.details,
            status=data.status.value,  # 转为字符串
            error_msg=data.error_msg,
            trace_id=data.trace_id or ""
        )
        self.db.add(log)
        await self.db.commit()
        await self.db.refresh(log)
        return LogEntryOut.model_validate(log, from_attributes=True)

    async def delete_older_than(self, days: int) -> int:
        """删除 days 天前的日志，返回删除条数"""
        cutoff = datetime.utcnow() - timedelta(days=days)
        stmt = delete(Log).where(Log.timestamp < cutoff)
        result = await self.db.execute(stmt)
        await self.db.commit()
        return result.rowcount