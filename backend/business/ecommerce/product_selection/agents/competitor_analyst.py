"""
竞品分析 Agent - 电商选品分析场景

职责：
1. 读取 state.collected_products（Keepa 采集的真实商品数据）
2. 按品牌聚合，计算市场份额、价格、BSR、评分等竞争力指标
3. 分层竞争格局（梯队划分）
4. 识别差异化机会（价格带空白、低竞争品牌、BSR 上升机会）

数据源：state.collected_products（由 product_collector 通过 Keepa 采集）
"""

from typing import Any, Dict, List
from datetime import datetime

from backend.common.core.agent import Agent, AgentInput, AgentOutput
from backend.common.core.state import State
from backend.utils.logger import logger


class CompetitorAnalystAgent(Agent):
    """竞品分析 Agent — 基于 Keepa 真实数据做品牌级竞品对比"""

    name = "competitor_analyst"
    description = "电商竞品分析 Agent，基于 Keepa 数据做品牌对比和差异化分析"

    def run(self, state: State) -> State:
        state.add_event("competitor_analyst_start")

        try:
            products: List[Dict] = state.get("collected_products", []) or []
            if not products:
                state.set("result", {
                    "analysis_type": "competitor_benchmark",
                    "error": "无商品数据，请先调用 product_collector 采集商品",
                })
                state.add_event("competitor_analyst_no_products")
                return state

            result = self._analyze_competitors(products)

            state.set("result", result)
            state.set_meta("analysis_completed", True)
            state.add_event("competitor_analyst_success")

        except Exception as e:
            logger.error(f"[CompetitorAnalyst] Error: {e}")
            state.set("error", str(e))
            state.set_meta("analysis_completed", False)
            state.add_event(f"competitor_analyst_error: {e}")

        return state

    def _analyze_competitors(self, products: List[Dict]) -> Dict[str, Any]:
        # 按品牌聚合
        brand_data = self._aggregate_brands(products)
        total_sales = sum(b["total_sales"] for b in brand_data.values())

        # 计算市场份额并排序
        brand_list = []
        for brand, b in brand_data.items():
            share = b["total_sales"] / total_sales if total_sales > 0 else 0
            brand_list.append({
                "brand": brand,
                "market_share": round(share, 4),
                "product_count": b["count"],
                "total_monthly_sales": b["total_sales"],
                "avg_price": round(b["_price_sum"] / b["count"], 2) if b["count"] else 0,
                "min_price": b["min_price"],
                "max_price": b["max_price"],
                "avg_bsr": round(b["_bsr_sum"] / b["_bsr_count"]) if b["_bsr_count"] else None,
                "best_bsr": b["best_bsr"],
                "best_bsr_asin": b["best_bsr_asin"],
                "avg_rating": round(b["_rating_sum"] / b["_rating_count"], 2) if b["_rating_count"] else None,
                "total_reviews": b["total_reviews"],
                "avg_seller_count": round(b["_seller_sum"] / b["count"]) if b["count"] else 0,
                "bsr_trends": b["bsr_trends"],
            })

        brand_list.sort(key=lambda x: x["total_monthly_sales"], reverse=True)

        # 竞争格局分层
        landscape = self._analyze_landscape(brand_list)

        # 差异化机会
        differentiation = self._identify_differentiation(brand_list, products)

        # 评分对比
        rating_comparison = sorted(
            [{"brand": b["brand"], "avg_rating": b["avg_rating"], "total_reviews": b["total_reviews"]}
             for b in brand_list if b["avg_rating"] is not None],
            key=lambda x: x["avg_rating"],
            reverse=True,
        )

        # 价格区间对比
        price_comparison = [
            {
                "brand": b["brand"],
                "min_price": b["min_price"],
                "max_price": b["max_price"],
                "avg_price": b["avg_price"],
                "price_span": round(b["max_price"] - b["min_price"], 2) if b["max_price"] and b["min_price"] else 0,
            }
            for b in brand_list
        ]

        # 集中度
        top3_share = sum(b["market_share"] for b in brand_list[:3])
        leader_share = brand_list[0]["market_share"] if brand_list else 0

        return {
            "analysis_type": "competitor_benchmark",
            "summary": {
                "total_brands_analyzed": len(brand_list),
                "total_products": len(products),
                "total_monthly_sales": total_sales,
                "market_concentration": "高" if leader_share > 0.3 else ("中" if top3_share > 0.5 else "低"),
                "top_3_market_share": round(top3_share, 4),
            },
            "market_share_distribution": [
                {
                    "rank": i + 1,
                    "brand": b["brand"],
                    "market_share": b["market_share"],
                    "market_share_percent": f"{b['market_share']*100:.1f}%",
                    "product_count": b["product_count"],
                    "total_monthly_sales": b["total_monthly_sales"],
                    "avg_price": b["avg_price"],
                    "avg_bsr": b["avg_bsr"],
                }
                for i, b in enumerate(brand_list)
            ],
            "price_comparison": price_comparison,
            "rating_comparison": rating_comparison,
            "differentiation_opportunities": differentiation,
            "competitive_landscape": landscape,
            "generated_at": datetime.now().isoformat(),
        }

    def _aggregate_brands(self, products: List[Dict]) -> Dict[str, Dict]:
        brands: Dict[str, Dict] = {}
        for p in products:
            brand = p.get("brand") or "Unknown"
            if brand not in brands:
                brands[brand] = {
                    "count": 0,
                    "total_sales": 0,
                    "total_reviews": 0,
                    "_price_sum": 0,
                    "min_price": float("inf"),
                    "max_price": 0,
                    "_bsr_sum": 0,
                    "_bsr_count": 0,
                    "best_bsr": None,
                    "best_bsr_asin": None,
                    "_rating_sum": 0,
                    "_rating_count": 0,
                    "_seller_sum": 0,
                    "bsr_trends": {"improving": 0, "declining": 0, "stable": 0, "unknown": 0},
                }
            b = brands[brand]
            b["count"] += 1
            b["total_sales"] += p.get("monthly_sold", 0)
            b["total_reviews"] += p.get("review_count", 0)
            b["_seller_sum"] += p.get("seller_count", 0)

            price = p.get("current_price")
            if price:
                b["_price_sum"] += price
                b["min_price"] = min(b["min_price"], price)
                b["max_price"] = max(b["max_price"], price)

            bsr = p.get("current_bsr")
            if bsr:
                b["_bsr_sum"] += bsr
                b["_bsr_count"] += 1
                if b["best_bsr"] is None or bsr < b["best_bsr"]:
                    b["best_bsr"] = bsr
                    b["best_bsr_asin"] = p.get("asin")

            rating = p.get("rating")
            if rating:
                b["_rating_sum"] += rating
                b["_rating_count"] += 1

            trend = p.get("bsr_trend", "unknown")
            if trend in b["bsr_trends"]:
                b["bsr_trends"][trend] += 1

        # 修正 inf
        for b in brands.values():
            if b["min_price"] == float("inf"):
                b["min_price"] = None

        return brands

    def _analyze_landscape(self, brand_list: List[Dict]) -> Dict[str, Any]:
        tiers = {"第一梯队": [], "第二梯队": [], "第三梯队": []}
        for b in brand_list:
            share = b["market_share"]
            if share >= 0.2:
                tiers["第一梯队"].append(b["brand"])
            elif share >= 0.1:
                tiers["第二梯队"].append(b["brand"])
            else:
                tiers["第三梯队"].append(b["brand"])

        leader_count = len(tiers["第一梯队"])
        if leader_count == 0:
            entry_barrier = "低"
            strategy = "市场分散，可直接进入并争夺份额"
        elif leader_count <= 2:
            entry_barrier = "中"
            strategy = "差异化竞争，避免与头部品牌正面价格战，聚焦细分价格带"
        else:
            entry_barrier = "高"
            strategy = "市场集中度高，建议寻找被忽略的细分需求或价格带切入"

        return {
            "tiers": tiers,
            "market_leaders": [b["brand"] for b in brand_list[:3]],
            "entry_barrier": entry_barrier,
            "recommended_strategy": strategy,
        }

    def _identify_differentiation(
        self, brand_list: List[Dict], products: List[Dict]
    ) -> List[Dict]:
        opportunities = []

        # 1. 价格带空白
        price_bands = [
            ("<$20", 0, 20), ("$20-50", 20, 50), ("$50-100", 50, 100),
            ("$100-200", 100, 200), ("$200+", 200, float("inf")),
        ]
        for label, lo, hi in price_bands:
            in_band = [p for p in products if p.get("current_price") and lo <= p["current_price"] < hi]
            if len(in_band) == 0:
                opportunities.append({
                    "type": "价格带空白",
                    "detail": f"{label} 价格区间无商品覆盖，存在差异化定价机会",
                    "potential": "中",
                })
            elif len(in_band) == 1:
                opportunities.append({
                    "type": "价格带低竞争",
                    "detail": f"{label} 价格区间仅 1 个商品（{in_band[0].get('asin')}），竞争极低",
                    "potential": "中高",
                })

        # 2. BSR 上升但品牌弱势（小品牌在起飞）
        for b in brand_list:
            improving = b["bsr_trends"].get("improving", 0)
            total_trends = sum(b["bsr_trends"].values())
            if total_trends > 0 and improving / total_trends > 0.5 and b["market_share"] < 0.1:
                opportunities.append({
                    "type": "上升中的小品牌",
                    "detail": f"{b['brand']} 超过半数商品 BSR 改善中，份额仅 {b['market_share']*100:.1f}%，值得关注或对标",
                    "potential": "高",
                })

        # 3. 高评论壁垒品牌的弱点（评分低但评论多 = 锁定效应弱）
        for b in brand_list:
            if b["avg_rating"] and b["avg_rating"] < 3.8 and b["total_reviews"] > 500:
                opportunities.append({
                    "type": "评分低洼竞品",
                    "detail": f"{b['brand']} 评分仅 {b['avg_rating']}（{b['total_reviews']} 条评论），用户满意度低，可切入",
                    "potential": "高",
                })

        return opportunities

    async def execute(self, input_data: AgentInput) -> AgentOutput:
        return await super().execute(input_data)
