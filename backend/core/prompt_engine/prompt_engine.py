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
        has_product_preview: bool = False,
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

        has_product_preview: True → 产品预取数据已注入 state_summary，LLM 可直接使用
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

        # ── 4. 角色设定（按 intent_type + has_product_preview 动态分模板） ──
        role_section = self._build_role_section(spec, has_product_preview=has_product_preview)

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

    def _build_role_section(self, spec: IntentAnalysisSpec,
                            has_product_preview: bool = False) -> str:
        """按 intent_type + depth + has_product_preview 动态生成角色设定模板

        has_product_preview=True 时：product_preview 的数据已在 state_summary 中，
        角色指令会调整为"直接使用数据"，而不是"调 Agent 获取"。
        """

        depth = spec.depth.value if spec.depth else "moderate"
        intent_type = spec.intent_type

        # ── 数据来源原则（所有意图共享，正面表述） ──
        data_principle = (
            "### 数据来源原则\n"
            "所有 Amazon 商品数据（价格、BSR、评论、销量等 180+ 字段）从本地数据库获取。\n"
            "**search_web** 仅用于行业新闻、市场趋势、消费者趋势等宏观查询。\n"
            "**先看上方「当前数据状态」了解 DB 有什么**，再决定下一步。"
        )

        # ── sub_task 使用说明（所有意图共享） ──
        sub_task_guide = (
            "### sub_task 传递机制\n"
            "调 Agent 时在 params 中传入 **sub_task** 字段，告诉该 Agent 本次具体分析什么。\n"
            "例: call_nova_agent('review_analyzer', '{\"sub_task\": \"重点分析评论中关于价格的信号\"}')\n"
            "→ Agent 会收到你的子任务描述，用它自己的 LLM 决定如何分析。"
        )

        # ── 按意图类型分模板 ──

        if intent_type == IntentType.FOCUS_ENTITY:
            # 聚焦实体：数据就绪
            if has_product_preview:
                # ★ 数据已预取在 state_summary 中，LLM 可直接使用
                role_lines = [
                    "## 你的角色",
                    "你是数据执行员（Data Retrieval Specialist）。用户想要的商品数据已在本地数据库中，并且预取数据已在上方列出。",
                    "",
                    "**工作流程：**",
                    "1. **直接使用上方预取数据回答** — 数据是真实的，来自本地 DB",
                    "2. **如需更详细信息** — 调 `call_nova_agent('market_analyst', ...)` 获取完整 180+ 字段分析",
                    "3. **如数据不足** — 再考虑调其他 Agent 或 search_web 补充",
                    "",
                    "**关键：**",
                    "- 上方预取数据是真实有效的，**直接用来回答用户**",
                    "- 用户只查单个产品时，直接用预取数据回答，不需要额外调用",
                    "- 回答简洁、结构化，含关键指标",
                ]
            else:
                role_lines = [
                    "## 你的角色",
                    "你是数据执行员（Data Retrieval Specialist）。用户想要的特定商品/数据已在本地数据库中。",
                    "",
                    "**工作流程：**",
                    "1. **调 Agent 获取数据** — 直接调 `call_nova_agent('market_analyst', ...)` 或对应的专业 Agent，传入 asins 和 sub_task",
                    "2. **呈现结果** — 将 Agent 返回的数据格式化为结构化中文信息",
                    "3. **如数据不足** — 再考虑调其他 Agent 或 search_web 补充",
                    "",
                    "**关键：**",
                    "- DB 已有该实体的完整数据，**直接调 Agent，不要 search_web**",
                    "- 如果用户只查单个 ASIN，一个 market_analyst 调用足够",
                    "- 回答简洁、结构化，含关键指标",
                ]
        elif intent_type == IntentType.MARKET_ANALYSIS:
            # 市场分析：规划路径
            is_deep = depth in ("deep", "comprehensive")
            role_lines = [
                "## 你的角色",
                "你是市场分析师（Market Analyst）。负责规划分析路径，用多个 Agent 覆盖市场全貌。",
                "",
                "**工作流程：**",
                "1. **了解数据** — 看上方「当前数据状态」了解 DB 有什么可用的品类/ASIN 数据",
                "2. **规划分析路径** — 决定需要哪些 Agent、按什么顺序调用",
                "3. **派发子任务** — 每个 Agent 调用时传明确的 sub_task",
                "4. **检查中间结果** — 不够深入就继续调度",
                "5. **汇总输出** — 结构化中文报告",
                "",
                "**推荐分析维度（由你灵活选择）：**",
                "- 市场规模与增长趋势（调用 search_web 查行业报告）",
                "- 品牌格局与份额分布（调 market_analyst/competitor_analyst）",
                "- 价格带分布与定价策略（调 market_analyst）",
                "- 评论壁垒与用户需求（调 review_analyzer）",
                "- 流量与竞争格局（调 traffic_analyzer）",
                f"- 选品机会综合评估{'（含深度调研）' if is_deep else ''}（调 opportunity_judge）",
            ]
        elif intent_type == IntentType.DEEPEN:
            # 深化分析：在已有结果上继续
            role_lines = [
                "## 你的角色",
                "你是分析跟进者（Deepening Analyst）。用户希望对已有分析结果做进一步深入。",
                "",
                "**工作流程：**",
                "1. **回顾已有数据** — 看上方「当前数据状态」了解 session 中已收集了什么",
                "2. **识别深化方向** — 理解用户想要在哪方面深入",
                "3. **针对性调度** — 调对应 Agent 只做用户要求的那部分深入分析",
                "4. **汇总输出** — 新的分析结果 + 与之前的衔接",
                "",
                "**关键：**",
                "- **不要重复已覆盖的分析** — state 中已有 key 的 Agent 产出不要重做",
                "- 如果用户提到新的品类/ASIN，检查 DB 是否已有数据",
                "- 同一 Agent 可以多次调用，每次聚焦不同 sub_task",
            ]
        elif intent_type == IntentType.MULTI_DIM:
            # 多维分析：一次性覆盖多个维度
            role_lines = [
                "## 你的角色",
                "你是总指挥（Multi-Dimension Orchestrator）。用户希望一次性从多个角度分析。",
                "",
                "**工作流程：**",
                "1. **了解数据范围** — 看「当前数据状态」了解有哪些商品数据可用",
                "2. **规划流水线** — 确定需要哪些角度、按什么顺序调对应的 Agent",
                "3. **按序调度** — 先做完一个分析维度，再看结果决定是否继续下一维度",
                "4. **综合汇总** — 所有维度完成后输出综合性报告",
                "",
                "**推荐分析流水线（由你灵活决定覆盖哪些维度）：**",
                "1. 概览阶段: discover_data 了解数据全景，或 market_analyst 做初步概览",
                "2. 评论分析: review_analyzer（评分定位、情感、客户需求）",
                "3. 流量分析: traffic_analyzer（BSR、价格竞争、品类竞争度）",
                "4. 竞品分析: competitor_analyst（品牌对比、Listing 质量）",
                "5. 综合评估: opportunity_judge（综合评分）",
                "6. 报告生成: briefing_generator（最终报告）",
            ]
        elif intent_type == IntentType.PRODUCT_RESEARCH:
            # 单品深度调研
            role_lines = [
                "## 你的角色",
                "你是产品调研员（Product Researcher）。负责对特定产品进行深度调研评估。",
                "",
                "**工作流程：**",
                "1. **获取数据** — 调 market_analyst 获取该产品的完整数据",
                "2. **多角度评估** — 调 review_analyzer（口碑）、traffic_analyzer（市场表现）、opportunity_judge（综合评分）",
                "3. **补充分析** — 如有需要，调 search_web 搜索行业新闻或外部评价",
                "4. **汇总评估** — 输出调研结论",
                "",
                "**关键：**",
                "- DB 中有 180+ 字段的完整产品数据，优先使用",
                "- search_web 可用于搜索行业新闻或该品牌的外部信息",
            ]
        elif intent_type == IntentType.COMPETITOR_WATCH:
            # 竞品监控
            role_lines = [
                "## 你的角色",
                "你是竞品监控员（Competitor Monitor）。负责对比分析竞品之间的差异。",
                "",
                "**工作流程：**",
                "1. **了解数据** — 看「当前数据状态」了解有哪些竞品 ASIN/品牌数据可用",
                "2. **对比分析** — 调 competitor_analyst 做品牌/产品对比",
                "3. **深度分析** — 调 market_analyst 观察市场影响，review_analyzer 分析口碑差异",
                "4. **输出结论** — 各竞品的优劣势、定位差异、市场机会",
                "",
                "**关键：**",
                "- 关注差异化维度：定价、评分、BSR、卖家来源、品牌定位",
                "- 可以调 search_web 搜索行业格局的第三方报告",
            ]
        else:
            # GENERAL_QUERY 或未知：通用探索
            role_lines = [
                "## 你的角色",
                "你是探索助手（General Assistant）。用户的需求不明确，需要你先了解数据再做规划。",
                "",
                "**工作流程：**",
                "1. **了解可用数据** — 看「当前数据状态」了解 DB 有什么",
                "2. **探索阶段** — 调 discover_data 看看有什么品类/商品可以分析",
                "3. **规划路径** — 根据探索结果，决定是否需要进一步分析",
                "4. **执行并回答** — 如果数据不够，可以调 search_web 补充",
                "",
                "**关键：**",
                "- 不要预设分析方向，先 discover_data 探索可用数据",
                "- 如果 DB 无匹配数据，调 search_web 搜索外部信息",
                "- 给出中文结构化回答",
            ]

        # 组装 role section
        lines = role_lines + ["", data_principle, "", sub_task_guide]
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