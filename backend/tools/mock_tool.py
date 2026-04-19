"""
Mock Tool - 用于测试的模拟工具
"""


class MockTool:
    """
    模拟工具，用于测试 ToolRegistry 的基本功能
    """
    
    def run(self, input_data):
        """
        执行模拟工具
        
        Args:
            input_data: 输入数据
            
        Returns:
            包含状态和输入数据的响应
        """
        return {
            "status": "ok",
            "input": input_data,
            "message": "Mock tool executed successfully"
        }