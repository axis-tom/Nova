from abc import ABC, abstractmethod
from typing import Dict, Any, Optional


class Tool(ABC):
    """
    Tool统一调用入口基类
    所有Tool必须继承该接口
    """
    
    name: str = "base_tool"
    description: str = "基础工具"
    
    @abstractmethod
    async def execute(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        执行Tool逻辑
        
        Args:
            input_data: 输入数据字典
            
        Returns:
            执行结果字典
            
        Raises:
            NotImplementedError: 子类必须实现此方法
        """
        raise NotImplementedError
    
    def get_schema(self) -> Dict[str, Any]:
        """
        获取Tool的输入输出schema
        
        Returns:
            Tool的schema定义
        """
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": self._get_input_schema(),
            "output_schema": self._get_output_schema()
        }
    
    def _get_input_schema(self) -> Dict[str, Any]:
        """
        获取输入schema（子类可重写）
        
        Returns:
            输入schema定义
        """
        return {
            "type": "object",
            "properties": {},
            "required": []
        }
    
    def _get_output_schema(self) -> Dict[str, Any]:
        """
        获取输出schema（子类可重写）
        
        Returns:
            输出schema定义
        """
        return {
            "type": "object",
            "properties": {}
        }


class ToolRegistry:
    """
    Tool注册表（简单实现，不引入复杂registry逻辑）
    """
    
    def __init__(self):
        self._tools: Dict[str, Tool] = {}
    
    def register(self, tool: Tool) -> None:
        """
        注册Tool
        
        Args:
            tool: 要注册的Tool实例
        """
        self._tools[tool.name] = tool
        print(f"✅ 注册Tool: {tool.name} - {tool.description}")
    
    def get_tool(self, name: str) -> Optional[Tool]:
        """
        获取Tool
        
        Args:
            name: Tool名称
            
        Returns:
            Tool实例，如果不存在则返回None
        """
        return self._tools.get(name)
    
    def list_tools(self) -> Dict[str, str]:
        """
        列出所有已注册的Tool
        
        Returns:
            工具名称到描述的映射
        """
        return {name: tool.description for name, tool in self._tools.items()}
    
    async def execute_tool(self, name: str, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        执行指定Tool
        
        Args:
            name: Tool名称
            input_data: 输入数据
            
        Returns:
            执行结果
            
        Raises:
            ValueError: 如果Tool不存在
        """
        tool = self.get_tool(name)
        if not tool:
            raise ValueError(f"Tool '{name}' 未注册")
        
        return await tool.execute(input_data)


# 全局Tool注册表实例
tool_registry = ToolRegistry()
