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

from backend.common.core import Agent, AgentInput, AgentOutput
from backend.common.core import BaseAgent
from backend.common.contracts import AgentRegistry
from backend.foundation.cognition.state_machine.agent_adapter import adapt_agent, adapt_agent_async
from backend.common.core.state import State


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
            "expected_path": execution_path
        }
            
