"""
33 分析方向的映射注册表。

不重复定义方向——直接从 aqueduct/agent_context.py 读取。
只扩展 agent_context.py 没有的部分：每个方向影响哪些 Agent + 定制指令。
"""

from typing import Dict, List, Optional
from backend.aqueduct.agent_context import (
    ANALYSIS_DIRECTIONS_PROMPTS,
    DIRECTION_META,
)


class DimensionRegistry:
    """维度映射注册表——从 agent_context.py 读取 + 扩展 Agent 映射"""

    def __init__(self):
        # 从 agent_context.py 读取——不重复定义
        self.directions: Dict[str, str] = ANALYSIS_DIRECTIONS_PROMPTS       # 33 方向的 prompt 模板
        self.meta: Dict[str, dict] = DIRECTION_META                          # 33 方向的元信息

        # 扩展：每个方向影响哪些 Agent + 各 Agent 的定制指令
        # 这部分 agent_context.py 没有，是本层新增的
        self.agent_map: Dict[str, dict] = self._build_agent_map()

    def _build_agent_map(self) -> Dict[str, dict]:
        """构建 33 方向 → Agent 映射表"""
        return {
            "pricing_strategy": {
                "affects": ["review_analyzer", "market_analyst",
                           "competitor_analyst", "opportunity_judge",
                           "briefing_generator"],
                "agent_prompts": {
                    "review_analyzer": "重点提取价格相关的评论信号，包括价格敏感度评价、性价比讨论、价格投诉等。",
                    "market_analyst": "分析价格带结构：各价格带的品牌分布、销量贡献、价格中位数/均值、价格集中度。识别定价锚点产品。",
                    "competitor_analyst": "竞品定价策略对比：按价格分层分析头部竞品的定价模式（高价策略/低价渗透/中端定位），历史价格变动趋势。",
                    "opportunity_judge": "定价权重提升：评分标准中价格竞争力权重翻倍。评估定价优化空间和价格弹性。",
                    "briefing_generator": "在报告中突出价格带地图和定价优化建议。",
                },
                "downgrades": ["listing_quality", "fulfillment"],
                "depends_on": ["competition_landscape"],
            },
            "competition_landscape": {
                "affects": ["market_analyst", "competitor_analyst",
                           "opportunity_judge", "briefing_generator"],
                "agent_prompts": {
                    "market_analyst": "在市场规模分析中区分品牌层级，识别头部品牌集中度（CR4/CR8）和品类集中度趋势。",
                    "competitor_analyst": "竞争格局分层：头部/腰部/长尾品牌的市场份额和增长趋势。FBA vs FBM 卖家比例。中国卖家渗透率。",
                    "opportunity_judge": "竞争格局权重提升：将竞争壁垒和格局集中度作为关键评分因子。",
                    "briefing_generator": "在报告中提供竞争格局雷达图和品牌定位地图。",
                },
                "downgrades": [],
                "depends_on": [],
            },
            "review_intelligence": {
                "affects": ["review_analyzer", "opportunity_judge",
                           "briefing_generator"],
                "agent_prompts": {
                    "review_analyzer": "深度分析评论内容：提取情感倾向（正面/负面比例）、好评关键词云、差评痛点归纳、分价位评论质量对比。",
                    "opportunity_judge": "将评论质量和客户满意度作为核心评分维度，特别关注差评中可改进的产品缺陷。",
                    "briefing_generator": "在报告中用词云和情感趋势图展示评论洞察。",
                },
                "downgrades": ["pricing_strategy"],
                "depends_on": [],
            },
            "demand_analysis": {
                "affects": ["market_analyst", "opportunity_judge",
                           "briefing_generator"],
                "agent_prompts": {
                    "market_analyst": "分析市场需求：可根据搜索热度趋势、BSR 趋势判断需求扩缩。区分季节性需求 vs 长期趋势。",
                    "opportunity_judge": "需求权重提升：将需求增长趋势和季节性作为评分因子。评估淡季入场 vs 旺季前布局的风险。",
                    "briefing_generator": "在报告中提供需求曲线和搜索热度趋势图。",
                },
                "downgrades": ["fulfillment", "supply_chain"],
                "depends_on": [],
            },
            "market_entry": {
                "affects": ["market_analyst", "opportunity_judge",
                           "briefing_generator"],
                "agent_prompts": {
                    "market_analyst": "评估进入可行性：分析市场成熟度、行业壁垒、新品牌入场难度。给出进入策略建议和预算估算。",
                    "opportunity_judge": "市场进入权重提升：将市场进入难度和壁垒作为关键评分因子。",
                    "briefing_generator": "在报告中提供市场进入路线图（分阶段建议）。",
                },
                "downgrades": [],
                "depends_on": ["competition_landscape", "demand_analysis"],
            },
            "product_opportunity": {
                "affects": ["opportunity_judge", "briefing_generator"],
                "agent_prompts": {
                    "opportunity_judge": "产品机会权重提升：综合评分中产品机会信号权重翻倍。重点关注产品生命周期位置和差异化潜力。",
                    "briefing_generator": "在报告中提供产品机会矩阵（机会 vs 风险）。",
                },
                "downgrades": [],
                "depends_on": ["demand_analysis", "competition_landscape"],
            },
            "competitor_profile": {
                "affects": ["competitor_analyst", "briefing_generator"],
                "agent_prompts": {
                    "competitor_analyst": "单品牌深度剖析：分析头部竞品的品牌定位、产品线宽度、价格策略、卖家行为模式（跟卖/品牌备案/自有品牌）。",
                    "briefing_generator": "在报告中提供主要竞争对手档案卡片。",
                },
                "downgrades": [],
                "depends_on": [],
            },
            "listing_quality": {
                "affects": ["competitor_analyst", "briefing_generator"],
                "agent_prompts": {
                    "competitor_analyst": "对比上榜产品的 Listing 质量：标题结构、五点描述完整度、图片质量、A+ 使用率、视频占比。",
                    "briefing_generator": "在报告中用 checklist 格式评估各竞品 Listing 质量。",
                },
                "downgrades": ["pricing_strategy"],
                "depends_on": [],
            },
            "keyword_expander": {
                "affects": ["keyword_expander", "briefing_generator"],
                "agent_prompts": {
                    "keyword_expander": "扩词偏好：优先扩展品类相关长尾词、场景词、问题词。从竞品标题提取未被覆盖的搜索词。",
                    "briefing_generator": "在报告中列出关键词覆盖矩阵和遗漏的关键词机会。",
                },
                "downgrades": [],
                "depends_on": [],
            },
            "financial_model": {
                "affects": ["market_analyst", "opportunity_judge",
                           "briefing_generator"],
                "agent_prompts": {
                    "market_analyst": "盈利能力分析：估算类目平均利润率、ROI、投资回收期。区分自发货 vs FBA 的成本结构差异。",
                    "opportunity_judge": "财务权重提升：将 ROI、回收期、利润率纳入评分体系。高风险低回报场景自动降分。",
                    "briefing_generator": "在报告中提供财务模型拆解表（收入/成本/利润）。",
                },
                "downgrades": ["listing_quality"],
                "depends_on": ["pricing_strategy"],
            },
            "cross_domain": {
                "affects": ["market_analyst", "opportunity_judge",
                           "briefing_generator"],
                "agent_prompts": {
                    "market_analyst": "跨域对比分析：对比同品类在不同站点的市场规模、竞争格局、价格水平。给出跨域套利机会评分。",
                    "opportunity_judge": "跨域权重提升：将多站点机会纳入评分，特别是高利润低竞争的组合。",
                    "briefing_generator": "在报告中提供跨域对比表和国际化扩张建议。",
                },
                "downgrades": [],
                "depends_on": [],
            },
            "supply_chain": {
                "affects": ["opportunity_judge", "briefing_generator"],
                "agent_prompts": {
                    "opportunity_judge": "供应链权重提升：将供应链风险作为重要评分因子，高风险品类自动降分。",
                    "briefing_generator": "在报告中列出供应链风险因素和应对策略。",
                },
                "downgrades": [],
                "depends_on": [],
            },
            "fraud_warning": {
                "affects": ["review_analyzer", "opportunity_judge",
                           "briefing_generator"],
                "agent_prompts": {
                    "review_analyzer": "审查评论真实性：识别可疑评论模式（批量好评/关键词密度异常/同 IP 聚集）。标注高风险 ASIN。",
                    "opportunity_judge": "评分时标注评论造假风险，造假率高的 ASIN 自动降低评分。",
                    "briefing_generator": "在报告中用风险标识警示评论造假品类。",
                },
                "downgrades": [],
                "depends_on": [],
            },
            "lifecycle": {
                "affects": ["market_analyst", "opportunity_judge",
                           "briefing_generator"],
                "agent_prompts": {
                    "market_analyst": "生命周期分析：判断品类所处的生命周期阶段（引入/增长/成熟/衰退）。分析新品 vs 老品的比例和趋势。",
                    "opportunity_judge": "生命周期权重提升：在增长期品类中评分倾向入场；衰退期品类的机会评分自动降级。",
                    "briefing_generator": "在报告中标注品类生命周期阶段图标。",
                },
                "downgrades": [],
                "depends_on": ["demand_analysis"],
            },
            "pricing_profit": {
                "affects": ["market_analyst", "opportunity_judge",
                           "briefing_generator"],
                "agent_prompts": {
                    "market_analyst": "定价优化分析：各定价带的利润贡献、价格弹性评估、提价/降价空间分析。优化建议应包括利润最大化的定价策略。",
                    "opportunity_judge": "将利润潜力作为核心评分因子，关注高利润细分市场。",
                    "briefing_generator": "在报告中提供定价-利润敏感性分析矩阵。",
                },
                "downgrades": [],
                "depends_on": ["pricing_strategy"],
            },
            "seo_audit": {
                "affects": ["competitor_analyst", "briefing_generator"],
                "agent_prompts": {
                    "competitor_analyst": "Listing SEO 审计：分析标题关键词密度、五点覆盖度、后台关键词使用情况。识别 SEO 不足的竞品。",
                    "briefing_generator": "在报告中提供 SEO 改进清单和关键词优化建议。",
                },
                "downgrades": [],
                "depends_on": [],
            },
            "fulfillment": {
                "affects": ["opportunity_judge", "briefing_generator"],
                "agent_prompts": {
                    "opportunity_judge": "物流权重提升：将 FBA 渗透率、配送方式作为评分因子。FBA 为主品类降低入场门槛评估。",
                    "briefing_generator": "在报告中分析配送结构（FBA/FBM/VC）和成本优化建议。",
                },
                "downgrades": [],
                "depends_on": [],
            },
            "variation_strategy": {
                "affects": ["competitor_analyst", "briefing_generator"],
                "agent_prompts": {
                    "competitor_analyst": "变体策略分析：分析头部竞品的变体覆盖策略（颜色/尺寸/配置），评估变体密度和覆盖盲区。",
                    "briefing_generator": "在报告中提供变体覆盖矩阵和产品线扩展建议。",
                },
                "downgrades": [],
                "depends_on": [],
            },
            "category": {
                "affects": ["market_analyst", "opportunity_judge",
                           "briefing_generator"],
                "agent_prompts": {
                    "market_analyst": "类目生态分析：分析类目结构（父类目/子类目）、类目健康度（新品占比/淘汰率）、类目漂移检测。",
                    "opportunity_judge": "类目健康度权重提升：健康类目评分上浮，萎缩类目下浮。",
                    "briefing_generator": "在报告中提供类目树结构和健康指标仪表盘。",
                },
                "downgrades": [],
                "depends_on": [],
            },
            "risk_warning": {
                "affects": ["opportunity_judge", "briefing_generator"],
                "agent_prompts": {
                    "opportunity_judge": "风险权重提升：在所有评分维度中优先考虑风险因素，高风险品类自动降低评分到 ≤50。",
                    "briefing_generator": "在报告中提供风险仪表盘（高风险/中风险/低风险信号）。",
                },
                "downgrades": [],
                "depends_on": ["fraud_warning"],
            },
            "seller_behavior": {
                "affects": ["competitor_analyst", "opportunity_judge",
                           "briefing_generator"],
                "agent_prompts": {
                    "competitor_analyst": "卖家行为分析：分析活跃卖家类型（品牌卖家/跟卖/VC），追踪卖家活跃度和上新频率。",
                    "opportunity_judge": "将卖家行为模式纳入风险评估，异常行为聚集的品类降低评分。",
                    "briefing_generator": "在报告中提供卖家生态报告。",
                },
                "downgrades": [],
                "depends_on": [],
            },
            "anomaly_alerts": {
                "affects": ["review_analyzer", "traffic_analyzer",
                           "opportunity_judge"],
                "agent_prompts": {
                    "review_analyzer": "标记评论异常：评论数量激增/骤减、评分异常波动、异常星级分布。",
                    "traffic_analyzer": "标记流量异常：BSR 剧烈波动、价格异常变动、排名异常跳变。",
                    "opportunity_judge": "异常指标自动降分：存在异常信号的维度加权后分数自动扣减。",
                },
                "downgrades": [],
                "depends_on": [],
            },
            "product_activity": {
                "affects": ["market_analyst", "competitor_analyst"],
                "agent_prompts": {
                    "market_analyst": "产品活跃度分析：分析新品上线率、老品淘汰率、活跃产品占比。判断市场活力。",
                    "competitor_analyst": "追踪头部 SKU 的上新频率和活跃度变化。",
                },
                "downgrades": [],
                "depends_on": [],
            },
            "promotion_effectiveness": {
                "affects": ["competitor_analyst", "opportunity_judge",
                           "briefing_generator"],
                "agent_prompts": {
                    "competitor_analyst": "促销策略分析：分析竞品促销频率、折扣深度、Coupon 使用情况。评估促销对排名的拉动效果。",
                    "opportunity_judge": "将促销成本纳入利润评估，过度依赖促销的品类降低评分。",
                    "briefing_generator": "在报告中提供促销效果评估和建议。",
                },
                "downgrades": [],
                "depends_on": [],
            },
            "inventory_intelligence": {
                "affects": ["opportunity_judge", "briefing_generator"],
                "agent_prompts": {
                    "opportunity_judge": "库存权重提升：关注库存风险（缺货/高库存）、仓储成本和周转率。",
                    "briefing_generator": "在报告中提供库存健康度评估。",
                },
                "downgrades": [],
                "depends_on": [],
            },
            "market_timing": {
                "affects": ["market_analyst", "opportunity_judge",
                           "briefing_generator"],
                "agent_prompts": {
                    "market_analyst": "入场时机分析：结合季节性、市场趋势、新品增速判断最佳入场窗口。给出分月入场建议。",
                    "opportunity_judge": "时机权重提升：将入场时机合理性纳入评分。计算最佳入场时间窗口。",
                    "briefing_generator": "在报告中提供入场时机日历和倒推生产/物流时间线。",
                },
                "downgrades": [],
                "depends_on": ["demand_analysis", "lifecycle"],
            },
            "fba_cost_optimization": {
                "affects": ["opportunity_judge", "briefing_generator"],
                "agent_prompts": {
                    "opportunity_judge": "FBA 成本权重提升：分析 FBA 费用结构（仓储/配送/长期仓储），高成本品类降分。",
                    "briefing_generator": "在报告中提供 FBA 费用拆解和优化建议。",
                },
                "downgrades": [],
                "depends_on": [],
            },
            "international_priority": {
                "affects": ["market_analyst", "opportunity_judge",
                           "briefing_generator"],
                "agent_prompts": {
                    "market_analyst": "国际化优先级：对比不同站点的市场吸引力（市场大小/竞争强度/物流复杂度）。给出国际化建议排序。",
                    "opportunity_judge": "多站点权重提升：给出各站点独立的机会评分和推荐优先级。",
                    "briefing_generator": "在报告中提供国际化扩张路线图。",
                },
                "downgrades": [],
                "depends_on": ["cross_domain"],
            },
            "cross_sell": {
                "affects": ["market_analyst", "briefing_generator"],
                "agent_prompts": {
                    "market_analyst": "交叉销售分析：分析常与目标品类一起购买的关联品类。推荐产品线扩展方向。",
                    "briefing_generator": "在报告中提供关联品类矩阵和扩展建议。",
                },
                "downgrades": [],
                "depends_on": [],
            },
            "product_network": {
                "affects": ["competitor_analyst", "briefing_generator"],
                "agent_prompts": {
                    "competitor_analyst": "产品网络分析：分析竞品的产品网络策略、子品牌布局、品牌间关联关系。",
                    "briefing_generator": "在报告中提供产品网络拓扑图。",
                },
                "downgrades": [],
                "depends_on": [],
            },
            "multi_domain": {
                "affects": ["market_analyst", "opportunity_judge",
                           "briefing_generator"],
                "agent_prompts": {
                    "market_analyst": "多域数据分析：整合多域（US/EU/JP）数据做跨域比较。分析各域合规要求差异。",
                    "opportunity_judge": "跨域评分：给出每个域的机会评分，推荐优先级。",
                    "briefing_generator": "在报告中提供多域对比仪表盘。",
                },
                "downgrades": [],
                "depends_on": ["cross_domain"],
            },
            "compliance": {
                "affects": ["opportunity_judge", "briefing_generator"],
                "agent_prompts": {
                    "opportunity_judge": "合规权重提升：合规要求高的品类降低评分，标注各站点特殊合规要求。",
                    "briefing_generator": "在报告中提供合规 checklist（EU 能效标签/危险品申报等）。",
                },
                "downgrades": [],
                "depends_on": [],
            },
            "security": {
                "affects": ["review_analyzer", "opportunity_judge"],
                "agent_prompts": {
                    "review_analyzer": "安全审查：标注可能存在安全问题的产品或品类。",
                    "opportunity_judge": "安全权重提升：安全问题可能影响评分，高风险品类降分。",
                },
                "downgrades": [],
                "depends_on": [],
            },
        }

    def get_agent_prompt(self, dim: str, agent: str) -> str:
        """获取某个方向对某个 Agent 的定制指令"""
        return self.agent_map.get(dim, {}).get("agent_prompts", {}).get(agent, "")

    def get_affected_agents(self, dimensions: List[str]) -> Dict[str, List[str]]:
        """获取指定方向列表影响的所有 Agent 清单"""
        affected: Dict[str, List[str]] = {}
        for dim in dimensions:
            info = self.agent_map.get(dim, {})
            dim_name = self.meta.get(dim, {}).get("id", dim)
            for agent in info.get("affects", []):
                if agent not in affected:
                    affected[agent] = []
                affected[agent].append(f"{dim_name} {dim}")
        return affected

    def get_downgraded_directions(self, primary_dim: str) -> List[str]:
        """获取某个主线方向需要弱化的方向列表"""
        return self.agent_map.get(primary_dim, {}).get("downgrades", [])

    def get_depends_on(self, dim: str) -> List[str]:
        """获取某个方向依赖的其他方向"""
        return self.agent_map.get(dim, {}).get("depends_on", [])

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


# 单例
_registry: Optional[DimensionRegistry] = None


def get_dimension_registry() -> DimensionRegistry:
    global _registry
    if _registry is None:
        _registry = DimensionRegistry()
    return _registry