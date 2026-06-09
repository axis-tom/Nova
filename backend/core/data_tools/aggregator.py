"""
安全聚合引擎 — LLM 声明式聚合 → 安全 SQL GROUP BY

只允许预定义的白名单聚合函数和分组列，禁止任意 SQL 拼接。
"""
import json
import logging
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import select, func as sql_func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.data_tools.field_registry import (
    ALLOWED_AGGREGATIONS,
    ALLOWED_GROUP_BY,
    ENTITY_MODEL_MAP,
    COMMON_METRICS,
)

logger = logging.getLogger(__name__)

# 聚合函数名 → SQLAlchemy func
_AGG_FUNC_MAP = {
    "avg": sql_func.avg,
    "sum": sql_func.sum,
    "count": sql_func.count,
    "min": sql_func.min,
    "max": sql_func.max,
}


def _resolve_column_name(entity_type: str, metric_name: str) -> Optional[str]:
    """将指标名解析为数据库列名（支持别名和原始列名）"""
    lower = metric_name.lower().strip()

    # 先查注册表
    if lower in COMMON_METRICS:
        return COMMON_METRICS[lower][0]

    # 直接是数据库列名
    model = ENTITY_MODEL_MAP.get(entity_type)
    if model and lower in {c.name for c in model.__table__.columns}:
        return lower

    return None


def _parse_metric_expression(entity_type: str, expr: str) -> Optional[Any]:
    """
    解析聚合指标表达式 → SQLAlchemy selectable

    支持的格式：
      "avg(current_price)"     → sql_func.avg(column)
      "sum(weekly_sold)"       → sql_func.sum(column)
      "count(*)"               → sql_func.count()
      "count(DISTINCT brand)"  → sql_func.count(column.distinct())

    Args:
        entity_type: 实体类型
        expr: 表达式字符串

    Returns:
        SQLAlchemy 可选的表达式，或 None（解析失败）
    """
    expr = expr.strip()

    # --- count(*) ---
    if expr.lower() == "count(*)":
        return sql_func.count().label("count")

    # --- count(DISTINCT col) ---
    distinct_match = __import__("re").match(r"^count\s*\(\s*DISTINCT\s+(.+?)\s*\)$", expr, __import__("re").IGNORECASE)
    if distinct_match:
        col_name = _resolve_column_name(entity_type, distinct_match.group(1))
        if col_name is None:
            return None
        model = ENTITY_MODEL_MAP.get(entity_type)
        col = model.__table__.columns.get(col_name) if model else None
        if col is None:
            return None
        label = f"{expr.replace(' ', '_').lower()}"
        return sql_func.count(col.distinct()).label(label)

    # --- agg(col) ---
    agg_match = __import__("re").match(r"^(\w+)\s*\((.+?)\)$", expr)
    if not agg_match:
        return None

    agg_name = agg_match.group(1).lower()
    col_name = agg_match.group(2).strip()

    if agg_name not in ALLOWED_AGGREGATIONS:
        logger.warning(f"[Aggregator] 不允许的聚合函数: {agg_name}")
        return None

    # 解析列名
    resolved = _resolve_column_name(entity_type, col_name)
    if resolved is None:
        logger.warning(f"[Aggregator] 无法解析列: {col_name}")
        return None

    model = ENTITY_MODEL_MAP.get(entity_type)
    col = model.__table__.columns.get(resolved) if model else None
    if col is None:
        return None

    func = _AGG_FUNC_MAP[agg_name]
    label = f"{agg_name}_{resolved}"
    return func(col).label(label)


def _resolve_group_by_column(entity_type: str, group_key: str) -> Optional[Any]:
    """解析 GROUP BY 列名"""
    model = ENTITY_MODEL_MAP.get(entity_type)
    if model is None:
        return None

    col_name = group_key.strip().lower()
    if col_name in COMMON_METRICS:
        col_name = COMMON_METRICS[col_name][0]

    if col_name not in ALLOWED_GROUP_BY:
        # 如果也是数据库列但不在白名单中，跳过
        if col_name not in {c.name for c in model.__table__.columns}:
            return None
        # 即使是在列中，也要白名单放行
        return None

    col = model.__table__.columns.get(col_name)
    return col


class AggregationSpec:
    """聚合规格 — 解析后的合法聚合请求"""

    def __init__(
        self,
        entity_type: str,
        metric_exprs: List[str],
        group_by: Optional[str] = None,
        filters: Optional[Dict[str, Any]] = None,
    ):
        self.entity_type = entity_type
        self.raw_metrics = metric_exprs
        self.group_by_col = group_by
        self.raw_filters = filters or {}

        # 解析结果
        self.select_columns: List[Any] = []
        self.group_by_clause: Optional[Any] = None
        self.filter_conditions: List[Any] = []
        self.errors: List[str] = []

    def validate(self) -> bool:
        """校验并解析聚合规格，返回是否合法"""
        from backend.core.data_tools.filters import build_filter_condition

        # 1. 解析聚合指标
        for expr in self.raw_metrics:
            col = _parse_metric_expression(self.entity_type, expr)
            if col is not None:
                self.select_columns.append(col)
            else:
                self.errors.append(f"无法解析聚合表达式: {expr}")

        if not self.select_columns:
            self.errors.append("至少需要一个有效的聚合指标")
            return False

        # 2. 解析 GROUP BY
        if self.group_by_col:
            col = _resolve_group_by_column(self.entity_type, self.group_by_col)
            if col is not None:
                self.group_by_clause = col
                self.select_columns.insert(0, col)  # GROUP BY 列先于聚合列
            else:
                self.errors.append(f"无法解析 GROUP BY 列: {self.group_by_col}")

        # 3. 解析 filters
        try:
            self.filter_conditions = build_filter_condition(self.entity_type, self.raw_filters)
        except Exception as e:
            self.errors.append(f"filter 解析失败: {e}")

        return len(self.errors) == 0


async def run_aggregation(
    db: AsyncSession,
    spec: AggregationSpec,
    limit: int = 100,
) -> Dict[str, Any]:
    """
    执行安全聚合查询

    Args:
        db: 数据库会话
        spec: 已验证的聚合规格
        limit: 最大返回行数

    Returns:
        {"columns": [...], "rows": [...], "total": N, "errors": [...]}
    """
    model = ENTITY_MODEL_MAP.get(spec.entity_type)
    if model is None:
        return {"columns": [], "rows": [], "total": 0, "errors": [f"未知实体类型: {spec.entity_type}"]}

    stmt = select(*spec.select_columns)

    if spec.filter_conditions:
        stmt = stmt.where(and_(*spec.filter_conditions) if len(spec.filter_conditions) > 1 else spec.filter_conditions[0])

    if spec.group_by_clause:
        stmt = stmt.group_by(spec.group_by_clause)

    try:
        result = await db.execute(stmt)
        rows = result.fetchmany(limit)

        columns = list(result.keys())
        data = [dict(zip(columns, row)) for row in rows]

        return {
            "columns": columns,
            "rows": data,
            "total": len(data),
            "group_by": spec.group_by_col,
            "errors": spec.errors,
        }
    except Exception as e:
        logger.error(f"[Aggregator] 查询失败: {e}")
        return {"columns": [], "rows": [], "total": 0, "errors": [f"查询执行失败: {e}"]}


def describe_aggregation_syntax() -> str:
    """生成聚合语法说明"""
    aggs = ", ".join(sorted(ALLOWED_AGGREGATIONS))
    groups = ", ".join(sorted(ALLOWED_GROUP_BY))
    return (
        "聚合语法：\n"
        f"  聚合函数: {aggs}\n"
        f"  支持分组: {groups}\n"
        "  示例: ['avg(current_price)', 'sum(monthly_sold)', 'count(*)']\n"
        "  示例 group_by: 'brand' -> 按品牌分组\n"
    )