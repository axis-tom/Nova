"""
Deterministic Graph Engine - F5稳定化版本

确保Graph执行是"确定性的":
1. 同样input → 同样path
2. 不允许runtime变更节点顺序
3. 不允许Agent修改Graph flow

定义三类节点:
1. DataNode - 数据处理节点
2. AgentNode - 智能体执行节点  
3. OutputNode - 输出节点
"""

from typing import Dict, Any, Union, List, Optional
from enum import Enum
import json
import hashlib
import time
from dataclasses import dataclass, asdict

from backend.agents.base import Agent, AgentInput, AgentOutput
from backend.agents.standard_base import BaseAgent
from backend.agents.registry import AgentRegistry
from backend.workflow.agent_adapter import adapt_agent, adapt_agent_async
from backend.core.state import State


class NodeType(Enum):
    """节点类型枚举"""
    DATA_NODE = "data_node"
    AGENT_NODE = "agent_node"
    OUTPUT_NODE = "output_node"


@dataclass
class NodeDefinition:
    """节点定义"""
    node_id: str
    node_type: NodeType
    config: Dict[str, Any]
    next_node: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "node_id": self.node_id,
            "node_type": self.node_type.value,
            "config": self.config,
            "next_node": self.next_node
        }


@dataclass
class GraphDefinition:
    """图定义"""
    graph_id: str
    version: str = "1.0"
    description: str = ""
    start_node: Optional[str] = None
    nodes: Dict[str, NodeDefinition] = None
    
    def __post_init__(self):
        if self.nodes is None:
            self.nodes = {}
    
    def add_node(self, node: NodeDefinition):
        """添加节点"""
        self.nodes[node.node_id] = node
        
        # 如果这是第一个节点，设置为起始节点
        if len(self.nodes) == 1:
            self.start_node = node.node_id
    
    def validate(self) -> List[str]:
        """验证图定义"""
        errors = []
        
        # 检查起始节点
        if not self.start_node:
            errors.append("图必须指定起始节点")
        elif self.start_node not in self.nodes:
            errors.append(f"起始节点 '{self.start_node}' 不存在")
        
        # 检查节点连接
        for node_id, node in self.nodes.items():
            if node.next_node and node.next_node not in self.nodes:
                errors.append(f"节点 '{node_id}' 的下一个节点 '{node.next_node}' 不存在")
        
        # 检查循环引用
        visited = set()
        current = self.start_node
        
        while current and current not in visited:
            visited.add(current)
            if current in self.nodes:
                current = self.nodes[current].next_node
            else:
                errors.append(f"节点 '{current}' 不存在")
                break
        
        if current and current in visited:
            errors.append("图中存在循环引用")
        
        return errors
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "graph_id": self.graph_id,
            "version": self.version,
            "description": self.description,
            "start_node": self.start_node,
            "nodes": {node_id: node.to_dict() for node_id, node in self.nodes.items()}
        }
    
    def get_execution_path(self) -> List[str]:
        """获取执行路径"""
        path = []
        current = self.start_node
        
        while current:
            path.append(current)
            if current in self.nodes:
                current = self.nodes[current].next_node
            else:
                break
        
        return path


class DeterministicGraphEngine:
    """
    确定性Graph引擎
    
    特性:
    1. 同样input → 同样path
    2. 不允许runtime变更节点顺序
    3. 不允许Agent修改Graph flow
    4. 执行路径完全由Graph定义决定
    """
    
    def __init__(self, db=None):
        """
        初始化确定性Graph引擎
        
        Args:
            db: 数据库会话（可选，用于智能体初始化）
        """
        self.db = db
        self.execution_history = []
    
    def run(self, graph_def: Union[Dict[str, Any], GraphDefinition], 
            state: Union[Dict[str, Any], State]) -> Dict[str, Any]:
        """
        执行确定性图（同步版本）
        
        Args:
            graph_def: 图定义，可以是字典或GraphDefinition对象
            state: 初始状态，可以是字典或State对象
            
        Returns:
            最终状态字典，包含执行追踪信息
        """
        # 转换图定义
        if isinstance(graph_def, dict):
            graph = self._parse_graph_definition(graph_def)
        else:
            graph = graph_def
        
        # 验证图定义
        errors = graph.validate()
        if errors:
            raise ValueError(f"图定义验证失败: {errors}")
        
        # 确保状态是State对象
        if not isinstance(state, State):
            state = State(state)
        
        # 记录执行开始
        execution_id = self._generate_execution_id(graph.graph_id, state)
        execution_path = graph.get_execution_path()
        
        state["execution_metadata"] = {
            "execution_id": execution_id,
            "graph_id": graph.graph_id,
            "graph_version": graph.version,
            "start_time": time.time(),
            "expected_path": execution_path,
            "actual_path": []
        }
        
        state.log(f"开始执行确定性图 '{graph.graph_id}'，执行ID: {execution_id}")
        state.log(f"预期执行路径: {execution_path}")
        
        # 确定性执行：严格按照图定义路径执行
        current_node_id = graph.start_node
        step_count = 0
        
        while current_node_id:
            step_count += 1
            node = graph.nodes[current_node_id]
            
            # 记录节点开始执行
            node_start_time = time.time()
            state["execution_metadata"]["actual_path"].append(current_node_id)
            
            state.log(f"步骤 {step_count}: 执行节点 '{current_node_id}' ({node.node_type.value})")
            
            try:
                # 根据节点类型执行
                if node.node_type == NodeType.DATA_NODE:
                    result_state = self._execute_data_node(node, state)
                elif node.node_type == NodeType.AGENT_NODE:
                    result_state = self._execute_agent_node(node, state)
                elif node.node_type == NodeType.OUTPUT_NODE:
                    result_state = self._execute_output_node(node, state)
                else:
                    raise ValueError(f"未知节点类型: {node.node_type}")
                
                # 更新状态
                state = result_state
                
                # 记录节点执行成功
                node_execution_time = time.time() - node_start_time
                state[f"{current_node_id}_executed"] = True
                state[f"{current_node_id}_execution_time"] = node_execution_time
                state[f"{current_node_id}_status"] = "success"
                
                state.log(f"节点 '{current_node_id}' 执行成功，耗时: {node_execution_time:.2f}秒")
                
            except Exception as e:
                # 记录节点执行失败（但不中断执行）
                node_execution_time = time.time() - node_start_time
                state[f"{current_node_id}_executed"] = False
                state[f"{current_node_id}_execution_time"] = node_execution_time
                state[f"{current_node_id}_status"] = "error"
                state[f"{current_node_id}_error"] = str(e)
                
                state.log(f"节点 '{current_node_id}' 执行失败: {str(e)}，耗时: {node_execution_time:.2f}秒")
            
            # 确定性流转：严格按照图定义的下一个节点
            current_node_id = node.next_node
        
        # 记录执行完成
        total_time = time.time() - state["execution_metadata"]["start_time"]
        state["execution_metadata"]["end_time"] = time.time()
        state["execution_metadata"]["total_execution_time"] = total_time
        state["execution_metadata"]["steps_executed"] = step_count
        state["execution_metadata"]["execution_completed"] = True
        
        # 验证执行路径与预期一致
        expected_path = state["execution_metadata"]["expected_path"]
        actual_path = state["execution_metadata"]["actual_path"]
        
        if expected_path == actual_path:
            state["execution_metadata"]["path_consistency"] = True
            state.log(f"执行完成，路径一致性验证通过，总耗时: {total_time:.2f}秒")
        else:
            state["execution_metadata"]["path_consistency"] = False
            state["execution_metadata"]["path_discrepancy"] = {
                "expected": expected_path,
                "actual": actual_path
            }
            state.log(f"执行完成，路径一致性验证失败，总耗时: {total_time:.2f}秒")
        
        # 保存执行历史
        self._save_execution_history(state)
        
        return state.to_plain_dict()
    
    async def run_async(self, graph_def: Union[Dict[str, Any], GraphDefinition],
                       state: Union[Dict[str, Any], State]) -> Dict[str, Any]:
        """
        异步执行确定性图
        
        Args:
            graph_def: 图定义，可以是字典或GraphDefinition对象
            state: 初始状态，可以是字典或State对象
            
        Returns:
            最终状态字典
        """
        # 转换图定义
        if isinstance(graph_def, dict):
            graph = self._parse_graph_definition(graph_def)
        else:
            graph = graph_def
        
        # 验证图定义
        errors = graph.validate()
        if errors:
            raise ValueError(f"图定义验证失败: {errors}")
        
        # 确保状态是State对象
        if not isinstance(state, State):
            state = State(state)
        
        # 记录执行开始
        execution_id = self._generate_execution_id(graph.graph_id, state)
        execution_path = graph.get_execution_path()
        
        state["execution_metadata"] = {
            "execution_id": execution_id,
            "graph_id": graph.graph_id,
            "graph_version": graph.version,
            "start_time": time.time(),
            "expected_path": execution_path,
            "actual_path": []
        }
        
        state.log(f"开始异步执行确定性图 '{graph.graph_id}'，执行ID: {execution_id}")
        
        # 确定性执行：严格按照图定义路径执行
        current_node_id = graph.start_node
        step_count = 0
        
        while current_node_id:
            step_count += 1
            node = graph.nodes[current_node_id]
            
            # 记录节点开始执行
            node_start_time = time.time()
            state["execution_metadata"]["actual_path"].append(current_node_id)
            
            state.log(f"步骤 {step_count}: 异步执行节点 '{current_node_id}' ({node.node_type.value})")
            
            try:
                # 根据节点类型执行
                if node.node_type == NodeType.DATA_NODE:
                    result_state = await self._execute_data_node_async(node, state)
                elif node.node_type == NodeType.AGENT_NODE:
                    result_state = await self._execute_agent_node_async(node, state)
                elif node.node_type == NodeType.OUTPUT_NODE:
                    result_state = await self._execute_output_node_async(node, state)
                else:
                    raise ValueError(f"未知节点类型: {node.node_type}")
                
                # 更新状态
                state = result_state
                
                # 记录节点执行成功
                node_execution_time = time.time() - node_start_time
                state[f"{current_node_id}_executed"] = True
                state[f"{current_node_id}_execution_time"] = node_execution_time
                state[f"{current_node_id}_status"] = "success"
                
                state.log(f"节点 '{current_node_id}' 异步执行成功，耗时: {node_execution_time:.2f}秒")
                
            except Exception as e:
                # 记录节点执行失败（但不中断执行）
                node_execution_time = time.time() - node_start_time
                state[f"{current_node_id}_executed"] = False
                state[f"{current_node_id}_execution_time"] = node_execution_time
                state[f"{current_node_id}_status"] = "error"
                state[f"{current_node_id}_error"] = str(e)
                
                state.log(f"节点 '{current_node_id}' 异步执行失败: {str(e)}，耗时: {node_execution_time:.2f}秒")
            
            # 确定性流转：严格按照图定义的下一个节点
            current_node_id = node.next_node
        
        # 记录执行完成
        total_time = time.time() - state["execution_metadata"]["start_time"]
        state["execution_metadata"]["end_time"] = time.time()
        state["execution_metadata"]["total_execution_time"] = total_time
        state["execution_metadata"]["steps_executed"] = step_count
        state["execution_metadata"]["execution_completed"] = True
        
        # 验证执行路径与预期一致
        expected_path = state["execution_metadata"]["expected_path"]
        actual_path = state["execution_metadata"]["actual_path"]
        
        if expected_path == actual_path:
            state["execution_metadata"]["path_consistency"] = True
            state.log(f"异步执行完成，路径一致性验证通过，总耗时: {total_time:.2f}秒")
        else:
            state["execution_metadata"]["path_consistency"] = False
            state["execution_metadata"]["path_discrepancy"] = {
                "expected": expected_path,
                "actual": actual_path
            }
            state.log(f"异步执行完成，路径一致性验证失败，总耗时: {total_time:.2f}秒")
        
        # 保存执行历史
        self._save_execution_history(state)
        
        return state.to_plain_dict()
    
    def _execute_data_node(self, node: NodeDefinition, state: State) -> State:
        """执行数据节点"""
        config = node.config
        
        # 数据转换操作
        if "transform" in config:
            transform_config = config["transform"]
            for field, transform in transform_config.items():
                if field in state:
                    if transform == "to_string":
                        state[field] = str(state[field])
                    elif transform == "to_int":
                        state[field] = int(state[field])
                    elif transform == "to_float":
                        state[field] = float(state[field])
                    elif transform == "to_json":
                        state[field] = json.dumps(state[field])
        
        # 数据过滤操作
        if "filter" in config:
            filter_config = config["filter"]
            for field, condition in filter_config.items():
                if field in state:
                    # 简单的过滤逻辑
                    if condition.get("type") == "range":
                        min_val = condition.get("min")
                        max_val = condition.get("max")
                        if min_val is not None and state[field] < min_val:
                            state[field] = min_val
                        if max_val is not None and state[field] > max_val:
                            state[field] = max_val
        
        # 数据验证操作
        if "validate" in config:
            validate_config = config["validate"]
            for field, rules in validate_config.items():
                if field in state:
                    for rule in rules:
                        if rule == "required" and not state[field]:
                            raise ValueError(f"字段 '{field}' 是必填的")
                        elif rule == "numeric" and not isinstance(state[field], (int, float)):
                            raise ValueError(f"字段 '{field}' 必须是数字")
        
        return state
    
    async def _execute_data_node_async(self, node: NodeDefinition, state: State) -> State:
        """异步执行数据节点"""
        # 数据节点通常是同步操作，直接调用同步版本
        return self._execute_data_node(node, state)
    
    def _execute_agent_node(self, node: NodeDefinition, state: State) -> State:
        """执行智能体节点"""
        config = node.config
        
        # 获取智能体名称
        agent_name = config.get("agent")
        if not agent_name:
            raise ValueError(f"智能体节点 '{node.node_id}' 必须指定 'agent' 配置")
        
        # 从注册表获取智能体实例
        try:
            if self.db is not None:
                agent = AgentRegistry.get(agent_name, self.db)
            else:
                agent = AgentRegistry.get(agent_name)
        except Exception as e:
            raise ValueError(f"无法从注册表获取智能体 '{agent_name}': {e}")
        
        # 适配Agent到统一接口
        adapted_agent = self._adapt_agent(agent)
        
        # 准备智能体输入
        agent_input = self._prepare_agent_input(config, state)
        
        # 执行智能体
        try:
            result = adapted_agent.run(agent_input)
            
            # 处理返回结果
            if isinstance(result, dict) and "state" in result:
                # 新的规范格式
                state_dict = result["state"]
                status = result.get("status", "ok")
                events = result.get("events", [])
                
                # 更新状态
                for key, value in state_dict.items():
                    state[key] = value
                
                # 记录执行状态
                state[f"{node.node_id}_agent_status"] = status
                if events:
                    state[f"{node.node_id}_agent_events"] = events
                
            else:
                # 兼容旧格式：直接返回状态字典
                if isinstance(result, dict):
                    for key, value in result.items():
                        state[key] = value
                else:
                    state[f"{node.node_id}_result"] = result
            
            return state
            
        except Exception as e:
            raise RuntimeError(f"智能体 '{agent_name}' 执行失败: {e}")
    
    async def _execute_agent_node_async(self, node: NodeDefinition, state: State) -> State:
        """异步执行智能体节点"""
        config = node.config
        
        # 获取智能体名称
        agent_name = config.get("agent")
        if not agent_name:
            raise ValueError(f"智能体节点 '{node.node_id}' 必须指定 'agent' 配置")
        
        # 从注册表获取智能体实例
        try:
            if self.db is not None:
                agent = AgentRegistry.get(agent_name, self.db)
            else:
                agent = AgentRegistry.get(agent_name)
        except Exception as e:
            raise ValueError(f"无法从注册表获取智能体 '{agent_name}': {e}")
        
        # 适配Agent到统一接口
        adapted_agent = self._adapt_agent_async(agent)
        
        # 准备智能体输入
        agent_input = self._prepare_agent_input(config, state)
        
        # 执行智能体
        try:
            if hasattr(adapted_agent, 'run_async'):
                result = await adapted_agent.run_async(agent_input)
            else:
                # 如果没有异步版本，在线程中运行同步版本
                import asyncio
                result = await asyncio.to_thread(adapted_agent.run, agent_input)
            
            # 处理返回结果
            if isinstance(result, dict) and "state" in result:
                # 新的规范格式
                state_dict = result["state"]
                status = result.get("status", "ok")
                events = result.get("events", [])
                
                # 更新状态
                for key, value in state_dict.items():
                    state[key] = value
                
                # 记录执行状态
                state[f"{node.node_id}_agent_status"] = status
                if events:
                    state[f"{node.node_id}_agent_events"] = events
                
            else:
                # 兼容旧格式：直接返回状态字典
                if isinstance(result, dict):
                    for key, value in result.items():
                        state[key] = value
                else:
                    state[f"{node.node_id}_result"] = result
            
            return state
            
        except Exception as e:
            raise RuntimeError(f"智能体 '{agent_name}' 异步执行失败: {e}")
    
    def _execute_output_node(self, node: NodeDefinition, state: State) -> State:
        """执行输出节点"""
        config = node.config
        
        # 输出格式化
        if "format" in config:
            format_config = config["format"]
            output_format = format_config.get("type", "json")
            
            if output_format == "json":
                state["output"] = json.dumps(state.to_plain_dict(), ensure_ascii=False, indent=2)
            elif output_format == "text":
                # 简单的文本输出
                output_lines = []
                for key, value in state.items():
                    if not key.startswith("_"):  # 跳过内部字段
                        output_lines.append(f"{key}: {value}")
                state["output"] = "\n".join(output_lines)
        
        # 输出验证
        if "validate_output" in config:
            validate_rules = config["validate_output"]
            for field, rule in validate_rules.items():
                if field not in state:
                    raise ValueError(f"输出字段 '{field}' 不存在")
                
                if rule == "required" and not state[field]:
                    raise ValueError(f"输出字段 '{field}' 是必填的")
        
        # 标记输出完成
        state["output_generated"] = True
        state["output_node"] = node.node_id
        
        return state
    
    async def _execute_output_node_async(self, node: NodeDefinition, state: State) -> State:
        """异步执行输出节点"""
        # 输出节点通常是同步操作，直接调用同步版本
        return self._execute_output_node(node, state)
    
    def _parse_graph_definition(self, graph_dict: Dict[str, Any]) -> GraphDefinition:
        """解析图定义字典"""
        graph_id = graph_dict.get("graph_id", f"graph_{int(time.time())}")
        version = graph_dict.get("version", "1.0")
        description = graph_dict.get("description", "")
        start_node = graph_dict.get("start")
        
        graph = GraphDefinition(
            graph_id=graph_id,
            version=version,
            description=description,
            start_node=start_node
        )
        
        # 解析节点
        nodes_dict = graph_dict.get("nodes", {})
        for node_id, node_config in nodes_dict.items():
            node_type_str = node_config.get("node_type", "agent_node")
            
            try:
                node_type = NodeType(node_type_str)
            except ValueError:
                raise ValueError(f"未知的节点类型: {node_type_str}")
            
            node = NodeDefinition(
                node_id=node_id,
                node_type=node_type,
                config=node_config.get("config", {}),
                next_node=node_config.get("next")
            )
            
            graph.add_node(node)
        
        return graph
    
    def _generate_execution_id(self, graph_id: str, state: State) -> str:
        """生成执行ID（确定性）"""
        # 使用图ID和状态哈希生成确定性执行ID
        state_str = json.dumps(state.to_plain_dict(), sort_keys=True)
        state_hash = hashlib.md5(state_str.encode()).hexdigest()[:8]
        
        timestamp = int(time.time())
        return f"{graph_id}_{state_hash}_{timestamp}"
    
    def _prepare_agent_input(self, config: Dict[str, Any], state: State) -> State:
        """准备智能体输入"""
        # 提取智能体需要的输入字段
        input_fields = config.get("input_fields", [])
        
        if input_fields:
            # 只提取指定的字段
            agent_input = {}
            for field in input_fields:
                if field in state:
                    agent_input[field] = state[field]
                elif "." in field:
                    # 支持嵌套字段访问
                    parts = field.split(".")
                    current = state
                    for part in parts:
                        if isinstance(current, dict) and part in current:
                            current = current[part]
                        else:
                            current = None
                            break
                    if current is not None:
                        agent_input[field] = current
        else:
            # 如果没有指定字段，传递整个状态
            agent_input = state.to_plain_dict()
        
        return State(agent_input)
    
    def _adapt_agent(self, agent):
        """适配Agent到统一接口（同步版本）"""
        if isinstance(agent, Agent):
            # 如果是Agent实例（有execute方法），使用适配器
            return adapt_agent(agent)
        elif isinstance(agent, BaseAgent):
            # 如果是BaseAgent实例（有run方法），直接使用
            return agent
        elif hasattr(agent, 'run'):
            # 如果有run方法，直接使用
            return agent
        else:
            raise ValueError(f"Agent '{agent.__class__.__name__}' 没有有效的接口（需要 'execute' 或 'run' 方法）")
    
    def _adapt_agent_async(self, agent):
        """适配Agent到统一接口（异步版本）"""
        if isinstance(agent, Agent):
            # 如果是Agent实例（有execute方法），使用异步适配器
            return adapt_agent_async(agent)
        elif isinstance(agent, BaseAgent):
            # 如果是BaseAgent实例，检查是否有异步版本
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
            # 如果有run_async方法，直接使用
            return agent
        elif hasattr(agent, 'run'):
            # 只有run方法，创建异步包装器
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
            raise ValueError(f"Agent '{agent.__class__.__name__}' 没有有效的接口（需要 'execute', 'run', 或 'run_async' 方法）")
    
    def _save_execution_history(self, state: State):
        """保存执行历史"""
        execution_record = {
            "execution_id": state.get("execution_metadata", {}).get("execution_id"),
            "graph_id": state.get("execution_metadata", {}).get("graph_id"),
            "timestamp": time.time(),
            "execution_time": state.get("execution_metadata", {}).get("total_execution_time", 0),
            "steps_executed": state.get("execution_metadata", {}).get("steps_executed", 0),
            "path_consistency": state.get("execution_metadata", {}).get("path_consistency", False),
            "state_summary": {
                "keys": list(state.keys()),
                "has_output": "output" in state
            }
        }
        
        self.execution_history.append(execution_record)
        
        # 限制历史记录大小
        if len(self.execution_history) > 100:
            self.execution_history = self.execution_history[-100:]
    
    def get_execution_history(self, limit: int = 10) -> List[Dict[str, Any]]:
        """获取执行历史"""
        return self.execution_history[-limit:] if self.execution_history else []
    
    def clear_execution_history(self):
        """清空执行历史"""
        self.execution_history = []
    
    def create_example_graph(self) -> GraphDefinition:
        """创建示例图定义"""
        graph = GraphDefinition(
            graph_id="example_deterministic_graph",
            version="1.0",
            description="确定性图示例"
        )
        
        # 数据节点：输入验证
        graph.add_node(NodeDefinition(
            node_id="validate_input",
            node_type=NodeType.DATA_NODE,
            config={
                "validate": {
                    "context": ["required"],
                    "data": ["required"]
                }
            },
            next_node="process_data"
        ))
        
        # 数据节点：数据处理
        graph.add_node(NodeDefinition(
            node_id="process_data",
            node_type=NodeType.DATA_NODE,
            config={
                "transform": {
                    "timestamp": "to_int"
                },
                "filter": {
                    "value": {
                        "type": "range",
                        "min": 0,
                        "max": 100
                    }
                }
            },
            next_node="analyze_with_ai"
        ))
        
        # 智能体节点：AI分析
        graph.add_node(NodeDefinition(
            node_id="analyze_with_ai",
            node_type=NodeType.AGENT_NODE,
            config={
                "agent": "ai_analyzer",
                "input_fields": ["context", "data", "timestamp"]
            },
            next_node="generate_output"
        ))
        
        # 输出节点：生成输出
        graph.add_node(NodeDefinition(
            node_id="generate_output",
            node_type=NodeType.OUTPUT_NODE,
            config={
                "format": {
                    "type": "json"
                },
                "validate_output": {
                    "output": "required"
                }
            },
            next_node=None  # 结束节点
        ))
        
        return graph


# 全局确定性Graph引擎实例
deterministic_graph_engine = DeterministicGraphEngine()
        
       