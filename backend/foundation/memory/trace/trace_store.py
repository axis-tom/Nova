"""
追踪存储 - Trace持久化层
负责Trace数据的存储和检索
"""

from typing import Dict, Any, List, Optional
from datetime import datetime
import json


class TraceStore:
    """
    追踪数据存储
    提供Trace数据的持久化存储和检索功能
    """
    
    def __init__(self, storage_path: Optional[str] = None):
        """
        初始化TraceStore
        
        Args:
            storage_path: 存储路径（可选）
        """
        self.storage_path = storage_path
        self._cache: Dict[str, Dict[str, Any]] = {}
    
    def save(self, trace_id: str, data: Dict[str, Any]) -> bool:
        """
        保存Trace数据
        
        Args:
            trace_id: 追踪ID
            data: 追踪数据
            
        Returns:
            是否保存成功
        """
        self._cache[trace_id] = {
            **data,
            "saved_at": datetime.now().isoformat()
        }
        return True
    
    def load(self, trace_id: str) -> Optional[Dict[str, Any]]:
        """
        加载Trace数据
        
        Args:
            trace_id: 追踪ID
            
        Returns:
            追踪数据，如果不存在则返回None
        """
        return self._cache.get(trace_id)
    
    def delete(self, trace_id: str) -> bool:
        """
        删除Trace数据
        
        Args:
            trace_id: 追踪ID
            
        Returns:
            是否删除成功
        """
        if trace_id in self._cache:
            del self._cache[trace_id]
            return True
        return False
    
    def list(self) -> List[str]:
        """
        列出所有Trace ID
        
        Returns:
            Trace ID列表
        """
        return list(self._cache.keys())
    
    def clear(self) -> None:
        """清空所有Trace数据"""
        self._cache.clear()
