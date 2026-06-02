"""
数据调度层统一入口 — Agent 唯一的数据来源

Agent 通过此 Provider 读取数据，不直接访问任何 API 连接器。

返回三层结构：
  Layer 1 (~50 列): 扁平核心字段，Agent 直接引用
  Layer 2 (33 域):  分析域推导结果，开箱即用
  Layer 3:          子表原始数据（offers/variations）+ raw_payload

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
from backend.aqueduct.acquisition_queue import acquisition_queue
from backend.aqueduct.cost_catalog import estimate_min_cost
from backend.aqueduct.cost_controller import cost_controller
from backend.aqueduct.etl_pipeline import ETLPipeline
from backend.aqueduct.quality_scorer import enrich_with_trust
from backend.aqueduct.roi_tracker import roi_tracker
from backend.aqueduct.derived_fields import compute_all_derived_fields

logger = logging.getLogger(__name__)

# 各维度新鲜度阈值（小时）
_FRESHNESS_TTL = {
    "has_price": 6,
    "has_buybox": 6,
    "has_price_stats": 12,
    "has_price_stats_extended": 24,
    "has_bsr": 6,
    "has_bsr_stats": 12,
    "has_bsr_stats_extended": 24,
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
    "has_specifications": 168,
    "has_physical_dims": 720,
    "has_product_type": 720,
}

# 冷启动等待超时（秒）
_COLD_START_TIMEOUT = 120

# Layer 1 核心字段（Agent 最常直接引用的 ~50 列）
_CORE_FIELDS = {
    "asin", "domain", "title", "brand", "product_type", "product_type_name",
    "current_price", "currency", "list_price", "buybox_price",
    "avg_price_30d", "avg_price_90d",
    "current_bsr", "bsr_category", "avg_bsr_30d", "avg_bsr_90d", "bsr_trend",
    "monthly_sold", "weekly_sold", "annual_sold",
    "rating", "review_count", "rating_breakdown", "review_velocity_30d",
    "seller_count", "offer_count", "offer_count_fba", "offer_count_fbm",
    "buybox_seller_id", "buybox_seller_name", "is_fba", "is_prime",
    "main_image", "images", "feature_bullets", "description",
    "stock_level", "is_in_stock",
    "fba_fee", "referral_fee_percent",
    "coupon_text", "is_bundle",
    "color", "size", "style", "material",
    "item_weight_g",
    "is_warehouse_deal", "is_preorder",
    "has_amazon_selling", "has_china_sellers",
    "coverage_map", "freshness_map",
    "data_source",
    "lifecycle_status", "importance_score", "importance_tier",
    "created_at", "updated_at",
}

# 从 Layer 1 排除的字段（内部/元信息/原始数据）
_EXCLUDED_FROM_LAYER1 = {
    "id", "raw_payload", "price_history", "bsr_history", "rating_history",
    "review_count_history", "sales_rank_history", "offer_history",
    "coverage_map", "freshness_map",
    "parent_asin_history", "sales_rank_reference_history",
    "hazardous_materials", "seller_profile",
    "seller_ids_lowest_fba", "seller_ids_lowest_fbm",
    "buybox_eligible_offer_counts",
    "child_asins",
    "keepa_updated_at", "rainforest_updated_at", "canopy_updated_at",
    "importance_updated_at", "importance_details",
    "last_accessed_at",
}


class DataProvider:
    """
    Agent 唯一数据入口。

    用法：
        provider = DataProvider()
        product = await provider.get_product("B0GPD2H4GN")

    所有 Agent 必须通过此入口读取数据，不得直接 import 任何 connector。
    返回数据为三层结构，Agent 可开箱即用。
    """

    def __init__(self):
        self._queue = acquisition_queue
        self._cold_start_locks: Dict[str, asyncio.Event] = {}
        self._cold_start_results: Dict[str, Optional[Dict]] = {}

    # ── 公开入口 ───────────────────────────────────────────────────

    async def get_product(self, asin: str, domain: str = "US", with_trust: bool = True) -> Optional[Dict]:
        """读优先：有且新鲜 → 直接返回；过期 → 异步刷新；无 → 冷启动"""
        async with AsyncSessionLocal() as db:
            repo = AmazonProductRepository(db)
            product = await repo.get_by_asin(asin, domain)
            offers = await repo.get_offers(asin, domain)
            variations = await repo.get_variations(asin, domain)

        if product is None:
            result = await self._cold_start(asin, domain)
            if result and with_trust:
                result = enrich_with_trust(result, result.get("freshness_map", {}))
            return self._assemble_response(result) if result else None

        # 记录访问时间
        async with AsyncSessionLocal() as db:
            repo = AmazonProductRepository(db)
            await repo.update_last_accessed(asin, domain)

        await roi_tracker.record_query(asin)

        product_dict = self._product_to_dict(product)
        offers_list = [self._offer_to_dict(o) for o in offers]
        variations_list = [self._variation_to_dict(v) for v in variations]

        # 组装三层结构
        result = self._assemble_response(
            product_dict, offers_list, variations_list
        )

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
        if result:
            assembled = self._assemble_response(result)
            if with_trust:
                assembled = enrich_with_trust(assembled, result.get("freshness_map", {}))
            return assembled
        return None

    async def get_products(self, asins: List[str], domain: str = "US", with_trust: bool = True) -> Dict[str, Optional[Dict]]:
        """批量查"""
        results = {}
        for asin in asins:
            results[asin] = await self.get_product(asin, domain, with_trust)
        return results

    async def get_product_multi_domain(
        self, asin: str, domains: List[str] = None, with_trust: bool = True,
    ) -> Dict[str, Optional[Dict]]:
        """同时获取多个站点的商品数据"""
        if domains is None:
            domains = ["US", "DE", "JP"]
        results = {}
        for d in domains:
            results[d] = await self.get_product(asin, d, with_trust)
        return results

    # ── 三层结构组装 ───────────────────────────────────────────────

    def _assemble_response(
        self,
        product: Dict[str, Any],
        offers: List[Dict] = None,
        variations: List[Dict] = None,
    ) -> Dict[str, Any]:
        """将原始数据组装为三层结构"""
        if not product:
            return None

        # ── Layer 1: 核心扁平字段 ──
        layer1 = {}
        for key in _CORE_FIELDS:
            if key in product and product[key] is not None:
                layer1[key] = product[key]

        # 也包含不在 _CORE_FIELDS 但不在不排除列表中的非空字段
        for key, value in product.items():
            if key not in _EXCLUDED_FROM_LAYER1 and key not in _CORE_FIELDS:
                if value is not None and not key.startswith("_"):
                    layer1[key] = value

        # ── Layer 2: 33 分析域推导结果 ──
        layer2 = compute_all_derived_fields(product, offers or [], variations or [])

        # ── Layer 3: 原始数据 ──
        layer3 = {
            "offers": offers or [],
            "variations": variations or [],
            "raw_payload": product.get("raw_payload", {}),
        }

        # ── 元信息 ──
        meta = {
            "coverage_map": product.get("coverage_map", {}),
            "freshness_map": product.get("freshness_map", {}),
            "data_source": product.get("data_source", []),
            "_trust_summary": {"overall": "high"},
        }

        return {
            **layer1,
            **layer2,
            **meta,
            **layer3,
        }

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
        cost_plan = estimate_min_cost(stale_dims)
        logger.info(
            f"[DataProvider] Async refresh {asin}: {stale_dims} "
            f"(cost={cost_plan['total']}, feasible={cost_plan['feasible']})"
        )
        if not cost_plan["feasible"] and cost_plan["total"]:
            logger.warning(f"[DataProvider] {asin} refresh 成本超出预算，降低优先级入队")
        await acquisition_queue.enqueue(
            asin,
            priority=0 if cost_plan["feasible"] else 2,
            domain=domain,
            dimensions=stale_dims,
        )

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

    def _offer_to_dict(self, offer) -> Dict:
        """Offer ORM 对象转 dict"""
        from sqlalchemy.orm import class_mapper
        data = {}
        for col in class_mapper(type(offer)).mapped_table.columns:
            val = getattr(offer, col.name, None)
            if val is not None:
                data[col.name] = val
        return data

    def _variation_to_dict(self, variation) -> Dict:
        """Variation ORM 对象转 dict"""
        from sqlalchemy.orm import class_mapper
        data = {}
        for col in class_mapper(type(variation)).mapped_table.columns:
            val = getattr(variation, col.name, None)
            if val is not None:
                data[col.name] = val
        return data