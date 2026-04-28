"""
Graph Engine - 支持 State 流转的统一接口版本
实现 state = agent.run(state) 的统一调用方式
"""

from typing import Dict, Any, Optional, Union
from backend.common.core import Agent, AgentInput, AgentOutput
from backend.common.core import BaseAgent
from backend.common.contracts import AgentRegistry
from backend.cognition.state_machine.agent_adapter import adapt_agent, adapt_agent_async
from backend.cognition.state_machine.state_machine import State


class GraphEngineV2:
    """
    Graph Engine V2 - 支持 State 流转的统一接口版本
    
    特性：
    1. 支持 state = agent.run(state) 统一接口
    2. 自动适配现有的 Agent.execute(AgentInput) 接口
    3. 支持同步和异步执行
    4. 使用 State 对象进行状态管理
    """
    
    def __init__(self, db=None):
        """
        初始化 GraphEngineV2
        
        Args:
            db: 数据库会话（可选，用于智能体初始化）
        """
        self.db = db
    
    def run(self, graph: Dict[str, Any], state: Union[Dict[str, Any], State]) -> Dict[str, Any]:
        """
        执行线性图（同步版本）
        
        Args:
            graph: 图定义，格式为:
                {
                    "start": "node_id",  # 起始节点ID
                    "nodes": {
                        "node_id": {
                            "agent": "agent_name",  # Agent名称（字符串）
                            "next": "next_node_id"  # 下一个节点ID（可选，None表示结束）
                        },
                        ...
                    }
                }
            state: 初始状态，可以是字典或 State 对象
            
        Returns:
            最终状态字典
        """
        # 获取起始节点
        current_node_id = graph.get("start")
        if not current_node_id:
            raise ValueError("Graph must have a 'start' node")
        
        nodes = graph.get("nodes", {})
        if not nodes:
            raise ValueError("Graph must have at least one node")
        
        # 确保状态是 State 对象
        if not isinstance(state, State):
            state = State(state)
        
        # 线性遍历节点
        while current_node_id:
            node_config = nodes.get(current_node_id)
            if not node_config:
                raise ValueError(f"Node '{current_node_id}' not found in graph")
            
            agent_name = node_config.get("agent")
            if not agent_name or not isinstance(agent_name, str):
                raise ValueError(f"Node '{current_node_id}' must have an 'agent' that is a string (agent name)")
            
            # 使用AgentRegistry获取智能体实例
            try:
                # 根据注册的工厂函数类型传递参数
                if self.db is not None:
                    agent = AgentRegistry.get(agent_name, self.db)
                else:
                    # 尝试无参数获取
                    agent = AgentRegistry.get(agent_name)
            except Exception as e:
                raise ValueError(f"Failed to get agent '{agent_name}' from registry: {e}")
            
            # 适配 Agent 到统一接口
            adapted_agent = self._adapt_agent(agent)
            
            # 执行智能体：state = agent.run(state)
            try:
                # 调用统一的 run 方法
                result = adapted_agent.run(state)
                
                # 处理规范格式：{"state": state_dict, "events": [], "status": "ok"}
                if isinstance(result, dict) and "state" in result:
                    # 新的规范格式
                    state_dict = result["state"]
                    status = result.get("status", "ok")
                    events = result.get("events", [])
                    
                    # 更新状态
                    state = State(state_dict)
                    
                    # 记录执行状态
                    state[f"{current_node_id}_executed"] = True
                    state[f"{current_node_id}_status"] = status
                    if events:
                        state[f"{current_node_id}_events"] = events
                    state.log(f"Node '{current_node_id}' (Agent: {agent_name}) 执行成功，状态: {status}")
                    
                    # 如果状态是错误，记录但不抛出
                    if status == "error":
                        error_msg = result.get("error", "Unknown error")
                        state[f"{current_node_id}_error"] = error_msg
                        state.log(f"Node '{current_node_id}' (Agent: {agent_name}) 执行出错: {error_msg}")
                else:
                    # 兼容旧格式：直接返回状态字典
                    state_dict = result
                    state = State(state_dict)
                    state[f"{current_node_id}_executed"] = True
                    state.log(f"Node '{current_node_id}' (Agent: {agent_name}) 执行成功（旧格式）")
                
            except Exception as e:
                # 记录错误但继续执行（线性图要求）
                state[f"{current_node_id}_error"] = str(e)
                state[f"{current_node_id}_executed"] = False
                state[f"{current_node_id}_status"] = "error"
                state.log(f"Node '{current_node_id}' (Agent: {agent_name}) 执行失败: {e}")
            
            # 获取下一个节点
            current_node_id = node_config.get("next")
        
        return state.to_plain_dict()
    
    async def run_async(self, graph: Dict[str, Any], state: Union[Dict[str, Any], State]) -> Dict[str, Any]:
        """
        异步执行线性图
        
        Args:
            graph: 图定义，格式同上
            state: 初始状态，可以是字典或 State 对象
            
        Returns:
            最终状态字典
        """
        # 获取起始节点
        current_node_id = graph.get("start")
        if not current_node_id:
            raise ValueError("Graph must have a 'start' node")
        
        nodes = graph.get("nodes", {})
        if not nodes:
            raise ValueError("Graph must have at least one node")
        
        # 确保状态是 State 对象
        if not isinstance(state, State):
            state = State(state)
        
        # 线性遍历节点
        while current_node_id:
            node_config = nodes.get(current_node_id)
            if not node_config:
                raise ValueError(f"Node '{current_node_id}' not found in graph")
            
            agent_name = node_config.get("agent")
            if not agent_name or not isinstance(agent_name, str):
                raise ValueError(f"Node '{current_node_id}' must have an 'agent' that is a string (agent name)")
            
            # 使用AgentRegistry获取智能体实例
            try:
                # 根据注册的工厂函数类型传递参数
                if self.db is not None:
                    agent = AgentRegistry.get(agent_name, self.db)
                else:
                    # 尝试无参数获取
                    agent = AgentRegistry.get(agent_name)
            except Exception as e:
                raise ValueError(f"Failed to get agent '{agent_name}' from registry: {e}")
            
            # 适配 Agent 到统一接口
            adapted_agent = self._adapt_agent_async(agent)
            
            # 执行智能体：state = await agent.run_async(state)
            try:
                if hasattr(adapted_agent, 'run_async'):
                    # 使用异步版本
                    result = await adapted_agent.run_async(state)
                else:
                    # 使用同步版本（在线程中运行）
                    import asyncio
                    result = await asyncio.to_thread(adapted_agent.run, state)
                
                # 处理规范格式：{"state": state_dict, "events": [], "status": "ok"}
                if isinstance(result, dict) and "state" in result:
                    # 新的规范格式
                    state_dict = result["state"]
                    status = result.get("status", "ok")
                    events = result.get("events", [])
                    
                    # 更新状态
                    state = State(state_dict)
                    
                    # 记录执行状态
                    state[f"{current_node_id}_executed"] = True
                    state[f"{current_node_id}_status"] = status
                    if events:
                        state[f"{current_node_id}_events"] = events
                    state.log(f"Node '{current_node_id}' (Agent: {agent_name}) 异步执行成功，状态: {status}")
                    
                    # 如果状态是错误，记录但不抛出
                    if status == "error":
                        error_msg = result.get("error", "Unknown error")
                        state[f"{current_node_id}_error"] = error_msg
                        state.log(f"Node '{current_node_id}' (Agent: {agent_name}) 异步执行出错: {error_msg}")
                else:
                    # 兼容旧格式：直接返回状态字典
                    state_dict = result
                    state = State(state_dict)
                    state[f"{current_node_id}_executed"] = True
                    state.log(f"Node '{current_node_id}' (Agent: {agent_name}) 异步执行成功（旧格式）")
                
            except Exception as e:
                # 记录错误但继续执行（线性图要求）
                state[f"{current_node_id}_error"] = str(e)
                state[f"{current_node_id}_executed"] = False
                state[f"{current_node_id}_status"] = "error"
                state.log(f"Node '{current_node_id}' (Agent: {agent_name}) 异步执行失败: {e}")
            
            # 获取下一个节点
            current_node_id = node_config.get("next")
        
        return state.to_plain_dict()
    
    def _adapt_agent(self, agent):
        """
        适配 Agent 到统一接口（同步版本）
        
        Args:
            agent: 从 Registry 获取的 Agent 实例
            
        Returns:
            适配后的 BaseAgent 实例
        """
        if isinstance(agent, Agent):
            # 如果是 Agent 实例（有 execute 方法），使用适配器
            return adapt_agent(agent)
        elif isinstance(agent, BaseAgent):
            # 如果是 BaseAgent 实例（有 run 方法），直接使用
            return agent
        elif hasattr(agent, 'run'):
            # 如果有 run 方法，直接使用
            return agent
        else:
            raise ValueError(f"Agent '{agent.__class__.__name__}' does not have a valid interface (needs 'execute' or 'run' method)")
    
    def _adapt_agent_async(self, agent):
        """
        适配 Agent 到统一接口（异步版本）
        
        Args:
            agent: 从 Registry 获取的 Agent 实例
            
        Returns:
            适配后的支持异步的 Agent 实例
        """
        if isinstance(agent, Agent):
            # 如果是 Agent 实例（有 execute 方法），使用异步适配器
            return adapt_agent_async(agent)
        elif isinstance(agent, BaseAgent):
            # 如果是 BaseAgent 实例，检查是否有异步版本
            if hasattr(agent, 'run_async'):
                return agent
            else:
                # 创建异步包装器
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
            # 如果有 run_async 方法，直接使用
            return agent
        elif hasattr(agent, 'run'):
            # 只有 run 方法，创建异步包装器
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
            raise ValueError(f"Agent '{agent.__class__.__name__}' does not have a valid interface (needs 'execute', 'run', or 'run_async' method)")


# 全局 GraphEngineV2 实例
graph_engine_v2 = GraphEngineV2()


# 兼容性包装器，保持原有接口
class GraphEngine:
    """
    兼容性 Graph Engine，包装 GraphEngineV2 以保持向后兼容
    """
    
    def __init__(self, db=None):
        self.engine = GraphEngineV2(db)
    
    def run(self, graph: Dict[str, Any], state: Dict[str, Any]) -> Dict[str, Any]:
        """
        执行线性图（兼容原有接口）
        """
        return self.engine.run(graph, state)
    
    async def run_async(self, graph: Dict[str, Any], state: Dict[str, Any]) -> Dict[str, Any]:
        """
        异步执行线性图（兼容原有接口）
        """
        return await self.engine.run_async(graph, state)


# 全局 GraphEngine 实例（兼容性版本）
graph_engine = GraphEngine()
