from typing import Dict, Any, Optional
from backend.agents.base import Agent, AgentInput, AgentOutput

class DialogManager(Agent):
    """
    对话状态管理智能体：
    维护会话上下文，处理多轮对话状态（如待确认、等待输入等）。
    """
    name = "dialog_manager"
    description = "管理多轮对话状态，维护会话上下文"

    async def execute(self, input_data: AgentInput) -> AgentOutput:
        # 输入应包含当前消息、历史状态、用户ID等
        current_message = input_data.data.get("message", "")
        state = input_data.data.get("state", {})
        user_id = input_data.user_id

        # 根据状态决定下一步动作
        action = self._determine_action(state, current_message)

        # 更新状态
        new_state = self._update_state(state, current_message, action)

        # 返回结果包含要执行的动作和更新后的状态
        return AgentOutput(
            result={
                "action": action,
                "state": new_state,
                "response": action.get("response", "")
            },
            metadata={"user_id": user_id}
        )

    def _determine_action(self, state: Dict, message: str) -> Dict[str, Any]:
        """根据当前状态和用户消息决定下一步动作"""
        # 如果状态为空，说明是对话开始
        if not state:
            return {"type": "intent_recognition", "response": None}

        # 如果状态有 pending_intent，等待用户确认或提供信息
        pending = state.get("pending_intent")
        if pending:
            # 示例：如果意图是生成简报，等待用户指定日期
            if pending == "generate_briefing" and not state.get("date"):
                # 尝试从消息中提取日期
                import re
                date_match = re.search(r'\d{4}-\d{2}-\d{2}', message)
                if date_match:
                    return {"type": "execute", "intent": pending, "params": {"date": date_match.group()}, "response": f"好的，为您生成{date_match.group()}的简报。"}
                else:
                    return {"type": "ask", "question": "请问要查询哪一天的简报？（格式：YYYY-MM-DD）", "response": "请问要查询哪一天的简报？"}
            else:
                # 其他待处理意图的处理
                return {"type": "execute", "intent": pending, "params": state.get("params", {}), "response": f"正在执行{pending}..."}

        # 默认进行意图识别
        return {"type": "intent_recognition", "response": None}

    def _update_state(self, state: Dict, message: str, action: Dict) -> Dict:
        """根据动作更新状态"""
        new_state = state.copy()
        if action["type"] == "intent_recognition":
            # 清空状态，等待识别结果（由外部调用意图识别后设置）
            new_state = {}
        elif action["type"] == "ask":
            # 保持等待状态，记录待处理意图
            new_state["pending_intent"] = action.get("intent", "unknown")
            new_state["params"] = action.get("params", {})
        elif action["type"] == "execute":
            # 执行后清空状态
            new_state = {}
        return new_state