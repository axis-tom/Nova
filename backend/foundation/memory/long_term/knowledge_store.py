"""
知识存储 - 长期记忆层
管理持久化的知识数据
"""

from typing import Dict, Any, Optional, List
from datetime import datetime
import uuid


class KnowledgeStore:
    """
    知识存储
    负责管理持久化的知识数据
    """
    
    def __init__(self):
        """初始化知识存储"""
        self._knowledge: Dict[str, Dict[str, Any]] = {}
    
    def add(self, key: str, data: Dict[str, Any]) -> str:
        """
        添加知识
        
        Args:
            key: 知识键
            data: 知识数据
            
        Returns:
            知识ID
        """
        knowledge_id = str(uuid.uuid4())
        self._knowledge[knowledge_id] = {
            "id": knowledge_id,
            "key": key,
            "data": data,
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat()
        }
        return knowledge_id
    
    def get(self, knowledge_id: str) -> Optional[Dict[str, Any]]:
        """
        获取知识
        
        Args:
            knowledge_id: 知识ID
            
        Returns:
            知识数据，如果不存在则返回None
        """
        return self._knowledge.get(knowledge_id)
    
    def search(self, query: str) -> List[Dict[str, Any]]:
        """
        搜索知识
        
        Args:
            query: 搜索关键词
            
        Returns:
            匹配的知识列表
        """
        results = []
        query_lower = query.lower()
        for knowledge in self._knowledge.values():
            if query_lower in knowledge["key"].lower():
                results.append(knowledge)
            elif isinstance(knowledge["data"], dict):
                for k, v in knowledge["data"].items():
                    if query_lower in str(k).lower() or query_lower in str(v).lower():
                        results.append(knowledge)
                        break
        return results
    
    def delete(self, knowledge_id: str) -> bool:
        """
        删除知识
        
        Args:
            knowledge_id: 知识ID
            
        Returns:
            是否删除成功
        """
        if knowledge_id in self._knowledge:
            del self._knowledge[knowledge_id]
            return True
        return False
    
    def list_all(self) -> List[Dict[str, Any]]:
        """
        列出所有知识
        
        Returns:
            知识列表
        """
        return list(self._knowledge.values())
