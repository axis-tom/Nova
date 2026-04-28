"""
Tool Registry - 外部能力调用统一入口（最小可用版）
只做结构，不接真实业务
"""


class ToolRegistry:
    """
    工具注册表 - 类方法实现
    提供简单的工具注册和调用功能
    """
    _tools = {}

    @classmethod
    def register(cls, name: str, tool):
        """
        注册工具
        
        Args:
            name: 工具名称
            tool: 工具实例，必须实现 run 方法
        """
        cls._tools[name] = tool
        print(f"✅ Tool '{name}' registered successfully")

    @classmethod
    def call(cls, name: str, input_data):
        """
        调用工具
        
        Args:
            name: 工具名称
            input_data: 输入数据
            
        Returns:
            工具执行结果
            
        Raises:
            KeyError: 如果工具未注册
        """
        if name not in cls._tools:
            raise KeyError(f"Tool '{name}' is not registered")
        
        tool = cls._tools[name]
        return tool.run(input_data)

    @classmethod
    def list_tools(cls):
        """
        列出所有已注册的工具
        
        Returns:
            已注册工具名称列表
        """
        return list(cls._tools.keys())

    @classmethod
    def clear(cls):
        """
        清空所有注册的工具（主要用于测试）
        """
        cls._tools.clear()
        print("✅ All tools cleared")
