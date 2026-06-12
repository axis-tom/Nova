"""
竞品分析 Agent - 电商选品分析场景（LLM 驱动的新架构）

职责：
1. LLM 拿到商品数据后自主决定竞品分析路径
2. 按需调用分析工具（品牌聚合、head-to-head、listing 质量、定价策略等）
3. LLM 逐步思考、决策、输出完整的竞品分析报告

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
from backend.business.ecommerce.product_selection.tools.product_loader import load_products_from_db


_COMPETITOR_SYSTEM_PROMPT = """你是 Amazon 竞品分析专家。你有以下分析工具可用：

{tool_descriptions}

你的分析维度必须覆盖：
1. 品牌格局与市场份额（品牌数量、各品牌份额、Top3 集中度、市场集中度判定）
2. 头部竞品深度对比（BSR 最好的 3 个产品的逐项对比：价格/评分/评论/定价策略/功能/变体）
3. Listing 质量对比（五点/图片/A+/描述完整度、各商品评分及分布）
4. 定价策略分析（各竞品的价格模式：稳定/涨价/降价/波动）
5. 评分对比（各品牌的平均评分、总评论数）
6. 价格区间对比（各品牌的价格区间和价格跨度）
7. 竞争格局分层（第一/二/三梯队、市场领导者、进入壁垒）
8. 差异化机会（价格带空白、上升中的小品牌、评分低洼竞品）

规则：
- 每次调用一个工具，看结果，思考后决定下一步
- 不要一次性调用所有工具，按需逐步分析
- 当你认为信息足够覆盖以上维度时，输出最终分析报告
- 最终报告必须是 JSON 格式，包含你分析过的所有维度
- 在报告中说明关键洞察和战略建议

最终 JSON 格式示例：
{{"market_share_distribution": [...], "head_to_head": {{...}}, "listing_quality": {{...}}, "brand_landscape": {{...}}, "differentiation_opportunities": [...], "overall_strategy": "..."}}"""


class CompetitorAnalystAgent(Agent):
    """竞品分析 Agent — LLM 驱动，按需调竞品分析工具"""

    name = "competitor_analyst"
    description = "电商竞品分析 Agent，基于 Keepa + Canopy/Rainforest 数据做品牌竞争和产品级对比分析"

    async def run(self, state: State) -> State:
        state.add_event("competitor_analyst_start")

        try:
            products: List[Dict] = state.get("collected_products", []) or []

            # ── 优先从 amazon_products 本地表读取 ──
            if not products:
                asins = state.get("asins") or []
                category = state.get("category") or state.get("market_category") or state.get("category_name")
                try:
                    products = await self._load_from_local_db(
                        asins=asins, category=category, domain=state.get("domain", "US"),
                    )
                except Exception as e:
                    logger.warning(f"[CompetitorAnalyst] 本地表查询失败: {e}")

            if not products:
                category = state.get("category") or state.get("market_category") or state.get("category_name", "未知")
                domain = state.get("domain", "US")
                state.set("result", {
                    "analysis_type": "competitor_benchmark",
                    "error": "无商品数据",
                    "category": category,
                    "domain": domain,
                    "hint": f"品类名='{category}' 在 {domain} 未找到数据。请尝试：1) 用 discover_data 查找正确的品类名；"
                            f"2) 换相近品类名重新调用；3) 或用 ASIN 列表直接查询。",
                })
                state.add_event("competitor_analyst_no_products")
                return state

            # ── 先跑确定性分析作为兜底 ──
            brand_list = self._aggregate_brands(products)
            state.set("result", {
                "analysis_type": "competitor_benchmark",
                "market_share_distribution": brand_list,
                "head_to_head": self._analyze_head_to_head(products),
                "listing_quality": self._analyze_listing_quality(products),
                "brand_landscape": self._analyze_brand_landscape(brand_list, products),
                "differentiation_opportunities": self._identify_differentiation(brand_list, products),
            })
            state.set("competitor_analysis_result", state.get("result"))
            state.set_meta("analysis_completed", True)

            # ── LLM 驱动的分析循环（仅用于增强，失败不丢兜底数据） ──
            tools = self._build_analysis_tools(products)
            tool_descriptions = "\n".join(
                f"- {t.name}: {t.description}" for t in tools
            )
            system_prompt = _COMPETITOR_SYSTEM_PROMPT.format(
                tool_descriptions=tool_descriptions,
            )

            analysis_question = (
                f"请分析以下 {len(products)} 个商品的竞品格局。\n"
                f"商品数量：{len(products)}，跨越多个品牌。\n"
                f"请逐步分析，每次调用工具后思考结果，再决定下一步。"
            )

            raw_output = await self._run_analysis_loop(
                products=products,
                system_prompt=system_prompt,
                analysis_question=analysis_question,
                max_turns=15,
            )

            result = self._parse_json_output(raw_output)
            result["analysis_type"] = "competitor_benchmark"
            result["generated_at"] = datetime.now().isoformat()
            result["llm_driven"] = True
            logger.info("[CompetitorAnalyst] LLM 驱动竞品分析完成")

            # 如果 LLM 返回了合法 JSON，用其覆盖兜底数据（否则保留兜底）
            if result.get("market_share_distribution") or result.get("head_to_head"):
                state.set("result", result)
                state.set("competitor_analysis_result", result)
            state.set_meta("llm_driven", True)
            state.add_event("competitor_analyst_success")

        except Exception as e:
            logger.error(f"[CompetitorAnalyst] Error: {e}")
            state.set("error", str(e))
            state.set_meta("analysis_completed", False)
            state.add_event(f"competitor_analyst_error: {e}")

        return state

    # ════════════════════════════════════════════════════════════════
    # 工具定义
    # ════════════════════════════════════════════════════════════════

    def _build_analysis_tools(self, products: List[Dict]) -> List:
        """将竞品分析维度暴露为 LLM 可调用的工具"""

        @tool
        def analyze_brand_market_share() -> dict:
            """分析品牌市场份额：各品牌的商品数/总销量/平均价格/平均BSR/平均评分/BSR趋势"""
            brand_data = self._aggregate_brands(products)
            total_sales = sum(b["total_sales"] for b in brand_data.values())
            brand_list = []
            for brand, b in brand_data.items():
                share = b["total_sales"] / total_sales if total_sales > 0 else 0
                brand_list.append({
                    "brand": brand,
                    "market_share_percent": round(share * 100, 1),
                    "product_count": b["count"],
                    "total_monthly_sales": b["total_sales"],
                    "avg_price": round(b["_price_sum"] / b["count"], 2) if b["count"] else 0,
                    "avg_bsr": round(b["_bsr_sum"] / b["_bsr_count"]) if b["_bsr_count"] else None,
                    "avg_rating": round(b["_rating_sum"] / b["_rating_count"], 2) if b["_rating_count"] else None,
                    "total_reviews": b["total_reviews"],
                    "bsr_trends": b["bsr_trends"],
                })
            brand_list.sort(key=lambda x: x["total_monthly_sales"], reverse=True)
            top3_share = sum(b["market_share_percent"] for b in brand_list[:3])
            return {
                "total_brands": len(brand_list),
                "total_products": len(products),
                "top_3_market_share_pct": round(top3_share, 1),
                "brands": brand_list,
            }

        @tool
        def analyze_head_to_head() -> dict:
            """头部竞品深度对比：BSR 最好的 3 个产品的逐项对比（价格/评分/评论/定价策略/规格/图片/变体）"""
            return self._analyze_head_to_head(products)

        @tool
        def analyze_listing_quality() -> dict:
            """对比各商品的 listing 完整度：五点/图片/规格/描述/A+ 评分，平均分和分布"""
            return self._compare_listing_quality(products)

        @tool
        def analyze_competitive_landscape() -> dict:
            """分析竞争格局分层：第一/二/三梯队、市场领导者、进入壁垒、推荐策略"""
            brand_data = self._aggregate_brands(products)
            total_sales = sum(b["total_sales"] for b in brand_data.values())
            brand_list = []
            for brand, b in brand_data.items():
                share = b["total_sales"] / total_sales if total_sales > 0 else 0
                brand_list.append({
                    "brand": brand, "market_share": share, "product_count": b["count"],
                    "avg_rating": round(b["_rating_sum"] / b["_rating_count"], 2) if b["_rating_count"] else None,
                    "total_reviews": b["total_reviews"], "bsr_trends": b["bsr_trends"],
                })
            brand_list.sort(key=lambda x: x["market_share"], reverse=True)
            return self._analyze_landscape(brand_list)

        @tool
        def analyze_differentiation_opportunities() -> dict:
            """识别差异化机会：价格带空白、上升中的小品牌、评分低洼竞品"""
            brand_data = self._aggregate_brands(products)
            total_sales = sum(b["total_sales"] for b in brand_data.values())
            brand_list = []
            for brand, b in brand_data.items():
                share = b["total_sales"] / total_sales if total_sales > 0 else 0
                brand_list.append({
                    "brand": brand, "market_share": share, "product_count": b["count"],
                    "avg_price": round(b["_price_sum"] / b["count"], 2) if b["count"] else 0,
                    "avg_rating": round(b["_rating_sum"] / b["_rating_count"], 2) if b["_rating_count"] else None,
                    "total_reviews": b["total_reviews"], "bsr_trends": b["bsr_trends"],
                    "min_price": b["min_price"], "max_price": b["max_price"],
                })
            brand_list.sort(key=lambda x: x["market_share"], reverse=True)
            return self._identify_differentiation(brand_list, products)

        return [
            analyze_brand_market_share, analyze_head_to_head,
            analyze_listing_quality, analyze_competitive_landscape,
            analyze_differentiation_opportunities,
        ]

    # ── 定价策略识别 ──────────────────────────────────────────────────

    @staticmethod
    def _classify_price_pattern(price_history: List) -> str:
        """从 price_history CSV 判断定价策略"""
        if not price_history or len(price_history) < 3:
            return "数据不足"

        vals = [v for _, v in price_history[-90:]] if len(price_history) > 90 else [v for _, v in price_history]
        if not vals or len(vals) < 3:
            return "数据不足"

        first = vals[0]
        last = vals[-1]
        if first <= 0:
            return "数据异常"

        total_change = (last - first) / first * 100
        max_val = max(vals)
        min_val = min(vals)
        volatility = (max_val - min_val) / first * 100 if first > 0 else 0

        if volatility < 5:
            return "稳定"
        if total_change < -5:
            return "持续降价"
        if total_change > 5:
            return "持续涨价"
        if volatility > 15:
            return "频繁波动"
        return "小幅调整"

    # ── listing 质量评估 ──────────────────────────────────────────────

    def _compare_listing_quality(self, products: List[Dict]) -> Dict[str, Any]:
        """对比各商品的 listing 完整度"""
        scored = []
        for p in products:
            score = 0
            bullets = p.get("feature_bullets") or []
            images = p.get("images") or []
            specs = p.get("specifications") or {}
            desc = p.get("description") or ""
            aplus = p.get("aplus_content")

            if len(bullets) >= 5:
                score += 2
            elif len(bullets) >= 3:
                score += 1

            if len(images) >= 7:
                score += 2
            elif len(images) >= 3:
                score += 1

            if len(specs) >= 10:
                score += 2
            elif len(specs) >= 5:
                score += 1

            if aplus:
                score += 2

            if len(desc) > 500:
                score += 2
            elif len(desc) > 100:
                score += 1

            scored.append({
                "asin": p.get("asin", ""),
                "title": (p.get("title") or "")[:60],
                "listing_score": score,
                "max_score": 10,
                "bullet_count": len(bullets),
                "image_count": len(images),
                "spec_count": len(specs),
                "has_aplus": bool(aplus),
                "has_description": len(desc) > 0,
            })

        scored.sort(key=lambda x: x["listing_score"], reverse=True)
        avg_score = round(sum(s["listing_score"] for s in scored) / len(scored), 1) if scored else 0

        return {
            "average_listing_score": avg_score,
            "max_score": 10,
            "distribution": {
                "excellent": sum(1 for s in scored if s["listing_score"] >= 8),
                "good": sum(1 for s in scored if 5 <= s["listing_score"] < 8),
                "weak": sum(1 for s in scored if s["listing_score"] < 5),
            },
            "rankings": scored[:10],
        }

    # ── 头部竞品深挖 ──────────────────────────────────────────────────

    def _analyze_head_to_head(self, products: List[Dict]) -> Dict[str, Any]:
        """BSR 最好的 3 个产品做逐项对比"""
        def _to_num(v):
            """安全转数字，非数字返回 999999"""
            if v is None:
                return 999999
            try:
                return float(v)
            except (ValueError, TypeError):
                return 999999

        sorted_prods = sorted(products, key=lambda p: _to_num(p.get("current_bsr")))
        top3 = sorted_prods[:3]

        def _safe_price(p):
            v = p.get("current_price")
            if v is None:
                return None
            try:
                return float(v)
            except (ValueError, TypeError):
                return None

        top3_prices = [_safe_price(p) for p in top3]
        top3_prices = [p for p in top3_prices if p is not None]

        def _safe_rating(p):
            v = p.get("rating")
            if v is None:
                return 0
            try:
                return float(v)
            except (ValueError, TypeError):
                return 0

        def _extract_key_specs(specs: Dict) -> Dict:
            """提取关键规格"""
            key_fields = [
                "Brand", "Color", "Size", "Material", "Weight",
                "Product Dimensions", "Item Weight", "Batteries",
                "Power Source", "Style", "Special Feature",
            ]
            return {k: specs[k] for k in key_fields if k in specs}

        return {
            "top_3_products": [
                {
                    "asin": p.get("asin"),
                    "title": (p.get("title") or "")[:80],
                    "brand": p.get("brand", "Unknown"),
                    "price": p.get("current_price"),
                    "list_price": p.get("list_price"),
                    "is_prime": p.get("is_prime", False),
                    "is_fba": p.get("fulfillment") == "FBA",
                    "is_in_stock": p.get("is_in_stock"),
                    "price_pattern": self._classify_price_pattern(p.get("price_history") or []),
                    "bsr_trajectory": p.get("bsr_trend", "unknown"),
                    "rating": p.get("rating"),
                    "review_count": p.get("review_count", 0),
                    "rating_breakdown": p.get("rating_breakdown", {}),
                    "monthly_sold": p.get("monthly_sold", 0),
                    "seller_count": p.get("seller_count", 0),
                    "feature_bullets": p.get("feature_bullets", [])[:5],
                    "spec_highlights": _extract_key_specs(p.get("specifications", {})),
                    "variation_count": len(p.get("variations", [])),
                    "image_count": len(p.get("images", [])),
                    "has_description": bool(p.get("description", "")),
                    "sponsored": len(p.get("sponsored_products", [])) > 0,
                    "data_sources": p.get("data_sources", []),
                }
                for p in top3
            ],
            "cross_comparison": {
                "price_range": {
                    "min": min(top3_prices) if top3_prices else None,
                    "max": max(top3_prices) if top3_prices else None,
                },
                "all_prime": all(p.get("is_prime") for p in top3),
                "all_fba": all(p.get("fulfillment") == "FBA" for p in top3),
                "avg_rating": round(
                    sum(_safe_rating(p) for p in top3) /
                    max(1, sum(1 for p in top3 if _safe_rating(p) > 0)),
                    2,
                ),
                "total_monthly_sold": sum(p.get("monthly_sold", 0) for p in top3),
                "price_patterns": list(set(
                    self._classify_price_pattern(p.get("price_history") or []) for p in top3
                )),
            },
        }

    # ── 从 amazon_products 本地表加载 ──

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

        price_bands = [
            ("<$20", 0, 20), ("$20-50", 20, 50), ("$50-100", 50, 100),
            ("$100-200", 100, 200), ("$200+", 200, float("inf")),
        ]
        for label, lo, hi in price_bands:
            def _safe_price_band(p):
                v = p.get("current_price")
                if v is None:
                    return None
                try:
                    return float(v)
                except (ValueError, TypeError):
                    return None

            in_band = [p for p in products if _safe_price_band(p) is not None and lo <= _safe_price_band(p) < hi]
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

        for b in brand_list:
            improving = b["bsr_trends"].get("improving", 0)
            total_trends = sum(b["bsr_trends"].values())
            if total_trends > 0 and improving / total_trends > 0.5 and b["market_share"] < 0.1:
                opportunities.append({
                    "type": "上升中的小品牌",
                    "detail": f"{b['brand']} 超过半数商品 BSR 改善中，份额仅 {b['market_share']*100:.1f}%，值得关注或对标",
                    "potential": "高",
                })

        for b in brand_list:
            if b["avg_rating"] and b["avg_rating"] < 3.8 and b["total_reviews"] > 500:
                opportunities.append({
                    "type": "评分低洼竞品",
                    "detail": f"{b['brand']} 评分仅 {b['avg_rating']}（{b['total_reviews']} 条评论），用户满意度低，可切入",
                    "potential": "高",
                })

        return opportunities

    # ── 从 amazon_products 本地表加载（完整 180+ 字段 + 33 推导域 + API fallback） ──

    async def _load_from_local_db(
        self, asins: List[str] = None, category: str = None, domain: str = "US",
    ) -> List[Dict]:
        """从 amazon_products 表加载完整商品数据。
        DB 没有 → 自动触发 ETL Pipeline 冷启动采集。"""
        products = await load_products_from_db(
            asins=asins, category=category, domain=domain, with_derived=True,
        )
        n = len(products)
        source = f"{len(asins)} ASIN" if asins else f"类目={category}"

        if products:
            logger.info(
                f"[CompetitorAnalyst] 从本地表加载 {n} 个商品（{source}），"
                f"每商品 {len(products[0])} 个字段/推导域"
            )
            return products

        # ★ DB 无数据 → 走 DataProvider 冷启动
        logger.info(f"[CompetitorAnalyst] 本地表未找到商品（{source}），触发冷启动...")
        if asins:
            from backend.aqueduct.data_provider import DataProvider
            provider = DataProvider()
            for a in asins[:10]:
                try:
                    await provider.get_product_blocking(a, domain)
                except Exception:
                    pass
            # 冷启动后重新查
            products = await load_products_from_db(
                asins=asins, domain=domain, with_derived=True,
            )
            if products:
                logger.info(f"[CompetitorAnalyst] 冷启动后加载 {len(products)} 个商品")
                return products

        return products

    async def execute(self, input_data: AgentInput) -> AgentOutput:
        return await super().execute(input_data)