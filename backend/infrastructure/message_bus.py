"""MessageBus — 进程内事件总线（实现 MessageBus Protocol）

当前实现：asyncio.Queue
未来可替换：Redis Streams / Kafka

用途：
- Agent 完成任务后发布事件
- 其他 Agent 订阅事件做出响应
- 解耦 Agent 之间的直接依赖
"""

import asyncio
import fnmatch
from typing import Dict, Any, Callable, List
from collections import defaultdict


class InMemoryBus:
    """基于 asyncio.Queue 的进程内事件总线"""

    def __init__(self):
        # topic -> list of (pattern, handler, queue)
        self._subscribers: Dict[str, List[tuple]] = defaultdict(list)
        self._tasks: List[asyncio.Task] = []

    async def publish(self, topic: str, event: Dict[str, Any]) -> None:
        """发布事件到主题

        Args:
            topic: 主题名，如 'agent.product_collector.completed'
            event: 事件数据字典
        """
        # 查找匹配的订阅者
        for pattern, subscribers in self._subscribers.items():
            if fnmatch.fnmatch(topic, pattern):
                for _, handler, queue in subscribers:
                    # 将事件放入队列
                    await queue.put((topic, event))

    async def subscribe(
        self,
        topic: str,
        handler: Callable[[Dict[str, Any]], Any]
    ) -> None:
        """订阅主题

        Args:
            topic: 主题名，支持通配符（如 'agent.*.completed'）
            handler: 事件处理函数，接收 event 字典
        """
        queue = asyncio.Queue()
        self._subscribers[topic].append((topic, handler, queue))

        # 启动后台任务处理事件
        task = asyncio.create_task(self._process_events(handler, queue))
        self._tasks.append(task)

    async def _process_events(
        self,
        handler: Callable,
        queue: asyncio.Queue
    ) -> None:
        """后台任务：从队列取事件并调用 handler"""
        while True:
            try:
                topic, event = await queue.get()
                # 调用处理函数（支持同步和异步）
                if asyncio.iscoroutinefunction(handler):
                    await handler(event)
                else:
                    handler(event)
            except asyncio.CancelledError:
                break
            except Exception as e:
                # 处理函数异常不应中断订阅
                print(f"[MessageBus] Handler error for topic {topic}: {e}")

    async def shutdown(self) -> None:
        """关闭事件总线，取消所有后台任务"""
        for task in self._tasks:
            task.cancel()
        await asyncio.gather(*self._tasks, return_exceptions=True)


# 全局单例
_message_bus: InMemoryBus = None


def get_message_bus() -> InMemoryBus:
    """获取全局 MessageBus 实例"""
    global _message_bus
    if _message_bus is None:
        _message_bus = InMemoryBus()
    return _message_bus


# 兼容导出：直接使用 message_bus 作为单例
message_bus = get_message_bus()
