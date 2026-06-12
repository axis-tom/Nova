"""
市场机会评估 Agent - Amazon 监控场景
对应文章第5步：市场机会综合判断

职责：
1. 综合关键词、商品、评论、流量数据
2. 计算每个商品/品类的机会评分（含 Keepa 历史趋势维度）
3. 生成选品建议和市场报告
4. 生成预警通知（价格/评分/竞品变动/BSR异动）

评分维度升级（接入 Keepa 后）：
  - BSR 趋势（improving/stable/declining）→ 判断销量走势
  - 价格稳定性（90天价格波动率）→ 判断价格风险
  - 月销量估算（monthlySold）→ 市场规模
  - 卖家数量（seller_count）→ 竞争激烈程度
"""

import json as _json
from typing import Any, Dict, List, Optional
from datetime import datetime

from backend.common.core.agent import Agent
from backend.common.core.state import State
from backend.utils.logger import logger
from backend.business.ecommerce.product_selection.tools.product_loader import load_products_from_db
from backend.aqueduct.scoring import (
    score_single_product,
    SCORE_WEIGHTS,
)




class OpportunityJudgeAgent(Agent):
    """
    市场机会评估 Agent
    综合评估选品机会，生成市场报告和预警
    """

    name = "opportunity_judge"
    description = "Amazon 市场机会评估 Agent，综合评分并生成选品建议"

    async def run(self, state: State) -> State:
        """
        执行市场机会评估

        输入（从 state 读取）：
          - collected_products: List[dict]
          - review_insights: List[dict]
          - sentiment_summary: dict
          - customer_needs: List[str]
          - traffic_insights: dict
          - competitor_comparison: dict
          - price_alerts: List[dict]
          - keyword_groups: dict

        输出（写入 state）：
          - opportunities: List[dict] 机会列表（含评分）
          - market_report: str Markdown 格式市场报告
          - top_picks: List[dict] Top 10 选品建议
          - alerts: List[dict] 预警通知
          - alert_summary: dict 预警摘要
        """
        state.add_event("opportunity_judge_start")
        logger.info("[OpportunityJudge] Starting opportunity assessment")

        try:
            # 读取所有上游数据
            products: List[Dict] = state.get("collected_products", [])

            # ── 优先从 amazon_products 本地表读取 ──
            if not products:
                asins = state.get("asins") or []
                category = state.get("category") or state.get("market_category") or state.get("category_name")
                try:
                    products = await self._load_from_local_db(
                        asins=asins, category=category, domain=state.get("domain", "US"),
                    )
                except Exception as e:
                    logger.warning(f"[OpportunityJudge] 本地表查询失败: {e}")

            # 字段归一化：Keepa 用 current_price/current_bsr，内部分析用 price/bsr_rank
            for p in products:
                if "current_price" in p and "price" not in p:
                    p["price"] = p["current_price"]
                if "current_bsr" in p and "bsr_rank" not in p:
                    p["bsr_rank"] = p["current_bsr"]

            review_insights: List[Dict] = state.get("review_insights", [])
            sentiment_summary: Dict = state.get("sentiment_summary", {})
            customer_needs: List[str] = state.get("customer_needs", [])
            traffic_insights: Dict = state.get("traffic_insights", {})
            competitor_comparison: Dict = state.get("competitor_comparison", {})
            price_alerts: List[Dict] = state.get("price_alerts", [])
            keyword_groups: Dict = state.get("keyword_groups", {})
            min_score: int = state.get("min_opportunity_score", 60)
            top_n: int = state.get("output_top_n", 10)

            # 构建评论洞察索引
            review_map: Dict[str, Dict] = {r["asin"]: r for r in review_insights}

            # 1. 计算每个商品的机会评分
            scored_products = []
            for product in products:
                score_detail = self._score_product(
                    product, review_map, sentiment_summary, competitor_comparison
                )
                if score_detail["total_score"] >= min_score:
                    scored_products.append({**product, **score_detail})

            # 按评分排序
            scored_products.sort(key=lambda p: p["total_score"], reverse=True)

            # 2. Top N 选品
            top_picks = scored_products[:top_n]

            # 3. 生成机会列表
            opportunities = self._build_opportunities(
                scored_products, competitor_comparison, customer_needs
            )

            # 4. 生成预警通知
            alerts = self._build_alerts(price_alerts, review_insights, state)
            alert_summary = self._build_alert_summary(alerts)

            # 5. 生成 Markdown 市场报告
            market_report = self._generate_market_report(
                products, top_picks, opportunities, sentiment_summary,
                traffic_insights, customer_needs, alerts
            )

            # LLM 增强：对 Top Picks 做第二意见审核
            ai_result = await self._llm_review_picks(top_picks, sentiment_summary, customer_needs)
            if ai_result:
                state.set_meta("llm_enhanced", True)
                for pick in top_picks:
                    asin = pick.get("asin")
                    if asin and asin in ai_result:
                        pick["ai_comment"] = ai_result[asin]
                logger.info("[OpportunityJudge] LLM 第二意见已注入 top_picks")
            else:
                state.set_meta("llm_enhanced", False)

            # 写入结果
            state.set("opportunities", opportunities)
            state.set("market_report", market_report)
            state.set("top_picks", top_picks)
            state.set("alerts", alerts)
            state.set("alert_summary", alert_summary)
            state.set("result", market_report)  # 供前端直接渲染
            state.set_meta("opportunities_found", len(opportunities))
            state.set_meta("alerts_generated", len(alerts))

            logger.info(
                f"[OpportunityJudge] Found {len(opportunities)} opportunities, "
                f"{len(top_picks)} top picks, {len(alerts)} alerts"
            )
            state.add_event(
                f"opportunity_judge_success: {len(opportunities)} opportunities, "
                f"{len(alerts)} alerts"
            )

        except Exception as e:
            logger.error(f"[OpportunityJudge] Error: {e}")
            state.set("error", str(e))
            state.set("opportunities", [])
            state.set("market_report", f"# 市场报告生成失败\n\n错误：{e}")
            state.set("top_picks", [])
            state.set("alerts", [])
            state.set("alert_summary", {})
            state.add_event(f"opportunity_judge_error: {e}")

        return state

    # ── LLM 增强：第二意见 ──

    async def _llm_review_picks(
        self,
        top_picks: List[Dict],
        sentiment_summary: Dict,
        customer_needs: List[str],
    ) -> Dict[str, str]:
        """让 LLM 审核 Top Picks，给出每个商品的简短评语。返回 {asin: comment}，失败返回空 dict"""
        if not top_picks:
            return {}

        picks_data = [
            {
                "asin": p.get("asin"),
                "title": (p.get("title") or "")[:50],
                "price": p.get("current_price") or p.get("price"),
                "rating": p.get("rating"),
                "review_count": p.get("review_count"),
                "monthly_sold": p.get("monthly_sold"),
                "bsr_trend": p.get("bsr_trend"),
                "total_score": p.get("total_score"),
                "score_grade": p.get("score_grade"),
                "score_highlights": p.get("score_highlights", []),
            }
            for p in top_picks[:5]
        ]

        prompt = _json.dumps({
            "top_picks": picks_data,
            "market_sentiment": sentiment_summary.get("market_sentiment"),
            "customer_needs": customer_needs[:5],
        }, ensure_ascii=False, indent=2)

        system = (
            "You are an Amazon product selection expert reviewing algorithm-scored picks.\n"
            "For each ASIN, provide a brief Chinese comment (1-2 sentences) on whether "
            "the score might be overestimated or underestimated, and why.\n"
            "Return JSON: {\"ASIN1\": \"评语\", \"ASIN2\": \"评语\", ...}\n"
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
                return {k: str(v) for k, v in result.items()}
        except (_json.JSONDecodeError, ValueError):
            logger.warning("[OpportunityJudge] LLM returned invalid JSON, skipping")
        return {}

    def _score_product(
        self,
        product: Dict,
        review_map: Dict[str, Dict],
        sentiment_summary: Dict,
        competitor_comparison: Dict,
    ) -> Dict[str, Any]:
        """
        计算单个商品的机会评分（0-100）

        复用 scoring.py 的 8 维评分逻辑，覆盖 sentiment 维度（使用 Agent 独有的评论情感数据）。
        """
        # 基础 8 维评分（sentiment=60 默认值）
        base = score_single_product(product)
        scores = base["score_detail"]
        asin = product.get("asin", "")

        # ── 8. 情感评分（Agent 特有：从 review_insights 取真实情感） ──
        review_insight = review_map.get(asin)
        if review_insight:
            positive_pct = review_insight.get("sentiment_positive_pct", 0)
            scores["sentiment"] = min(100, positive_pct)
        else:
            scores["sentiment"] = sentiment_summary.get("avg_positive_pct", 60)

        # ── 加权总分 ──
        total = sum(scores[k] * SCORE_WEIGHTS[k] for k in SCORE_WEIGHTS)

        return {
            "total_score": round(total, 1),
            "score_detail": scores,
            "score_highlights": base["highlights"],
            "score_grade": base["score_grade"],
        }

    def _build_opportunities(
        self,
        scored_products: List[Dict],
        competitor_comparison: Dict,
        customer_needs: List[str],
    ) -> List[Dict]:
        """构建机会列表"""
        opportunities = []
        for i, product in enumerate(scored_products[:20]):
            cat = product.get("category", "")
            cat_data = competitor_comparison.get(cat, {})

            opportunities.append({
                "rank": i + 1,
                "asin": product.get("asin"),
                "title": product.get("title", "")[:80],
                "category": cat,
                "price": product.get("current_price") or product.get("price"),
                "rating": product.get("rating"),
                "review_count": product.get("review_count"),
                "bsr_rank": product.get("current_bsr") or product.get("bsr_rank"),
                "total_score": product.get("total_score"),
                "score_grade": product.get("score_grade"),
                "competition_level": cat_data.get("competition_level", "未知"),
                "url": product.get("url"),
                "opportunity_reason": self._generate_opportunity_reason(product, cat_data),
            })

        return opportunities

    def _generate_opportunity_reason(self, product: Dict, cat_data: Dict) -> str:
        """生成机会说明"""
        reasons = []
        score = product.get("total_score", 0)
        bsr = product.get("current_bsr") or product.get("bsr_rank")
        rating = product.get("rating", 0)
        reviews = product.get("review_count", 0)

        if bsr and bsr <= 1000:
            reasons.append(f"BSR #{bsr}（市场热销）")
        if rating >= 4.5:
            reasons.append(f"高评分 {rating}/5.0")
        if reviews >= 1000:
            reasons.append(f"市场验证充分（{reviews:,} 评论）")
        if cat_data.get("competition_level") == "低":
            reasons.append("竞争程度低")

        if not reasons:
            reasons.append(f"综合评分 {score:.0f}/100")

        return "；".join(reasons)

    def _build_alerts(
        self,
        price_alerts: List[Dict],
        review_insights: List[Dict],
        state: State,
    ) -> List[Dict]:
        """构建预警通知列表"""
        alerts = []

        # 价格预警
        for alert in price_alerts:
            alerts.append({
                "type": "price_alert",
                "severity": "medium",
                "asin": alert.get("asin"),
                "title": alert.get("title"),
                "message": alert.get("message"),
                "data": {
                    "current_price": alert.get("current_price"),
                    "avg_market_price": alert.get("avg_market_price"),
                    "deviation_pct": alert.get("deviation_pct"),
                },
                "created_at": datetime.now().isoformat(),
            })

        # 低评分预警
        for insight in review_insights:
            if insight.get("rating", 5) < 3.5:
                alerts.append({
                    "type": "rating_alert",
                    "severity": "high",
                    "asin": insight.get("asin"),
                    "title": insight.get("title"),
                    "message": (
                        f"商品评分偏低：{insight.get('rating')}/5.0，"
                        f"负面评论占比 {insight.get('sentiment_negative_pct', 0):.1f}%"
                    ),
                    "data": {
                        "rating": insight.get("rating"),
                        "negative_pct": insight.get("sentiment_negative_pct"),
                        "complaints": insight.get("common_complaints", [])[:3],
                    },
                    "created_at": datetime.now().isoformat(),
                })

        return alerts

    def _build_alert_summary(self, alerts: List[Dict]) -> Dict[str, Any]:
        """构建预警摘要"""
        if not alerts:
            return {"total": 0, "message": "无预警"}

        by_type: Dict[str, int] = {}
        by_severity: Dict[str, int] = {}
        for alert in alerts:
            t = alert.get("type", "unknown")
            s = alert.get("severity", "low")
            by_type[t] = by_type.get(t, 0) + 1
            by_severity[s] = by_severity.get(s, 0) + 1

        return {
            "total": len(alerts),
            "by_type": by_type,
            "by_severity": by_severity,
            "high_severity_count": by_severity.get("high", 0),
            "generated_at": datetime.now().isoformat(),
        }

    def _generate_market_report(
        self,
        products: List[Dict],
        top_picks: List[Dict],
        opportunities: List[Dict],
        sentiment_summary: Dict,
        traffic_insights: Dict,
        customer_needs: List[str],
        alerts: List[Dict],
    ) -> str:
        """生成 Markdown 格式市场报告"""
        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        lines = [
            "# 📊 Amazon 市场监控报告",
            f"\n> 生成时间：{now}",
            "\n---",
        ]

        # 市场概况
        lines.append("\n## 一、市场概况")
        summary = traffic_insights.get("market_summary", "")
        if summary:
            lines.append(f"\n{summary}")

        total = len(products)
        avg_rating = traffic_insights.get("avg_market_rating", 0)
        high_potential = traffic_insights.get("high_potential_count", 0)
        lines.append(f"\n| 指标 | 数值 |")
        lines.append(f"|------|------|")
        lines.append(f"| 采集商品总数 | {total} |")
        lines.append(f"| 市场平均评分 | {avg_rating}/5.0 |")
        lines.append(f"| 高潜力商品数 | {high_potential} |")
        lines.append(f"| 市场竞争程度 | {traffic_insights.get('competition_level', '未知')} |")

        # 客户需求洞察
        if customer_needs:
            lines.append("\n## 二、客户需求洞察")
            lines.append(f"\n基于评论分析，客户核心需求：")
            for need in customer_needs[:5]:
                lines.append(f"- {need}")

        if sentiment_summary:
            lines.append(f"\n**市场情感：** {sentiment_summary.get('market_sentiment', '未知')}")
            lines.append(f"（正面评价占比 {sentiment_summary.get('avg_positive_pct', 0):.1f}%）")

            praise = sentiment_summary.get("top_praise_keywords", [])
            complaints = sentiment_summary.get("top_complaint_keywords", [])
            if praise:
                lines.append(f"\n🟢 **常见好评：** {', '.join(praise)}")
            if complaints:
                lines.append(f"\n🔴 **常见差评：** {', '.join(complaints)}")

        # Top 选品建议
        if top_picks:
            lines.append("\n## 三、Top 选品建议")
            lines.append(f"\n| 排名 | ASIN | 商品 | 价格 | 评分 | BSR | 综合评分 |")
            lines.append(f"|------|------|------|------|------|-----|---------|")
            for pick in top_picks[:10]:
                title = (pick.get("title") or "")[:30]
                price_val = pick.get("current_price") or pick.get("price")
                price = f"${price_val:.2f}" if price_val else "N/A"
                rating = pick.get("rating", "N/A")
                bsr_val = pick.get("current_bsr") or pick.get("bsr_rank")
                bsr = f"#{bsr_val}" if bsr_val else "N/A"
                score = f"{pick.get('total_score', 0):.0f} ({pick.get('score_grade', 'N/A')})"
                lines.append(
                    f"| {pick.get('rank', '')} | {pick.get('asin', '')} | {title} | "
                    f"{price} | {rating} | {bsr} | {score} |"
                )

        # 预警通知
        if alerts:
            lines.append("\n## 四、预警通知")
            high_alerts = [a for a in alerts if a.get("severity") == "high"]
            medium_alerts = [a for a in alerts if a.get("severity") == "medium"]

            if high_alerts:
                lines.append(f"\n### 🔴 高优先级预警 ({len(high_alerts)})")
                for alert in high_alerts[:5]:
                    lines.append(f"- **{alert.get('asin')}**: {alert.get('message')}")

            if medium_alerts:
                lines.append(f"\n### 🟡 中优先级预警 ({len(medium_alerts)})")
                for alert in medium_alerts[:5]:
                    lines.append(f"- **{alert.get('asin')}**: {alert.get('message')}")
        else:
            lines.append("\n## 四、预警通知")
            lines.append("\n✅ 当前无预警")

        lines.append("\n---")
        lines.append(f"\n*本报告由 Nova AI 智能体自动生成 | {now}*")

        return "\n".join(lines)

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
                f"[OpportunityJudge] 从本地表加载 {n} 个商品（{source}），"
                f"每商品 {len(products[0])} 个字段/推导域"
            )
            return products

        # ★ DB 无数据 → 走 DataProvider 冷启动
        logger.info(f"[OpportunityJudge] 本地表未找到商品（{source}），触发冷启动...")
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
            for p in products:
                if p.get("current_price") is not None:
                    p["price"] = p["current_price"]
                if p.get("current_bsr") is not None:
                    p["bsr_rank"] = p["current_bsr"]
            if products:
                logger.info(f"[OpportunityJudge] 冷启动后加载 {len(products)} 个商品")

        return products
