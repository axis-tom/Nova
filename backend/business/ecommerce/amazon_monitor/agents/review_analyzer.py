"""
评论分析 Agent - Amazon 监控场景
对应文章第3步：评论情感分析

职责：
1. 接收采集到的商品列表
2. 调用 AmazonReviewAnalyzer 分析评论
3. 提取用户需求、痛点、好评/差评关键词
4. 生成情感分析摘要
5. 识别产品改进机会
"""

import asyncio
from typing import Any, Dict, List, Optional
from datetime import datetime

from backend.common.core.agent import Agent
from backend.common.core.state import State
from backend.utils.logger import logger


class AmazonReviewAnalyzerAgent(Agent):
    """
    评论分析 Agent
    分析 Amazon 商品评论，提取用户洞察
    """

    name = "review_analyzer"
    description = "Amazon 评论分析 Agent，提取用户需求和情感洞察"

    async def run(self, state: State) -> State:
        """
        执行评论分析（异步入口，与 product_collector 保持一致）

        输入（从 state 读取）：
          - collected_products: List[dict] 采集到的商品列表
          - max_products_to_analyze: int 最多分析商品数（默认20）

        输出（写入 state）：
          - review_insights: List[dict] 每个商品的评论洞察
          - sentiment_summary: dict 整体情感摘要
          - customer_needs: List[str] 提取的客户需求
        """
        state.add_event("review_analyzer_start")
        logger.info("[ReviewAnalyzer] Starting review analysis")
        return await self._async_run(state)

    async def _async_run(self, state: State) -> State:
        """异步执行评论分析"""
        try:
            products: List[Dict] = state.get("collected_products", [])
            max_analyze: int = state.get("max_products_to_analyze", 20)

            if not products:
                logger.warning("[ReviewAnalyzer] No products to analyze")
                state.set("review_insights", [])
                state.set("sentiment_summary", {})
                state.set("customer_needs", [])
                state.add_event("review_analyzer_no_products")
                return state

            # 选取评论数最多的商品进行分析（最多 max_analyze 个）
            products_to_analyze = sorted(
                [p for p in products if p.get("review_count", 0) > 0],
                key=lambda p: p.get("review_count", 0),
                reverse=True
            )[:max_analyze]

            logger.info(f"[ReviewAnalyzer] Analyzing {len(products_to_analyze)} products")

            # 导入工具
            from backend.business.ecommerce.amazon_monitor.tools.amazon_api import get_review_analyzer
            analyzer = get_review_analyzer()

            # 并发分析（限制并发数为3）
            review_insights = []
            semaphore = asyncio.Semaphore(3)

            async def analyze_one(product: Dict):
                async with semaphore:
                    asin = product.get("asin", "")
                    try:
                        review = await analyzer.analyze_reviews(asin, use_cache=True)
                        if review:
                            insight = {
                                "asin": asin,
                                "title": product.get("title", ""),
                                "rating": review.rating.overall_rating,
                                "review_count": review.rating.total_reviews,
                                "review_summary": review.review_summary,
                                "sentiment_positive_pct": review.sentiment_positive_pct,
                                "sentiment_negative_pct": review.sentiment_negative_pct,
                                "sentiment_neutral_pct": review.sentiment_neutral_pct,
                                "common_praise": review.common_praise,
                                "common_complaints": review.common_complaints,
                                "customer_needs": review.customer_needs,
                                "analyzed_at": datetime.now().isoformat(),
                            }
                            review_insights.append(insight)
                            logger.info(
                                f"[ReviewAnalyzer] {asin}: {review.rating.overall_rating}/5 "
                                f"({review.rating.total_reviews} reviews)"
                            )
                    except Exception as e:
                        logger.error(f"[ReviewAnalyzer] Failed to analyze {asin}: {e}")

            await asyncio.gather(*[analyze_one(p) for p in products_to_analyze])

            # 生成整体情感摘要
            sentiment_summary = self._build_sentiment_summary(review_insights)

            # 提取客户需求（去重合并）
            all_needs = []
            for insight in review_insights:
                all_needs.extend(insight.get("customer_needs", []))
            # 统计频率
            need_freq: Dict[str, int] = {}
            for need in all_needs:
                need_freq[need] = need_freq.get(need, 0) + 1
            customer_needs = [
                need for need, _ in sorted(need_freq.items(), key=lambda x: x[1], reverse=True)
            ]

            # 写入结果
            state.set("review_insights", review_insights)
            state.set("sentiment_summary", sentiment_summary)
            state.set("customer_needs", customer_needs)
            state.set_meta("reviews_analyzed", len(review_insights))

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

    def _build_sentiment_summary(self, insights: List[Dict]) -> Dict[str, Any]:
        """构建整体情感摘要"""
        if not insights:
            return {}

        total = len(insights)
        avg_rating = sum(i.get("rating", 0) for i in insights) / total
        avg_positive = sum(i.get("sentiment_positive_pct", 0) for i in insights) / total
        avg_negative = sum(i.get("sentiment_negative_pct", 0) for i in insights) / total

        # 高评分商品（≥4.5）
        high_rated = [i for i in insights if i.get("rating", 0) >= 4.5]
        # 低评分商品（<3.5）
        low_rated = [i for i in insights if i.get("rating", 0) < 3.5]

        # 汇总常见好评/差评
        all_praise: Dict[str, int] = {}
        all_complaints: Dict[str, int] = {}
        for insight in insights:
            for p in insight.get("common_praise", []):
                all_praise[p] = all_praise.get(p, 0) + 1
            for c in insight.get("common_complaints", []):
                all_complaints[c] = all_complaints.get(c, 0) + 1

        top_praise = [k for k, _ in sorted(all_praise.items(), key=lambda x: x[1], reverse=True)[:5]]
        top_complaints = [k for k, _ in sorted(all_complaints.items(), key=lambda x: x[1], reverse=True)[:5]]

        return {
            "total_analyzed": total,
            "avg_rating": round(avg_rating, 2),
            "avg_positive_pct": round(avg_positive, 1),
            "avg_negative_pct": round(avg_negative, 1),
            "high_rated_count": len(high_rated),
            "low_rated_count": len(low_rated),
            "top_praise_keywords": top_praise,
            "top_complaint_keywords": top_complaints,
            "market_sentiment": (
                "非常正面" if avg_positive >= 80 else
                "正面" if avg_positive >= 60 else
                "中性" if avg_positive >= 40 else
                "负面"
            ),
            "generated_at": datetime.now().isoformat(),
        }
