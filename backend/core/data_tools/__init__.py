"""
Data Tools — 5 个全局抽象数据访问工具（LangChain @tool 函数）

这些是 LLM 可见的唯一 5 个数据工具。内部调用 DataQueryEngine 的动态查询。

Tool 列表：
  1. get_entity_details    — 单实体详情（按需选字段）
  2. compare_entities      — 多实体对比
  3. search_entities       — 条件筛选搜索
  4. get_trends            — 时间序列趋势
  5. analyze_custom        — 自定义聚合（安全版 GROUP BY）

设计原则：
  - 每个工具都是 LLM 的一次调用，内部处理所有数据库交互
  - 字段缺失保留 null，不伪造/估算
  - 结果格式化为 LLM 易读的文本 + 结构化数据
"""

import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from langchain_core.tools import tool

from backend.core.data_tools.engine import get_query_engine, DataQueryEngine

logger = logging.getLogger(__name__)

# ── 字段选择帮助 ──

_METRICS_HELP = (
    "可查询的指标（按场景）：\n"
    "  - 基础: asin, title, brand, category_name, product_type\n"
    "  - 价格: current_price, list_price, buybox_price, avg_price_30d/90d/180d/365d, min_price_30d\n"
    "  - BSR: current_bsr, avg_bsr_30d/90d/180d, bsr_trend\n"
    "  - 销量: weekly_sold, monthly_sold, annual_sold\n"
    "  - 评论: rating, review_count, review_velocity_30d, rating_breakdown\n"
    "  - 竞争: seller_count, offer_count, offer_count_fba, is_fba, is_prime\n"
    "  - 卖家: top_seller_name, has_amazon_selling, has_china_sellers\n"
    "  - 履约: fba_fee, stock_level, is_in_stock, out_of_stock_pct_30d\n"
    "  - Listing: feature_bullets, description, color, size, material, images_count\n"
    "  - 历史: price_history, bsr_history, rating_history\n"
    "\n"
    "不传 metrics 参数将返回所有常用指标的有限集合。"
)


def _entity_type_desc() -> str:
    return (
        '实体类型: "product" (商品主表 — 180+ 字段), '
        '"offer" (卖家报价 — 每个卖家一条), '
        '"variation" (变体 — 每个变体一条)'
    )


# ── 1. 单实体详情 ──


@tool
async def get_entity_details(
    entity_type: str,
    entity_id: str,
    metrics: Optional[List[str]] = None,
    domain: str = "US",
) -> str:
    """
    查询单个商品/Offer/变体的详细信息。

    一次调用可覆盖 180+ 字段，按需选择 metrics 参数来减少 token 消耗。
    这是最常用的工具——先查核心字段，如需更多再查。

    Args:
        entity_type: "product" | "offer" | "variation"
        entity_id: ASIN（产品查询）或 seller_id（Offer 查询）或 variant_asin（变体查询）
        metrics: 需要的指标列表，如 ["current_price", "rating", "weekly_sold"]。不传则返回常用字段。
        domain: 站点，默认 "US"
    """
    try:
        engine = get_query_engine()
        data = await engine.fetch_details(entity_type, entity_id, metrics, domain)

        # ★ DB 没有 → 走 DataProvider 冷启动（调 API → 存 DB → 返回）
        if data is None and entity_type == "product":
            logger.info(f"[get_entity_details] DB 未命中，触发冷启动: {entity_id}")
            from backend.aqueduct.data_provider import DataProvider
            provider = DataProvider()
            raw = await provider.get_product_blocking(entity_id, domain)
            if raw:
                # 冷启动后 DB 已有数据，再查一次
                data = await engine.fetch_details(entity_type, entity_id, metrics, domain)

        if data is None:
            return f"未找到 {entity_type}: {entity_id}"

        lines = [f"📋 {entity_type.upper()} [{entity_id}]"]
        for key, value in data.items():
            if key in ("id",):
                continue
            if value is None:
                lines.append(f"  {key}: null")
            elif isinstance(value, (dict, list)):
                try:
                    lines.append(f"  {key}: {json.dumps(value, ensure_ascii=False)[:200]}")
                except Exception:
                    lines.append(f"  {key}: {str(value)[:200]}")
            elif isinstance(value, datetime):
                lines.append(f"  {key}: {value.isoformat()}")
            else:
                lines.append(f"  {key}: {value}")

        return "\n".join(lines)
    except Exception as e:
        logger.error(f"[get_entity_details] 失败: {e}", exc_info=True)
        return f"查询失败: {e}"


# ── 2. 多实体对比 ──


@tool
async def compare_entities(
    entity_type: str,
    entity_ids: List[str],
    metrics: Optional[List[str]] = None,
    domain: str = "US",
) -> str:
    """
    对比多个商品/Offer/变体的关键指标。

    用一次调用代替多次 get_entity_details，结果自动以表格对比格式呈现。
    适用于：竞品分析、价格对比、多 ASIN 横向评估。

    Args:
        entity_type: "product" | "offer" | "variation"
        entity_ids: ASIN/ID 列表，最多 20 个
        metrics: 需要对比的指标列表，如 ["current_price", "rating", "monthly_sold", "seller_count"]
        domain: 站点，默认 "US"
    """
    if len(entity_ids) > 20:
        return f"最多对比 20 个实体，收到 {len(entity_ids)} 个"

    try:
        engine = get_query_engine()
        result = await engine.compare(entity_type, entity_ids, metrics, domain)

        if not result["data"]:
            return result["summary"]

        # 结构化表格
        lines = [f"📊 对比: {', '.join(result['entity_ids'][:10])}"]
        if len(result['entity_ids']) > 10:
            lines.append(f"  (还有 {len(result['entity_ids']) - 10} 个...)")

        # 选用户指定的 metrics 字段优先展示
        display_fields = metrics[:15] if metrics else result["fields"][:15]

        # header
        header = f"{'字段':<25}"
        for eid in result["entity_ids"][:8]:
            header += f" | {eid:<18}"
        if len(result["entity_ids"]) > 8:
            header += " | ..."
        lines.append("")
        lines.append(header)
        lines.append("-" * len(header))

        for field in display_fields:
            row = f"{field:<25}"
            for eid in result["entity_ids"][:8]:
                val = result["data"].get(eid, {}).get(field)
                if val is None:
                    row += " | {'null':^18}"
                elif isinstance(val, float):
                    row += f" | {val:<18.2f}"
                elif isinstance(val, (dict, list)):
                    row += f" | {'JSON':<18}"
                else:
                    s = str(val)
                    row += f" | {s[:18]:<18}"
            if len(result["entity_ids"]) > 8:
                row += " | ..."
            lines.append(row)

        return "\n".join(lines)
    except Exception as e:
        logger.error(f"[compare_entities] 失败: {e}", exc_info=True)
        return f"对比查询失败: {e}"


# ── 3. 条件筛选搜索 ──


@tool
async def search_entities(
    entity_type: str,
    filters: Optional[Dict[str, Any]] = None,
    metrics: Optional[List[str]] = None,
    sort_by: Optional[str] = None,
    sort_order: str = "desc",
    limit: int = 20,
    offset: int = 0,
    domain: str = "US",
) -> str:
    """
    按条件筛选和搜索商品/Offer/变体。

    支持多维筛选：价格区间、评分、BSR、销量、是否 FBA/Prime、品类模糊匹配等。
    这是数据分析的第一步——先搜索再深入。

    Args:
        entity_type: "product" | "offer" | "variation"
        filters: 筛选条件，语法为 {"字段名__操作符": 值}。
                 示例:
                   {"rating__gte": 4.0, "current_price__lte": 50, "is_prime": true}
                   {"category_name__contains": "Headphones", "brand__in": ["Sony", "Bose"]}
                   {"is_fba": true, "monthly_sold__gte": 500, "current_bsr__lte": 10000}
                 支持的操作符:
                   __eq (默认), __gte, __lte, __gt, __lt, __neq,
                   __in (列表), __contains (ILIKE 模糊), __isnull (true=IS NULL)
        metrics: 需要返回的指标。不传则返回常用字段。
        sort_by: 排序字段，如 "monthly_sold", "rating", "current_price", "current_bsr"
        sort_order: "desc" (降序) 或 "asc" (升序)
        limit: 最大行数 (1-100)
        offset: 分页偏移
        domain: 站点，默认 "US"
    """
    limit = max(1, min(limit, 100))

    try:
        engine = get_query_engine()
        result = await engine.search(
            entity_type=entity_type,
            filters=filters,
            sort_by=sort_by,
            sort_order=sort_order,
            limit=limit,
            offset=offset,
            domain=domain,
        )

        total = result["total"]
        rows = result["results"]

        if not rows:
            return f"未找到符合条件的 {entity_type}（总匹配: {total}）"

        lines = [f"🔍 找到 {total} 个{entity_type}（显示 {len(rows)} 个）"]
        if sort_by:
            lines[0] += f" | 排序: {sort_by} {sort_order}"

        for i, row in enumerate(rows):
            lines.append("")
            asin = row.get("asin", row.get("seller_id", "?"))
            lines.append(f"#{offset + i + 1} **{asin}**")
            # 优先显示关键字段
            for key in ("title", "brand", "category_name"):
                val = row.get(key)
                if val:
                    lines.append(f"  {key}: {str(val)[:60]}")
            for key in ("current_price", "rating", "review_count", "monthly_sold", "current_bsr"):
                val = row.get(key)
                if val is not None:
                    if key == "current_price":
                        lines.append(f"  价格: ${val}" if val else "")
                    elif key == "rating":
                        lines.append(f"  评分: {val}⭐")
                    else:
                        lines.append(f"  {key}: {val}")
            # 布尔标志
            flags = []
            if row.get("is_fba"):
                flags.append("FBA")
            if row.get("is_prime"):
                flags.append("Prime")
            if row.get("has_coupon"):
                flags.append("🎟️Coupon")
            if row.get("has_amazon_selling"):
                flags.append("Amazon自营")
            if flags:
                lines.append(f"  {' | '.join(flags)}")

        if total > len(rows):
            lines.append(f"\n... 还有 {total - len(rows)} 条。调 offset={offset + limit} 翻页。")

        return "\n".join(lines)
    except Exception as e:
        logger.error(f"[search_entities] 失败: {e}", exc_info=True)
        return f"搜索失败: {e}"


# ── 4. 趋势查询 ──


@tool
async def get_trends(
    entity_ids: List[str],
    metrics: List[str],
    max_points: int = 60,
    domain: str = "US",
) -> str:
    """
    查询商品的历史趋势数据（价格/BSR/评分/评论数）。

    数据来源为数据库中的 JSON 历史字段。趋势辅助判断市场变化方向。
    适用于：判断价格是否在下降通道、BSR 是否恶化、评论增速是否放缓。

    Args:
        entity_ids: ASIN 列表，最多 10 个
        metrics: 趋势字段，可选值: "price_history", "bsr_history", "rating_history", "review_count_history"
        max_points: 每字段每实体最多返回的数据点数 (10-180)
        domain: 站点，默认 "US"
    """
    if len(entity_ids) > 10:
        return f"最多查询 10 个 ASIN 的趋势，收到 {len(entity_ids)} 个"
    if not metrics:
        return "请指定至少一个趋势字段: price_history, bsr_history, rating_history, review_count_history"
    if not all(m in ("price_history", "bsr_history", "rating_history", "review_count_history") for m in metrics):
        return f"趋势字段必须是: price_history, bsr_history, rating_history, review_count_history。收到: {metrics}"

    max_points = max(10, min(max_points, 180))

    try:
        engine = get_query_engine()
        result = await engine.fetch_trends(
            entity_type="product",
            entity_ids=entity_ids,
            metrics=metrics,
            max_points=max_points,
            domain=domain,
        )

        return result["summary"]
    except Exception as e:
        logger.error(f"[get_trends] 失败: {e}", exc_info=True)
        return f"趋势查询失败: {e}"


# ── 5. 自定义聚合 ──


@tool
async def analyze_custom(
    entity_type: str,
    metric_expressions: List[str],
    group_by: Optional[str] = None,
    filters: Optional[Dict[str, Any]] = None,
    limit: int = 50,
    domain: str = "US",
) -> str:
    """
    自定义聚合分析——对商品/Offer/变体做分组统计。

    当你需要"各品牌的平均价格和总销量"、"各品类的商品数量"等跨商品的统计时使用。
    只允许安全的聚合函数（avg/sum/count/min/max），不能执行任意 SQL。

    Args:
        entity_type: "product" | "offer" | "variation"
        metric_expressions: 聚合表达式列表，如
            ["avg(current_price)", "sum(monthly_sold)", "count(*)"]
        group_by: 分组字段，可选值:
            brand, category_name, product_type_name, bsr_category,
            color, size, material, seller_name, is_fba, is_prime,
            product_type, importance_tier, lifecycle_status,
            has_amazon_selling, has_china_sellers
        filters: 筛选条件（同 search_entities 的 filter 语法）
        limit: 最大行数 (1-200)
        domain: 站点，默认 "US"
    """
    limit = max(1, min(limit, 200))

    if not metric_expressions:
        return "请指定至少一个聚合表达式，如 ['avg(current_price)', 'count(*)']"

    try:
        engine = get_query_engine()
        result = await engine.aggregate(
            entity_type=entity_type,
            metric_expressions=metric_expressions,
            group_by=group_by,
            filters=filters,
            limit=limit,
        )

        if result.get("errors"):
            return f"聚合查询错误:\n" + "\n".join(result["errors"])

        rows = result.get("rows", [])
        if not rows:
            return "聚合结果为空"

        columns = result.get("columns", [])
        lines = [f"📊 聚合结果（{result['total']} 行）"]
        if result.get("group_by"):
            lines[0] += f" | 分组: {result['group_by']}"

        # 表格头
        header = " | ".join(f"{c:<20}" for c in columns)
        lines.append(header)
        lines.append("-" * len(header))

        for row in rows:
            vals = []
            for c in columns:
                v = row.get(c)
                if v is None:
                    vals.append(f"{'null':<20}")
                elif isinstance(v, float):
                    vals.append(f"{v:<20.2f}")
                else:
                    vals.append(f"{str(v)[:20]:<20}")
            lines.append(" | ".join(vals))

        return "\n".join(lines)
    except Exception as e:
        logger.error(f"[analyze_custom] 失败: {e}", exc_info=True)
        return f"聚合分析失败: {e}"


# ── 工具列表 ──

def get_data_tools():
    """返回 5 个数据工具的列表（供 orchestrator 注册使用）"""
    return [
        get_entity_details,
        compare_entities,
        search_entities,
        get_trends,
        analyze_custom,
    ]