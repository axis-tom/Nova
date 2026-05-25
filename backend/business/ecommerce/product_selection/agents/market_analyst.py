"""
市场分析 Agent - 电商选品分析场景

职责：
1. 读取 state.collected_products（Keepa + Rainforest + Canopy 三源数据）
2. 市场体量：月销总额、营收估算、价格带分布
3. 市场趋势：用 price_history / bsr_history CSV 时间序列做真正的趋势计算
4. 淡旺季：按月份聚合 BSR/价格，识别旺季低谷
5. 品牌分布、价格带、机会/风险识别
6. 盈利评估（roi_analysis 模式）

数据源：state.collected_products（由 product_collector 三源采集）
"""

import json as _json
from typing import Any, Dict, List
from datetime import datetime
from statistics import median

from backend.common.core.agent import Agent, AgentInput, AgentOutput
from backend.common.core.state import State
from backend.utils.logger import logger

# ── 新增：本地表查询依赖 ──
from backend.data.database import AsyncSessionLocal
from backend.data.repositories.postgreSQL.amazon_product_repo import AmazonProductRepository


class MarketAnalystAgent(Agent):
    """市场分析 Agent — 基于 Keepa 历史 + Rainforest/Canopy 详情做市场趋势和淡旺季分析"""

    name = "market_analyst"
    description = "电商选品市场分析 Agent，基于 Keepa 时间序列 + Canopy/Rainforest listing 数据做市场体量/趋势/淡旺季分析"

    async def run(self, state: State) -> State:
        state.add_event("market_analyst_start")
        analysis_type = state.get("analysis_type", "market_trends")
        state.set_meta("analysis_type", analysis_type)

        try:
            products: List[Dict] = state.get("collected_products", []) or []

            # ── 优先从 amazon_products 本地表读取 ──
            if not products:
                category = state.get("category") or state.get("market_category")
                if category:
                    try:
                        products = await self._load_from_local_db(category, state.get("domain", "US"))
                    except Exception as e:
                        logger.warning(f"[MarketAnalyst] 本地表查询失败，回退旧路径: {e}")

            if not products:
                state.set("result", {
                    "analysis_type": analysis_type,
                    "error": "无商品数据，请先调用 product_collector 采集商品",
                })
                state.add_event("market_analyst_no_products")
                return state

            if analysis_type == "market_trends":
                result = self._analyze_market_trends(products)

                # 注入搜索热度（从 search_results 中提取）
                search_results = state.get("search_results") or {}
                if search_results:
                    result["search_heat"] = self._analyze_search_heat(search_results)

                # LLM 增强
                ai_result = await self._llm_analyze_market(result)
                if ai_result:
                    result["ai_insights"] = ai_result
                    logger.info("[MarketAnalyst] LLM 市场洞察已注入")

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
            state.set_meta("llm_enhanced", bool(result.get("ai_insights")))
            state.add_event("market_analyst_success")

        except Exception as e:
            logger.error(f"[MarketAnalyst] Error: {e}")
            state.set("error", str(e))
            state.set_meta("analysis_completed", False)
            state.add_event(f"market_analyst_error: {e}")

        return state

    # ── 新增：从 amazon_products 本地表加载 ──

    async def _load_from_local_db(self, category: str, domain: str) -> List[Dict]:
        """从 amazon_products 表查询该类目的商品，转为旧格式供下游分析"""
        async with AsyncSessionLocal() as db:
            repo = AmazonProductRepository(db)
            from sqlalchemy import select
            from backend.data.models.amazon_product import AmazonProduct
            stmt = select(AmazonProduct).where(
                AmazonProduct.category_name == category,
                AmazonProduct.domain == domain,
            )
            result = await db.execute(stmt)
            products = list(result.scalars().all())

        if not products:
            return []

        # 转为 MarketAnalystAgent 期望的 dict 格式
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
        logger.info(f"[MarketAnalyst] 从本地表加载 {len(converted)} 个商品（类目={category}）")
        return converted

    # ── LLM 增强分析 ──

    async def _llm_analyze_market(self, market_result: Dict[str, Any]) -> Dict[str, Any]:
        summary = market_result.get("summary", {})
        volume = market_result.get("market_volume", {})
        seasonality = market_result.get("seasonality", {})
        trends = market_result.get("trends", {})
        brand_distribution = market_result.get("brand_distribution", {})
        opportunities = market_result.get("opportunities", [])
        risks = market_result.get("risks", [])

        top_brands = dict(list(brand_distribution.items())[:5])

        prompt = _json.dumps({
            "market_volume": volume,
            "summary": summary,
            "trends": trends,
            "seasonality": {k: v for k, v in seasonality.items() if k != "monthly_bsr_median" and k != "monthly_price_median"},
            "top_brands": {
                brand: {
                    "count": info.get("count"), "total_sales": info.get("total_sales"),
                    "avg_price": info.get("avg_price"), "avg_rating": info.get("avg_rating"),
                }
                for brand, info in top_brands.items()
            },
            "opportunities": opportunities[:5],
            "risks": risks[:5],
        }, ensure_ascii=False, indent=2)

        system = (
            "You are an Amazon market analyst. "
            "Based on the market data below, provide strategic insights in Chinese.\n"
            "Return JSON with these fields:\n"
            "- market_stage: string, 市场所处阶段（成长期/成熟期/衰退期）\n"
            "- entry_recommendation: string, 进入建议（考虑体量+趋势+淡旺季）\n"
            "- key_success_factors: list of strings, 关键成功因素\n"
            "- hidden_risks: list of strings, 隐藏风险\n"
            "- seasonality_strategy: string, 基于淡旺季的运营策略建议\n"
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
            logger.warning("[MarketAnalyst] LLM returned invalid JSON, skipping")
        return {}

    # ── 市场体量 ──────────────────────────────────────────────────────

    def _analyze_market_volume(self, products: List[Dict]) -> Dict[str, Any]:
        """用 monthly_sold + 价格 + BSR 综合估算市场体量"""
        total_monthly_sold = sum(p.get("monthly_sold", 0) for p in products)
        total_revenue = sum(
            (p.get("monthly_sold", 0) or 0) *
            (p.get("avg_price_90d") or p.get("current_price") or 0)
            for p in products
        )

        prices = [p["current_price"] for p in products if p.get("current_price")]
        bsr_vals = [p["current_bsr"] for p in products if p.get("current_bsr")]

        # 价格带
        price_bands = self._analyze_price_bands(products)

        return {
            "total_monthly_units": total_monthly_sold,
            "estimated_monthly_revenue": round(total_revenue, 2),
            "product_count": len(products),
            "avg_price": round(sum(prices) / len(prices), 2) if prices else 0,
            "price_tier_distribution": price_bands,
            "bsr_range": {
                "min": min(bsr_vals) if bsr_vals else None,
                "max": max(bsr_vals) if bsr_vals else None,
                "median": round(median(bsr_vals)) if bsr_vals else None,
            },
        }

    # ── 市场趋势（用 time-series 替代单点标签） ──────────────────────

    @staticmethod
    def _get_value_at_days_ago(history: List, days: int):
        """从 [[timestamp_ms, value], ...] 中找约 N 天前的值"""
        if not history or len(history) < 2:
            return None
        target_ts = history[-1][0] - days * 86400 * 1000
        best = None
        for ts, val in history:
            if best is None or abs(ts - target_ts) < abs(best[0] - target_ts):
                best = (ts, val)
        return best[1] if best else None

    def _analyze_trends_from_history(self, products: List[Dict]) -> Dict[str, Any]:
        """从 price_history / bsr_history CSV 计算真正的趋势指标"""
        bsr_changes_30d = []
        bsr_changes_90d = []
        price_changes_30d = []
        price_changes_90d = []
        bsr_direction = {"improving": 0, "declining": 0, "stable": 0}

        for p in products:
            bsr_hist = p.get("bsr_history") or []
            price_hist = p.get("price_history") or []

            if bsr_hist and len(bsr_hist) >= 2:
                bsr_30 = self._get_value_at_days_ago(bsr_hist, 30)
                bsr_90 = self._get_value_at_days_ago(bsr_hist, 90)
                bsr_now = bsr_hist[-1][1]

                if bsr_30 and bsr_30 > 0:
                    chg = (bsr_now - bsr_30) / bsr_30 * 100
                    bsr_changes_30d.append(chg)
                if bsr_90 and bsr_90 > 0:
                    chg = (bsr_now - bsr_90) / bsr_90 * 100
                    bsr_changes_90d.append(chg)

                # 方向分类
                if bsr_30 and bsr_now < bsr_30 * 0.95:
                    bsr_direction["improving"] += 1
                elif bsr_30 and bsr_now > bsr_30 * 1.05:
                    bsr_direction["declining"] += 1
                else:
                    bsr_direction["stable"] += 1
            else:
                bsr_direction["stable"] += 1  # 无历史数据默认稳定

            if price_hist and len(price_hist) >= 2:
                price_30 = self._get_value_at_days_ago(price_hist, 30)
                price_90 = self._get_value_at_days_ago(price_hist, 90)
                price_now = price_hist[-1][1]

                if price_30 and price_30 > 0:
                    chg = (price_now - price_30) / price_30 * 100
                    price_changes_30d.append(chg)
                if price_90 and price_90 > 0:
                    chg = (price_now - price_90) / price_90 * 100
                    price_changes_90d.append(chg)

        total = len(products)
        median_bsr_30 = round(median(bsr_changes_30d), 1) if bsr_changes_30d else None
        median_price_30 = round(median(price_changes_30d), 1) if price_changes_30d else None

        # 市场方向判断
        improving_pct = bsr_direction["improving"] / total * 100 if total else 0
        declining_pct = bsr_direction["declining"] / total * 100 if total else 0
        if improving_pct > 40:
            market_dir = "上升"
        elif declining_pct > 40:
            market_dir = "下降"
        else:
            market_dir = "稳定"

        return {
            "bsr": {
                "median_change_30d_pct": median_bsr_30,
                "median_change_90d_pct": round(median(bsr_changes_90d), 1) if bsr_changes_90d else None,
                "improving_pct": round(improving_pct, 1),
                "declining_pct": round(declining_pct, 1),
                "stable_pct": round(bsr_direction["stable"] / total * 100, 1) if total else 0,
                "market_direction": market_dir,
            },
            "price": {
                "median_change_30d_pct": median_price_30,
                "median_change_90d_pct": round(median(price_changes_90d), 1) if price_changes_90d else None,
                "price_direction": (
                    "上涨" if median_price_30 and median_price_30 > 3
                    else "下降" if median_price_30 and median_price_30 < -3
                    else "稳定"
                ),
            },
        }

    # ── 淡旺季 ────────────────────────────────────────────────────────

    def _analyze_seasonality(self, products: List[Dict]) -> Dict[str, Any]:
        """
        用 price_history / bsr_history CSV 按月聚合。
        BSR 最低 = 需求最高（旺季），价格最高 = 溢价期。
        """
        monthly_bsr: Dict[int, List[float]] = {i: [] for i in range(1, 13)}
        monthly_price: Dict[int, List[float]] = {i: [] for i in range(1, 13)}

        for p in products:
            for ts, bsr in (p.get("bsr_history") or []):
                try:
                    month = datetime.fromtimestamp(ts / 1000).month
                    monthly_bsr[month].append(float(bsr))
                except (OSError, ValueError, TypeError):
                    continue

            for ts, price in (p.get("price_history") or []):
                try:
                    month = datetime.fromtimestamp(ts / 1000).month
                    monthly_price[month].append(float(price))
                except (OSError, ValueError, TypeError):
                    continue

        # 计算月度中位数
        monthly_bsr_med = {}
        monthly_price_med = {}
        for m in range(1, 13):
            vals = monthly_bsr.get(m, [])
            monthly_bsr_med[m] = round(median(vals)) if vals else None
            pvals = monthly_price.get(m, [])
            monthly_price_med[m] = round(median(pvals), 2) if pvals else None

        # BSR 中位数最低的月份 = 旺季
        valid_bsr = [(m, v) for m, v in monthly_bsr_med.items() if v is not None]
        valid_bsr.sort(key=lambda x: x[1])
        peak_months = [m for m, _ in valid_bsr[:3]]
        low_months = [m for m, _ in valid_bsr[-3:]] if len(valid_bsr) >= 6 else []

        # 季节性强度：旺季 BSR vs 淡季 BSR 差距
        strength = "弱"
        if peak_months and low_months:
            peak_bsr = monthly_bsr_med.get(peak_months[0])
            low_bsr = monthly_bsr_med.get(low_months[0])
            if peak_bsr and low_bsr and peak_bsr > 0:
                ratio = low_bsr / peak_bsr
                if ratio > 2:
                    strength = "强"
                elif ratio > 1.3:
                    strength = "中"

        return {
            "peak_season_months": peak_months,
            "low_season_months": low_months,
            "monthly_bsr_median": monthly_bsr_med,
            "monthly_price_median": monthly_price_med,
            "seasonality_strength": strength,
        }

    # ── 搜索热度 ──────────────────────────────────────────────────────

    def _analyze_search_heat(self, search_results: Dict[str, Any]) -> Dict[str, Any]:
        """从 Canopy/Rainforest 搜索结果中提取搜索热度指标"""
        keyword_results = search_results.get("keyword_results") or []
        total_results = []
        for kr in keyword_results:
            tr = kr.get("total_results", 0)
            if isinstance(tr, (int, float)) and tr > 0:
                total_results.append(tr)

        if not total_results:
            return {"heat_level": "未知", "keyword_count": len(keyword_results)}

        avg_results = round(sum(total_results) / len(total_results))
        if avg_results > 200:
            heat = "高"
        elif avg_results > 100:
            heat = "中"
        else:
            heat = "低"

        return {
            "heat_level": heat,
            "avg_search_results": avg_results,
            "max_search_results": max(total_results),
            "min_search_results": min(total_results),
            "keyword_count": len(keyword_results),
        }

    # ── 市场趋势分析（重构） ─────────────────────────────────────────

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

        # 品牌分布
        brand_distribution = self._aggregate_by_brand(products)

        # 价格带分析
        price_band_analysis = self._analyze_price_bands(products)

        # 市场体量（新增）
        market_volume = self._analyze_market_volume(products)

        # 趋势（time-series 增强）
        trends = self._analyze_trends_from_history(products)

        # 淡旺季（新增）
        seasonality = self._analyze_seasonality(products)

        # 机会识别
        opportunities = self._identify_opportunities(products, price_band_analysis)

        # 风险识别
        risks = self._identify_risks(products, trends, total)

        return {
            "analysis_type": "market_trends",
            "summary": {
                "total_products_analyzed": total,
                "average_price": round(avg_price, 2),
                "total_monthly_sales": total_monthly_sales,
                "average_rating": round(avg_rating, 2),
                "average_bsr": round(avg_bsr),
                "market_direction": trends["bsr"]["market_direction"],
            },
            "market_volume": market_volume,
            "trends": trends,
            "seasonality": seasonality,
            "brand_distribution": brand_distribution,
            "price_band_analysis": price_band_analysis,
            "opportunities": opportunities,
            "risks": risks,
            "generated_at": datetime.now().isoformat(),
        }

    # ── 品牌聚合 ──────────────────────────────────────────────────────

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

        for band, stats in price_bands.items():
            if stats["count"] == 0:
                opportunities.append({
                    "opportunity": f"价格带空白：{band}",
                    "evidence": "该价格区间无商品，可能是差异化切入点",
                    "strength": "中",
                })

        return opportunities

    def _identify_risks(self, products: List[Dict], trends: Dict, total: int) -> List[Dict]:
        risks = []

        bsr_t = trends.get("bsr", {})
        declining_pct = bsr_t.get("declining_pct", 0)
        if declining_pct > 40:
            risks.append({
                "risk_type": "市场萎缩",
                "detail": f"{declining_pct:.0f}% 的商品 BSR 呈下降趋势，市场可能在收缩",
                "severity": "高",
            })

        seller_counts = [p.get("seller_count", 0) for p in products if p.get("seller_count")]
        avg_sellers = sum(seller_counts) / len(seller_counts) if seller_counts else 0
        if avg_sellers > 20:
            risks.append({
                "risk_type": "竞争激烈",
                "detail": f"平均每个商品有 {avg_sellers:.0f} 个卖家，竞争密度高",
                "severity": "高" if avg_sellers > 50 else "中",
            })

        review_counts = [p.get("review_count", 0) for p in products if p.get("review_count")]
        avg_reviews = sum(review_counts) / len(review_counts) if review_counts else 0
        if avg_reviews > 1000:
            risks.append({
                "risk_type": "评论壁垒",
                "detail": f"平均评论数 {avg_reviews:.0f}，新进入者难以快速建立信任",
                "severity": "高" if avg_reviews > 5000 else "中",
            })

        return risks

    # ── 盈利评估 ──────────────────────────────────────────────────────

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