"""
Mock Agent 用于测试 GraphEngine
"""

from typing import Any
from backend.agents.base import Agent, AgentInput, AgentOutput


class MockAgent(Agent):
    """Mock Agent 用于测试"""
    
    def __init__(self, name: str = "mock_agent", result: Any = None):
        self.name = name
        self.result = result if result is not None else {"status": "success", "agent": name}
    
    async def execute(self, input_data: AgentInput) -> AgentOutput:
        """模拟执行"""
        # 从输入中获取数据
        input_data_dict = input_data.data
        
        # 模拟处理：将输入数据与预设结果合并
        if isinstance(self.result, dict) and isinstance(input_data_dict, dict):
            result = {**input_data_dict, **self.result}
        else:
            result = self.result
        
        # 添加一些元数据
        metadata = {
            "agent_name": self.name,
            "execution_time": 0.1,
            "input_keys": list(input_data_dict.keys()) if isinstance(input_data_dict, dict) else []
        }
        
        return AgentOutput(result=result, metadata=metadata)


class SimpleAddAgent(Agent):
    """简单的加法 Agent，用于测试状态传递"""
    
    def __init__(self, add_value: int = 1):
        self.add_value = add_value
    
    async def execute(self, input_data: AgentInput) -> AgentOutput:
        """执行加法操作"""
        input_data_dict = input_data.data
        
        # 尝试从状态中获取 counter 值
        counter = input_data_dict.get("counter", 0)
        
        # 执行加法
        new_counter = counter + self.add_value
        
        # 更新结果
        result = {
            "counter": new_counter,
            "previous_counter": counter,
            "added": self.add_value
        }
        
        metadata = {
            "agent_name": "SimpleAddAgent",
            "operation": f"add_{self.add_value}"
        }
        
        return AgentOutput(result=result, metadata=metadata)


class EchoAgent(Agent):
    """回显 Agent，返回输入数据"""
    
    async def execute(self, input_data: AgentInput) -> AgentOutput:
        """返回输入数据"""
        return AgentOutput(
            result=input_data.data,
            metadata={"agent_name": "EchoAgent", "echoed": True}
        )