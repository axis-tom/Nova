"""
数据调度层统一入口 — Agent 唯一的数据来源

Agent 通过此 Provider 读取数据，不直接访问任何 API 连接器。
内部路由：
  amazon_products 表里有且新鲜 → 直接返回（附可信度标记）
  表里有但过期 → enqueue 异步刷新 → 返回现有数据
  表里没有 → ETL Pipeline 冷启动（4 阶段递进）→ 返回
"""
import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from backend.data.database import AsyncSessionLocal
from backend.data.repositories.postgreSQL.amazon_product_repo import AmazonProductRepository
from backend.aqueduct.acquisition_queue import AcquisitionQueue
from backend.aqueduct.etl_pipeline import ETLPipeline
from backend.aqueduct.quality_scorer import enrich_with_trust

logger = logging.getLogger(__name__)

# 各维度新鲜度阈值（小时）
_FRESHNESS_TTL = {
    "has_price": 6,
    "has_buybox": 6,
    "has_price_stats": 12,
    "has_bsr": 6,
    "has_bsr_stats": 12,
    "has_rating_history": 24,
    "has_listing": 72,
    "has_aplus": 168,
    "has_videos": 168,
    "has_reviews_body": 24,
    "has_rating_breakdown": 72,
    "has_sales_estimate": 24,
    "has_stock_level": 24,
    "has_offer_counts": 24,
    "has_fba_fee": 168,
    "has_referral_fee": 168,
}

# 冷启动等待超时（秒）
_COLD_START_TIMEOUT = 120


class DataProvider:
    """
    Agent 唯一数据入口。

    用法：
        provider = DataProvider()
        product = await provider.get_product("B0GPD2H4GN")

    所有 Agent 必须通过此入口读取数据，不得直接 import 任何 connector。
    """

    def __init__(self):
        self._queue = AcquisitionQueue()
        self._cold_start_locks: Dict[str, asyncio.Event] = {}
        self._cold_start_results: Dict[str, Optional[Dict]] = {}

    # ── 公开入口 ───────────────────────────────────────────────────

    async def get_product(self, asin: str, domain: str = "US", with_trust: bool = True) -> Optional[Dict]:
        """读优先：有且新鲜 → 直接返回；过期 → 异步刷新；无 → 冷启动"""
        async with AsyncSessionLocal() as db:
            repo = AmazonProductRepository(db)
            product = await repo.get_by_asin(asin, domain)

        if product is None:
            return await self._cold_start(asin, domain)

        result = self._product_to_dict(product)

        # 检查新鲜度
        stale_dims = self._check_staleness(product.freshness_map or {})
        if stale_dims:
            asyncio.create_task(self._refresh(asin, domain, stale_dims))

        # 附可信度
        if with_trust:
            result = enrich_with_trust(result, product.freshness_map or {})

        return result

    async def get_product_blocking(self, asin: str, domain: str = "US", with_trust: bool = True) -> Optional[Dict]:
        """阻塞模式：等数据采集完毕再返回（用于冷启动）"""
        result = await self._cold_start(asin, domain)
        if result and with_trust:
            result = enrich_with_trust(result, result.get("freshness_map", {}))
        return result

    async def get_products(self, asins: List[str], domain: str = "US", with_trust: bool = True) -> Dict[str, Optional[Dict]]:
        """批量查"""
        results = {}
        for asin in asins:
            results[asin] = await self.get_product(asin, domain, with_trust)
        return results

    # ── 冷启动 ─────────────────────────────────────────────────────

    async def _cold_start(self, asin: str, domain: str = "US") -> Optional[Dict]:
        """冷启动：走 ETL Pipeline 的 4 阶段递进冷启动"""
        lock_key = f"{asin}:{domain}"

        if lock_key in self._cold_start_locks:
            event = self._cold_start_locks[lock_key]
            await asyncio.wait_for(event.wait(), timeout=_COLD_START_TIMEOUT)
            return self._cold_start_results.get(lock_key)

        event = asyncio.Event()
        self._cold_start_locks[lock_key] = event

        try:
            # 直接调 ETL Pipeline 的 cold_start（不走队列——冷启动是同步阻塞的）
            async with AsyncSessionLocal() as db:
                pipeline = ETLPipeline(db)
                product_data = await pipeline.cold_start(asin, domain)
                self._cold_start_results[lock_key] = product_data
                return product_data
        except Exception as e:
            logger.error(f"[DataProvider] Cold start failed for {asin}: {e}")
            return None
        finally:
            event.set()
            self._cold_start_locks.pop(lock_key, None)
            self._cold_start_results.pop(lock_key, None)

    # ── 异步刷新 ───────────────────────────────────────────────────

    async def _refresh(self, asin: str, domain: str, stale_dims: List[str]):
        """异步刷新过期维度"""
        logger.info(f"[DataProvider] Async refresh {asin}: {stale_dims}")
        await self._queue.enqueue(asin, priority=1, domain=domain, dimensions=stale_dims)

    # ── 新鲜度检查 ─────────────────────────────────────────────────

    def _check_staleness(self, freshness_map: Dict) -> List[str]:
        """检查哪些维度过期了"""
        now = datetime.now(timezone.utc)
        stale = []
        for dim, ttl_hours in _FRESHNESS_TTL.items():
            meta = freshness_map.get(dim, {})
            updated_str = meta.get("updated_at") if isinstance(meta, dict) else None
            if not updated_str:
                stale.append(dim)
                continue
            try:
                updated = datetime.fromisoformat(updated_str.replace("Z", "+00:00"))
                if (now - updated).total_seconds() > ttl_hours * 3600:
                    stale.append(dim)
            except (ValueError, TypeError):
                stale.append(dim)
        return stale

    # ── 工具 ───────────────────────────────────────────────────────

    def _product_to_dict(self, product) -> Dict:
        """ORM 对象转 dict"""
        from sqlalchemy.orm import class_mapper
        data = {}
        for col in class_mapper(type(product)).mapped_table.columns:
            val = getattr(product, col.name, None)
            if val is not None:
                data[col.name] = val
        return data