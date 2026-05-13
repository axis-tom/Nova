"""
Node Runner - 节点运行器
执行图节点中的智能体逻辑
"""

from typing import Dict, Any, Optional, Callable
from backend.common.core import Agent, AgentInput, AgentOutput
from backend.common.core import BaseAgent
from backend.common.contracts import AgentRegistry
from backend.common.core.state import State
from backend.foundation.cognition.state_machine.agent_adapter import adapt_agent, adapt_agent_async


class NodeRunner:
    """
    节点运行器
    
    执行图节点中的智能体逻辑，支持：
    1. 同步和异步执行
    2. 输入/输出转换
    3. 错误处理和重试
    """
    
    def __init__(self, db=None):
        self.db = db
    
    def run_node(self, node_config: Dict[str, Any], state: State) -> State:
        """
        执行节点（同步）
        
        Args:
            node_config: 节点配置
            state: 当前状态
            
        Returns:
            执行后的状态
        """
        agent_name = node_config.get("agent")
        if not agent_name:
            raise ValueError("Node config must contain 'agent'")
        
        # 获取智能体
        agent = self._get_agent(agent_name)
        
        # 适配接口
        adapted = self._adapt_agent(agent)
        
        # 准备输入
        input_state = self._prepare_input(node_config, state)
        
        # 执行
        result = adapted.run(input_state)
        
        # 处理输出
        return self._process_output(result, state, node_config)
    
    async def run_node_async(self, node_config: Dict[str, Any], state: State) -> State:
        """
        执行节点（异步）
        
        Args:
            node_config: 节点配置
            state: 当前状态
            
        Returns:
            执行后的状态
        """
        agent_name = node_config.get("agent")
        if not agent_name:
            raise ValueError("Node config must contain 'agent'")
        
        # 获取智能体
        agent = self._get_agent(agent_name)
        
        # 适配接口
        adapted = self._adapt_agent_async(agent)
        
        # 准备输入
        input_state = self._prepare_input(node_config, state)
        
        # 执行
        if hasattr(adapted, 'run_async'):
            result = await adapted.run_async(input_state)
        else:
            import asyncio
            result = await asyncio.to_thread(adapted.run, input_state)
        
        # 处理输出
        return self._process_output(result, state, node_config)
    
    def _get_agent(self, agent_name: str):
        """获取智能体实例"""
        try:
            if self.db is not None:
                return AgentRegistry.get(agent_name, self.db)
            return AgentRegistry.get(agent_name)
        except Exception as e:
            raise ValueError(f"Failed to get agent '{agent_name}': {e}")
    
    def _adapt_agent(self, agent):
        """适配智能体到统一接口"""
        if isinstance(agent, Agent):
            return adapt_agent(agent)
        elif isinstance(agent, BaseAgent):
            return agent
        elif hasattr(agent, 'run'):
            return agent
        else:
            raise ValueError(f"Agent '{agent.__class__.__name__}' has no valid interface")
    
    def _adapt_agent_async(self, agent):
        """适配智能体到异步接口"""
        if isinstance(agent, Agent):
            return adapt_agent_async(agent)
        elif isinstance(agent, BaseAgent):
            if hasattr(agent, 'run_async'):
                return agent
            class AsyncWrapper(BaseAgent):
                def __init__(self, agent):
                    self.agent = agent
                async def run_async(self, state):
                    import asyncio
                    return await asyncio.to_thread(self.agent.run, state)
                def run(self, state):
                    return self.agent.run(state)
            return AsyncWrapper(agent)
        elif hasattr(agent, 'run_async'):
            return agent
        elif hasattr(agent, 'run'):
            class AsyncWrapper:
                def __init__(self, agent):
                    self.agent = agent
                async def run_async(self, state):
                    import asyncio
                    return await asyncio.to_thread(self.agent.run, state)
                def run(self, state):
                    return self.agent.run(state)
            return AsyncWrapper(agent)
        else:
            raise ValueError(f"Agent '{agent.__class__.__name__}' has no valid interface")
    
    def _prepare_input(self, node_config: Dict[str, Any], state: State) -> State:
        """准备节点输入"""
        input_fields = node_config.get("input_fields", [])
        if input_fields:
            filtered = {}
            for field in input_fields:
                if field in state:
                    filtered[field] = state[field]
            return State(filtered)
        return state
    
    def _process_output(self, result: Any, state: State, node_config: Dict[str, Any]) -> State:
        """处理节点输出"""
        if isinstance(result, State):
            for key, value in result.data.items():
                state[key] = value
        elif isinstance(result, dict):
            for key, value in result.items():
                state[key] = value
        else:
            node_id = node_config.get("node_id", "unknown")
            state[f"{node_id}_result"] = result
        return state
