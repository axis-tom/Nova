import asyncio
import sys
from pathlib import Path

# 将项目根目录加入 Python 路径
sys.path.insert(0, str(Path(__file__).parent))

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from backend.config.config import settings
from backend.agents.collector.email_agent import EmailAgent
from backend.agents.base import AgentInput

async def test():
    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with async_session() as db:
        # 用户 ID 假设为 1，如果不对可以改成你登录时获得的 ID
        user_id = 1
        agent = EmailAgent(db)
        input_data = AgentInput(user_id=user_id, parameters={})
        output = await agent.execute(input_data)
        print(f"获取到 {output.metadata.get('count', 0)} 封邮件")
        for email in output.result[:5]:
            print(f"主题: {email.get('subject')} | 发件人: {email.get('from')}")
    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(test())