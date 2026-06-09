"""
动态 Filter 解析器 — LLM 的声明式筛选条件 → SQL WHERE 子句

支持的操作符（通过字段名后缀声明）：
  field__eq      等于（默认）
  field__gte     大于等于
  field__lte     小于等于
  field__gt      大于
  field__lt      小于
  field__in      在列表中
  field__contains   ILIKE 模糊匹配
  field__neq     不等于
  field__isnull   IS NULL / IS NOT NULL

示例：
  {"rating__gte": 4.0, "current_price__lte": 50, "is_prime": true}
  → rating >= 4.0 AND current_price <= 50 AND is_prime = true

  {"category_name__contains": "Headphones", "brand__in": ["Sony", "Bose"]}
  → category_name ILIKE '%Headphones%' AND brand IN ('Sony', 'Bose')
"""

import re
from typing import Any, Dict, List, Optional, Tuple
from sqlalchemy import Column, and_, or_
from sqlalchemy.sql.elements import BinaryExpression

from backend.data.models.amazon_product import AmazonProduct
from backend.data.models.amazon_product_offer import AmazonProductOffer
from backend.data.models.amazon_product_variation import AmazonProductVariation


# ── 操作符解析 ──

# 后缀 → (SQL 操作符, 是否需要值)
_OPERATORS = {
    "__eq": ("=", True),
    "__gte": (">=", True),
    "__lte": ("<=", True),
    "__gt": (">", True),
    "__lt": ("<", True),
    "__neq": ("!=", True),
    "__in": ("IN", True),       # 值必须是 list
    "__contains": ("ILIKE", True),  # 自动包装 %value%
    "__isnull": ("IS NULL", False),  # 值应为 bool：true → IS NULL, false → IS NOT NULL
}

# 实体类型 → SQLAlchemy Model
_ENTITY_MODEL = {
    "product": AmazonProduct,
    "offer": AmazonProductOffer,
    "variation": AmazonProductVariation,
}


def parse_filter_key(key: str) -> Tuple[str, str, bool]:
    """
    将带后缀的字段名拆解为 (列名, SQL 操作符, 是否需要值)

    Args:
        key: 如 "rating__gte" 或 "is_prime"

    Returns:
        (column_name, sql_operator, needs_value)
    """
    for suffix, (op, needs_val) in _OPERATORS.items():
        if key.endswith(suffix):
            col = key[:-len(suffix)]
            # 列名不允许空
            if col:
                return col, op, needs_val
    return key, "=", True  # 默认 eq


def get_orm_column(entity_type: str, column_name: str) -> Optional[Column]:
    """从 ORM 模型获取列对象，不存在返回 None"""
    model = _ENTITY_MODEL.get(entity_type)
    if model is None:
        return None
    return model.__table__.columns.get(column_name)


def build_filter_condition(
    entity_type: str,
    flt: Dict[str, Any],
) -> List[BinaryExpression]:
    """
    将声明式 filter dict 转换为 SQLAlchemy WHERE 条件列表

    Args:
        entity_type: "product" | "offer" | "variation"
        flt: filter dict，如 {"rating__gte": 4.0, "category_name__contains": "Phone"}

    Returns:
        SQLAlchemy BinaryExpression 列表（可直接 and_() 连接）
    """
    conditions = []

    for key, value in flt.items():
        col_name, operator, needs_value = parse_filter_key(key)

        orm_col = get_orm_column(entity_type, col_name)
        if orm_col is None:
            continue  # 跳过不存在的列，不报错

        if operator == "=":
            conditions.append(orm_col == value)
        elif operator == ">=":
            conditions.append(orm_col >= value)
        elif operator == "<=":
            conditions.append(orm_col <= value)
        elif operator == ">":
            conditions.append(orm_col > value)
        elif operator == "<":
            conditions.append(orm_col < value)
        elif operator == "!=":
            conditions.append(orm_col != value)
        elif operator == "IN":
            if isinstance(value, list) and value:
                conditions.append(orm_col.in_(value))
        elif operator == "ILIKE":
            conditions.append(orm_col.ilike(f"%{value}%"))
        elif operator == "IS NULL":
            is_null = bool(value)
            if is_null:
                conditions.append(orm_col.is_(None))
            else:
                conditions.append(orm_col.isnot(None))

    return conditions


def build_order_by(
    entity_type: str,
    sort_by: Optional[str] = None,
    sort_desc: bool = True,
) -> Optional[Any]:
    """
    构建 ORDER BY 子句

    Args:
        entity_type: "product" | "offer" | "variation"
        sort_by: 排序列名（指标名或数据库列名）
        sort_desc: 是否降序

    Returns:
        SQLAlchemy order expression，或 None（不排序）
    """
    from backend.core.data_tools.field_registry import SORTABLE_COLUMNS, COMMON_METRICS

    if not sort_by:
        return None

    lower_col = sort_by.lower().strip()

    # 先查注册表别名
    if lower_col in COMMON_METRICS:
        col_name = COMMON_METRICS[lower_col][0]
    else:
        col_name = lower_col

    orm_col = get_orm_column(entity_type, col_name)
    if orm_col is None:
        return None

    from sqlalchemy import desc
    return desc(orm_col) if sort_desc else orm_col


def validate_filter(entity_type: str, flt: Dict[str, Any]) -> List[str]:
    """
    校验 filter 的每个字段是否合法，返回所有错误信息（空列表表示完全合法）

    Args:
        entity_type: 实体类型
        flt: filter dict

    Returns:
        错误信息列表，空 = 合法
    """
    errors = []
    for key, value in flt.items():
        col_name, operator, needs_value = parse_filter_key(key)

        orm_col = get_orm_column(entity_type, col_name)
        if orm_col is None:
            errors.append(f"字段 '{col_name}' 在 {entity_type} 表中不存在")
            continue

        if operator == "IN" and not isinstance(value, list):
            errors.append(f"__in 操作符的值必须是列表，收到 {type(value).__name__}")

        if operator == "__isnull" and not isinstance(value, bool):
            errors.append(f"__isnull 操作符的值必须是 bool")

    return errors


def describe_supported_filters() -> str:
    """生成 filter 语法说明文本（供 tool description 使用）"""
    return (
        "筛选条件 filter 语法：\n"
        "  field__eq     =        field='value' 的简写\n"
        "  field__gte    >=       e.g. rating__gte: 4.0\n"
        "  field__lte    <=\n"
        "  field__gt     >\n"
        "  field__lt     <\n"
        "  field__neq    !=\n"
        "  field__in     IN LIST  e.g. brand__in: ['Sony', 'Bose']\n"
        "  field__contains  ILIKE  e.g. title__contains: 'Bluetooth'\n"
        "  field__isnull IS NULL  e.g. is_fba__isnull: true\n"
    )