"""
State上下文传递机制
提供标准化的上下文对象，支持类型安全访问
"""

from typing import Dict, Any, Optional, Union, List
from datetime import datetime
import json
import copy


class Context:
    """
    统一上下文对象，用于在Agent/Tool之间传递状态
    支持类型安全访问和链式操作
    """
    
    def __init__(self, initial_state: Optional[Dict[str, Any]] = None):
        """
        初始化上下文
        
        Args:
            initial_state: 初始状态字典
        """
        self._state: Dict[str, Any] = initial_state.copy() if initial_state else {}
        self._metadata: Dict[str, Any] = {
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
            "version": "1.0"
        }
        self._history: List[Dict[str, Any]] = []
    
    def get(self, key: str, default: Any = None) -> Any:
        """
        安全获取值
        
        Args:
            key: 键名
            default: 默认值
            
        Returns:
            键对应的值，如果不存在则返回默认值
        """
        return self._state.get(key, default)
    
    def set(self, key: str, value: Any) -> 'Context':
        """
        设置值（链式操作）
        
        Args:
            key: 键名
            value: 值
            
        Returns:
            self（支持链式调用）
        """
        # 记录历史
        old_value = self._state.get(key)
        self._history.append({
            "timestamp": datetime.now().isoformat(),
            "operation": "set",
            "key": key,
            "old_value": old_value,
            "new_value": value
        })
        
        # 更新状态
        self._state[key] = value
        self._metadata["updated_at"] = datetime.now().isoformat()
        
        return self
    
    def update(self, updates: Dict[str, Any]) -> 'Context':
        """
        批量更新值（链式操作）
        
        Args:
            updates: 更新字典
            
        Returns:
            self（支持链式调用）
        """
        for key, value in updates.items():
            self.set(key, value)
        return self
    
    def delete(self, key: str) -> 'Context':
        """
        删除键（链式操作）
        
        Args:
            key: 要删除的键名
            
        Returns:
            self（支持链式调用）
        """
        if key in self._state:
            # 记录历史
            old_value = self._state[key]
            self._history.append({
                "timestamp": datetime.now().isoformat(),
                "operation": "delete",
                "key": key,
                "old_value": old_value
            })
            
            # 删除键
            del self._state[key]
            self._metadata["updated_at"] = datetime.now().isoformat()
        
        return self
    
    def has(self, key: str) -> bool:
        """
        检查键是否存在
        
        Args:
            key: 键名
            
        Returns:
            是否存在
        """
        return key in self._state
    
    def keys(self) -> List[str]:
        """
        获取所有键
        
        Returns:
            键列表
        """
        return list(self._state.keys())
    
    def values(self) -> List[Any]:
        """
        获取所有值
        
        Returns:
            值列表
        """
        return list(self._state.values())
    
    def items(self) -> List[tuple]:
        """
        获取所有键值对
        
        Returns:
            键值对列表
        """
        return list(self._state.items())
    
    def to_dict(self) -> Dict[str, Any]:
        """
        转换为字典
        
        Returns:
            状态字典
        """
        return copy.deepcopy(self._state)
    
    def get_metadata(self) -> Dict[str, Any]:
        """
        获取元数据
        
        Returns:
            元数据字典
        """
        return copy.deepcopy(self._metadata)
    
    def get_history(self) -> List[Dict[str, Any]]:
        """
        获取操作历史
        
        Returns:
            操作历史列表
        """
        return copy.deepcopy(self._history)
    
    def clear_history(self) -> 'Context':
        """
        清空操作历史
        
        Returns:
            self（支持链式调用）
        """
        self._history.clear()
        return self
    
    def snapshot(self) -> Dict[str, Any]:
        """
        创建快照
        
        Returns:
            快照字典（包含状态和元数据）
        """
        return {
            "state": self.to_dict(),
            "metadata": self.get_metadata(),
            "history_size": len(self._history)
        }
    
    def restore(self, snapshot: Dict[str, Any]) -> 'Context':
        """
        从快照恢复
        
        Args:
            snapshot: 快照字典
            
        Returns:
            self（支持链式调用）
        """
        if "state" in snapshot:
            self._state = copy.deepcopy(snapshot["state"])
        if "metadata" in snapshot:
            self._metadata.update(copy.deepcopy(snapshot["metadata"]))
        
        self._metadata["updated_at"] = datetime.now().isoformat()
        return self
    
    def __getitem__(self, key: str) -> Any:
        """支持字典式访问"""
        return self._state[key]
    
    def __setitem__(self, key: str, value: Any) -> None:
        """支持字典式设置"""
        self.set(key, value)
    
    def __contains__(self, key: str) -> bool:
        """支持in操作符"""
        return key in self._state
    
    def __len__(self) -> int:
        """获取状态大小"""
        return len(self._state)
    
    def __str__(self) -> str:
        """字符串表示"""
        return f"Context(state={self._state}, metadata={self._metadata})"
    
    def __repr__(self) -> str:
        """repr表示"""
        return f"Context(state={self._state})"


class ContextManager:
    """
    上下文管理器，管理多个上下文实例
    """
    
    def __init__(self):
        self._contexts: Dict[str, Context] = {}
    
    def create_context(self, context_id: str, initial_state: Optional[Dict[str, Any]] = None) -> Context:
        """
        创建新上下文
        
        Args:
            context_id: 上下文ID
            initial_state: 初始状态
            
        Returns:
            创建的Context实例
        """
        context = Context(initial_state)
        self._contexts[context_id] = context
        return context
    
    def get_context(self, context_id: str) -> Optional[Context]:
        """
        获取上下文
        
        Args:
            context_id: 上下文ID
            
        Returns:
            Context实例，如果不存在则返回None
        """
        return self._contexts.get(context_id)
    
    def delete_context(self, context_id: str) -> bool:
        """
        删除上下文
        
        Args:
            context_id: 上下文ID
            
        Returns:
            是否成功删除
        """
        if context_id in self._contexts:
            del self._contexts[context_id]
            return True
        return False
    
    def list_contexts(self) -> List[str]:
        """
        列出所有上下文ID
        
        Returns:
            上下文ID列表
        """
        return list(self._contexts.keys())
    
    def clear_all(self) -> None:
        """清空所有上下文"""
        self._contexts.clear()


# 全局上下文管理器实例
context_manager = ContextManager()