"""
Agent Adapter - 统一 Agent 接口适配器（新规范）

将现有的 Agent.execute(AgentInput) 接口适配到新的 Agent.run(state) 接口
实现 state = agent.run(state) 的统一调用方式（新规范）
"""

from typing import Dict, Any, Union
from backend.common.core import Agent, AgentInput, AgentOutput
from backend.common.core import BaseAgent
from backend.foundation.cognition.state_machine.state_machine import State


class AgentAdapter(BaseAgent):
    """
    Agent 适配器类（新规范）
    
    将现有的 Agent.execute(AgentInput) 接口适配到新的 Agent.run(state) 接口
    支持 state = agent.run(state) 的统一调用方式（新规范）
    """
    
    def __init__(self, agent: Agent):
        """
        初始化适配器
        
        Args:
            agent: 要适配的 Agent 实例（必须有 execute 方法）
        """
        self.agent = agent
        
    def run(self, state: State) -> State:
        """
        执行 Agent 逻辑（适配器方法，新规范）
        
        Args:
            state: State对象，包含执行上下文和数据
            
        Returns:
            修改后的State对象
        """
        # 记录Agent开始执行
        state.add_event(f"{self.agent.name}_start")
        
        # 从 State 中提取必要信息
        user_id = state.get("user_id", 0)
        trace_id = state.get("trace_id")
        config = state.get("config", {})
        
        # 创建 AgentInput（向后兼容）
        agent_input = AgentInput(
            data=state.to_plain_dict(),  # 使用 data 部分
            user_id=user_id,
            trace_id=trace_id,
            config=config
        )
        
        try:
            # 执行 Agent（同步调用异步方法）
            import asyncio
            output = asyncio.run(self.agent.execute(agent_input))
            
            # 处理输出
            if isinstance(output, AgentOutput):
                # 将 result 合并到状态
                if isinstance(output.result, dict):
                    state.update(output.result)
                else:
                    # 如果不是字典，将其存储在特定键下
                    state.set("result", output.result)
                
                # 合并元数据
                if output.metadata:
                    state.set("metadata", output.metadata)
                
                # 如果有错误，记录但不抛出
                if output.error:
                    state.set("error", output.error)
                    state.add_event(f"Agent {self.agent.name} 执行出错: {output.error}")
            else:
                # 如果不是 AgentOutput，直接存储
                state.set("result", output)
            
            # 记录执行成功
            state.add_event(f"Agent {self.agent.name} 执行成功")
            state.set("executed", True)
            
        except Exception as e:
            # 记录错误
            state.set("error", str(e))
            state.set("executed", False)
            state.add_event(f"Agent {self.agent.name} 执行异常: {e}")
        
        # 记录Agent结束执行
        state.add_event(f"{self.agent.name}_end")
        
        return state


class AsyncAgentAdapter(BaseAgent):
    """
    异步 Agent 适配器类（新规范）
    
    支持异步调用的适配器版本（新规范）
    """
    
    def __init__(self, agent: Agent):
        """
        初始化异步适配器
        
        Args:
            agent: 要适配的 Agent 实例（必须有 execute 方法）
        """
        self.agent = agent
        
    async def run_async(self, state: State) -> State:
        """
        异步执行 Agent 逻辑（新规范）
        
        Args:
            state: State对象，包含执行上下文和数据
            
        Returns:
            修改后的State对象
        """
        # 记录Agent开始执行
        state.add_event(f"{self.agent.name}_start")
        
        # 从 State 中提取必要信息
        user_id = state.get("user_id", 0)
        trace_id = state.get("trace_id")
        config = state.get("config", {})
        
        # 创建 AgentInput（向后兼容）
        agent_input = AgentInput(
            data=state.to_plain_dict(),  # 使用 data 部分
            user_id=user_id,
            trace_id=trace_id,
            config=config
        )
        
        try:
            # 异步执行 Agent
            output = await self.agent.execute(agent_input)
            
            # 处理输出
            if isinstance(output, AgentOutput):
                # 将 result 合并到状态
                if isinstance(output.result, dict):
                    state.update(output.result)
                else:
                    # 如果不是字典，将其存储在特定键下
                    state.set("result", output.result)
                
                # 合并元数据
                if output.metadata:
                    state.set("metadata", output.metadata)
                
                # 如果有错误，记录但不抛出
                if output.error:
                    state.set("error", output.error)
                    state.add_event(f"Agent {self.agent.name} 执行出错: {output.error}")
            else:
                # 如果不是 AgentOutput，直接存储
                state.set("result", output)
            
            # 记录执行成功
            state.add_event(f"Agent {self.agent.name} 执行成功")
            state.set("executed", True)
            
        except Exception as e:
            # 记录错误
            state.set("error", str(e))
            state.set("executed", False)
            state.add_event(f"Agent {self.agent.name} 执行异常: {e}")
        
        # 记录Agent结束执行
        state.add_event(f"{self.agent.name}_end")
        
        return state
    
    def run(self, state: State) -> State:
        """
        同步执行 Agent 逻辑（包装异步方法，新规范）
        
        Args:
            state: State对象，包含执行上下文和数据
            
        Returns:
            修改后的State对象
        """
        import asyncio
        return asyncio.run(self.run_async(state))


def adapt_agent(agent: Agent) -> BaseAgent:
    """
    适配 Agent 到 BaseAgent 接口
    
    Args:
        agent: 要适配的 Agent 实例
        
    Returns:
        适配后的 BaseAgent 实例
    """
    return AgentAdapter(agent)


def adapt_agent_async(agent: Agent) -> AsyncAgentAdapter:
    """
    适配 Agent 到异步 BaseAgent 接口
    
    Args:
        agent: 要适配的 Agent 实例
        
    Returns:
        适配后的 AsyncAgentAdapter 实例
    """
    return AsyncAgentAdapter(agent)