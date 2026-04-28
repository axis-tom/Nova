from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete
from typing import Optional, List, Dict, Any
from backend.data.models.db import Conversation
from backend.foundation.memory.short_term.conversation_store import ConversationInDB, ConversationOut

class ConversationRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_id(self, conv_id: int) -> Optional[ConversationOut]:
        result = await self.db.execute(select(Conversation).where(Conversation.id == conv_id))
        conv = result.scalar_one_or_none()
        if conv:
            return ConversationOut.model_validate(conv, from_attributes=True)
        return None

    async def get_by_user(self, user_id: int, skip: int = 0, limit: int = 50) -> List[ConversationOut]:
        result = await self.db.execute(
            select(Conversation)
            .where(Conversation.user_id == user_id)
            .order_by(Conversation.updated_at.desc())
            .offset(skip)
            .limit(limit)
        )
        convs = result.scalars().all()
        return [ConversationOut.model_validate(c, from_attributes=True) for c in convs]

    async def get_by_project(self, project_id: int) -> List[ConversationOut]:
        result = await self.db.execute(
            select(Conversation)
            .where(Conversation.project_id == project_id)
            .order_by(Conversation.updated_at.desc())
        )
        convs = result.scalars().all()
        return [ConversationOut.model_validate(c, from_attributes=True) for c in convs]

    async def create(
        self,
        user_id: int,
        project_id: int,
        name: str,
        scene_id: Optional[str] = None,
        model_id: Optional[str] = None
    ) -> ConversationOut:
        conv = Conversation(
            user_id=user_id,
            project_id=project_id,
            name=name,
            scene_id=scene_id,
            model_id=model_id
        )
        self.db.add(conv)
        await self.db.commit()
        await self.db.refresh(conv)
        return ConversationOut.model_validate(conv, from_attributes=True)

    async def update(self, conv_id: int, data: Dict[str, Any]) -> Optional[ConversationOut]:
        if not data:
            return await self.get_by_id(conv_id)
        stmt = update(Conversation).where(Conversation.id == conv_id).values(**data).returning(Conversation)
        result = await self.db.execute(stmt)
        await self.db.commit()
        conv = result.scalar_one_or_none()
        if conv:
            return ConversationOut.model_validate(conv, from_attributes=True)
        return None

    async def delete(self, conv_id: int) -> bool:
        stmt = delete(Conversation).where(Conversation.id == conv_id)
        result = await self.db.execute(stmt)
        await self.db.commit()
        return result.rowcount > 0

    async def delete_by_project(self, project_id: int) -> bool:
        stmt = delete(Conversation).where(Conversation.project_id == project_id)
        result = await self.db.execute(stmt)
        await self.db.commit()
        return result.rowcount > 0