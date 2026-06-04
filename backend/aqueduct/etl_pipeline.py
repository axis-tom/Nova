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
from typing import Any, Dict, List, Optional, Tuple, Set

from sqlalchemy.ext.asyncio import AsyncSession

from backend.aqueduct.connectors.keepa_connector import (
    KeepaConnector,
    KeepaError as KError,
)
from backend.aqueduct.connectors.rainforest_connector import (
    RainforestConnector,
    RainforestError as RFError,
)
from backend.aqueduct.connectors.canopy_connector import (
    CanopyConnector,
    CanopyError as CNError,
)
from backend.data.models.change_log import detect_changes, changes_to_log_entries, TRACKED_FIELDS
from backend.data.models.anomaly_log import detect_anomalies
from backend.data.repositories.postgreSQL.amazon_product_repo import AmazonProductRepository
from backend.aqueduct.metrics import (
    etl_run_duration, etl_asins_processed, structured_log,
)
from backend.config.config import settings

logger = logging.getLogger(__name__)

# ── 字段级源优先级 ─────────────────────────────────────────────
# 从 field_config.py 自动生成，不再手写
from backend.aqueduct.field_config import _SOURCE_PRIORITY, FIELD_CONFIG


# 需要从 ETL 结果中排除的内部字段
_EXCLUDED_KEYS = {
    "id", "created_at", "updated_at",
    "keepa_updated_at", "rainforest_updated_at", "canopy_updated_at",
    "importance_updated_at", "importance_score", "importance_tier", "importance_details",
    "data_source",
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
        keepa_domain = None
        for k, v in _KEEPA_TO_RF_MAP.items():
            if v == domain:
                keepa_domain = k
                break
        for asin in asins:
            try:
                result = await self.rainforest.async_get_product(asin, domain)
                result["domain"] = keepa_domain or "US"
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
        keepa_domain = None
        for k, v in _KEEPA_TO_RF_MAP.items():
            if v == domain:
                keepa_domain = k
                break
        for asin in asins:
            try:
                result = await self.canopy.async_get_product(asin, domain)
                result["domain"] = keepa_domain or "US"
                data[asin] = result
                success += 1
            except CNError as e:
                errors.append(asin)
                logger.warning(f"Canopy extract failed for {asin}: {e}")
        return {"data": data, "asins_total": len(asins), "asins_success": success, "asins_failed": errors}

    # ── Normalize ──

    def _normalize_keepa(self, raw: Dict[str, Any]) -> Dict[str, Any]:
        """Keepa 数据归一化到 amazon_products 字段（全字段版）"""
        # Keepa 连接器 _parse_product 已经把所有字段标准化了
        # 这里只需要过滤出模型已定义的列
        keepa_fields = {
            "asin", "domain", "parent_asin", "product_type", "product_type_name",
            "title", "brand", "brand_store", "feature_bullets", "description",
            "images_csv", "color", "size", "style", "material",
            "weight", "item_weight_g", "item_height_mm", "item_length_mm", "item_width_mm",
            "package_weight_g", "package_dimensions_mm", "package_quantity",
            "number_of_items", "item_type_keyword", "unit_count_type", "unit_count_value",
            "current_price", "list_price", "buybox_price", "buybox_seller_id",
            "buybox_seller_name", "currency",
            "avg_price_30d", "avg_price_90d", "avg_price_180d", "avg_price_365d",
            "min_price_30d", "min_price_90d", "min_price_180d",
            "max_price_90d", "max_price_180d",
            "is_lowest_price", "buybox_is_amazon", "buybox_is_prime_eligible", "buybox_shipping",
            "current_bsr", "avg_bsr_30d", "avg_bsr_90d", "avg_bsr_180d", "avg_bsr_365d",
            "bsr_trend",
            "sales_rank_drops_30d", "sales_rank_drops_90d", "sales_rank_drops_180d", "sales_rank_drops_365d",
            "sales_rank_reference_id", "root_category_id", "sales_rank_reference_history",
            "monthly_sold", "sales_rank_history",
            "rating", "review_count", "rating_history", "review_count_history",
            "seller_count", "offer_count", "offer_count_fba", "offer_count_fbm",
            "seller_ids_lowest_fba", "seller_ids_lowest_fbm", "buybox_eligible_offer_counts",
            "is_fba", "is_prime",
            "fba_fee", "referral_fee_percent",
            "offer_history",
            "is_warehouse_deal", "is_preorder", "is_map_restricted",
            "batteries_included", "batteries_required", "is_sns", "is_heat_sensitive",
            "is_adult_product", "is_eligible_for_trade_in", "is_redirect_asin", "launchpad",
            "shipping_origin", "is_eligible_for_free_shipping", "available_prime_exclusive",
            "hazardous_materials",
            "coupon_text", "promotions_json", "lightning_deal_info",
            "price_history", "bsr_history",
            "out_of_stock_pct_30d", "out_of_stock_pct_90d", "out_of_stock_pct_180d",
            "out_of_stock_count_amazon",
            "tracking_since", "listed_since",
            "url_slug",
            "category_tree", "root_category", "product_group", "binding",
            "manufacturer", "model", "part_number", "upc", "ean", "isbn",
            "variation_csv",
            # 新增 Keepa 解析字段
            "availability_text", "whats_in_the_box", "sales_rank_history",
            "parent_asin_history", "link", "dimensions", "shipping_weight",
            "bestsellers_rank_flat", "variant_asins_flat",
            "has_coupon", "unit_price", "used_offers_count",
            "new_offers_from", "used_offers_from",
            "has_reviews", "gift_guide_badge",
            "amazons_choice", "subscribe_and_save", "trade_in_and_save",
            "deal_badge", "big_spring_deal_percentage",
            "is_fulfilled_by_amazon_international",
            "isEligibleForSuperSaverShipping", "free_shipping_minimum_spend",
            "is_amazon_brand", "is_exclusive_to_amazon", "is_small_business",
            "climate_pledge_friendly", "add_on_item", "proposition_65_warning",
            "sell_on_amazon",
            "brand_store_name", "brand_store_url",
            "feature_bullets_count", "specifications_flat",
            "has_size_guide", "has_360_view",
            "summarization_attributes", "customers_say",
            "keywords_list",
            # 字段名别名
            "category_id",       # Keepa 返回 category_id → 模型叫 bsr_category_id
        }
        result = {}
        for key in keepa_fields:
            if key in raw and raw[key] is not None:
                # 字段名别名映射
                aliases = {
                    "category_id": "bsr_category_id",
                }
                dst_key = aliases.get(key, key)
                result[dst_key] = raw[key]

        # 衍生计算：images_count = len(images)
        if "images" in result and isinstance(result["images"], (list, dict)):
            try:
                imgs = result["images"]
                if isinstance(imgs, list):
                    result["images_count"] = len(imgs)
            except Exception:
                pass

        # unit_count JSON 组合
        if result.get("unit_count_type") or result.get("unit_count_value"):
            result["unit_count"] = {
                "unitType": result.get("unit_count_type"),
                "unitValue": result.get("unit_count_value"),
            }

        return result

    def _normalize_rainforest(self, raw: Dict[str, Any]) -> Dict[str, Any]:
        """Rainforest 数据归一化到 amazon_products 字段（全字段版）"""
        mapping = {
            "asin": "asin", "title": "title", "brand": "brand",
            "parent_asin": "parent_asin", "child_asins": "child_asins",
            "category_name": "category_name", "category_tree": "category_tree",
            "feature_bullets": "feature_bullets",
            "description": "description", "aplus_content": "aplus_content",
            "main_image": "main_image", "images": "images",
            "videos_count": "videos_count", "videos": "videos",
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
            # 新增字段
            "sub_title": "sub_title",
            "return_policy": "return_policy",
            "protection_plans": "protection_plans",
            "buybox_availability": "buybox_availability",
            "buybox_condition": "buybox_condition",
            "buybox_is_amazon": "buybox_is_amazon",
            "keywords_list": "keywords_list",
            "search_alias": "search_alias",
            "seller_profile": "seller_profile",
            "first_available": "first_available",
            "rich_product_description": "rich_product_description",
            "frequently_bought_together": "frequently_bought_together",
            "product_type_name": "product_type_name",
            "images_count": "images_count",
            "is_bundle": "is_bundle",
            # 修复遗漏
            "specifications": "specifications",
            "style": "style",
            # 新增 RF 字段
            "link": "link",
            "dimensions": "dimensions",
            "shipping_weight": "shipping_weight",
            "also_bought": "also_bought",
            "also_viewed": "also_viewed",
            "bestsellers_rank_flat": "bestsellers_rank_flat",
            "variant_asins_flat": "variant_asins_flat",
            "brand_store_name": "brand_store_name",
            "brand_store_url": "brand_store_url",
            "specifications_flat": "specifications_flat",
            "feature_bullets_count": "feature_bullets_count",
            # 新增 RF 字段 Phase 2 补全
            "has_coupon": "has_coupon",
            "amazons_choice": "amazons_choice",
            "subscribe_and_save": "subscribe_and_save",
            "trade_in_and_save": "trade_in_and_save",
            "deal_badge": "deal_badge",
            "big_spring_deal_percentage": "big_spring_deal_percentage",
            "has_reviews": "has_reviews",
            "has_size_guide": "has_size_guide",
            "has_360_view": "has_360_view",
            "gift_guide_badge": "gift_guide_badge",
            "is_amazon_brand": "is_amazon_brand",
            "is_exclusive_to_amazon": "is_exclusive_to_amazon",
            "is_small_business": "is_small_business",
            "climate_pledge_friendly": "climate_pledge_friendly",
            "proposition_65_warning": "proposition_65_warning",
            "sell_on_amazon": "sell_on_amazon",
            "add_on_item": "add_on_item",
            "summarization_attributes": "summarization_attributes",
            "customers_say": "customers_say",
            "used_offers_count": "used_offers_count",
            "new_offers_from": "new_offers_from",
            "used_offers_from": "used_offers_from",
            "unit_price": "unit_price",
            "free_shipping_minimum_spend": "free_shipping_minimum_spend",
            "is_fulfilled_by_amazon_international": "is_fulfilled_by_amazon_international",
        }
        result = {}
        for src_key, dst_key in mapping.items():
            if src_key in raw and raw[src_key] is not None:
                result[dst_key] = raw[src_key]
        return result

    def _normalize_canopy(self, raw: Dict[str, Any]) -> Dict[str, Any]:
        """Canopy 数据归一化到 amazon_products 字段（全字段版）"""
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
            "seller_name": "seller_name", "seller_id": "seller_id",
            "manufacturer": "manufacturer", "model_number": "model_number",
            "part_number": "part_number", "upc": "upc", "ean": "ean",
            "color": "color", "size": "size",
            "weight": "weight", "dimensions": "dimensions",
            "domain": "domain",
            "is_in_stock": "is_in_stock",
            # 新增字段
            "monthly_sold": "monthly_sold",
            "weekly_sold": "weekly_sold",
            "annual_sold": "annual_sold",
            "stock_level": "stock_level",
            "review_velocity_30d": "review_velocity_30d",
            "material": "material",
            "style": "style",
            "package_quantity": "package_quantity",
            "binding": "binding",
            "product_group": "product_group",
            "frequently_bought_together": "frequently_bought_together",
        }
        result = {}
        for src_key, dst_key in mapping.items():
            if src_key in raw and raw[src_key] is not None:
                result[dst_key] = raw[src_key]

        # Canopy top_reviews → reviews 别名（Canopy 只返回 topReviews 作为评论）
        if "top_reviews" in result and result["top_reviews"] and "reviews" not in result:
            result["reviews"] = result["top_reviews"]

        return result

    # ── 字段级覆盖度维度检查 ──────────────────────────────────

    _COVERAGE_DIMS = {
        "has_basic_info": {"asin", "title", "brand"},
        "has_listing": {"feature_bullets", "main_image", "images"},
        "has_aplus": {"aplus_content"},
        "has_videos": {"videos_count"},
        "has_price": {"current_price"},
        "has_buybox": {"buybox_price", "buybox_seller_id"},
        "has_price_stats": {"avg_price_30d", "avg_price_90d"},
        "has_price_stats_extended": {"avg_price_180d", "avg_price_365d"},
        "has_bsr": {"current_bsr"},
        "has_bsr_stats": {"avg_bsr_30d", "avg_bsr_90d"},
        "has_bsr_stats_extended": {"avg_bsr_180d", "avg_bsr_365d"},
        "has_bsr_drops": {"sales_rank_drops_30d"},
        "has_bsr_drops_extended": {"sales_rank_drops_180d", "sales_rank_drops_365d"},
        "has_reviews_body": {"top_reviews"},
        "has_rating_breakdown": {"rating_breakdown"},
        "has_rating_history": {"rating_history"},
        "has_review_count_history": {"review_count_history"},
        "has_sales_estimate": {"monthly_sold"},
        "has_sales_estimate_extended": {"weekly_sold", "annual_sold"},
        "has_stock_level": {"stock_level"},
        "has_offer_counts": {"offer_count", "seller_count"},
        "has_fba_fee": {"fba_fee"},
        "has_referral_fee": {"referral_fee_percent"},
        "has_price_history": {"price_history"},
        "has_bsr_history": {"bsr_history"},
        "has_specifications": {"specifications"},
        "has_brand_store": {"brand_store"},
        "has_offer_detail": {"offer_count_fba", "offer_count_fbm"},
        "has_out_of_stock": {"out_of_stock_pct_30d"},
        "has_coupon_promo": {"coupon_text", "promotions_json"},
        "has_physical_dims": {"item_weight_g", "package_dimensions_mm"},
        "has_listing_safety": {"is_redirect_asin", "is_adult_product"},
        "has_shipping_info": {"shipping_origin", "is_eligible_for_free_shipping"},
        "has_buybox_detail": {"buybox_is_amazon", "buybox_is_prime_eligible"},
        "has_product_type": {"product_type_name"},
        "has_unit_count": {"unit_count_type"},
        "has_fulfillment": {"fulfillment"},
        "has_return_policy": {"return_policy"},
        "has_seller_profile": {"seller_profile"},
        "has_first_available": {"first_available"},
        "has_tracking_since": {"tracking_since"},
        "has_listed_since": {"listed_since"},
        "has_keywords": {"keywords_list"},
        "has_search_alias": {"search_alias"},
        "has_frequently_bought": {"frequently_bought_together"},
        "has_sponsored": {"sponsored_products"},
        "has_sales_rank_reference": {"sales_rank_reference_id"},
        "has_seller_ids_lowest": {"seller_ids_lowest_fba"},
        "has_buybox_eligible_counts": {"buybox_eligible_offer_counts"},
        "has_batteries": {"batteries_included"},
        "has_heat_sensitive": {"is_heat_sensitive"},
        "has_lightning_deal": {"lightning_deal_info"},
        "has_rich_product_description": {"rich_product_description"},
    }

    def _calc_coverage(self, product: Dict) -> Dict[str, bool]:
        """
        根据合并后的 product dict 计算覆盖度。
        True=有数据 / False=真没有 / 不在 dict 中=从未尝试
        """
        coverage = {}
        for dim, required_fields in self._COVERAGE_DIMS.items():
            has = all(product.get(f) is not None for f in required_fields)
            if has:
                coverage[dim] = True
            else:
                # 检查是否至少在某个源的原始数据中出现过（真没有 vs 未尝试）
                any_source_has = any(
                    product.get(f) is not None
                    for f in required_fields
                )
                if any_source_has:
                    coverage[dim] = True  # 部分有也算有
        return coverage

    def _calc_freshness(self, product: Dict, raw_sources: Dict[str, Dict]) -> Dict:
        """
        计算每个数据维度的新鲜度元信息：
        来源、端点、采集时间、cost。
        """
        now_iso = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        freshness = {}

        has_aplus = product.get("aplus_content") is not None
        has_buybox = product.get("buybox_price") is not None or product.get("buybox_seller_id") is not None

        # — 源头映射：每个维度来自哪个源的哪个端点 —
        _DIM_SOURCE = {
            "has_basic_info": ("keepa", "/product", 1, 0, 0),
            "has_listing": ("rainforest", "/product", 0, 1, 0),
            "has_aplus": ("rainforest", "/product", 0, 1, 0),
            "has_videos": ("rainforest", "/product", 0, 1, 0),
            "has_price": ("canopy", "/product", 0, 0, 1),
            "has_buybox": ("rainforest", "/product", 0, 1, 0),
            "has_price_stats": ("keepa", "/product", 1, 0, 0),
            "has_price_stats_extended": ("keepa", "/product", 1, 0, 0),
            "has_bsr": ("keepa", "/product", 1, 0, 0),
            "has_bsr_stats": ("keepa", "/product", 1, 0, 0),
            "has_bsr_stats_extended": ("keepa", "/product", 1, 0, 0),
            "has_bsr_drops": ("keepa", "/product", 1, 0, 0),
            "has_bsr_drops_extended": ("keepa", "/product", 1, 0, 0),
            "has_reviews_body": ("canopy", "/reviews", 0, 0, 1),
            "has_rating_breakdown": ("rainforest", "/product", 0, 1, 0),
            "has_rating_history": ("keepa", "/product", 1, 0, 0),
            "has_review_count_history": ("keepa", "/product", 1, 0, 0),
            "has_sales_estimate": ("canopy", "/sales", 0, 0, 1),
            "has_sales_estimate_extended": ("canopy", "/sales", 0, 0, 1),
            "has_stock_level": ("canopy", "/stock", 0, 0, 1),
            "has_offer_counts": ("keepa", "/product", 1, 0, 0),
            "has_fba_fee": ("keepa", "/product", 1, 0, 0),
            "has_referral_fee": ("keepa", "/product", 1, 0, 0),
            "has_price_history": ("keepa", "/product", 1, 0, 0),
            "has_bsr_history": ("keepa", "/product", 1, 0, 0),
            "has_specifications": ("rainforest", "/product", 0, 1, 0),
            "has_brand_store": ("keepa", "/product", 1, 0, 0),
            "has_offer_detail": ("keepa", "/product", 1, 0, 0),
            "has_out_of_stock": ("keepa", "/product", 1, 0, 0),
            "has_coupon_promo": ("keepa", "/product", 1, 0, 0),
            "has_physical_dims": ("keepa", "/product", 1, 0, 0),
            "has_listing_safety": ("keepa", "/product", 1, 0, 0),
            "has_shipping_info": ("keepa", "/product", 1, 0, 0),
            "has_buybox_detail": ("keepa", "/product", 1, 0, 0),
            "has_product_type": ("keepa", "/product", 1, 0, 0),
            "has_unit_count": ("keepa", "/product", 1, 0, 0),
            "has_fulfillment": ("rainforest", "/product", 0, 1, 0),
            "has_return_policy": ("rainforest", "/product", 0, 1, 0),
            "has_seller_profile": ("rainforest", "/product", 0, 1, 0),
            "has_first_available": ("rainforest", "/product", 0, 1, 0),
            "has_tracking_since": ("keepa", "/product", 1, 0, 0),
            "has_listed_since": ("keepa", "/product", 1, 0, 0),
            "has_keywords": ("rainforest", "/product", 0, 1, 0),
            "has_search_alias": ("rainforest", "/product", 0, 1, 0),
            "has_frequently_bought": ("rainforest", "/product", 0, 1, 0),
            "has_sponsored": ("rainforest", "/product", 0, 1, 0),
            "has_sales_rank_reference": ("keepa", "/product", 1, 0, 0),
            "has_seller_ids_lowest": ("keepa", "/product", 1, 0, 0),
            "has_buybox_eligible_counts": ("keepa", "/product", 1, 0, 0),
            "has_batteries": ("keepa", "/product", 1, 0, 0),
            "has_heat_sensitive": ("keepa", "/product", 1, 0, 0),
            "has_lightning_deal": ("keepa", "/product", 1, 0, 0),
            "has_rich_product_description": ("rainforest", "/product", 0, 1, 0),
        }

        for dim, (source, endpoint, k_cost, rf_cost, cn_cost) in _DIM_SOURCE.items():
            required = self._COVERAGE_DIMS.get(dim, set())
            has_data = any(product.get(f) is not None for f in required)
            if not has_data:
                continue

            entry = {
                "updated_at": now_iso,
                "source": source,
                "endpoint": endpoint,
                "cost": {},
            }
            if k_cost:
                entry["cost"]["keepa_token"] = k_cost
            if rf_cost:
                entry["cost"]["rf_credit"] = rf_cost
            if cn_cost:
                entry["cost"]["canopy_credit"] = cn_cost
            freshness[dim] = entry

        return freshness

    # ── 降级链配置 ───────────────────────────────────────────────

    _DEGRADATION_CHAINS = {
        "reviews_body": [
            ("canopy", "get_reviews"),            # 首选：Canopy /reviews
            ("rainforest", "get_product"),         # 降级：RF product.top_reviews
        ],
        "buybox_info": [
            ("rainforest", "get_product"),         # 首选：RF buybox_winner
            ("keepa", "query_products"),           # 降级：Keepa stats.buyBoxPrice
        ],
        "price": [
            ("keepa", "query_products"),           # 首选：Keepa csv[1]
            ("rainforest", "get_product"),         # 降级：RF buybox_winner.price
            ("canopy", "get_product"),             # 再降级：Canopy product
        ],
        "listing": [
            ("rainforest", "get_product"),         # 首选：RF listing
            ("canopy", "get_product"),             # 降级：Canopy listing
        ],
        "sales_estimate": [
            ("canopy", "get_sales"),               # 首选：Canopy /sales
        ],
        "stock_level": [
            ("canopy", "get_stock"),               # 首选：Canopy /stock
            ("rainforest", "get_product"),         # 降级：RF availability
        ],
        "rating_breakdown": [
            ("rainforest", "get_product"),         # 独占，无降级
        ],
        "bsr_history": [
            ("keepa", "query_products"),           # 独占
        ],
    }

    def _get_degradation_plan(self, needed_dims: List[str]) -> List[tuple]:
        """
        根据冷启动/刷新需要的维度，生成降级采集计划。
        返回 [(source, endpoint, dims), ...] 去重合并后的计划。
        """
        plan = []
        seen = set()
        for dim in needed_dims:
            chain = self._DEGRADATION_CHAINS.get(dim, [])
            for source, endpoint in chain:
                key = f"{source}:{endpoint}"
                if key not in seen:
                    seen.add(key)
                    plan.append((source, endpoint, [dim]))
                else:
                    # 合并到已有条目
                    for i, (s, e, dims) in enumerate(plan):
                        if s == source and e == endpoint:
                            plan[i] = (s, e, dims + [dim])
                            break
        return plan

    # ── 子表提取：Offer ─────────────────────────────────────────

    def _extract_offers_from_keepa(self, keepa_raw: Dict[str, Any], asin: str, domain: str) -> List[Dict]:
        """从 Keepa offers=20 响应提取 Offer 列表"""
        offers_raw = keepa_raw.get("offers") or keepa_raw.get("offerHistory") or []
        if not offers_raw:
            return []

        offers = []
        for o in offers_raw:
            if not isinstance(o, dict):
                continue
            offer = {
                "asin": asin,
                "domain": domain,
                "seller_id": o.get("sellerId") or o.get("seller_id", ""),
                "seller_name": o.get("sellerName") or o.get("seller_name", ""),
                "price": o.get("price"),
                "condition": o.get("condition", "NEW"),
                "is_amazon": o.get("isAmazon", False) or o.get("is_amazon", False),
                "is_fba": o.get("isFBA", False) or o.get("is_fba", False),
                "is_prime": o.get("isPrime", False) or o.get("is_prime", False),
                "is_preorder": o.get("isPreorder", False) or o.get("is_preorder", False),
                "is_warehouse_deal": o.get("isWarehouseDeal", False) or o.get("is_warehouse_deal", False),
                "is_shippable": o.get("isShippable", True),
                "is_map": o.get("isMAP", False) or o.get("is_map", False),
                "min_order_qty": o.get("minOrderQty", 1) or o.get("min_order_qty", 1),
                "ships_from_china": o.get("shipsFromChina", False) or o.get("ships_from_china", False),
                "offer_csv": o.get("offerCSV") or o.get("offer_csv") or o.get("csv"),
            }
            # 去空 buyerbox_winner
            if offer["seller_id"]:
                offers.append(offer)
        return offers

    def _extract_variations_from_keepa(self, keepa_raw: Dict[str, Any], asin: str, domain: str) -> List[Dict]:
        """从 Keepa variationCSV 提取变体列表"""
        variation_csv = keepa_raw.get("variationCSV") or keepa_raw.get("variation_csv") or ""
        if not variation_csv:
            return []

        # variationCSV 格式: parentASIN|variationASIN|attributesCSV
        variations = []
        rows = variation_csv.split(";") if ";" in variation_csv else [variation_csv]
        for row in rows:
            parts = row.split("|") if "|" in row else []
            if len(parts) >= 2:
                var_asin = parts[1].strip()
                if var_asin and var_asin != asin:
                    attrs = {}
                    if len(parts) >= 3:
                        attr_pairs = parts[2].strip().split(",")
                        for pair in attr_pairs:
                            if "=" in pair:
                                k, v = pair.split("=", 1)
                                attrs[k.strip()] = v.strip()
                    variations.append({
                        "asin": asin,
                        "domain": domain,
                        "variant_asin": var_asin,
                        "attributes": attrs if attrs else None,
                        "image": None,
                    })
        return variations

    def _extract_variations_from_rainforest(self, rf_raw: Dict[str, Any], asin: str, domain: str) -> List[Dict]:
        """从 Rainforest variations 列表提取变体"""
        variations_raw = rf_raw.get("variations") or []
        if not variations_raw:
            return []

        variations = []
        for v in variations_raw:
            if not isinstance(v, dict):
                continue
            var_asin = v.get("asin", "")
            if var_asin and var_asin != asin:
                attrs = v.get("dimensions", "")
                variations.append({
                    "asin": asin,
                    "domain": domain,
                    "variant_asin": var_asin,
                    "title": v.get("title"),
                    "is_current": v.get("is_current", False),
                    "attributes": attrs if attrs else None,
                    "image": v.get("image"),
                })
        return variations

    # ── 子表加载 ──

    async def _load_offers(self, asin: str, domain: str, offers: List[Dict]) -> int:
        """批量加载 Offer 到子表"""
        if not offers:
            return 0
        count = 0
        async with self.repo.db as session:
            repo = AmazonProductRepository(session)
            count = await repo.bulk_upsert_offers(asin, domain, offers)
        return count

    async def _load_variations(self, asin: str, domain: str, variations: List[Dict]) -> int:
        """批量加载变体到子表"""
        if not variations:
            return 0
        count = 0
        async with self.repo.db as session:
            repo = AmazonProductRepository(session)
            count = await repo.bulk_upsert_variations(asin, domain, variations)
        return count

    # ── 冷启动（4 阶段递进） ────────────────────────────────────

    async def cold_start(self, asin: str, domain: str = "US") -> Optional[Dict]:
        """
        4 阶段递进式冷启动。

        Phase 1 (必选): Keepa /product — 验证 ASIN 存在 + 历史曲线
        Phase 2 (必选): Rainforest /product — listing + buy box + A+ + 评分
        Phase 3 (可选): Canopy /product + /reviews + /sales + /stock
        Phase 4 (可选): Keepa offers=20 — Offer 阵列 + FBA 费用
        """
        started_at = datetime.now(timezone.utc)
        logger.info(f"[ColdStart] Begin {asin}@{domain}")

        # Phase 1: Keepa（必选）
        logger.info(f"[ColdStart] Phase 1: Keepa /product for {asin}")
        try:
            keepa_result = await self.keepa.async_query_products([asin], domain, history=True, stats=180)
            if not keepa_result:
                logger.warning(f"[ColdStart] Phase 1 failed: {asin} not found on Keepa")
                return None
            kp_raw = keepa_result[0]
            kp_raw["domain"] = domain
        except KError as e:
            logger.warning(f"[ColdStart] Phase 1 error: {e}")
            return None

        # Phase 2: Rainforest（必选）
        logger.info(f"[ColdStart] Phase 2: Rainforest /product for {asin}")
        rf_raw = {}
        try:
            rf_domain = keepa_to_rf_domain(domain)
            rf_result = await self.rainforest.async_get_product(asin, rf_domain)
            if rf_result:
                rf_result["domain"] = domain
                rf_raw = rf_result
        except RFError as e:
            logger.warning(f"[ColdStart] Phase 2 failed (degraded): {e}")

        # Phase 3: Canopy（可选）
        logger.info(f"[ColdStart] Phase 3: Canopy for {asin}")
        cn_raw = {}
        try:
            cn_domain = keepa_to_rf_domain(domain)
            cn_result = await self.canopy.async_get_product(asin, cn_domain)
            if cn_result:
                cn_result["domain"] = domain
                cn_raw = cn_result
        except CNError as e:
            logger.warning(f"[ColdStart] Phase 3 failed (optional): {e}")

        # Phase 4: Keepa offers=20（可选）
        logger.info(f"[ColdStart] Phase 4: Keepa offers for {asin}")
        kp_offers_raw = {}
        try:
            offers_result = await self.keepa.async_query_products([asin], domain, offers=20)
            if offers_result:
                kp_offers_raw = offers_result[0]
                # 合并 offers 数据到 keepa 主数据
                if kp_offers_raw:
                    for key in ("offerCount", "offerCountFBA", "buyboxSellerId",
                                "buyboxIsFBA", "fbaFee", "referralFeePercent",
                                "salesRankDrops30", "salesRankDrops90"):
                        if key in kp_offers_raw and kp_offers_raw[key] is not None:
                            kp_raw[key] = kp_offers_raw[key]
        except Exception as e:
            logger.warning(f"[ColdStart] Phase 4 failed (optional): {e}")

        # Normalize
        kp_norm = self._normalize_keepa(kp_raw)
        rf_norm = self._normalize_rainforest(rf_raw)
        cn_norm = self._normalize_canopy(cn_raw)

        # Merge + coverage + freshness
        raw_by_source = {"keepa": kp_raw}
        if rf_raw:
            raw_by_source["rainforest"] = rf_raw
        merged = self._merge_products(
            {asin: kp_norm}, {asin: rf_norm}, {asin: cn_norm},
            raw_by_source=raw_by_source,
        )
        product_data = merged.get(asin, {})

        # 标记降级
        if not rf_raw:
            if "coverage_map" in product_data:
                for dim in ("has_aplus", "has_videos", "has_rating_breakdown"):
                    if isinstance(product_data["coverage_map"], dict):
                        product_data["coverage_map"][dim] = {
                            "available": False,
                            "degraded": True,
                            "reason": "rainforest_product_unavailable"
                        }
            coverage_map = product_data.get("coverage_map", {})
            if isinstance(coverage_map, dict):
                coverage_map.setdefault("has_listing", False)

        # 写入 DB（含子表）
        async with self.repo.db as session:
            repo = AmazonProductRepository(session)
            for s in product_data.get("data_source", ["keepa"]):
                await repo.upsert(product_data, s)

        # 写入子表
        if kp_offers_raw.get("offers"):
            offers = self._extract_offers_from_keepa(kp_offers_raw, asin, domain)
            await self._load_offers(asin, domain, offers)
        variations = self._extract_variations_from_keepa(kp_raw, asin, domain)
        if rf_raw:
            rf_vars = self._extract_variations_from_rainforest(rf_raw, asin, domain)
            variations.extend(rf_vars)
        await self._load_variations(asin, domain, variations)

        elapsed = (datetime.now(timezone.utc) - started_at).total_seconds()
        logger.info(f"[ColdStart] Done {asin}@{domain} in {elapsed:.1f}s (sources={product_data.get('data_source', [])})")

        return product_data

    def _merge_products(
        self, keepa_data: Dict, rf_data: Dict, cn_data: Dict,
        raw_by_source: Dict[str, Dict] = None,
    ) -> Dict[str, Dict]:
        """
        按字段级优先级合并三源数据为一个统一的 product dict。
        规则：
          - 独占字段（如 price_history）只来自一个源，直接保留
          - 共享字段按 _SOURCE_PRIORITY 中定义的源优先级写入
          - 三源都有的字段，优先级最高源的覆盖其他
        新增：
          - 写入 coverage_map + freshness_map
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
                preferred = _SOURCE_PRIORITY.get(field)

                val = None
                if preferred == "keepa":
                    val = kp.get(field)
                elif preferred == "rainforest":
                    val = rf.get(field)
                elif preferred == "canopy":
                    val = cn.get(field)
                else:
                    for src in [kp, rf, cn]:
                        if field in src and src[field] is not None:
                            val = src[field]
                            break

                if val is not None:
                    product[field] = val

            # ── coverage_map + freshness_map ──
            product["coverage_map"] = self._calc_coverage(product)
            product["freshness_map"] = self._calc_freshness(product, raw_by_source or {})

            # ── 从 offers 原始数据推导卖家生态字段 ──
            raw_kp = (raw_by_source or {}).get("keepa", {})
            offers_raw = raw_kp.get("offers", []) if isinstance(raw_kp, dict) else []
            if offers_raw and isinstance(offers_raw, list):
                has_amazon = any(o.get("isAmazon") or o.get("is_amazon") for o in offers_raw
                                 if isinstance(o, dict))
                has_china = any(o.get("shipsFromChina") or o.get("ships_from_china") for o in offers_raw
                                if isinstance(o, dict))
                # Top seller: lowest price FBA offer
                fba_offers = [o for o in offers_raw if isinstance(o, dict) and
                             (o.get("isFBA") or o.get("is_fba")) and o.get("price")]
                top_seller = None
                if fba_offers:
                    top_seller = min(fba_offers, key=lambda o: o.get("price", 999999))
                if has_amazon:
                    product["has_amazon_selling"] = True
                if has_china:
                    product["has_china_sellers"] = True
                if top_seller:
                    tid = top_seller.get("sellerId") or top_seller.get("seller_id")
                    tname = top_seller.get("sellerName") or top_seller.get("seller_name")
                    if tid:
                        product["top_seller_id"] = tid
                    if tname:
                        product["top_seller_name"] = tname

            # ── 数据一致性校验 ──
            consistency = validate_consistency(kp, rf, cn)
            if consistency:
                product["_consistency"] = consistency
                # 把不一致标记写入 coverage_map
                cm = product.get("coverage_map", {})
                if isinstance(cm, dict):
                    cm["_consistency"] = consistency
                    for field, check in consistency.items():
                        if isinstance(check, dict) and check.get("divergent"):
                            logger.warning(
                                f"[Consistency] {asin} {field} 不一致: {check.get('alert', '')}"
                            )

            # ── raw_payload: 三源原始数据快照 ──
            raw_sources = raw_by_source or {}
            raw_payload = {}
            for src_name in ("keepa", "rainforest", "canopy"):
                src_data = raw_sources.get(src_name, {})
                asin_data = src_data.get(asin) if isinstance(src_data, dict) else None
                if asin_data:
                    # 精简：只保留原始响应顶层 key，去掉超大 csv 数组
                    cleaned = {}
                    for k, v in asin_data.items():
                        if k in ("csv", "offers", "variationCSV", "imagesCSV"):
                            continue  # 这些已在具体字段中，不重复存
                        cleaned[k] = v
                    raw_payload[f"{src_name}_product"] = cleaned

            if raw_payload:
                product["raw_payload"] = raw_payload

            merged[asin] = product

        return merged

    # ── Load ──

    async def _load_asin(self, asin: str, product_data: Dict, merged: Dict) -> bool:
        """加载单个 ASIN 数据到数据库，写入变更检测 + 异常检测"""
        try:
            # 1. 获取旧数据（用于变更检测）
            old_product = await self.repo.get_by_asin(asin, product_data.get("domain", "US"))
            old_dict = {}
            if old_product:
                from sqlalchemy.orm import class_mapper
                for col in class_mapper(type(old_product)).mapped_table.columns:
                    val = getattr(old_product, col.name, None)
                    if val is not None:
                        old_dict[col.name] = val

            # 2. 更新对应源的数据
            sources = product_data.get("data_source", [])
            for s in sources:
                if s == "keepa":
                    await self.repo.upsert(product_data, "keepa")
                elif s == "rainforest":
                    await self.repo.upsert(product_data, "rainforest")
                elif s == "canopy":
                    await self.repo.upsert(product_data, "canopy")

            # 3. 变更检测（仅在旧数据存在时对比）
            if old_dict and merged:
                changes = detect_changes(old_dict, product_data, TRACKED_FIELDS)
                if changes:
                    domain = product_data.get("domain", "US")
                    entries = changes_to_log_entries(asin, domain, changes)
                    for entry in entries:
                        try:
                            await self.repo.create_change_log(entry)
                        except Exception as e:
                            logger.warning(f"Change log write failed for {asin}.{entry['field']}: {e}")

                    # 4. 异常检测
                    anomalies = detect_anomalies(changes)
                    for anomaly in anomalies:
                        try:
                            await self.repo.create_anomaly_log({
                                "asin": asin,
                                "domain": domain,
                                "field": anomaly["field"],
                                "old_value": anomaly.get("old_value"),
                                "new_value": anomaly.get("new_value"),
                                "delta_pct": anomaly.get("delta_pct"),
                                "alert_type": anomaly["alert_type"],
                                "severity": anomaly["severity"],
                                "description": anomaly.get("description"),
                            })
                        except Exception as e:
                            logger.warning(f"Anomaly log write failed for {asin}.{anomaly['field']}: {e}")

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
                rf_domain = keepa_to_rf_domain(domain)
                tasks.append(("rainforest", self.extract_rainforest(asins, rf_domain)))
            if "canopy" in sources:
                cn_domain = keepa_to_rf_domain(domain)
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
            raw_by_source = {}
            if keepa_raw:
                raw_by_source["keepa"] = keepa_raw
            if rf_raw:
                raw_by_source["rainforest"] = rf_raw
            if cn_raw:
                raw_by_source["canopy"] = cn_raw
            merged = self._merge_products(keepa_norm, rf_norm, cn_norm, raw_by_source=raw_by_source)

            # 4. Load
            total, success, failed = await self.load_products(merged)

            # 5. 计算重要性评分
            if calc_importance:
                for asin in merged:
                    try:
                        await self.repo.recalc_importance(asin, domain)
                    except Exception as e:
                        logger.warning(f"Importance calc failed for {asin}: {e}")

            # 6. 度量 + 结构化日志
            duration = (datetime.now(timezone.utc) - started_at).total_seconds()
            etl_run_duration.observe(duration)
            etl_asins_processed.labels(status="success").inc(success)
            if failed:
                etl_asins_processed.labels(status="failed").inc(len(failed))
            structured_log("etl_run_completed",
                run_id=self.run_id,
                asins_total=result["asins_total"],
                asins_success=success,
                asins_failed=len(failed),
                keepa_consumed=result["keepa_consumed"],
                rainforest_consumed=result["rainforest_consumed"],
                canopy_consumed=result["canopy_consumed"],
                duration_s=round(duration, 1),
                sources=",".join(sources) if sources else "none",
            )

            # 7. 记录 ETL 日志
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


# ── 三源域映射 ──────────────────────────────────────────────────────
# Keepa 用 US/DE/JP 代码；Rainforest/Canopy 用 amazon.com/amazon.de

_KEEPA_TO_RF_MAP = {
    "US": "amazon.com", "GB": "amazon.co.uk", "DE": "amazon.de",
    "FR": "amazon.fr", "JP": "amazon.co.jp", "CA": "amazon.ca",
    "IT": "amazon.it", "ES": "amazon.es", "IN": "amazon.in",
    "MX": "amazon.com.mx", "BR": "amazon.com.br", "AU": "amazon.com.au",
    "NL": "amazon.nl", "SG": "amazon.sg", "AE": "amazon.ae",
    "SA": "amazon.sa", "TR": "amazon.com.tr", "SE": "amazon.se",
    "PL": "amazon.pl",
}
_RF_TO_KEEPA_MAP = {v: k for k, v in _KEEPA_TO_RF_MAP.items()}


def keepa_to_rf_domain(keepa_domain: str) -> str:
    """Keepa 的 US → Rainforest 的 amazon.com"""
    return _KEEPA_TO_RF_MAP.get(keepa_domain.upper(), "amazon.com")


def rf_to_keepa_domain(rf_domain: str) -> str:
    """Rainforest 的 amazon.com → Keepa 的 US"""
    return _RF_TO_KEEPA_MAP.get(rf_domain, "US")


# ── 数据一致性校验 ──────────────────────────────────────────────────

_PRICE_FIELDS = ["current_price", "buybox_price", "list_price"]


def validate_consistency(keepa: Dict, rainforest: Dict, canopy: Dict) -> Dict:
    """
    校验三源数据的关键字段一致性。

    Returns:
        {field: {keepa: ..., rainforest: ..., canopy: ..., divergent: bool, alert: str}}
    """
    checks = {}

    for field in _PRICE_FIELDS:
        prices = {
            "keepa": keepa.get(field),
            "rainforest": rainforest.get(field),
            "canopy": canopy.get(field),
        }
        valid = [v for v in prices.values() if v and isinstance(v, (int, float))]
        if len(valid) >= 2:
            avg = sum(valid) / len(valid)
            for source, price in prices.items():
                if price and isinstance(price, (int, float)) and abs(price - avg) / max(avg, 0.01) > 0.2:
                    checks[field] = {
                        "values": prices, "divergent": True,
                        "alert": f"{source} {field}={price} deviates >20% from avg={avg:.2f}",
                    }
                    break
        if field not in checks:
            checks[field] = {"values": prices, "divergent": False}

    old_bsr = {"keepa": keepa.get("current_bsr"), "rainforest": rainforest.get("current_bsr")}
    valid_bsr = [v for v in old_bsr.values() if v and isinstance(v, (int, float))]
    if len(valid_bsr) >= 2 and max(valid_bsr) / max(min(valid_bsr), 1) > 3:
        checks["current_bsr"] = {
            "values": old_bsr, "divergent": True,
            "alert": f"BSR differs >3x between sources: {old_bsr}",
        }

    return checks