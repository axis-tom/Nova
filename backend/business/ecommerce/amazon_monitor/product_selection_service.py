"""
选品分析服务层 — 对标卖家精灵选品类 API
直接从 amazon_products 表查询，无需 Agent/State 管道

S1: 8 维度机会评分
S2: 关键词扩展+搜索选品
S3: 多维筛选选品
S4: 关键词选品趋势
S5: ASIN 详情及趋势
S6: ASIN 优惠趋势
"""
import logging
from typing import Any, Dict, List, Optional
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

from backend.data.repositories.postgreSQL.amazon_product_repo import AmazonProductRepository
from backend.data.models.amazon_product import AmazonProduct
from backend.business.ecommerce.amazon_monitor.scoring import (
    score_single_product,
    grade_distribution,
    calc_price_stability,
)

logger = logging.getLogger(__name__)


class ProductSelectionService:
    """选品分析服务 — 封装所有选品类分析查询"""

    def __init__(self, db: AsyncSession):
        self.repo = AmazonProductRepository(db)
        self.db = db

    # ── 工具：ORM → Dict ──

    def _product_to_dict(self, p: AmazonProduct) -> Dict:
        return {
            "asin": p.asin, "title": p.title, "brand": p.brand or "Unknown",
            "current_price": p.current_price, "current_bsr": p.current_bsr,
            "rating": p.rating, "review_count": p.review_count,
            "monthly_sold": p.monthly_sold, "seller_count": p.seller_count,
            "bsr_trend": p.bsr_trend, "bsr_history": p.bsr_history,
            "price_history": p.price_history,
            "avg_price_30d": p.avg_price_30d, "avg_price_90d": p.avg_price_90d,
            "min_price_90d": p.min_price_90d, "max_price_90d": p.max_price_90d,
            "feature_bullets": p.feature_bullets, "description": p.description,
            "main_image": p.main_image, "images": p.images,
            "is_fba": p.is_fba, "is_prime": p.is_prime,
            "aplus_content": p.aplus_content,
            "parent_asin": p.parent_asin, "child_asins": p.child_asins,
            "rating_breakdown": p.rating_breakdown,
            "seller_name": p.seller_name, "fulfillment": p.fulfillment,
            "availability": p.availability,
            "category_name": p.category_name,
            "importance_score": p.importance_score,
            "importance_tier": p.importance_tier,
            "data_source": p.data_source,
            "review_velocity_30d": p.review_velocity_30d,
            "review_count_history": p.review_count_history,
            "review_improv_30d": p.review_improv_30d,
            "sponsored_products": p.sponsored_products,
        }

    # ════════════════════════════════════════════
    # S1: 8 维度机会评分
    # ════════════════════════════════════════════

    async def score_opportunities(
        self,
        category: Optional[str] = None,
        asins: Optional[List[str]] = None,
        domain: str = "US",
        min_score: int = 60,
        top_n: int = 20,
    ) -> Dict[str, Any]:
        """对指定类目或 ASIN 列表做 8 维机会评分"""
        products = await self._load_products(asins=asins, category=category, domain=domain)
        if not products:
            return {"total": 0, "scored_products": [], "message": "未找到商品"}

        scored = []
        for p in products:
            d = self._product_to_dict(p)
            score = score_single_product(d)
            if score["total_score"] >= min_score:
                scored.append({**d, **score})

        scored.sort(key=lambda x: x["total_score"], reverse=True)
        top = scored[:top_n]

        return {
            "category": category,
            "total_products": len(products),
            "scored_count": len(scored),
            "top_picks": [
                {
                    "rank": i + 1,
                    "asin": s["asin"],
                    "title": (s["title"] or "")[:80],
                    "brand": s["brand"],
                    "current_price": s["current_price"],
                    "current_bsr": s["current_bsr"],
                    "rating": s["rating"],
                    "review_count": s["review_count"],
                    "monthly_sold": s["monthly_sold"],
                    "total_score": s["total_score"],
                    "score_grade": s["score_grade"],
                    "score_detail": s["score_detail"],
                    "highlights": s["highlights"],
                    "importance_tier": s["importance_tier"],
                }
                for i, s in enumerate(top)
            ],
            "grade_distribution": grade_distribution(scored),
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

    # ════════════════════════════════════════════
    # S2: 关键词扩展+搜索选品
    # ════════════════════════════════════════════

    async def keyword_search_selection(
        self,
        keyword: str,
        domain: str = "US",
        expand: bool = True,
        top_n: int = 20,
    ) -> Dict[str, Any]:
        """
        关键词 → 搜索 → 返回 amazon_products 中匹配的商品。

        如果 expand=True，扩充 N 个变体词分别搜索。
        实际搜索委托给 product_collector（调 Canopy/Rainforest）。
        此处只查本地表已有数据。
        """
        category = keyword
        products = await self._load_products(category=category, domain=domain)
        if not products:
            return {
                "keyword": keyword,
                "total": 0,
                "message": f"类目「{keyword}」暂无数据，请先通过聊天采集",
                "hint": "请在对话中发送「采集 {keyword} 的商品数据」",
            }

        dicts = [self._product_to_dict(p) for p in products]

        # 排序取 top_n
        dicts.sort(key=lambda p: p.get("monthly_sold") or 0, reverse=True)
        top = dicts[:top_n]

        return {
            "keyword": keyword,
            "domain": domain,
            "total_in_db": len(dicts),
            "products": [
                {
                    "asin": p["asin"],
                    "title": (p["title"] or "")[:80],
                    "brand": p["brand"],
                    "current_price": p["current_price"],
                    "current_bsr": p["current_bsr"],
                    "rating": p["rating"],
                    "review_count": p["review_count"],
                    "monthly_sold": p["monthly_sold"],
                    "seller_count": p["seller_count"],
                    "main_image": p["main_image"],
                    "importance_tier": p["importance_tier"],
                }
                for p in top
            ],
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

    # ════════════════════════════════════════════
    # S3: 多维筛选选品
    # ════════════════════════════════════════════

    async def filter_products(
        self,
        domain: str = "US",
        category: Optional[str] = None,
        tier: Optional[str] = None,
        min_rating: Optional[float] = None,
        min_review_count: Optional[int] = None,
        min_monthly_sold: Optional[int] = None,
        min_price: Optional[float] = None,
        max_price: Optional[float] = None,
        max_bsr: Optional[int] = None,
        has_aplus: Optional[bool] = None,
        is_fba: Optional[bool] = None,
        sort_by: str = "importance_score",
        sort_desc: bool = True,
        limit: int = 50,
        offset: int = 0,
    ) -> Dict[str, Any]:
        """多维条件筛选选品（直接映射 search_products 筛选条件）"""
        products, total = await self.repo.search_products(
            domain=domain,
            tier=tier,
            min_rating=min_rating,
            min_review_count=min_review_count,
            min_monthly_sold=min_monthly_sold,
            min_price=min_price,
            max_price=max_price,
            max_bsr=max_bsr,
            has_aplus=has_aplus,
            is_fba=is_fba,
            sort_by=sort_by,
            sort_desc=sort_desc,
            limit=limit,
            offset=offset,
        )

        return {
            "total": total,
            "returned": len(products),
            "limit": limit,
            "offset": offset,
            "products": [
                {
                    "asin": p.asin,
                    "title": (p.title or "")[:80],
                    "brand": p.brand,
                    "current_price": p.current_price,
                    "current_bsr": p.current_bsr,
                    "rating": p.rating,
                    "review_count": p.review_count,
                    "monthly_sold": p.monthly_sold,
                    "seller_count": p.seller_count,
                    "main_image": p.main_image,
                    "is_fba": p.is_fba,
                    "is_prime": p.is_prime,
                    "has_aplus": bool(p.aplus_content),
                    "importance_score": p.importance_score,
                    "importance_tier": p.importance_tier,
                    "category_name": p.category_name,
                }
                for p in products
            ],
            "filters_applied": {
                "domain": domain, "category": category, "tier": tier,
                "min_rating": min_rating, "min_review_count": min_review_count,
                "min_monthly_sold": min_monthly_sold,
                "min_price": min_price, "max_price": max_price,
                "max_bsr": max_bsr, "has_aplus": has_aplus, "is_fba": is_fba,
            },
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

    # ════════════════════════════════════════════
    # S4: 关键词选品趋势
    # ════════════════════════════════════════════

    async def keyword_product_trends(
        self,
        keyword: str,
        domain: str = "US",
        top_n: int = 10,
        days: int = 90,
    ) -> Dict[str, Any]:
        """关键词匹配商品 + 趋势数据（price_history, bsr_history）"""
        products = await self._load_products(category=keyword, domain=domain)
        if not products:
            return {"keyword": keyword, "total": 0, "message": "暂无数据"}

        dicts = [self._product_to_dict(p) for p in products]
        dicts.sort(key=lambda p: p.get("monthly_sold") or 0, reverse=True)
        top = dicts[:top_n]

        return {
            "keyword": keyword,
            "domain": domain,
            "total_in_db": len(dicts),
            "products": [
                {
                    "asin": p["asin"],
                    "title": (p["title"] or "")[:80],
                    "current_price": p["current_price"],
                    "current_bsr": p["current_bsr"],
                    "rating": p["rating"],
                    "review_count": p["review_count"],
                    "monthly_sold": p["monthly_sold"],
                    "price_history": self._trim_history(p.get("price_history"), days),
                    "bsr_history": self._trim_history(p.get("bsr_history"), days),
                    "avg_price_90d": p["avg_price_90d"],
                    "min_price_90d": p["min_price_90d"],
                    "max_price_90d": p["max_price_90d"],
                    "bsr_trend": p["bsr_trend"],
                    "price_stability": calc_price_stability(p),
                }
                for p in top
            ],
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

    # ════════════════════════════════════════════
    # S5: ASIN 详情及趋势
    # ════════════════════════════════════════════

    async def asin_detail_with_trends(
        self,
        asin: str,
        domain: str = "US",
        days: int = 90,
    ) -> Optional[Dict[str, Any]]:
        """单个 ASIN 完整详情 + Keepa 趋势"""
        product = await self.repo.get_by_asin(asin, domain)
        if not product:
            return None

        p = self._product_to_dict(product)

        return {
            "asin": p["asin"],
            "title": p["title"],
            "brand": p["brand"],
            "category": p["category_name"],
            "main_image": p["main_image"],
            "images": p["images"],
            "feature_bullets": p["feature_bullets"],
            "description": p["description"],
            "aplus_content": p["aplus_content"],
            "current_price": p["current_price"],
            "current_bsr": p["current_bsr"],
            "rating": p["rating"],
            "rating_breakdown": p["rating_breakdown"],
            "review_count": p["review_count"],
            "review_velocity_30d": p["review_velocity_30d"],
            "monthly_sold": p["monthly_sold"],
            "estimated_revenue": round(
                (p["monthly_sold"] or 0) * (p["current_price"] or 0), 2
            ),
            "seller_count": p["seller_count"],
            "seller_name": p["seller_name"],
            "is_fba": p["is_fba"],
            "is_prime": p["is_prime"],
            "fulfillment": p["fulfillment"],
            "availability": p["availability"],
            "parent_asin": p["parent_asin"],
            "variation_count": len(p["child_asins"]) if p["child_asins"] else 0,
            "importance_score": p["importance_score"],
            "importance_tier": p["importance_tier"],
            "trends": {
                "price_history": self._trim_history(p.get("price_history"), days),
                "bsr_history": self._trim_history(p.get("bsr_history"), days),
                "bsr_trend": p["bsr_trend"],
                "avg_price_90d": p["avg_price_90d"],
                "min_price_90d": p["min_price_90d"],
                "max_price_90d": p["max_price_90d"],
                "price_stability": calc_price_stability(p),
            },
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

    # ════════════════════════════════════════════
    # S6: ASIN 优惠趋势
    # ════════════════════════════════════════════

    async def asin_deal_trends(
        self,
        asin: str,
        domain: str = "US",
        days: int = 90,
    ) -> Optional[Dict[str, Any]]:
        """基于 price_history 的优惠趋势分析"""
        product = await self.repo.get_by_asin(asin, domain)
        if not product:
            return None

        price_history = product.price_history or []
        if not price_history or len(price_history) < 5:
            return {
                "asin": asin,
                "message": "价格历史数据不足（至少需要 5 个数据点）",
            }

        prices = [p["value"] for p in price_history if p.get("value", 0) > 0]
        timestamps = [p.get("timestamp") for p in price_history if p.get("value", 0) > 0]

        if not prices:
            return {"asin": asin, "message": "无有效价格数据"}

        # 优惠检测：价格显著低于平均值
        avg_price = sum(prices) / len(prices)
        deal_threshold = avg_price * 0.85  # 低于均价 15% 视为优惠

        deals = []
        for i, price in enumerate(prices):
            if price <= deal_threshold:
                pct_off = round((1 - price / avg_price) * 100, 1)
                deals.append({
                    "price": price,
                    "timestamp": timestamps[i] if i < len(timestamps) else None,
                    "discount_pct": pct_off,
                    "vs_avg": round(price - avg_price, 2),
                })

        # 限时优惠检测：价格回弹模式
        flash_deals = []
        for i in range(2, len(prices)):
            if prices[i] < avg_price * 0.8 and prices[i - 1] >= prices[i] and (i + 1 < len(prices) and prices[i + 1] > prices[i] * 1.1):
                flash_deals.append({
                    "deal_price": prices[i],
                    "recovery_price": prices[i + 1] if i + 1 < len(prices) else None,
                    "timestamp": timestamps[i] if i < len(timestamps) else None,
                    "discount_pct": round((1 - prices[i] / avg_price) * 100, 1),
                })

        return {
            "asin": asin,
            "title": (product.title or "")[:80],
            "current_price": product.current_price,
            "avg_price_90d": product.avg_price_90d,
            "price_stability": calc_price_stability(self._product_to_dict(product)),
            "deal_analysis": {
                "total_price_points": len(prices),
                "avg_price": round(avg_price, 2),
                "min_price": min(prices),
                "max_price": max(prices),
                "deal_count": len(deals),
                "flash_deal_count": len(flash_deals),
                "avg_discount_when_on_deal": round(
                    sum(d["discount_pct"] for d in deals) / len(deals), 1
                ) if deals else None,
            },
            "recent_deals": deals[-10:] if len(deals) > 10 else deals,
            "flash_deals": flash_deals[-5:] if len(flash_deals) > 5 else flash_deals,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

    # ── 工具方法 ──

    async def _load_products(
        self, asins: Optional[List[str]] = None, category: Optional[str] = None, domain: str = "US",
    ) -> List[AmazonProduct]:
        conditions = [AmazonProduct.domain == domain]
        if asins:
            conditions.append(AmazonProduct.asin.in_(asins))
        elif category:
            conditions.append(AmazonProduct.category_name == category)
        else:
            return []

        stmt = select(AmazonProduct).where(and_(*conditions))
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    def _trim_history(self, history: Optional[List], days: int = 90) -> List:
        """截取最近 N 天的历史数据"""
        if not history:
            return []
        if days <= 0:
            return history
        # 如果历史有 timestamp 字段且可用
        if isinstance(history, list) and len(history) > 0:
            return history[-days:] if len(history) > days else history
        return history

    def _calc_price_stability_label(self, p: Dict) -> Dict:
        min_p = p.get("min_price_90d")
        max_p = p.get("max_price_90d")
        avg_p = p.get("avg_price_90d") or p.get("current_price")
        if min_p and max_p and avg_p and avg_p > 0:
            vol = (max_p - min_p) / avg_p
            label = "极稳定" if vol <= 0.05 else "稳定" if vol <= 0.15 else "一般" if vol <= 0.30 else "不稳定"
            return {"label": label, "volatility_pct": round(vol * 100, 1)}
        return {"label": "未知", "volatility_pct": None}