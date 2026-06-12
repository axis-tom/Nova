"""
ASIN 分析 Pipeline — 确定性多步骤分析

流程：
  1. fetch_products  → 获取所有 ASIN 的 DB 数据
  2. fetch_trends    → 获取价格/BSR 趋势
  3. market_volume   → 计算市场体量（实算，不走 LLM）
  4. brand_analysis  → 品牌分布
  5. price_bands     → 价格带分析
  6. review_analysis → 评论壁垒
  7. market_score    → 规则引擎评分
  8. llm_commentary  → LLM 写解读

全部步骤由代码控制，没有 LLM 决策。
"""
import logging
import time
from typing import Any, Dict, List, Optional
from datetime import datetime

from backend.core.pipeline.base import BasePipeline, PipelineContext, PipelineResult
from backend.business.ecommerce.product_selection.agents.market_analyst import MarketAnalystAgent
from backend.common.core.state import State

logger = logging.getLogger(__name__)


class ASINAnalysisPipeline(BasePipeline):
    """基于给定 ASIN 列表做市场分析"""

    name = "asin_analysis"

    async def run(self, ctx: PipelineContext, tracer=None) -> PipelineResult:
        start = time.time()
        asins = ctx.found_asins  # 全量 ASIN（不再截断，清除前 8 个的历史限制）
        logger.info(f"[Pipeline] 开始分析: 输入 {len(ctx.found_asins)} 个 ASIN, 全部参与计算")

        if not asins:
            return PipelineResult(
                pipeline_name=self.name,
                executed_at=datetime.now().isoformat(),
                structured={"error": "无可用 ASIN 数据"},
                error="无可用 ASIN",
                duration_ms=0,
            )

        # ── Step 1: 批量获取 ASIN 详情 ──
        await self._trace_handoff(tracer, "Pipeline→fetch_asin_details", f"获取 {len(asins)} 个 ASIN 详情")
        logger.info(f"[Pipeline] Step 1: 获取 {len(asins)} 个 ASIN 详情（全部参与，无截断）")
        products = await self._fetch_asin_details(ctx, asins)
        await self._trace_handoff(tracer, "fetch_asin_details→products", f"加载了 {len(products)} 个 ASIN 数据")

        # ── Step 2: 获取趋势数据 ──
        logger.info(f"[Pipeline] Step 2: 获取趋势")
        trends = await self._fetch_trends(ctx, asins)
        await self._trace_handoff(tracer, "fetch_trends→trends", f"获取了 {len(asins)} 个 ASIN 的趋势")

        # ── Step 3-7: 复用 MarketAnalyst 的确定性工具 ──
        await self._trace_handoff(tracer, "Pipeline→MarketAnalyst工具", "执行确定性市场维度计算")
        logger.info(f"[Pipeline] Step 3: 市场维度计算")
        analyst = MarketAnalystAgent()

        volume = analyst._analyze_market_volume(products) if products else {}
        brand_dist = analyst._aggregate_by_brand(products) if products else {}
        price_bands = analyst._analyze_price_bands(products) if products else {}
        review_barrier = analyst._analyze_review_barrier(products) if products else {}
        rating_health = analyst._analyze_rating_health(products) if products else {}
        seller = analyst._analyze_seller_composition(products) if products else {}
        brand_conc = analyst._analyze_brand_concentration(brand_dist, products) if products and brand_dist else {}
        opportunities = analyst._identify_opportunities(products, price_bands) if products else []
        risks = analyst._identify_risks(products, {"bsr": {}}, len(products)) if products else []
        seasonality = analyst._analyze_seasonality(products) if products else {}

        # ── 组合为结构化数据（证据链） ──
        deterministic = {
            "market_volume": volume,
            "trends": trends,
            "seasonality": seasonality,
            "brand_distribution": brand_dist,
            "price_bands": price_bands,
            "review_barrier": review_barrier,
            "rating_health": rating_health,
            "seller_composition": seller,
            "brand_concentration": brand_conc,
            "opportunities": opportunities,
            "risks": risks,
        }
        await self._trace_handoff(tracer, "确定性计算→deterministic",
                                  f"完成 {len(deterministic)} 个维度计算",
                                  {k: str(type(v))[:30] for k, v in deterministic.items()})

        # ── 规则引擎评分 ──
        score = analyst._market_entry_scorer(deterministic) if hasattr(analyst, '_market_entry_scorer') else {}
        await self._trace_handoff(tracer, "规则引擎→decision_support",
                                  f"市场进入评分: {score.get('market_entry_score', '?')}/100 — {score.get('label', '?')}",
                                  score)

        # ── 结构化数据 ──
        structured = {
            "products": len(products),
            "asins_analyzed": asins,
            "deterministic": deterministic,
            "decision_support": score,
            # ★ 数据快照：原始 ASIN 数据（冻住的真相源，供重分析和追问答疑）
            "data_snapshot": {
                "asins": asins,
                "products_count": len(products),
                "products_raw": [
                    {
                        "asin": p.get("asin"),
                        "current_price": p.get("current_price"),
                        "monthly_sold": p.get("monthly_sold"),
                        "rating": p.get("rating"),
                        "review_count": p.get("review_count"),
                        "current_bsr": p.get("current_bsr"),
                        "brand": p.get("brand"),
                        "seller_count": p.get("seller_count"),
                        "is_fba": p.get("is_fba"),
                        "is_prime": p.get("is_prime"),
                        "has_coupon": p.get("has_coupon"),
                        "category_name": p.get("category_name"),
                    }
                    for p in products
                ],
            },
        }

        # ── Step 8: LLM 注释（只写解读，不提证据） ──
        await self._trace_handoff(tracer, "Pipeline→LLM commentary", "基于结构化数据生成 LLM 注释")
        commentary = await self._generate_llm_commentary(ctx, structured)

        elapsed = int((time.time() - start) * 1000)
        logger.info(f"[Pipeline] 完成，耗时 {elapsed}ms")

        # ── 追踪最终报告到文件 ──
        if tracer:
            import json
            tracer.final_answer = commentary
            tracer._write_to_files()

        return PipelineResult(
            pipeline_name=self.name,
            executed_at=datetime.now().isoformat(),
            structured=structured,
            llm_commentary=commentary,
            duration_ms=elapsed,
        )