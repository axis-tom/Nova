"""
市场分析服务层 — 对标卖家精灵市场类 API
直接从 amazon_products 表查询，不走 Agent/State 管道

M1: 选市场-统计（类目聚合）
M2: 商品需求趋势（BSR/价格/销量趋势）
M3: 价格分布
M4: 品牌集中度
M5: 评分数分布
M6: 评分值分布
M7: 商品集中度
M8: 卖家类型分布
M9: A+视频分布
"""

import asyncio
import logging
from typing import Any, Dict, List, Optional
from datetime import datetime, timezone
from statistics import median

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func as sql_func, and_

from backend.data.repositories.postgreSQL.amazon_product_repo import AmazonProductRepository
from backend.data.models.amazon_product import AmazonProduct

logger = logging.getLogger(__name__)


class MarketAnalysisService:
    """市场分析服务 — 封装所有市场类分析查询"""

    def __init__(self, db: AsyncSession):
        self.repo = AmazonProductRepository(db)
        self.db = db

    # ════════════════════════════════════════════════
    # M1: 选市场-统计
    # ════════════════════════════════════════════════

    async def get_market_summary(
        self, category_name: Optional[str] = None, domain: str = "US",
        tier: Optional[str] = None, brand: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        类目聚合统计。

        统计指标：
          - ASIN 总数、平均 BSR、平均价格、平均评分、平均评论数
          - 品牌数、卖家数、月销总量、月营收估算
          - 价格带分布
        """
        conditions = [AmazonProduct.domain == domain]
        if category_name:
            conditions.append(AmazonProduct.category_name == category_name)
        if tier:
            conditions.append(AmazonProduct.importance_tier == tier)
        if brand:
            conditions.append(AmazonProduct.brand == brand)

        base = select(AmazonProduct).where(and_(*conditions))
        count_stmt = select(sql_func.count()).select_from(AmazonProduct).where(and_(*conditions))
        count_result = await self.db.execute(count_stmt)
        total_asins = count_result.scalar() or 0

        # 取全部做统计分析
        result = await self.db.execute(base)
        products = list(result.scalars().all())

        if not products:
            return {
                "category": category_name or "all",
                "domain": domain,
                "total_asins": 0,
                "avg_bsr": None,
                "avg_price": None,
                "avg_rating": None,
                "avg_review_count": None,
                "brand_count": 0,
                "seller_count": None,
                "total_monthly_sold": 0,
                "estimated_monthly_revenue": 0,
                "price_distribution": {},
            }

        prices = [p.current_price for p in products if p.current_price]
        bsrs = [p.current_bsr for p in products if p.current_bsr]
        ratings = [p.rating for p in products if p.rating]
        reviews = [p.review_count for p in products if p.review_count]
        monthly_solds = [p.monthly_sold for p in products if p.monthly_sold]
        brand_set = {p.brand for p in products if p.brand}
        seller_count_sum = sum(p.seller_count or 0 for p in products)
        seller_avg = round(seller_count_sum / len(products)) if products else 0

        # 营收估算
        revenue = sum(
            (p.monthly_sold or 0) * (p.current_price or 0) for p in products
        )

        # 价格带分布
        price_dist = self._calc_price_distribution(products)

        # Tier 分布
        tier_counts = {"hot": 0, "active": 0, "passive": 0}
        for p in products:
            tier = p.importance_tier or "passive"
            tier_counts[tier] = tier_counts.get(tier, 0) + 1

        return {
            "category": category_name or "all",
            "domain": domain,
            "tier_filter": tier,
            "brand_filter": brand,
            "total_asins": total_asins,
            "avg_bsr": round(sum(bsrs) / len(bsrs)) if bsrs else None,
            "avg_price": round(sum(prices) / len(prices), 2) if prices else None,
            "avg_rating": round(sum(ratings) / len(ratings), 2) if ratings else None,
            "avg_review_count": round(sum(reviews) / len(reviews)) if reviews else None,
            "total_monthly_sold": sum(monthly_solds) if monthly_solds else 0,
            "estimated_monthly_revenue": round(revenue, 2),
            "brand_count": len(brand_set),
            "avg_seller_count": seller_avg,
            "price_distribution": price_dist,
            "importance_tier_distribution": tier_counts,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

    # ════════════════════════════════════════════════
    # M2: 商品需求趋势
    # ════════════════════════════════════════════════

    async def get_market_trend(
        self, category_name: Optional[str] = None, domain: str = "US", days: int = 90,
    ) -> Dict[str, Any]:
        """
        市场趋势分析 — 基于 Keepa 时间序列数据。

        从 amazon_products 的 price_history / bsr_history JSON 字段
        聚合出品类级趋势。
        """
        conditions = [AmazonProduct.domain == domain]
        if category_name:
            conditions.append(AmazonProduct.category_name == category_name)

        stmt = select(AmazonProduct).where(and_(*conditions))
        result = await self.db.execute(stmt)
        products = list(result.scalars().all())

        if not products:
            return {"category": category_name or "all", "total_asins": 0, "trends": {}}

        # BSR 趋势统计
        bsr_directions = {"improving": 0, "declining": 0, "stable": 0}
        bsr_changes_30d = []
        price_changes_30d = []

        for p in products:
            # BSR 方向
            trend = p.bsr_trend or "unknown"
            if trend in bsr_directions:
                bsr_directions[trend] += 1

            # price/bsr 历史最后 N 个点
            price_hist = p.price_history or []
            bsr_hist = p.bsr_history or []

            if bsr_hist and len(bsr_hist) >= 2:
                now_val = bsr_hist[-1]["value"]
                # 找 30 天前的点
                older_val = None
                for pt in bsr_hist:
                    if pt["value"] > 0:
                        older_val = pt["value"]
                if older_val and older_val > 0:
                    bsr_changes_30d.append((now_val - older_val) / older_val * 100)

            if price_hist and len(price_hist) >= 2:
                now_price = price_hist[-1]["value"]
                older_price = None
                for pt in price_hist:
                    if pt["value"] > 0:
                        older_price = pt["value"]
                if older_price and older_price > 0:
                    price_changes_30d.append((now_price - older_price) / older_price * 100)

        total = len(products)
        median_bsr_30 = round(median(bsr_changes_30d), 1) if bsr_changes_30d else None
        median_price_30 = round(median(price_changes_30d), 1) if price_changes_30d else None

        # 市场方向
        improving_pct = bsr_directions["improving"] / total * 100 if total else 0
        declining_pct = bsr_directions["declining"] / total * 100 if total else 0
        if improving_pct > 40:
            market_dir = "上升"
        elif declining_pct > 40:
            market_dir = "下降"
        else:
            market_dir = "稳定"

        # 月度聚合（季节性）
        seasonality = await self._calc_seasonality(products)

        return {
            "category": category_name or "all",
            "total_asins": total,
            "market_direction": market_dir,
            "bsr_trend": {
                "improving_count": bsr_directions["improving"],
                "declining_count": bsr_directions["declining"],
                "stable_count": bsr_directions["stable"],
                "improving_pct": round(improving_pct, 1),
                "declining_pct": round(declining_pct, 1),
                "median_change_30d_pct": median_bsr_30,
            },
            "price_trend": {
                "median_change_30d_pct": median_price_30,
                "direction": (
                    "上涨" if median_price_30 and median_price_30 > 3
                    else "下降" if median_price_30 and median_price_30 < -3
                    else "稳定"
                ),
            },
            "seasonality": seasonality,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

    async def _calc_seasonality(self, products: List[AmazonProduct]) -> Dict[str, Any]:
        """从 BSR 历史计算季节性"""
        monthly_bsr: Dict[int, List[float]] = {i: [] for i in range(1, 13)}
        monthly_price: Dict[int, List[float]] = {i: [] for i in range(1, 13)}

        for p in products:
            bsr_hist = p.bsr_history or []
            price_hist = p.price_history or []
            for pt in bsr_hist:
                ts = pt.get("timestamp", "")
                val = pt.get("value", 0)
                if ts and val > 0:
                    try:
                        month = datetime.fromisoformat(ts.replace("Z", "+00:00")).month
                        monthly_bsr[month].append(float(val))
                    except (ValueError, TypeError):
                        pass
            for pt in price_hist:
                ts = pt.get("timestamp", "")
                val = pt.get("value", 0)
                if ts and val > 0:
                    try:
                        month = datetime.fromisoformat(ts.replace("Z", "+00:00")).month
                        monthly_price[month].append(float(val))
                    except (ValueError, TypeError):
                        pass

        monthly_bsr_med = {}
        monthly_price_med = {}
        for m in range(1, 13):
            bvals = monthly_bsr.get(m, [])
            monthly_bsr_med[m] = round(median(bvals)) if bvals else None
            pvals = monthly_price.get(m, [])
            monthly_price_med[m] = round(median(pvals), 2) if pvals else None

        valid_bsr = [(m, v) for m, v in monthly_bsr_med.items() if v is not None]
        valid_bsr.sort(key=lambda x: x[1])
        peak_months = [m for m, _ in valid_bsr[:3]]
        low_months = [m for m, _ in valid_bsr[-3:]] if len(valid_bsr) >= 6 else []

        strength = "弱"
        if peak_months and low_months:
            peak_v = monthly_bsr_med.get(peak_months[0])
            low_v = monthly_bsr_med.get(low_months[0])
            if peak_v and low_v and peak_v > 0 and low_v / peak_v > 2:
                strength = "强"
            elif peak_v and low_v and peak_v > 0 and low_v / peak_v > 1.3:
                strength = "中"

        return {
            "peak_months": peak_months,
            "low_months": low_months,
            "strength": strength,
            "monthly_bsr_median": monthly_bsr_med,
            "monthly_price_median": monthly_price_med,
        }

    # ════════════════════════════════════════════════
    # M3: 价格分布
    # ════════════════════════════════════════════════

    async def get_price_distribution(
        self, category_name: Optional[str] = None, domain: str = "US",
    ) -> Dict[str, Any]:
        """
        价格分布统计。
        """
        conditions = [AmazonProduct.domain == domain]
        if category_name:
            conditions.append(AmazonProduct.category_name == category_name)

        stmt = select(AmazonProduct).where(and_(*conditions))
        result = await self.db.execute(stmt)
        products = list(result.scalars().all())

        if not products:
            return {"category": category_name or "all", "price_distribution": {}}

        price_dist = self._calc_price_distribution(products)
        prices = [p.current_price for p in products if p.current_price]

        prime_count = sum(1 for p in products if p.is_prime)
        prime_ratio = round(prime_count / len(products) * 100, 1) if products else 0

        return {
            "category": category_name or "all",
            "total_with_price": len(prices),
            "avg_price": round(sum(prices) / len(prices), 2) if prices else None,
            "min_price": min(prices) if prices else None,
            "max_price": max(prices) if prices else None,
            "median_price": round(median(prices), 2) if prices else None,
            "price_distribution": price_dist,
            "prime_ratio_pct": prime_ratio,
            "recommended_price_min": round(sum(prices) / len(prices) * 0.8, 2) if prices else None,
            "recommended_price_max": round(sum(prices) / len(prices) * 1.2, 2) if prices else None,
        }

    def _calc_price_distribution(self, products: List[AmazonProduct]) -> Dict[str, int]:
        """价格带分布"""
        bands = {
            "<$20": (0, 20),
            "$20-50": (20, 50),
            "$50-100": (50, 100),
            "$100-200": (100, 200),
            "$200+": (200, float("inf")),
        }
        result = {}
        for label, (lo, hi) in bands.items():
            count = sum(
                1 for p in products
                if p.current_price and lo <= p.current_price < hi
            )
            result[label] = count
        return result

    # ════════════════════════════════════════════════
    # M4: 品牌集中度
    # ════════════════════════════════════════════════

    async def get_brand_concentration(
        self, category_name: Optional[str] = None, domain: str = "US",
    ) -> Dict[str, Any]:
        """
        品牌集中度分析。
        聚合 per-brand 统计，计算市场份额和集中度指数。
        """
        conditions = [AmazonProduct.domain == domain]
        if category_name:
            conditions.append(AmazonProduct.category_name == category_name)

        stmt = select(AmazonProduct).where(and_(*conditions))
        result = await self.db.execute(stmt)
        products = list(result.scalars().all())

        if not products:
            return {"total_brands": 0, "brands": [], "concentration": "未知"}

        # 按品牌聚合
        brands: Dict[str, Dict] = {}
        for p in products:
            brand = p.brand or "Unknown"
            if brand not in brands:
                brands[brand] = {
                    "count": 0,
                    "total_sales": 0,
                    "prices": [],
                    "ratings": [],
                    "bsrs": [],
                    "best_bsr": 999999,
                    "best_bsr_asin": None,
                }
            b = brands[brand]
            b["count"] += 1
            b["total_sales"] += p.monthly_sold or 0
            if p.current_price:
                b["prices"].append(p.current_price)
            if p.rating:
                b["ratings"].append(p.rating)
            if p.current_bsr:
                b["bsrs"].append(p.current_bsr)
                if p.current_bsr < b["best_bsr"]:
                    b["best_bsr"] = p.current_bsr
                    b["best_bsr_asin"] = p.asin

        total_sales = sum(b["total_sales"] for b in brands.values())

        # 计算市场份额
        brand_list = []
        for brand, b in brands.items():
            share = (b["total_sales"] / total_sales * 100) if total_sales > 0 else 0
            brand_list.append({
                "brand": brand,
                "product_count": b["count"],
                "total_monthly_sales": b["total_sales"],
                "market_share_pct": round(share, 1),
                "avg_price": round(sum(b["prices"]) / len(b["prices"]), 2) if b["prices"] else None,
                "avg_rating": round(sum(b["ratings"]) / len(b["ratings"]), 2) if b["ratings"] else None,
                "avg_bsr": round(sum(b["bsrs"]) / len(b["bsrs"])) if b["bsrs"] else None,
                "best_bsr_asin": b["best_bsr_asin"],
            })

        brand_list.sort(key=lambda x: x["market_share_pct"], reverse=True)

        # 市场集中度判断
        top3_share = sum(b["market_share_pct"] for b in brand_list[:3])
        if top3_share > 80:
            concentration = "高（寡占型）"
            entry_barrier = "极高"
        elif top3_share > 50:
            concentration = "中（分散型）"
            entry_barrier = "中等"
        else:
            concentration = "低（竞争型）"
            entry_barrier = "较低"

        return {
            "total_brands": len(brands),
            "total_products": len(products),
            "top_3_market_share_pct": round(top3_share, 1),
            "concentration": concentration,
            "entry_barrier": entry_barrier,
            "brands": brand_list,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

    # ════════════════════════════════════════════════
    # M5: 评分数分布
    # ════════════════════════════════════════════════

    async def get_review_count_distribution(
        self, category_name: Optional[str] = None, domain: str = "US",
    ) -> Dict[str, Any]:
        """评论数分布统计"""
        conditions = [AmazonProduct.domain == domain]
        if category_name:
            conditions.append(AmazonProduct.category_name == category_name)

        stmt = select(AmazonProduct).where(and_(*conditions))
        result = await self.db.execute(stmt)
        products = list(result.scalars().all())

        if not products:
            return {"total_with_reviews": 0, "distribution": {}}

        reviews = [p.review_count for p in products if p.review_count is not None]
        if not reviews:
            return {"total_with_reviews": 0, "distribution": {}}

        bands = {
            "0-10": (0, 10),
            "10-50": (10, 50),
            "50-200": (50, 200),
            "200-1000": (200, 1000),
            "1000-5000": (1000, 5000),
            "5000+": (5000, float("inf")),
        }
        distribution = {}
        for label, (lo, hi) in bands.items():
            distribution[label] = sum(1 for r in reviews if lo <= r < hi)

        # 评论壁垒评估
        avg_reviews = sum(reviews) / len(reviews)
        if avg_reviews > 5000:
            barrier = "极高"
        elif avg_reviews > 1000:
            barrier = "高"
        elif avg_reviews > 200:
            barrier = "中"
        else:
            barrier = "低"

        return {
            "total_with_reviews": len(reviews),
            "avg_review_count": round(avg_reviews),
            "median_review_count": round(median(reviews)),
            "min_reviews": min(reviews),
            "max_reviews": max(reviews),
            "review_barrier": barrier,
            "distribution": distribution,
        }

    # ════════════════════════════════════════════════
    # M6: 评分值分布
    # ════════════════════════════════════════════════

    async def get_rating_distribution(
        self, category_name: Optional[str] = None, domain: str = "US",
    ) -> Dict[str, Any]:
        """评分分布统计"""
        conditions = [AmazonProduct.domain == domain]
        if category_name:
            conditions.append(AmazonProduct.category_name == category_name)

        stmt = select(AmazonProduct).where(and_(*conditions))
        result = await self.db.execute(stmt)
        products = list(result.scalars().all())

        if not products:
            return {"total_with_rating": 0, "distribution": {}}

        ratings = [p.rating for p in products if p.rating]
        if not ratings:
            return {"total_with_rating": 0, "distribution": {}}

        bands = {
            "4.0-5.0": (4.0, 5.0),
            "3.0-4.0": (3.0, 4.0),
            "2.0-3.0": (2.0, 3.0),
            "1.0-2.0": (1.0, 2.0),
        }
        distribution = {}
        for label, (lo, hi) in bands.items():
            distribution[label] = sum(1 for r in ratings if lo <= r < hi)

        # 评分健康度
        excellent = sum(1 for r in ratings if r >= 4.5)
        good = sum(1 for r in ratings if 4.0 <= r < 4.5)
        average = sum(1 for r in ratings if 3.0 <= r < 4.0)
        poor = sum(1 for r in ratings if r < 3.0)
        total = len(ratings)

        health_score = round((excellent * 100 + good * 75 + average * 50 + poor * 0) / total, 1) if total else 0

        return {
            "total_with_rating": total,
            "avg_rating": round(sum(ratings) / total, 2),
            "median_rating": round(median(ratings), 2),
            "rating_health_score": health_score,
            "rating_health_label": (
                "优秀" if health_score >= 80
                else "良好" if health_score >= 60
                else "一般" if health_score >= 40
                else "较差"
            ),
            "distribution": distribution,
            "distribution_detail": {
                "excellent_count": excellent,
                "good_count": good,
                "average_count": average,
                "poor_count": poor,
                "excellent_pct": round(excellent / total * 100, 1),
                "good_pct": round(good / total * 100, 1),
                "average_pct": round(average / total * 100, 1),
                "poor_pct": round(poor / total * 100, 1),
            },
        }

    # ════════════════════════════════════════════════
    # M7: 商品集中度
    # ════════════════════════════════════════════════

    async def get_product_concentration(
        self, category_name: Optional[str] = None, domain: str = "US",
    ) -> Dict[str, Any]:
        """
        商品集中度 — 卖家数分布、去重卖家数、头部卖家控制比例。
        """
        conditions = [AmazonProduct.domain == domain]
        if category_name:
            conditions.append(AmazonProduct.category_name == category_name)

        stmt = select(AmazonProduct).where(and_(*conditions))
        result = await self.db.execute(stmt)
        products = list(result.scalars().all())

        if not products:
            return {"total_products": 0, "seller_distribution": {}}

        seller_counts = [p.seller_count for p in products if p.seller_count is not None]
        seller_names = [p.seller_name for p in products if p.seller_name]

        # 卖家数分布
        bands = {
            "1-3 个卖家": (1, 3),
            "4-10 个卖家": (4, 10),
            "11-25 个卖家": (11, 25),
            "26-50 个卖家": (26, 50),
            "50+ 个卖家": (50, float("inf")),
        }
        distribution = {}
        for label, (lo, hi) in bands.items():
            distribution[label] = sum(1 for s in seller_counts if lo <= s < hi)

        return {
            "total_products": len(products),
            "total_with_seller_info": len(seller_counts),
            "avg_seller_count": round(sum(seller_counts) / len(seller_counts)) if seller_counts else None,
            "median_seller_count": round(median(seller_counts)) if seller_counts else None,
            "unique_seller_names": len(set(seller_names)),
            "seller_distribution": distribution,
        }

    # ════════════════════════════════════════════════
    # M8: 卖家类型分布
    # ════════════════════════════════════════════════

    async def get_seller_type_distribution(
        self, category_name: Optional[str] = None, domain: str = "US",
    ) -> Dict[str, Any]:
        """FBA / FBM / Amazon 自营分布"""
        conditions = [AmazonProduct.domain == domain]
        if category_name:
            conditions.append(AmazonProduct.category_name == category_name)

        stmt = select(AmazonProduct).where(and_(*conditions))
        result = await self.db.execute(stmt)
        products = list(result.scalars().all())

        if not products:
            return {"total": 0}

        fba = sum(1 for p in products if p.is_fba)
        fbm = sum(1 for p in products if p.fulfillment and "fba" not in p.fulfillment.lower())
        unknown = sum(1 for p in products if not p.fulfillment)
        prime = sum(1 for p in products if p.is_prime)
        total = len(products)

        return {
            "total_products": total,
            "fba_count": fba,
            "fba_pct": round(fba / total * 100, 1) if total else 0,
            "fbm_count": fbm,
            "fbm_pct": round(fbm / total * 100, 1) if total else 0,
            "unknown_count": unknown,
            "prime_count": prime,
            "prime_pct": round(prime / total * 100, 1) if total else 0,
        }

    # ════════════════════════════════════════════════
    # M9: A+ 视频分布
    # ════════════════════════════════════════════════

    async def get_aplus_video_distribution(
        self, category_name: Optional[str] = None, domain: str = "US",
    ) -> Dict[str, Any]:
        """A+ Content 和视频分布（Rainforest 独家数据）"""
        conditions = [AmazonProduct.domain == domain]
        if category_name:
            conditions.append(AmazonProduct.category_name == category_name)

        stmt = select(AmazonProduct).where(and_(*conditions))
        result = await self.db.execute(stmt)
        products = list(result.scalars().all())

        if not products:
            return {"total": 0}

        has_aplus = sum(1 for p in products if p.aplus_content)
        no_aplus = sum(1 for p in products if not p.aplus_content)
        with_video = sum(1 for p in products if p.videos_count and p.videos_count > 0)
        total = len(products)
        video_counts = [p.videos_count for p in products if p.videos_count]

        return {
            "total_products": total,
            "aplus_count": has_aplus,
            "aplus_pct": round(has_aplus / total * 100, 1) if total else 0,
            "no_aplus_count": no_aplus,
            "no_aplus_pct": round(no_aplus / total * 100, 1) if total else 0,
            "with_video_count": with_video,
            "with_video_pct": round(with_video / total * 100, 1) if total else 0,
            "avg_video_count": round(sum(video_counts) / len(video_counts)) if video_counts else 0,
        }

    # ════════════════════════════════════════════════
    # M10: 市场报告（组合 9 个维度）
    # ════════════════════════════════════════════════

    async def get_market_report(
        self, category_name: Optional[str] = None, domain: str = "US",
    ) -> Dict[str, Any]:
        """一次性返回市场分析全维度数据"""
        summary, trend, price_dist, brand_conc, review_dist, \
            rating_dist, seller_dist, seller_type, aplus = await asyncio.gather(
                self.get_market_summary(category_name, domain),
                self.get_market_trend(category_name, domain),
                self.get_price_distribution(category_name, domain),
                self.get_brand_concentration(category_name, domain),
                self.get_review_count_distribution(category_name, domain),
                self.get_rating_distribution(category_name, domain),
                self.get_product_concentration(category_name, domain),
                self.get_seller_type_distribution(category_name, domain),
                self.get_aplus_video_distribution(category_name, domain),
            )

        return {
            "category": category_name or "all",
            "domain": domain,
            "summary": summary,
            "trend": trend,
            "price_distribution": price_dist,
            "brand_concentration": brand_conc,
            "review_distribution": review_dist,
            "rating_distribution": rating_dist,
            "seller_distribution": seller_dist,
            "seller_type_distribution": seller_type,
            "aplus_video_distribution": aplus,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }