"""
测试 GraphEngine 的 State 流转功能
验证 state = agent.run(state) 的统一接口
"""

import asyncio
import sys
import os

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.workflow.graph_engine import GraphEngine, GraphEngineV2
from backend.workflow.agent_adapter import adapt_agent
from backend.core.state import State
from backend.agents.base import Agent, AgentInput, AgentOutput


class TestAgentWithExecute(Agent):
    """测试 Agent（有 execute 方法）"""
    
    def __init__(self, name="test_agent"):
        self.name = name
    
    def run(self, state: State) -> State:
        """执行逻辑（新规范）"""
        # 记录Agent开始执行
        state.add_event(f"{self.name}_start")
        
        # 处理逻辑
        counter = state.get("counter", 0)
        state.set("counter", counter + 1)
        state.set("agent", self.name)
        state.set_meta("executed", True)
        state.set_meta("method", "execute")
        
        # 记录Agent结束执行
        state.add_event(f"{self.name}_end")
        
        return state
    
    async def execute(self, input_data: AgentInput) -> AgentOutput:
        """执行逻辑（向后兼容）"""
        # 将 AgentInput 转换为 State
        state = State(input_data.data)
        state.set_meta("user_id", input_data.user_id)
        if input_data.trace_id:
            state.set_meta("trace_id", input_data.trace_id)
        if input_data.config:
            state.set_meta("config", input_data.config)
        
        # 执行 run 方法
        result_state = self.run(state)
        
        # 将 State 转换为 AgentOutput
        # 优先使用"result"键，否则使用整个data部分
        if "result" in result_state:
            result = result_state.get("result")
        else:
            # 返回整个data部分，但排除一些内部键
            result = result_state.to_plain_dict()
            # 移除可能不需要的键
            for key in ["error", "metadata", "executed"]:
                if key in result:
                    del result[key]
        
        # 从meta中提取metadata
        metadata = {}
        for key in result_state.meta:
            if key not in ["user_id", "trace_id", "config", "step"]:
                metadata[key] = result_state.meta[key]
        
        # 提取error信息
        error = result_state.get("error")
        
        return AgentOutput(
            result=result,
            metadata=metadata,
            error=error
        )


class TestAgentWithRun:
    """测试 Agent（有 run 方法）"""
    
    def __init__(self, name="test_agent_run"):
        self.name = name
    
    def run(self, state):
        """执行逻辑"""
        if isinstance(state, State):
            counter = state.get("counter", 0)
            state["counter"] = counter + 1
            state[f"{self.name}_executed"] = True
            state[f"{self.name}_method"] = "run"
            return state.to_plain_dict()
        else:
            counter = state.get("counter", 0)
            state["counter"] = counter + 1
            state[f"{self.name}_executed"] = True
            state[f"{self.name}_method"] = "run"
            return state


async def test_agent_adapter():
    """测试 Agent 适配器"""
    print("=== 测试 Agent 适配器 ===")
    
    # 创建有 execute 方法的 Agent
    agent_with_execute = TestAgentWithExecute("execute_agent")
    
    # 适配到统一接口
    adapted_agent = adapt_agent(agent_with_execute)
    
    # 测试运行
    initial_state = State({"counter": 0, "test": "data"})
    result = adapted_agent.run(initial_state)
    
    print(f"初始状态: {initial_state.to_plain_dict()}")
    print(f"适配后执行结果: {result}")
    
    assert result["counter"] == 1
    assert result["agent"] == "execute_agent"
    assert result["execute_agent_executed"] == True
    
    print("✓ Agent 适配器测试通过")


async def test_graph_engine_with_execute_agent():
    """测试 GraphEngine 与有 execute 方法的 Agent"""
    print("\n=== 测试 GraphEngine 与 execute Agent ===")
    
    # 注册测试 Agent
    from backend.agents.registry import AgentRegistry
    AgentRegistry.clear()
    AgentRegistry.register("test_execute_agent", TestAgentWithExecute)
    
    # 创建 GraphEngine
    engine = GraphEngine()
    
    # 定义图
    graph = {
        "start": "node1",
        "nodes": {
            "node1": {
                "agent": "test_execute_agent",
                "next": None
            }
        }
    }
    
    # 初始状态
    initial_state = {"counter": 10, "user_id": 123}
    
    # 执行图
    final_state = await engine.run_async(graph, initial_state)
    
    print(f"初始状态: {initial_state}")
    print(f"最终状态: {final_state}")
    
    assert final_state["counter"] == 11
    assert final_state["agent"] == "test_execute_agent"
    assert final_state["node1_executed"] == True
    
    print("✓ GraphEngine 与 execute Agent 测试通过")


async def test_graph_engine_with_run_agent():
    """测试 GraphEngine 与有 run 方法的 Agent"""
    print("\n=== 测试 GraphEngine 与 run Agent ===")
    
    # 注册测试 Agent
    from backend.agents.registry import AgentRegistry
    AgentRegistry.clear()
    AgentRegistry.register("test_run_agent", TestAgentWithRun)
    
    # 创建 GraphEngine
    engine = GraphEngine()
    
    # 定义图
    graph = {
        "start": "node1",
        "nodes": {
            "node1": {
                "agent": "test_run_agent",
                "next": None
            }
        }
    }
    
    # 初始状态
    initial_state = {"counter": 20, "user_id": 456}
    
    # 执行图
    final_state = await engine.run_async(graph, initial_state)
    
    print(f"初始状态: {initial_state}")
    print(f"最终状态: {final_state}")
    
    assert final_state["counter"] == 21
    assert final_state["test_run_agent_executed"] == True
    assert final_state["test_run_agent_method"] == "run"
    assert final_state["node1_executed"] == True
    
    print("✓ GraphEngine 与 run Agent 测试通过")


async def test_state_flow_chain():
    """测试 State 流转链"""
    print("\n=== 测试 State 流转链 ===")
    
    # 注册多个测试 Agent
    from backend.agents.registry import AgentRegistry
    AgentRegistry.clear()
    
    # 注册有 execute 方法的 Agent
    class AddAgent(Agent):
        def __init__(self, value):
            self.value = value
            self.name = f"add_{value}"
        
        def run(self, state: State) -> State:
            """执行逻辑（新规范）"""
            # 记录Agent开始执行
            state.add_event(f"{self.name}_start")
            
            # 处理逻辑
            counter = state.get("counter", 0)
            state.set("counter", counter + self.value)
            state.set_meta("added", self.value)
            
            # 记录Agent结束执行
            state.add_event(f"{self.name}_end")
            
            return state
        
        async def execute(self, input_data: AgentInput) -> AgentOutput:
            """执行逻辑（向后兼容）"""
            # 将 AgentInput 转换为 State
            state = State(input_data.data)
            state.set_meta("user_id", input_data.user_id)
            if input_data.trace_id:
                state.set_meta("trace_id", input_data.trace_id)
            if input_data.config:
                state.set_meta("config", input_data.config)
            
            # 执行 run 方法
            result_state = self.run(state)
            
            # 将 State 转换为 AgentOutput
            # 优先使用"result"键，否则使用整个data部分
            if "result" in result_state:
                result = result_state.get("result")
            else:
                # 返回整个data部分，但排除一些内部键
                result = result_state.to_plain_dict()
                # 移除可能不需要的键
                for key in ["error", "metadata", "executed"]:
                    if key in result:
                        del result[key]
            
            # 从meta中提取metadata
            metadata = {}
            for key in result_state.meta:
                if key not in ["user_id", "trace_id", "config", "step"]:
                    metadata[key] = result_state.meta[key]
            
            # 提取error信息
            error = result_state.get("error")
            
            return AgentOutput(
                result=result,
                metadata=metadata,
                error=error
            )
    
    # 注册有 run 方法的 Agent
    class MultiplyAgent:
        def __init__(self, factor):
            self.factor = factor
            self.name = f"multiply_{factor}"
        
        def run(self, state):
            if isinstance(state, State):
                counter = state.get("counter", 0)
                state["counter"] = counter * self.factor
                state[f"{self.name}_executed"] = True
                return state.to_plain_dict()
            else:
                counter = state.get("counter", 0)
                state["counter"] = counter * self.factor
                state[f"{self.name}_executed"] = True
                return state
    
    AgentRegistry.register("add_5", lambda: AddAgent(5))
    AgentRegistry.register("multiply_2", lambda: MultiplyAgent(2))
    AgentRegistry.register("add_10", lambda: AddAgent(10))
    
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
    initial_state = {"counter": 1, "user_id": 789}
    
    # 执行图
    final_state = await engine.run_async(graph, initial_state)
    
    print(f"初始计数器: {initial_state['counter']}")
    print(f"最终计数器: {final_state['counter']}")
    
    # 验证计算链：((1 + 5) * 2) + 10 = 22
    assert final_state["counter"] == 22
    assert final_state["add5_executed"] == True
    assert final_state["multiply2_executed"] == True
    assert final_state["add10_executed"] == True
    
    print("✓ State 流转链测试通过")


async def test_state_object_features():
    """测试 State 对象特性"""
    print("\n=== 测试 State 对象特性 ===")
    
    # 注册测试 Agent
    from backend.agents.registry import AgentRegistry
    AgentRegistry.clear()
    
    class StateAwareAgent:
        def run(self, state):
            # 确保 state 是 State 对象
            if not isinstance(state, State):
                state = State(state)
            
            # 使用 State 对象的特性
            state.log("开始处理")
            state.set_meta("processed_by", "StateAwareAgent")
            state.set_nested("user.profile.name", "Test User")
            state["processed"] = True
            state.log("处理完成")
            
            return state.to_plain_dict()
    
    AgentRegistry.register("state_aware_agent", StateAwareAgent)
    
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
    
    # 初始状态
    initial_state = {"user_id": 999, "data": "test"}
    
    # 执行图
    final_state = await engine.run_async(graph, initial_state)
    
    print(f"初始状态: {initial_state}")
    print(f"最终状态 keys: {list(final_state.keys())}")
    
    # 检查 State 对象的特性
    assert final_state["processed"] == True
    assert "user.profile.name" in str(final_state)
    assert "logs" in str(final_state)  # State 对象的字符串表示包含 logs
    
    print("✓ State 对象特性测试通过")


async def test_error_handling():
    """测试错误处理"""
    print("\n=== 测试错误处理 ===")
    
    # 注册会出错的 Agent
    from backend.agents.registry import AgentRegistry
    AgentRegistry.clear()
    
    class ErrorAgent:
        def run(self, state):
            raise ValueError("模拟错误")
    
    class NormalAgent:
        def run(self, state):
            state["normal_executed"] = True
            return state
    
    AgentRegistry.register("error_agent", ErrorAgent)
    AgentRegistry.register("normal_agent", NormalAgent)
    
    # 创建 GraphEngine
    engine = GraphEngine()
    
    # 定义包含错误节点的图
    graph = {
        "start": "error",
        "nodes": {
            "error": {
                "agent": "error_agent",
                "next": "normal"
            },
            "normal": {
                "agent": "normal_agent",
                "next": None
            }
        }
    }
    
    # 初始状态
    initial_state = {"continue": True}
    
    # 执行图（应该继续执行）
    final_state = await engine.run_async(graph, initial_state)
    
    print(f"最终状态: {final_state}")
    
    # 验证错误被记录但继续执行
    assert "error_error" in final_state
    assert final_state["normal_executed"] == True
    assert final_state["normal_executed"] == True
    
    print("✓ 错误处理测试通过")


async def main():
    """运行所有测试"""
    print("开始测试 GraphEngine State 流转功能...")
    
    try:
        await test_agent_adapter()
        await test_graph_engine_with_execute_agent()
        await test_graph_engine_with_run_agent()
        await test_state_flow_chain()
        await test_state_object_features()
        await test_error_handling()
        
        print("\n🎉 所有测试通过！GraphEngine 已成功支持 state = agent.run(state) 统一接口。")
        
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)