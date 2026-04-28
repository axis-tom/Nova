"""
Agent记忆 - 长期记忆层
管理Agent的持久化记忆数据
"""

from typing import Dict, Any, Optional, List
from datetime import datetime
import uuid


class AgentMemory:
    """
    Agent记忆管理器
    负责管理Agent的持久化记忆数据
    """
    
    def __init__(self, agent_id: str):
        """
        初始化Agent记忆
        
        Args:
            agent_id: Agent ID
        """
        self.agent_id = agent_id
        self._memories: Dict[str, Dict[str, Any]] = {}
    
    def remember(self, key: str, data: Dict[str, Any]) -> str:
        """
        记录记忆
        
        Args:
            key: 记忆键
            data: 记忆数据
            
        Returns:
            记忆ID
        """
        memory_id = str(uuid.uuid4())
        self._memories[memory_id] = {
            "id": memory_id,
            "agent_id": self.agent_id,
            "key": key,
            "data": data,
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat()
        }
        return memory_id
    
    def recall(self, memory_id: str) -> Optional[Dict[str, Any]]:
        """
        回忆记忆
        
        Args:
            memory_id: 记忆ID
            
        Returns:
            记忆数据，如果不存在则返回None
        """
        return self._memories.get(memory_id)
    
    def forget(self, memory_id: str) -> bool:
        """
        遗忘记忆
        
        Args:
            memory_id: 记忆ID
            
        Returns:
            是否遗忘成功
        """
        if memory_id in self._memories:
            del self._memories[memory_id]
            return True
        return False
    
    def recall_all(self) -> List[Dict[str, Any]]:
        """
        回忆所有记忆
        
        Returns:
            记忆列表
        """
        return list(self._memories.values())
    
    def search(self, query: str) -> List[Dict[str, Any]]:
        """
        搜索记忆
        
        Args:
            query: 搜索关键词
            
        Returns:
            匹配的记忆列表
        """
        results = []
        query_lower = query.lower()
        for memory in self._memories.values():
            if query_lower in memory["key"].lower():
                results.append(memory)
            elif isinstance(memory["data"], dict):
                for k, v in memory["data"].items():
                    if query_lower in str(k).lower() or query_lower in str(v).lower():
                        results.append(memory)
                        break
        return results
