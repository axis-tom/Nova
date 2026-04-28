#!/usr/bin/env python3
"""
示例：如何按照新规范编写Agent

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

class NewStyleEmailAgent(Agent):
    """按照新规范编写的EmailAgent示例"""
    
    def __init__(self, db_session=None):
        self.name = "new_style_email_agent"
        self.description = "按照新规范编写的EmailAgent"
        self.db = db_session
        # 注意：在实际实现中，这里会初始化数据库仓库等
        
    def run(self, state: State) -> State:
        """
        执行EmailAgent逻辑（新规范）
        
        遵循新规范：
        1. 接受 State 对象作为输入
        2. 在方法开始和结束时添加事件
        3. 通过 state.set() 设置结果
        4. 返回修改后的 State 对象
        """
        # 记录Agent开始执行
        state.add_event(f"{self.name}_start")
        
        # 从state中获取必要信息
        user_id = state.get("user_id")
        if not user_id:
            state.set("error", "缺少user_id")
            state.add_event(f"{self.name}_error: 缺少user_id")
            state.add_event(f"{self.name}_end")
            return state
        
        # 模拟处理逻辑
        email_count = state.get("email_count", 0)
        new_emails = [
            {"id": 1, "subject": "测试邮件1", "from": "sender1@example.com"},
            {"id": 2, "subject": "测试邮件2", "from": "sender2@example.com"}
        ]
        
        # 通过state.set()设置结果
        state.set("emails", new_emails)
        state.set("total_emails", email_count + len(new_emails))
        state.set("processed_at", "2024-01-01T12:00:00")
        
        # 设置元数据
        state.set_meta("agent_version", "1.0.0")
        state.set_meta("processing_time_ms", 150)
        
        # 记录处理详情
        state.add_event(f"{self.name}_processed_{len(new_emails)}_emails")
        
        # 记录Agent结束执行
        state.add_event(f"{self.name}_end")
        
        return state

class NewStyleFinancialAgent(Agent):
    """按照新规范编写的FinancialAgent示例"""
    
    def __init__(self):
        self.name = "new_style_financial_agent"
        self.description = "按照新规范编写的FinancialAgent"
        
    def run(self, state: State) -> State:
        """
        执行FinancialAgent逻辑（新规范）
        """
        # 记录Agent开始执行
        state.add_event(f"{self.name}_start")
        
        # 处理逻辑
        financial_data = state.get("financial_data", {})
        
        # 模拟财务分析
        analysis_result = {
            "revenue": financial_data.get("revenue", 0) * 1.1,  # 增长10%
            "profit": financial_data.get("profit", 0) * 1.15,   # 增长15%
            "risk_score": 0.3,  # 风险评分
            "recommendation": "买入" if financial_data.get("revenue", 0) > 1000 else "持有"
        }
        
        # 通过state.set()设置结果
        state.set("analysis", analysis_result)
        state.set("analyzed", True)
        
        # 记录Agent结束执行
        state.add_event(f"{self.name}_end")
        
        return state

def example_chain_agents():
    """示例：链式调用多个Agent"""
    print("=== 示例：链式调用多个Agent ===")
    
    # 创建Agent实例
    email_agent = NewStyleEmailAgent()
    financial_agent = NewStyleFinancialAgent()
    
    # 创建初始状态
    state = State({
        "user_id": 12345,
        "email_count": 5,
        "financial_data": {
            "revenue": 1500,
            "profit": 300,
            "expenses": 1200
        }
    })
    
    print(f"初始状态: {state}")
    
    # 链式调用：EmailAgent -> FinancialAgent
    state = email_agent.run(state)
    print(f"\nEmailAgent执行后:")
    print(f"  - 邮件数量: {state.get('total_emails')}")
    print(f"  - 事件: {state.events[-2:]}")  # 显示最后两个事件
    
    state = financial_agent.run(state)
    print(f"\nFinancialAgent执行后:")
    print(f"  - 分析结果: {state.get('analysis')}")
    print(f"  - 事件: {state.events[-2:]}")  # 显示最后两个事件
    
    print(f"\n最终状态摘要:")
    print(f"  - 数据键: {list(state.keys())}")
    print(f"  - 事件数量: {len(state.events)}")
    print(f"  - 元数据: {state.meta}")

def example_backward_compatibility():
    """示例：向后兼容性"""
    print("\n=== 示例：向后兼容性 ===")
    
    # 创建新规范Agent
    agent = NewStyleEmailAgent()
    
    # 使用旧接口调用
    from backend.agents.base import AgentInput
    
    agent_input = AgentInput(
        data={"user_id": 999, "email_count": 10},
        user_id=999,
        trace_id="backward-comp-test",
        config={"test_mode": True}
    )
    
    print(f"使用旧接口调用Agent:")
    print(f"  - AgentInput: {agent_input}")
    
    # 执行execute方法（旧接口）
    import asyncio
    output = asyncio.run(agent.execute(agent_input))
    
    print(f"  - AgentOutput: {output}")
    print(f"  - 结果类型: {type(output.result)}")
    
    # 验证向后兼容
    assert isinstance(output.result, dict), "结果应该是字典"
    assert "emails" in output.result, "结果应该包含emails"
    
    print("✓ 向后兼容性验证通过")

def example_state_operations():
    """示例：State操作"""
    print("\n=== 示例：State操作 ===")
    
    # 创建State
    state = State({"initial": "data"})
    
    print("State操作示例:")
    
    # 1. 基本操作
    state.set("key1", "value1")
    state["key2"] = "value2"
    print(f"1. 设置值: key1={state.get('key1')}, key2={state['key2']}")
    
    # 2. 事件记录
    state.add_event("event1")
    state.add_event("event2")
    print(f"2. 事件记录: {state.events}")
    
    # 3. 元数据操作
    state.set_meta("version", "1.0")
    state.set_meta("source", "test")
    print(f"3. 元数据: {state.meta}")
    
    # 4. 嵌套操作
    state.set_nested("user.profile.name", "John Doe")
    state.set_nested("user.profile.age", 30)
    print(f"4. 嵌套值: user.profile.name={state.get_nested('user.profile.name')}")
    
    # 5. 批量更新
    state.update_nested({
        "user.profile.city": "Beijing",
        "user.profile.job": "Engineer"
    })
    print(f"5. 批量更新后: user.profile.city={state.get_nested('user.profile.city')}")
    
    # 6. 复制和合并
    state_copy = state.copy()
    state_copy["new_key"] = "new_value"
    print(f"6. 复制验证: 原始有new_key={'new_key' in state}, 复制有new_key={'new_key' in state_copy}")

def main():
    """运行所有示例"""
    print("开始展示新的Agent接口规范示例...")
    
    try:
        example_chain_agents()
        example_backward_compatibility()
        example_state_operations()
        
        print("\n🎉 所有示例执行成功！")
        print("\n新规范要点总结:")
        print("1. 所有Agent必须实现 run(state: State) -> State 方法")
        print("2. 在run方法中使用 state.add_event() 记录执行过程")
        print("3. 使用 state.set() 或 state['key'] = value 设置结果")
        print("4. 使用 state.get() 获取输入数据")
        print("5. 保持向后兼容：execute方法会自动调用run方法")
        print("6. Agent之间通过State对象传递数据，而不是直接传参")
        
    except Exception as e:
        print(f"\n❌ 示例执行失败: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)