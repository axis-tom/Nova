"""
记忆存储工具 — 增强版
基于 ChromaDB 的向量存储 + 语义检索
零配置，本地运行，数据持久化

架构：
  chat_history    ← 对话历史（短期）
  knowledge_cache ← 知识缓存（长期）
  agent_memory    ← Agent 记忆（持久化业务记忆）

增强功能：
  - 跨 collection 统一搜索 + 时间衰减评分
  - 重要性评分（importance 1-10）
  - 标签分类（tags）
  - TTL 自动清理（按 collection 配置）
  - 短期 → 长期整合（consolidate）
  - 时间衰减遗忘（forget）
  - 记忆统计
"""

from typing import List, Dict, Optional, Any
import chromadb
from chromadb.config import Settings
import uuid
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)

# ── TTL 配置（天） ──
TTL_CONFIG = {
    "chat_history": 7,       # 7 天
    "knowledge_cache": 90,   # 90 天
    "agent_memory": 30,      # 30 天
}

# ── 检索评分权重 ──
WEIGHT_SEMANTIC = 0.6
WEIGHT_RECENCY = 0.3
WEIGHT_IMPORTANCE = 0.1
RECENCY_DECAY_DAYS = 30  # 超过此天数 recency_score = 0


class MemoryStore:
    """
    增强版记忆存储
    管理对话历史、知识缓存、Agent 记忆
    """

    def __init__(self, persist_dir: str = "./nova_memory"):
        self.client = chromadb.PersistentClient(
            path=persist_dir,
            settings=Settings(anonymized_telemetry=False),
        )
        # 三个 collection
        self._chat_collection = self._get_or_create("chat_history")
        self._knowledge_collection = self._get_or_create("knowledge_cache")
        self._agent_collection = self._get_or_create("agent_memory")

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
                "importance": 5,  # 默认中等
                "tags": "chat",
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

    def save_knowledge(self, key: str, content: str, source: str = "",
                       importance: int = 5, tags: str = "",
                       metadata: Optional[Dict] = None) -> str:
        """保存知识片段（搜索结果、Agent 输出等）

        Args:
            key: 知识键
            content: 知识内容
            source: 来源
            importance: 重要性 1-10
            tags: 逗号分隔的标签
            metadata: 额外元数据
        """
        doc_id = str(uuid.uuid4())
        self._knowledge_collection.add(
            documents=[content],
            metadatas=[{
                "key": key,
                "source": source,
                "importance": importance,
                "tags": tags,
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

    # ── Agent 记忆 ──

    def save_memory(self, content: str, importance: int = 5, tags: str = "",
                    source: str = "", metadata: Optional[Dict] = None) -> str:
        """保存 Agent 记忆

        Args:
            content: 记忆内容
            importance: 重要性 1-10（10=最关键）
            tags: 逗号分隔的标签，如 "amazon,product_analysis,competitor"
            source: 来源（agent 名称等）
            metadata: 额外元数据
        """
        mem_id = str(uuid.uuid4())
        self._agent_collection.add(
            documents=[content],
            metadatas=[{
                "type": "agent_memory",
                "importance": importance,
                "tags": tags,
                "source": source,
                "timestamp": datetime.now().isoformat(),
                **(metadata or {}),
            }],
            ids=[mem_id],
        )
        return mem_id

    def search_memory(self, query: str, k: int = 5,
                      min_importance: int = 0,
                      tags_filter: Optional[str] = None) -> List[Dict[str, Any]]:
        """搜索 Agent 记忆

        Args:
            query: 搜索查询
            k: 返回数量
            min_importance: 最低重要性过滤
            tags_filter: 标签过滤（逗号分隔，匹配任一即可）
        """
        where_clause = {}
        if min_importance > 0:
            where_clause["importance"] = {"$gte": min_importance}
        if tags_filter:
            # ChromaDB 不支持 OR 查询，用 $contains 匹配单个标签
            # 这里简化处理：只取第一个标签
            tag = tags_filter.split(",")[0].strip()
            if tag:
                where_clause["tags"] = {"$contains": tag}

        if where_clause:
            results = self._agent_collection.query(
                query_texts=[query], n_results=k, where=where_clause
            )
        else:
            results = self._agent_collection.query(query_texts=[query], n_results=k)
        return self._format_results(results)

    def get_high_importance_memories(self, min_importance: int = 7, k: int = 10) -> List[Dict[str, Any]]:
        """获取高重要性记忆"""
        results = self._agent_collection.get(
            where={"importance": {"$gte": min_importance}},
            limit=k,
        )
        return self._format_get_results(results)

    # ── 跨 collection 统一搜索（时间衰减评分） ──

    @staticmethod
    def _compute_ranked_score(item: Dict[str, Any]) -> float:
        """综合评分 = 语义相似度 * 0.6 + 时间新鲜度 * 0.3 + 重要性 * 0.1"""
        # 语义相似度：ChromaDB distance 越小越好，转为 0-1 分数
        distance = item.get("distance") or 1.0
        semantic_score = max(0.0, 1.0 - distance)

        # 时间新鲜度
        recency_score = 0.0
        ts = item.get("metadata", {}).get("timestamp", "")
        if ts:
            try:
                dt = datetime.fromisoformat(ts)
                age_days = (datetime.now() - dt).total_seconds() / 86400
                recency_score = max(0.0, 1.0 - age_days / RECENCY_DECAY_DAYS)
            except (ValueError, TypeError):
                pass

        # 重要性：归一化到 0-1
        importance = int(item.get("metadata", {}).get("importance", 5))
        importance_score = min(importance / 10.0, 1.0)

        return (
            WEIGHT_SEMANTIC * semantic_score
            + WEIGHT_RECENCY * recency_score
            + WEIGHT_IMPORTANCE * importance_score
        )

    def search_all(self, query: str, k: int = 3) -> List[Dict[str, Any]]:
        """跨所有 collection 统一语义搜索（时间衰减 + 重要性加权排序）"""
        results = []
        # 搜索对话
        chat_results = self._chat_collection.query(query_texts=[query], n_results=k)
        results.extend(self._format_results(chat_results))
        # 搜索知识
        knowledge_results = self._knowledge_collection.query(query_texts=[query], n_results=k)
        results.extend(self._format_results(knowledge_results))
        # 搜索 Agent 记忆
        agent_results = self._agent_collection.query(query_texts=[query], n_results=k)
        results.extend(self._format_results(agent_results))
        # 按综合评分排序（高 → 低）
        for item in results:
            item["_ranked_score"] = self._compute_ranked_score(item)
        results.sort(key=lambda x: x["_ranked_score"], reverse=True)
        return results[:k]

    # ── 记忆整合（短期 → 长期） ──

    def consolidate(self, min_importance: int = 6, max_age_days: int = 7) -> Dict[str, int]:
        """将高重要性对话历史整合到知识缓存

        策略：
        - 从 chat_history 中找 importance >= min_importance 且 age <= max_age_days 的条目
        - 复制到 knowledge_cache
        - 标记原条目为已整合

        Returns:
            统计信息
        """
        stats = {"consolidated": 0, "skipped": 0, "errors": 0}

        try:
            # 获取所有 chat_history 条目
            all_chats = self._chat_collection.get()
            if not all_chats["ids"]:
                return stats

            cutoff = datetime.now() - timedelta(days=max_age_days)

            for i in range(len(all_chats["ids"])):
                try:
                    meta = all_chats["metadatas"][i] if all_chats["metadatas"] else {}
                    doc = all_chats["documents"][i] if all_chats["documents"] else ""

                    # 检查是否已整合
                    if meta.get("consolidated") == "true":
                        stats["skipped"] += 1
                        continue

                    # 检查重要性
                    imp = int(meta.get("importance", 0))
                    if imp < min_importance:
                        stats["skipped"] += 1
                        continue

                    # 检查时效
                    ts = meta.get("timestamp", "")
                    if ts:
                        try:
                            dt = datetime.fromisoformat(ts)
                            if dt < cutoff:
                                stats["skipped"] += 1
                                continue
                        except ValueError:
                            pass

                    # 复制到 knowledge_cache
                    self._knowledge_collection.add(
                        documents=[doc],
                        metadatas=[{
                            "key": f"consolidated_chat_{all_chats['ids'][i]}",
                            "source": meta.get("source", "chat_consolidation"),
                            "importance": imp,
                            "tags": meta.get("tags", "consolidated"),
                            "timestamp": datetime.now().isoformat(),
                            "original_id": all_chats["ids"][i],
                            "consolidated_from": "chat_history",
                        }],
                        ids=[f"consolidated_{all_chats['ids'][i]}"],
                    )

                    # 标记原条目
                    self._chat_collection.update(
                        ids=[all_chats["ids"][i]],
                        metadatas=[{**meta, "consolidated": "true"}],
                    )

                    stats["consolidated"] += 1

                except Exception as e:
                    logger.warning(f"consolidate item {i} failed: {e}")
                    stats["errors"] += 1

        except Exception as e:
            logger.error(f"consolidate failed: {e}")
            stats["errors"] += 1

        return stats

    # ── 记忆遗忘（TTL 驱动） ──

    def forget(self, min_importance: int = 3) -> Dict[str, int]:
        """按 TTL_CONFIG 清理过期低价值记忆

        策略：
        - 每个 collection 按各自 TTL 判断是否过期
        - 过期且 importance < min_importance 的条目删除
        - chat_history 也纳入清理（TTL 7 天）

        Returns:
            统计信息
        """
        stats = {"chat_deleted": 0, "knowledge_deleted": 0, "agent_deleted": 0, "errors": 0}

        for collection_name, collection, stats_key in [
            ("chat_history", self._chat_collection, "chat_deleted"),
            ("knowledge_cache", self._knowledge_collection, "knowledge_deleted"),
            ("agent_memory", self._agent_collection, "agent_deleted"),
        ]:
            ttl_days = TTL_CONFIG.get(collection_name, 30)
            cutoff = datetime.now() - timedelta(days=ttl_days)

            try:
                all_items = collection.get()
                if not all_items["ids"]:
                    continue

                to_delete = []
                for i in range(len(all_items["ids"])):
                    try:
                        meta = all_items["metadatas"][i] if all_items["metadatas"] else {}
                        imp = int(meta.get("importance", 0))
                        ts = meta.get("timestamp", "")

                        if imp >= min_importance:
                            continue

                        if ts:
                            try:
                                dt = datetime.fromisoformat(ts)
                                if dt > cutoff:
                                    continue
                            except ValueError:
                                pass

                        to_delete.append(all_items["ids"][i])

                    except Exception as e:
                        logger.warning(f"forget check item {i} in {collection_name} failed: {e}")
                        stats["errors"] += 1

                if to_delete:
                    batch_size = 100
                    for batch_start in range(0, len(to_delete), batch_size):
                        batch = to_delete[batch_start:batch_start + batch_size]
                        collection.delete(ids=batch)
                    stats[stats_key] = len(to_delete)

            except Exception as e:
                logger.error(f"forget collection {collection_name} failed: {e}")
                stats["errors"] += 1

        return stats

    # ── 全量清理（启动时调用） ──

    def cleanup_all(self) -> Dict[str, Any]:
        """执行全量清理：TTL 遗忘 + 高重要性整合 + SQLite 过期会话清理

        适合在应用启动时调用一次。

        Returns:
            各阶段统计
        """
        results = {}

        # 1. TTL 遗忘
        results["forget"] = self.forget()
        logger.info(f"[MemoryStore] cleanup forget: {results['forget']}")

        # 2. 高重要性 chat → knowledge
        results["consolidate"] = self.consolidate()
        logger.info(f"[MemoryStore] cleanup consolidate: {results['consolidate']}")

        # 3. SQLite 过期会话
        try:
            from backend.core.memory.durable import get_durable_session
            durable = get_durable_session()
            expired_count = durable._cleanup_expired_sync(max_age_days=30)
            results["sqlite_expired"] = expired_count
        except Exception as e:
            logger.warning(f"[MemoryStore] SQLite cleanup failed: {e}")
            results["sqlite_expired"] = 0

        logger.info(f"[MemoryStore] cleanup_all complete: {results}")
        return results

    # ── 记忆统计 ──

    def get_stats(self) -> Dict[str, Any]:
        """获取记忆系统统计"""
        return {
            "chat_count": self._chat_collection.count(),
            "knowledge_count": self._knowledge_collection.count(),
            "agent_memory_count": self._agent_collection.count(),
            "total": self._chat_collection.count()
                     + self._knowledge_collection.count()
                     + self._agent_collection.count(),
        }

    # ── 格式化 ──

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

    def count_agent_memories(self) -> int:
        return self._agent_collection.count()