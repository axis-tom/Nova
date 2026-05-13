"""
Agent Registry - 智能体注册表（支持轻量接入）

这是一个支持轻量接入的注册表实现，用于管理智能体的注册和获取。
遵循任务要求：不改 email_agent，不重构 briefing_agent，只是"包一层调用"。
"""

from typing import Dict, Type, Any, Callable, Union


class AgentRegistry:
    """
    智能体注册表类
    
    这是一个支持轻量接入的注册表实现，可以存储智能体类或工厂函数。
    """
    
    # 类变量，存储注册的智能体类或工厂函数
    _agents: Dict[str, Union[Type[Any], Callable[..., Any]]] = {}
    
    @classmethod
    def register(cls, name: str, agent_or_factory: Union[Type[Any], Callable[..., Any]]) -> None:
        """
        注册智能体类或工厂函数
        
        Args:
            name: 智能体名称
            agent_or_factory: 智能体类或工厂函数
            
        Raises:
            ValueError: 如果名称已存在
        """
        if name in cls._agents:
            raise ValueError(f"Agent '{name}' is already registered")
        
        cls._agents[name] = agent_or_factory
    
    @classmethod
    def get(cls, name: str, *args, **kwargs) -> Any:
        """
        获取智能体实例
        
        Args:
            name: 智能体名称
            *args, **kwargs: 传递给工厂函数或构造函数的参数
            
        Returns:
            智能体实例
            
        Raises:
            KeyError: 如果名称不存在
        """
        if name not in cls._agents:
            raise KeyError(f"Agent '{name}' is not registered")
        
        # 获取注册的类或工厂函数
        agent_or_factory = cls._agents[name]
        
        # 如果是可调用对象（工厂函数），调用它
        if callable(agent_or_factory):
            return agent_or_factory(*args, **kwargs)
        # 如果是类，实例化它
        elif isinstance(agent_or_factory, type):
            return agent_or_factory(*args, **kwargs)
        else:
            raise TypeError(f"Registered agent '{name}' is not callable or a class")
    
    @classmethod
    def list_agents(cls) -> Dict[str, str]:
        """
        列出所有已注册的智能体
        
        Returns:
            字典，键为智能体名称，值为智能体类的字符串表示
        """
        return {name: str(cls._agents[name]) for name in cls._agents}
    
    @classmethod
    def clear(cls) -> None:
        """
        清空注册表（主要用于测试）
        """
        cls._agents.clear()
    
    @classmethod
    def is_registered(cls, name: str) -> bool:
        """
        检查智能体是否已注册
        
        Args:
            name: 智能体名称
            
        Returns:
            bool: 如果已注册返回 True，否则返回 False
        """
        return name in cls._agents