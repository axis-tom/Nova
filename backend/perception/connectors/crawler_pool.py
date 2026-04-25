import asyncio
import random
from typing import List, Dict, Any, Optional

class CrawlerPool:
    """云端爬虫池管理"""
    def __init__(self, proxy_list: List[str] = None):
        self.proxy_list = proxy_list or []
        self.active_tasks = {}
        self.task_queue = asyncio.Queue()

    async def add_task(self, url: str, callback: callable, **kwargs):
        """添加爬取任务"""
        await self.task_queue.put((url, callback, kwargs))

    async def start_workers(self, worker_count: int = 3):
        """启动工作协程"""
        workers = [asyncio.create_task(self._worker(i)) for i in range(worker_count)]
        await asyncio.gather(*workers)

    async def _worker(self, worker_id: int):
        """工作协程，从队列取任务并执行"""
        while True:
            url, callback, kwargs = await self.task_queue.get()
            # 随机选择一个代理（如有）
            proxy = random.choice(self.proxy_list) if self.proxy_list else None
            try:
                result = await self._fetch(url, proxy)
                await callback(result, **kwargs)
            except Exception as e:
                # 错误处理，可以重试或记录
                print(f"Worker {worker_id} failed for {url}: {e}")
            finally:
                self.task_queue.task_done()

    async def _fetch(self, url: str, proxy: Optional[str]) -> str:
        """执行 HTTP 请求（使用 aiohttp）"""
        import aiohttp
        async with aiohttp.ClientSession() as session:
            proxy_url = f"http://{proxy}" if proxy else None
            async with session.get(url, proxy=proxy_url) as response:
                return await response.text()

# 全局爬虫池实例（需在应用启动时初始化）
crawler_pool = CrawlerPool()