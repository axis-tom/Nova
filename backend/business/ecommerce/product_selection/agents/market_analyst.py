"""
市场分析 Agent - 电商选品分析场景

职责：
1. 读取 state.collected_products（Keepa 采集的真实商品数据）
2. 分析市场趋势：价格/BSR/品牌分布、趋势方向
3. 识别市场机会点和风险点
4. 进行盈利评估（基于 Keepa monthly_sold 估算）

数据源：state.collected_products（由 product_collector 通过 Keepa 采集）
"""

from typing import Any, Dict, List
from datetime import datetime

from backend.common.core.agent import Agent, AgentInput, AgentOutput
from backend.common.core.state import State
from backend.utils.logger import logger


class MarketAnalystAgent(Agent):
    """市场分析 Agent — 基于 Keepa 真实数据做市场趋势分析和盈利评估"""

    name = "market_analyst"
    description = "电商选品市场分析 Agent，基于 Keepa 数据做市场趋势和盈利评估"

    def run(self, state: State) -> State:
        state.add_event("market_analyst_start")
        analysis_type = state.get("analysis_type", "market_trends")
        state.set_meta("analysis_type", analysis_type)

        try:
            products: List[Dict] = state.get("collected_products", []) or []
            if not products:
                state.set("result", {
                    "analysis_type": analysis_type,
                    "error": "无商品数据，请先调用 product_collector 采集商品",
                })
                state.add_event("market_analyst_no_products")
                return state

            if analysis_type == "market_trends":
                result = self._analyze_market_trends(products)
            elif analysis_type == "roi_analysis":
                profit_margin = state.get("profit_margin", 0.25)
                result = self._analyze_profitability(products, profit_margin)
            else:
                result = {
                    "error": f"未知的分析类型: {analysis_type}",
                    "available_types": ["market_trends", "roi_analysis"],
                }

            state.set("result", result)
            if analysis_type == "market_trends":
                state.set("market_analysis_result", result)
            elif analysis_type == "roi_analysis":
                state.set("profitability_result", result)
            state.set_meta("analysis_completed", True)
            state.add_event("market_analyst_success")

        except Exception as e:
            logger.error(f"[MarketAnalyst] Error: {e}")
            state.set("error", str(e))
            state.set_meta("analysis_completed", False)
            state.add_event(f"market_analyst_error: {e}")

        return state

    # ── 市场趋势分析 ──

    def _analyze_market_trends(self, products: List[Dict]) -> Dict[str, Any]:
        total = len(products)

        # 基础统计
        prices = [p["current_price"] for p in products if p.get("current_price")]
        bsr_list = [p["current_bsr"] for p in products if p.get("current_bsr")]
        ratings = [p["rating"] for p in products if p.get("rating")]
        avg_price = sum(prices) / len(prices) if prices else 0
        avg_bsr = sum(bsr_list) / len(bsr_list) if bsr_list else 0
        avg_rating = sum(ratings) / len(ratings) if ratings else 0
        total_monthly_sales = sum(p.get("monthly_sold", 0) for p in products)

        # BSR 趋势分布
        bsr_trend_dist = {"improving": 0, "declining": 0, "stable": 0, "unknown": 0}
        for p in products:
            trend = p.get("bsr_trend", "unknown")
            if trend in bsr_trend_dist:
                bsr_trend_dist[trend] += 1
            else:
                bsr_trend_dist["unknown"] += 1

        improving_pct = bsr_trend_dist["improving"] / total if total else 0
        declining_pct = bsr_trend_dist["declining"] / total if total else 0
        if improving_pct > 0.5:
            market_trend = "上升"
        elif declining_pct > 0.5:
            market_trend = "下降"
        else:
            market_trend = "稳定"

        # 品牌分布
        brand_distribution = self._aggregate_by_brand(products)

        # 价格带分析
        price_band_analysis = self._analyze_price_bands(products)

        # 机会识别
        opportunities = self._identify_opportunities(products, price_band_analysis)

        # 风险识别
        risks = self._identify_risks(products, bsr_trend_dist, total)

        return {
            "analysis_type": "market_trends",
            "summary": {
                "total_products_analyzed": total,
                "average_price": round(avg_price, 2),
                "total_monthly_sales": total_monthly_sales,
                "average_rating": round(avg_rating, 2),
                "average_bsr": round(avg_bsr),
                "market_trend": market_trend,
            },
            "brand_distribution": brand_distribution,
            "price_band_analysis": price_band_analysis,
            "bsr_trend_distribution": bsr_trend_dist,
            "opportunities": opportunities,
            "risks": risks,
            "generated_at": datetime.now().isoformat(),
        }

    def _aggregate_by_brand(self, products: List[Dict]) -> Dict[str, Any]:
        brands: Dict[str, Dict] = {}
        for p in products:
            brand = p.get("brand") or "Unknown"
            if brand not in brands:
                brands[brand] = {
                    "count": 0,
                    "total_sales": 0,
                    "_prices": [],
                    "_ratings": [],
                    "_bsr": [],
                    "best_bsr_asin": None,
                    "best_bsr_val": 999999,
                }
            b = brands[brand]
            b["count"] += 1
            b["total_sales"] += p.get("monthly_sold", 0)
            if p.get("current_price"):
                b["_prices"].append(p["current_price"])
            if p.get("rating"):
                b["_ratings"].append(p["rating"])
            if p.get("current_bsr"):
                b["_bsr"].append(p["current_bsr"])
                if p["current_bsr"] < b["best_bsr_val"]:
                    b["best_bsr_val"] = p["current_bsr"]
                    b["best_bsr_asin"] = p.get("asin")

        result = {}
        for brand, b in sorted(brands.items(), key=lambda x: x[1]["total_sales"], reverse=True):
            result[brand] = {
                "count": b["count"],
                "total_sales": b["total_sales"],
                "avg_price": round(sum(b["_prices"]) / len(b["_prices"]), 2) if b["_prices"] else None,
                "avg_rating": round(sum(b["_ratings"]) / len(b["_ratings"]), 2) if b["_ratings"] else None,
                "avg_bsr": round(sum(b["_bsr"]) / len(b["_bsr"])) if b["_bsr"] else None,
                "best_bsr_asin": b["best_bsr_asin"],
            }
        return result

    def _analyze_price_bands(self, products: List[Dict]) -> Dict[str, Any]:
        bands = {
            "<$20": {"min": 0, "max": 20},
            "$20-50": {"min": 20, "max": 50},
            "$50-100": {"min": 50, "max": 100},
            "$100-200": {"min": 100, "max": 200},
            "$200+": {"min": 200, "max": float("inf")},
        }
        result = {}
        for label, rng in bands.items():
            in_band = [
                p for p in products
                if p.get("current_price") and rng["min"] <= p["current_price"] < rng["max"]
            ]
            if not in_band:
                result[label] = {"count": 0, "avg_bsr": None, "avg_rating": None, "avg_monthly_sold": None}
                continue
            bsr_vals = [p["current_bsr"] for p in in_band if p.get("current_bsr")]
            rating_vals = [p["rating"] for p in in_band if p.get("rating")]
            result[label] = {
                "count": len(in_band),
                "avg_bsr": round(sum(bsr_vals) / len(bsr_vals)) if bsr_vals else None,
                "avg_rating": round(sum(rating_vals) / len(rating_vals), 2) if rating_vals else None,
                "avg_monthly_sold": round(sum(p.get("monthly_sold", 0) for p in in_band) / len(in_band)),
            }
        return result

    def _identify_opportunities(self, products: List[Dict], price_bands: Dict) -> List[Dict]:
        opportunities = []

        # 上升期 + 高评分 + 低评论（竞争小的成长商品）
        rising_low_competition = [
            p for p in products
            if p.get("bsr_trend") == "improving"
            and (p.get("rating") or 0) >= 4.0
            and (p.get("review_count") or 0) < 500
        ]
        if rising_low_competition:
            opportunities.append({
                "opportunity": "上升期低竞争商品",
                "evidence": f"{len(rising_low_competition)} 个商品 BSR 改善中、评分≥4.0、评论<500",
                "strength": "高" if len(rising_low_competition) >= 3 else "中",
                "asins": [p["asin"] for p in rising_low_competition[:5]],
            })

        # 月销高 + 卖家少（供给不足）
        high_demand_low_supply = [
            p for p in products
            if (p.get("monthly_sold") or 0) > 100
            and (p.get("seller_count") or 0) < 5
        ]
        if high_demand_low_supply:
            opportunities.append({
                "opportunity": "需求旺盛但供给不足",
                "evidence": f"{len(high_demand_low_supply)} 个商品月销>100 但卖家<5",
                "strength": "高" if len(high_demand_low_supply) >= 2 else "中",
                "asins": [p["asin"] for p in high_demand_low_supply[:5]],
            })

        # 价格带空白
        for band, stats in price_bands.items():
            if stats["count"] == 0:
                opportunities.append({
                    "opportunity": f"价格带空白：{band}",
                    "evidence": f"该价格区间无商品，可能是差异化切入点",
                    "strength": "中",
                })

        return opportunities

    def _identify_risks(self, products: List[Dict], bsr_trend_dist: Dict, total: int) -> List[Dict]:
        risks = []

        # 市场萎缩
        declining_pct = bsr_trend_dist.get("declining", 0) / total if total else 0
        if declining_pct > 0.5:
            risks.append({
                "risk_type": "市场萎缩",
                "detail": f"{declining_pct*100:.0f}% 的商品 BSR 呈下降趋势，市场可能在收缩",
                "severity": "高",
            })

        # 竞争激烈
        seller_counts = [p.get("seller_count", 0) for p in products if p.get("seller_count")]
        avg_sellers = sum(seller_counts) / len(seller_counts) if seller_counts else 0
        if avg_sellers > 20:
            risks.append({
                "risk_type": "竞争激烈",
                "detail": f"平均每个商品有 {avg_sellers:.0f} 个卖家，竞争密度高",
                "severity": "高" if avg_sellers > 50 else "中",
            })

        # 评论壁垒
        review_counts = [p.get("review_count", 0) for p in products if p.get("review_count")]
        avg_reviews = sum(review_counts) / len(review_counts) if review_counts else 0
        if avg_reviews > 1000:
            risks.append({
                "risk_type": "评论壁垒",
                "detail": f"平均评论数 {avg_reviews:.0f}，新进入者难以快速建立信任",
                "severity": "高" if avg_reviews > 5000 else "中",
            })

        return risks

    # ── 盈利评估 ──

    def _analyze_profitability(
        self, products: List[Dict], profit_margin: float = 0.25
    ) -> Dict[str, Any]:
        results = []
        for p in products:
            price = p.get("current_price") or 0
            monthly_sold = p.get("monthly_sold") or 0
            monthly_revenue = price * monthly_sold
            est_profit = monthly_revenue * profit_margin

            results.append({
                "asin": p.get("asin"),
                "title": (p.get("title") or "")[:60],
                "brand": p.get("brand") or "Unknown",
                "price": price,
                "monthly_sold": monthly_sold,
                "monthly_revenue": round(monthly_revenue, 2),
                "est_monthly_profit": round(est_profit, 2),
                "rating": p.get("rating"),
                "current_bsr": p.get("current_bsr"),
                "bsr_trend": p.get("bsr_trend"),
                "review_count": p.get("review_count", 0),
            })

        results.sort(key=lambda x: x["monthly_revenue"], reverse=True)

        total_revenue = sum(r["monthly_revenue"] for r in results)
        total_profit = sum(r["est_monthly_profit"] for r in results)

        # 按品牌汇总
        brand_profit: Dict[str, Dict] = {}
        for r in results:
            brand = r["brand"]
            if brand not in brand_profit:
                brand_profit[brand] = {"count": 0, "revenue": 0, "est_profit": 0}
            bp = brand_profit[brand]
            bp["count"] += 1
            bp["revenue"] += r["monthly_revenue"]
            bp["est_profit"] += r["est_monthly_profit"]

        for bp in brand_profit.values():
            bp["revenue"] = round(bp["revenue"], 2)
            bp["est_profit"] = round(bp["est_profit"], 2)

        top_picks = [
            {
                "rank": i + 1,
                "asin": r["asin"],
                "title": r["title"],
                "price": r["price"],
                "monthly_revenue": r["monthly_revenue"],
                "est_monthly_profit": r["est_monthly_profit"],
                "rating": r["rating"],
                "reason": (
                    f"月收入 ${r['monthly_revenue']:,.0f}，"
                    f"估利 ${r['est_monthly_profit']:,.0f}（{profit_margin*100:.0f}% margin），"
                    f"BSR {r.get('current_bsr') or 'N/A'}，"
                    f"评分 {r.get('rating') or 'N/A'}"
                ),
            }
            for i, r in enumerate(results[:5])
        ]

        return {
            "analysis_type": "roi_analysis",
            "summary": {
                "total_products_evaluated": len(results),
                "total_monthly_revenue": round(total_revenue, 2),
                "estimated_monthly_profit": round(total_profit, 2),
                "default_profit_margin": profit_margin,
            },
            "brand_profitability": dict(
                sorted(brand_profit.items(), key=lambda x: x[1]["revenue"], reverse=True)
            ),
            "product_profitability": results,
            "top_picks": top_picks,
            "generated_at": datetime.now().isoformat(),
        }

    async def execute(self, input_data: AgentInput) -> AgentOutput:
        return await super().execute(input_data)
