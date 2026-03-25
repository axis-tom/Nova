from abc import ABC, abstractmethod
from typing import Any, Dict, Optional
from pydantic import BaseModel, Field

class AgentInput(BaseModel):
    """智能体输入模型"""
    data: Dict[str, Any] = Field(default_factory=dict, description="输入数据")
    user_id: int = Field(..., description="用户ID")
    trace_id: Optional[str] = Field(None, description="链路追踪ID")
    config: Optional[Dict[str, Any]] = Field(default_factory=dict, description="运行时配置")

    class Config:
        arbitrary_types_allowed = True

class AgentOutput(BaseModel):
    """智能体输出模型"""
    result: Any = Field(..., description="执行结果")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="附加元数据（耗时、模型等）")
    error: Optional[str] = Field(None, description="错误信息（如果失败）")

class Agent(ABC):
    """智能体抽象基类，所有智能体必须继承并实现 execute 方法"""
    name: str = "base_agent"
    description: str = "Base agent for all agents"

    @abstractmethod
    async def execute(self, input_data: AgentInput) -> AgentOutput:
        """
        执行智能体逻辑
        :param input_data: 输入数据
        :return: 输出结果
        """
        raise NotImplementedError

    async def _call_model(self, prompt: str, model: Optional[str] = None) -> str:
        """
        调用模型服务的辅助方法（子类可使用）
        实际应通过 model_clients 模块实现
        """
        from backend.model_clients.ollama_client import ollama_client
        # 示例调用
        response = await ollama_client.generate(prompt, model=model)
        return response