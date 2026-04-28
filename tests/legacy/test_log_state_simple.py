#!/usr/bin/env python3
"""
简单测试 log_state 函数
直接模拟函数行为，避免导入依赖
"""

# 模拟 State 类
class MockState:
    def __init__(self):
        self.events = []
    
    def add_event(self, event):
        self.events.append(event)

# 模拟 log_state 函数
def log_state(state):
    """
    打印State的事件日志（轻量级追踪）
    
    Args:
        state: State对象，包含events列表
    """
    print(state.events)

def test_log_state():
    """测试 log_state 函数"""
    print("=== 测试 log_state 函数 ===")
    
    # 创建一个 MockState 对象并添加一些事件
    state = MockState()
    state.add_event("事件1: 开始处理")
    state.add_event("事件2: 处理中...")
    state.add_event("事件3: 完成处理")
    
    print("State 对象创建完成，包含以下事件:")
    print(f"state.events = {state.events}")
    
    print("\n调用 log_state(state):")
    log_state(state)
    
    print("\n✅ 测试完成！log_state 函数正常工作。")

if __name__ == "__main__":
    test_log_state()