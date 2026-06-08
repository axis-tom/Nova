"""
Amazon 产品 Repository
封装 amazon_products 表的所有查询操作
下游 Agent 通过此 Repo 查数据，不再直接调 API
"""
import json
import logging
from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime, timezone, timedelta

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete, desc, or_, and_, func as sql_func, Boolean, String, Integer, BigInteger, Float, JSON, Text, DateTime

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

    # ── 品类模糊查询 ──

    async def search_by_category_name(
        self,
        category_hint: str,
        domain: str = "US",
        limit: int = 50,
    ) -> Tuple[List[AmazonProduct], int]:
        """
        按品类名模糊查询（ILIKE），支持中英文品类名、同义词匹配。
        """
        conditions = [AmazonProduct.domain == domain]

        if category_hint:
            exact_cond = AmazonProduct.category_name == category_hint
            ilike_cond = AmazonProduct.category_name.ilike(f"%{category_hint}%")
            tokens = [t.strip() for t in category_hint.replace(",", " ").split() if len(t.strip()) > 1]
            token_conds = [AmazonProduct.category_name.ilike(f"%{t}%") for t in tokens]

            from sqlalchemy import or_
            conditions.append(or_(exact_cond, ilike_cond, *token_conds))

        count_stmt = select(sql_func.count()).select_from(AmazonProduct).where(and_(*conditions))
        count_result = await self.db.execute(count_stmt)
        total = count_result.scalar() or 0

        stmt = (
            select(AmazonProduct)
            .where(and_(*conditions))
            .order_by(AmazonProduct.importance_score.desc().nullslast())
            .limit(limit)
        )
        result = await self.db.execute(stmt)
        products = list(result.scalars().all())

        logger.info(f"[Repo] search_by_category_name(hint={category_hint}) → {len(products)}/{total}")
        return products, total

    # ── 跨列探索 ──

    async def explore(
        self, hint: str, domain: str = "US", limit: int = 100,
    ) -> Dict[str, Any]:
        """
        跨列探索——不在单一列上死磕，而是尝试所有可能相关的列，
        返回每种尝试的结果和命中细节。

        探索的列（按优先级）：
        1. category_name (ILIKE)
        2. product_type_name (ILIKE)
        3. bsr_category (ILIKE)
        4. title (ILIKE)
        5. brand (ILIKE)
        6. category_name token 级拆分
        7. title token 级拆分（英文）
        """
        from collections import Counter
        from sqlalchemy import or_

        strategies = []
        tokens = [t.strip() for t in hint.replace(",", " ").split() if len(t.strip()) > 1]

        # 策略 1: category_name ILIKE
        strategies.append({
            "column": "category_name", "strategy": "ilike",
            "cond": AmazonProduct.category_name.ilike(f"%{hint}%"),
        })
        # 策略 2: product_type_name ILIKE
        strategies.append({
            "column": "product_type_name", "strategy": "ilike",
            "cond": AmazonProduct.product_type_name.ilike(f"%{hint}%"),
        })
        # 策略 3: bsr_category ILIKE
        strategies.append({
            "column": "bsr_category", "strategy": "ilike",
            "cond": AmazonProduct.bsr_category.ilike(f"%{hint}%"),
        })
        # 策略 4: title ILIKE（英文 hint 或 token）
        if hint.isascii():
            strategies.append({
                "column": "title", "strategy": "ilike",
                "cond": AmazonProduct.title.ilike(f"%{hint}%"),
            })
        # 策略 5: brand
        strategies.append({
            "column": "brand", "strategy": "ilike",
            "cond": AmazonProduct.brand.ilike(f"%{hint}%"),
        })
        # 策略 6: 对 1 个以上 token 做 token 级 OR 匹配
        if len(tokens) > 1:
            for col in ("category_name", "product_type_name", "bsr_category", "title", "brand"):
                token_conds = []
                for t in tokens:
                    col_attr = getattr(AmazonProduct, col, None)
                    if col_attr is not None:
                        token_conds.append(col_attr.ilike(f"%{t}%"))
                if token_conds:
                    strategies.append({
                        "column": col, "strategy": "token_or",
                        "cond": or_(*token_conds) if len(token_conds) > 1 else token_conds[0],
                    })

        # 去重：一个 ASIN 可能命中间一行的多个策略，我们要的是全景
        domain_cond = AmazonProduct.domain == domain
        all_hit_asins = {}  # asin -> first_attempt 信息

        strategy_results = []
        for i, s in enumerate(strategies):
            try:
                stmt = (
                    select(AmazonProduct)
                    .where(and_(domain_cond, s["cond"]))
                    .order_by(AmazonProduct.importance_score.desc().nullslast())
                    .limit(limit)
                )
                result = await self.db.execute(stmt)
                products = list(result.scalars().all())

                hit_asins_count_before = len(all_hit_asins)
                for p in products:
                    if p.asin not in all_hit_asins:
                        all_hit_asins[p.asin] = {
                            "first_hit_column": s["column"],
                            "first_hit_strategy": s["strategy"],
                            "asin": p.asin,
                            "title": p.title,
                            "brand": p.brand,
                            "category_name": p.category_name,
                            "product_type_name": p.product_type_name,
                            "bsr_category": p.bsr_category,
                            "current_price": p.current_price,
                            "rating": p.rating,
                            "current_bsr": p.current_bsr,
                            "monthly_sold": p.monthly_sold,
                            "review_count": p.review_count,
                            "importance_score": p.importance_score,
                            "importance_tier": p.importance_tier,
                        }

                strategy_results.append({
                    "column": s["column"],
                    "strategy": s["strategy"],
                    "matched": len(products),
                    "new_asins": len(all_hit_asins) - hit_asins_count_before,
                })
            except Exception as e:
                strategy_results.append({
                    "column": s["column"], "strategy": s["strategy"],
                    "matched": 0, "new_asins": 0, "error": str(e),
                })

        # 汇总分类
        category_names = Counter(p["category_name"] for p in all_hit_asins.values() if p.get("category_name"))
        product_types = Counter(p["product_type_name"] for p in all_hit_asins.values() if p.get("product_type_name"))
        bsr_cats = Counter(p["bsr_category"] for p in all_hit_asins.values() if p.get("bsr_category"))
        brands = Counter(p["brand"] for p in all_hit_asins.values() if p.get("brand"))

        return {
            "total_distinct_asins": len(all_hit_asins),
            "strategies_attempted": strategy_results,
            "categories_found": dict(category_names.most_common(10)),
            "product_types_found": dict(product_types.most_common(10)),
            "bsr_categories_found": dict(bsr_cats.most_common(10)),
            "brands_found": dict(brands.most_common(15)),
            "products": list(all_hit_asins.values()),
        }

    # ── 数据库全景 ──

    async def get_catalog(self, domain: str = "US") -> Dict[str, Any]:
        """
        返回该 domain 的数据全景——不依赖任何 hint，纯统计。

        返回：
        - total_products: int
        - categories: [{name, count}] (category_name)
        - product_types: [{name, count}] (product_type_name)
        - brands: [{name, count}]
        - field_stats: {field_name: {filled, total, pct}}
        """
        from sqlalchemy import func as sql_func

        # 总数
        count_stmt = select(sql_func.count()).select_from(AmazonProduct).where(
            AmazonProduct.domain == domain
        )
        total_result = await self.db.execute(count_stmt)
        total = total_result.scalar() or 0

        if total == 0:
            return {"total_products": 0, "categories": [], "product_types": [], "brands": [], "field_stats": {}}

        # 聚合
        async def _agg(column, limit=20):
            stmt = (
                select(column, sql_func.count().label("cnt"))
                .where(and_(AmazonProduct.domain == domain, column.isnot(None)))
                .group_by(column)
                .order_by(sql_func.count().desc())
                .limit(limit)
            )
            result = await self.db.execute(stmt)
            return [{"name": row[0], "count": row[1]} for row in result if row[0]]

        categories = await _agg(AmazonProduct.category_name)
        product_types = await _agg(AmazonProduct.product_type_name)
        brands = await _agg(AmazonProduct.brand)

        # 字段填充率
        fields_to_check = [
            "current_price", "rating", "review_count", "current_bsr",
            "monthly_sold", "fba_fee", "feature_bullets", "main_image",
            "buybox_price", "offer_count", "stock_level", "aplus_content",
            "price_history", "bsr_history", "rating_history",
            "monthly_sold", "weekly_sold", "annual_sold",
            "is_fba", "is_prime", "has_amazon_selling",
            "out_of_stock_pct_30d", "coupon_text",
        ]
        field_stats = {}
        for field in fields_to_check:
            col = getattr(AmazonProduct, field, None)
            if col is None:
                continue
            filled_stmt = (
                select(sql_func.count())
                .select_from(AmazonProduct)
                .where(and_(AmazonProduct.domain == domain, col.isnot(None)))
            )
            filled_result = await self.db.execute(filled_stmt)
            filled = filled_result.scalar() or 0
            field_stats[field] = {
                "filled": filled,
                "total": total,
                "pct": round(filled / total * 100, 1) if total > 0 else 0,
            }

        return {
            "total_products": total,
            "categories": categories,
            "product_types": product_types,
            "brands": brands,
            "field_stats": field_stats,
        }

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

        # 通用类型矫正：将 ETL 传来的任意类型值适配到数据库列类型
        def _coerce(key: str, value: Any, col_type) -> Any:
            if value is None:
                return None
            # Boolean: dict/list → bool(value)
            if isinstance(col_type, Boolean):
                return bool(value) if not isinstance(value, bool) else value
            # String/Text: int/dict/list/float → str
            if isinstance(col_type, (String, type(Text()))):
                if isinstance(value, (dict, list)):
                    return json.dumps(value, ensure_ascii=False)
                if not isinstance(value, str):
                    return str(value)
                return value
            # Integer/BigInteger: large values, strings, floats
            if isinstance(col_type, (Integer, BigInteger)):
                if isinstance(value, str):
                    try:
                        return int(float(value))
                    except (ValueError, TypeError):
                        return None
                if isinstance(value, float):
                    return int(value)
                if isinstance(value, bool):  # bool is subclass of int
                    return int(value)
                return value
            # Float: int, str
            if isinstance(col_type, Float):
                if isinstance(value, str):
                    try:
                        return float(value)
                    except (ValueError, TypeError):
                        return None
                if isinstance(value, (int, float)) and not isinstance(value, bool):
                    return float(value)
                return value
            # DateTime: str → parse to datetime
            if isinstance(col_type, DateTime):
                if isinstance(value, str):
                    if not value.strip():
                        return None
                    try:
                        return datetime.fromisoformat(value.replace('Z', '+00:00'))
                    except (ValueError, TypeError):
                        return None
                return value
            # JSON: str → try parse as JSON
            if isinstance(col_type, JSON):
                if isinstance(value, str):
                    try:
                        return json.loads(value)
                    except (json.JSONDecodeError, TypeError):
                        return value
                return value
            return value

        existing = await self.get_by_asin(asin, domain)

        if existing:
            # 部分更新：只覆盖该源提供的字段，不覆盖其他源的独占字段
            for key, value in data.items():
                if hasattr(existing, key) and value is not None:
                    col = AmazonProduct.__table__.columns.get(key)
                    coerced = _coerce(key, value, col.type) if col is not None else value
                    setattr(existing, key, coerced)
            existing.updated_at = datetime.now(timezone.utc)
        else:
            # 过滤掉非模型字段 + 通用类型矫正
            model_keys = {c.name for c in AmazonProduct.__table__.columns}
            col_map = {c.name: c.type for c in AmazonProduct.__table__.columns}
            clean_data = {}
            for k, v in data.items():
                if k not in model_keys:
                    continue
                clean_data[k] = _coerce(k, v, col_map[k])
            existing = AmazonProduct(**clean_data)
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