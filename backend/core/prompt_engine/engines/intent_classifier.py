"""
IntentClassifier — 意图理解模块

策略：
1. LLM 主路径：每次调用用 gpt-5.4-mini-high 理解意图（自然语言输出）
2. 规则引擎辅助：只做实体提取（ASIN/引号）和深度匹配 — 这些 regex 比 LLM 更可靠
3. LLM 不可用时降级到纯规则引擎
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
    depth: AnalysisDepth = AnalysisDepth.MODERATE
    entities: List[str] = field(default_factory=list)

    # ── 自然语言字段 ──
    paraphrased_intent: str = ""     # LLM 对用户意图的重新表述
    category_hint: str = ""          # 品类数据范围提示（中文，供 DataLiaison 解析用）

    # ── 已废弃字段（保持兼容，不参与序列化） ──
    dimensions: List[str] = field(default_factory=list)
    primary_dim: str = ""
    focus_description: str = ""
    analysis_hint: str = ""
    is_incremental: bool = False
    previous_dimensions: List[str] = field(default_factory=list)
    raw_query: str = ""


# ── 规则引擎：只做 regex 可靠的辅助工作 ──

_DEPTH_RULES = [
    (r"全面|详细|彻底|深度|深入", AnalysisDepth.DEEP),
    (r"快速|简单|大概|概览|扫一眼", AnalysisDepth.BASIC),
]

# ── LLM 意图理解 prompt ──

_LLM_CLASSIFY_PROMPT = """你是一个意图理解助手。分析用户关于亚马逊电商的输入。

输入: {query}

输出格式（严格 JSON，不要多余文本）：
{{
    "intent_type": "market_analysis|deepen|focus_entity|multi_dim|product_research|competitor_watch|general_query",
    "depth": "basic|moderate|deep|comprehensive",
    "entities": ["关注的实体名称列表（品牌名、品类名、ASIN）"],
    "paraphrased_intent": "用一句话重新表述用户想做什么（不要预设分析方向，只描述意图）",
    "category_hint": "中文品类名提示（如'手机支架'），仅当用户需要分析某个品类时提供；如果用户问的是具体 ASIN（entities 含 B0xxx 格式），category_hint 留空"
}}

规则：
- 如果 entities 中包含 ASIN（B0xxx 格式），说明用户是在问具体产品。此时 **category_hint 必须留空**，不要再编造任何文本。
- 如果 entities 中只有品类名/品牌名（无 ASIN），category_hint 如实填写。
- paraphrased_intent: 要中立，如"用户想了解蓝牙耳机类目各品牌的表现"或"用户查询 ASIN B0xxx 的产品数据"
- entities: 提取品牌名、品类名、ASIN
- 不要输出旧字段 dimensions/primary_dim/focus_description/analysis_hint——它们已废弃
"""


class IntentClassifier:
    """意图理解器——LLM 主路径 + 规则引擎辅助"""

    def __init__(self):
        self.llm = None  # 懒加载

    def classify(self, query: str, history_context: Optional[str] = None) -> IntentAnalysisSpec:
        """分类用户输入 → IntentAnalysisSpec

        流程：
        1. LLM 主路径：理解用户意图，输出自然语言描述
        2. 规则引擎辅助：实体提取（ASIN/引号）覆盖 LLM 可能遗漏的
        3. LLM 不可用时降级到纯规则引擎（只做实体+深度）
        4. 增量检测
        """
        # Step 1: LLM 主路径
        spec = self._llm_classify(query)

        # Step 2: LLM 失败时降级
        if spec is None:
            spec = self._rule_based_classify(query)

        # Step 3: 规则引擎辅助（实体提取比 LLM 更精确）
        rule_spec = self._rule_based_classify(query)
        if rule_spec.entities:
            spec.entities = list(set(spec.entities + rule_spec.entities))
        # 规则引擎的深度匹配作为兜底（如果 LLM 没识别出用户说的"快速/全面"）
        if rule_spec.depth != AnalysisDepth.MODERATE and spec.depth == AnalysisDepth.MODERATE:
            spec.depth = rule_spec.depth

        spec.raw_query = query

        # Step 4: 增量检测
        if history_context and self._detect_incremental(query, history_context):
            spec.is_incremental = True

        return spec

    def _rule_based_classify(self, query: str) -> IntentAnalysisSpec:
        """规则引擎辅助分类——只做 regex 比 LLM 更可靠的事

        不做方向映射，不做 intent_type 判断（这些交给 LLM）。
        只做：
        - 实体提取（ASIN 正则、引号内容、品牌名）
        - 深度匹配（用户明确说"全面/快速"）
        """
        query_lower = query.lower()

        # 深度匹配
        depth = AnalysisDepth.MODERATE
        for pattern, matched_depth in _DEPTH_RULES:
            if re.search(pattern, query_lower):
                depth = matched_depth
                break

        # 实体提取：引号内的词 + ASIN
        entities = re.findall(r'[""]([^""]+)[""]', query)
        asin_match = re.findall(r'(?<![A-Za-z0-9])B[A-Z0-9]{9}[A-Z0-9]?(?![A-Za-z0-9])', query.upper())
        if asin_match:
            entities = list(set(entities + asin_match[:5]))
        if not entities:
            # 品牌名：中文或英文大写开头的连续词
            brand_match = re.findall(r'\b([A-Z][a-z]+(?:\s[A-Z][a-z]+)*)\b', query)
            entities = [b for b in brand_match if b.lower() not in
                       ("分析", "重点", "看", "查", "对比", "比较")][:3]

        return IntentAnalysisSpec(
            intent_type=IntentType.GENERAL_QUERY,  # 规则引擎不再判断类型
            depth=depth,
            entities=entities,
            paraphrased_intent="",    # 规则引擎不产生自然语言
            analysis_hint="",
        )

    def _llm_classify(self, query: str) -> Optional[IntentAnalysisSpec]:
        """LLM 主路径——用 gpt-5.4-mini-high 理解意图"""
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
                depth=AnalysisDepth(data.get("depth", "moderate")),
                entities=data.get("entities", []),
                paraphrased_intent=data.get("paraphrased_intent", ""),
                category_hint=data.get("category_hint", ""),
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