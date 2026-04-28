from abc import ABC, abstractmethod
from typing import Dict, Any, Union, List
from backend.foundation.cognition.state_machine.state_machine import State


class BaseAgent(ABC):
    """
    所有Agent必须继承该接口（新规范）
    输入：state（State对象）
    输出：state（修改后的State对象）
    
    新规范要求：
    1. 接受 State 对象作为输入
    2. 在方法开始和结束时添加事件
    3. 通过 state.set() 设置结果
    4. 返回修改后的 State 对象
    """
    
    @abstractmethod
    def run(self, state: State) -> State:
        """
        执行Agent逻辑（新规范）
        
        Args:
            state: State对象，包含执行上下文和数据
            
        Returns:
            修改后的State对象
            
        Raises:
            NotImplementedError: 子类必须实现此方法
        """
        raise NotImplementedError
    
    def _ensure_state(self, state: Union[Dict[str, Any], State]) -> State:
        """
        确保输入是State对象（向后兼容）
        
        Args:
            state: 输入状态
            
        Returns:
            State对象
        """
        if isinstance(state, State):
            return state
        return State(state)
    
    def _run_with_events(self, state: State) -> State:
        """
        带有事件记录的run方法包装器
        
        这是一个辅助方法，子类可以重写run方法，然后调用此方法
        来添加标准的事件记录
        
        Args:
            state: State对象
            
        Returns:
            修改后的State对象
        """
        # 记录Agent开始执行
        state.add_event(f"{self.__class__.__name__}_start")
        
        # 调用子类的run方法
        result_state = self.run(state)
        
        # 记录Agent结束执行
        result_state.add_event(f"{self.__class__.__name__}_end")
        
        return result_state
