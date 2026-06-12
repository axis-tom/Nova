"""
市场调研 Pipeline — 品类级市场分析（待完善）

跟 ASINAnalysisPipeline 的区别：
  - ASINAnalysisPipeline: 用户给了固定 ASIN，围绕这些 ASIN 做分析
  - MarketResearchPipeline: 用户给品类名，先探索品类再分析

目前先做一个占位版本，后期完善品类探索逻辑。
"""
import logging
from typing import Dict, Any
from datetime import datetime

from backend.core.pipeline.base import BasePipeline, PipelineContext, PipelineResult

logger = logging.getLogger(__name__)


class MarketResearchPipeline(BasePipeline):
    """品类级市场调研"""

    name = "market_research"

    async def run(self, ctx: PipelineContext) -> PipelineResult:
        # 暂时 fallback 到 ASINAnalysisPipeline（如果有 ASIN）
        if ctx.found_asins:
            from backend.core.pipeline.pipelines.asin_analysis import ASINAnalysisPipeline
            return await ASINAnalysisPipeline().run(ctx)

        return PipelineResult(
            pipeline_name=self.name,
            executed_at=datetime.now().isoformat(),
            structured={"note": "品类级市场分析 Pipeline 待完善"},
            llm_commentary="品类级分析尚未实现，请提供具体的 ASIN 列表。",
            error="品类级分析未实现",
        )