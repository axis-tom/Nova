"""
简报生成 Agent - 电商选品分析场景

职责：
1. 读取上游 Agent 写入 state 的所有分析结果
2. 生成 Markdown 格式的选品简报
3. 汇总市场/竞品/评论/盈利等多维度分析

数据源（全部从 state 读取）：
- collected_products        → product_collector
- market_analysis_result    → market_analyst (market_trends)
- profitability_result      → market_analyst (roi_analysis)
- competitor_analysis_result → competitor_analyst
- review_insights / sentiment_summary / customer_needs → review_analyzer
- traffic_insights          → traffic_analyzer
"""

from datetime import datetime
from typing import Dict, Any, List

from backend.common.core.agent import Agent, AgentInput, AgentOutput
from backend.common.core.state import State


class BriefingGeneratorAgent(Agent):
    """简报生成 Agent — 汇总所有分析结果，输出 Markdown 选品简报"""

    name = "briefing_generator"
    description = "电商选品简报生成 Agent，汇总上游分析输出 Markdown 报告"

    def run(self, state: State) -> State:
        state.add_event("briefing_generator_start")

        try:
            market = state.get("market_analysis_result") or {}
            competitor = state.get("competitor_analysis_result") or {}
            profitability = state.get("profitability_result") or {}
            sentiment = state.get("sentiment_summary") or {}
            review_insights = state.get("review_insights") or []
            customer_needs = state.get("customer_needs") or []
            traffic = state.get("traffic_insights") or {}
            products = state.get("collected_products") or []

            md = self._generate_markdown(
                market, competitor, profitability,
                sentiment, review_insights, customer_needs,
                traffic, products,
            )

            briefing = {
                "title": "电商选品分析简报",
                "generated_at": datetime.now().isoformat(),
                "sections_available": {
                    "market_analysis": bool(market),
                    "competitor_analysis": bool(competitor),
                    "profitability": bool(profitability),
                    "review_analysis": bool(sentiment),
                    "traffic_analysis": bool(traffic),
                },
                "markdown": md,
            }

            state.set("briefing", briefing)
            state.set("result", md)
            state.add_event("briefing_generator_success")

        except Exception as e:
            state.set("error", f"简报生成失败: {e}")
            state.add_event(f"briefing_generator_error: {e}")

        return state

    # ── Markdown 生成 ──

    def _generate_markdown(
        self,
        market: Dict, competitor: Dict, profitability: Dict,
        sentiment: Dict, review_insights: List, customer_needs: List,
        traffic: Dict, products: List,
    ) -> str:
        lines = [
            "# 电商选品分析简报",
            f"\n> 生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            f"> 分析商品数：{len(products)}",
            "\n---",
        ]

        if market:
            lines.extend(self._section_market(market))
        if competitor:
            lines.extend(self._section_competitor(competitor))
        if sentiment:
            lines.extend(self._section_review(sentiment, review_insights, customer_needs))
        if profitability:
            lines.extend(self._section_profitability(profitability))
        if traffic:
            lines.extend(self._section_traffic(traffic))

        lines.append("\n---\n*本简报由 Nova AI 智能体自动生成*")
        return "\n".join(lines)

    def _section_market(self, market: Dict) -> List[str]:
        lines = ["\n## 一、市场概况"]
        s = market.get("summary", {})
        if s:
            lines.append(f"\n| 指标 | 数值 |")
            lines.append(f"|------|------|")
            lines.append(f"| 分析商品数 | {s.get('total_products_analyzed', '-')} |")
            lines.append(f"| 平均价格 | ${s.get('average_price', '-')} |")
            lines.append(f"| 月总销量 | {s.get('total_monthly_sales', '-'):,} |")
            lines.append(f"| 平均评分 | {s.get('average_rating', '-')} |")
            lines.append(f"| 平均 BSR | {s.get('average_bsr', '-')} |")
            lines.append(f"| 市场趋势 | {s.get('market_trend', '-')} |")

        brands = market.get("brand_distribution", {})
        if brands:
            lines.append("\n### 品牌分布 (Top 5)")
            lines.append("| 品牌 | 商品数 | 月销量 | 均价 |")
            lines.append("|------|--------|--------|------|")
            for brand, info in list(brands.items())[:5]:
                lines.append(
                    f"| {brand} | {info.get('count', 0)} | "
                    f"{info.get('total_sales', 0):,} | "
                    f"${info.get('avg_price', 0)} |"
                )

        opps = market.get("opportunities", [])
        if opps:
            lines.append("\n### 市场机会")
            for o in opps[:5]:
                strength = o.get("strength", "")
                lines.append(f"- **[{strength}]** {o.get('opportunity', '')}: {o.get('evidence', '')}")

        risks = market.get("risks", [])
        if risks:
            lines.append("\n### 风险提示")
            for r in risks[:5]:
                severity = r.get("severity", "")
                lines.append(f"- **[{severity}]** {r.get('risk_type', '')}: {r.get('detail', '')}")

        return lines

    def _section_competitor(self, competitor: Dict) -> List[str]:
        lines = ["\n---\n## 二、竞品分析"]
        s = competitor.get("summary", {})
        if s:
            lines.append(f"\n- 分析品牌数：{s.get('total_brands_analyzed', '-')}")
            lines.append(f"- 市场集中度：{s.get('market_concentration', '-')}")
            lines.append(f"- Top 3 份额：{s.get('top_3_market_share', 0) * 100:.1f}%")

        share = competitor.get("market_share_distribution", [])
        if share:
            lines.append("\n### 市场份额")
            lines.append("| 排名 | 品牌 | 份额 | 商品数 | 月销量 | 均价 |")
            lines.append("|------|------|------|--------|--------|------|")
            for b in share[:8]:
                lines.append(
                    f"| {b.get('rank', '')} | {b.get('brand', '')} | "
                    f"{b.get('market_share_percent', '')} | {b.get('product_count', 0)} | "
                    f"{b.get('total_monthly_sales', 0):,} | ${b.get('avg_price', 0)} |"
                )

        diff = competitor.get("differentiation_opportunities", [])
        if diff:
            lines.append("\n### 差异化机会")
            for d in diff[:5]:
                potential = d.get("potential", "")
                lines.append(f"- **[{potential}]** {d.get('type', '')}: {d.get('detail', '')}")

        landscape = competitor.get("competitive_landscape", {})
        if landscape:
            lines.append(f"\n### 竞争格局")
            lines.append(f"- 进入壁垒：{landscape.get('entry_barrier', '-')}")
            lines.append(f"- 建议策略：{landscape.get('recommended_strategy', '-')}")

        return lines

    def _section_review(self, sentiment: Dict, insights: List, needs: List) -> List[str]:
        lines = ["\n---\n## 三、评论/评分洞察"]
        if sentiment:
            lines.append(f"\n- 平均评分：{sentiment.get('avg_rating', '-')}")
            lines.append(f"- 正面情感：{sentiment.get('avg_positive_pct', 0)}%")
            lines.append(f"- 市场情感：{sentiment.get('market_sentiment', '-')}")

            barrier = sentiment.get("review_barrier_distribution", {})
            if barrier:
                parts = [f"{k}:{v}" for k, v in barrier.items() if v > 0]
                lines.append(f"- 评论壁垒分布：{', '.join(parts)}")

            praise = sentiment.get("top_praise_keywords", [])
            if praise:
                lines.append("\n**Top 好评点：**")
                for p in praise[:5]:
                    lines.append(f"- {p}")

            complaints = sentiment.get("top_complaint_keywords", [])
            if complaints:
                lines.append("\n**Top 差评点：**")
                for c in complaints[:5]:
                    lines.append(f"- {c}")

        if needs:
            lines.append("\n### 客户需求推断")
            for n in needs[:5]:
                lines.append(f"- {n}")

        return lines

    def _section_profitability(self, profitability: Dict) -> List[str]:
        lines = ["\n---\n## 四、盈利评估"]
        s = profitability.get("summary", {})
        if s:
            lines.append(f"\n| 指标 | 数值 |")
            lines.append(f"|------|------|")
            lines.append(f"| 评估商品数 | {s.get('total_products_evaluated', '-')} |")
            lines.append(f"| 月总收入 | ${s.get('total_monthly_revenue', 0):,.0f} |")
            lines.append(f"| 估算月利润 | ${s.get('estimated_monthly_profit', 0):,.0f} |")
            lines.append(f"| 利润率假设 | {s.get('default_profit_margin', 0) * 100:.0f}% |")

        picks = profitability.get("top_picks", [])
        if picks:
            lines.append("\n### Top 推荐商品")
            lines.append("| 排名 | ASIN | 标题 | 价格 | 月收入 | 估利 |")
            lines.append("|------|------|------|------|--------|------|")
            for p in picks[:5]:
                lines.append(
                    f"| {p.get('rank', '')} | {p.get('asin', '')} | "
                    f"{p.get('title', '')[:30]} | ${p.get('price', 0)} | "
                    f"${p.get('monthly_revenue', 0):,.0f} | "
                    f"${p.get('est_monthly_profit', 0):,.0f} |"
                )

        return lines

    def _section_traffic(self, traffic: Dict) -> List[str]:
        lines = ["\n---\n## 五、流量分析"]
        s = traffic.get("summary", {})
        if s:
            for k, v in s.items():
                lines.append(f"- {k}: {v}")
        return lines

    async def execute(self, input_data: AgentInput) -> AgentOutput:
        return await super().execute(input_data)
