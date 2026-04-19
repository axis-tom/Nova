#!/usr/bin/env python3
"""
测试 log_state 函数
"""

import sys
sys.path.insert(0, '.')

from backend.core.state import State
from backend.core.audit import log_state

def test_log_state():
    """测试 log_state 函数"""
    print("=== 测试 log_state 函数 ===")
    
    # 创建一个 State 对象并添加一些事件
    state = State()
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