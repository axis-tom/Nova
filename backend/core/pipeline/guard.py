"""
PipelineGuard — Pipeline 执行强制守护

铁律：PIPELINE MUST BE THE ONLY SOURCE OF TRUTH

对于 analysis 类 intent，Pipeline 是唯一强制执行路径。
不允许：
  - Pipeline 被绕过 → 裸数据输出
  - Pipeline 失败 → 优雅降级到 ReAct
  - Router 未匹配 → LLM 自己玩

只允许：
  - Pipeline 执行成功 → DecisionCard 输出
  - Pipeline 执行失败 → 硬错误，不 fallback
"""
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional, Set
from enum import Enum


class TaskCategory(str, Enum):
    """任务分类 — 决定是否强制执行 Pipeline"""
    # ── 必须走 Pipeline 的分析类 ──
    ANALYSIS = "analysis"             # 产品/市场分析
    REANALYSIS = "reanalysis"         # 重新分析
    MARKET_ANALYSIS = "market_analysis"

    # ── 可选走 Pipeline 的数据查询类 ──
    DATA_QUERY = "data_query"         # 纯数据查询

    # ── 不走 Pipeline 的对话类 ──
    GENERAL_CHAT = "general_chat"     # 闲聊/新问题


# ── intent_type → TaskCategory 映射 ──
# ★ 这里定义了哪些 intent 必须走 Pipeline
INTENT_TO_CATEGORY: Dict[str, TaskCategory] = {
    "product_research": TaskCategory.ANALYSIS,
    "focus_entity": TaskCategory.ANALYSIS,
    "market_analysis": TaskCategory.MARKET_ANALYSIS,
    "multi_dim": TaskCategory.ANALYSIS,
    "competitor_watch": TaskCategory.ANALYSIS,
    "deepen": TaskCategory.ANALYSIS,
    "general_query": TaskCategory.GENERAL_CHAT,
}


@dataclass
class PipelineGuardResult:
    """
    PipelineGuard 的执行结果

    包含：
      - must_run_pipeline: bool — 是否强制走 Pipeline
      - category: TaskCategory — 任务分类
      - intent_type: str — 原始 intent type
      - validation_errors: List[str] — 校验错误（如果 Pipeline 执行失败）
    """
    must_run_pipeline: bool = False
    category: TaskCategory = TaskCategory.GENERAL_CHAT
    intent_type: str = ""
    validation_errors: List[str] = field(default_factory=list)

    @property
    def is_valid(self) -> bool:
        """Pipeline 执行结果是否有效"""
        return len(self.validation_errors) == 0


# ── DecisionCard Schema ──
# ★ 所有 Pipeline 的输出必须符合此结构


DECISION_CARD_SCHEMA = {
    "decision": {
        "type": "object",
        "required": ["conclusion", "score", "confidence"],
        "properties": {
            "conclusion": {"type": "string", "enum": ["做", "不做", "观望"]},
            "score": {"type": "number", "minimum": 0, "maximum": 100},
            "confidence": {"type": "string", "enum": ["高", "中", "低"]},
        },
    },
    "evidence": {
        "type": "object",
        "required": ["market_volume", "competition", "price_structure"],
        "properties": {
            "market_volume": {"type": "object"},
            "competition": {"type": "object"},
            "price_structure": {"type": "object"},
        },
    },
    "risks": {"type": "array"},
    "action_paths": {"type": "array"},
}


@dataclass
class DecisionCard:
    """
    决策卡 — Pipeline 的唯一输出格式

    ★ 前端只渲染 DecisionCard，不渲染 raw tool output
    ★ LLM 注释只是 DecisionCard 的补充，不是替代品
    """
    # ── 决策结论 ──
    conclusion: str = ""         # "做" / "不做" / "观望"
    score: int = 0               # 0-100
    confidence: str = "中"        # "高" / "中" / "低"

    # ── 决策依据 ──
    positives: List[str] = field(default_factory=list)
    negatives: List[str] = field(default_factory=list)
    entry_routes: List[Dict[str, Any]] = field(default_factory=list)

    # ── 关键证据摘要 ──
    evidence_summary: Dict[str, Any] = field(default_factory=dict)

    # ── 风险清单 ──
    risks: List[Dict[str, str]] = field(default_factory=list)

    # ── LLM 注释（可选） ──
    llm_commentary: str = ""

    # ── 原始结构化数据（用于前端渲染） ──
    raw_structured: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_pipeline_result(cls, structured: Dict[str, Any], llm_commentary: str) -> "DecisionCard":
        """从 PipelineResult.structured 构建 DecisionCard"""
        decision = structured.get("decision_support", {})
        deterministic = structured.get("deterministic", {})

        # 提取证据摘要
        evidence = {}
        mv = deterministic.get("market_volume", {})
        if mv:
            evidence["market_volume"] = {
                "monthly_units": mv.get("total_monthly_units"),
                "monthly_revenue": mv.get("estimated_monthly_revenue"),
                "product_count": mv.get("product_count"),
                "avg_price": mv.get("avg_price"),
            }
        bc = deterministic.get("brand_concentration", {})
        if bc:
            evidence["competition"] = {
                "top3_share": bc.get("top_3_market_share_pct"),
                "concentration": bc.get("concentration"),
                "total_brands": bc.get("total_brands"),
            }
        pb = deterministic.get("price_bands", {})
        if pb:
            evidence["price_structure"] = pb

        return cls(
            conclusion=decision.get("label", ""),
            score=decision.get("market_entry_score", 0),
            confidence="高" if decision.get("market_entry_score", 0) >= 70
            else "中" if decision.get("market_entry_score", 0) >= 40
            else "低",
            positives=decision.get("positives", []),
            negatives=decision.get("negatives", []),
            entry_routes=decision.get("entry_routes", []),
            evidence_summary=evidence,
            risks=deterministic.get("risks", []),
            llm_commentary=llm_commentary,
            raw_structured=structured,
        )

    def to_dict(self) -> Dict[str, Any]:
        """序列化为前端可渲染的 dict"""
        return {
            "type": "decision_card",
            "data": {
                "decision": {
                    "conclusion": self.conclusion,
                    "score": self.score,
                    "confidence": self.confidence,
                },
                "evidence": self.evidence_summary,
                "positives": self.positives,
                "negatives": self.negatives,
                "entry_routes": self.entry_routes,
                "risks": self.risks,
                "llm_commentary": self.llm_commentary,
            },
        }

    def validate(self) -> List[str]:
        """校验 DecisionCard 是否完整有效"""
        errors = []
        if not self.conclusion:
            errors.append("决策卡缺少结论 (conclusion)")
        if not self.score and self.score != 0:
            errors.append("决策卡缺少评分 (score)")
        if not self.evidence_summary.get("market_volume"):
            errors.append("决策卡缺少市场体量证据 (market_volume)")
        if not self.evidence_summary.get("competition"):
            errors.append("决策卡缺少竞争结构证据 (competition)")
        if not self.risks:
            errors.append("决策卡缺少风险清单 (risks)")
        return errors


# ── PipelineGuard ──


class PipelineGuard:
    """
    Pipeline 执行强制守护

    职责：
      1. 判断当前任务是否必须走 Pipeline
      2. 如果必须走但没有 Pipeline 结果 → 硬错误
      3. 验证 Pipeline 输出是否符合 DecisionCard schema
      4. 禁用 ReAct fallback（对于 analysis 类任务）
    """

    ANALYSIS_INTENTS: Set[str] = {
        "product_research", "focus_entity", "market_analysis",
        "multi_dim", "competitor_watch", "deepen",
    }

    def __init__(self, intent_type: str):
        self.intent_type = intent_type
        self.category = INTENT_TO_CATEGORY.get(intent_type, TaskCategory.GENERAL_CHAT)
        self.must_run_pipeline = self.category in (
            TaskCategory.ANALYSIS, TaskCategory.REANALYSIS, TaskCategory.MARKET_ANALYSIS,
        )

    def check(self, pipeline_result: Optional[Any] = None,
              found_asins: Optional[List[str]] = None) -> PipelineGuardResult:
        """
        执行 Pipeline 强制校验

        Args:
            pipeline_result: Pipeline 执行结果（None 表示 Pipeline 未执行）
            found_asins: 可选的 ASIN 列表（用于判断是否有数据可分析）

        Returns:
            PipelineGuardResult — 包含校验结果
        """
        result = PipelineGuardResult(
            must_run_pipeline=self.must_run_pipeline,
            category=self.category,
            intent_type=self.intent_type,
        )

        # ── 非 analysis 类 → 不强制校验 ──
        if not self.must_run_pipeline:
            return result

        # ── Guard 1: Pipeline 必须执行 ──
        if pipeline_result is None:
            if found_asins:
                result.validation_errors.append(
                    f"PIPELINE GUARD: intent={self.intent_type}, "
                    f"found_asins={len(found_asins)}, BUT pipeline was NOT executed. "
                    f"Analysis tasks MUST go through Pipeline."
                )
            else:
                result.validation_errors.append(
                    f"PIPELINE GUARD: intent={self.intent_type}, "
                    f"but no ASIN data found. Cannot produce DecisionCard without data."
                )
            return result

        # ── Guard 2: Pipeline 必须有结构化输出 ──
        structured = getattr(pipeline_result, 'structured', None)
        if not structured:
            result.validation_errors.append(
                f"PIPELINE GUARD: Pipeline executed but structured output is empty"
            )
            return result

        # ── Guard 3: 必须有 decision_support（评分） ──
        decision = structured.get("decision_support", {})
        if not decision or not decision.get("market_entry_score"):
            result.validation_errors.append(
                f"PIPELINE GUARD: Pipeline structured output missing decision_support. "
                f"Keys present: {list(structured.keys())}"
            )
            return result

        # ── Guard 4: 必须有 deterministic 维度 ──
        deterministic = structured.get("deterministic", {})
        if not deterministic:
            result.validation_errors.append(
                f"PIPELINE GUARD: Pipeline structured output missing deterministic data. "
                f"Keys present: {list(structured.keys())}"
            )
            return result

        # ── Guard 5: 必须有 market_volume（最基础的证据） ──
        if not deterministic.get("market_volume"):
            result.validation_errors.append(
                f"PIPELINE GUARD: Pipeline deterministic output missing market_volume. "
                f"Deterministic keys: {list(deterministic.keys())}"
            )
            return result

        return result

    @property
    def disable_react(self) -> bool:
        """analysis 类任务必须禁用 ReAct fallback"""
        return self.must_run_pipeline

    @staticmethod
    def format_guard_error(result: PipelineGuardResult) -> str:
        """格式化为用户可见的错误消息"""
        lines = [
            "🚨 系统执行路径异常：Pipeline 未产生有效决策卡",
            "",
        ]
        for err in result.validation_errors:
            lines.append(f"- {err}")
        lines.append("")
        lines.append("系统无法对此请求生成分析结论。")
        return "\n".join(lines)