"""
数据生命周期管理

状态机：active → passive (30天无人查) → archived (90天无人查) → deleted (手动)

各状态的 TTL 不同：
  - active: 价格 6h, listing 72h
  - passive: 价格 72h, listing 240h
  - archived: 不刷新，保留 365 天后清理
"""
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Set

from backend.data.database import AsyncSessionLocal
from backend.data.repositories.postgreSQL.amazon_product_repo import AmazonProductRepository
from backend.aqueduct.cost_controller import cost_controller

logger = logging.getLogger(__name__)

# 各生命周期状态的 TTL（小时）
LIFECYCLE_TTL = {
    "active": {
        "keepa": 24,           # 每天刷价格/BSR
        "rainforest": 72,      # 3 天刷 listing
        "canopy": 72,          # 3 天刷评论/销量
    },
    "passive": {
        "keepa": 168,          # 7 天刷
        "rainforest": 720,     # 30 天刷
        "canopy": 720,
    },
    "archived": {
        "keepa": None,         # 不刷新
        "rainforest": None,
        "canopy": None,
    },
}

# 生命周期转换阈值（天）
_DEMOTE_AFTER_DAYS = 30      # active → passive
_ARCHIVE_AFTER_DAYS = 90     # passive → archived
_RETENTION_DAYS = 365        # 存档保留天数


class LifecycleManager:
    """
    数据生命周期管理。
    每天检查一次，自动 demote/archive/cleanup。
    """

    def __init__(self):
        self._stats: Dict[str, int] = {}

    async def tick(self):
        """每日生命周期检查"""
        stats = {"demoted": 0, "archived": 0, "deleted": 0, "errors": 0}

        async with AsyncSessionLocal() as db:
            repo = AmazonProductRepository(db)
            now = datetime.now(timezone.utc)
            cutoff_demote = now - timedelta(days=_DEMOTE_AFTER_DAYS)
            cutoff_archive = now - timedelta(days=_ARCHIVE_AFTER_DAYS)
            cutoff_retention = now - timedelta(days=_RETENTION_DAYS)

            # 1. active → passive (30 天无人查)
            stale_active = await repo.get_products_by_lifecycle(
                status="active", last_accessed_before=cutoff_demote, limit=200,
            )
            for p in stale_active:
                try:
                    await repo.update_lifecycle(p.asin, p.domain or "US", "passive")
                    stats["demoted"] += 1
                    logger.info(f"[Lifecycle] {p.asin}@US active → passive (last_accessed={p.last_accessed_at})")
                except Exception as e:
                    logger.warning(f"[Lifecycle] demote failed {p.asin}: {e}")
                    stats["errors"] += 1

            # 2. passive → archived (90 天无人查)
            stale_passive = await repo.get_products_by_lifecycle(
                status="passive", last_accessed_before=cutoff_archive, limit=100,
            )
            for p in stale_passive:
                try:
                    await repo.update_lifecycle(p.asin, p.domain or "US", "archived")
                    stats["archived"] += 1
                    logger.info(f"[Lifecycle] {p.asin}@US passive → archived")
                except Exception as e:
                    logger.warning(f"[Lifecycle] archive failed {p.asin}: {e}")
                    stats["errors"] += 1

            # 3. archived 超过保留期 → 删除
            expired = await repo.get_products_by_lifecycle(
                status="archived", last_accessed_before=cutoff_retention, limit=50,
            )
            for p in expired:
                try:
                    await repo.delete_by_asin(p.asin, p.domain or "US")
                    stats["deleted"] += 1
                    logger.info(f"[Lifecycle] {p.asin}@US archived → deleted (retention expired)")
                except Exception as e:
                    logger.warning(f"[Lifecycle] delete failed {p.asin}: {e}")
                    stats["errors"] += 1

        self._stats = stats
        if stats["demoted"] or stats["archived"] or stats["deleted"]:
            logger.info(f"[Lifecycle] tick done: demoted={stats['demoted']}, archived={stats['archived']}, deleted={stats['deleted']}")

        return stats

    def get_ttl(self, lifecycle_status: str, source: str) -> Optional[int]:
        """获取某个生命周期状态+源的 TTL"""
        return LIFECYCLE_TTL.get(lifecycle_status, LIFECYCLE_TTL["active"]).get(source)

    def should_refresh(self, lifecycle_status: str, source: str) -> bool:
        """判断某个状态+源是否应该刷新"""
        ttl = self.get_ttl(lifecycle_status, source)
        return ttl is not None and ttl > 0


# 全局单例
lifecycle_manager = LifecycleManager()