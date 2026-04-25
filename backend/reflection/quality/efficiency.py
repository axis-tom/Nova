from typing import Dict, Any, List
from backend.agents.base import Agent, AgentInput, AgentOutput

class EfficiencyAgent(Agent):
    """
    效率分析智能体：
    分析操作日志，生成效率报告，如注意力消耗、决策疲劳热力图等。
    """
    name = "efficiency_agent"
    description = "分析用户操作效率，生成报告"

    async def execute(self, input_data: AgentInput) -> AgentOutput:
        # 输入可能包含操作日志列表
        logs = input_data.data.get("logs", [])
        if not logs:
            return AgentOutput(
                result={"error": "No logs provided"},
                metadata={},
                error="No logs"
            )

        # 生成效率报告（示例）
        report = self._generate_report(logs)

        return AgentOutput(
            result=report,
            metadata={"log_count": len(logs)}
        )

    def _generate_report(self, logs: List[Dict]) -> Dict[str, Any]:
        """基于日志生成报告（模拟）"""
        # 按动作类型分组计数
        action_counts = {}
        for log in logs:
            action = log.get("action", "unknown")
            action_counts[action] = action_counts.get(action, 0) + 1

        # 计算注意力消耗（假设每个动作消耗一定点数）
        attention_cost = sum(self._get_action_cost(action) * count for action, count in action_counts.items())

        # 模拟决策疲劳热力图（按小时分组）
        hourly_counts = {}
        for log in logs:
            timestamp = log.get("timestamp")
            if timestamp:
                # 假设 timestamp 是 datetime 对象或字符串
                hour = timestamp.hour if hasattr(timestamp, "hour") else 0
                hourly_counts[hour] = hourly_counts.get(hour, 0) + 1

        return {
            "action_counts": action_counts,
            "attention_cost": attention_cost,
            "hourly_activity": hourly_counts,
            "suggestion": "建议在低活动时段处理重要决策。" if max(hourly_counts.values()) > 10 else "活动量适中，保持良好节奏。"
        }

    def _get_action_cost(self, action: str) -> int:
        """返回每个动作的注意力消耗点数（模拟）"""
        if "decision" in action:
            return 5
        elif "view" in action:
            return 1
        else:
            return 2
