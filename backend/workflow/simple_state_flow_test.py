"""
简单测试 GraphEngine 的 State 流转功能
不依赖外部库
"""

import asyncio
import sys
import os

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 模拟必要的类
class AgentInput:
    def __init__(self, data, user_id=0, trace_id=None, config=None):
        self.data = data
        self.user_id = user_id
        self.trace_id = trace_id
        self.config = config or {}

class AgentOutput:
    def __init__(self, result, metadata=None, error=None):
        self.result = result
        self.metadata = metadata or {}
        self.error = error

class Agent:
    name = "base_agent"
    
    async def execute(self, input_data):
        raise NotImplementedError

class BaseAgent:
    def run(self, state):
        raise NotImplementedError

class State:
    def __init__(self, *args, **kwargs):
        self._data = {}
        if args:
            if len(args) == 1 and isinstance(args[0], dict):
                self._data = args[0].copy()
        if kwargs:
            self._data.update(kwargs)
    
    def get(self, key, default=None):
        return self._data.get(key, default)
    
    def __getitem__(self, key):
        return self._data[key]
    
    def __setitem__(self, key, value):
        self._data[key] = value
    
    def to_plain_dict(self):
        return self._data.copy()
    
    def log(self, msg):
        if "logs" not in self._data:
            self._data["logs"] = []
        self._data["logs"].append(msg)
        return self

# 导入我们修改后的 GraphEngine
from backend.workflow.graph_engine import GraphEngine


async def test_basic_state_flow():
    """测试基本的 State 流转"""
    print("=== 测试基本的 State 流转 ===")
    
    # 创建简单的测试 Agent
    class SimpleAgent:
        def run(self, state):
            if isinstance(state, State):
                counter = state.get("counter", 0)
                state["counter"] = counter + 1
                state["processed"] = True
                return state.to_plain_dict()
            else:
                counter = state.get("counter", 0)
                state["counter"] = counter + 1
                state["processed"] = True
                return state
    
    # 手动模拟 Registry
    class MockRegistry:
        _agents = {}
        
        @classmethod
        def clear(cls):
            cls._agents.clear()
        
        @classmethod
        def register(cls, name, agent_factory):
            cls._agents[name] = agent_factory
        
        @classmethod
        def get(cls, name, *args, **kwargs):
            if name not in cls._agents:
                raise KeyError(f"Agent '{name}' not found")
            return cls._agents[name](*args, **kwargs)
    
    # 替换原来的 Registry
    import backend.agents.registry
    backend.agents.registry.AgentRegistry = MockRegistry
    
    # 注册测试 Agent
    MockRegistry.clear()
    MockRegistry.register("simple_agent", SimpleAgent)
    
    # 创建 GraphEngine
    engine = GraphEngine()
    
    # 定义图
    graph = {
        "start": "node1",
        "nodes": {
            "node1": {
                "agent": "simple_agent",
                "next": None
            }
        }
    }
    
    # 初始状态
    initial_state = {"counter": 5, "test": "data"}
    
    # 执行图
    final_state = await engine.run_async(graph, initial_state)
    
    print(f"初始状态: {initial_state}")
    print(f"最终状态: {final_state}")
    
    assert final_state["counter"] == 6
    assert final_state["processed"] == True
    assert final_state["node1_executed"] == True
    
    print("✓ 基本 State 流转测试通过")
    return True


async def test_multiple_agents():
    """测试多个 Agent 的 State 流转"""
    print("\n=== 测试多个 Agent 的 State 流转 ===")
    
    class AddAgent:
        def __init__(self, value):
            self.value = value
        
        def run(self, state):
            counter = state.get("counter", 0)
            state["counter"] = counter + self.value
            state[f"added_{self.value}"] = True
            return state
    
    class MultiplyAgent:
        def __init__(self, factor):
            self.factor = factor
        
        def run(self, state):
            counter = state.get("counter", 0)
            state["counter"] = counter * self.factor
            state[f"multiplied_{self.factor}"] = True
            return state
    
    # 手动模拟 Registry
    class MockRegistry:
        _agents = {}
        
        @classmethod
        def clear(cls):
            cls._agents.clear()
        
        @classmethod
        def register(cls, name, agent_factory):
            cls._agents[name] = agent_factory
        
        @classmethod
        def get(cls, name, *args, **kwargs):
            if name not in cls._agents:
                raise KeyError(f"Agent '{name}' not found")
            return cls._agents[name](*args, **kwargs)
    
    # 替换原来的 Registry
    import backend.agents.registry
    backend.agents.registry.AgentRegistry = MockRegistry
    
    # 注册测试 Agent
    MockRegistry.clear()
    MockRegistry.register("add_5", lambda: AddAgent(5))
    MockRegistry.register("multiply_2", lambda: MultiplyAgent(2))
    MockRegistry.register("add_10", lambda: AddAgent(10))
    
    # 创建 GraphEngine
    engine = GraphEngine()
    
    # 定义复杂图
    graph = {
        "start": "add5",
        "nodes": {
            "add5": {
                "agent": "add_5",
                "next": "multiply2"
            },
            "multiply2": {
                "agent": "multiply_2",
                "next": "add10"
            },
            "add10": {
                "agent": "add_10",
                "next": None
            }
        }
    }
    
    # 初始状态
    initial_state = {"counter": 1}
    
    # 执行图
    final_state = await engine.run_async(graph, initial_state)
    
    print(f"初始计数器: {initial_state['counter']}")
    print(f"最终计数器: {final_state['counter']}")
    
    # 验证计算链：((1 + 5) * 2) + 10 = 22
    expected = ((1 + 5) * 2) + 10
    assert final_state["counter"] == expected, f"Expected {expected}, got {final_state['counter']}"
    assert final_state["added_5"] == True
    assert final_state["multiplied_2"] == True
    assert final_state["added_10"] == True
    
    print(f"✓ 多个 Agent State 流转测试通过 (计算: {expected})")
    return True


async def test_state_object_usage():
    """测试 State 对象的使用"""
    print("\n=== 测试 State 对象的使用 ===")
    
    class StateAwareAgent:
        def run(self, state):
            # GraphEngine 应该已经将 state 转换为 State 对象
            assert isinstance(state, State), f"Expected State object, got {type(state)}"
            
            # 使用 State 方法
            state["processed"] = True
            state.log("Agent 执行完成")
            
            return state.to_plain_dict()
    
    # 手动模拟 Registry
    class MockRegistry:
        _agents = {}
        
        @classmethod
        def clear(cls):
            cls._agents.clear()
        
        @classmethod
        def register(cls, name, agent_factory):
            cls._agents[name] = agent_factory
        
        @classmethod
        def get(cls, name, *args, **kwargs):
            if name not in cls._agents:
                raise KeyError(f"Agent '{name}' not found")
            return cls._agents[name](*args, **kwargs)
    
    # 替换原来的 Registry
    import backend.agents.registry
    backend.agents.registry.AgentRegistry = MockRegistry
    
    # 注册测试 Agent
    MockRegistry.clear()
    MockRegistry.register("state_aware_agent", StateAwareAgent)
    
    # 创建 GraphEngine
    engine = GraphEngine()
    
    # 定义图
    graph = {
        "start": "process",
        "nodes": {
            "process": {
                "agent": "state_aware_agent",
                "next": None
            }
        }
    }
    
    # 初始状态（普通字典）
    initial_state = {"data": "test"}
    
    # 执行图
    final_state = await engine.run_async(graph, initial_state)
    
    print(f"初始状态: {initial_state}")
    print(f"最终状态: {final_state}")
    
    assert final_state["processed"] == True
    assert "logs" in final_state
    assert len(final_state["logs"]) > 0
    
    print("✓ State 对象使用测试通过")
    return True


async def main():
    """运行所有测试"""
    print("开始测试 GraphEngine State 流转功能...")
    
    success = True
    try:
        if not await test_basic_state_flow():
            success = False
        
        if not await test_multiple_agents():
            success = False
        
        if not await test_state_object_usage():
            success = False
        
        if success:
            print("\n🎉 所有测试通过！GraphEngine 已成功支持 state = agent.run(state) 统一接口。")
        else:
            print("\n❌ 部分测试失败")
        
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        success = False
    
    return 0 if success else 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)