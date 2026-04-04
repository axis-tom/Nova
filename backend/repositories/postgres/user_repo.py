from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete
from backend.models.db import User
from backend.models.user import UserCreate, UserUpdate, UserInDB

class UserRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get(self, user_id: int) -> UserInDB | None:
        result = await self.db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        if user:
            return UserInDB.model_validate(user, from_attributes=True)
        return None

    async def get_by_email(self, email: str) -> UserInDB | None:
        result = await self.db.execute(select(User).where(User.email == email))
        user = result.scalar_one_or_none()
        if user:
            return UserInDB.model_validate(user, from_attributes=True)
        return None

    async def create(self, data: UserCreate) -> UserInDB:
        # data 包含 email, name, password（已哈希）, company, phone
        user = User(**data.model_dump())
        self.db.add(user)
        await self.db.commit()
        await self.db.refresh(user)
        return UserInDB.model_validate(user, from_attributes=True)

    async def update(self, user_id: int, data: UserUpdate) -> UserInDB | None:
        # 仅更新非 None 字段
        update_dict = data.model_dump(exclude_unset=True)
        if not update_dict:
            return await self.get(user_id)

        stmt = update(User).where(User.id == user_id).values(**update_dict).returning(User)
        result = await self.db.execute(stmt)
        await self.db.commit()
        user = result.scalar_one_or_none()
        if user:
            return UserInDB.model_validate(user, from_attributes=True)
        return None

    async def delete(self, user_id: int) -> bool:
        stmt = delete(User).where(User.id == user_id)
        result = await self.db.execute(stmt)
        await self.db.commit()
        return result.rowcount > 0