from typing import Dict, Any, List
from backend.agents.base import Agent, AgentInput, AgentOutput

class OutcomeLearner(Agent):
    """
    决策结果学习智能体：
    根据决策后的成功/失败反馈，调整决策规则或模型权重。
    """
    name = "outcome_learner"
    description = "从决策结果（成功/失败）学习改进"

    async def execute(self, input_data: AgentInput) -> AgentOutput:
        # 输入应包含决策记录和结果反馈
        decisions = input_data.data.get("decisions", [])
        if not decisions:
            return AgentOutput(
                result={"learned": False},
                metadata={"error": "No decisions"},
                error="No decisions"
            )

        # 分析哪些决策成功/失败
        insights = self._analyze_outcomes(decisions)

        # 实际可能更新模型权重或规则（模拟）
        # await self._update_weights(insights)

        return AgentOutput(
            result={"learned": True, "insights": insights},
            metadata={"decision_count": len(decisions)}
        )

    def _analyze_outcomes(self, decisions: List[Dict]) -> List[Dict]:
        """分析决策结果，提取模式"""
        insights = []
        success_count = 0
        failure_count = 0
        for dec in decisions:
            outcome = dec.get("outcome")
            if outcome == "success":
                success_count += 1
            elif outcome == "failure":
                failure_count += 1

        if failure_count > 0:
            insights.append({
                "type": "failure_rate",
                "value": failure_count / len(decisions),
                "suggestion": "决策失败率较高，建议调整决策阈值。"
            })

        # 还可以按决策类型分析
        type_outcomes = {}
        for dec in decisions:
            dec_type = dec.get("type")
            outcome = dec.get("outcome")
            if dec_type not in type_outcomes:
                type_outcomes[dec_type] = {"success": 0, "failure": 0}
            type_outcomes[dec_type][outcome] += 1

        for dec_type, stats in type_outcomes.items():
            if stats.get("failure", 0) > stats.get("success", 0):
                insights.append({
                    "type": "type_risk",
                    "decision_type": dec_type,
                    "suggestion": f"决策类型「{dec_type}」失败率较高，请检查相关规则。"
                })

        return insights
