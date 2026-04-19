#!/usr/bin/env python3
"""
测试 Agent 返回 state patch 规范格式
"""

import asyncio
import sys
import os

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from backend.agents.standard_base import BaseAgent
from backend.core.state import State
from backend.workflow.agent_adapter import AgentAdapter, AsyncAgentAdapter
from backend.agents.base import Agent, AgentInput, AgentOutput
from backend.workflow.graph_engine import GraphEngine
from backend.agents.registry import AgentRegistry


class SimpleAgentWithPatch(BaseAgent):
    """简单的 Agent，返回规范格式的 state patch"""
    
    def run(self, state):
        # 确保输入是 State 对象
        state_obj = self._ensure_state(state)
        
        # 更新状态
        counter = state_obj.get("counter", 0)
        state_obj["counter"] = counter + 1
        state_obj["processed"] = True
        
        # 返回规范格式
        return {
            "state": state_obj.to_plain_dict(),
            "events": ["counter_incremented"],
            "status": "ok"
        }


class SimpleAgentWithError(BaseAgent):
    """返回错误状态的 Agent"""
    
    def run(self, state):
        # 确保输入是 State 对象
        state_obj = self._ensure_state(state)
        
        # 返回错误状态
        return {
            "state": state_obj.to_plain_dict(),
            "events": [],
            "status": "error",
            "error": "模拟错误"
        }


class LegacyAgentWithExecute(Agent):
    """传统的 Agent（有 execute 方法）"""
    
    def __init__(self, name="legacy_agent"):
        self.name = name
    
    async def execute(self, input_data: AgentInput) -> AgentOutput:
        """执行逻辑"""
        data = input_data.data
        counter = data.get("counter", 0)
        
        return AgentOutput(
            result={"counter": counter + 2, "legacy": True},
            metadata={"executed": True}
        )


async def test_base_agent_with_patch():
    """测试 BaseAgent 返回规范格式"""
    print("=== 测试 BaseAgent 返回规范格式 ===")
    
    agent = SimpleAgentWithPatch()
    
    # 测试同步执行
    initial_state = {"counter": 5, "test": "data"}
    result = agent.run(initial_state)
    
    print(f"初始状态: {initial_state}")
    print(f"Agent 返回结果: {result}")
    
    # 验证规范格式
    assert isinstance(result, dict), "结果应该是字典"
    assert "state" in result, "结果应该包含 'state' 字段"
    assert "events" in result, "结果应该包含 'events' 字段"
    assert "status" in result, "结果应该包含 'status' 字段"
    assert result["status"] == "ok", "状态应该是 'ok'"
    assert result["state"]["counter"] == 6, "计数器应该增加"
    assert result["state"]["processed"] == True, "应该标记为已处理"
    assert "counter_incremented" in result["events"], "应该包含事件"
    
    print("✓ BaseAgent 规范格式测试通过")


async def test_agent_with_error():
    """测试返回错误状态的 Agent"""
    print("\n=== 测试返回错误状态的 Agent ===")
    
    agent = SimpleAgentWithError()
    
    initial_state = {"counter": 10}
    result = agent.run(initial_state)
    
    print(f"初始状态: {initial_state}")
    print(f"Agent 返回结果: {result}")
    
    # 验证错误格式
    assert result["status"] == "error", "状态应该是 'error'"
    assert "error" in result, "应该包含错误信息"
    assert result["error"] == "模拟错误", "错误信息应该正确"
    assert result["state"]["counter"] == 10, "状态应该保持不变"
    
    print("✓ Agent 错误状态测试通过")


async def test_legacy_agent_adaptation():
    """测试传统 Agent 的适配"""
    print("\n=== 测试传统 Agent 的适配 ===")
    
    legacy_agent = LegacyAgentWithExecute()
    adapter = AgentAdapter(legacy_agent)
    
    initial_state = {"counter": 20, "user_id": 123}
    result = adapter.run(initial_state)
    
    print(f"初始状态: {initial_state}")
    print(f"适配器返回结果: {result}")
    
    # 验证适配器返回规范格式
    assert isinstance(result, dict), "结果应该是字典"
    assert "state" in result, "结果应该包含 'state' 字段"
    assert "status" in result, "结果应该包含 'status' 字段"
    assert result["status"] == "ok", "状态应该是 'ok'"
    assert result["state"]["counter"] == 22, "计数器应该增加2"
    assert result["state"]["legacy"] == True, "应该包含 legacy 标记"
    assert result["state"]["legacy_agent_executed"] == True, "应该标记为已执行"
    
    print("✓ 传统 Agent 适配测试通过")


async def test_graph_engine_with_patch():
    """测试 GraphEngine 处理规范格式"""
    print("\n=== 测试 GraphEngine 处理规范格式 ===")
    
    # 注册测试 Agent
    AgentRegistry.clear()
    AgentRegistry.register("patch_agent", SimpleAgentWithPatch)
    AgentRegistry.register("error_agent", SimpleAgentWithError)
    
    # 创建 GraphEngine
    engine = GraphEngine()
    
    # 定义图
    graph = {
        "start": "node1",
        "nodes": {
            "node1": {
                "agent": "patch_agent",
                "next": "node2"
            },
            "node2": {
                "agent": "error_agent",
                "next": "node3"
            },
            "node3": {
                "agent": "patch_agent",
                "next": None
            }
        }
    }
    
    # 初始状态
    initial_state = {"counter": 0, "user_id": 456}
    
    # 执行图
    final_state = await engine.run_async(graph, initial_state)
    
    print(f"初始状态: {initial_state}")
    print(f"最终状态: {final_state}")
    
    # 验证执行结果
    assert final_state["counter"] == 2, "应该执行了两次 patch_agent"
    assert final_state["node1_executed"] == True, "node1 应该已执行"
    assert final_state["node1_status"] == "ok", "node1 状态应该是 ok"
    assert final_state["node2_executed"] == True, "node2 应该已执行"
    assert final_state["node2_status"] == "error", "node2 状态应该是 error"
    assert "node2_error" in final_state, "node2 应该有错误信息"
    assert final_state["node3_executed"] == True, "node3 应该已执行"
    assert final_state["node3_status"] == "ok", "node3 状态应该是 ok"
    
    print("✓ GraphEngine 规范格式处理测试通过")


async def test_async_agent_adapter():
    """测试异步 Agent 适配器"""
    print("\n=== 测试异步 Agent 适配器 ===")
    
    legacy_agent = LegacyAgentWithExecute()
    async_adapter = AsyncAgentAdapter(legacy_agent)
    
    initial_state = {"counter": 30, "user_id": 789}
    
    # 测试异步执行
    result = await async_adapter.run_async(initial_state)
    
    print(f"初始状态: {initial_state}")
    print(f"异步适配器返回结果: {result}")
    
    # 验证异步适配器返回规范格式
    assert isinstance(result, dict), "结果应该是字典"
    assert "state" in result, "结果应该包含 'state' 字段"
    assert "status" in result, "结果应该包含 'status' 字段"
    assert result["status"] == "ok", "状态应该是 'ok'"
    assert result["state"]["counter"] == 32, "计数器应该增加2"
    
    # 测试同步包装
    sync_result = async_adapter.run(initial_state)
    assert sync_result["state"]["counter"] == 32, "同步包装应该工作正常"
    
    print("✓ 异步 Agent 适配器测试通过")


async def main():
    """运行所有测试"""
    print("开始测试 Agent 返回 state patch 规范格式...")
    
    try:
        await test_base_agent_with_patch()
        await test_agent_with_error()
        await test_legacy_agent_adaptation()
        await test_graph_engine_with_patch()
        await test_async_agent_adapter()
        
        print("\n🎉 所有测试通过！Agent 已成功支持返回 state patch 规范格式。")
        print("规范格式: {\"state\": state_dict, \"events\": [], \"status\": \"ok\"}")
        
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)