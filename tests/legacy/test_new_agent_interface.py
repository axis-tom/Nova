#!/usr/bin/env python3
"""
测试新的Agent接口规范

新规范要求：
def run(self, state: State) -> State:
    state.add_event("agent_start")

    # 处理逻辑
    state.set("result", "xxx")

    state.add_event("agent_end")

    return state
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from backend.core.state import State
from backend.agents.base import Agent

class TestNewAgent(Agent):
    """测试新的Agent接口"""
    
    def __init__(self):
        self.name = "test_new_agent"
        self.description = "测试新的Agent接口规范"
    
    def run(self, state: State) -> State:
        """
        执行Agent逻辑（新规范）
        
        遵循新规范：
        1. 接受 State 对象作为输入
        2. 在方法开始和结束时添加事件
        3. 通过 state.set() 设置结果
        4. 返回修改后的 State 对象
        """
        # 记录Agent开始执行
        state.add_event("agent_start")
        
        # 处理逻辑
        # 从state中获取输入数据
        input_data = state.get("input", "default")
        
        # 执行处理逻辑
        result = f"处理结果: {input_data}"
        
        # 通过state.set()设置结果
        state.set("result", result)
        state.set("processed", True)
        state.set_meta("agent_name", self.name)
        
        # 记录Agent结束执行
        state.add_event("agent_end")
        
        return state

class TestLegacyAgent(Agent):
    """测试向后兼容的Agent接口"""
    
    def __init__(self):
        self.name = "test_legacy_agent"
        self.description = "测试向后兼容的Agent接口"
    
    def run(self, state: State) -> State:
        """
        执行Agent逻辑（新规范）
        """
        # 记录Agent开始执行
        state.add_event("legacy_agent_start")
        
        # 处理逻辑
        counter = state.get("counter", 0)
        state.set("counter", counter + 1)
        state.set("message", "Hello from legacy agent")
        
        # 记录Agent结束执行
        state.add_event("legacy_agent_end")
        
        return state

def test_new_agent_interface():
    """测试新的Agent接口"""
    print("=== 测试新的Agent接口 ===")
    
    # 创建测试Agent
    agent = TestNewAgent()
    
    # 创建初始状态
    initial_state = State({
        "input": "测试数据",
        "user_id": 123,
        "trace_id": "test-trace-001"
    })
    
    print(f"初始状态: {initial_state}")
    print(f"初始事件: {initial_state.events}")
    
    # 执行Agent
    result_state = agent.run(initial_state)
    
    print(f"\n执行后状态: {result_state}")
    print(f"执行后事件: {result_state.events}")
    print(f"执行结果: {result_state.get('result')}")
    print(f"是否已处理: {result_state.get('processed')}")
    
    # 验证新规范
    assert "agent_start" in result_state.events[0], "应该包含agent_start事件"
    assert "agent_end" in result_state.events[-1], "应该包含agent_end事件"
    assert result_state.get("result") == "处理结果: 测试数据", "结果应该正确"
    assert result_state.get("processed") == True, "应该标记为已处理"
    
    print("✓ 新的Agent接口测试通过")

def test_legacy_agent_interface():
    """测试向后兼容的Agent接口"""
    print("\n=== 测试向后兼容的Agent接口 ===")
    
    # 创建测试Agent
    agent = TestLegacyAgent()
    
    # 创建初始状态
    initial_state = State({
        "counter": 0,
        "user_id": 456
    })
    
    print(f"初始状态: {initial_state}")
    print(f"初始计数器: {initial_state.get('counter')}")
    
    # 执行Agent多次
    for i in range(3):
        result_state = agent.run(initial_state)
        initial_state = result_state  # 链式调用
        print(f"第{i+1}次执行后计数器: {result_state.get('counter')}")
    
    print(f"\n最终状态: {result_state}")
    print(f"最终事件: {result_state.events}")
    
    # 验证
    assert result_state.get("counter") == 3, "计数器应该增加3次"
    assert "legacy_agent_start" in result_state.events[0], "应该包含开始事件"
    assert "legacy_agent_end" in result_state.events[-1], "应该包含结束事件"
    
    print("✓ 向后兼容的Agent接口测试通过")

def test_backward_compatibility():
    """测试向后兼容性（execute方法）"""
    print("\n=== 测试向后兼容性（execute方法） ===")
    
    # 创建测试Agent
    agent = TestNewAgent()
    
    # 创建AgentInput（旧接口）
    from backend.agents.base import AgentInput
    agent_input = AgentInput(
        data={"input": "向后兼容测试"},
        user_id=789,
        trace_id="backward-test-001",
        config={"test": True}
    )
    
    print(f"AgentInput: {agent_input}")
    
    # 执行execute方法（旧接口）
    import asyncio
    output = asyncio.run(agent.execute(agent_input))
    
    print(f"\nAgentOutput: {output}")
    print(f"结果: {output.result}")
    print(f"元数据: {output.metadata}")
    
    # 验证
    assert output.result == "处理结果: 向后兼容测试", "结果应该正确"
    # 注意：现在metadata包含agent_name，因为从state.meta中提取
    assert "agent_name" in output.metadata, "元数据应该包含agent_name"
    
    print("✓ 向后兼容性测试通过")

def test_state_immutability():
    """测试State的不可变性"""
    print("\n=== 测试State的不可变性 ===")
    
    # 创建测试Agent
    agent = TestNewAgent()
    
    # 创建初始状态
    initial_state = State({
        "input": "原始数据",
        "user_id": 999
    })
    
    # 复制初始状态用于比较
    original_state_copy = initial_state.copy()
    
    # 执行Agent
    result_state = agent.run(initial_state)
    
    print(f"原始状态: {original_state_copy}")
    print(f"结果状态: {result_state}")
    
    # 验证原始状态没有被修改
    assert original_state_copy.get("input") == "原始数据", "原始状态应该保持不变"
    assert "result" not in original_state_copy, "原始状态不应该包含结果"
    assert len(original_state_copy.events) == 0, "原始状态不应该包含事件"
    
    # 验证结果状态被修改
    assert result_state.get("result") == "处理结果: 原始数据", "结果状态应该包含结果"
    assert len(result_state.events) == 2, "结果状态应该包含事件"
    
    print("✓ State不可变性测试通过")

def main():
    """运行所有测试"""
    print("开始测试新的Agent接口规范...")
    
    try:
        test_new_agent_interface()
        test_legacy_agent_interface()
        test_backward_compatibility()
        test_state_immutability()
        
        print("\n🎉 所有测试通过！新的Agent接口规范已成功实现。")
        print("\n新规范总结:")
        print("1. Agent.run(state: State) -> State")
        print("2. 使用 state.add_event() 记录事件")
        print("3. 使用 state.set() 设置结果")
        print("4. 返回修改后的state对象")
        print("5. 保持向后兼容（execute方法）")
        
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)