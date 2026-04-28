import aiosqlite
from typing import Optional, List, Dict, Any
from backend.models.user import UserCreate, UserUpdate, UserInDB
from backend.repositories.base import BaseRepository
from backend.repositories.sqlite.base import SQLiteRepository

class UserRepository(BaseRepository[UserInDB, UserCreate, UserUpdate], SQLiteRepository):
    """SQLite 实现的用户仓库"""

    async def _init_db(self):
        """确保表存在（可在应用启动时调用）"""
        async with await self._get_connection() as conn:
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    email TEXT UNIQUE NOT NULL,
                    name TEXT NOT NULL,
                    hashed_password TEXT NOT NULL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            await conn.commit()

    async def get(self, id: int, user_id: int) -> Optional[UserInDB]:
        async with await self._get_connection() as conn:
            async with conn.execute(
                "SELECT id, email, name, hashed_password, created_at, updated_at FROM users WHERE id = ?",
                (id,)
            ) as cursor:
                row = await cursor.fetchone()
                if row:
                    return UserInDB(
                        id=row[0], email=row[1], name=row[2],
                        hashed_password=row[3], created_at=row[4], updated_at=row[5]
                    )
                return None

    async def list(
        self,
        user_id: int,
        skip: int = 0,
        limit: int = 100,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[UserInDB]:
        # 注意：user_id 在这里其实无用，因为用户表不按用户过滤
        query = "SELECT id, email, name, hashed_password, created_at, updated_at FROM users LIMIT ? OFFSET ?"
        async with await self._get_connection() as conn:
            async with conn.execute(query, (limit, skip)) as cursor:
                rows = await cursor.fetchall()
                return [UserInDB(
                    id=r[0], email=r[1], name=r[2],
                    hashed_password=r[3], created_at=r[4], updated_at=r[5]
                ) for r in rows]

    async def create(self, user_id: int, data: UserCreate) -> UserInDB:
        # user_id 被忽略，因为新用户没有 ID
        async with await self._get_connection() as conn:
            # 假设 data 中包含 password（明文），实际应哈希
            hashed = data.password  # 简化
            cursor = await conn.execute(
                "INSERT INTO users (email, name, hashed_password) VALUES (?, ?, ?) RETURNING id, created_at, updated_at",
                (data.email, data.name, hashed)
            )
            row = await cursor.fetchone()
            await conn.commit()
            return UserInDB(
                id=row[0], email=data.email, name=data.name,
                hashed_password=hashed, created_at=row[1], updated_at=row[2]
            )

    async def update(
        self,
        id: int,
        user_id: int,
        data: UserUpdate
    ) -> Optional[UserInDB]:
        # 构建更新字段
        updates = []
        params = []
        if data.email is not None:
            updates.append("email = ?")
            params.append(data.email)
        if data.name is not None:
            updates.append("name = ?")
            params.append(data.name)
        if not updates:
            return await self.get(id, user_id)
        params.append(id)
        async with await self._get_connection() as conn:
            await conn.execute(
                f"UPDATE users SET {', '.join(updates)}, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                params
            )
            await conn.commit()
            return await self.get(id, user_id)

    async def delete(self, id: int, user_id: int) -> bool:
        async with await self._get_connection() as conn:
            cursor = await conn.execute("DELETE FROM users WHERE id = ?", (id,))
            await conn.commit()
            return cursor.rowcount > 0

    async def count(self, user_id: int, filters: Optional[Dict[str, Any]] = None) -> int:
        async with await self._get_connection() as conn:
            cursor = await conn.execute("SELECT COUNT(*) FROM users")
            row = await cursor.fetchone()
            return row[0] if row else 0