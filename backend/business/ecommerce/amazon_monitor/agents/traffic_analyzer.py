"""
流量与竞品分析 Agent - Amazon 监控场景（LLM 驱动的新架构）

职责：
1. LLM 拿到商品数据后自主决定流量/竞品分析路径
2. 按需调用分析工具（BSR 排名、价格分析、竞品对比、价格预警）
3. LLM 逐步思考、决策、输出完整的流量洞察报告
"""

import asyncio
import json as _json
from typing import Any, Dict, List, Optional
from datetime import datetime

from langchain_core.tools import tool

from backend.common.core.agent import Agent
from backend.common.core.state import State
from backend.utils.logger import logger
from backend.business.ecommerce.product_selection.tools.product_loader import load_products_from_db


_TRAFFIC_SYSTEM_PROMPT = """你是 Amazon 流量与竞品分析专家。你有以下分析工具可用：

{tool_descriptions}

你的分析维度必须覆盖：
1. BSR 排名分布（Top 100/1000/10000/Others 分布、平均 BSR、最佳 BSR 商品、品类平均 BSR）
2. 价格分布（平均/最低/最高价格、价格区间分布、Prime 占比、推荐价格区间）
3. 竞品对比（按品类分组的平均价格/评分/评论数、竞争等级判断）
4. 价格预警（价格异常偏离市场均价的商品、偏离百分比）
5. 流量洞察汇总（竞争等级、高潜力商品数、市场摘要、Top 机会）

规则：
- 每次调用一个工具，看结果，思考后决定下一步
- 按需逐步分析，不要一次性调用所有工具
- 当你认为信息足够覆盖以上维度时，输出最终分析报告
- 最终报告必须是 JSON 格式

最终报告输出到以下 state keys：
- traffic_insights: 流量洞察
- bsr_analysis: BSR 排名分析
- price_analysis: 价格分析
- competitor_comparison: 竞品对比
- price_alerts: 价格预警列表"""


class TrafficAnalyzerAgent(Agent):
    """
    流量与竞品分析 Agent — LLM 驱动，按需调流量/竞品工具
    分析 BSR 排名、价格竞争和市场格局
    """

    name = "traffic_analyzer"
    description = "Amazon 流量与竞品分析 Agent，分析 BSR 排名和价格竞争"

    async def run(self, state: State) -> State:
        state.add_event("traffic_analyzer_start")
        logger.info("[TrafficAnalyzer] Starting LLM-driven traffic analysis")

        try:
            products: List[Dict] = state.get("collected_products", [])
            product_map: Dict = state.get("product_map", {})

            # ── 优先从 amazon_products 本地表读取 ──
            if not products:
                asins = state.get("asins") or []
                category = state.get("category") or state.get("market_category") or state.get("category_name")
                try:
                    products = await self._load_from_local_db(
                        asins=asins, category=category, domain=state.get("domain", "US"),
                    )
                except Exception as e:
                    logger.warning(f"[TrafficAnalyzer] 本地表查询失败: {e}")

            # 字段归一化：Keepa 用 current_price/current_bsr，内部分析用 price/bsr_rank
            for p in products:
                if "current_price" in p and "price" not in p:
                    p["price"] = p["current_price"]
                if "current_bsr" in p and "bsr_rank" not in p:
                    p["bsr_rank"] = p["current_bsr"]

            if not products:
                logger.warning("[TrafficAnalyzer] No products to analyze")
                state.set("traffic_insights", {})
                state.set("bsr_analysis", {})
                state.set("competitor_comparison", {})
                state.set("price_alerts", [])
                state.add_event("traffic_analyzer_no_products")
                return state

            # ── 先跑确定性分析作为兜底 ──
            bsr_analysis = self._analyze_bsr(products)
            price_analysis = self._analyze_prices(products)
            competitor_comparison = self._compare_competitors(products)
            price_alerts = self._detect_price_alerts(products)
            traffic_insights = self._build_traffic_insights(
                products, bsr_analysis, price_analysis, competitor_comparison,
            )
            state.set("traffic_insights", traffic_insights)
            state.set("bsr_analysis", bsr_analysis)
            state.set("competitor_comparison", competitor_comparison)
            state.set("price_alerts", price_alerts)

            # ── LLM 驱动的分析循环（仅用于增强，失败不丢兜底数据） ──
            tools = self._build_analysis_tools(products)
            tool_descriptions = "\n".join(
                f"- {t.name}: {t.description}" for t in tools
            )
            system_prompt = _TRAFFIC_SYSTEM_PROMPT.format(
                tool_descriptions=tool_descriptions,
            )

            analysis_question = (
                f"请分析以下 {len(products)} 个商品的流量和竞争数据。\n"
                f"请逐步分析，每次调用工具后思考结果，再决定下一步。"
            )

            raw_output = await self._run_analysis_loop(
                products=products,
                system_prompt=system_prompt,
                analysis_question=analysis_question,
                max_turns=15,
            )

            result = self._parse_json_output(raw_output)
            result["llm_driven"] = True
            logger.info("[TrafficAnalyzer] LLM 驱动流量分析完成")

            # 如果 LLM 返回了合法 JSON，用其覆盖兜底数据（否则保留兜底）
            if result.get("traffic_insights"):
                state.set("traffic_insights", result["traffic_insights"])
            if result.get("bsr_analysis"):
                state.set("bsr_analysis", result["bsr_analysis"])
            if result.get("competitor_comparison"):
                state.set("competitor_comparison", result["competitor_comparison"])
            if result.get("price_alerts"):
                state.set("price_alerts", result["price_alerts"])
            state.set_meta("traffic_analyzed", len(products))
            state.set_meta("llm_driven", True)

            logger.info(f"[TrafficAnalyzer] LLM analysis complete")
            state.add_event(f"traffic_analyzer_success")

        except Exception as e:
            logger.error(f"[TrafficAnalyzer] Error: {e}")
            state.set("error", str(e))
            state.set("traffic_insights", {})
            state.set("bsr_analysis", {})
            state.set("competitor_comparison", {})
            state.set("price_alerts", [])
            state.add_event(f"traffic_analyzer_error: {e}")

        return state

    # ════════════════════════════════════════════════════════════════
    # 工具定义
    # ════════════════════════════════════════════════════════════════

    def _build_analysis_tools(self, products: List[Dict]) -> List:
        """将流量/竞品分析维度暴露为 LLM 可调用的工具"""

        @tool
        def analyze_bsr_distribution() -> dict:
            """分析 BSR 排名分布：Top 100/1000/10000/Others 分布、平均 BSR、最佳 BSR 商品、品类平均 BSR"""
            return self._analyze_bsr(products)

        @tool
        def analyze_price_distribution() -> dict:
            """分析价格分布：平均/最低/最高价格、价格区间分布、Prime 占比、推荐价格区间"""
            return self._analyze_prices(products)

        @tool
        def compare_competitors_by_category() -> dict:
            """竞品对比：按品类分组的平均价格/评分/评论数、最佳评分/最多评论商品、竞争等级"""
            return self._compare_competitors(products)

        @tool
        def detect_price_anomalies() -> list:
            """检测价格异常：价格显著偏离市场均价的商品、偏离百分比、预警类型"""
            return self._detect_price_alerts(products)

        @tool
        def build_traffic_overview() -> dict:
            """构建流量洞察汇总：竞争等级、高潜力商品数、市场摘要、Top 机会"""
            bsr = self._analyze_bsr(products)
            price = self._analyze_prices(products)
            comp = self._compare_competitors(products)
            return self._build_traffic_insights(products, bsr, price, comp)

        return [
            analyze_bsr_distribution, analyze_price_distribution,
            compare_competitors_by_category, detect_price_anomalies,
            build_traffic_overview,
        ]


        try:
            cleaned = raw.strip()
            if cleaned.startswith("```"):
                cleaned = cleaned.split("\n", 1)[-1].rsplit("```", 1)[0]
            result = _json.loads(cleaned)
            if isinstance(result, dict):
                return result
        except (_json.JSONDecodeError, ValueError):
            logger.warning("[TrafficAnalyzer] LLM returned invalid JSON, skipping")
        return {}

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

    # ── 从 amazon_products 本地表加载（完整 180+ 字段 + 33 推导域） ──

    async def _load_from_local_db(
        self, asins: List[str] = None, category: str = None, domain: str = "US",
    ) -> List[Dict]:
        """从 amazon_products 表加载完整商品数据。DB 没有 → 自动通过 API 冷启动采集。"""
        products = await load_products_from_db(
            asins=asins, category=category, domain=domain, with_derived=True,
        )
        # 字段归一化：下游分析用 price/bsr_rank
        for p in products:
            if p.get("current_price") is not None:
                p["price"] = p["current_price"]
            if p.get("current_bsr") is not None:
                p["bsr_rank"] = p["current_bsr"]

        n = len(products)
        source = f"{len(asins)} ASIN" if asins else f"类目={category}"
        if products:
            logger.info(
                f"[TrafficAnalyzer] 从本地表加载 {n} 个商品（{source}），"
                f"每商品 {len(products[0])} 个字段/推导域"
            )
            return products

        # ★ DB 无数据 → 走 DataProvider 冷启动
        logger.info(f"[TrafficAnalyzer] 本地表未找到商品（{source}），触发冷启动...")
        if asins:
            from backend.aqueduct.data_provider import DataProvider
            provider = DataProvider()
            for a in asins[:10]:
                try:
                    await provider.get_product_blocking(a, domain)
                except Exception:
                    pass
            products = await load_products_from_db(
                asins=asins, domain=domain, with_derived=True,
            )
            # 冷启动后的字段归一化
            for p in products:
                if p.get("current_price") is not None:
                    p["price"] = p["current_price"]
                if p.get("current_bsr") is not None:
                    p["bsr_rank"] = p["current_bsr"]
            if products:
                logger.info(f"[TrafficAnalyzer] 冷启动后加载 {len(products)} 个商品")

        return products
