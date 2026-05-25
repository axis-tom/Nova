"""
评论分析 Agent - Amazon 监控场景

职责：
1. 读取 state.collected_products（Keepa 采集的真实商品数据）
2. 基于评分、评论数、BSR 趋势、价格等数据做评论/评分洞察
3. 生成情感分析摘要和客户需求推断
4. 识别高口碑 / 低口碑 / 评论壁垒等特征

数据源：state.collected_products（由 product_collector 通过 Keepa 采集）
"""

import json as _json
from typing import Any, Dict, List, Optional
from datetime import datetime

from backend.common.core.agent import Agent, AgentInput, AgentOutput
from backend.common.core.state import State
from backend.utils.logger import logger
from backend.data.database import AsyncSessionLocal
from backend.data.repositories.postgreSQL.amazon_product_repo import AmazonProductRepository


class AmazonReviewAnalyzerAgent(Agent):
    """评论分析 Agent — 基于 Keepa 真实数据做评分洞察和用户需求推断"""

    name = "review_analyzer"
    description = "Amazon 评论分析 Agent，基于 Keepa 数据提取评分洞察"

    async def run(self, state: State) -> State:
        state.add_event("review_analyzer_start")

        try:
            products: List[Dict] = state.get("collected_products", []) or []
            max_analyze: int = state.get("max_products_to_analyze", 20)

            # ── 优先从 amazon_products 本地表读取 ──
            if not products:
                asins = state.get("asins") or []
                category = state.get("category") or state.get("market_category")
                try:
                    products = await self._load_from_local_db(
                        asins=asins, category=category, domain=state.get("domain", "US"),
                    )
                except Exception as e:
                    logger.warning(f"[ReviewAnalyzer] 本地表查询失败: {e}")

            if not products:
                state.set("review_insights", [])
                state.set("sentiment_summary", {})
                state.set("customer_needs", [])
                state.add_event("review_analyzer_no_products")
                return state

            # 筛选有评论的商品，按评论数排序取 TOP N
            products_with_reviews = sorted(
                [p for p in products if (p.get("review_count") or 0) > 0],
                key=lambda p: p.get("review_count", 0),
                reverse=True,
            )[:max_analyze]

            if not products_with_reviews:
                products_with_reviews = products[:max_analyze]

            benchmark = self._compute_benchmark(products)

            review_insights = [
                self._analyze_single(p, benchmark)
                for p in products_with_reviews
            ]

            sentiment_summary = self._build_sentiment_summary(review_insights)
            customer_needs = self._infer_customer_needs(review_insights, benchmark)

            # LLM 增强：基于代码计算的数据让 LLM 做深度语义分析
            ai_insights = await self._llm_analyze(
                benchmark, review_insights, sentiment_summary, customer_needs
            )
            if ai_insights:
                sentiment_summary["ai_insights"] = ai_insights
                logger.info("[ReviewAnalyzer] LLM 深度洞察已注入")

            state.set("review_insights", review_insights)
            state.set("sentiment_summary", sentiment_summary)
            state.set("customer_needs", customer_needs)
            state.set_meta("reviews_analyzed", len(review_insights))
            state.set_meta("llm_enhanced", bool(ai_insights))

            logger.info(
                f"[ReviewAnalyzer] Analyzed {len(review_insights)} products, "
                f"avg sentiment: {sentiment_summary.get('avg_positive_pct', 0):.1f}% positive"
            )
            state.add_event(f"review_analyzer_success: {len(review_insights)} analyzed")

        except Exception as e:
            logger.error(f"[ReviewAnalyzer] Error: {e}")
            state.set("error", str(e))
            state.set("review_insights", [])
            state.set("sentiment_summary", {})
            state.set("customer_needs", [])
            state.add_event(f"review_analyzer_error: {e}")

        return state

    # ── LLM 深度洞察 ──

    async def _llm_analyze(
        self,
        benchmark: Dict[str, Any],
        review_insights: List[Dict],
        sentiment_summary: Dict[str, Any],
        customer_needs: List[str],
    ) -> Dict[str, Any]:
        """让 LLM 基于代码计算的数据做深度分析，失败返回空 dict"""
        top_rated = sorted(
            [i for i in review_insights if i.get("rating")],
            key=lambda i: i["rating"], reverse=True,
        )[:5]
        low_rated = sorted(
            [i for i in review_insights if i.get("rating")],
            key=lambda i: i["rating"],
        )[:5]

        def _brief(item: Dict) -> Dict:
            return {
                "asin": item.get("asin"),
                "title": item.get("title", "")[:60],
                "rating": item.get("rating"),
                "review_count": item.get("review_count"),
                "review_barrier": item.get("review_barrier"),
                "praise": item.get("common_praise", [])[:3],
                "complaints": item.get("common_complaints", [])[:3],
            }

        prompt = _json.dumps({
            "benchmark": {
                "avg_rating": benchmark.get("avg_rating"),
                "avg_price": benchmark.get("avg_price"),
                "avg_review_count": benchmark.get("avg_review_count"),
                "total_products": benchmark.get("total_products"),
            },
            "sentiment": {
                "market_sentiment": sentiment_summary.get("market_sentiment"),
                "avg_positive_pct": sentiment_summary.get("avg_positive_pct"),
                "top_praise": sentiment_summary.get("top_praise_keywords", [])[:5],
                "top_complaints": sentiment_summary.get("top_complaint_keywords", [])[:5],
                "review_barrier_dist": sentiment_summary.get("review_barrier_distribution"),
            },
            "top_rated_products": [_brief(i) for i in top_rated],
            "low_rated_products": [_brief(i) for i in low_rated],
            "inferred_customer_needs": customer_needs[:5],
        }, ensure_ascii=False, indent=2)

        system = (
            "You are an Amazon review data analyst. "
            "Based on the product rating data below, provide deep insights in Chinese. "
            "Return JSON with these fields:\n"
            "- pain_points: list of user pain points that existing products ignore\n"
            "- differentiation_advice: list of actionable suggestions for new sellers\n"
            "- review_barrier_assessment: string, whether the review barrier is a real entry obstacle\n"
            "- market_quality_verdict: string, one-sentence market quality judgment\n"
            "Return valid JSON only, no markdown."
        )

        raw = await self.llm_invoke(prompt, system=system)
        if not raw:
            return {}

        try:
            cleaned = raw.strip()
            if cleaned.startswith("```"):
                cleaned = cleaned.split("\n", 1)[-1].rsplit("```", 1)[0]
            result = _json.loads(cleaned)
            if isinstance(result, dict):
                return result
        except (_json.JSONDecodeError, ValueError):
            logger.warning("[ReviewAnalyzer] LLM returned invalid JSON, skipping")
        return {}

    # ── 基准值 ──

    def _compute_benchmark(self, products: List[Dict]) -> Dict[str, Any]:
        """计算品类基准值，供单品对比"""
        ratings = [p["rating"] for p in products if p.get("rating")]
        review_counts = [p["review_count"] for p in products if p.get("review_count")]
        prices = [p["current_price"] for p in products if p.get("current_price")]
        bsr_list = [p["current_bsr"] for p in products if p.get("current_bsr")]

        return {
            "avg_rating": sum(ratings) / len(ratings) if ratings else 0,
            "median_review_count": sorted(review_counts)[len(review_counts) // 2] if review_counts else 0,
            "avg_review_count": sum(review_counts) / len(review_counts) if review_counts else 0,
            "avg_price": sum(prices) / len(prices) if prices else 0,
            "avg_bsr": sum(bsr_list) / len(bsr_list) if bsr_list else 0,
            "total_products": len(products),
        }

    # ── 单品分析 ──

    def _analyze_single(self, product: Dict, benchmark: Dict) -> Dict[str, Any]:
        rating = product.get("rating") or 0
        review_count = product.get("review_count") or 0

        sentiment = self._estimate_sentiment(rating)
        praise = self._infer_praise(product, benchmark)
        complaints = self._infer_complaints(product, benchmark)

        avg_r = benchmark["avg_rating"]
        if avg_r > 0:
            if rating >= avg_r + 0.3:
                rating_position = "高于品类均值"
            elif rating <= avg_r - 0.3:
                rating_position = "低于品类均值"
            else:
                rating_position = "接近品类均值"
        else:
            rating_position = "无对比数据"

        if review_count >= 5000:
            review_barrier = "极高"
        elif review_count >= 1000:
            review_barrier = "高"
        elif review_count >= 200:
            review_barrier = "中"
        else:
            review_barrier = "低"

        return {
            "asin": product.get("asin"),
            "title": (product.get("title") or "")[:80],
            "brand": product.get("brand") or "Unknown",
            "rating": rating,
            "review_count": review_count,
            "rating_position": rating_position,
            "review_barrier": review_barrier,
            "sentiment_positive_pct": sentiment["positive"],
            "sentiment_negative_pct": sentiment["negative"],
            "sentiment_neutral_pct": sentiment["neutral"],
            "common_praise": praise,
            "common_complaints": complaints,
            "customer_needs": self._infer_product_needs(product, benchmark),
            "bsr_trend": product.get("bsr_trend", "unknown"),
            "monthly_sold": product.get("monthly_sold") or 0,
            "analyzed_at": datetime.now().isoformat(),
        }

    def _estimate_sentiment(self, rating: float) -> Dict[str, float]:
        """基于评分估算情感分布（无评论文本时的合理近似）"""
        if rating <= 0:
            return {"positive": 0, "negative": 0, "neutral": 0}

        positive = min(95, max(5, (rating / 5.0) ** 1.3 * 100))
        negative = min(80, max(2, (1 - rating / 5.0) ** 0.8 * 100))
        neutral = max(0, 100 - positive - negative)
        return {
            "positive": round(positive, 1),
            "negative": round(negative, 1),
            "neutral": round(neutral, 1),
        }

    # ── 数据驱动的好评/差评/需求推断 ──

    def _infer_praise(self, product: Dict, benchmark: Dict) -> List[str]:
        praise = []
        rating = product.get("rating") or 0
        price = product.get("current_price") or 0
        review_count = product.get("review_count") or 0
        bsr_trend = product.get("bsr_trend", "unknown")
        monthly_sold = product.get("monthly_sold") or 0
        avg_price = benchmark["avg_price"]
        avg_rating = benchmark["avg_rating"]

        if rating >= 4.5:
            praise.append(f"用户满意度极高（评分 {rating}/5.0）")
        elif rating >= 4.0:
            praise.append(f"用户评价良好（评分 {rating}/5.0）")

        if review_count >= 1000:
            praise.append(f"市场验证充分（{review_count} 条评论）")

        if avg_price > 0 and price < avg_price * 0.8:
            praise.append(f"价格有竞争力（低于品类均价 {(1 - price / avg_price) * 100:.0f}%）")

        if bsr_trend == "improving":
            praise.append("需求上升中（BSR 持续改善）")

        if monthly_sold and monthly_sold > 500:
            praise.append(f"畅销品（月销 {monthly_sold}+）")

        if avg_rating > 0 and rating > avg_rating + 0.3:
            praise.append(f"评分领先品类均值（{rating} vs {avg_rating:.1f}）")

        return praise

    def _infer_complaints(self, product: Dict, benchmark: Dict) -> List[str]:
        complaints = []
        rating = product.get("rating") or 0
        price = product.get("current_price") or 0
        review_count = product.get("review_count") or 0
        bsr_trend = product.get("bsr_trend", "unknown")
        seller_count = product.get("seller_count") or 0
        avg_price = benchmark["avg_price"]
        avg_rating = benchmark["avg_rating"]

        if 0 < rating < 3.5:
            complaints.append(f"用户满意度偏低（评分仅 {rating}/5.0）")

        if avg_rating > 0 and rating < avg_rating - 0.3:
            complaints.append(f"评分低于品类均值（{rating} vs {avg_rating:.1f}）")

        if avg_price > 0 and price > avg_price * 1.3:
            complaints.append(f"定价偏高（高于品类均价 {(price / avg_price - 1) * 100:.0f}%）")

        if bsr_trend == "declining":
            complaints.append("需求下滑（BSR 走低）")

        if seller_count > 20:
            complaints.append(f"跟卖严重（{seller_count} 个卖家），品质可能参差不齐")

        if 0 < rating < 4.0 and review_count > 500:
            complaints.append("评论多但评分不高，存在明显产品痛点")

        return complaints

    def _infer_product_needs(self, product: Dict, benchmark: Dict) -> List[str]:
        needs = []
        rating = product.get("rating") or 0
        price = product.get("current_price") or 0
        monthly_sold = product.get("monthly_sold") or 0
        bsr_trend = product.get("bsr_trend", "unknown")
        avg_price = benchmark.get("avg_price", 0)

        if monthly_sold > 300 and price < 30:
            needs.append("高性价比需求")
        elif monthly_sold > 100 and price > 100:
            needs.append("品质优先型需求")

        if bsr_trend == "improving" and rating >= 4.0:
            needs.append("品质与口碑驱动购买")
        elif bsr_trend == "improving" and avg_price > 0 and price < avg_price * 0.8:
            needs.append("价格敏感型需求上升")

        if 0 < rating < 3.8 and monthly_sold > 200:
            needs.append("刚需品（即使评分一般仍有销量）")

        return needs

    # ── 汇总 ──

    def _build_sentiment_summary(self, insights: List[Dict]) -> Dict[str, Any]:
        if not insights:
            return {}

        total = len(insights)
        rated = [i for i in insights if i.get("rating")]
        avg_rating = sum(i["rating"] for i in rated) / len(rated) if rated else 0
        avg_positive = sum(i.get("sentiment_positive_pct", 0) for i in insights) / total
        avg_negative = sum(i.get("sentiment_negative_pct", 0) for i in insights) / total

        high_rated = [i for i in insights if (i.get("rating") or 0) >= 4.5]
        low_rated = [i for i in insights if 0 < (i.get("rating") or 0) < 3.5]

        praise_freq: Dict[str, int] = {}
        complaint_freq: Dict[str, int] = {}
        for insight in insights:
            for p in insight.get("common_praise", []):
                praise_freq[p] = praise_freq.get(p, 0) + 1
            for c in insight.get("common_complaints", []):
                complaint_freq[c] = complaint_freq.get(c, 0) + 1

        top_praise = [k for k, _ in sorted(praise_freq.items(), key=lambda x: x[1], reverse=True)[:5]]
        top_complaints = [k for k, _ in sorted(complaint_freq.items(), key=lambda x: x[1], reverse=True)[:5]]

        barrier_dist = {"极高": 0, "高": 0, "中": 0, "低": 0}
        for i in insights:
            b = i.get("review_barrier", "低")
            if b in barrier_dist:
                barrier_dist[b] += 1

        return {
            "total_analyzed": total,
            "avg_rating": round(avg_rating, 2),
            "avg_positive_pct": round(avg_positive, 1),
            "avg_negative_pct": round(avg_negative, 1),
            "high_rated_count": len(high_rated),
            "low_rated_count": len(low_rated),
            "top_praise_keywords": top_praise,
            "top_complaint_keywords": top_complaints,
            "review_barrier_distribution": barrier_dist,
            "market_sentiment": (
                "非常正面" if avg_positive >= 80 else
                "正面" if avg_positive >= 60 else
                "中性" if avg_positive >= 40 else
                "负面"
            ),
            "generated_at": datetime.now().isoformat(),
        }

    def _infer_customer_needs(self, insights: List[Dict], benchmark: Dict) -> List[str]:
        need_freq: Dict[str, int] = {}
        for insight in insights:
            for need in insight.get("customer_needs", []):
                need_freq[need] = need_freq.get(need, 0) + 1

        needs = [need for need, _ in sorted(need_freq.items(), key=lambda x: x[1], reverse=True)]

        avg_rating = benchmark.get("avg_rating", 0)
        avg_price = benchmark.get("avg_price", 0)

        if avg_rating >= 4.2:
            needs.append("品类整体满意度高，用户注重品质和体验")
        elif 0 < avg_rating < 3.5:
            needs.append("品类整体满意度偏低，存在产品改进空间")

        if 0 < avg_price < 30:
            needs.append("低客单价品类，价格竞争力是关键")
        elif avg_price > 100:
            needs.append("高客单价品类，用户对品质和服务要求更高")

        return needs

    # ── 从 amazon_products 本地表加载 ──

    async def _load_from_local_db(
        self, asins: List[str] = None, category: str = None, domain: str = "US",
    ) -> List[Dict]:
        """从 amazon_products 表查询商品，转为旧分析逻辑需要的格式"""
        async with AsyncSessionLocal() as db:
            from sqlalchemy import select
            from backend.data.models.amazon_product import AmazonProduct

            conditions = [AmazonProduct.domain == domain]
            if asins:
                conditions.append(AmazonProduct.asin.in_(asins))
            elif category:
                conditions.append(AmazonProduct.category_name == category)
            else:
                return []

            stmt = select(AmazonProduct).where(*conditions)
            result = await db.execute(stmt)
            products = list(result.scalars().all())

        if not products:
            return []

        converted = []
        for p in products:
            converted.append({
                "asin": p.asin,
                "title": p.title,
                "brand": p.brand,
                "current_price": p.current_price,
                "current_bsr": p.current_bsr,
                "rating": p.rating,
                "review_count": p.review_count,
                "monthly_sold": p.monthly_sold,
                "seller_count": p.seller_count,
                "bsr_trend": p.bsr_trend,
                "bsr_history": p.bsr_history,
                "price_history": p.price_history,
                "avg_price_90d": p.avg_price_90d,
                "feature_bullets": p.feature_bullets,
                "main_image": p.main_image,
                "is_fba": p.is_fba,
                "is_prime": p.is_prime,
                "aplus_content": p.aplus_content,
                "data_source": p.data_source,
            })
        n = len(converted)
        source = f"{len(asins)} ASIN" if asins else f"类目={category}"
        logger.info(f"[ReviewAnalyzer] 从本地表加载 {n} 个商品（{source}）")
        return converted

    async def execute(self, input_data: AgentInput) -> AgentOutput:
        return await super().execute(input_data)
