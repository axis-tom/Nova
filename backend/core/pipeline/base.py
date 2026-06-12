"""
Pipeline 基类 — Level 2: Deterministic Pipeline

所有 Pipeline 继承此类，实现 run() 方法。
Pipeline 是纯代码执行，不经过 LLM 决策。
每个步骤直接调 DataQueryEngine 或 DataProvider。
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, TYPE_CHECKING
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from backend.core.decision_trace.tracer import DecisionTracer


@dataclass
class PipelineContext:
    """Pipeline 执行的上下文"""
    intent_type: str
    entities: List[str]           # ASIN 列表
    category_hint: str            # 品类提示
    found_asins: List[str]        # DB 中已有的 ASIN
    missing_asins: List[str]      # DB 中缺失的 ASIN
    domain: str = "US"
    raw_query: str = ""
    conversation_id: str = ""
    reanalysis_prompt: str = ""   # 重分析时用户指出的问题 + 上次分析摘要，LLM 注释会据此做对比修正

    # 执行过程中填充
    products_data: List[Dict] = field(default_factory=list)
    market_data: Dict[str, Any] = field(default_factory=dict)
    trend_data: Dict[str, Any] = field(default_factory=dict)
    analysis_result: Dict[str, Any] = field(default_factory=dict)
    llm_commentary: str = ""


@dataclass
class PipelineResult:
    """Pipeline 执行结果 — 结构化数据 + LLM 注释"""
    pipeline_name: str
    executed_at: str

    # 结构化数据（证据链，直接渲染到前端）
    structured: Dict[str, Any]

    # LLM 注释（基于结构化数据写的解读）
    llm_commentary: str = ""

    # 元信息
    duration_ms: int = 0
    error: Optional[str] = None


class BasePipeline(ABC):
    """Pipeline 基类"""

    name: str = "base"

    @abstractmethod
    async def run(self, ctx: PipelineContext, tracer: Optional['DecisionTracer'] = None) -> PipelineResult:
        """执行 Pipeline，返回结构化结果"""
        ...

    async def _trace_handoff(self, tracer: Optional['DecisionTracer'], from_to: str, what: str, detail: dict = None):
        """记录 Pipeline 内部的交接链到 DecisionTrace"""
        if tracer is None:
            return
        from backend.core.decision_trace.tracer import HandoffRecord
        tracer.handoffs.append(HandoffRecord(
            from_to=from_to,
            what=what,
            detail=detail or {},
        ))

    async def _fetch_asin_details(self, ctx: PipelineContext, asins: List[str]) -> List[Dict]:
        """批量查 ASIN 详情（确定性，不走 LLM）"""
        from backend.core.data_tools.engine import get_query_engine
        engine = get_query_engine()
        results = []
        logger.info(f"[Pipeline] _fetch_asin_details: 加载 {len(asins)} 个 ASIN（无上限）")
        for asin in asins:
            data = await engine.fetch_details("product", asin, domain=ctx.domain)
            if data:
                # 过滤掉大型非结构化字段，减少 token
                for skip in ("raw_payload", "feature_bullets", "description", "specifications",
                             "images", "top_reviews", "videos", "aplus_content",
                             "also_bought", "also_viewed", "sponsored_products",
                             "seller_profile", "reviews", "category_tree"):
                    data.pop(skip, None)
                results.append(data)
            else:
                logger.warning(f"[Pipeline] _fetch_asin_details: ASIN {asin} 未返回数据")
        logger.info(f"[Pipeline] _fetch_asin_details: 实际加载 {len(results)}/{len(asins)} 个 ASIN")
        return results

    async def _fetch_trends(self, ctx: PipelineContext, asins: List[str]) -> Dict[str, Any]:
        """批量查趋势数据"""
        from backend.core.data_tools.engine import get_query_engine
        engine = get_query_engine()
        logger.info(f"[Pipeline] _fetch_trends: 加载 {len(asins)} 个 ASIN 的趋势数据")
        result = await engine.fetch_trends(
            entity_type="product",
            entity_ids=asins,
            metrics=["price_history", "bsr_history"],
            max_points=60,
            domain=ctx.domain,
        )
        return result

    async def _generate_llm_commentary(self, ctx: PipelineContext, structured: Dict[str, Any]) -> str:
        """
        基于结构化数据让 LLM 写结论注释（Level 3）

        根据 ctx.intent_type 切换不同的 prompt 模板：
          - product_research → 决策卡（做/不做/观望）
          - market_analysis  → 市场调研报告
          - competitor_watch → 竞品分析报告
          - focus_entity     → 单品概览
          其他 → 通用决策卡（兜底）
        """
        from backend.core.llm.config import get_llm_for_agent
        llm = get_llm_for_agent("orchestrator")

        # 提取关键数据摘要（所有模板共享）
        det = structured.get("deterministic", {})
        decision = structured.get("decision_support", {})
        asins = structured.get("asins_analyzed", [])

        volume = det.get("market_volume", {})
        trends = det.get("trends", {}).get("trends", {})
        bsr_trend = det.get("trends", {}).get("summary", "")
        brand_conc = det.get("brand_concentration", {})
        price_bands = det.get("price_bands", {})
        review = det.get("review_barrier", {})
        health = det.get("rating_health", {})
        opportunities = det.get("opportunities", [])
        risks = det.get("risks", [])
        brand_dist = det.get("brand_distribution", {})
        seasonality = det.get("seasonality", {})
        seller_comp = det.get("seller_composition", {})

        # 覆盖率
        coverage = structured.get("coverage_audit", {})
        coverage_line = (
            f"【数据覆盖率审计】输入 {coverage.get('input_asins', '?')} 个 → "
            f"DB 加载 {coverage.get('loaded_from_db', '?')} 个 → "
            f"分析 {coverage.get('loaded_from_db', '?')} 个"
            f"（{coverage.get('coverage_pct', '?')}%），"
            f"失败 {coverage.get('failed_to_load_count', 0)} 个"
            f"{' ⚠️ 数据不完整' if coverage.get('failed_to_load_count', 0) > 0 else ' ✅ 全覆盖'}"
        )

        # 公共数据摘要
        data_summary = (
            f"用户 ASIN: {asins}\n"
            f"{coverage_line}\n"
            f"商品数: {volume.get('product_count', '?')} | "
            f"月销总量: {volume.get('total_monthly_units', '?'):,} 件 | "
            f"月营收: ${volume.get('estimated_monthly_revenue', 0):,.0f}\n"
            f"均价: ${volume.get('avg_price', '?'):.2f} | "
            f"BSR中位数: {volume.get('bsr_range', {}).get('median', '?')}\n\n"
            f"品牌: {brand_conc.get('total_brands', '?')} 个 | "
            f"Top3 份额: {brand_conc.get('top_3_market_share_pct', '?')}% | "
            f"集中度: {brand_conc.get('concentration', '?')}\n"
            f"壁垒等级: {review.get('review_barrier', '?')} | "
            f"评论中位数: {review.get('median_review_count', '?')} 条\n"
            f"健康分: {health.get('rating_health_score', '?')} | "
            f"均分: {health.get('avg_rating', '?')}\n\n"
            f"BSR 趋势: {bsr_trend[:300] if bsr_trend else '无趋势数据'}\n\n"
            f"市场进入评分: {decision.get('market_entry_score', '?')}/100 — {decision.get('label', '?')}\n"
            f"有利因素: {decision.get('positives', [])}\n"
            f"风险因素: {decision.get('negatives', [])}\n"
            f"切入路径: {decision.get('entry_routes', [])}\n"
            f"机会点: {[o.get('opportunity', '') for o in (opportunities or [])[:3]]}\n"
            f"风险: {[r.get('risk_type', '') for r in (risks or [])[:3]]}\n"
        )

        # ── 重分析修正前缀（所有模板共享） ──
        reanalysis_section = ""
        if ctx.reanalysis_prompt:
            reanalysis_section = (
                "\n\n## ⚠️ 这是重新分析（用户指出上次分析有误）\n\n"
                "以下是你（LLM）上一次分析的内容和用户指出的问题：\n"
                f"{ctx.reanalysis_prompt}\n\n"
                "**你的任务**：\n"
                "1. 基于最新的结构化数据重新做分析判断\n"
                "2. 在输出中明确标出：这次修正了哪个具体结论、修正前后对比是什么\n"
                "3. 如果数据与用户指出的问题仍不一致，在结论中说明矛盾点\n"
                "4. 不要简单重复旧结论——基于当前真实数据重新判断\n"
            )

        # ── intent_type → prompt 模板路由 ──
        intent = ctx.intent_type

        # ═══════════════════════════════════════════════════════
        # 模板 1: 竞品分析（competitor_watch）
        # ═══════════════════════════════════════════════════════
        if intent == "competitor_watch":
            prompt = (
                "你是一位亚马逊竞品分析专家。基于以下真实数据，输出**竞品分析报告**。\n\n"
                f"--- 数据 ---\n{data_summary}\n"
                f"{reanalysis_section}"
                "--- 任务 ---\n"
                "按以下结构输出竞品分析报告，每一条必须引用具体数据：\n\n"
                "🧾 竞品格局概览\n"
                "- 品牌数量与集中度\n"
                "- 头部品牌及市场份额\n"
                "- 价格带分布\n\n"
                "📊 竞品价格对比\n"
                "- 各价格区间的主流品牌和 ASIN\n"
                "- 价格中位数/均值的品牌差异\n\n"
                "⭐ Review 分析\n"
                "- 各品牌评论数分布\n"
                "- 评分健康度差异\n"
                "- 高频差评关键词（3个以内）\n\n"
                "📋 Listing 质量对比\n"
                "- A+ 覆盖率\n"
                "- 视频/图片质量\n"
                "- 卖点差异化\n\n"
                "🔑 差异化机会\n"
                "- 竞品未覆盖的价格带/功能\n"
                "- 评论缺口\n"
                "- Listing 优化空间\n\n"
                "规则：\n"
                "- 每一条必须引用具体数字（月销、评分、评论数、价格、份额等）\n"
                "- 不要写「市场体量中等」——说「6.6 万台/月」\n"
                "- 风险必须具体，不要套话\n"
                "- 直接输出，不含 Markdown 代码块包裹"
            )

        # ═══════════════════════════════════════════════════════
        # 模板 2: 市场调研报告（market_analysis）
        # ═══════════════════════════════════════════════════════
        elif intent == "market_analysis":
            prompt = (
                "你是一位亚马逊市场调研专家。基于以下真实数据，输出**市场调研报告**。\n\n"
                f"--- 数据 ---\n{data_summary}\n"
                f"{reanalysis_section}"
                "--- 任务 ---\n"
                "按以下结构输出市场调研报告，每一条必须引用具体数据：\n\n"
                "📊 市场规模与结构\n"
                "- 月销总量 / 月营收\n"
                "- 价格分布\n"
                "- BSR 范围\n\n"
                "📈 市场趋势\n"
                "- BSR 趋势方向（上升/下降/稳定）\n"
                "- 价格变化方向\n"
                "- 淡旺季特征\n\n"
                "🏷️ 品牌格局\n"
                "- Top 品牌及市场份额\n"
                "- 集中度判断\n"
                "- 进入壁垒\n\n"
                "📝 用户需求与痛点\n"
                "- 基于 Review 数据分析用户高频关注点\n"
                "- 高频差评关键词（3个以内）\n"
                "- 评分健康度\n\n"
                "💰 价格结构\n"
                "- 主流价格带\n"
                "- 各价格区间竞争密度\n"
                "- 潜在价格空白\n\n"
                "🔍 热门关键词与趋势\n"
                "- 搜索热度信号（如有）\n"
                "- 与品类相关的季节性\n"
                "- 新兴趋势\n\n"
                "💡 潜在差异化机会\n"
                "- 价格带空白\n"
                "- 评论缺口\n"
                "- Listing 质量差距\n"
                "- 产品功能缺口\n\n"
                "规则：\n"
                "- 每一条必须引用具体数字（月销、评分、评论数、价格、份额等）\n"
                "- 不要写「市场体量中等」——说「6.6 万台/月」\n"
                "- 建议必须可执行，说清楚具体路径\n"
                "- 直接输出，不含 Markdown 代码块包裹"
            )

        # ═══════════════════════════════════════════════════════
        # 模板 3: 决策卡 — 默认 / product_research
        # ═══════════════════════════════════════════════════════
        else:
            prompt = (
                "你是一位资深亚马逊运营分析师。你面前是系统基于真实数据算出的市场分析。\n\n"
                f"--- 数据 ---\n{data_summary}\n"
                f"{reanalysis_section}"
                "--- 任务 ---\n"
                "把以上数据压缩成一张**决策卡**。不要回答任何额外内容，直接按以下模板输出：\n\n"
                "🧾 结论：做 / 不做 / 观望\n\n"
                "置信度：高 / 中 / 低\n\n"
                "📊 决策依据\n"
                "1. 市场信号：是否增长（+/-/稳） | 需求稳定性（高/中/低）\n"
                "2. 竞争结构：是否头部垄断（是/否） | 新品进入难度（高/中/低）\n"
                "3. 执行匹配：是否适合你们当前供应链/资金/运营能力（是/否）\n\n"
                "⚠️ 风险清单\n"
                "- 商业风险：例如价格战/利润压缩/生命周期短\n"
                "- 执行风险：例如供应链/广告成本/合规\n"
                "- 时间风险：回款周期 vs 资金压力\n\n"
                "🧪 关键证据（可折叠）\n"
                "- 市场：月销量区间 / 趋势方向\n"
                "- 竞争：Top 集中度 / 评论量分布\n"
                "- 用户反馈：高频差评关键词（3个以内）\n"
                "- 价格结构：主流价格带\n\n"
                "🧭 建议行动路径\n"
                "- 如果做：Step 1 最小验证方式 | Step 2 验证指标\n"
                "- 如果不做：替代方向建议（1个）\n\n"
                "🧷 一句话判断\n"
                "（这个品是否适合你们现在这个阶段的资源结构）\n\n"
                "规则：\n"
                "- 结论直接用 decision_support 的 label，不用犹豫\n"
                "- 置信度 = 如果 market_entry_score >= 70 → 高，>= 40 → 中，< 40 → 低\n"
                "- 每一条必须引用数据（月销、份额、评分、价格带等），让运营可以回查验证\n"
                "- 不要写「市场体量中等」——说「6.6 万台/月」\n"
                "- 风险必须具体，不要套话\n"
                "- 建议必须可执行，说清楚具体路径\n"
                "- 直接输出，不含 Markdown 代码块包裹"
            )

        try:
            response = await llm.ainvoke(prompt)
            return response.content if hasattr(response, 'content') else str(response)
        except Exception as e:
            return f"（LLM 注释生成失败: {e}）"