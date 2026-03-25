import json
import asyncio
from datetime import datetime
from typing import Any, Dict, Optional
from uuid import uuid4

# 为避免循环导入，使用字符串导入或直接引用
from backend.core.config import settings
from backend.core.exceptions import AuditError

class AuditLogger:
    """审计日志记录器（异步写入）"""
    def __init__(self):
        self._queue = asyncio.Queue()
        self._worker_task = None
        self._started = False

    async def start(self):
        """启动后台写入任务"""
        if self._started:
            return
        self._started = True
        self._worker_task = asyncio.create_task(self._worker())
        # 可选：注册关闭钩子
        # atexit.register(lambda: asyncio.create_task(self.stop()))

    async def stop(self):
        """停止后台任务并刷新队列"""
        if not self._started:
            return
        await self._queue.put(None)  # 哨兵
        await self._worker_task
        self._started = False

    async def _worker(self):
        """后台写入循环"""
        while True:
            item = await self._queue.get()
            if item is None:
                break
            try:
                await self._write_to_storage(item)
            except Exception as e:
                # 记录错误但不中断
                print(f"Audit write failed: {e}")

    async def _write_to_storage(self, entry: Dict[str, Any]):
        """实际写入存储（可替换为数据库/文件）"""
        # 示例：写入文件
        if settings.LOG_FILE:
            with open(settings.LOG_FILE, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, default=str) + "\n")
        # 也可通过 HTTP 发送到集中日志服务

    async def log(
        self,
        user_id: int,
        action: str,
        details: Optional[Dict] = None,
        status: str = "success",
        error_msg: Optional[str] = None,
        trace_id: Optional[str] = None,
    ):
        """记录一条审计日志"""
        if not self._started:
            await self.start()

        entry = {
            "id": str(uuid4()),
            "user_id": user_id,
            "action": action,
            "details": details or {},
            "status": status,
            "error_msg": error_msg,
            "timestamp": datetime.utcnow().isoformat(),
            "trace_id": trace_id or "",
        }
        await self._queue.put(entry)

# 全局单例
audit_logger = AuditLogger()