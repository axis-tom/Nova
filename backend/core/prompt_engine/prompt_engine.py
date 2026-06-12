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
        # dimension_registry 不再用于 prompt 生成，仅保留引用防止旧代码报错
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
    # 核心接口 2: customize — IntentAnalysisSpec/子任务 → 定制 system prompt
    # ════════════════════════════════════════════════════════════════

    def customize(
        self,
        agent_name: str,
        spec: Optional[IntentAnalysisSpec] = None,
        session_id: Optional[str] = None,
        # ── 新参数（推荐） ──
        sub_task: str = "",
    ) -> str:
        """
        IntentAnalysisSpec/子任务 → 定制 system prompt。

        推荐新用法（自然语言子任务）：
            custom_prompt = pe.customize("review_analyzer", sub_task="重点分析评论中关于价格的信号")

        旧用法（向后兼容）：
            custom_prompt = pe.customize("market_analyst", spec)

        流程：
        1. 如果有 sub_task（新路径），直接注入 orchestrator 分配的自然语言子任务
        2. 否则从 spec 中读取旧字段（维度 ID → 已废弃，走空值兼容）
        3. 返回渲染后的完整 system prompt（不含产品数据部分）
        """
        if sub_task:
            # ★ 新路径：自然语言子任务
            system_prompt = self.customizer.customize(
                agent_name=agent_name,
                sub_task=sub_task,
                is_incremental=spec.is_incremental if spec else False,
            )
        elif spec:
            # 旧路径（向后兼容）
            system_prompt = self.customizer.customize(
                agent_name=agent_name,
                dimensions=spec.dimensions,
                primary_dim=spec.primary_dim,
                is_incremental=spec.is_incremental,
            )
        else:
            # 无 spec 无 sub_task → 默认模板
            system_prompt = self.customizer.customize(
                agent_name=agent_name,
            )

        # 追踪 Span
        if session_id and spec:
            self.tracker.start_span(
                session_id=session_id,
                agent_name=agent_name,
                input_text=sub_task or spec.focus_description,
                dimensions=spec.dimensions if not sub_task else [],
                is_incremental=spec.is_incremental,
            )
        elif session_id and sub_task:
            self.tracker.start_span(
                session_id=session_id,
                agent_name=agent_name,
                input_text=sub_task,
                dimensions=[],
                is_incremental=False,
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

        生成逻辑按 intent_type 分模板：
        - focus_entity → 执行模板（数据就绪，直接获取呈现）
        - market_analysis → 分析师模板（规划分析路径，多 Agent 覆盖）
        - deepen → 跟进模板（已有结果上深化）
        - multi_dim → 总指挥模板（全维度流水线）
        - product_research → 调研模板（单品深度挖掘）
        - competitor_watch → 监控模板（竞品对比）
        - general_query → 探索模板（先看看有什么可用）
        """

        # ── 1. 意图描述（自然语言） ──
        parsed_intent = spec.paraphrased_intent or spec.raw_query[:200]
        intent_section = f"""## 用户原始需求
{spec.raw_query}

## 意图理解
{parsed_intent}"""

        # ── 2. 数据状态（state_summary 注入到此，让 LLM 先看到数据再读指令） ──
        data_section = ""
        if state_summary:
            data_section = state_summary

        # ── 3. 字段总览（精简，所有意图共享） ──
        field_section = """## 数据库中已有的数据字段（按组分类，供规划分析路径时参考）
- **价格类**: current_price, buybox_price, avg_price_30d/90d/180d/365d, list_price, min_price, max_price, has_coupon, buybox_winner
- **BSR/销量**: current_bsr, avg_bsr_30d/90d/180d/365d, bsr_trend, monthly_sold, weekly_sold, annual_sold, sales_rank_history
- **评论类**: rating, review_count, rating_breakdown, review_velocity_30d, top_reviews, customers_say, rating_history
- **卖家/Offer**: seller_count, offer_count_fba/fbm, buybox_seller_id, buybox_seller_name, has_amazon_selling, has_china_sellers
- **Listing**: title, brand, feature_bullets, description, images_count, videos_count, aplus_content, specifications
- **配送/变体/品牌/属性/促销/库存**: 详细信息建议调 Agent 获取，Agent 会自动从本地表加载"""

        # ── 4. 角色设定（按 intent_type 分模板） ──
        role_section = self._build_role_section(spec)

        # ── 5. Agent 能力清单 ──
        agent_lines = []
        if agents_info:
            for a in agents_info:
                agent_lines.append(f"- **{a['name']}**: {a['description']}")
        else:
            agent_lines = [
                "- **review_analyzer**: 评论分析（情感、壁垒、评分定位）",
                "- **traffic_analyzer**: 流量分析（BSR分布、价格分布）",
                "- **market_analyst**: 市场分析（品牌份额、价格带、趋势）",
                "- **competitor_analyst**: 竞品分析（市场份额、Listing质量）",
                "- **opportunity_judge**: 综合评分（各维度评分+选品推荐）",
                "- **briefing_generator**: 生成最终报告",
            ]
        agent_section = "## 可调用的 Agent\n" + "\n".join(agent_lines)

        # ── 组装（关键：state_summary 在 role 之前，LLM 先看数据再看怎么干） ──
        prompt_parts = ["# 任务：Amazon 电商智能分析", intent_section]
        if data_section:
            prompt_parts.append(data_section)
        prompt_parts.extend([
            field_section,
            role_section,
            agent_section,
        ])
        system_prompt = "\n\n".join(prompt_parts)

        if memory_context:
            system_prompt += f"\n\n{memory_context}"

        return system_prompt

    def _build_role_section(self, spec: IntentAnalysisSpec) -> str:
        """按意图类型动态生成角色设定模板

        统一模板（不再分数据执行模式/分析模式）：
        LLM 永远通过工具获取数据，不从上下文或记忆"编造"。
        intent_type 只影响任务背景描述，不影响"必须调工具"的规则。
        """

        # ── 从 intent_type 推断任务背景 ──
        intent_hints = {
            IntentType.FOCUS_ENTITY: "用户想查询某个具体 ASIN 的数据。**第一步永远调 get_entity_details** 获取真实数据。",
            IntentType.MARKET_ANALYSIS: "用户想了解市场全貌。分析方向包括品牌格局、价格分布、竞争态势、选品机会等。",
            IntentType.DEEPEN: "用户希望对已有的分析结果进一步深入。回顾已有数据，聚焦用户要求的新方向，不要重复已覆盖的分析。",
            IntentType.MULTI_DIM: "用户希望从多个角度一次性覆盖分析。规划覆盖哪些维度，按序进行。",
            IntentType.PRODUCT_RESEARCH: "用户想深度调研特定产品。获取产品数据后评估其市场表现、竞争力和机会。",
            IntentType.COMPETITOR_WATCH: "用户想对比分析竞品。关注差异化维度：定价、评分、BSR、卖家来源、品牌定位。",
            IntentType.GENERAL_QUERY: "用户需求不明确。先 search_entities 了解可用数据，再决定分析方向。",
        }
        hint = intent_hints.get(spec.intent_type, "用户有分析需求。先理解任务，再决定如何执行。")

        role_lines = [
            "## 你的角色",
            "你是 Amazon 电商分析师。用户给你一个任务。",
            "",
            f"任务背景：{hint}",
            "",
            "可用资源（数据工具 — 从本地 DB 获取真实数据）：",
            "- **query_analysis**: ⭐ 如果当前会话已完成一次 Pipeline 分析（上方「当前数据状态」有显示「已完成分析」），用户追问的细节**优先调这个工具**——它返回完整的价格分布、评论壁垒、品牌集中度等结构化证据 JSON，直接引用数值回答",
            "- **get_entity_details**: 查单个 ASIN/Offer/变体的指定字段。查图片传 metrics=['main_image']",
            "- **compare_entities**: 对比多个 ASIN 的指标（竞品分析首选）",
            "- **search_entities**: 按价格/评分/BSR/品类/品牌等条件筛选商品",
            "- **get_trends**: 查价格/BSR/评分的历史趋势（时序文本）",
            "- **analyze_custom**: 按品牌/品类分组做聚合统计",
            "",
            "⚠️ 必须调工具获取数据。**不调工具直接回答 = 编造数据**。",
            "⚠️ 上方「当前数据状态」只是告诉你 DB 有哪些数据可用，不是数据本身。",
            "⚠️ system prompt 中的字段列表只告诉你 DB 有什么字段，不是字段的值。",
            "",
            "工作原则：",
            "- 第一步永远调工具获取数据，再看结果决定下一步",
            "- 复杂任务拆成子任务，每次调 call_nova_agent 给明确的 sub_task",
            "- 如数据不够，先调滚动获取更多数据，不要硬答",
            "- 不确定的事直接说，标注置信度",
            "- 输出结构化中文报告",
            "",
            "关键：",
            "- 数据库中有完整 Amazon 产品数据（180+ 字段），调工具获取",
            "- search_web 只用于行业新闻、市场趋势等宏观信息",
            "- 用户只查单个产品图片/价格等简单字段时，一次 get_entity_details 即可",
        ]

        # ── 共享原则 ──
        data_principle = (
            "### 数据来源原则\n"
            "所有 Amazon 商品数据（价格、BSR、评论、销量等 180+ 字段）从本地数据库获取。\n"
            "**search_web** 仅用于行业新闻、市场趋势、消费者趋势等宏观查询。\n"
            "**先看上方「当前数据状态」了解 DB 有什么**，再决定下一步。"
        )

        sub_task_guide = (
            "### sub_task 传递机制\n"
            "调 Agent 时在 params 中传入 **sub_task** 字段，告诉该 Agent 本次具体分析什么。\n"
            "例: `call_nova_agent('review_analyzer', '{\\\"sub_task\\\": \\\"重点分析评论中关于价格的信号\\\"}')`\n"
            "→ Agent 会收到你的子任务描述，用它自己的 LLM 决定如何分析。"
        )

        self_check_section = """\
### 输出前自检（必须执行，不是可选）
最终回答**必须**以以下格式的自检段落结尾：

## 自检确认
- 回答了什么问题：XXX
- 关键数据支撑：XXX（具体指标，列出支撑结论的数据点）
- 是否修正了之前的结论：是/否（如修正请说明原因和依据）

### 结论置信度标注规则
- **不标注**：有 ≥3 个独立数据点支撑的结论
- **【中置信度】**：有 1-2 个数据点支撑的结论
- **【低置信度】**：无直接数据支撑，为推理/推断
- 标注放在结论文字末尾，如"产品销量呈上升趋势【高置信度】\""""

        lines = role_lines + ["", data_principle, "", sub_task_guide, "", self_check_section]
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