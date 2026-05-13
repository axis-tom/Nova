"""
Execution Queue - 执行队列
管理图节点的执行顺序和并发控制
"""

from typing import Dict, Any, List, Optional, Callable
from collections import deque
import asyncio
import time
from dataclasses import dataclass, field


@dataclass
class QueueItem:
    """队列项"""
    node_id: str
    agent_name: str
    config: Dict[str, Any] = field(default_factory=dict)
    priority: int = 0
    dependencies: List[str] = field(default_factory=list)
    status: str = "pending"  # pending, running, completed, failed
    result: Any = None
    error: Optional[str] = None
    start_time: Optional[float] = None
    end_time: Optional[float] = None


class ExecutionQueue:
    """
    执行队列
    
    管理图节点的执行顺序，支持：
    1. 优先级队列
    2. 依赖关系管理
    3. 并发控制
    4. 超时处理
    """
    
    def __init__(self, max_concurrent: int = 5):
        self.max_concurrent = max_concurrent
        self.queue = deque()
        self.running = {}
        self.completed = {}
        self.failed = {}
        self.dependencies = {}
        self._running_count = 0
    
    def enqueue(self, item: QueueItem):
        """添加节点到队列"""
        self.queue.append(item)
        self.dependencies[item.node_id] = set(item.dependencies)
    
    def enqueue_batch(self, items: List[QueueItem]):
        """批量添加节点"""
        for item in items:
            self.enqueue(item)
    
    def dequeue(self) -> Optional[QueueItem]:
        """从队列中取出下一个可执行的节点"""
        # 按优先级排序
        sorted_items = sorted(self.queue, key=lambda x: (-x.priority, x.node_id))
        
        for item in sorted_items:
            # 检查依赖是否都已满足
            if self._dependencies_met(item):
                self.queue.remove(item)
                return item
        
        return None
    
    def _dependencies_met(self, item: QueueItem) -> bool:
        """检查依赖是否都已满足"""
        deps = self.dependencies.get(item.node_id, set())
        for dep in deps:
            if dep not in self.completed:
                return False
        return True
    
    async def execute(self, executor: Callable, timeout: int = 300):
        """
        执行队列中的节点
        
        Args:
            executor: 执行函数，接收QueueItem参数
            timeout: 单个节点超时时间（秒）
        """
        while self.queue or self.running:
            # 检查是否可以启动新节点
            while self._running_count < self.max_concurrent:
                item = self.dequeue()
                if not item:
                    break
                
                self._running_count += 1
                item.status = "running"
                item.start_time = time.time()
                self.running[item.node_id] = item
                
                # 启动执行
                asyncio.create_task(self._execute_item(item, executor, timeout))
            
            if self._running_count == 0 and not self.queue:
                break
            
            # 等待一段时间再检查
            await asyncio.sleep(0.1)
    
    async def _execute_item(self, item: QueueItem, executor: Callable, timeout: int):
        """执行单个节点"""
        try:
            result = await asyncio.wait_for(executor(item), timeout=timeout)
            item.status = "completed"
            item.result = result
            item.end_time = time.time()
            self.completed[item.node_id] = item
        except asyncio.TimeoutError:
            item.status = "failed"
            item.error = f"Timeout after {timeout}s"
            item.end_time = time.time()
            self.failed[item.node_id] = item
        except Exception as e:
            item.status = "failed"
            item.error = str(e)
            item.end_time = time.time()
            self.failed[item.node_id] = item
        finally:
            self._running_count -= 1
            if item.node_id in self.running:
                del self.running[item.node_id]
    
    def get_status(self) -> Dict[str, Any]:
        """获取队列状态"""
        return {
            "queue_size": len(self.queue),
            "running_count": self._running_count,
            "completed_count": len(self.completed),
            "failed_count": len(self.failed),
            "running": list(self.running.keys()),
            "completed": list(self.completed.keys()),
            "failed": list(self.failed.keys())
        }
    
    def clear(self):
        """清空队列"""
        self.queue.clear()
        self.running.clear()
        self.completed.clear()
        self.failed.clear()
        self.dependencies.clear()
        self._running_count = 0
