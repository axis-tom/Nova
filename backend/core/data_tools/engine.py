"""
DataQueryEngine — 统一数据查询引擎

5 个工具调用的底层查询引擎，封装所有数据库操作。
职责：
  - 动态构建单表查询（SELECT column_a, column_b FROM table WHERE ...）
  - 跨表路由（product / offer / variation）
  - 空值保留（不填充默认值）
  - JSON 历史字段解析委托给 trends.py
"""

import json
import logging
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import select, and_, func as sql_func
from sqlalchemy.ext.asyncio import AsyncSession

from backend.data.database import AsyncSessionLocal
from backend.data.repositories.postgreSQL.amazon_product_repo import AmazonProductRepository
from backend.data.models.amazon_product import AmazonProduct
from backend.data.models.amazon_product_offer import AmazonProductOffer
from backend.data.models.amazon_product_variation import AmazonProductVariation

from backend.core.data_tools.field_registry import (
    ENTITY_MODEL_MAP,
    get_model_columns,
    resolve_metrics,
    COMMON_METRICS,
    SORTABLE_COLUMNS,
)
from backend.core.data_tools.filters import build_filter_condition, build_order_by
from backend.core.data_tools.trends import (
    is_history_field,
    parse_timestamp_series,
    batch_format_trends,
)
from backend.core.data_tools.aggregator import AggregationSpec, run_aggregation

logger = logging.getLogger(__name__)

# ── 限制 ──
MAX_ENTITY_IDS = 50        # 单次查询最大实体数
SEARCH_LIMIT = 100          # search 最大返回
DETAIL_LIMIT = 20           # 批量详情最大


class DataQueryEngine:
    """统一数据查询引擎"""

    def __init__(self):
        self._session = None

    async def _get_db(self) -> AsyncSession:
        """获取数据库会话（懒加载）"""
        if self._session is None:
            self._session = AsyncSessionLocal()
        return self._session

    async def close(self):
        """关闭数据库会话"""
        if self._session is not None:
            await self._session.close()
            self._session = None

    # ── 1. 实体详情 ──

    async def fetch_details(
        self,
        entity_type: str,
        entity_id: str,
        metrics: Optional[List[str]] = None,
        domain: str = "US",
    ) -> Optional[Dict[str, Any]]:
        """
        查询单个实体详情

        Args:
            entity_type: "product" | "offer" | "variation"
            entity_id: ASIN / seller_id / variant_asin
            metrics: 指标名列表，None 返回所有常用指标
            domain: 站点

        Returns:
            {column: value, ...} 或 None（不存在）
        """
        db = await self._get_db()
        model = ENTITY_MODEL_MAP.get(entity_type)
        if model is None:
            return None

        resolved = resolve_metrics(entity_type, metrics)
        if not resolved:
            resolved = list(get_model_columns(entity_type))

        # 始终包含 id 和 asin
        id_cols = ["id", "asin"]
        cols = list(dict.fromkeys(id_cols + resolved))  # 去重保序

        select_cols = [model.__table__.columns[c] for c in cols if model.__table__.columns.get(c) is not None]

        stmt = select(*select_cols).where(
            model.__table__.columns["asin"] == entity_id,
            model.__table__.columns.get("domain", AmazonProduct.domain) == domain,
        )

        try:
            result = await db.execute(stmt)
            row = result.mappings().first()
            if row is None:
                return None
            # 转普通 dict，保留 None
            data = dict(row)
            # Offer 表按 seller_id 查
            if entity_type == "offer" and not data.get("asin"):
                stmt = (
                    select(*select_cols)
                    .where(AmazonProductOffer.seller_id == entity_id)
                    .limit(1)
                )
                result = await db.execute(stmt)
                row = result.mappings().first()
                return dict(row) if row else None
            return data
        except Exception as e:
            logger.error(f"[Engine] fetch_details 失败: {e}")
            return None

    async def fetch_details_bulk(
        self,
        entity_type: str,
        entity_ids: List[str],
        metrics: Optional[List[str]] = None,
        domain: str = "US",
    ) -> Dict[str, Dict[str, Any]]:
        """
        批量查询多个实体详情

        Returns:
            {entity_id: {column: value, ...}, ...}
            不存在的 entity_id 不在结果中
        """
        if not entity_ids:
            return {}
        limited = entity_ids[:MAX_ENTITY_IDS]
        results = {}
        for eid in limited:
            data = await self.fetch_details(entity_type, eid, metrics, domain)
            if data:
                results[eid] = data
        return results

    # ── 2. 条件搜索 ──

    async def search(
        self,
        entity_type: str,
        filters: Optional[Dict[str, Any]] = None,
        sort_by: Optional[str] = None,
        sort_order: str = "desc",
        limit: int = 20,
        offset: int = 0,
        domain: str = "US",
    ) -> Dict[str, Any]:
        """
        条件搜索实体

        Args:
            entity_type: "product" | "offer" | "variation"
            filters: 筛选条件 dict（见 filters.py）
            sort_by: 排序字段
            sort_order: "asc" | "desc"
            limit: 最大行数
            offset: 偏移
            domain: 站点

        Returns:
            {"total": N, "results": [{...}, ...], "offset": N, "limit": N}
        """
        db = await self._get_db()
        model = ENTITY_MODEL_MAP.get(entity_type)
        if model is None:
            return {"total": 0, "results": [], "offset": offset, "limit": limit}

        conditions = []
        domain_col = model.__table__.columns.get("domain")
        if domain_col is not None:
            conditions.append(domain_col == domain)

        # 构建 filter 条件
        if filters:
            filter_conds = build_filter_condition(entity_type, filters)
            conditions.extend(filter_conds)

        # 总数
        from sqlalchemy import func as sql_func
        count_stmt = select(sql_func.count()).select_from(model).where(and_(*conditions) if conditions else True)
        try:
            count_result = await db.execute(count_stmt)
            total = count_result.scalar() or 0
        except Exception as e:
            logger.error(f"[Engine] search count 失败: {e}")
            total = 0

        # 查询列：全部常用列（限制字段数量防止爆 token）
        resolved = resolve_metrics(entity_type, None)[:30]
        id_cols = ["id", "asin"]
        cols = list(dict.fromkeys(id_cols + resolved))
        select_cols = [model.__table__.columns[c] for c in cols if model.__table__.columns.get(c) is not None]

        stmt = select(*select_cols).where(and_(*conditions) if conditions else True)

        # 排序
        order = build_order_by(entity_type, sort_by, sort_order != "asc")
        if order is not None:
            stmt = stmt.order_by(order)

        stmt = stmt.offset(offset).limit(min(limit, SEARCH_LIMIT))

        try:
            result = await db.execute(stmt)
            rows = result.mappings().all()
            return {
                "total": total,
                "results": [dict(r) for r in rows],
                "offset": offset,
                "limit": min(limit, SEARCH_LIMIT),
            }
        except Exception as e:
            logger.error(f"[Engine] search 失败: {e}")
            return {"total": 0, "results": [], "offset": offset, "limit": limit}

    # ── 3. 趋势查询 ──

    async def fetch_trends(
        self,
        entity_type: str,
        entity_ids: List[str],
        metrics: List[str],
        date_range: Optional[Tuple[str, str]] = None,
        max_points: int = 90,
        domain: str = "US",
    ) -> Dict[str, Any]:
        """
        查询实体的时间序列趋势

        Args:
            entity_type: "product"
            entity_ids: ASIN 列表
            metrics: 历史字段名，如 ["price_history", "bsr_history"]
            date_range: (start, end) ISO 日期
            max_points: 每字段每实体最大点数
            domain: 站点

        Returns:
            {"trends": {"price_history": {"B0...": [...points], ...}, ...}, "summary": "..."}
        """
        db = await self._get_db()
        model = ENTITY_MODEL_MAP.get(entity_type)
        if model is None:
            return {"trends": {}, "summary": "不支持的实体类型"}

        # 只取历史字段
        history_metrics = [m for m in metrics if is_history_field(m)]
        if not history_metrics:
            return {"trends": {}, "summary": "未指定历史字段（price_history / bsr_history / rating_history / review_count_history）"}

        limited_ids = entity_ids[:MAX_ENTITY_IDS]

        # 只查所需列
        select_cols = [model.__table__.columns["asin"]]
        for m in history_metrics:
            col_name = COMMON_METRICS.get(m.lower(), (None,))[0] or m
            orm_col = model.__table__.columns.get(col_name)
            if orm_col is not None:
                select_cols.append(orm_col)

        stmt = (
            select(*select_cols)
            .where(
                model.__table__.columns["asin"].in_(limited_ids),
                model.__table__.columns["domain"] == domain,
            )
        )

        try:
            result = await db.execute(stmt)
            rows = result.all()
        except Exception as e:
            logger.error(f"[Engine] fetch_trends 查询失败: {e}")
            return {"trends": {}, "summary": f"查询失败: {e}"}

        # 解析历史字段
        result_dict: Dict[str, Dict[str, List]] = {}
        for m in history_metrics:
            col_name = COMMON_METRICS.get(m.lower(), (None,))[0] or m
            result_dict[m] = {}

        for row in rows:
            asin = row[0]
            for i, m in enumerate(history_metrics):
                raw = row[i + 1]
                if raw is None:
                    continue
                points = parse_timestamp_series(raw, m, max_points=max_points)

                # 日期范围过滤
                if date_range and points:
                    start_date, end_date = date_range
                    points = [p for p in points if start_date <= p["date"] <= end_date]

                if points:
                    result_dict[m][asin] = points

        # 生成摘要文本
        summary_parts = []
        for m in history_metrics:
            if result_dict[m]:
                summary_parts.append(batch_format_trends(m, result_dict[m]))
            else:
                summary_parts.append(f"[{m}] 无历史数据")

        return {
            "trends": result_dict,
            "summary": "\n\n".join(summary_parts),
        }

    # ── 4. 对比查询（包装 fetch_details_bulk 为对比格式） ──

    async def compare(
        self,
        entity_type: str,
        entity_ids: List[str],
        metrics: Optional[List[str]] = None,
        domain: str = "US",
    ) -> Dict[str, Any]:
        """
        对比多个实体

        Returns:
            {"entity_type": "...", "entity_ids": [...], "fields": [...], "data": {id: {...}}, "summary": "..."}
        """
        data = await self.fetch_details_bulk(entity_type, entity_ids, metrics, domain)

        if not data:
            return {
                "entity_type": entity_type,
                "entity_ids": entity_ids,
                "fields": [],
                "data": {},
                "summary": "未找到任何实体的数据",
            }

        # 提取公共字段
        all_fields = set()
        for d in data.values():
            all_fields.update(d.keys())
        common_fields = sorted(f for f in all_fields if f not in ("id",))

        # 生成文本摘要
        lines = [f"对比: {', '.join(data.keys())}"]
        for field in common_fields[:15]:  # 只显示前 15 个字段
            vals = []
            for eid in data:
                v = data[eid].get(field)
                if v is not None:
                    vals.append(f"{eid}={v}")
                else:
                    vals.append(f"{eid}=null")
            lines.append(f"  {field}: {' | '.join(vals)}")

        return {
            "entity_type": entity_type,
            "entity_ids": list(data.keys()),
            "fields": common_fields[:30],
            "data": data,
            "summary": "\n".join(lines),
        }

    # ── 5. 自定义聚合（委托给 aggregator） ──

    async def aggregate(
        self,
        entity_type: str,
        metric_expressions: List[str],
        group_by: Optional[str] = None,
        filters: Optional[Dict[str, Any]] = None,
        limit: int = 100,
    ) -> Dict[str, Any]:
        """
        自定义聚合查询

        Args:
            entity_type: "product" | "offer" | "variation"
            metric_expressions: e.g. ["avg(current_price)", "sum(monthly_sold)", "count(*)"]
            group_by: e.g. "brand"
            filters: 筛选条件
            limit: 最大行数

        Returns:
            {"columns": [...], "rows": [...], "total": N, "group_by": "...", "errors": [...]}
        """
        spec = AggregationSpec(entity_type, metric_expressions, group_by, filters)
        if not spec.validate():
            return {"columns": [], "rows": [], "total": 0, "group_by": group_by, "errors": spec.errors}

        db = await self._get_db()
        return await run_aggregation(db, spec, limit=limit)

    # ── 辅助：列出所有指标（供工具描述使用） ──

    @staticmethod
    def list_available_metrics(entity_type: str) -> str:
        """返回可查询的指标列表文本"""
        from backend.core.data_tools.field_registry import ENTITY_METRICS_MAP
        metrics_map = ENTITY_METRICS_MAP.get(entity_type, {})
        if not metrics_map:
            return "无可用的指标定义"
        lines = [f"--- {entity_type} 可用指标 ---"]
        for name, (col, desc) in sorted(metrics_map.items()):
            lines.append(f"  {name}: {desc}")
        return "\n".join(lines)


# ── 全局单例 ──
_engine: Optional[DataQueryEngine] = None


def get_query_engine() -> DataQueryEngine:
    """获取全局查询引擎单例"""
    global _engine
    if _engine is None:
        _engine = DataQueryEngine()
    return _engine