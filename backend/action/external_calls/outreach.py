import asyncio
from typing import List, Dict, Any
from backend.agents.base import Agent, AgentInput, AgentOutput
from backend.connectors.outbound.notion import NotionConnector
from backend.connectors.outbound.feishu import FeishuConnector
from backend.connectors.outbound.todoist import TodoistConnector

class OutboundAgent(Agent):
    """
    跨平台推送智能体：
    将内容（如简报、任务）推送到外部平台（Notion、飞书、Todoist等）。
    """
    name = "outbound_agent"
    description = "将内容推送到指定外部平台"

    async def execute(self, input_data: AgentInput) -> AgentOutput:
        targets = input_data.data.get("targets", [])  # 列表，每个包含 platform 和 config
        content = input_data.data.get("content", {})  # 要推送的内容

        if not targets or not content:
            return AgentOutput(
                result=[],
                metadata={"error": "Missing targets or content"},
                error="Invalid input"
            )

        results = []
        for target in targets:
            platform = target.get("platform")
            config = target.get("config", {})
            success = await self._push_to_platform(platform, content, config)
            results.append({
                "platform": platform,
                "success": success
            })
            await asyncio.sleep(0.2)

        return AgentOutput(
            result=results,
            metadata={"count": len(results), "success_count": sum(1 for r in results if r["success"])}
        )

    async def _push_to_platform(self, platform: str, content: Dict, config: Dict) -> bool:
        """根据平台调用对应的连接器"""
        try:
            if platform == "notion":
                connector = NotionConnector()
                # 假设推送内容为页面
                await connector.create_page(config.get("database_id"), content)
            elif platform == "feishu":
                connector = FeishuConnector()
                await connector.send_message(config.get("chat_id"), content.get("text", ""))
            elif platform == "todoist":
                connector = TodoistConnector()
                # 假设内容为任务列表
                for task in content.get("tasks", []):
                    await connector.add_task(task.get("title"), **task.get("options", {}))
            else:
                return False
            return True
        except Exception as e:
            print(f"Push to {platform} failed: {e}")
            return False
