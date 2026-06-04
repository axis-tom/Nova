"""
IntentClassifier — 意图分类模块

借鉴 DSPy 的 Signature 模式做结构化输入输出定义。
策略：
1. 规则引擎初步分类（关键词匹配，零 LLM）
2. 边界模糊时调 gpt-5.4-mini-high（DSPy Signature 模式做 LLM 分类）
"""

import re
from dataclasses import dataclass, field
from typing import List, Optional
from enum import Enum

from backend.core.llm.config import get_prompt_engine_llm


class IntentType(str, Enum):
    MARKET_ANALYSIS = "market_analysis"       # 市场分析
    DEEPEN = "deepen"                          # 深化已有分析
    FOCUS_ENTITY = "focus_entity"              # 聚焦特定实体
    MULTI_DIM = "multi_dim"                    # 一次性多维分析
    PRODUCT_RESEARCH = "product_research"      # 单品调研
    COMPETITOR_WATCH = "competitor_watch"      # 竞品监控
    GENERAL_QUERY = "general_query"            # 通用查询


class AnalysisDepth(str, Enum):
    BASIC = "basic"              # 基本
    MODERATE = "moderate"        # 中等
    DEEP = "deep"                # 深入
    COMPREHENSIVE = "comprehensive"  # 全面


@dataclass
class IntentAnalysisSpec:
    """意图分析规格——PromptEngine.translate() 的输出"""
    intent_type: IntentType = IntentType.GENERAL_QUERY
    dimensions: List[str] = field(default_factory=list)
    depth: AnalysisDepth = AnalysisDepth.MODERATE
    primary_dim: str = ""
    entities: List[str] = field(default_factory=list)
    focus_description: str = ""
    is_incremental: bool = False
    previous_dimensions: List[str] = field(default_factory=list)
    raw_query: str = ""


# ── 规则引擎：关键词 → 意图/方向 映射 ──

_INTENT_RULES = [
    # 意图类型匹配 — 特定模式优先于通用模式
    (r"(上次|之前|接着|继续|刚才|说说.*上次)", IntentType.DEEPEN),
    (r"再.*(看|分析|深入|详细|说说)", IntentType.DEEPEN),
    (r"(深入|继续|更.*详细|进一步)", IntentType.DEEPEN),
    (r"(对比|比较).*(竞品|品牌|竞争对手)", IntentType.COMPETITOR_WATCH),
    (r"(竞品|竞争对手|品牌).*(分析|对比|比较|报告)", IntentType.COMPETITOR_WATCH),
    (r"什么.*值得|选品|机会.*分析|入.*场|值不值得", IntentType.PRODUCT_RESEARCH),
    (r"(推荐|值得|进场|入场).*(产品|品类|类目)", IntentType.PRODUCT_RESEARCH),
    # 兜底：任何"分析/评估/调研/看看"都视为市场分析
    (r"(分析|评估|调研|看看).*", IntentType.MARKET_ANALYSIS),
    (r"(市场|品类|类目).*(分析|评估|报告|机会)", IntentType.MARKET_ANALYSIS),
]

_DIRECTION_RULES = [
    (r"定价|价格|价格带|价.*格|利润|毛利", "pricing_strategy"),
    (r"竞争|格局|集中度|CR[48]|份额|垄断", "competition_landscape"),
    (r"评论|口碑|评分|评价|客诉|差评|好评|review", "review_intelligence"),
    (r"需求|搜索.*热|趋势|增长|下降", "demand_analysis"),
    (r"进入|入场|门槛|壁垒|难.*进", "market_entry"),
    (r"机会|潜力|蓝海|红海|空白", "product_opportunity"),
    (r"竞品|对比.*品牌|对标|模仿", "competitor_profile"),
    (r"listing|标题|图片|五点|详情|转化", "listing_quality"),
    (r"关键词|搜索词|长尾|拓词|SEO", "keyword_expander"),
    (r"利润|ROI|回报|赚钱|投入产出|盈利", "financial_model"),
    (r"跨境|跨域|多站|国际化|EU|欧洲|日本", "cross_domain"),
    (r"供应链|物流|FBA|仓储|发货|运费", "supply_chain"),
    (r"造假|刷单|虚假|fraud|可疑|水分", "fraud_warning"),
    (r"生命周期|新品|老品|迭代|升级", "lifecycle"),
    (r"促销|折扣|Coupon|优惠|降价", "promotion_effectiveness"),
    (r"库存|缺货|积压|周转", "inventory_intelligence"),
    (r"季节|时机|淡季|旺季|最佳.*时间", "market_timing"),
    (r"变体|颜色|尺寸|款式|SKU.*覆盖", "variation_strategy"),
    (r"类目|类目结构|子类目|类目树", "category"),
    (r"风险|预警|危险|合规|安全", "risk_warning"),
    (r"卖家|跟卖|VC|供货", "seller_behavior"),
    (r"异常|波动|跳变|突变", "anomaly_alerts"),
    (r"合规|认证|CE|FCC|RoHS|UL", "compliance"),
    (r"市场规模|体量|月销|年销|销售|营收|GMV", "demand_analysis"),
    (r"特征|卖点|功能|材料|颜色|尺寸|属性", "product_attribute"),
    (r"品牌.*分布|品牌.*分析|品牌.*格局", "competition_landscape"),
]

_DEPTH_RULES = [
    (r"全面|详细|彻底|深度|深入", AnalysisDepth.DEEP),
    (r"快速|简单|大概|概览|扫一眼", AnalysisDepth.BASIC),
]

# ── LLM 回退分类 prompt ──

_LLM_CLASSIFY_PROMPT = """你是一个意图分类器。分析用户输入，输出 JSON。

输入: {query}

分析要求：
1. 判断用户意图类型
2. 从以下 33 方向中选择相关的分析方向
3. 判断分析深度
4. 识别主线方向

输出格式（严格 JSON，不要多余文本）：
{{
    "intent_type": "market_analysis|deepen|focus_entity|multi_dim|product_research|competitor_watch|general_query",
    "dimensions": ["方向ID列表"],
    "depth": "basic|moderate|deep|comprehensive",
    "primary_dim": "主线方向ID",
    "entities": ["关注的实体列表"],
    "focus_description": "一句话描述分析焦点"
}}
"""


class IntentClassifier:
    """意图分类器——规则引擎 + LLM fallback"""

    def __init__(self):
        self.llm = None  # 懒加载

    def classify(self, query: str, history_context: Optional[str] = None) -> IntentAnalysisSpec:
        """分类用户输入 → IntentAnalysisSpec"""
        # Step 1: 规则引擎快速分类（零 LLM）
        spec = self._rule_based_classify(query)

        # Step 2: 如果规则引擎结果不确定（general_query），或维度太少需要 LLM 补充
        if spec.intent_type == IntentType.GENERAL_QUERY or len(spec.dimensions) < 2:
            llm_spec = self._llm_classify(query)
            if llm_spec:
                # 合并 LLM 提取的额外维度、实体、主线方向
                llm_dims = [d for d in llm_spec.dimensions if d not in spec.dimensions]
                spec.dimensions.extend(llm_dims)
                if llm_spec.entities:
                    spec.entities = list(set(spec.entities + llm_spec.entities))
                if llm_spec.primary_dim and not spec.primary_dim:
                    spec.primary_dim = llm_spec.primary_dim
                if llm_spec.focus_description:
                    spec.focus_description = llm_spec.focus_description

        spec.raw_query = query

        # Step 3: 如果历史上下文表明是增量分析
        if history_context and self._detect_incremental(query, history_context):
            spec.is_incremental = True

        return spec

    def _rule_based_classify(self, query: str) -> IntentAnalysisSpec:
        """规则引擎初步分类——关键词匹配，零 LLM"""
        query_lower = query.lower()

        # 意图匹配
        intent = IntentType.GENERAL_QUERY
        for pattern, matched_intent in _INTENT_RULES:
            if re.search(pattern, query_lower):
                intent = matched_intent
                break

        # 方向匹配
        dimensions = []
        for pattern, dim in _DIRECTION_RULES:
            if re.search(pattern, query_lower):
                dimensions.append(dim)

        # 深度匹配
        depth = AnalysisDepth.MODERATE
        for pattern, matched_depth in _DEPTH_RULES:
            if re.search(pattern, query_lower):
                depth = matched_depth
                break

        # 主线方向：第一个匹配的方向
        primary_dim = dimensions[0] if dimensions else ""

        # 实体提取：引号内的词 + ASIN
        entities = re.findall(r'[""]([^""]+)[""]', query)
        asin_match = re.findall(r'\bB[A-Z0-9]{9}\w?\b', query.upper())
        if asin_match:
            entities = list(set(entities + asin_match[:5]))
        if not entities:
            # 品牌名：中文或英文大写开头的连续词
            brand_match = re.findall(r'\b([A-Z][a-z]+(?:\s[A-Z][a-z]+)*)\b', query)
            entities = [b for b in brand_match if b.lower() not in
                       ("分析", "重点", "看", "查", "对比", "比较")][:3]

        return IntentAnalysisSpec(
            intent_type=intent,
            dimensions=dimensions,
            depth=depth,
            primary_dim=primary_dim,
            entities=entities,
            focus_description=query[:200],
        )

    def _llm_classify(self, query: str) -> Optional[IntentAnalysisSpec]:
        """LLM 回退分类——用 gpt-5.4-mini-high"""
        try:
            if self.llm is None:
                self.llm = get_prompt_engine_llm()
            if self.llm is None:
                return None

            prompt = _LLM_CLASSIFY_PROMPT.format(query=query)
            response = self.llm.invoke(prompt)
            content = response.content.strip()

            # 提取 JSON
            if content.startswith("```"):
                content = content.split("\n", 1)[-1].rsplit("```", 1)[0].strip()

            import json
            data = json.loads(content)

            return IntentAnalysisSpec(
                intent_type=IntentType(data.get("intent_type", "general_query")),
                dimensions=data.get("dimensions", []),
                depth=AnalysisDepth(data.get("depth", "moderate")),
                primary_dim=data.get("primary_dim", ""),
                entities=data.get("entities", []),
                focus_description=data.get("focus_description", query[:200]),
            )
        except Exception:
            return None

    def _detect_incremental(self, query: str, history_context: str) -> bool:
        """检测是否是增量分析"""
        incremental_patterns = [
            r"上[次回轮]",
            r"再.*(看|分析|查)",
            r"继续|接着|深入",
            r"那.*呢$",
            r"还.*(呢|吗|怎么样)",
            r"具体|更.*多|进一步",
            r"价格呢|评论呢|竞品呢",
        ]
        return any(re.search(p, query) for p in incremental_patterns)

    def classify_dimensions(self, query: str) -> List[str]:
        """只做维度分类（快捷方法）"""
        return self._rule_based_classify(query).dimensions