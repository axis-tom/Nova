class NovaException(Exception):
    """Nova基础异常"""
    def __init__(self, message: str, code: int = 500):
        self.message = message
        self.code = code
        super().__init__(message)

class AgentError(NovaException):
    """智能体执行错误"""
    pass

class OrchestratorError(NovaException):
    """调度引擎错误"""
    pass

class SOPNotFoundError(OrchestratorError):
    """SOP定义未找到"""
    pass

class StepExecutionError(OrchestratorError):
    """SOP步骤执行失败"""
    def __init__(self, step_name: str, agent_name: str, reason: str):
        self.step_name = step_name
        self.agent_name = agent_name
        self.reason = reason
        super().__init__(f"Step '{step_name}' with agent '{agent_name}' failed: {reason}")

class MessageBusError(NovaException):
    """消息总线错误"""
    pass

class AuditError(NovaException):
    """审计日志错误"""
    pass