"""
工作记忆 - 短期记忆层
管理当前会话的上下文状态
"""

from typing import Dict, Any, Optional, List
from datetime import datetime
import uuid
import json


class WorkingMemory:
    """
    工作记忆管理器
    负责管理当前会话的上下文状态
    """
    
    def __init__(self, session_id: Optional[str] = None):
        """
        初始化工作记忆
        
        Args:
            session_id: 会话ID，如果未提供则自动生成
        """
        self.session_id = session_id or str(uuid.uuid4())
        self.context: Dict[str, Any] = {}
        self.history: List[Dict[str, Any]] = []
        self.created_at = datetime.now()
        self.updated_at = datetime.now()
    
    def set(self, key: str, value: Any) -> 'WorkingMemory':
        """
        设置上下文
        
        Args:
            key: 键
            value: 值
            
        Returns:
            self（支持链式调用）
        """
        self.context[key] = value
        self.updated_at = datetime.now()
        return self
    
    def get(self, key: str, default: Any = None) -> Any:
        """
        获取上下文
        
        Args:
            key: 键
            default: 默认值
            
        Returns:
            上下文值
        """
        return self.context.get(key, default)
    
    def update(self, updates: Dict[str, Any]) -> 'WorkingMemory':
        """
        批量更新上下文
        
        Args:
            updates: 更新字典
            
        Returns:
            self（支持链式调用）
        """
        self.context.update(updates)
        self.updated_at = datetime.now()
        return self
    
    def push_history(self, entry: Dict[str, Any]) -> 'WorkingMemory':
        """
        添加历史记录
        
        Args:
            entry: 历史记录条目
            
        Returns:
            self（支持链式调用）
        """
        entry["timestamp"] = datetime.now().isoformat()
        self.history.append(entry)
        self.updated_at = datetime.now()
        return self
    
    def clear(self) -> 'WorkingMemory':
        """
        清空上下文
        
        Returns:
            self（支持链式调用）
        """
        self.context.clear()
        self.history.clear()
        self.updated_at = datetime.now()
        return self
    
    def to_dict(self) -> Dict[str, Any]:
        """
        转换为字典
        
        Returns:
            字典表示
        """
        return {
            "session_id": self.session_id,
            "context": self.context,
            "history": self.history,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat()
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'WorkingMemory':
        """
        从字典创建
        
        Args:
            data: 字典数据
            
        Returns:
            WorkingMemory实例
        """
        instance = cls(session_id=data.get("session_id"))
        instance.context = data.get("context", {})
        instance.history = data.get("history", [])
        instance.created_at = datetime.fromisoformat(data["created_at"]) if "created_at" in data else datetime.now()
        instance.updated_at = datetime.fromisoformat(data["updated_at"]) if "updated_at" in data else datetime.now()
        return instance
    
    def __str__(self) -> str:
        return f"WorkingMemory(session_id={self.session_id[:8]}..., context_keys={list(self.context.keys())})"
