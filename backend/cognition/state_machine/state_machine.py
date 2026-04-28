"""
State Machine - 状态机引擎
管理状态流转和转换规则
"""

from typing import Dict, Any, Optional, Callable, List
from enum import Enum
from backend.cognition.state_machine.state_machine import State


class StateMachine:
    """
    状态机引擎
    
    管理状态流转，支持：
    1. 状态定义和转换规则
    2. 状态进入/离开钩子
    3. 状态转换事件
    """
    
    def __init__(self, initial_state: str = "initial"):
        self.current_state = initial_state
        self.states = {}
        self.transitions = {}
        self.hooks = {"enter": {}, "leave": {}, "transition": {}}
    
    def add_state(self, name: str, config: Dict[str, Any] = None):
        """添加状态定义"""
        self.states[name] = config or {}
    
    def add_transition(self, from_state: str, to_state: str, 
                       condition: Callable = None, action: Callable = None):
        """添加转换规则"""
        if from_state not in self.transitions:
            self.transitions[from_state] = []
        self.transitions[from_state].append({
            "to": to_state,
            "condition": condition,
            "action": action
        })
    
    def add_hook(self, hook_type: str, state: str, handler: Callable):
        """添加钩子函数"""
        if hook_type not in self.hooks:
            raise ValueError(f"Unknown hook type: {hook_type}")
        if state not in self.hooks[hook_type]:
            self.hooks[hook_type][state] = []
        self.hooks[hook_type][state].append(handler)
    
    def transition(self, target_state: str, context: State = None) -> bool:
        """
        执行状态转换
        
        Args:
            target_state: 目标状态
            context: 上下文状态
            
        Returns:
            是否转换成功
        """
        # 检查转换规则
        if self.current_state in self.transitions:
            for rule in self.transitions[self.current_state]:
                if rule["to"] == target_state:
                    # 检查条件
                    if rule["condition"] and context:
                        if not rule["condition"](context):
                            return False
                    
                    # 执行离开钩子
                    self._run_hooks("leave", self.current_state, context)
                    
                    # 执行转换动作
                    if rule["action"] and context:
                        rule["action"](context)
                    
                    # 更新状态
                    old_state = self.current_state
                    self.current_state = target_state
                    
                    # 执行转换钩子
                    self._run_hooks("transition", f"{old_state}->{target_state}", context)
                    
                    # 执行进入钩子
                    self._run_hooks("enter", target_state, context)
                    
                    return True
        
        return False
    
    def _run_hooks(self, hook_type: str, state: str, context: State = None):
        """运行钩子函数"""
        if state in self.hooks.get(hook_type, {}):
            for handler in self.hooks[hook_type][state]:
                try:
                    if context:
                        handler(context)
                    else:
                        handler()
                except Exception as e:
                    print(f"Hook error ({hook_type}/{state}): {e}")
    
    def get_state(self) -> str:
        """获取当前状态"""
        return self.current_state
    
    def can_transition(self, target_state: str, context: State = None) -> bool:
        """检查是否可以转换到目标状态"""
        if self.current_state in self.transitions:
            for rule in self.transitions[self.current_state]:
                if rule["to"] == target_state:
                    if rule["condition"] and context:
                        return rule["condition"](context)
                    return True
        return False
    
    def get_available_transitions(self, context: State = None) -> List[str]:
        """获取可用的转换目标"""
        available = []
        if self.current_state in self.transitions:
            for rule in self.transitions[self.current_state]:
                if rule["condition"] and context:
                    if rule["condition"](context):
                        available.append(rule["to"])
                else:
                    available.append(rule["to"])
        return available
    
    def reset(self, initial_state: str = "initial"):
        """重置状态机"""
        self.current_state = initial_state
