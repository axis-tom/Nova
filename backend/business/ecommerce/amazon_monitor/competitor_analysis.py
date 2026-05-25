"""
竞品分析服务层 — 对标卖家精灵竞品类 API
直接从 amazon_products 表查询，复用 CompetitorAnalystAgent 的分析逻辑

C1: 查竞品 Profile（竞品卡片）
C2: Head-to-Head 对比
C3: 定价策略分类
C4: Listing 质量评分
C5: 差异化机会识别
C6: 卖家报价详情
"""

import math
import logging
from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime, timezone
from statistics import median

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

from backend.data.repositories.postgreSQL.amazon_product_repo import AmazonProductRepository
from backend.data.models.amazon_product import AmazonProduct

logger = logging.getLogger(__name__)


class CompetitorAnalysisService:
    """竞品分析服务 — 从 amazon_products 表查询竞品数据"""

    def __init__(self, db: AsyncSession):
        self.repo = AmazonProductRepository(db)
        self.db = db

    # ── 工具：加载商品数据 ──

    async def _load_products(
        self, asins: Optional[List[str]] = None, category: Optional[str] = None, domain: str = "US",
    ) -> List[AmazonProduct]:
        """加载商品数据"""
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

    def _product_to_dict(self, p: AmazonProduct) -> Dict:
        """ORM → Dict"""
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
        }

    # ════════════════════════════════════════════
    # C1: 查竞品 Profile
    # ════════════════════════════════════════════

    async def get_competitor_profile(
        self, asin: str, domain: str = "US",
    ) -> Optional[Dict[str, Any]]:
        """单个竞品详细 Profile"""
        product = await self.repo.get_by_asin(asin, domain)
        if not product:
            return None

        p = self._product_to_dict(product)

        # 价格稳定性
        price_stability = self._calc_price_stability(p)

        return {
            "asin": p["asin"],
            "title": p["title"],
            "brand": p["brand"],
            "category": p["category_name"],
            "main_image": p["main_image"],
            "current_price": p["current_price"],
            "current_bsr": p["current_bsr"],
            "rating": p["rating"],
            "review_count": p["review_count"],
            "monthly_sold": p["monthly_sold"],
            "estimated_monthly_revenue": round(
                (p["monthly_sold"] or 0) * (p["current_price"] or 0), 2
            ),
            "seller_count": p["seller_count"],
            "seller_name": p["seller_name"],
            "is_fba": p["is_fba"],
            "is_prime": p["is_prime"],
            "bsr_trend": p["bsr_trend"],
            "price_stability": price_stability,
            "listing_quality_score": self._score_listing_quality(p),
            "has_aplus": bool(p["aplus_content"]),
            "has_video": bool(p.get("images") and len(p.get("images", [])) > 1),
            "variation_count": len(p["child_asins"]) if p["child_asins"] else 0,
            "importance_score": p["importance_score"],
            "importance_tier": p["importance_tier"],
            "data_sources": p["data_source"],
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

    # ════════════════════════════════════════════
    # C2: Head-to-Head 对比
    # ════════════════════════════════════════════

    async def compare_products(
        self, asins: List[str], domain: str = "US",
    ) -> Dict[str, Any]:
        """指定 ASIN 的头对头对比"""
        products_map = await self.repo.get_by_asins(asins, domain)
        products = [products_map[a] for a in asins if a in products_map]

        if not products:
            return {"error": "未找到指定 ASIN", "asins_requested": asins}

        details = []
        for p in products:
            d = self._product_to_dict(p)
            details.append({
                "asin": d["asin"],
                "title": (d["title"] or "")[:80],
                "brand": d["brand"],
                "current_price": d["current_price"],
                "current_bsr": d["current_bsr"],
                "rating": d["rating"],
                "review_count": d["review_count"],
                "monthly_sold": d["monthly_sold"],
                "seller_count": d["seller_count"],
                "seller_name": d["seller_name"],
                "is_fba": d["is_fba"],
                "is_prime": d["is_prime"],
                "bsr_trend": d["bsr_trend"],
                "price_stability": self._calc_price_stability(d),
                "listing_quality_score": self._score_listing_quality(d),
                "price_pattern": self._classify_price_pattern(d.get("price_history") or []),
                "has_aplus": bool(d["aplus_content"]),
                "variation_count": len(d["child_asins"]) if d["child_asins"] else 0,
                "main_image": d["main_image"],
                "importance_score": d["importance_score"],
                "importance_tier": d["importance_tier"],
            })

        prices = [d["current_price"] for d in details if d["current_price"]]
        ratings = [d["rating"] for d in details if d["rating"]]
        bsrs = [d["current_bsr"] for d in details if d["current_bsr"]]
        solds = [d["monthly_sold"] for d in details if d["monthly_sold"]]

        return {
            "products_compared": len(details),
            "details": details,
            "cross_comparison": {
                "price_range": {
                    "min": min(prices) if prices else None,
                    "max": max(prices) if prices else None,
                },
                "avg_rating": round(sum(ratings) / len(ratings), 2) if ratings else None,
                "total_monthly_sold": sum(solds) if solds else None,
                "all_prime": all(d["is_prime"] for d in details if d["is_prime"] is not None),
                "all_fba": all(d["is_fba"] for d in details if d["is_fba"] is not None),
                "best_bsr": min(bsrs) if bsrs else None,
                "best_bsr_asin": min(details, key=lambda d: d["current_bsr"] or 999999)["asin"] if bsrs else None,
                "best_rating_asin": max(details, key=lambda d: d["rating"] or 0)["asin"] if ratings else None,
            },
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

    # ════════════════════════════════════════════
    # C3: 定价策略分类
    # ════════════════════════════════════════════

    async def classify_price_strategy(
        self, asin: str, domain: str = "US",
    ) -> Dict[str, Any]:
        """识别 ASIN 的定价策略"""
        product = await self.repo.get_by_asin(asin, domain)
        if not product:
            return {"error": f"ASIN {asin} 未找到"}

        price_history = product.price_history or []
        pattern = self._classify_price_pattern(price_history)

        result = {
            "asin": asin,
            "title": (product.title or "")[:80],
            "current_price": product.current_price,
            "price_pattern": pattern["label"],
            "pattern_detail": pattern["detail"],
            "price_changes_30d": pattern["changes_30d"],
            "price_changes_90d": pattern["changes_90d"],
        }

        if price_history:
            prices_90d = [p["value"] for p in price_history[-50:] if p.get("value", 0) > 0]
            if prices_90d:
                result["price_min_90d"] = min(prices_90d)
                result["price_max_90d"] = max(prices_90d)
                result["price_avg_90d"] = round(sum(prices_90d) / len(prices_90d), 2)

        return result

    def _classify_price_pattern(self, price_history: List[Dict]) -> Dict:
        """从 price_history 识别定价模式"""
        if not price_history or len(price_history) < 10:
            return {"label": "数据不足", "detail": "历史数据不足 10 个点, 无法识别定价模式", "changes_30d": None, "changes_90d": None}

        prices = [p["value"] for p in price_history if p.get("value", 0) > 0]
        if len(prices) < 10:
            return {"label": "数据不足", "detail": "有效价格点不足 10 个", "changes_30d": None, "changes_90d": None}

        # 分段
        mid = len(prices) // 2
        recent_avg = sum(prices[mid:]) / len(prices[mid:])
        older_avg = sum(prices[:mid]) / len(prices[:mid])
        change_pct = (recent_avg - older_avg) / older_avg * 100 if older_avg > 0 else 0

        # 波动率
        volatility = (max(prices) - min(prices)) / sum(prices) * len(prices) if prices else 0

        # 最近 30 天变化
        prices_30 = prices[-30:] if len(prices) >= 30 else prices
        changes_30d = None
        if len(prices_30) >= 10:
            mid_30 = len(prices_30) // 2
            recent_30 = sum(prices_30[mid_30:]) / len(prices_30[mid_30:])
            old_30 = sum(prices_30[:mid_30]) / len(prices_30[:mid_30])
            changes_30d = round((recent_30 - old_30) / old_30 * 100, 1) if old_30 > 0 else 0

        changes_90d = round(change_pct, 1)

        if volatility < 0.05 and abs(change_pct) < 3:
            label, detail = "稳定", "价格长期稳定，波动极小"
        elif change_pct < -5 and abs(change_pct) > 5:
            label, detail = "持续降价", "整体呈降价趋势，可能清仓或价格战"
        elif change_pct > 5:
            label, detail = "持续涨价", "持续涨价中，产品溢价能力强"
        elif volatility > 0.2:
            label, detail = "频繁波动", "价格波动频繁，可能频繁调价测试市场"
        else:
            label, detail = "小幅调整", "价格有微调，总体稳定"

        return {"label": label, "detail": detail, "changes_30d": changes_30d, "changes_90d": changes_90d}

    # ════════════════════════════════════════════
    # C4: Listing 质量评分
    # ════════════════════════════════════════════

    async def score_listing_quality(
        self, asin: str, domain: str = "US",
    ) -> Dict[str, Any]:
        """单品 Listing 质量评分"""
        product = await self.repo.get_by_asin(asin, domain)
        if not product:
            return {"error": f"ASIN {asin} 未找到"}

        p = self._product_to_dict(product)
        score = self._score_listing_quality(p)

        return {
            "asin": asin,
            "title": (p["title"] or "")[:80],
            "total_score": score,
            "grade": self._grade_listing(score),
            "details": {
                "bullet_points": self._score_bullets(p.get("feature_bullets") or []),
                "images_count": self._score_images(p.get("images") or []),
                "aplus_content": 2 if p.get("aplus_content") else 0,
                "description": 1 if p.get("description") else 0,
                "has_video": 1 if (p.get("images") and len(p.get("images", [])) > 1) else 0,
            },
            "max_score": 10,
            "analysis": self._listing_quality_analysis(p, score),
        }

    def _score_listing_quality(self, p: Dict) -> int:
        """10 分制 Listing 质量评分"""
        score = 0
        bullets = p.get("feature_bullets") or []
        images = p.get("images") or []

        score += self._score_bullets(bullets)
        score += self._score_images(images)
        score += 2 if p.get("aplus_content") else 0
        score += 1 if p.get("description") else 0
        score += 1 if (images and len(images) > 1) else 0

        return min(score, 10)

    def _score_bullets(self, bullets: List) -> int:
        """五点描述评分（0-3）"""
        count = len(bullets) if isinstance(bullets, list) else 0
        if count >= 5: return 3
        if count >= 3: return 2
        if count >= 1: return 1
        return 0

    def _score_images(self, images: List) -> int:
        """图片评分（0-3）"""
        count = len(images) if isinstance(images, list) else 0
        if count >= 7: return 3
        if count >= 4: return 2
        if count >= 1: return 1
        return 0

    def _grade_listing(self, score: int) -> str:
        if score >= 9: return "优秀"
        if score >= 7: return "良好"
        if score >= 5: return "一般"
        return "薄弱"

    def _listing_quality_analysis(self, p: Dict, score: int) -> Dict:
        """给出改进建议"""
        suggestions = []
        bullets = p.get("feature_bullets") or []
        images = p.get("images") or []

        if len(bullets) < 5:
            suggestions.append(f"五点描述仅 {len(bullets)} 条，建议补全至 5 条")
        if len(images) < 6:
            suggestions.append("主图数量不足 6 张，建议增加")
        if not p.get("aplus_content"):
            suggestions.append("缺少 A+ Content，可显著提升转化率")
        if not p.get("description"):
            suggestions.append("缺少商品描述")
        if len(images) <= 1:
            suggestions.append("缺少商品视频/多角度图")

        return {"score": score, "grade": self._grade_listing(score), "suggestions": suggestions}

    # ════════════════════════════════════════════
    # C5: 差异化机会识别
    # ════════════════════════════════════════════

    async def identify_opportunities(
        self, category: str, domain: str = "US",
    ) -> Dict[str, Any]:
        """识别该品类的差异化机会"""
        products = await self._load_products(category=category, domain=domain)
        if not products:
            return {"category": category, "total_products": 0, "opportunities": []}

        products_dicts = [self._product_to_dict(p) for p in products]

        # 品牌聚合
        brands = self._aggregate_brands(products_dicts)
        total_sales = sum(b["total_sales"] for b in brands.values())

        opportunities = []

        # 1. 价格带空白
        price_bands = self._calc_price_band_gaps(products_dicts)
        for band, info in price_bands.items():
            if info["count"] == 0:
                opportunities.append({
                    "type": "价格带空白",
                    "title": f"价格带空白：{band}",
                    "detail": "该价格区间无商品在售，可考虑作为差异化切入点",
                    "potential": "中",
                })
            elif info["count"] == 1:
                opportunities.append({
                    "type": "价格带竞争低",
                    "title": f"价格带竞争低：{band}（仅 {info['count']} 个商品）",
                    "detail": f"平均 BSR {info.get('avg_bsr', 'N/A')}，竞争程度较低",
                    "potential": "高",
                })

        # 2. 上升中的小品牌
        for brand_name, b in sorted(brands.items(), key=lambda x: -x[1]["total_sales"]):
            share = (b["total_sales"] / total_sales * 100) if total_sales > 0 else 0
            if share > 0 and share < 10 and b.get("improving_count", 0) >= b["count"] * 0.5:
                opportunities.append({
                    "type": "上升中的小品牌",
                    "title": f"品牌 {brand_name} 上升中",
                    "detail": f"市场份额 {share:.1f}%，超半数商品 BSR 改善，存在对标或合作机会",
                    "potential": "高",
                })

        # 3. 评分低洼竞品
        for brand_name, b in sorted(brands.items(), key=lambda x: x[1].get("avg_rating", 5) or 5):
            avg_rating = b.get("avg_rating") or 5
            total_reviews = b.get("total_reviews", 0)
            share = (b["total_sales"] / total_sales * 100) if total_sales > 0 else 0
            if avg_rating < 3.8 and total_reviews > 500 and share > 5:
                opportunities.append({
                    "type": "评分低洼竞品",
                    "title": f"品牌 {brand_name} 评分低",
                    "detail": f"评分仅 {avg_rating}（{total_reviews} 条评论），用户满意度低，存在切入机会",
                    "potential": "高",
                })

        # 4. Listing 质量差但销量好的
        low_listing = [
            p for p in products_dicts
            if self._score_listing_quality(p) <= 5 and (p.get("monthly_sold") or 0) > 200
        ]
        if low_listing:
            opportunities.append({
                "type": "Listing 质量洼地",
                "title": "高销量但 Listing 质量差的商品",
                "detail": f"{len(low_listing)} 个商品月销 200+ 但 Listing 评分 ≤5，优化 Listing 即可超越",
                "potential": "高",
                "asins": [p["asin"] for p in low_listing[:5]],
            })

        # 5. 高需求低竞争（销量大但卖家少）
        high_demand_low_comp = [
            p for p in products_dicts
            if (p.get("monthly_sold") or 0) > 100 and (p.get("seller_count") or 0) < 5
        ]
        if high_demand_low_comp:
            opportunities.append({
                "type": "高需求低竞争",
                "title": "需求旺盛但供给不足的商品",
                "detail": f"{len(high_demand_low_comp)} 个商品月销>100 但卖家<5",
                "potential": "高",
                "asins": [p["asin"] for p in high_demand_low_comp[:5]],
            })

        return {
            "category": category,
            "total_products": len(products),
            "total_brands": len(brands),
            "opportunity_count": len(opportunities),
            "opportunities": opportunities,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

    # ════════════════════════════════════════════
    # C6: 卖家报价详情
    # ════════════════════════════════════════════

    async def get_seller_details(
        self, asin: str, domain: str = "US",
    ) -> Dict[str, Any]:
        """展示 ASIN 的卖家报价详情"""
        product = await self.repo.get_by_asin(asin, domain)
        if not product:
            return {"error": f"ASIN {asin} 未找到"}

        p = self._product_to_dict(product)

        return {
            "asin": asin,
            "title": (p["title"] or "")[:80],
            "seller_count": p["seller_count"],
            "seller_name": p["seller_name"],
            "is_fba": p["is_fba"],
            "fulfillment": p["fulfillment"],
            "availability": p["availability"],
            "is_prime": p["is_prime"],
            "current_price": p["current_price"],
            "estimated_revenue": round(
                (p["monthly_sold"] or 0) * (p["current_price"] or 0), 2
            ),
            "analysis": {
                "fba_status": "FBA" if p["is_fba"] else "FBM / 未知",
                "competition_level": (
                    "极高" if (p["seller_count"] or 0) > 50
                    else "高" if (p["seller_count"] or 0) > 20
                    else "中" if (p["seller_count"] or 0) > 10
                    else "低" if (p["seller_count"] or 0) > 0
                    else "未知"
                ),
                "buybox_risk": (
                    "高" if (p["seller_count"] or 0) > 20
                    else "中" if (p["seller_count"] or 0) > 10
                    else "低"
                ),
            },
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

    # ════════════════════════════════════════════
    # 工具方法
    # ════════════════════════════════════════════

    def _calc_price_stability(self, p: Dict) -> Dict:
        """计算价格稳定性"""
        min_price = p.get("min_price_90d")
        max_price = p.get("max_price_90d")
        avg_price = p.get("avg_price_90d") or p.get("current_price")

        if min_price and max_price and avg_price and avg_price > 0:
            volatility = (max_price - min_price) / avg_price
            if volatility <= 0.05:
                return {"label": "极稳定", "volatility_pct": round(volatility * 100, 1)}
            elif volatility <= 0.15:
                return {"label": "稳定", "volatility_pct": round(volatility * 100, 1)}
            elif volatility <= 0.30:
                return {"label": "一般", "volatility_pct": round(volatility * 100, 1)}
            else:
                return {"label": "不稳定", "volatility_pct": round(volatility * 100, 1)}
        return {"label": "未知", "volatility_pct": None}

    def _aggregate_brands(self, products: List[Dict]) -> Dict[str, Dict]:
        """按品牌聚合"""
        brands: Dict[str, Dict] = {}
        for p in products:
            brand = p.get("brand") or "Unknown"
            if brand not in brands:
                brands[brand] = {
                    "count": 0, "total_sales": 0, "total_reviews": 0,
                    "prices": [], "ratings": [], "bsrs": [],
                    "improving_count": 0, "declining_count": 0,
                }
            b = brands[brand]
            b["count"] += 1
            b["total_sales"] += p.get("monthly_sold", 0) or 0
            b["total_reviews"] += p.get("review_count", 0) or 0
            if p.get("current_price"): b["prices"].append(p["current_price"])
            if p.get("rating"): b["ratings"].append(p["rating"])
            if p.get("current_bsr"): b["bsrs"].append(p["current_bsr"])
            if p.get("bsr_trend") == "improving": b["improving_count"] += 1
            if p.get("bsr_trend") == "declining": b["declining_count"] += 1

        result = {}
        for brand, b in brands.items():
            result[brand] = {
                "count": b["count"],
                "total_sales": b["total_sales"],
                "total_reviews": b["total_reviews"],
                "avg_price": round(sum(b["prices"]) / len(b["prices"]), 2) if b["prices"] else None,
                "avg_rating": round(sum(b["ratings"]) / len(b["ratings"]), 2) if b["ratings"] else None,
                "avg_bsr": round(sum(b["bsrs"]) / len(b["bsrs"])) if b["bsrs"] else None,
                "improving_count": b["improving_count"],
                "declining_count": b["declining_count"],
            }
        return result

    def _calc_price_band_gaps(self, products: List[Dict]) -> Dict[str, Dict]:
        """价格带分析"""
        bands = {
            "<$20": (0, 20), "$20-50": (20, 50), "$50-100": (50, 100),
            "$100-200": (100, 200), "$200+": (200, float("inf")),
        }
        result = {}
        for label, (lo, hi) in bands.items():
            in_band = [p for p in products if p.get("current_price") and lo <= p["current_price"] < hi]
            bsrs = [p["current_bsr"] for p in in_band if p.get("current_bsr")]
            result[label] = {
                "count": len(in_band),
                "avg_bsr": round(sum(bsrs) / len(bsrs)) if bsrs else None,
            }
        return result