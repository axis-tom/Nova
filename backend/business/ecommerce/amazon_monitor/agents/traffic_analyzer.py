"""
流量与竞品分析 Agent - Amazon 监控场景
对应文章第4步：流量分析与竞品监控

职责：
1. 分析商品 BSR 排名分布
2. 进行竞品价格比较
3. 识别价格异常（大幅下降/上涨）
4. 分析市场竞争格局
5. 生成流量洞察报告
"""

import asyncio
from typing import Any, Dict, List, Optional
from datetime import datetime

from backend.common.core.agent import Agent
from backend.common.core.state import State
from backend.utils.logger import logger


class TrafficAnalyzerAgent(Agent):
    """
    流量与竞品分析 Agent
    分析 BSR 排名、价格竞争和市场格局
    """

    name = "traffic_analyzer"
    description = "Amazon 流量与竞品分析 Agent，分析 BSR 排名和价格竞争"

    def run(self, state: State) -> State:
        """
        执行流量与竞品分析

        输入（从 state 读取）：
          - collected_products: List[dict] 采集到的商品列表
          - product_map: Dict[str, dict] ASIN → 商品详情映射

        输出（写入 state）：
          - traffic_insights: dict 流量洞察
          - bsr_analysis: dict BSR 排名分析
          - competitor_comparison: dict 竞品对比
          - price_alerts: List[dict] 价格预警
        """
        state.add_event("traffic_analyzer_start")
        logger.info("[TrafficAnalyzer] Starting traffic and competitor analysis")

        try:
            products: List[Dict] = state.get("collected_products", [])
            product_map: Dict = state.get("product_map", {})

            if not products:
                logger.warning("[TrafficAnalyzer] No products to analyze")
                state.set("traffic_insights", {})
                state.set("bsr_analysis", {})
                state.set("competitor_comparison", {})
                state.set("price_alerts", [])
                state.add_event("traffic_analyzer_no_products")
                return state

            # 1. BSR 排名分析
            bsr_analysis = self._analyze_bsr(products)

            # 2. 价格分析
            price_analysis = self._analyze_prices(products)

            # 3. 竞品对比（按品类分组）
            competitor_comparison = self._compare_competitors(products)

            # 4. 价格预警
            price_alerts = self._detect_price_alerts(products)

            # 5. 流量洞察汇总
            traffic_insights = self._build_traffic_insights(
                products, bsr_analysis, price_analysis, competitor_comparison
            )

            # 写入结果
            state.set("traffic_insights", traffic_insights)
            state.set("bsr_analysis", bsr_analysis)
            state.set("competitor_comparison", competitor_comparison)
            state.set("price_alerts", price_alerts)
            state.set_meta("traffic_analyzed", len(products))

            logger.info(
                f"[TrafficAnalyzer] Analyzed {len(products)} products, "
                f"{len(price_alerts)} price alerts"
            )
            state.add_event(f"traffic_analyzer_success: {len(products)} products, {len(price_alerts)} alerts")

        except Exception as e:
            logger.error(f"[TrafficAnalyzer] Error: {e}")
            state.set("error", str(e))
            state.set("traffic_insights", {})
            state.set("bsr_analysis", {})
            state.set("competitor_comparison", {})
            state.set("price_alerts", [])
            state.add_event(f"traffic_analyzer_error: {e}")

        return state

    def _analyze_bsr(self, products: List[Dict]) -> Dict[str, Any]:
        """分析 BSR 排名分布"""
        products_with_bsr = [p for p in products if p.get("bsr_rank")]

        if not products_with_bsr:
            return {"message": "No BSR data available"}

        bsr_ranks = [p["bsr_rank"] for p in products_with_bsr]
        avg_bsr = sum(bsr_ranks) / len(bsr_ranks)

        # 按 BSR 分层
        top_100 = [p for p in products_with_bsr if p["bsr_rank"] <= 100]
        top_1000 = [p for p in products_with_bsr if 100 < p["bsr_rank"] <= 1000]
        top_10000 = [p for p in products_with_bsr if 1000 < p["bsr_rank"] <= 10000]
        others = [p for p in products_with_bsr if p["bsr_rank"] > 10000]

        # 最佳 BSR 商品
        best_bsr_product = min(products_with_bsr, key=lambda p: p["bsr_rank"])

        # 按品类分组 BSR
        category_bsr: Dict[str, List[int]] = {}
        for p in products_with_bsr:
            cat = p.get("bsr_category") or p.get("category", "Unknown")
            if cat not in category_bsr:
                category_bsr[cat] = []
            category_bsr[cat].append(p["bsr_rank"])

        category_avg_bsr = {
            cat: round(sum(ranks) / len(ranks))
            for cat, ranks in category_bsr.items()
        }

        return {
            "total_with_bsr": len(products_with_bsr),
            "avg_bsr": round(avg_bsr),
            "min_bsr": min(bsr_ranks),
            "max_bsr": max(bsr_ranks),
            "distribution": {
                "top_100": len(top_100),
                "top_1000": len(top_1000),
                "top_10000": len(top_10000),
                "others": len(others),
            },
            "best_bsr_product": {
                "asin": best_bsr_product.get("asin"),
                "title": best_bsr_product.get("title", "")[:60],
                "bsr_rank": best_bsr_product.get("bsr_rank"),
                "price": best_bsr_product.get("price"),
                "rating": best_bsr_product.get("rating"),
            },
            "category_avg_bsr": category_avg_bsr,
        }

    def _analyze_prices(self, products: List[Dict]) -> Dict[str, Any]:
        """分析价格分布"""
        products_with_price = [p for p in products if p.get("price")]

        if not products_with_price:
            return {"message": "No price data available"}

        prices = [p["price"] for p in products_with_price]
        avg_price = sum(prices) / len(prices)

        # 价格区间分布
        under_20 = [p for p in products_with_price if p["price"] < 20]
        under_50 = [p for p in products_with_price if 20 <= p["price"] < 50]
        under_100 = [p for p in products_with_price if 50 <= p["price"] < 100]
        over_100 = [p for p in products_with_price if p["price"] >= 100]

        # Prime 商品比例
        prime_count = sum(1 for p in products_with_price if p.get("is_prime"))

        return {
            "total_with_price": len(products_with_price),
            "avg_price": round(avg_price, 2),
            "min_price": round(min(prices), 2),
            "max_price": round(max(prices), 2),
            "price_distribution": {
                "under_$20": len(under_20),
                "$20-$50": len(under_50),
                "$50-$100": len(under_100),
                "over_$100": len(over_100),
            },
            "prime_ratio": round(prime_count / len(products_with_price) * 100, 1),
            "recommended_price_range": f"${round(avg_price * 0.8, 2)} - ${round(avg_price * 1.2, 2)}",
        }

    def _compare_competitors(self, products: List[Dict]) -> Dict[str, Any]:
        """按品类分组进行竞品对比"""
        category_groups: Dict[str, List[Dict]] = {}
        for p in products:
            cat = p.get("category") or "Unknown"
            if cat not in category_groups:
                category_groups[cat] = []
            category_groups[cat].append(p)

        comparison = {}
        for cat, cat_products in category_groups.items():
            if len(cat_products) < 2:
                continue

            prices = [p["price"] for p in cat_products if p.get("price")]
            ratings = [p["rating"] for p in cat_products if p.get("rating")]
            reviews = [p["review_count"] for p in cat_products if p.get("review_count")]

            # 找出该品类最佳商品
            best_rated = max(cat_products, key=lambda p: p.get("rating", 0)) if ratings else None
            most_reviewed = max(cat_products, key=lambda p: p.get("review_count", 0)) if reviews else None

            comparison[cat] = {
                "product_count": len(cat_products),
                "avg_price": round(sum(prices) / len(prices), 2) if prices else None,
                "avg_rating": round(sum(ratings) / len(ratings), 2) if ratings else None,
                "avg_reviews": round(sum(reviews) / len(reviews)) if reviews else None,
                "best_rated": {
                    "asin": best_rated.get("asin"),
                    "title": best_rated.get("title", "")[:50],
                    "rating": best_rated.get("rating"),
                } if best_rated else None,
                "most_reviewed": {
                    "asin": most_reviewed.get("asin"),
                    "title": most_reviewed.get("title", "")[:50],
                    "review_count": most_reviewed.get("review_count"),
                } if most_reviewed else None,
                "competition_level": (
                    "高" if len(cat_products) >= 10 else
                    "中" if len(cat_products) >= 5 else
                    "低"
                ),
            }

        return comparison

    def _detect_price_alerts(self, products: List[Dict]) -> List[Dict]:
        """检测价格异常（基于当前数据的统计分析）"""
        alerts = []
        products_with_price = [p for p in products if p.get("price")]

        if len(products_with_price) < 3:
            return alerts

        prices = [p["price"] for p in products_with_price]
        avg_price = sum(prices) / len(prices)
        std_dev = (sum((p - avg_price) ** 2 for p in prices) / len(prices)) ** 0.5

        for product in products_with_price:
            price = product["price"]
            deviation = abs(price - avg_price)

            # 价格偏离超过2个标准差视为异常
            if std_dev > 0 and deviation > 2 * std_dev:
                alert_type = "price_too_low" if price < avg_price else "price_too_high"
                alerts.append({
                    "asin": product.get("asin"),
                    "title": product.get("title", "")[:60],
                    "current_price": price,
                    "avg_market_price": round(avg_price, 2),
                    "deviation_pct": round((price - avg_price) / avg_price * 100, 1),
                    "alert_type": alert_type,
                    "message": (
                        f"价格 ${price:.2f} 远低于市场均价 ${avg_price:.2f}，"
                        f"偏差 {abs(price - avg_price) / avg_price * 100:.1f}%"
                        if alert_type == "price_too_low" else
                        f"价格 ${price:.2f} 远高于市场均价 ${avg_price:.2f}，"
                        f"偏差 {(price - avg_price) / avg_price * 100:.1f}%"
                    ),
                    "detected_at": datetime.now().isoformat(),
                })

        return alerts

    def _build_traffic_insights(
        self,
        products: List[Dict],
        bsr_analysis: Dict,
        price_analysis: Dict,
        competitor_comparison: Dict,
    ) -> Dict[str, Any]:
        """构建流量洞察摘要"""
        total = len(products)
        products_with_rating = [p for p in products if p.get("rating")]
        avg_rating = (
            sum(p["rating"] for p in products_with_rating) / len(products_with_rating)
            if products_with_rating else 0
        )

        # 高潜力商品（BSR < 1000 且评分 >= 4.0）
        high_potential = [
            p for p in products
            if (p.get("bsr_rank") or 999999) < 1000 and (p.get("rating") or 0) >= 4.0
        ]

        # 市场竞争强度
        competition_level = "高" if total >= 50 else "中" if total >= 20 else "低"

        return {
            "total_products": total,
            "avg_market_rating": round(avg_rating, 2),
            "high_potential_count": len(high_potential),
            "competition_level": competition_level,
            "market_summary": (
                f"共采集 {total} 个商品，市场竞争程度{competition_level}，"
                f"平均评分 {avg_rating:.1f}/5.0，"
                f"发现 {len(high_potential)} 个高潜力商品（BSR<1000 且评分≥4.0）"
            ),
            "top_opportunities": [
                {
                    "asin": p.get("asin"),
                    "title": p.get("title", "")[:60],
                    "price": p.get("price"),
                    "rating": p.get("rating"),
                    "bsr_rank": p.get("bsr_rank"),
                    "review_count": p.get("review_count"),
                }
                for p in sorted(
                    high_potential,
                    key=lambda p: p.get("bsr_rank", 999999)
                )[:5]
            ],
            "categories_analyzed": list(competitor_comparison.keys()),
            "generated_at": datetime.now().isoformat(),
        }
