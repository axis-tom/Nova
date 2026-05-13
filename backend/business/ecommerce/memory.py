"""
Memory Agent - 长期记忆Agent
负责存储和检索历史执行记录、学习经验
"""

from typing import Dict, Any, List, Optional
from backend.common.core.state import State
from backend.business.ecommerce.base import BaseEcommerceAgent
import json
import time
import hashlib
from datetime import datetime, timedelta


class MemoryAgent(BaseEcommerceAgent):
    """
    Memory Agent - 长期记忆Agent
    
    职责：
    1. 存储执行记录和历史数据
    2. 检索相关历史经验
    3. 学习模式和经验总结
    4. 提供基于历史的建议
    """
    
    def __init__(self, storage_path: str = None):
        """
        初始化Memory Agent
        
        Args:
            storage_path: 存储路径（可选）
        """
        super().__init__(
            name="ecommerce_memory",
            description="电商长期记忆Agent，负责存储和检索历史执行记录、学习经验"
        )
        
        # 设置存储路径
        self.storage_path = storage_path or "/tmp/ecommerce_memory.json"
        
        # 初始化内存存储
        self.memory_store = self._load_memory_store()
        
        # 内存索引
        self.memory_index = self._build_memory_index()
    
    def run(self, state: State) -> State:
        """
        执行Memory Agent逻辑
        
        Args:
            state: 输入状态
            
        Returns:
            输出状态
        """
        # 记录开始事件
        state = self.log_event(state, "start", "开始执行记忆操作")
        
        try:
            # 验证输入
            if not self.validate_input(state):
                state = self.log_event(state, "error", "输入验证失败")
                state["memory_error"] = "输入数据不完整"
                state = self.add_execution_record(state, False, {"error": "输入验证失败"})
                return state
            
            # 提取记忆操作
            memory_operation = state.get("memory_operation", {})
            data = state.get("data", {})
            context = state.get("context", {})
            
            # 根据操作类型执行记忆操作
            operation_type = memory_operation.get("type", "unknown")
            
            if operation_type == "store":
                result = self._store_memory(data, context)
            elif operation_type == "retrieve":
                result = self._retrieve_memory(data, context)
            elif operation_type == "analyze":
                result = self._analyze_memory(data, context)
            elif operation_type == "learn":
                result = self._learn_from_memory(data, context)
            else:
                result = self._general_memory_operation(data, context)
            
            # 更新状态
            state["memory_result"] = result
            state["memory_executed"] = True
            
            # 记录成功事件
            state = self.log_event(state, "success", f"成功完成{operation_type}记忆操作")
            state = self.add_execution_record(state, True, {
                "operation_type": operation_type,
                "memory_entries": result.get("entries_affected", 0),
                "store_size": len(self.memory_store)
            })
            
        except Exception as e:
            # 记录错误事件
            state = self.log_event(state, "error", f"记忆操作失败: {str(e)}")
            state["memory_error"] = str(e)
            state["memory_executed"] = False
            state = self.add_execution_record(state, False, {"error": str(e)})
        
        return state
    
    def get_required_fields(self) -> list:
        """
        获取必需的输入字段
        
        Returns:
            必需字段列表
        """
        return ["memory_operation"]
    
    def get_output_fields(self) -> list:
        """
        获取输出的字段
        
        Returns:
            输出字段列表
        """
        return ["memory_result", "memory_executed", "memory_error"]
    
    def _load_memory_store(self) -> Dict[str, Any]:
        """
        加载内存存储
        
        Returns:
            内存存储数据
        """
        try:
            with open(self.storage_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            # 如果文件不存在或格式错误，返回空存储
            return {
                "version": "1.0",
                "created_at": time.time(),
                "last_updated": time.time(),
                "memory_entries": [],
                "statistics": {
                    "total_entries": 0,
                    "successful_entries": 0,
                    "failed_entries": 0,
                    "average_execution_time": 0
                }
            }
    
    def _save_memory_store(self) -> None:
        """
        保存内存存储到文件
        """
        # 更新最后修改时间
        self.memory_store["last_updated"] = time.time()
        
        # 保存到文件
        with open(self.storage_path, 'w', encoding='utf-8') as f:
            json.dump(self.memory_store, f, ensure_ascii=False, indent=2)
    
    def _build_memory_index(self) -> Dict[str, List[str]]:
        """
        构建内存索引
        
        Returns:
            内存索引
        """
        index = {
            "by_agent": {},
            "by_operation": {},
            "by_status": {},
            "by_timestamp": {},
            "by_tags": {}
        }
        
        memory_entries = self.memory_store.get("memory_entries", [])
        
        for entry in memory_entries:
            entry_id = entry.get("id", "")
            
            # 按Agent索引
            agent = entry.get("agent", "unknown")
            if agent not in index["by_agent"]:
                index["by_agent"][agent] = []
            index["by_agent"][agent].append(entry_id)
            
            # 按操作类型索引
            operation = entry.get("operation", "unknown")
            if operation not in index["by_operation"]:
                index["by_operation"][operation] = []
            index["by_operation"][operation].append(entry_id)
            
            # 按状态索引
            status = entry.get("status", "unknown")
            if status not in index["by_status"]:
                index["by_status"][status] = []
            index["by_status"][status].append(entry_id)
            
            # 按时间戳索引（按天）
            timestamp = entry.get("timestamp", 0)
            date_str = datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d")
            if date_str not in index["by_timestamp"]:
                index["by_timestamp"][date_str] = []
            index["by_timestamp"][date_str].append(entry_id)
            
            # 按标签索引
            tags = entry.get("tags", [])
            for tag in tags:
                if tag not in index["by_tags"]:
                    index["by_tags"][tag] = []
                index["by_tags"][tag].append(entry_id)
        
        return index
    
    def _generate_entry_id(self, data: Dict[str, Any]) -> str:
        """
        生成记忆条目ID
        
        Args:
            data: 记忆数据
            
        Returns:
            条目ID
        """
        # 使用数据哈希生成唯一ID
        data_str = json.dumps(data, sort_keys=True)
        hash_obj = hashlib.md5(data_str.encode())
        return f"mem_{hash_obj.hexdigest()[:12]}_{int(time.time())}"
    
    def _store_memory(self, data: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """
        存储记忆
        
        Args:
            data: 要存储的数据
            context: 上下文信息
            
        Returns:
            存储结果
        """
        # 生成记忆条目
        memory_entry = {
            "id": self._generate_entry_id(data),
            "timestamp": time.time(),
            "agent": context.get("agent", "unknown"),
            "operation": context.get("operation", "store"),
            "status": "stored",
            "data": data,
            "metadata": {
                "context": context,
                "storage_timestamp": time.time(),
                "storage_agent": self.name
            },
            "tags": context.get("tags", []),
            "importance": context.get("importance", 1)  # 1-10，重要性评分
        }
        
        # 添加到内存存储
        if "memory_entries" not in self.memory_store:
            self.memory_store["memory_entries"] = []
        
        self.memory_store["memory_entries"].append(memory_entry)
        
        # 更新统计信息
        self._update_statistics(memory_entry)
        
        # 重建索引
        self.memory_index = self._build_memory_index()
        
        # 保存到文件
        self._save_memory_store()
        
        return {
            "success": True,
            "entry_id": memory_entry["id"],
            "timestamp": memory_entry["timestamp"],
            "entries_affected": 1,
            "total_entries": len(self.memory_store["memory_entries"]),
            "message": "记忆存储成功"
        }
    
    def _update_statistics(self, entry: Dict[str, Any]) -> None:
        """
        更新统计信息
        
        Args:
            entry: 记忆条目
        """
        stats = self.memory_store.get("statistics", {})
        
        # 更新总条目数
        stats["total_entries"] = len(self.memory_store.get("memory_entries", []))
        
        # 更新成功/失败计数
        if entry.get("status") == "success":
            stats["successful_entries"] = stats.get("successful_entries", 0) + 1
        elif entry.get("status") == "failed":
            stats["failed_entries"] = stats.get("failed_entries", 0) + 1
        
        # 更新平均执行时间
        execution_time = entry.get("data", {}).get("execution_time", 0)
        if execution_time > 0:
            current_avg = stats.get("average_execution_time", 0)
            total_entries = stats.get("total_entries", 1)
            new_avg = (current_avg * (total_entries - 1) + execution_time) / total_entries
            stats["average_execution_time"] = new_avg
        
        self.memory_store["statistics"] = stats
    
    def _retrieve_memory(self, query: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """
        检索记忆
        
        Args:
            query: 查询条件
            context: 上下文信息
            
        Returns:
            检索结果
        """
        # 提取查询参数
        query_type = query.get("type", "similar")
        limit = query.get("limit", 10)
        filters = query.get("filters", {})
        
        # 获取所有记忆条目
        memory_entries = self.memory_store.get("memory_entries", [])
        
        # 应用过滤器
        filtered_entries = self._apply_filters(memory_entries, filters)
        
        # 根据查询类型排序
        if query_type == "recent":
            # 按时间倒序
            filtered_entries.sort(key=lambda x: x.get("timestamp", 0), reverse=True)
        elif query_type == "similar":
            # 按相似度排序（简单实现）
            query_data = query.get("data", {})
            filtered_entries = self._sort_by_similarity(filtered_entries, query_data)
        elif query_type == "important":
            # 按重要性排序
            filtered_entries.sort(key=lambda x: x.get("importance", 1), reverse=True)
        
        # 限制返回数量
        result_entries = filtered_entries[:limit]
        
        # 提取关键信息
        extracted_info = self._extract_key_information(result_entries, context)
        
        return {
            "success": True,
            "entries_found": len(result_entries),
            "total_entries": len(memory_entries),
            "entries": result_entries,
            "extracted_info": extracted_info,
            "query": query,
            "timestamp": time.time()
        }
    
    def _apply_filters(self, entries: List[Dict[str, Any]], filters: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        应用过滤器
        
        Args:
            entries: 记忆条目列表
            filters: 过滤器
            
        Returns:
            过滤后的条目列表
        """
        filtered_entries = entries
        
        # 按Agent过滤
        if "agent" in filters:
            agent_filter = filters["agent"]
            if isinstance(agent_filter, str):
                filtered_entries = [e for e in filtered_entries if e.get("agent") == agent_filter]
            elif isinstance(agent_filter, list):
                filtered_entries = [e for e in filtered_entries if e.get("agent") in agent_filter]
        
        # 按操作类型过滤
        if "operation" in filters:
            operation_filter = filters["operation"]
            if isinstance(operation_filter, str):
                filtered_entries = [e for e in filtered_entries if e.get("operation") == operation_filter]
            elif isinstance(operation_filter, list):
                filtered_entries = [e for e in filtered_entries if e.get("operation") in operation_filter]
        
        # 按状态过滤
        if "status" in filters:
            status_filter = filters["status"]
            if isinstance(status_filter, str):
                filtered_entries = [e for e in filtered_entries if e.get("status") == status_filter]
            elif isinstance(status_filter, list):
                filtered_entries = [e for e in filtered_entries if e.get("status") in status_filter]
        
        # 按时间范围过滤
        if "time_range" in filters:
            time_range = filters["time_range"]
            start_time = time_range.get("start", 0)
            end_time = time_range.get("end", time.time())
            filtered_entries = [
                e for e in filtered_entries 
                if start_time <= e.get("timestamp", 0) <= end_time
            ]
        
        # 按标签过滤
        if "tags" in filters:
            tags_filter = filters["tags"]
            if isinstance(tags_filter, str):
                filtered_entries = [e for e in filtered_entries if tags_filter in e.get("tags", [])]
            elif isinstance(tags_filter, list):
                filtered_entries = [
                    e for e in filtered_entries 
                    if any(tag in e.get("tags", []) for tag in tags_filter)
                ]
        
        # 按重要性过滤
        if "min_importance" in filters:
            min_importance = filters["min_importance"]
            filtered_entries = [
                e for e in filtered_entries 
                if e.get("importance", 1) >= min_importance
            ]
        
        return filtered_entries
    
    def _sort_by_similarity(self, entries: List[Dict[str, Any]], query_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        按相似度排序
        
        Args:
            entries: 记忆条目列表
            query_data: 查询数据
            
        Returns:
            按相似度排序的条目列表
        """
        # 简单相似度计算：基于数据字段匹配
        scored_entries = []
        
        for entry in entries:
            entry_data = entry.get("data", {})
            similarity_score = self._calculate_similarity(entry_data, query_data)
            
            scored_entries.append({
                "entry": entry,
                "similarity_score": similarity_score
            })
        
        # 按相似度降序排序
        scored_entries.sort(key=lambda x: x["similarity_score"], reverse=True)
        
        # 返回原始条目
        return [item["entry"] for item in scored_entries]
    
    def _calculate_similarity(self, data1: Dict[str, Any], data2: Dict[str, Any]) -> float:
        """
        计算数据相似度
        
        Args:
            data1: 数据1
            data2: 数据2
            
        Returns:
            相似度分数 (0-1)
        """
        if not data1 or not data2:
            return 0.0
        
        # 计算共同键的数量
        keys1 = set(data1.keys())
        keys2 = set(data2.keys())
        common_keys = keys1.intersection(keys2)
        
        if not common_keys:
            return 0.0
        
        # 计算值相似度
        total_similarity = 0.0
        
        for key in common_keys:
            value1 = data1[key]
            value2 = data2[key]
            
            if isinstance(value1, (int, float)) and isinstance(value2, (int, float)):
                # 数值相似度
                if value1 == 0 and value2 == 0:
                    similarity = 1.0
                else:
                    similarity = 1.0 - abs(value1 - value2) / max(abs(value1), abs(value2), 1)
            elif isinstance(value1, str) and isinstance(value2, str):
                # 字符串相似度（简单实现）
                if value1 == value2:
                    similarity = 1.0
                else:
                    # 计算共同字符比例
                    common_chars = set(value1).intersection(set(value2))
                    similarity = len(common_chars) / max(len(value1), len(value2), 1)
            elif isinstance(value1, dict) and isinstance(value2, dict):
                # 递归计算字典相似度
                similarity = self._calculate_similarity(value1, value2)
            else:
                # 类型不同，相似度为0
                similarity = 0.0
            
            total_similarity += similarity
        
        # 平均相似度
        return total_similarity / len(common_keys)
    
    def _extract_key_information(self, entries: List[Dict[str, Any]], context: Dict[str, Any]) -> Dict[str, Any]:
        """
        提取关键信息
        
        Args:
            entries: 记忆条目列表
            context: 上下文信息
            
        Returns:
            提取的关键信息
        """
        if not entries:
            return {"message": "没有可提取的信息"}
        
        # 统计信息
        total_entries = len(entries)
        successful