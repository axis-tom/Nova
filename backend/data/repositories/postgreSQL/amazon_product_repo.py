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
from backend.data.models.amazon_product_offer import AmazonProductOffer
from backend.data.models.amazon_product_variation import AmazonProductVariation
from backend.data.models.change_log import AmazonChangeLog
from backend.data.models.anomaly_log import AmazonAnomalyLog
from backend.aqueduct.importance_score import (
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

    # ── 数据生命周期 ──

    async def get_products_by_lifecycle(
        self, status: str, last_accessed_before: Optional[datetime] = None,
        domain: str = "US", limit: int = 100,
    ) -> List[AmazonProduct]:
        """按生命周期状态查询 ASIN"""
        conditions = [
            AmazonProduct.lifecycle_status == status,
            AmazonProduct.domain == domain,
        ]
        if last_accessed_before:
            conditions.append(
                or_(
                    AmazonProduct.last_accessed_at.is_(None),
                    AmazonProduct.last_accessed_at < last_accessed_before,
                )
            )
        stmt = (
            select(AmazonProduct)
            .where(and_(*conditions))
            .order_by(AmazonProduct.last_accessed_at.asc().nullsfirst())
            .limit(limit)
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def update_lifecycle(self, asin: str, domain: str, status: str) -> bool:
        """更新 ASIN 的生命周期状态"""
        stmt = (
            update(AmazonProduct)
            .where(
                AmazonProduct.asin == asin,
                AmazonProduct.domain == domain,
            )
            .values(lifecycle_status=status, updated_at=datetime.now(timezone.utc))
        )
        result = await self.db.execute(stmt)
        await self.db.commit()
        return result.rowcount > 0

    async def update_last_accessed(self, asin: str, domain: str = "US") -> bool:
        """记录 ASIN 被 Agent 访问的时间（用于生命周期判断）"""
        stmt = (
            update(AmazonProduct)
            .where(
                AmazonProduct.asin == asin,
                AmazonProduct.domain == domain,
            )
            .values(last_accessed_at=datetime.now(timezone.utc))
        )
        result = await self.db.execute(stmt)
        await self.db.commit()
        return result.rowcount > 0

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

    # ── 变更日志 ──

    async def create_change_log(self, entry: Dict) -> AmazonChangeLog:
        """写入变更日志"""
        log = AmazonChangeLog(**entry)
        self.db.add(log)
        await self.db.commit()
        await self.db.refresh(log)
        return log

    async def get_change_logs(self, asin: Optional[str] = None,
                              limit: int = 50) -> List[AmazonChangeLog]:
        """查询变更日志"""
        stmt = select(AmazonChangeLog)
        if asin:
            stmt = stmt.where(AmazonChangeLog.asin == asin)
        stmt = stmt.order_by(desc(AmazonChangeLog.detected_at)).limit(limit)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    # ── 异常日志 ──

    async def create_anomaly_log(self, entry: Dict) -> AmazonAnomalyLog:
        """写入异常事件"""
        log = AmazonAnomalyLog(**entry)
        self.db.add(log)
        await self.db.commit()
        await self.db.refresh(log)
        return log

    async def get_anomaly_logs(self, asin: Optional[str] = None,
                               severity: Optional[str] = None,
                               limit: int = 50) -> List[AmazonAnomalyLog]:
        """查询异常事件"""
        conditions = []
        if asin:
            conditions.append(AmazonAnomalyLog.asin == asin)
        if severity:
            conditions.append(AmazonAnomalyLog.severity == severity)
        stmt = select(AmazonAnomalyLog)
        if conditions:
            stmt = stmt.where(and_(*conditions))
        stmt = stmt.order_by(desc(AmazonAnomalyLog.detected_at)).limit(limit)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    # ── Offer 子表 CRUD ──

    async def get_offers(self, asin: str, domain: str = "US") -> List[AmazonProductOffer]:
        """获取指定 ASIN 的所有 Offer"""
        stmt = select(AmazonProductOffer).where(
            AmazonProductOffer.asin == asin,
            AmazonProductOffer.domain == domain,
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def upsert_offer(self, offer_data: Dict) -> AmazonProductOffer:
        """写入/更新单个 Offer"""
        asin = offer_data.get("asin")
        domain = offer_data.get("domain", "US")
        seller_id = offer_data.get("seller_id")
        if not all([asin, seller_id]):
            raise ValueError("asin and seller_id are required for offer")

        stmt = select(AmazonProductOffer).where(
            AmazonProductOffer.asin == asin,
            AmazonProductOffer.domain == domain,
            AmazonProductOffer.seller_id == seller_id,
        )
        result = await self.db.execute(stmt)
        existing = result.scalar_one_or_none()

        if existing:
            for key, value in offer_data.items():
                if hasattr(existing, key) and value is not None:
                    setattr(existing, key, value)
        else:
            existing = AmazonProductOffer(**offer_data)
            self.db.add(existing)

        await self.db.commit()
        await self.db.refresh(existing)
        return existing

    async def bulk_upsert_offers(self, asin: str, domain: str, offers: List[Dict]) -> int:
        """批量写入 Offer，返回写入/更新条数"""
        count = 0
        for offer in offers:
            offer["asin"] = asin
            offer["domain"] = domain
            try:
                await self.upsert_offer(offer)
                count += 1
            except Exception as e:
                logger.warning(f"Offer upsert failed for {asin}/{offer.get('seller_id')}: {e}")
        return count

    async def delete_offers(self, asin: str, domain: str = "US") -> int:
        """删除指定 ASIN 的所有 Offer"""
        stmt = delete(AmazonProductOffer).where(
            AmazonProductOffer.asin == asin,
            AmazonProductOffer.domain == domain,
        )
        result = await self.db.execute(stmt)
        await self.db.commit()
        return result.rowcount

    # ── Variation 子表 CRUD ──

    async def get_variations(self, asin: str, domain: str = "US") -> List[AmazonProductVariation]:
        """获取指定 ASIN 的所有变体"""
        stmt = select(AmazonProductVariation).where(
            AmazonProductVariation.asin == asin,
            AmazonProductVariation.domain == domain,
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def upsert_variation(self, var_data: Dict) -> AmazonProductVariation:
        """写入/更新单个变体"""
        asin = var_data.get("asin")
        domain = var_data.get("domain", "US")
        variant_asin = var_data.get("variant_asin")
        if not all([asin, variant_asin]):
            raise ValueError("asin and variant_asin are required for variation")

        stmt = select(AmazonProductVariation).where(
            AmazonProductVariation.asin == asin,
            AmazonProductVariation.domain == domain,
            AmazonProductVariation.variant_asin == variant_asin,
        )
        result = await self.db.execute(stmt)
        existing = result.scalar_one_or_none()

        if existing:
            for key, value in var_data.items():
                if hasattr(existing, key) and value is not None:
                    setattr(existing, key, value)
        else:
            existing = AmazonProductVariation(**var_data)
            self.db.add(existing)

        await self.db.commit()
        await self.db.refresh(existing)
        return existing

    async def bulk_upsert_variations(self, asin: str, domain: str, variations: List[Dict]) -> int:
        """批量写入变体，返回写入/更新条数"""
        count = 0
        for var in variations:
            var["asin"] = asin
            var["domain"] = domain
            try:
                await self.upsert_variation(var)
                count += 1
            except Exception as e:
                logger.warning(f"Variation upsert failed for {asin}/{var.get('variant_asin')}: {e}")
        return count

    async def delete_variations(self, asin: str, domain: str = "US") -> int:
        """删除指定 ASIN 的所有变体"""
        stmt = delete(AmazonProductVariation).where(
            AmazonProductVariation.asin == asin,
            AmazonProductVariation.domain == domain,
        )
        result = await self.db.execute(stmt)
        await self.db.commit()
        return result.rowcount

    # ── 工具方法 ──

    def _product_to_dict(self, product: AmazonProduct) -> Dict[str, Any]:
        """ORM 对象转 dict"""
        data = {}
        for col in AmazonProduct.__table__.columns:
            val = getattr(product, col.name, None)
            data[col.name] = val
        return data