#!/usr/bin/env python3
"""
每日简报生成：采集邮件并生成简报
用法: python -m backend.utils.daily_briefing
"""

import asyncio
import uuid
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select
from backend.config.config import settings
from backend.foundation.cognition.orchestrator.brain import orchestrator
from backend.data.models.db import DataSource

async def process_user(uid: int, semaphore: asyncio.Semaphore, engine):
    async with semaphore:
        async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        async with async_session() as db:
            trace_id = str(uuid.uuid4())
            context = {"user_id": uid}
            try:
                result = await orchestrator.run_sop(
                    sop_name="daily_briefing",
                    context=context,
                    user_id=uid,
                    db=db,
                    trace_id=trace_id
                )
                print(f"User {uid}: daily briefing completed")
            except Exception as e:
                print(f"User {uid}: daily briefing failed: {e}")

async def main():
    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    # 获取所有有数据源的用户ID
    async with engine.connect() as conn:
        result = await conn.execute(select(DataSource.user_id).distinct())
        user_ids = [row[0] for row in result]
    semaphore = asyncio.Semaphore(5)
    tasks = [process_user(uid, semaphore, engine) for uid in user_ids]
    await asyncio.gather(*tasks)

if __name__ == "__main__":
    asyncio.run(main())