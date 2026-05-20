from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
import asyncio
import logging
from pydantic import BaseModel, Field
from backend.common.core.state import State

logger = logging.getLogger(__name__)

class AgentInput(BaseModel):
    """智能体输入模型（向后兼容）"""
    data: Dict[str, Any] = Field(default_factory=dict, description="输入数据")
    user_id: int = Field(..., description="用户ID")
    trace_id: Optional[str] = Field(None, description="链路追踪ID")
    config: Optional[Dict[str, Any]] = Field(default_factory=dict, description="运行时配置")

    class Config:
        arbitrary_types_allowed = True

class AgentOutput(BaseModel):
    """智能体输出模型（向后兼容）"""
    result: Any = Field(..., description="执行结果")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="附加元数据（耗时、模型等）")
    error: Optional[str] = Field(None, description="错误信息（如果失败）")

class Agent(ABC):
    """智能体抽象基类，所有智能体必须继承并实现 run 方法"""
    name: str = "base_agent"
    description: str = "Base agent for all agents"
    llm: Optional[Any] = None

    async def llm_invoke(self, prompt: str, system: str = "") -> Optional[str]:
        """调用内嵌 LLM，失败返回 None（调用方自行 fallback 到规则引擎）"""
        if not self.llm:
            return None
        try:
            from langchain_core.messages import SystemMessage, HumanMessage
            messages: List[Any] = []
            if system:
                messages.append(SystemMessage(content=system))
            messages.append(HumanMessage(content=prompt))
            response = await self.llm.ainvoke(messages)
            return response.content
        except Exception as e:
            logger.warning(f"[{self.name}] LLM invoke failed, falling back to rules: {e}")
            return None

    @abstractmethod
    def run(self, state: State) -> State:
        """
        执行智能体逻辑（新规范）
        
        新规范要求：
        1. 接受 State 对象作为输入
        2. 在方法开始和结束时添加事件
        3. 通过 state.set() 设置结果
        4. 返回修改后的 State 对象
        
        :param state: 状态对象，包含执行上下文和数据
        :return: 修改后的状态对象
        """
        raise NotImplementedError

    async def execute(self, input_data: AgentInput) -> AgentOutput:
        """
        向后兼容的 execute 方法（已弃用）
        
        注意：新代码应该使用 run(state) 方法
        此方法仅为向后兼容保留，会调用 run 方法并转换接口
        
        转换规则：
        1. 如果state中有"result"键，则使用它作为结果
        2. 否则，返回整个state的data部分作为结果
        3. 从state.meta中提取metadata
        4. 从state中提取error信息
        """
        # 将 AgentInput 转换为 State
        state = State(input_data.data)
        state.set_meta("user_id", input_data.user_id)
        if input_data.trace_id:
            state.set_meta("trace_id", input_data.trace_id)
        if input_data.config:
            state.set_meta("config", input_data.config)
        
        # 执行 run 方法（支持同步和异步）
        run_method = self.run
        if asyncio.iscoroutinefunction(run_method):
            result_state = await run_method(state)
        else:
            result_state = run_method(state)
        
        # 将 State 转换为 AgentOutput
        # 优先使用"result"键，否则使用整个data部分
        if "result" in result_state:
            result = result_state.get("result")
        else:
            # 返回整个data部分，但排除一些内部键
            result = result_state.to_plain_dict()
            # 移除可能不需要的键
            for key in ["error", "metadata", "executed"]:
                if key in result:
                    del result[key]
        
        # 从meta中提取metadata
        metadata = {}
        for key in result_state.meta:
            if key not in ["user_id", "trace_id", "config", "step"]:
                metadata[key] = result_state.meta[key]
        
        # 提取error信息
        error = result_state.get("error")
        
        return AgentOutput(
            result=result,
            metadata=metadata,
            error=error
        )

    async def _call_model(self, prompt: str, model: Optional[str] = None) -> str:
        """
        调用模型服务的辅助方法（子类可使用）
        实际应通过 model_clients 模块实现
        """
        from backend.foundation.communication.model_clients.ollama import ollama_client
        # 示例调用
        response = await ollama_client.generate(prompt, model=model)
        return response
