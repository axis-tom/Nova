"""
PromptEngine — 6 个模块的协调器

用法：
    engine = PromptEngine()
    spec = engine.translate("分析蓝牙耳机，重点看定价", session_id="conv_xxx")
    system_prompt = engine.customize("market_analyst", spec)
    engine.evaluate("conv_xxx", spec, {"result": ...})

核心接口：
1. translate() — 用户输入 → IntentAnalysisSpec
2. customize() — IntentAnalysisSpec → 定制 system prompt
3. build_orchestrator_prompt() — IntentAnalysisSpec → orchestrator 的 system prompt
4. evaluate() — 对话结束后评估效果
"""

from typing import Dict, Any, Optional

from backend.core.prompt_engine.engines.intent_classifier import (
    IntentClassifier,
    IntentAnalysisSpec,
    IntentType,
    AnalysisDepth,
)
from backend.core.prompt_engine.engines.prompt_customizer import PromptCustomizer
from backend.core.prompt_engine.engines.incremental_tracker import IncrementalTracker
from backend.core.prompt_engine.engines.evaluator import Evaluator
from backend.core.prompt_engine.engines.weight_learner import WeightLearner
from backend.core.prompt_engine.dimension_registry import get_dimension_registry


class PromptEngine:
    """
    Agent System Prompt 动态定制引擎—6 个模块的协调器。

    两套模型各司其职：
    - Prompt Engine（翻译层）：gpt-5.4-mini-high — 便宜小模型做意图分类
    - Agent 分析层：gpt-5.2 / claude-sonnet-4-6 / claude-opus-4-6 — 强模型做分析
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self.classifier = IntentClassifier()
        self.tracker = IncrementalTracker()
        self.customizer = PromptCustomizer()
        self.evaluator = Evaluator()
        self.learner = WeightLearner()
        self.dimensions = get_dimension_registry()

    # ════════════════════════════════════════════════════════════════
    # 核心接口 1: translate — 用户输入 → 意图分析规格
    # ════════════════════════════════════════════════════════════════

    def translate(
        self,
        raw_input: str,
        session_id: Optional[str] = None,
    ) -> IntentAnalysisSpec:
        """
        用户输入 → 意图分析规格。

        流程：
        1. 规则引擎初步分类（关键词匹配，零 LLM）
        2. 边界模糊时调 gpt-5.4-mini-high（LLM 分类）
        3. 如果有历史对话 → 增量标记
        4. WeightLearner 优化策略选择
        """
        # Step 1: 获取历史上下文
        history_context = ""
        previous_dims = []
        if session_id:
            summary = self.tracker.get_trace_summary(session_id)
            previous_dims = summary.get("dimensions", [])
            if summary.get("rounds", 0) > 0:
                history_context = f"历史已分析维度: {', '.join(previous_dims[:5])}"

        # Step 2: 规则引擎 + LLM fallback 分类
        spec = self.classifier.classify(raw_input, history_context)

        # Step 3: 增量标记
        if session_id and self.tracker.is_incremental_possible(session_id):
            spec.is_incremental = True
            spec.previous_dimensions = previous_dims

        # Step 4: WeightLearner 优化策略选择
        if spec.primary_dim:
            # 将 primary_dim 映射到策略名
            strategy = f"{spec.primary_dim}_first"
            if strategy not in self.learner.weights:
                # 不在权重表中的方向用 balanced
                pass  # 保持默认

        # Step 5: 追踪
        if session_id:
            self.tracker.start_trace(session_id, raw_input)

        return spec

    # ════════════════════════════════════════════════════════════════
    # 核心接口 2: customize — IntentAnalysisSpec → 定制 system prompt
    # ════════════════════════════════════════════════════════════════

    def customize(
        self,
        agent_name: str,
        spec: IntentAnalysisSpec,
        session_id: Optional[str] = None,
    ) -> str:
        """
        IntentAnalysisSpec → 定制 system prompt。

        流程：
        1. PromptCustomizer 加载 agent.prompty 模板
        2. 注入 spec 中的维度+权重+增量标记
        3. 返回渲染后的完整 system prompt（不含产品数据部分）
        """
        system_prompt = self.customizer.customize(
            agent_name=agent_name,
            dimensions=spec.dimensions,
            primary_dim=spec.primary_dim,
            is_incremental=spec.is_incremental,
        )

        # 追踪 Span
        if session_id:
            self.tracker.start_span(
                session_id=session_id,
                agent_name=agent_name,
                input_text=spec.focus_description,
                dimensions=spec.dimensions,
                is_incremental=spec.is_incremental,
            )

        return system_prompt

    # ════════════════════════════════════════════════════════════════
    # 核心接口 3: build_orchestrator_prompt — 动态组装 orchestrator system prompt
    # ════════════════════════════════════════════════════════════════

    def build_orchestrator_prompt(
        self,
        spec: IntentAnalysisSpec,
        agents_info: Optional[list] = None,
        memory_context: str = "",
        state_summary: str = "",
    ) -> str:
        """
        根据 IntentAnalysisSpec 动态生成 orchestrator 的 system prompt。
        """
        dim_name = self.dimensions.get_dim_name(spec.primary_dim) if spec.primary_dim else "综合"
        category_hint = ""
        if spec.entities:
            category_hint = f"（关注实体：{', '.join(spec.entities[:3])}）"

        # ── 角色设定 + 用户意图 → 分析方向 ──
        prompt_parts = [
            f"# 任务：Amazon 电商智能分析\n\n"
            f"## 用户需求\n{spec.raw_query}\n\n"
            f"## 意图分析\n"
            f"- 分析类型：{self._intent_label(spec.intent_type)}\n"
            f"- 分析深度：{spec.depth.value}\n"
            f"- 主线方向：{dim_name}\n"
            f"- 辅助方向：{', '.join(self.dimensions.get_dim_name(d) for d in spec.dimensions if d != spec.primary_dim) or '无'}\n"
            f"- 关注对象：{', '.join(spec.entities) if spec.entities else '根据分析目标自动确定'}"
            f"{category_hint}\n\n"
            f"## 你的角色\n"
            f"你是总指挥（Orchestrator）。你的工作流程：\n"
            f"1. **分析需求**：根据上方意图分析，思考本次需要分析哪些方向+维度\n"
            f"2. **规划 Agent**：决定需要调哪些 Agent 来完成这些维度的分析\n"
            f"3. **派发任务**：按顺序调 Agent，每个 Agent 去数据库获取对应数据并分析\n"
            f"4. **检查结果**：看 Agent 的分析结果是否达到要求——如果某维度分析结果为空或不足，重新尝试或换角度\n"
            f"5. **汇总输出**：所有维度分析完成后，给出结构化中文报告\n\n"
            f"## Agent 调用策略\n"
            f"数据已预采集在数据库中，调 Agent 时传入空 params 即可从 state 读取数据：\n"
            f"1. **review_analyzer** — 评论分析（情感、壁垒、评分定位）\n"
            f"2. **traffic_analyzer** — 流量分析（BSR分布、价格分布）\n"
            f"3. **market_analyst** — 市场分析（品牌份额、价格带、趋势）\n"
            f"4. **competitor_analyst** — 竞品分析（市场份额、Listing质量）\n"
            f"5. **opportunity_judge** — 综合评分（各维度评分+选品推荐）\n"
            f"6. **briefing_generator** — 生成最终报告\n\n"
            f"## 注意\n"
            f"- 如果 state 中有 collected_products 说明数据已就绪，直接调分析 Agent\n"
            f"- 每个 Agent 完成后检查输出，如果结果为空说明缺少数据，尝试其他路径\n"
            f"- 最终回答结构化、中文、含关键数据表"
        ]
        system_prompt = "\n\n".join(prompt_parts)

        if memory_context:
            system_prompt += f"\n\n{memory_context}"
        if state_summary:
            system_prompt += f"\n\n{state_summary}"

        return system_prompt

    def _build_agents_section(self, spec: IntentAnalysisSpec, agents_info: list) -> str:
        """构建可用 Agent 说明"""
        # 获取本次涉及的 Agent
        affected = self.dimensions.get_affected_agents(spec.dimensions)
        affected_names = set(affected.keys())

        # 总是需要的 Agent
        needed = {"keyword_expander", "product_collector", "briefing_generator"}
        affected_names.update(needed)

        lines = ["【可用 Agent】（本次分析涉及以下 Agent）："]

        for a in agents_info:
            name = a["name"]
            if name not in affected_names:
                continue
            # 获取该 Agent 在本轮中的定制指令
            extra = ""
            if spec.primary_dim:
                agent_prompt = self.dimensions.get_agent_prompt(spec.primary_dim, name)
                if agent_prompt:
                    extra = f" → {agent_prompt[:80]}..."
            lines.append(f"  - {name}: {a['description']}{extra}")

        return "\n".join(lines)

    # ════════════════════════════════════════════════════════════════
    # 核心接口 4: evaluate — 对话结束后评估效果
    # ════════════════════════════════════════════════════════════════

    def evaluate(
        self,
        conversation_id: str,
        spec: IntentAnalysisSpec,
        result: Dict[str, Any],
    ):
        """对话结束后评估效果"""
        # 结束追踪
        self.tracker.end_trace(conversation_id)

        # 更新 WeightLearner
        if spec.primary_dim:
            strategy = f"{spec.primary_dim}_first"
            # 从 result 中提取 score（如果有）
            score = result.get("quality_score", 0.7)
            self.learner.update_score(strategy, score)

    # ════════════════════════════════════════════════════════════════
    # 工具方法
    # ════════════════════════════════════════════════════════════════

    @staticmethod
    def _intent_label(intent_type: IntentType) -> str:
        """获取意图类型的中文标签"""
        labels = {
            IntentType.MARKET_ANALYSIS: "市场分析",
            IntentType.DEEPEN: "深化分析",
            IntentType.FOCUS_ENTITY: "聚焦实体",
            IntentType.MULTI_DIM: "多维分析",
            IntentType.PRODUCT_RESEARCH: "产品调研",
            IntentType.COMPETITOR_WATCH: "竞品监控",
            IntentType.GENERAL_QUERY: "通用查询",
        }
        return labels.get(intent_type, "通用查询")