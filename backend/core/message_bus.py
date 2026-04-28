import json
import asyncio
from typing import Callable, Awaitable, Any, Dict, Optional
import redis.asyncio as redis
from backend.core.config import settings
from backend.core.exceptions import MessageBusError

class MessageBus:
    """基于Redis的异步消息总线，支持发布/订阅模式"""
    def __init__(self):
        self._pub = None
        self._sub = None
        self._handlers: Dict[str, Callable[[Dict], Awaitable[None]]] = {}
        self._listener_task = None
        self._running = False

    async def connect(self):
        """建立Redis连接"""
        try:
            self._pub = await redis.from_url(
                f"redis://{settings.REDIS_HOST}:{settings.REDIS_PORT}/{settings.REDIS_DB}",
                password=settings.REDIS_PASSWORD,
                decode_responses=True,
            )
            self._sub = await redis.from_url(
                f"redis://{settings.REDIS_HOST}:{settings.REDIS_PORT}/{settings.REDIS_DB}",
                password=settings.REDIS_PASSWORD,
                decode_responses=True,
            )
        except Exception as e:
            raise MessageBusError(f"Failed to connect to Redis: {e}")

    async def close(self):
        """关闭连接"""
        if self._running:
            self._running = False
            if self._listener_task:
                self._listener_task.cancel()
                try:
                    await self._listener_task
                except asyncio.CancelledError:
                    pass
        if self._pub:
            await self._pub.close()
        if self._sub:
            await self._sub.close()

    async def publish(self, channel: str, message: Dict[str, Any]):
        """发布消息到指定频道"""
        if not self._pub:
            await self.connect()
        try:
            await self._pub.publish(channel, json.dumps(message))
        except Exception as e:
            raise MessageBusError(f"Publish failed: {e}")

    async def subscribe(self, channel: str, handler: Callable[[Dict], Awaitable[None]]):
        """订阅频道，并注册消息处理器"""
        self._handlers[channel] = handler
        if not self._running:
            await self._start_listener()

    async def _start_listener(self):
        """启动后台监听"""
        self._running = True
        self._listener_task = asyncio.create_task(self._listen())

    async def _listen(self):
        """监听所有已订阅的频道"""
        if not self._sub:
            await self.connect()
        # 订阅所有需要的频道
        channels = list(self._handlers.keys())
        if not channels:
            return
        psub = self._sub.pubsub()
        await psub.subscribe(*channels)
        async for message in psub.listen():
            if message["type"] == "message":
                channel = message["channel"]
                handler = self._handlers.get(channel)
                if handler:
                    try:
                        data = json.loads(message["data"])
                        # 异步执行处理器，不阻塞监听
                        asyncio.create_task(handler(data))
                    except Exception as e:
                        # 记录错误但不崩溃
                        print(f"Message handler error on {channel}: {e}")

# 全局消息总线实例
message_bus = MessageBus()