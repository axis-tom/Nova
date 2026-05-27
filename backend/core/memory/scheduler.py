"""
记忆调度器 — 定期执行记忆整合与遗忘
运行在后台线程，定期执行：
1. consolidate(): 短期对话 → 长期知识迁移
2. forget(): 低重要性旧数据清理
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Optional

from backend.core.memory.vector_store import MemoryStore

logger = logging.getLogger(__name__)


class MemoryScheduler:
    """
    记忆调度器
    定期执行记忆整合与遗忘

    Args:
        memory: MemoryStore 实例
        consolidate_interval: 整合间隔（秒），默认 3600（1小时）
        consolidate_min_importance: 整合最低重要性，默认 6
        consolidate_max_age_days: 整合最长时效（天），默认 7
        forget_interval: 遗忘间隔（秒），默认 86400（24小时）
        forget_max_age_days: 遗忘最长时效（天），默认 30
        forget_min_importance: 遗忘保护重要性阈值（低于此值才可能遗忘），默认 3
    """

    def __init__(
        self,
        memory: Optional[MemoryStore] = None,
        consolidate_interval: int = 3600,
        consolidate_min_importance: int = 6,
        consolidate_max_age_days: int = 7,
        forget_interval: int = 86400,
        forget_max_age_days: int = 30,
        forget_min_importance: int = 3,
    ):
        self.memory = memory or MemoryStore()
        self.consolidate_interval = consolidate_interval
        self.consolidate_min_importance = consolidate_min_importance
        self.consolidate_max_age_days = consolidate_max_age_days
        self.forget_interval = forget_interval
        self.forget_max_age_days = forget_max_age_days
        self.forget_min_importance = forget_min_importance
        self._task: Optional[asyncio.Task] = None
        self._running = False

    async def start(self):
        """启动后台调度任务"""
        if self._running:
            logger.warning("MemoryScheduler already running")
            return
        self._running = True
        self._task = asyncio.create_task(self._run_loop())
        logger.info(
            "MemoryScheduler started: consolidate every %ds, forget every %ds",
            self.consolidate_interval,
            self.forget_interval,
        )

    async def stop(self):
        """停止后台调度任务"""
        if self._task:
            self._running = False
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
            logger.info("MemoryScheduler stopped")

    async def _run_loop(self):
        """主循环"""
        last_consolidate = datetime.now()
        last_forget = datetime.now()

        while self._running:
            try:
                now = datetime.now()

                # 周期性整合
                if (now - last_consolidate).total_seconds() >= self.consolidate_interval:
                    stats = self.memory.consolidate(
                        min_importance=self.consolidate_min_importance,
                        max_age_days=self.consolidate_max_age_days,
                    )
                    logger.info("Memory consolidate: %s", stats)
                    last_consolidate = now

                # 周期性遗忘
                if (now - last_forget).total_seconds() >= self.forget_interval:
                    stats = self.memory.forget(
                        max_age_days=self.forget_max_age_days,
                        min_importance=self.forget_min_importance,
                    )
                    logger.info("Memory forget: %s", stats)
                    last_forget = now

                # 等待 60 秒后再检查
                await asyncio.sleep(60)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("MemoryScheduler error: %s", e)
                await asyncio.sleep(60)

    def run_once(self) -> dict:
        """
        手动执行一次整合+遗忘（同步调用）
        适用于手动触发或测试
        Returns: 统计信息
        """
        consolidate_stats = self.memory.consolidate(
            min_importance=self.consolidate_min_importance,
            max_age_days=self.consolidate_max_age_days,
        )
        forget_stats = self.memory.forget(
            max_age_days=self.forget_max_age_days,
            min_importance=self.forget_min_importance,
        )
        return {
            "consolidate": consolidate_stats,
            "forget": forget_stats,
            "timestamp": datetime.now().isoformat(),
        }

    @property
    def is_running(self) -> bool:
        return self._running


# ── 快捷使用 ──

_scheduler: Optional[MemoryScheduler] = None


def start_scheduler(
    memory: Optional[MemoryStore] = None,
    consolidate_interval: int = 3600,
    forget_interval: int = 86400,
) -> MemoryScheduler:
    """启动全局记忆调度器"""
    global _scheduler
    if _scheduler and _scheduler.is_running:
        logger.warning("Global scheduler already running, returning existing")
        return _scheduler

    _scheduler = MemoryScheduler(
        memory=memory,
        consolidate_interval=consolidate_interval,
        forget_interval=forget_interval,
    )
    asyncio.create_task(_scheduler.start())
    return _scheduler


def stop_scheduler():
    """停止全局记忆调度器"""
    global _scheduler
    if _scheduler:
        asyncio.create_task(_scheduler.stop())
        _scheduler = None


def get_scheduler() -> Optional[MemoryScheduler]:
    """获取全局记忆调度器实例"""
    return _scheduler