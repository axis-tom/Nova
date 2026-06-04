"""
DimensionRegistry — 方向映射注册表（已废弃，保留兼容占位）

⚠️ 此模块正在废弃中。agent_map（33 方向 → Agent 路由）已被移除。
   旧调用方将在后续步骤中逐一改为使用 sub_task 自然语言方式。
   目前仅保留 get_dim_name() 供数据层引用 33 方向中文名。

数据层的 33 方向提示词定义已移至 aqueduct/agent_context.py，不受影响。
"""

from typing import Dict, List, Optional
from backend.aqueduct.agent_context import (
    ANALYSIS_DIRECTIONS_PROMPTS,
    DIRECTION_META,
)


class DimensionRegistry:
    """维度映射注册表（已废弃，保留兼容占位）

    之前的功能：
    - 33 方向 → Agent 路由映射（agent_map → 已删除）
    - 各 Agent 定制指令注入（已删除）
    - 方向强弱依赖关系（已删除）

    当前保留：
    - get_dim_name(): 方向 ID → 中文名（数据层仍有引用）
    - directions/meta: 从 agent_context.py 读取（只读）
    """

    def __init__(self):
        # 从 agent_context.py 读取——不重复定义
        self.directions: Dict[str, str] = ANALYSIS_DIRECTIONS_PROMPTS
        self.meta: Dict[str, dict] = DIRECTION_META
        # agent_map 已删除（见 git history）

    # ── 已删除的方法（原 33 方向 → Agent 路由） ──
    # get_agent_prompt()     — 改用 PromptCustomizer 的 sub_task 参数
    # get_affected_agents()  — 改用 Orchestrator 在 ReAct 中动态调度
    # get_downgraded_directions() — 不再需要
    # get_depends_on()       — 不再需要

    def get_dim_name(self, dim: str) -> str:
        """获取方向的中文可读名称"""
        names = {
            "pricing_strategy": "定价策略", "competition_landscape": "竞争格局",
            "review_intelligence": "评论洞察", "demand_analysis": "需求分析",
            "market_entry": "市场进入", "product_opportunity": "产品机会",
            "competitor_profile": "竞品画像", "listing_quality": "Listing 质量",
            "keyword_expander": "关键词拓展", "financial_model": "财务模型",
            "cross_domain": "跨域分析", "supply_chain": "供应链",
            "fraud_warning": "造假预警", "lifecycle": "生命周期",
            "pricing_profit": "定价利润", "seo_audit": "SEO 审计",
            "fulfillment": "物流配送", "variation_strategy": "变体策略",
            "category": "类目分析", "risk_warning": "风险预警",
            "seller_behavior": "卖家行为", "anomaly_alerts": "异常告警",
            "product_activity": "产品活跃度", "promotion_effectiveness": "促销效果",
            "inventory_intelligence": "库存情报", "market_timing": "市场时机",
            "fba_cost_optimization": "FBA 成本", "international_priority": "国际优先级",
            "cross_sell": "交叉销售", "product_network": "产品网络",
            "multi_domain": "多域分析", "compliance": "合规",
            "security": "安全",
        }
        return names.get(dim, dim)

    # ── 已废弃方法 — 返回空值保持兼容 ──

    def get_agent_prompt(self, dim: str, agent: str) -> str:
        """已废弃：返回空字符串"""
        return ""

    def get_affected_agents(self, dimensions: List[str]) -> Dict[str, List[str]]:
        """已废弃：返回空字典"""
        return {}

    def get_downgraded_directions(self, primary_dim: str) -> List[str]:
        """已废弃：返回空列表"""
        return []

    def get_depends_on(self, dim: str) -> List[str]:
        """已废弃：返回空列表"""
        return []


# 单例
_registry: Optional[DimensionRegistry] = None


def get_dimension_registry() -> DimensionRegistry:
    global _registry
    if _registry is None:
        _registry = DimensionRegistry()
    return _registry