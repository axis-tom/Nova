"""
Amazon 产品 Repository
封装 amazon_products 表的所有查询操作
下游 Agent 通过此 Repo 查数据，不再直接调 API
"""
import logging
from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime, timezone, timedelta

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete, desc, or_, and_, func as sql_func

from backend.data.models.amazon_product import AmazonProduct, AmazonETLLog
from backend.business.ecommerce.amazon_monitor.tools.importance_score import (
    calc_importance_score,
    calc_manual_override_tier,
)

logger = logging.getLogger(__name__)


class AmazonProductRepository:
    """Amazon 产品数据仓库"""

    def __init__(self, db: AsyncSession):
        self.db = db

    # ── 基础 CRUD ──

    async def get_by_asin(self, asin: str, domain: str = "US") -> Optional[AmazonProduct]:
        """按 ASIN 查询单个商品"""
        stmt = select(AmazonProduct).where(
            AmazonProduct.asin == asin,
            AmazonProduct.domain == domain,
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_asins(self, asins: List[str], domain: str = "US") -> Dict[str, AmazonProduct]:
        """批量查询，返回 {asin: product}"""
        stmt = select(AmazonProduct).where(
            AmazonProduct.asin.in_(asins),
            AmazonProduct.domain == domain,
        )
        result = await self.db.execute(stmt)
        products = result.scalars().all()
        return {p.asin: p for p in products}

    async def upsert(self, data: Dict[str, Any], source: str) -> AmazonProduct:
        """
        合并写入商品数据。
        source = "keepa" / "rainforest" / "canopy"
        部分更新而不是全量覆盖（按源写对应字段标记）
        """
        asin = data.get("asin", "")
        domain = data.get("domain", "US")
        if not asin:
            raise ValueError("asin is required")

        existing = await self.get_by_asin(asin, domain)

        if existing:
            # 部分更新：只覆盖该源提供的字段，不覆盖其他源的独占字段
            for key, value in data.items():
                if hasattr(existing, key) and value is not None:
                    setattr(existing, key, value)
            existing.updated_at = datetime.now(timezone.utc)
        else:
            existing = AmazonProduct(**data)
            existing.created_at = datetime.now(timezone.utc)
            existing.updated_at = datetime.now(timezone.utc)
            self.db.add(existing)

        # 更新来源时间戳
        now = datetime.now(timezone.utc)
        if source == "keepa":
            existing.keepa_updated_at = now
        elif source == "rainforest":
            existing.rainforest_updated_at = now
        elif source == "canopy":
            existing.canopy_updated_at = now

        await self.db.commit()
        await self.db.refresh(existing)
        return existing

    async def delete_by_asin(self, asin: str, domain: str = "US") -> bool:
        """删除指定 ASIN"""
        stmt = delete(AmazonProduct).where(
            AmazonProduct.asin == asin,
            AmazonProduct.domain == domain,
        )
        result = await self.db.execute(stmt)
        await self.db.commit()
        return result.rowcount > 0

    # ── 重要性评分 ──

    async def recalc_importance(self, asin: str, domain: str = "US") -> Optional[AmazonProduct]:
        """重新计算某个 ASIN 的 Importance Score"""
        product = await self.get_by_asin(asin, domain)
        if not product:
            return None

        data = self._product_to_dict(product)
        result = calc_importance_score(data)

        product.importance_score = result["score"]
        product.importance_tier = result["tier"]
        product.importance_details = result
        product.importance_updated_at = datetime.now(timezone.utc)
        product.updated_at = datetime.now(timezone.utc)

        await self.db.commit()
        await self.db.refresh(product)
        return product

    async def recalc_all_importance(self, domain: str = "US") -> int:
        """批量重新计算所有 ASIN 的重要性分"""
        stmt = select(AmazonProduct).where(AmazonProduct.domain == domain)
        result = await self.db.execute(stmt)
        products = result.scalars().all()

        count = 0
        for p in products:
            try:
                data = self._product_to_dict(p)
                score = calc_importance_score(data)
                p.importance_score = score["score"]
                p.importance_tier = score["tier"]
                p.importance_details = score
                p.importance_updated_at = datetime.now(timezone.utc)
                count += 1
            except Exception as e:
                logger.warning(f"Importance calc failed for {p.asin}: {e}")

        await self.db.commit()
        return count

    # ── 分级查询 ──

    async def get_asins_by_tier(
        self, tier: str, domain: str = "US", limit: int = 100,
    ) -> List[AmazonProduct]:
        """按 Tier 查询 ASIN 列表"""
        stmt = (
            select(AmazonProduct)
            .where(
                AmazonProduct.importance_tier == tier,
                AmazonProduct.domain == domain,
            )
            .order_by(AmazonProduct.importance_score.desc().nullslast())
            .limit(limit)
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_stale_asins(
        self, source: str, max_age_hours: int, tier: Optional[str] = None, limit: int = 100,
    ) -> List[AmazonProduct]:
        """
        获取数据过时需要刷新的 ASIN。

        Args:
            source: keepa / rainforest / canopy
            max_age_hours: 超过此小时数未更新视为过期
            tier: 可选，限定 tier
            limit: 最大返回数量
        """
        age_limit = datetime.now(timezone.utc) - timedelta(hours=max_age_hours)

        if source == "keepa":
            age_column = AmazonProduct.keepa_updated_at
        elif source == "rainforest":
            age_column = AmazonProduct.rainforest_updated_at
        elif source == "canopy":
            age_column = AmazonProduct.canopy_updated_at
        else:
            raise ValueError(f"Unknown source: {source}")

        conditions = [
            or_(age_column.is_(None), age_column < age_limit),
        ]
        if tier:
            conditions.append(AmazonProduct.importance_tier == tier)

        stmt = (
            select(AmazonProduct)
            .where(and_(*conditions))
            .order_by(age_column.asc().nullsfirst())
            .limit(limit)
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def count_by_tier(self, domain: str = "US") -> Dict[str, int]:
        """统计各 Tier 的 ASIN 数量"""
        stmt = (
            select(
                AmazonProduct.importance_tier,
                sql_func.count(AmazonProduct.id),
            )
            .where(AmazonProduct.domain == domain)
            .group_by(AmazonProduct.importance_tier)
        )
        result = await self.db.execute(stmt)
        counts = {"hot": 0, "active": 0, "passive": 0, "unknown": 0}
        for row in result:
            key = row[0] or "unknown"
            counts[key] = row[1]
        return counts

    # ── 搜索/筛选（对标卖家精灵选产品） ──

    async def search_products(
        self,
        domain: str = "US",
        tier: Optional[str] = None,
        min_rating: Optional[float] = None,
        min_review_count: Optional[int] = None,
        min_monthly_sold: Optional[int] = None,
        max_price: Optional[float] = None,
        min_price: Optional[float] = None,
        max_bsr: Optional[int] = None,
        has_aplus: Optional[bool] = None,
        is_fba: Optional[bool] = None,
        sort_by: str = "importance_score",
        sort_desc: bool = True,
        limit: int = 50,
        offset: int = 0,
    ) -> Tuple[List[AmazonProduct], int]:
        """多维条件筛选 ASIN"""
        conditions = [AmazonProduct.domain == domain]

        if tier:
            conditions.append(AmazonProduct.importance_tier == tier)
        if min_rating is not None:
            conditions.append(AmazonProduct.rating >= min_rating)
        if min_review_count is not None:
            conditions.append(AmazonProduct.review_count >= min_review_count)
        if min_monthly_sold is not None:
            conditions.append(AmazonProduct.monthly_sold >= min_monthly_sold)
        if max_price is not None:
            conditions.append(AmazonProduct.current_price <= max_price)
        if min_price is not None:
            conditions.append(AmazonProduct.current_price >= min_price)
        if max_bsr is not None:
            conditions.append(AmazonProduct.current_bsr <= max_bsr)
        if has_aplus is not None:
            if has_aplus:
                conditions.append(AmazonProduct.aplus_content.isnot(None))
            else:
                conditions.append(AmazonProduct.aplus_content.is_(None))
        if is_fba is not None:
            if is_fba:
                conditions.append(AmazonProduct.is_fba == True)
            else:
                conditions.append(AmazonProduct.is_fba == False)

        # 排序
        sort_columns = {
            "importance_score": AmazonProduct.importance_score,
            "current_price": AmazonProduct.current_price,
            "rating": AmazonProduct.rating,
            "review_count": AmazonProduct.review_count,
            "monthly_sold": AmazonProduct.monthly_sold,
            "current_bsr": AmazonProduct.current_bsr,
            "updated_at": AmazonProduct.updated_at,
        }
        order_col = sort_columns.get(sort_by, AmazonProduct.importance_score)
        order_expr = desc(order_col) if sort_desc else order_col

        # 总数
        count_stmt = select(sql_func.count()).select_from(AmazonProduct).where(and_(*conditions))
        count_result = await self.db.execute(count_stmt)
        total = count_result.scalar() or 0

        # 分页
        stmt = (
            select(AmazonProduct)
            .where(and_(*conditions))
            .order_by(order_expr)
            .offset(offset)
            .limit(limit)
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all()), total

    # ── ETL 日志 ──

    async def create_etl_log(self, log_data: Dict[str, Any]) -> AmazonETLLog:
        """创建 ETL 日志条目"""
        log = AmazonETLLog(**log_data)
        self.db.add(log)
        await self.db.commit()
        await self.db.refresh(log)
        return log

    async def get_etl_logs(
        self, limit: int = 50, source: Optional[str] = None, status: Optional[str] = None,
    ) -> List[AmazonETLLog]:
        """查询 ETL 日志"""
        conditions = []
        if source:
            conditions.append(AmazonETLLog.source == source)
        if status:
            conditions.append(AmazonETLLog.status == status)

        stmt = (
            select(AmazonETLLog)
            .where(and_(*conditions) if conditions else True)
            .order_by(desc(AmazonETLLog.created_at))
            .limit(limit)
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    # ── 工具方法 ──

    def _product_to_dict(self, product: AmazonProduct) -> Dict[str, Any]:
        """ORM 对象转 dict"""
        data = {}
        for col in AmazonProduct.__table__.columns:
            val = getattr(product, col.name, None)
            data[col.name] = val
        return data