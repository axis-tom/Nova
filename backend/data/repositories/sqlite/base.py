import aiosqlite
from typing import Optional
from backend.config.config import settings

class SQLiteRepository:
    """SQLite 基础仓库，提供连接获取"""
    def __init__(self):
        self.db_path = settings.DATABASE_URL.replace("sqlite:///", "")  # 去掉前缀

    async def _get_connection(self) -> aiosqlite.Connection:
        return aiosqlite.connect(self.db_path)