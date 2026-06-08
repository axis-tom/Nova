"""
市场分析 Agent - 电商选品分析场景

职责（LLM 驱动的新架构）：
1. LLM 拿到商品数据后自主决定分析路径
2. 按需调用分析工具（市场体量、趋势、淡旺季、品牌分布、壁垒等）
3. LLM 逐步思考、决策、输出完整分析报告
4. roi_analysis 模式仍保持纯计算路径

数据源：state.collected_products（由 product_collector 三源采集）或 amazon_products 本地表
"""

import json as _json
from typing import Any, Dict, List
from datetime import datetime
from statistics import median

from langchain_core.tools import tool

from backend.common.core.agent import Agent, AgentInput, AgentOutput
from backend.common.core.state import State
from backend.utils.logger import logger

# ── 本地表查询依赖 ──
from backend.business.ecommerce.product_selection.tools.product_loader import load_products_from_db


_MARKET_SYSTEM_PROMPT = """你是 Amazon 市场分析专家。你有以下分析工具可用：

{tool_descriptions}

你的分析维度必须覆盖：
1. 市场体量与规模（月销总额、营收估算、价格带分布）
2. 市场趋势与方向（BSR 变化率、价格变化率、改善/衰退比例）
3. 淡旺季特征（月度 BSR/价格中位数、旺季月份、季节性强度）
4. 品牌格局与集中度（品牌数量、Top3 市场份额、寡占/分散/竞争判定、进入壁垒）
5. 价格带分布（各价格区间的商品数、平均 BSR、平均评分）
6. 评论壁垒与评分健康（评论数分布、壁垒等级、评分健康度评分）
7. 卖家生态（FBA/FBM/Prime 数量及占比）
8. Listing 质量（A+ 内容覆盖率、视频覆盖率）

规则：
- 每次调用一个工具，看结果，思考后决定下一步
- 不要一次性调用所有工具，按需逐步分析
- 当你认为信息足够覆盖以上维度时，输出最终分析报告
- 最终报告必须是 JSON 格式，包含你分析过的所有维度
- 在报告中说明你选择分析这些维度的理由
- 如果某个工具返回空数据，说明该维度在该市场中不适用

最终 JSON 格式示例：
{{"market_volume": {{...}}, "trends": {{...}}, "seasonality": {{...}}, "brand_analysis": {{...}}, "price_bands": {{...}}, "review_barrier": {{...}}, "rating_health": {{...}}, "seller_composition": {{...}}, "aplus_coverage": {{...}}, "overall_assessment": "..."}}"""


class MarketAnalystAgent(Agent):
    """市场分析 Agent — LLM 驱动，按需调分析工具"""

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
                asins = state.get("asins") or []
                category = state.get("category") or state.get("market_category") or state.get("category_name")
                if asins:
                    try:
                        products = await self._load_from_local_db_by_asins(asins, state.get("domain", "US"))
                    except Exception as e:
                        logger.warning(f"[MarketAnalyst] 本地表 ASIN 查询失败: {e}")
                if not products and category:
                    try:
                        products = await self._load_from_local_db(category, state.get("domain", "US"))
                    except Exception as e:
                        logger.warning(f"[MarketAnalyst] 本地表查询失败: {e}")

            if not products:
                # ★ P1 修复：返回语义化错误，含品类名/domain 信息，方便 Orchestrator 调整策略
                category = state.get("category") or state.get("market_category") or state.get("category_name", "未知")
                domain = state.get("domain", "US")
                state.set("result", {
                    "analysis_type": analysis_type,
                    "error": "无商品数据",
                    "category": category,
                    "domain": domain,
                    "hint": f"品类名='{category}' 在 {domain} 未找到数据。请尝试：1) 用 discover_data 查找正确的品类名；"
                            f"2) 换相近品类名重新调用；3) 或用 ASIN 列表直接查询。",
                })
                state.add_event("market_analyst_no_products")
                return state

            if analysis_type == "market_trends":
                # ── LLM 驱动的分析循环 ──
                tools = self._build_analysis_tools(products)
                tool_descriptions = "\n".join(
                    f"- {t.name}: {t.description}" for t in tools
                )
                system_prompt = _MARKET_SYSTEM_PROMPT.format(
                    tool_descriptions=tool_descriptions,
                )

                # 搜索热度（从 search_results 提取，不作为工具）
                search_results = state.get("search_results") or {}
                extra_context = ""
                if search_results:
                    search_heat = self._analyze_search_heat(search_results)
                    extra_context = f"\n搜索热度数据（已预计算）:\n{_json.dumps(search_heat, ensure_ascii=False, indent=2)}"

                analysis_question = (
                    f"请分析以下 {len(products)} 个商品的市场情况。\n"
                    f"商品数量：{len(products)}，字段：asin/title/brand/price/bsr/rating/review_count/monthly_sold 等。\n"
                    f"部分商品含 price_history/bsr_history 时间序列数据。{extra_context}\n\n"
                    f"请逐步分析，每次调用工具后思考结果，再决定下一步。"
                )

                raw_output = await self._run_analysis_loop(
                    products=products,
                    system_prompt=system_prompt,
                    analysis_question=analysis_question,
                    max_turns=15,
                )

                result = self._parse_json_output(raw_output)
                result["analysis_type"] = "market_trends"
                result["generated_at"] = datetime.now().isoformat()
                result["llm_driven"] = True
                logger.info("[MarketAnalyst] LLM 驱动分析完成")

            elif analysis_type == "roi_analysis":
                # ROI 分析保持纯计算路径（不需要 LLM 决策）
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
            state.set_meta("llm_driven", analysis_type == "market_trends")
            state.add_event("market_analyst_success")

        except Exception as e:
            logger.error(f"[MarketAnalyst] Error: {e}")
            state.set("error", str(e))
            state.set_meta("analysis_completed", False)
            state.add_event(f"market_analyst_error: {e}")

        return state

    # ════════════════════════════════════════════════════════════════
    # 工具定义（每个 _analyze_* 方法 → LangChain tool）
    # ════════════════════════════════════════════════════════════════

    def _build_analysis_tools(self, products: List[Dict]) -> List:
        """将分析维度暴露为 LLM 可调用的工具"""

        @tool
        def analyze_market_volume() -> dict:
            """估算市场体量：月销总量、月营收、平均价格、价格带分布、BSR 范围"""
            return self._analyze_market_volume(products)

        @tool
        def analyze_trends() -> dict:
            """分析 BSR 和价格趋势：30天/90天变化率、改善/衰退/稳定比例、市场方向"""
            return self._analyze_trends_from_history(products)

        @tool
        def analyze_seasonality() -> dict:
            """分析淡旺季：月度 BSR/价格中位数、旺季月份、淡季月份、季节性强度"""
            return self._analyze_seasonality(products)

        @tool
        def analyze_brand_distribution() -> dict:
            """分析品牌分布：各品牌的商品数、总销量、平均价格/评分/BSR"""
            return self._aggregate_by_brand(products)

        @tool
        def analyze_price_bands() -> dict:
            """分析价格带分布：<$20, $20-50, $50-100, $100-200, $200+ 各区间商品数/平均BSR/平均评分"""
            return self._analyze_price_bands(products)

        @tool
        def analyze_review_barrier() -> dict:
            """分析评论数分布：6档评论数区间的分布、平均评论数、评论壁垒等级（极高/高/中/低）"""
            return self._analyze_review_barrier(products)

        @tool
        def analyze_rating_health() -> dict:
            """分析评分健康度：评分四档分布、健康评分(0-100)、健康等级（优秀/良好/一般/较差）"""
            return self._analyze_rating_health(products)

        @tool
        def analyze_seller_composition() -> dict:
            """分析卖家类型分布：FBA/FBM/Prime 的数量和占比"""
            return self._analyze_seller_composition(products)

        @tool
        def analyze_aplus_coverage() -> dict:
            """分析 A+ Content 和视频覆盖率：A+ 商品数/占比、带视频商品数/占比"""
            return self._analyze_aplus_coverage(products)

        @tool
        def analyze_brand_concentration() -> dict:
            """分析品牌集中度：品牌数量、Top3 市场份额、集中度判定（寡占/分散/竞争）、进入壁垒"""
            brand_dist = self._aggregate_by_brand(products)
            return self._analyze_brand_concentration(brand_dist, products)

        @tool
        def analyze_opportunities() -> dict:
            """识别市场机会：上升期低竞争商品、需求旺盛但供给不足、价格带空白"""
            price_bands = self._analyze_price_bands(products)
            return self._identify_opportunities(products, price_bands)

        @tool
        def analyze_risks() -> dict:
            """识别市场风险：市场萎缩风险、竞争激烈风险、评论壁垒风险"""
            trends = self._analyze_trends_from_history(products)
            return self._identify_risks(products, trends, len(products))

        return [
            analyze_market_volume, analyze_trends, analyze_seasonality,
            analyze_brand_distribution, analyze_price_bands,
            analyze_review_barrier, analyze_rating_health,
            analyze_seller_composition, analyze_aplus_coverage,
            analyze_brand_concentration,
            analyze_opportunities, analyze_risks,
        ]

    # ════════════════════════════════════════════════════════════════
    # 新增维度分析（从 market_analysis.py Service 层移植）
    # ════════════════════════════════════════════════════════════════

    def _analyze_review_barrier(self, products: List[Dict]) -> Dict[str, Any]:
        """评论数分布 + 壁垒评估（移植自 M5: get_review_count_distribution）"""
        reviews = [p.get("review_count") for p in products if p.get("review_count") is not None]
        if not reviews:
            return {"total_with_reviews": 0, "distribution": {}, "review_barrier": "未知"}

        bands = [
            ("0-10", 0, 10), ("10-50", 10, 50), ("50-200", 50, 200),
            ("200-1000", 200, 1000), ("1000-5000", 1000, 5000), ("5000+", 5000, float("inf")),
        ]
        distribution = {}
        for label, lo, hi in bands:
            distribution[label] = sum(1 for r in reviews if lo <= r < hi)

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

    def _analyze_rating_health(self, products: List[Dict]) -> Dict[str, Any]:
        """评分分布 + 健康度评估（移植自 M6: get_rating_distribution）"""
        ratings = [p.get("rating") for p in products if p.get("rating")]
        if not ratings:
            return {"total_with_rating": 0, "distribution": {}, "rating_health_score": 0}

        bands = [
            ("4.0-5.0", 4.0, 5.0), ("3.0-4.0", 3.0, 4.0),
            ("2.0-3.0", 2.0, 3.0), ("1.0-2.0", 1.0, 2.0),
        ]
        distribution = {}
        for label, lo, hi in bands:
            distribution[label] = sum(1 for r in ratings if lo <= r < hi)

        excellent = sum(1 for r in ratings if r >= 4.5)
        good = sum(1 for r in ratings if 4.0 <= r < 4.5)
        average = sum(1 for r in ratings if 3.0 <= r < 4.0)
        poor = sum(1 for r in ratings if r < 3.0)
        total = len(ratings)

        health_score = round(
            (excellent * 100 + good * 75 + average * 50 + poor * 0) / total, 1
        ) if total else 0

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

    def _analyze_seller_composition(self, products: List[Dict]) -> Dict[str, Any]:
        """卖家类型分布：FBA/FBM/Prime（移植自 M8: get_seller_type_distribution）"""
        total = len(products)
        if not total:
            return {"total_products": 0}

        fba = sum(1 for p in products if p.get("is_fba"))
        # FBM = not FBA (agent dict 没有 fulfillment 字段, 用 available/prime 推断)
        prime = sum(1 for p in products if p.get("is_prime"))
        fbm = total - fba
        unknown = 0

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

    def _analyze_aplus_coverage(self, products: List[Dict]) -> Dict[str, Any]:
        """A+ Content 和视频覆盖率（移植自 M9: get_aplus_video_distribution）"""
        total = len(products)
        if not total:
            return {"total_products": 0}

        has_aplus = sum(1 for p in products if p.get("aplus_content"))
        no_aplus = total - has_aplus
        # 从 images 数量推断是否有视频（images > 1 表示有额外媒体内容）
        with_video = sum(1 for p in products if p.get("images") and len(p.get("images", [])) > 1)
        video_counts = [len(p.get("images", [])) for p in products if p.get("images") and len(p.get("images", [])) > 1]

        return {
            "total_products": total,
            "aplus_count": has_aplus,
            "aplus_pct": round(has_aplus / total * 100, 1) if total else 0,
            "no_aplus_count": no_aplus,
            "no_aplus_pct": round(no_aplus / total * 100, 1) if total else 0,
            "with_video_count": with_video,
            "with_video_pct": round(with_video / total * 100, 1) if total else 0,
            "avg_video_or_image_count": round(sum(video_counts) / len(video_counts)) if video_counts else 0,
        }

    def _analyze_brand_concentration(self, brand_dist: Dict, products: List[Dict]) -> Dict[str, Any]:
        """品牌集中度 + 进入壁垒（移植自 M4: get_brand_concentration）

        brand_dist 来自 _aggregate_by_brand() 的输出，已含 total_sales。
        """
        if not brand_dist:
            return {"total_brands": 0, "concentration": "未知", "entry_barrier": "未知"}

        total_sales = sum(b.get("total_sales", 0) for b in brand_dist.values())

        # 构建品牌列表（按销量排序）
        brand_list = []
        for brand, info in brand_dist.items():
            share = (info["total_sales"] / total_sales * 100) if total_sales > 0 else 0
            brand_list.append({
                "brand": brand,
                "product_count": info.get("count", 0),
                "total_monthly_sales": info.get("total_sales", 0),
                "market_share_pct": round(share, 1),
                "avg_price": info.get("avg_price"),
                "avg_rating": info.get("avg_rating"),
                "avg_bsr": info.get("avg_bsr"),
                "best_bsr_asin": info.get("best_bsr_asin"),
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
            "total_brands": len(brand_dist),
            "total_products": sum(b.get("count", 0) for b in brand_dist.values()),
            "top_3_market_share_pct": round(top3_share, 1),
            "concentration": concentration,
            "entry_barrier": entry_barrier,
            "brands": brand_list[:10],  # top 10 品牌
        }

    # ── 新增：从 amazon_products 本地表加载 ──

    async def _load_from_local_db(self, category: str, domain: str) -> List[Dict]:
        """从 amazon_products 表加载完整商品数据（全字段 + 33 推导域 + 子表）"""
        products = await load_products_from_db(
            category=category, domain=domain, with_derived=True,
        )
        if products:
            logger.info(
                f"[MarketAnalyst] 从本地表加载 {len(products)} 个商品（类目={category}），"
                f"每商品 {len(products[0])} 个字段/推导域"
            )
        else:
            logger.info(f"[MarketAnalyst] 本地表未找到商品（类目={category}）")
        return products

    async def _load_from_local_db_by_asins(self, asins: list, domain: str) -> List[Dict]:
        """从 amazon_products 表按 ASIN 列表加载完整商品数据"""
        if not asins:
            return []
        products = await load_products_from_db(
            asins=asins, domain=domain, with_derived=True,
        )
        logger.info(
            f"[MarketAnalyst] 从本地表加载 {len(products)}/{len(asins)} 个商品（ASIN 列表）"
        )
        return products

    async def execute(self, input_data: AgentInput) -> AgentOutput:
        return await super().execute(input_data)

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