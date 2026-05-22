from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from typing import List, Optional
from backend.data.models.db import Message
from backend.foundation.memory.short_term.conversation_store import MessageInDB, MessageOut

class MessageRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_conversation(self, conversation_id: int) -> List[MessageOut]:
        result = await self.db.execute(
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.timestamp.asc())
        )
        messages = result.scalars().all()
        return [MessageOut.model_validate(m, from_attributes=True) for m in messages]

    async def create(
        self,
        conversation_id: int,
        user_id: int,
        role: str,
        content: str,
        scene_id: Optional[str] = None,
        function: Optional[str] = None,
        model_id: Optional[str] = None
    ) -> MessageOut:
        msg = Message(
            conversation_id=conversation_id,
            user_id=user_id,
            role=role,
            content=content,
            scene_id=scene_id,
            function=function,
            model_id=model_id
        )
        self.db.add(msg)
        await self.db.commit()
        await self.db.refresh(msg)
        return MessageOut.model_validate(msg, from_attributes=True)

    async def delete_by_conversation(self, conversation_id: int) -> bool:
        stmt = delete(Message).where(Message.conversation_id == conversation_id)
        result = await self.db.execute(stmt)
        await self.db.commit()
        return result.rowcount > 0