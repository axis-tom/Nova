"""
Pipeline 调度器 — Level 1: Intent Router

职责：
  根据 intent_type 路由到对应的确定性 Pipeline。
  不做 LLM 决策，纯代码匹配。
"""
from typing import Optional
from backend.core.pipeline.pipelines.asin_analysis import ASINAnalysisPipeline
from backend.core.pipeline.pipelines.market_research import MarketResearchPipeline

class PipelineRouter:
    """Pipeline 路由注册表"""

    def __init__(self):
        self._routes = {
            # ASIN 分析类
            "focus_entity": ASINAnalysisPipeline,
            "product_research": ASINAnalysisPipeline,
            # 市场分析类
            "market_analysis": MarketResearchPipeline,
            # 预留：关键词分析、Listing 优化等
        }

    def resolve(self, intent_type: str):
        """根据意图类型返回对应的 Pipeline 类"""
        pipeline_cls = self._routes.get(intent_type)
        if pipeline_cls is None:
            # 未匹配 → 退化为简单数据查询
            return None
        return pipeline_cls


# 模块级单例
router = PipelineRouter()