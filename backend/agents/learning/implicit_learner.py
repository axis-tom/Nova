from typing import Dict, Any, List
from backend.agents.base import Agent, AgentInput, AgentOutput

class ImplicitLearner(Agent):
    """
    隐式反馈学习智能体：
    从用户行为（如忽略、处理、点击）学习偏好，更新用户画像。
    """
    name = "implicit_learner"
    description = "从隐式反馈学习用户偏好"

    async def execute(self, input_data: AgentInput) -> AgentOutput:
        # 输入应包含用户行为记录
        actions = input_data.data.get("actions", [])
        if not actions:
            return AgentOutput(
                result={"learned": False},
                metadata={"error": "No actions"},
                error="No actions"
            )

        # 分析行为并更新画像
        learned = self._learn_from_actions(actions)

        # 实际更新数据库（此处模拟）
        # await self._update_user_profile(input_data.user_id, learned)

        return AgentOutput(
            result={"learned": True, "updates": learned},
            metadata={"action_count": len(actions)}
        )

    def _learn_from_actions(self, actions: List[Dict]) -> Dict[str, Any]:
        """从动作中提取偏好更新"""
        # 统计哪些类型的任务被忽略或处理
        ignored_types = []
        processed_types = []
        for action in actions:
            action_type = action.get("type")
            item_type = action.get("item_type")
            if action_type == "ignore":
                ignored_types.append(item_type)
            elif action_type == "process":
                processed_types.append(item_type)

        # 计算偏好权重（示例）
        preferences = {}
        for t in processed_types:
            preferences[t] = preferences.get(t, 0) + 1
        for t in ignored_types:
            preferences[t] = preferences.get(t, 0) - 1

        # 归一化或返回相对权重
        return {"preferences": preferences}