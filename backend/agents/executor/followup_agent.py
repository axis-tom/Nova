import asyncio
from typing import List, Dict, Any
from backend.agents.base import Agent, AgentInput, AgentOutput

class FollowupAgent(Agent):
    """
    自动跟进智能体：
    根据待跟进事项，自动发送提醒消息给用户（老板）。
    """
    name = "followup_agent"
    description = "根据任务清单自动发送跟进提醒"

    async def execute(self, input_data: AgentInput) -> AgentOutput:
        tasks = input_data.data.get("tasks", [])
        if not tasks:
            return AgentOutput(
                result=[],
                metadata={"error": "No tasks provided"},
                error="No tasks"
            )

        results = []
        for task in tasks:
            # 根据配置决定提醒方式（此处假设发送到飞书/邮件）
            method = input_data.config.get("method", "feishu")
            if method == "feishu":
                success = await self._send_feishu(task)
            elif method == "email":
                success = await self._send_email(task)
            else:
                success = await self._send_notification(task)

            results.append({
                "task_id": task.get("id"),
                "title": task.get("title"),
                "method": method,
                "success": success
            })
            await asyncio.sleep(0.2)

        return AgentOutput(
            result=results,
            metadata={"count": len(results), "success_count": sum(1 for r in results if r["success"])}
        )

    async def _send_feishu(self, task: Dict[str, Any]) -> bool:
        """发送飞书消息（模拟）"""
        try:
            # 实际应调用飞书机器人 API
            await asyncio.sleep(0.1)
            return True
        except:
            return False

    async def _send_email(self, task: Dict[str, Any]) -> bool:
        """发送邮件（模拟）"""
        await asyncio.sleep(0.1)
        return True

    async def _send_notification(self, task: Dict[str, Any]) -> bool:
        """通用通知（模拟）"""
        await asyncio.sleep(0.1)
        return True