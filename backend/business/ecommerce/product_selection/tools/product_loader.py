"""
Product Loader — Agent 加载完整商品数据的统一入口

职责：
1. 从 amazon_products 表加载完整 ORM 数据（180+ 字段）
2. 同时加载 offers / variations 子表
3. 调用 compute_all_derived_fields() 生成 Layer 2 的 33 个分析域
4. 返回统一富结构 dict，供下游 Agent 分析工具使用

用法：
    from backend.business.ecommerce.product_selection.tools.product_loader import load_products_from_db
    products = await load_products_from_db(asins=["B0F9FS7WQQ"], domain="US")
    # products[0]["current_price"]     → 原始字段
    # products[0]["competition_landscape"]  → Layer 2 推导域
    # products[0]["price_history"]     → 时间序列
    # products[0]["offers"]            → 子表数据

背景：此前 Agent 的 _load_from_local_db() 手动挑选 ~20 个字段，
把 ETL Pipeline 从三源采集的 180+ 字段 + 33 个推导方向全丢了。
这是分析"太笼统"的根本原因。
"""
import logging
from typing import Any, Dict, List, Optional

from backend.data.database import AsyncSessionLocal
from backend.data.models.amazon_product import AmazonProduct
from backend.data.repositories.postgreSQL.amazon_product_repo import AmazonProductRepository
from backend.aqueduct.derived_fields import compute_all_derived_fields

logger = logging.getLogger(__name__)


def _orm_to_dict(orm_obj) -> Dict[str, Any]:
    """将任意 SQLAlchemy ORM 对象转为 flat dict（全部数据库列，无丢失）"""
    from sqlalchemy.orm import class_mapper
    data = {}
    for col in class_mapper(type(orm_obj)).mapped_table.columns:
        val = getattr(orm_obj, col.name, None)
        if val is not None:
            data[col.name] = val
    return data


async def load_products_from_db(
    asins: Optional[List[str]] = None,
    category: Optional[str] = None,
    domain: str = "US",
    with_derived: bool = True,
) -> List[Dict[str, Any]]:
    """
    从 amazon_products 表加载完整商品数据（全字段 + 推导域 + 子表）。

    Args:
        asins: 指定 ASIN 列表
        category: 或指定类目名称
        domain: 市场代码（US/DE/JP）
        with_derived: 是否附上 33 个分析域推导结果（默认开启）

    Returns:
        每个 dict 包含：
        - 所有数据库列（180+ 字段，含 price_history/bsr_history）
        - Layer 2: 33 个分析域（如 competition_landscape, pricing_strategy）
        - offers: 子表 offer 列表
        - variations: 子表变体列表
    """
    async with AsyncSessionLocal() as db:
        repo = AmazonProductRepository(db)
        products_raw: List[AmazonProduct] = []

        if asins:
            existing = await repo.get_by_asins(asins, domain)
            products_raw = list(existing.values())
        elif category:
            # ★ P1 修复：使用 ILIKE 模糊匹配而非精确匹配
            from backend.data.repositories.postgreSQL.amazon_product_repo import AmazonProductRepository
            repo = AmazonProductRepository(db)
            category_products, _ = await repo.search_by_category_name(
                category_hint=category, domain=domain, limit=500,
            )
            products_raw = list(category_products)
        else:
            return []

        if not products_raw:
            return []

        result = []
        for p in products_raw:
            # 1. 全字段 ORM → flat dict
            d = _orm_to_dict(p)

            # 2. 子表数据（offers / variations）
            offers_raw = await repo.get_offers(p.asin, domain)
            variations_raw = await repo.get_variations(p.asin, domain)
            offers = [_orm_to_dict(o) for o in offers_raw]
            variations = [_orm_to_dict(v) for v in variations_raw]
            d["offers"] = offers
            d["variations"] = variations

            # 3. Layer 2: 33 个分析域推导
            if with_derived:
                try:
                    derived = compute_all_derived_fields(d, offers, variations)
                    d.update(derived)
                except Exception as e:
                    logger.warning(
                        f"[ProductLoader] 推导失败 {p.asin}: {e}"
                    )

            # 4. 兼容字段（旧代码引用的别名）
            d["data_sources"] = d.get("data_source", [])

            result.append(d)

    n = len(result)
    fields_count = len(d) if result else 0
    source_desc = f"{len(asins)} ASIN" if asins else f"类目={category}"
    logger.info(
        f"[ProductLoader] 加载 {n} 个商品（{source_desc}），每商品 {fields_count} 字段"
    )
    return result