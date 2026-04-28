"""
电商Agent基类
所有电商Agent必须继承此类，确保统一的接口和行为
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional
from backend.common.core.state import State
from backend.common.core import Agent


class BaseEcommerceAgent(Agent, ABC):
    """
    电商Agent基类
    扩展标准Agent接口，增加电商特定功能
    """
    
    def __init__(self, name: str, description: str):
        """
        初始化电商Agent
        
        Args:
            name: Agent名称
            description: Agent描述
        """
        self.name = name
        self.description = description
    
    @abstractmethod
    def run(self, state: State) -> State:
        """
        执行Agent逻辑（必须实现）
        
        Args:
            state: 输入状态
            
        Returns:
            输出状态
        """
        raise NotImplementedError
    
    def validate_input(self, state: State) -> bool:
        """
        验证输入状态是否满足Agent要求
        
        Args:
            state: 输入状态
            
        Returns:
            验证是否通过
        """
        # 默认实现：检查必要字段
        required_fields = self.get_required_fields()
        for field in required_fields:
            if field not in state:
                return False
        return True
    
    def get_required_fields(self) -> list:
        """
        获取Agent必需的输入字段
        
        Returns:
            必需字段列表
        """
        return []
    
    def get_output_fields(self) -> list:
        """
        获取Agent输出的字段
        
        Returns:
            输出字段列表
        """
        return []
    
    def add_execution_record(self, state: State, success: bool, metadata: Dict[str, Any] = None) -> State:
        """
        添加执行记录到状态
        
        Args:
            state: 状态对象
            success: 是否成功
            metadata: 附加元数据
            
        Returns:
            更新后的状态
        """
        execution_key = f"{self.name}_execution"
        if execution_key not in state:
            state[execution_key] = []
        
        record = {
            "agent": self.name,
            "success": success,
            "timestamp": self._get_timestamp(),
            "metadata": metadata or {}
        }
        
        state[execution_key].append(record)
        return state
    
    def _get_timestamp(self) -> str:
        """
        获取当前时间戳
        
        Returns:
            时间戳字符串
        """
        from datetime import datetime
        return datetime.now().isoformat()
    
    def log_event(self, state: State, event_type: str, message: str, details: Dict[str, Any] = None) -> State:
        """
        记录事件到状态
        
        Args:
            state: 状态对象
            event_type: 事件类型
            message: 事件消息
            details: 事件详情
            
        Returns:
            更新后的状态
        """
        event = {
            "type": event_type,
            "agent": self.name,
            "message": message,
            "timestamp": self._get_timestamp(),
            "details": details or {}
        }
        
        # 添加到事件列表
        if "events" not in state:
            state["events"] = []
        state["events"].append(event)
        
        # 同时添加到State的事件系统
        state.add_event(f"[{event_type}] {self.name}: {message}")
        
        return state
    
    def get_context(self, state: State) -> Dict[str, Any]:
        """
        从状态中提取Agent上下文
        
        Args:
            state: 状态对象
            
        Returns:
            上下文字典
        """
        context = {
            "agent_name": self.name,
            "timestamp": self._get_timestamp(),
            "state_keys": list(state.keys()),
            "meta": dict(state.meta)
        }
        
        # 添加电商特定上下文
        if "ecommerce_context" in state:
            context["ecommerce"] = state["ecommerce_context"]
        
        return context
    
    def format_result(self, result: Any, metadata: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        格式化Agent执行结果
        
        Args:
            result: 原始结果
            metadata: 附加元数据
            
        Returns:
            格式化后的结果
        """
        formatted = {
            "agent": self.name,
            "result": result,
            "timestamp": self._get_timestamp(),
            "metadata": metadata or {}
        }
        
        return formatted


class EcommerceAgentRegistry:
    """
    电商Agent注册表
    管理电商特定Agent的注册和获取
    """
    
    _agents: Dict[str, BaseEcommerceAgent] = {}
    
    @classmethod
    def register(cls, agent: BaseEcommerceAgent) -> None:
        """
        注册电商Agent
        
        Args:
            agent: Agent实例
            
        Raises:
            ValueError: 如果名称已存在
        """
        if agent.name in cls._agents:
            raise ValueError(f"Ecommerce Agent '{agent.name}' is already registered")
        
        cls._agents[agent.name] = agent
        print(f"✅ 注册电商Agent: {agent.name} - {agent.description}")
    
    @classmethod
    def get(cls, name: str) -> BaseEcommerceAgent:
        """
        获取电商Agent
        
        Args:
            name: Agent名称
            
        Returns:
            Agent实例
            
        Raises:
            KeyError: 如果名称不存在
        """
        if name not in cls._agents:
            raise KeyError(f"Ecommerce Agent '{name}' is not registered")
        
        return cls._agents[name]
    
    @classmethod
    def list_agents(cls) -> Dict[str, str]:
        """
        列出所有已注册的电商Agent
        
        Returns:
            字典，键为Agent名称，值为Agent描述
        """
        return {name: agent.description for name, agent in cls._agents.items()}
    
    @classmethod
    def clear(cls) -> None:
        """
        清空注册表（主要用于测试）
        """
        cls._agents.clear()