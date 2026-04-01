from typing import Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime

from backend.agents.base import Agent, AgentInput, AgentOutput
from backend.repositories.postgres.raw_email_repo import RawEmailRepository
from backend.repositories.postgres.briefing_repo import BriefingRepository
from backend.models.briefing import BriefingCreate
from backend.utils.llm_client import llm_client  # 统一 LLM 客户端

class BriefingGeneratorAgent(Agent):
    def __init__(self, db: AsyncSession):
        self.db = db
        self.raw_email_repo = RawEmailRepository(db)
        self.briefing_repo = BriefingRepository(db)

    async def execute(self, input_data: AgentInput) -> AgentOutput:
        user_id = input_data.user_id
        # 获取最近 24 小时内的邮件
        emails = await self.raw_email_repo.get_recent_emails(user_id, hours=24, limit=50)

        if not emails:
            return AgentOutput(
                result={"status": "no_emails"},
                metadata={"message": "无新邮件"}
            )

        # 构造待分析的消息列表（脱敏由 LLM 客户端内部完成）
        messages = []
        for email in emails:
            content = f"主题：{email['subject']}\n发件人：{email['from']}\n内容预览：{email['body_preview']}"
            messages.append(content)

        try:
            # 调用 LLM 客户端生成简报（自动脱敏、路由、降级）
            content = await llm_client.generate_briefing(messages)
        except Exception as e:
            print(f"简报生成失败: {e}")
            content = f"简报生成失败：{e}"

        # 保存简报
        title = f"{datetime.now().strftime('%Y-%m-%d')} 简报"
        briefing = await self.briefing_repo.create(
            user_id,
            BriefingCreate(
                title=title,
                content=content,
                source_data={"email_count": len(emails)}
            )
        )

        return AgentOutput(
            result={"briefing_id": briefing.id, "status": "success"},
            metadata={"email_count": len(emails)}
        )