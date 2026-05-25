"""
三源 ETL Pipeline

流程：Extract → Normalize → Merge → Load

职责：
  1. 从 Keepa / Rainforest / Canopy 提取原始数据
  2. 将不同源的相同字段归一化
  3. 按字段级源优先级合并（不覆盖独占字段）
  4. 写入 amazon_products 表
  5. 记录 ETL 日志
"""

import asyncio
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.ext.asyncio import AsyncSession

from backend.business.ecommerce.amazon_monitor.tools.keepa_connector import (
    KeepaConnector,
    KeepaError as KError,
)
from backend.business.ecommerce.amazon_monitor.tools.rainforest_connector import (
    RainforestConnector,
    RainforestError as RFError,
)
from backend.business.ecommerce.amazon_monitor.tools.canopy_connector import (
    CanopyConnector,
    CanopyError as CNError,
)
from backend.data.repositories.postgreSQL.amazon_product_repo import AmazonProductRepository
from backend.config.config import settings

logger = logging.getLogger(__name__)

# ── 字段级源优先级 ─────────────────────────────────────────────
# 当多个源有相同字段时，优先级高的源的写入覆盖优先级低的
# 独占字段（如 Keepa price_history）不会被其他源覆盖

_SOURCE_PRIORITY = {
    # Rainforest 独家或最优
    "aplus_content": "rainforest",
    "videos_count": "rainforest",
    "rating_breakdown": "rainforest",
    "sponsored_products": "rainforest",
    "fulfillment": "rainforest",
    "is_prime": "rainforest",
    "availability": "rainforest",
    "feature_bullets": "rainforest",
    "main_image": "rainforest",
    "images": "rainforest",
    "child_asins": "rainforest",
    "parent_asin": "rainforest",
    "specifications": "rainforest",
    "country_of_origin": "rainforest",
    "dimensions": "rainforest",
    "weight": "rainforest",
    "color": "rainforest",
    "size": "rainforest",

    # Keepa 独家字段（不会被覆盖）
    "price_history": "keepa",
    "bsr_history": "keepa",
    "monthly_sold": "keepa",
    "avg_price_30d": "keepa",
    "avg_price_90d": "keepa",
    "min_price_90d": "keepa",
    "max_price_90d": "keepa",
    "avg_bsr_30d": "keepa",
    "avg_bsr_90d": "keepa",
    "bsr_trend": "keepa",
    "review_count_history": "keepa",

    # Canopy 优先（价格/评分经常更及时）
    "current_price": "canopy",
    "rating": "canopy",
    "review_count": "canopy",
    "seller_name": "canopy",
    "current_bsr": "canopy",

    # 通用字段 — RF 优先
    "title": "rainforest",
    "brand": "rainforest",
    "category_name": "rainforest",
    "category_tree": "rainforest",
    "manufacturer": "rainforest",
    "model_number": "rainforest",
    "part_number": "rainforest",
    "upc": "rainforest",
    "ean": "rainforest",
    "product_group": "rainforest",
    "binding": "rainforest",
    "description": "rainforest",
}

# 需要从 ETL 结果中排除的内部字段
_EXCLUDED_KEYS = {
    "id", "created_at", "updated_at",
    "keepa_updated_at", "rainforest_updated_at", "canopy_updated_at",
    "importance_updated_at", "importance_score", "importance_tier", "importance_details",
    "data_source", "stock_level", "max_order_quantity",
}


class ETLPipeline:
    """
    三源 ETL Pipeline
    同享一个 repo 实例完成提取-转换-加载
    """

    def __init__(self, db: AsyncSession, keepa_api_key: Optional[str] = None,
                 rainforest_api_key: Optional[str] = None,
                 canopy_api_key: Optional[str] = None):
        self.repo = AmazonProductRepository(db)
        self.keepa = KeepaConnector(keepa_api_key)
        self.rainforest = RainforestConnector(rainforest_api_key)
        self.canopy = CanopyConnector(canopy_api_key)
        self.run_id = str(uuid.uuid4())[:8]

    # ── Extract ──

    async def extract_keepa(self, asins: List[str], domain: str = "US") -> Dict[str, Any]:
        """从 Keepa 提取商品历史数据"""
        try:
            result = await self.keepa.async_query_products(asins, domain, history=True, stats=180)
            data = {}
            for p in result:
                p["domain"] = domain
                data[p["asin"]] = p
            return {"data": data, "asins_total": len(asins), "asins_success": len(data)}
        except KError as e:
            logger.error(f"Keepa extract failed: {e}")
            return {"data": {}, "asins_total": len(asins), "asins_success": 0, "error": str(e)}

    async def extract_rainforest(self, asins: List[str], domain: str = "amazon.com") -> Dict[str, Any]:
        """从 Rainforest 提取商品详情"""
        success = 0
        data = {}
        errors = []
        for asin in asins:
            try:
                result = await self.rainforest.async_get_product(asin, domain)
                result["domain"] = "US"  # domain 映射在外部处理
                data[asin] = result
                success += 1
            except RFError as e:
                errors.append(asin)
                logger.warning(f"Rainforest extract failed for {asin}: {e}")
        return {"data": data, "asins_total": len(asins), "asins_success": success, "asins_failed": errors}

    async def extract_canopy(self, asins: List[str], domain: str = "amazon.com") -> Dict[str, Any]:
        """从 Canopy 提取商品详情"""
        success = 0
        data = {}
        errors = []
        for asin in asins:
            try:
                result = await self.canopy.async_get_product(asin, domain)
                result["domain"] = "US"
                data[asin] = result
                success += 1
            except CNError as e:
                errors.append(asin)
                logger.warning(f"Canopy extract failed for {asin}: {e}")
        return {"data": data, "asins_total": len(asins), "asins_success": success, "asins_failed": errors}

    # ── Normalize ──

    def _normalize_keepa(self, raw: Dict[str, Any]) -> Dict[str, Any]:
        """Keepa 数据归一化到 amazon_products 字段"""
        fields = [
            "asin", "title", "brand", "category_id", "root_category",
            "category_tree", "current_price", "avg_price_30d", "avg_price_90d",
            "min_price_90d", "max_price_90d", "current_bsr", "avg_bsr_30d",
            "avg_bsr_90d", "bsr_trend", "monthly_sold", "rating", "review_count",
            "seller_count", "price_history", "bsr_history", "parent_asin",
            "product_group", "binding", "manufacturer", "model_number",
            "part_number", "upc", "ean", "color", "size", "weight",
            "package_quantity", "features", "description", "images_csv",
            "variation_csv", "domain",
        ]
        result = {}
        for f in fields:
            if f in raw and raw[f] is not None:
                result[f] = raw[f]
        return result

    def _normalize_rainforest(self, raw: Dict[str, Any]) -> Dict[str, Any]:
        """Rainforest 数据归一化到 amazon_products 字段"""
        mapping = {
            "asin": "asin", "title": "title", "brand": "brand",
            "parent_asin": "parent_asin", "child_asins": "child_asins",
            "category_name": "category_name", "category_tree": "category_tree",
            "feature_bullets": "feature_bullets",
            "description": "description", "aplus_content": "aplus_content",
            "main_image": "main_image", "images": "images",
            "videos_count": "videos_count",
            "current_price": "current_price", "list_price": "list_price",
            "is_prime": "is_prime", "fulfillment": "fulfillment",
            "availability": "availability",
            "bsr_rank": "current_bsr", "bsr_category": "bsr_category",
            "rating": "rating", "ratings_total": "review_count",
            "rating_breakdown": "rating_breakdown",
            "variations": "variations", "top_reviews": "top_reviews",
            "manufacturer": "manufacturer", "model_number": "model_number",
            "part_number": "part_number", "upc": "upc", "ean": "ean",
            "color": "color", "size": "size",
            "dimensions": "dimensions", "binding": "binding",
            "product_group": "product_group",
            "country_of_origin": "country_of_origin",
            "sponsored_products": "sponsored_products",
            "recent_sales": "recent_sales",
            "item_weight": "weight",
            "package_quantity": "package_quantity",
            "material": "material",
            "domain": "domain",
            "stock_level": "stock_level",
            "max_order_quantity": "max_order_quantity",
        }
        result = {}
        for src_key, dst_key in mapping.items():
            if src_key in raw and raw[src_key] is not None:
                result[dst_key] = raw[src_key]
        return result

    def _normalize_canopy(self, raw: Dict[str, Any]) -> Dict[str, Any]:
        """Canopy 数据归一化到 amazon_products 字段"""
        mapping = {
            "asin": "asin", "title": "title", "brand": "brand",
            "category_name": "category_name", "category_tree": "category_tree",
            "feature_bullets": "feature_bullets",
            "description": "description",
            "main_image": "main_image", "images": "images",
            "current_price": "current_price",
            "is_prime": "is_prime",
            "rating": "rating", "ratings_total": "review_count",
            "top_reviews": "top_reviews",
            "seller_name": "seller_name",
            "manufacturer": "manufacturer", "model_number": "model_number",
            "part_number": "part_number", "upc": "upc", "ean": "ean",
            "color": "color", "size": "size",
            "weight": "weight", "dimensions": "dimensions",
            "domain": "domain",
        }
        result = {}
        for src_key, dst_key in mapping.items():
            if src_key in raw and raw[src_key] is not None:
                result[dst_key] = raw[src_key]
        return result

    # ── Merge（按字段级优先级合并） ──

    def _merge_products(self, keepa_data: Dict, rf_data: Dict, cn_data: Dict) -> Dict[str, Dict]:
        """
        按字段级优先级合并三源数据为一个统一的 product dict。
        规则：
          - 独占字段（如 price_history）只来自一个源，直接保留
          - 共享字段按 _SOURCE_PRIORITY 中定义的源优先级写入
          - 三源都有的字段，优先级最高源的覆盖其他
        """
        all_asins = set()
        all_asins.update(keepa_data.keys())
        all_asins.update(rf_data.keys())
        all_asins.update(cn_data.keys())

        merged = {}
        for asin in all_asins:
            product = {}

            # 收集三源数据
            kp = keepa_data.get(asin, {})
            rf = rf_data.get(asin, {})
            cn = cn_data.get(asin, {})

            # 标记数据来源
            sources = []
            if kp:
                sources.append("keepa")
            if rf:
                sources.append("rainforest")
            if cn:
                sources.append("canopy")
            product["data_source"] = sources

            # 组装所有可能的字段
            all_fields = set()
            all_fields.update(kp.keys())
            all_fields.update(rf.keys())
            all_fields.update(cn.keys())
            all_fields.difference_update(_EXCLUDED_KEYS)

            for field in all_fields:
                # 按优先级确定该字段的来源
                preferred = _SOURCE_PRIORITY.get(field)

                val = None
                if preferred == "keepa":
                    val = kp.get(field)
                elif preferred == "rainforest":
                    val = rf.get(field)
                elif preferred == "canopy":
                    val = cn.get(field)
                else:
                    # 无明确优先级：取第一个非空值
                    for src in [kp, rf, cn]:
                        if field in src and src[field] is not None:
                            val = src[field]
                            break

                if val is not None:
                    product[field] = val

            merged[asin] = product

        return merged

    # ── Load ──

    async def _load_asin(self, asin: str, product_data: Dict, merged: Dict) -> bool:
        """加载单个 ASIN 数据到数据库"""
        try:
            # 更新对应源的数据
            sources = product_data.get("data_source", [])
            for s in sources:
                if s == "keepa":
                    await self.repo.upsert(product_data, "keepa")
                elif s == "rainforest":
                    await self.repo.upsert(product_data, "rainforest")
                elif s == "canopy":
                    await self.repo.upsert(product_data, "canopy")
            return True
        except Exception as e:
            logger.error(f"Load failed for {asin}: {e}")
            return False

    async def load_products(self, merged: Dict) -> Tuple[int, int, List[str]]:
        """批量加载合并后的数据到数据库"""
        success = 0
        failed_asins = []

        for asin, product_data in merged.items():
            ok = await self._load_asin(asin, product_data, merged)
            if ok:
                success += 1
            else:
                failed_asins.append(asin)

        return len(merged), success, failed_asins

    # ── 完整 Pipeline ──

    async def run(
        self,
        asins: List[str],
        domain: str = "US",
        sources: List[str] = ("keepa", "rainforest", "canopy"),
        calc_importance: bool = True,
    ) -> Dict[str, Any]:
        """
        运行完整 ETL Pipeline。

        Args:
            asins: 需要处理的 ASIN 列表
            domain: 市场代码（US/DE/JP 等）
            sources: 本次运行需要调用的数据源
            calc_importance: 加载后是否重新计算重要性评分

        Returns:
            {
                "run_id": str,
                "status": str,
                "asins_total": int,
                "asins_success": int,
                "errors": [...],
                "keepa_consumed": int,
                ...
            }
        """
        started_at = datetime.now(timezone.utc)
        result = {
            "run_id": self.run_id,
            "status": "running",
            "asins_total": len(asins),
            "asins_success": 0,
            "asins_failed": [],
            "keepa_consumed": 0,
            "rainforest_consumed": 0,
            "canopy_consumed": 0,
        }

        try:
            # 1. Extract
            keepa_raw, rf_raw, cn_raw = {}, {}, {}
            tasks = []

            if "keepa" in sources:
                tasks.append(("keepa", self.extract_keepa(asins, domain)))
            if "rainforest" in sources:
                rf_domain = _keepa_to_rainforest_domain(domain)
                tasks.append(("rainforest", self.extract_rainforest(asins, rf_domain)))
            if "canopy" in sources:
                cn_domain = _keepa_to_rainforest_domain(domain)
                tasks.append(("canopy", self.extract_canopy(asins, cn_domain)))

            # 并发执行 Extract
            for name, coro in tasks:
                raw_result = await coro
                if name == "keepa":
                    keepa_raw = raw_result["data"]
                    result["keepa_consumed"] = raw_result["asins_success"]
                elif name == "rainforest":
                    rf_raw = raw_result["data"]
                    result["rainforest_consumed"] = raw_result["asins_success"]
                elif name == "canopy":
                    cn_raw = raw_result["data"]
                    result["canopy_consumed"] = raw_result["asins_success"]

            # 2. Normalize 每个源
            keepa_norm = {a: self._normalize_keepa(p) for a, p in keepa_raw.items()}
            rf_norm = {a: self._normalize_rainforest(p) for a, p in rf_raw.items()}
            cn_norm = {a: self._normalize_canopy(p) for a, p in cn_raw.items()}

            # 3. Merge
            merged = self._merge_products(keepa_norm, rf_norm, cn_norm)

            # 4. Load
            total, success, failed = await self.load_products(merged)

            # 5. 计算重要性评分
            if calc_importance:
                for asin in merged:
                    try:
                        await self.repo.recalc_importance(asin, domain)
                    except Exception as e:
                        logger.warning(f"Importance calc failed for {asin}: {e}")

            # 6. 记录 ETL 日志
            duration = (datetime.now(timezone.utc) - started_at).total_seconds()
            await self._log_result(result, "success", duration)

            result["status"] = "success"
            result["asins_success"] = success
            result["asins_failed"] = failed
            result["duration_seconds"] = round(duration, 1)

        except Exception as e:
            duration = (datetime.now(timezone.utc) - started_at).total_seconds()
            await self._log_result(result, "failed", duration, str(e))
            result["status"] = "failed"
            result["error"] = str(e)

        return result

    async def _log_result(self, result: Dict, status: str, duration: float, error: str = ""):
        """记录 ETL 运行日志到 amazon_etl_logs 表"""
        try:
            await self.repo.create_etl_log({
                "run_id": result["run_id"],
                "started_at": datetime.now(timezone.utc),
                "finished_at": datetime.now(timezone.utc),
                "duration_seconds": duration,
                "status": status,
                "source": "all",
                "asins_queried": result["asins_total"],
                "asins_success": result.get("asins_success", 0),
                "asins_failed": result.get("asins_failed", []) if error else None,
                "tokens_or_credits": result.get("keepa_consumed", 0),
                "error_message": error or None,
            })
        except Exception as e:
            logger.warning(f"Failed to log ETL result: {e}")


def _keepa_to_rainforest_domain(keepa_domain: str) -> str:
    """Keepa 的 US → Rainforest 的 amazon.com"""
    _MAP = {
        "US": "amazon.com", "GB": "amazon.co.uk", "DE": "amazon.de",
        "FR": "amazon.fr", "JP": "amazon.co.jp", "CA": "amazon.ca",
        "IT": "amazon.it", "ES": "amazon.es", "IN": "amazon.in",
        "MX": "amazon.com.mx", "BR": "amazon.com.br", "AU": "amazon.com.au",
        "NL": "amazon.nl", "SG": "amazon.sg", "AE": "amazon.ae",
        "SA": "amazon.sa", "TR": "amazon.com.tr", "SE": "amazon.se",
        "PL": "amazon.pl",
    }
    return _MAP.get(keepa_domain.upper(), "amazon.com")