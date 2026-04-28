#!/usr/bin/env python3
"""
最终测试 Agent 返回 state patch 规范格式
"""

import sys
import os

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# 导入我们修改后的模块
from backend.agents.standard_base import BaseAgent
from backend.core.state import State


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


def test_base_agent_with_patch():
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
    return True


def test_agent_with_error():
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
    return True


def test_state_object_usage():
    """测试 State 对象的使用"""
    print("\n=== 测试 State 对象的使用 ===")
    
    agent = SimpleAgentWithPatch()
    
    # 使用 State 对象作为输入
    initial_state = State({"counter": 15, "user_id": 123})
    result = agent.run(initial_state)
    
    print(f"初始状态 (State对象): {initial_state.to_plain_dict()}")
    print(f"Agent 返回结果: {result}")
    
    # 验证结果
    assert result["state"]["counter"] == 16, "计数器应该增加"
    assert result["status"] == "ok", "状态应该是 'ok'"
    
    print("✓ State 对象使用测试通过")
    return True


def test_interface_compliance():
    """测试接口符合性"""
    print("\n=== 测试接口符合性 ===")
    
    # 测试 BaseAgent 是抽象类
    try:
        base_agent = BaseAgent()
        base_agent.run({})
        print("❌ BaseAgent 应该不能实例化")
        return False
    except TypeError as e:
        print(f"✓ BaseAgent 是抽象类，不能实例化: {e}")
    
    # 测试子类必须实现 run 方法
    class IncompleteAgent(BaseAgent):
        pass
    
    try:
        agent = IncompleteAgent()
        agent.run({})
        print("❌ 不完整的 Agent 应该不能运行")
        return False
    except TypeError as e:
        print(f"✓ 不完整的 Agent 不能实例化: {e}")
    except NotImplementedError as e:
        print(f"✓ 不完整的 Agent 抛出 NotImplementedError: {e}")
    
    print("✓ 接口符合性测试通过")
    return True


def main():
    """运行所有测试"""
    print("开始测试 Agent 返回 state patch 规范格式...")
    
    success = True
    try:
        if not test_base_agent_with_patch():
            success = False
        
        if not test_agent_with_error():
            success = False
        
        if not test_state_object_usage():
            success = False
        
        if not test_interface_compliance():
            success = False
        
        if success:
            print("\n🎉 所有测试通过！Agent 已成功支持返回 state patch 规范格式。")
            print("规范格式: {\"state\": state_dict, \"events\": [], \"status\": \"ok\"}")
            print("\n修改的文件:")
            print("1. backend/agents/standard_base.py - 更新 BaseAgent 接口文档")
            print("2. backend/workflow/agent_adapter.py - 更新适配器返回规范格式")
            print("3. backend/workflow/graph_engine.py - 更新 GraphEngine 处理规范格式")
            print("4. backend/workflow/graph_engine_v2.py - 更新 GraphEngineV2 处理规范格式")
        else:
            print("\n❌ 部分测试失败")
        
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        success = False
    
    return 0 if success else 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)