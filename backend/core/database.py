from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, declarative_base
from backend.core.config import settings

# 创建异步引擎
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,               # 开发时打印 SQL
    future=True,
    pool_pre_ping=True,                # 连接前检测
)

# 会话工厂
AsyncSessionLocal = sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

# 基类，供模型继承
Base = declarative_base()

# 依赖注入函数
async def get_db() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        yield session