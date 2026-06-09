"""
字段注册表 — 指标名 ↔ 数据库列名映射（三表统一）

LLM 用友好的指标名（如 "price"、"rating"、"bsr"），
Engine 通过此注册表映射到具体数据库列。

设计：
- COMMON_METRICS: LLM 最常查询的指标，有友好别名
- ALL_PRODUCT_FIELDS: amazon_products 全部列名（动态安全兜底）
- entity_type → ORM model + 主键 + 可排序列
"""

from typing import Dict, List, Optional, Set, Tuple, Any
from backend.data.models.amazon_product import AmazonProduct
from backend.data.models.amazon_product_offer import AmazonProductOffer
from backend.data.models.amazon_product_variation import AmazonProductVariation

# ── 常用指标别名 → 数据库列名 ──
# key: LLM 可以写的友好名（不分大小写匹配）
# value: (数据库列名, 类型说明)
COMMON_METRICS: Dict[str, Tuple[str, str]] = {
    # ── 基础 ──
    "asin": ("asin", "ASIN"),
    "title": ("title", "商品标题"),
    "brand": ("brand", "品牌名"),
    "domain": ("domain", "站点"),
    "product_type": ("product_type", "商品类型"),
    "parent_asin": ("parent_asin", "父 ASIN"),

    # ── 价格 ──
    "price": ("current_price", "当前售价"),
    "current_price": ("current_price", "当前售价"),
    "list_price": ("list_price", "标价/建议零售价"),
    "buybox_price": ("buybox_price", "BuyBox 价格"),
    "avg_price_30d": ("avg_price_30d", "30 天均价"),
    "avg_price_90d": ("avg_price_90d", "90 天均价"),
    "avg_price_180d": ("avg_price_180d", "180 天均价"),
    "avg_price_365d": ("avg_price_365d", "365 天均价"),
    "min_price_30d": ("min_price_30d", "30 天最低价"),
    "max_price_90d": ("max_price_90d", "90 天最高价"),
    "has_coupon": ("has_coupon", "是否有 Coupon"),
    "unit_price": ("unit_price", "单价（如 $10.99/kg）"),

    # ── BSR ──
    "bsr": ("current_bsr", "当前 BSR"),
    "current_bsr": ("current_bsr", "当前 BSR"),
    "bsr_category": ("bsr_category", "BSR 类目名"),
    "avg_bsr_30d": ("avg_bsr_30d", "30 天平均 BSR"),
    "avg_bsr_90d": ("avg_bsr_90d", "90 天平均 BSR"),
    "avg_bsr_180d": ("avg_bsr_180d", "180 天平均 BSR"),
    "bsr_trend": ("bsr_trend", "BSR 趋势（up/down/stable）"),
    "sales_rank_drops_30d": ("sales_rank_drops_30d", "30 天 BSR 下降次数"),

    # ── 销量 ──
    "weekly_sold": ("weekly_sold", "周销量"),
    "monthly_sold": ("monthly_sold", "月销量"),
    "annual_sold": ("annual_sold", "年销量"),
    "recent_sales": ("recent_sales", "近期销量描述"),

    # ── 评论/评分 ──
    "rating": ("rating", "评分"),
    "review_count": ("review_count", "评论数"),
    "rating_breakdown": ("rating_breakdown", "评分分布（各星级占比）"),
    "review_velocity_30d": ("review_velocity_30d", "30 天新增评论数"),
    "top_reviews": ("top_reviews", "精选评论"),
    "customers_say": ("customers_say", "客户说（AI 摘要）"),
    "amazons_choice": ("amazons_choice", "Amazon's Choice 标签"),

    # ── Offer/竞争 ──
    "seller_count": ("seller_count", "卖家数量"),
    "offer_count": ("offer_count", "Offer 数量"),
    "offer_count_fba": ("offer_count_fba", "FBA Offer 数量"),
    "offer_count_fbm": ("offer_count_fbm", "FBM Offer 数量"),
    "is_fba": ("is_fba", "是否 FBA"),
    "is_prime": ("is_prime", "是否 Prime"),
    "buybox_seller_name": ("buybox_seller_name", "BuyBox 卖家名"),

    # ── 卖家生态 ──
    "top_seller_name": ("top_seller_name", "销量最大卖家"),
    "has_amazon_selling": ("has_amazon_selling", "Amazon 自营在售"),
    "has_china_sellers": ("has_china_sellers", "有中国卖家"),

    # ── 履约/库存 ──
    "fba_fee": ("fba_fee", "FBA 费用"),
    "referral_fee_percent": ("referral_fee_percent", "佣金比例"),
    "stock_level": ("stock_level", "库存水平"),
    "is_in_stock": ("is_in_stock", "是否有货"),
    "out_of_stock_pct_30d": ("out_of_stock_pct_30d", "30 天缺货率"),

    # ── Listing 内容 ──
    "feature_bullets": ("feature_bullets", "卖点列表"),
    "description": ("description", "商品描述"),
    "specifications": ("specifications", "规格参数"),
    "main_image": ("main_image", "主图 URL"),
    "images_count": ("images_count", "图片数量"),
    "videos_count": ("videos_count", "视频数量"),
    "dimensions": ("dimensions", "尺寸描述"),
    "color": ("color", "颜色"),
    "size": ("size", "尺码"),
    "material": ("material", "材质"),
    "category_name": ("category_name", "品类名"),
    "keywords_list": ("keywords_list", "关键词列表"),

    # ── 历史序列 ──
    "price_history": ("price_history", "价格历史（[[ts, price], ...]）"),
    "bsr_history": ("bsr_history", "BSR 历史（[[ts, bsr], ...]）"),
    "rating_history": ("rating_history", "评分历史（JSON）"),
    "review_count_history": ("review_count_history", "评论数历史（JSON）"),

    # ── 元信息 ──
    "importance_score": ("importance_score", "重要度评分"),
    "importance_tier": ("importance_tier", "重要度等级"),
    "lifecycle_status": ("lifecycle_status", "生命周期状态"),
    "listed_since": ("listed_since", "上架时间"),
    "data_source": ("data_source", "数据来源信息"),

    # ── 变体 ──
    "variations": ("variations", "变体信息（JSON）"),
    "child_asins": ("child_asins", "子 ASIN 列表"),
}

# ── Offer 表指标 ──
OFFER_METRICS: Dict[str, Tuple[str, str]] = {
    "seller_id": ("seller_id", "卖家 ID"),
    "seller_name": ("seller_name", "卖家名"),
    "seller_rating": ("seller_rating", "卖家评分"),
    "seller_ratings_total": ("seller_ratings_total", "卖家总评分"),
    "price": ("price", "Offer 价格"),
    "shipping": ("shipping", "运费"),
    "condition": ("condition", "商品成色"),
    "is_fba": ("is_fba", "是否 FBA"),
    "is_prime": ("is_prime", "是否 Prime"),
    "buybox_winner": ("buybox_winner", "是否 BuyBox 赢家"),
    "availability": ("availability", "库存状态"),
    "rating": ("rating", "评分"),
    "review_count": ("review_count", "评论数"),
    "ships_from_china": ("ships_from_china", "是否中国发货"),
    "is_amazon": ("is_amazon", "是否 Amazon 自营"),
    "last_seen": ("last_seen", "最后可见时间"),
}

# ── Variation 表指标 ──
VARIATION_METRICS: Dict[str, Tuple[str, str]] = {
    "variant_asin": ("variant_asin", "变体 ASIN"),
    "title": ("title", "变体标题"),
    "attributes": ("attributes", "变体属性（如颜色、尺寸）"),
    "price": ("price", "变体价格"),
    "rating": ("rating", "变体评分"),
    "review_count": ("review_count", "变体评论数"),
    "is_prime": ("is_prime", "是否 Prime"),
    "is_fba": ("is_fba", "是否 FBA"),
    "is_in_stock": ("is_in_stock", "是否有货"),
    "availability": ("availability", "库存状态"),
}

# ── 实体类型 → 模型映射 ──
ENTITY_MODEL_MAP = {
    "product": AmazonProduct,
    "offer": AmazonProductOffer,
    "variation": AmazonProductVariation,
}

# ── 实体类型 → 指标注册表 ──
ENTITY_METRICS_MAP = {
    "product": COMMON_METRICS,
    "offer": OFFER_METRICS,
    "variation": VARIATION_METRICS,
}

# ── 可排序的列（用于 search/sort_by） ──
SORTABLE_COLUMNS: Dict[str, Set[str]] = {
    "product": {
        "current_price", "rating", "review_count", "current_bsr",
        "monthly_sold", "weekly_sold", "annual_sold",
        "avg_bsr_30d", "avg_price_30d", "min_price_30d",
        "importance_score", "seller_count", "offer_count",
        "review_velocity_30d", "updated_at",
    },
    "offer": {
        "price", "shipping", "seller_rating", "seller_ratings_total",
        "rating", "review_count",
    },
    "variation": {
        "price", "rating", "review_count",
    },
}

# ── 安全聚合函数 ──
ALLOWED_AGGREGATIONS = {"avg", "sum", "count", "min", "max"}

# ── 安全 GROUP BY 列 ──
ALLOWED_GROUP_BY = {
    "brand", "category_name", "product_type_name", "bsr_category",
    "color", "size", "material", "seller_name", "is_fba", "is_prime",
    "product_type", "importance_tier", "lifecycle_status",
    "has_amazon_selling", "has_china_sellers",
}


def get_model_columns(entity_type: str) -> Set[str]:
    """获取指定实体类型的所有数据库列名（安全兜底用）"""
    model = ENTITY_MODEL_MAP.get(entity_type)
    if model is None:
        return set()
    return {c.name for c in model.__table__.columns}


def resolve_metrics(
    entity_type: str,
    metric_names: Optional[List[str]] = None,
) -> List[str]:
    """
    解析 LLM 传入的指标名 → 数据库列名列表

    Args:
        entity_type: "product" | "offer" | "variation"
        metric_names: LLM 指定的指标名，None 表示全部

    Returns:
        数据库列名列表
    """
    metrics_map = ENTITY_METRICS_MAP.get(entity_type, COMMON_METRICS)
    all_columns = get_model_columns(entity_type)

    if not metric_names:
        # 返回所有常用指标
        return list(metrics_map.keys())

    resolved = []
    for name in metric_names:
        lower = name.lower().strip()
        if lower in metrics_map:
            resolved.append(metrics_map[lower][0])
        elif lower in all_columns:
            # 直接传入数据库列名
            resolved.append(lower)
        # 不在注册表中也不在列中的指标 → 跳过（不报错，返回 None 由调用方处理）

    return resolved


def get_metric_description(entity_type: str) -> str:
    """生成指标说明文本（供 tool description 使用）"""
    metrics_map = ENTITY_METRICS_MAP.get(entity_type, COMMON_METRICS)
    lines = ["可用指标："]
    keys = list(metrics_map.keys())
    # 每 5 个一行
    for i in range(0, len(keys), 5):
        chunk = keys[i:i + 5]
        lines.append("  " + ", ".join(chunk))
    return "\n".join(lines)