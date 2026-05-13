from backend.common.core import Agent, AgentInput, AgentOutput
from backend.foundation.communication.audit import audit_logger

class AuditorAgent(Agent):
    """
    审计日志记录智能体：
    记录所有操作和调用，用于审计和回溯。
    """
    name = "auditor_agent"
    description = "记录审计日志"

    async def execute(self, input_data: AgentInput) -> AgentOutput:
        # 输入应包含要记录的事件信息
        user_id = input_data.user_id
        action = input_data.data.get("action", "unknown_action")
        details = input_data.data.get("details", {})
        status = input_data.data.get("status", "success")
        error_msg = input_data.data.get("error_msg", None)
        trace_id = input_data.trace_id

        # 调用全局审计记录器
        await audit_logger.log(
            user_id=user_id,
            action=action,
            details=details,
            status=status,
            error_msg=error_msg,
            trace_id=trace_id
        )

        return AgentOutput(
            result={"logged": True},
            metadata={"action": action}
        )
