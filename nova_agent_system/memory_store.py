"""
记忆存储工具
基于 ChromaDB 的向量存储 + 语义检索
零配置，本地运行，数据持久化
"""

from typing import List, Dict, Optional, Any
import chromadb
from chromadb.config import Settings
import uuid
from datetime import datetime


class MemoryStore:
    """
    记忆存储
    存/取历史对话、搜索结果、Agent 输出
    """

    def __init__(self, persist_dir: str = "./nova_memory"):
        self.client = chromadb.PersistentClient(
            path=persist_dir,
            settings=Settings(anonymized_telemetry=False),
        )
        # 两个 collection：对话历史 + 知识缓存
        self._chat_collection = self._get_or_create("chat_history")
        self._knowledge_collection = self._get_or_create("knowledge_cache")

    def _get_or_create(self, name):
        try:
            return self.client.get_collection(name)
        except chromadb.errors.NotFoundError:
            return self.client.create_collection(name)

    # ── 对话历史 ──

    def save_chat(self, user_input: str, response: str, metadata: Optional[Dict] = None) -> str:
        """保存一次对话"""
        chat_id = str(uuid.uuid4())
        self._chat_collection.add(
            documents=[f"用户: {user_input}\n助手: {response}"],
            metadatas=[{
                "type": "chat",
                "user_input": user_input,
                "timestamp": datetime.now().isoformat(),
                **(metadata or {}),
            }],
            ids=[chat_id],
        )
        return chat_id

    def search_chat(self, query: str, k: int = 3) -> List[Dict[str, Any]]:
        """搜索历史对话"""
        results = self._chat_collection.query(query_texts=[query], n_results=k)
        return self._format_results(results)

    # ── 知识缓存 ──

    def save_knowledge(self, key: str, content: str, source: str = "", metadata: Optional[Dict] = None) -> str:
        """保存知识片段（搜索结果、Agent 输出等）"""
        doc_id = str(uuid.uuid4())
        self._knowledge_collection.add(
            documents=[content],
            metadatas=[{
                "key": key,
                "source": source,
                "timestamp": datetime.now().isoformat(),
                **(metadata or {}),
            }],
            ids=[doc_id],
        )
        return doc_id

    def search_knowledge(self, query: str, k: int = 5) -> List[Dict[str, Any]]:
        """语义搜索知识缓存"""
        results = self._knowledge_collection.query(query_texts=[query], n_results=k)
        return self._format_results(results)

    def get_by_key(self, key: str) -> List[Dict[str, Any]]:
        """按 key 精确查找知识"""
        results = self._knowledge_collection.get(where={"key": key})
        return self._format_get_results(results)

    # ── 通用 ──

    def _format_results(self, results) -> List[Dict[str, Any]]:
        """格式化 query 返回结果"""
        items = []
        if not results["ids"]:
            return items
        for i in range(len(results["ids"][0])):
            items.append({
                "id": results["ids"][0][i],
                "content": results["documents"][0][i] if results["documents"] else "",
                "metadata": results["metadatas"][0][i] if results["metadatas"] else {},
                "distance": results["distances"][0][i] if results.get("distances") else None,
            })
        return items

    def _format_get_results(self, results) -> List[Dict[str, Any]]:
        """格式化 get 返回结果"""
        items = []
        if not results["ids"]:
            return items
        for i in range(len(results["ids"])):
            items.append({
                "id": results["ids"][i],
                "content": results["documents"][i] if results["documents"] else "",
                "metadata": results["metadatas"][i] if results["metadatas"] else {},
            })
        return items

    def count_chats(self) -> int:
        return self._chat_collection.count()

    def count_knowledge(self) -> int:
        return self._knowledge_collection.count()