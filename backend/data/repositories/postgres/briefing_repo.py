from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete
from typing import Optional, List, Dict, Any
from backend.data.models.db import Briefing
from backend.data.models.briefing import BriefingCreate, BriefingUpdate, BriefingInDB, BriefingOut

class BriefingRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get(self, briefing_id: int, user_id: int) -> Optional[BriefingOut]:
        result = await self.db.execute(
            select(Briefing).where(Briefing.id == briefing_id, Briefing.user_id == user_id)
        )
        briefing = result.scalar_one_or_none()
        if briefing:
            return BriefingOut.model_validate(briefing, from_attributes=True)
        return None

    async def list(self, user_id: int, skip: int = 0, limit: int = 100) -> List[BriefingOut]:
        result = await self.db.execute(
            select(Briefing)
            .where(Briefing.user_id == user_id)
            .order_by(Briefing.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        briefings = result.scalars().all()
        return [BriefingOut.model_validate(b, from_attributes=True) for b in briefings]

    async def create(self, user_id: int, data: BriefingCreate) -> BriefingOut:
        briefing = Briefing(
            user_id=user_id,
            title=data.title,
            content=data.content,
            source_data=data.source_data
        )
        self.db.add(briefing)
        await self.db.commit()
        await self.db.refresh(briefing)
        return BriefingOut.model_validate(briefing, from_attributes=True)

    async def update(self, briefing_id: int, user_id: int, data: BriefingUpdate) -> Optional[BriefingOut]:
        update_dict = data.model_dump(exclude_unset=True)
        if not update_dict:
            return await self.get(briefing_id, user_id)

        stmt = (
            update(Briefing)
            .where(Briefing.id == briefing_id, Briefing.user_id == user_id)
            .values(**update_dict)
            .returning(Briefing)
        )
        result = await self.db.execute(stmt)
        await self.db.commit()
        briefing = result.scalar_one_or_none()
        if briefing:
            return BriefingOut.model_validate(briefing, from_attributes=True)
        return None

    async def delete(self, briefing_id: int, user_id: int) -> bool:
        stmt = delete(Briefing).where(Briefing.id == briefing_id, Briefing.user_id == user_id)
        result = await self.db.execute(stmt)
        await self.db.commit()
        return result.rowcount > 0