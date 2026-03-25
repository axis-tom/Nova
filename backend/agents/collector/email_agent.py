from typing import Dict, Any
import asyncio
from backend.agents.base import Agent, AgentInput, AgentOutput
from backend.connectors.email.imap_client import IMAPClient

class EmailAgent(Agent):
    """邮件采集智能体：从配置的邮箱账号拉取未读邮件"""
    name = "email_agent"
    description = "采集指定邮箱的最新邮件，返回邮件列表"

    async def execute(self, input_data: AgentInput) -> AgentOutput:
        # 从输入中获取邮箱配置（应由上层传递）
        email_config = input_data.config.get("email_config", {})
        if not email_config:
            # 或从数据库获取用户默认邮箱配置
            email_config = await self._get_user_email_config(input_data.user_id)

        if not email_config:
            return AgentOutput(
                result=[],
                metadata={"error": "No email config found"},
                error="No email config"
            )

        try:
            client = IMAPClient(
                host=email_config.get("host"),
                port=email_config.get("port", 993),
                username=email_config.get("username"),
                password=email_config.get("password"),
                use_ssl=email_config.get("use_ssl", True)
            )
            await client.connect()
            # 拉取最近 N 封未读邮件
            emails = await client.fetch_unread(limit=email_config.get("limit", 10))
            await client.disconnect()
            return AgentOutput(
                result=emails,
                metadata={"source": "email", "count": len(emails)}
            )
        except Exception as e:
            return AgentOutput(
                result=[],
                metadata={"error": str(e)},
                error=str(e)
            )

    async def _get_user_email_config(self, user_id: int) -> Dict[str, Any]:
        """模拟从数据库获取用户邮件配置，实际应从 Repository 查询"""
        # 这里简单返回空或默认配置
        return {}