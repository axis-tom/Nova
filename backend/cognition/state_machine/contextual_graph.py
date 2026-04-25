"""
上下文感知的Graph引擎
确保Graph只能接收ContextualData，禁止访问数据库/IMAP/外部API
Graph内部不得判断env/source，只处理state.payload
"""

from typing import Dict, Any, Union, Optional
from backend.core.state import State
from backend.memory.short_term.contextual_data import ContextualData, ContextWrapper, is_sandbox_data, is_production_data
from backend.agents.registry import AgentRegistry
from backend.utils.logger import logger


class ContextualGraphEngine:
    """
    上下文感知的Graph引擎
    
    强制规范：
    1. Graph只能接收ContextualData格式的数据
    2. Graph禁止访问数据库/IMAP/外部API
    3. Graph内部不得判断env/source
    4. Graph节点只处理state.payload
    5. 确保数据流：collector → ContextWrapper → Graph → AI → output
    """
    
    def __init__(self, db=None):
        """
        初始化ContextualGraphEngine
        
        Args:
            db: 数据库会话（可选，用于智能体初始化）
        """
        self.db = db
        self._strict_mode = True  # 严格模式，强制使用ContextualData
    
    def run(self, graph: Dict[str, Any], state: Union[Dict[str, Any], State]) -> State:
        """
        执行线性图（上下文感知版本）
        
        Args:
            graph: 图定义
            state: 初始状态，必须是ContextualData格式
            
        Returns:
            最终状态（State对象）
        """
        # 确保状态是State对象
        if not isinstance(state, State):
            state = State(state)
        
        # 验证输入数据格式
        if self._strict_mode:
            self._validate_input_state(state)
        
        # 获取起始节点
        node = graph["start"]
        
        # 线性遍历节点
        while node:
            # 获取节点配置
            node_config = graph["nodes"][node]
            
            # 获取智能体名称
            agent_name = node_config["agent"]
            
            # 从注册表获取智能体实例
            try:
                if self.db is not None:
                    agent = AgentRegistry.get(agent_name, self.db)
                else:
                    agent = AgentRegistry.get(agent_name)
            except Exception as e:
                # 记录错误但继续执行
                state.add_event(f"error_get_agent_{agent_name}: {str(e)}")
                state[f"{node}_error"] = str(e)
                state[f"{node}_executed"] = False
                # 获取下一个节点
                node = node_config.get("next")
                continue
            
            # 添加执行事件
            state.add_event(f"run_{agent_name}")
            
            try:
                # 准备Graph节点输入数据
                graph_input_state = self._prepare_graph_input(state, node)
                
                # 执行智能体
                result = agent.run(graph_input_state)
                
                # 处理Graph节点输出
                state = self._process_graph_output(state, result, node, agent_name)
                
                # 标记节点已执行
                state[f"{node}_executed"] = True
                state.add_event(f"complete_{agent_name}")
                
            except Exception as e:
                # 记录错误但继续执行
                state.add_event(f"error_{agent_name}: {str(e)}")
                state[f"{node}_error"] = str(e)
                state[f"{node}_executed"] = False
            
            # 获取下一个节点
            node = node_config.get("next")
        
        return state
    
    async def run_async(self, graph: Dict[str, Any], state: Union[Dict[str, Any], State]) -> State:
        """
        异步执行线性图（上下文感知版本）
        
        Args:
            graph: 图定义
            state: 初始状态，必须是ContextualData格式
            
        Returns:
            最终状态（State对象）
        """
        # 确保状态是State对象
        if not isinstance(state, State):
            state = State(state)
        
        # 验证输入数据格式
        if self._strict_mode:
            self._validate_input_state(state)
        
        # 获取起始节点
        node = graph["start"]
        
        # 线性遍历节点
        while node:
            # 获取节点配置
            node_config = graph["nodes"][node]
            
            # 获取智能体名称
            agent_name = node_config["agent"]
            
            # 从注册表获取智能体实例
            try:
                if self.db is not None:
                    agent = AgentRegistry.get(agent_name, self.db)
                else:
                    agent = AgentRegistry.get(agent_name)
            except Exception as e:
                # 记录错误但继续执行
                state.add_event(f"error_get_agent_{agent_name}: {str(e)}")
                state[f"{node}_error"] = str(e)
                state[f"{node}_executed"] = False
                # 获取下一个节点
                node = node_config.get("next")
                continue
            
            # 添加执行事件
            state.add_event(f"run_{agent_name}")
            
            try:
                # 准备Graph节点输入数据
                graph_input_state = self._prepare_graph_input(state, node)
                
                # 执行智能体（支持异步）
                if hasattr(agent, 'run_async'):
                    result = await agent.run_async(graph_input_state)
                elif hasattr(agent, 'run'):
                    # 使用同步版本（在线程中运行）
                    import asyncio
                    result = await asyncio.to_thread(agent.run, graph_input_state)
                else:
                    raise ValueError(f"Agent '{agent_name}' has no 'run' or 'run_async' method")
                
                # 处理Graph节点输出
                state = self._process_graph_output(state, result, node, agent_name)
                
                # 标记节点已执行
                state[f"{node}_executed"] = True
                state.add_event(f"complete_{agent_name}")
                
            except Exception as e:
                # 记录错误但继续执行
                state.add_event(f"error_{agent_name}: {str(e)}")
                state[f"{node}_error"] = str(e)
                state[f"{node}_executed"] = False
            
            # 获取下一个节点
            node = node_config.get("next")
        
        return state
    
    def _validate_input_state(self, state: State) -> None:
        """
        验证输入状态是否符合ContextualData格式
        
        Args:
            state: 要验证的状态
            
        Raises:
            ValueError: 如果状态不符合格式要求
        """
        # 检查是否有contextual_data字段
        if "contextual_data" not in state:
            # 尝试从其他字段推断
            if "context" in state and "payload" in state:
                # 有context和payload，但格式可能不正确
                logger.warning("State has 'context' and 'payload' but not 'contextual_data'. Attempting to convert.")
                try:
                    # 尝试转换为ContextualData格式
                    contextual_data = {
                        "context": state.get("context"),
                        "payload": state.get("payload")
                    }
                    state.set("contextual_data", contextual_data)
                except Exception as e:
                    raise ValueError(f"Input state does not contain valid contextual data format: {e}")
            else:
                raise ValueError("Input state must contain 'contextual_data' field (or 'context' and 'payload')")
        
        # 验证contextual_data格式
        contextual_data = state.get("contextual_data")
        if not isinstance(contextual_data, dict):
            raise ValueError("contextual_data must be a dictionary")
        
        if "context" not in contextual_data or "payload" not in contextual_data:
            raise ValueError("contextual_data must contain 'context' and 'payload' keys")
        
        # 验证context字段
        context = contextual_data["context"]
        required_context_fields = ["env", "source", "collector", "trace_id"]
        for field in required_context_fields:
            if field not in context:
                raise ValueError(f"context must contain '{field}' field")
    
    def _prepare_graph_input(self, state: State, node: str) -> State:
        """
        准备Graph节点输入数据
        
        Args:
            state: 当前状态
            node: 节点名称
            
        Returns:
            供Graph节点使用的State
        """
        # 创建Graph节点专用的State副本
        graph_state = state.copy()
        
        # 提取payload数据供Graph节点使用
        contextual_data = state.get("contextual_data")
        if contextual_data and "payload" in contextual_data:
            payload = contextual_data["payload"]
            
            # 将payload数据设置到Graph State的data中
            # Graph节点应该只访问这些数据
            for key, value in payload.items():
                graph_state.set(key, value)
            
            # 记录payload提取信息
            graph_state.add_event(f"graph_node_{node}_payload_extracted")
            graph_state.set_meta("payload_keys", list(payload.keys()))
        
        # 设置节点特定的元数据
        graph_state.set_meta("current_node", node)
        graph_state.set_meta("graph_input_prepared", True)
        
        return graph_state
    
    def _process_graph_output(self, state: State, result: Any, node: str, agent_name: str) -> State:
        """
        处理Graph节点输出
        
        Args:
            state: 当前状态
            result: Graph节点执行结果
            node: 节点名称
            agent_name: 智能体名称
            
        Returns:
            更新后的状态
        """
        if isinstance(result, State):
            # 如果返回的是State对象，提取其中的数据
            
            # 获取Graph节点处理后的数据
            graph_output_data = {}
            for key in result.data:
                if key not in ["contextual_data", "context", "payload"]:
                    graph_output_data[key] = result.data[key]
            
            # 更新payload数据
            contextual_data = state.get("contextual_data", {})
            if "payload" in contextual_data:
                contextual_data["payload"].update(graph_output_data)
                state.set("contextual_data", contextual_data)
            
            # 合并元数据和事件
            for key, value in result.meta.items():
                if key not in ["current_node", "graph_input_prepared", "payload_keys"]:
                    state.set_meta(f"{node}_{key}", value)
            
            state.events.extend(result.events)
            
        elif isinstance(result, dict):
            # 如果返回的是字典，更新到payload中
            contextual_data = state.get("contextual_data", {})
            if "payload" in contextual_data:
                contextual_data["payload"].update(result)
                state.set("contextual_data", contextual_data)
            else:
                # 如果没有payload，创建新的
                state.set("contextual_data", {
                    "context": contextual_data.get("context", {}),
                    "payload": result
                })
        
        else:
            # 其他类型，记录到节点结果中
            state[f"{node}_result"] = result
        
        # 记录Graph节点执行信息
        state.add_event(f"graph_node_{node}_processed_by_{agent_name}")
        
        return state
    
    def enforce_contextual_data_flow(self, state: State) -> State:
        """
        强制数据流规范：确保数据始终是ContextualData格式
        
        Args:
            state: 要验证的状态
            
        Returns:
            验证后的状态
        """
        # 检查状态是否包含contextual_data
        if "contextual_data" not in state:
            # 尝试从现有数据构建contextual_data
            contextual_data = {}
            
            # 提取context信息
            context = {}
            if "context" in state:
                context = state.get("context")
            else:
                # 从meta中提取context信息
                context = {
                    "env": state.get_meta("env", "production"),
                    "source": state.get_meta("source", "unknown"),
                    "collector": state.get_meta("collector", "graph_engine"),
                    "trace_id": state.get_meta("trace_id", "unknown")
                }
            
            # 提取payload数据
            payload = {}
            for key in state.data:
                if key not in ["contextual_data", "context", "payload"]:
                    payload[key] = state.data[key]
            
            contextual_data = {
                "context": context,
                "payload": payload
            }
            
            state.set("contextual_data", contextual_data)
            state.add_event("contextual_data_enforced_by_graph_engine")
        
        return state
    
    def get_payload_for_ai(self, state: State) -> Dict[str, Any]:
        """
        为AI准备数据（只提供payload，不提供context）
        
        Args:
            state: 当前状态
            
        Returns:
            供AI使用的payload数据
        """
        contextual_data = state.get("contextual_data")
        if not contextual_data:
            raise ValueError("State does not contain contextual_data")
        
        return contextual_data.get("payload", {})
    
    def create_output_state(self, state: State, ai_output: Any) -> State:
        """
        创建最终输出状态（将AI输出整合回ContextualData）
        
        Args:
            state: 当前状态
            ai_output: AI处理结果
            
        Returns:
            包含AI输出的最终状态
        """
        # 确保状态有contextual_data
        state = self.enforce_contextual_data_flow(state)
        
        # 获取当前contextual_data
        contextual_data = state.get("contextual_data", {})
        
        # 将AI输出添加到payload中
        if isinstance(ai_output, dict):
            contextual_data["payload"].update(ai_output)
        else:
            contextual_data["payload"]["ai_output"] = ai_output
        
        # 更新contextual_data
        state.set("contextual_data", contextual_data)
        
        # 添加输出事件
        state.add_event("ai_output_integrated_into_contextual_data")
        
        return state
    
    def validate_no_env_checks(self, agent_code: str) -> bool:
        """
        验证智能体代码中没有环境检查逻辑
        
        Args:
            agent_code: 智能体代码字符串
            
        Returns:
            是否通过验证
        """
        forbidden_patterns = [
            r'if.*env.*==.*["\']sandbox["\']',
            r'if.*env.*==.*["\']production["\']',
            r'env.*=.*["\']sandbox["\']',
            r'env.*=.*["\']production["\']',
            r'is_sandbox',
            r'is_production',
            r'context\.env',
            r'context\["env"\]',
            r'state\.get.*env',
            r'state\["env"\]'
        ]
        
        import re
        for pattern in forbidden_patterns:
            if re.search(pattern, agent_code, re.IGNORECASE):
                return False
        
        return True


# 全局ContextualGraphEngine实例
contextual_graph_engine = ContextualGraphEngine()
