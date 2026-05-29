"""
采集队列 — 去重 + 优先级 + 批控

所有采集请求通过此队列调度，确保：
  - 同一 ASIN 不会重复入队
  - 优先级：hot > active > passive
  - 批大小根据 Keepa 桶水位动态调节
"""
import asyncio
import logging
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Set

logger = logging.getLogger(__name__)


@dataclass(order=True)
class QueueItem:
    priority: int           # 越小优先级越高（0=hot, 1=active, 2=passive）
    asin: str = field(compare=False)
    domain: str = field(compare=False, default="US")
    dimensions: List[str] = field(compare=False, default_factory=list)
    cold_start: bool = field(compare=False, default=False)


class AcquisitionQueue:
    """
    采集队列，支持：
    - 优先级：hot > active > passive
    - 批大小动态调节
    - 去重：同一 ASIN 的多次请求合并为一次
    - 冷启动回调通知
    """

    def __init__(self):
        self._queue: asyncio.PriorityQueue = asyncio.PriorityQueue()
        self._pending: Set[str] = set()  # 去重集合
        self._cold_start_callbacks: List[Callable] = []

    async def enqueue(
        self,
        asin: str,
        priority: int = 1,
        domain: str = "US",
        dimensions: Optional[List[str]] = None,
        cold_start: bool = False,
    ):
        """加入采集队列（自动去重）"""
        key = f"{asin}:{domain}"
        if key in self._pending:
            logger.debug(f"[AcquisitionQueue] {key} already in queue, skipped")
            return
        self._pending.add(key)
        item = QueueItem(
            priority=priority,
            asin=asin,
            domain=domain,
            dimensions=dimensions or [],
            cold_start=cold_start,
        )
        await self._queue.put(item)
        logger.debug(f"[AcquisitionQueue] Enqueued {key} (pri={priority}, cold={cold_start})")

    async def dequeue_batch(self, max_size: int = 30) -> List[QueueItem]:
        """批量出队"""
        batch = []
        while not self._queue.empty() and len(batch) < max_size:
            try:
                item = self._queue.get_nowait()
                batch.append(item)
                key = f"{item.asin}:{item.domain}"
                self._pending.discard(key)
            except asyncio.QueueEmpty:
                break
        if batch:
            logger.info(f"[AcquisitionQueue] Dequeued {len(batch)} items")
        return batch

    @property
    def size(self) -> int:
        return self._queue.qsize()

    @property
    def pending_count(self) -> int:
        return len(self._pending)

    def batch_size_by_budget(self, tokens_left: int) -> int:
        """桶水位决定批大小"""
        if tokens_left > 50:
            return 30
        if tokens_left > 20:
            return 15
        if tokens_left > 10:
            return 5
        return 0


# 全局单例 — DataProvider 和 BudgetAwareScheduler 共享同一队列
acquisition_queue = AcquisitionQueue()