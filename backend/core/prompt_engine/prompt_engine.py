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

        改造后：
        - 不再注入 dimension ID / 预设方向
        - 注入自然语言意图描述（paraphrased_intent + analysis_hint）
        - 展示所有可用 Agent 的能力清单（不按方向过滤）
        - 加入字段总览（让 orchestrator 知道哪些数据可用）
        - 强调 sub_task 传递机制
        """

        # ── 1. 意图描述（自然语言，不指向任何预设维度） ──
        parsed_intent = spec.paraphrased_intent or spec.raw_query[:200]
        hint = spec.analysis_hint
        intent_section = f"""## 用户原始需求
{spec.raw_query}

## 意图理解
{parsed_intent}

## 分析建议（供参考）
{hint if hint else '根据用户原始需求自行判断分析方向'}"""

        # ── 2. Agent 能力清单（全量，不按方向过滤） ──
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

        # ── 3. 字段总览（精简分组） ──
        field_section = """## 数据库中已有的数据字段（按组分类，供规划分析路径时参考）
- **价格类**: current_price, buybox_price, avg_price_30d/90d/180d/365d, list_price, min_price, max_price, has_coupon, buybox_winner
- **BSR/销量**: current_bsr, avg_bsr_30d/90d/180d/365d, bsr_trend, monthly_sold, weekly_sold, annual_sold, sales_rank_history
- **评论类**: rating, review_count, rating_breakdown, review_velocity_30d, top_reviews, customers_say, rating_history
- **卖家/Offer**: seller_count, offer_count_fba/fbm, buybox_seller_id, buybox_seller_name, has_amazon_selling, has_china_sellers
- **Listing**: title, brand, feature_bullets, description, images_count, videos_count, aplus_content, specifications
- **变体**: child_asins, variations, variation_csv, parent_asin
- **配送**: fulfillment_type, availability, is_fba, is_prime, buybox_shipping
- **FBA**: fba_fee, referral_fee_percent
- **库存**: stock_level, is_in_stock, out_of_stock_pct_30d/90d/180d
- **促销**: coupon_text, has_coupon, lightning_deal_info, promotions_json
- **属性**: color, size, style, material, weight, dimensions, item_weight_g
- **品牌**: brand_store, store_name, brand_store_url
- **类目**: categories, category_tree, bsr_category, root_category"""

        # ── 4. 角色设定（强调自由规划 + sub_task 机制） ──
        role_section = """## 你的角色
你是总指挥（Orchestrator）。你的工作流程：

1. **理解用户需求**：根据上方的意图理解和分析建议，**自己思考用户真正要什么**
2. **动态规划分析路径**：决定需要哪些 Agent、按什么顺序调用、每个 Agent 具体做什么
3. **派发子任务**：调 Agent 时，**在 params 中传入 sub_task 字段**，告诉该 Agent 本次具体要分析什么
4. **检查结果**：看 Agent 的输出是否满足需求；不足则重新调度或换角度
5. **汇总输出**：所有分析完成后给出结构化中文报告

### sub_task 传递示例
调 review_analyzer 时传 `{"sub_task": "重点分析评论中关于价格的信号，特别是价格敏感度评价和性价比讨论"}`
调 market_analyst 时传 `{"sub_task": "分析各品牌的价格带分布和定价策略差异"}`
→ Agent 会收到你的子任务描述，用它自己的 LLM 决定如何分析

### 关键原则
- **没有预设分析路径** — 你根据用户原话、可用数据和 Agent 能力现场决定
- **没有固定 Agent 顺序** — 可以先调 market_analyst 做概览，再决定是否需要更多数据
- **可以多次调用同一个 Agent** — 第一次做概览，第二次深挖某个具体细节
- **数据已就绪** — Phase 0 已为你准备好数据。用 discover_data 工具查数据库有哪些可用数据
- **使用 discover_data 工具探索可用数据** — 在你规划分析路径前，先调 discover_data 看看 DB 有什么
- **最终回答用中文、结构化、含关键数据表**"""

        # ── 组装 ──
        prompt_parts = [
            "# 任务：Amazon 电商智能分析",
            intent_section,
            agent_section,
            field_section,
            role_section,
        ]
        system_prompt = "\n\n".join(prompt_parts)

        if memory_context:
            system_prompt += f"\n\n{memory_context}"
        if state_summary:
            system_prompt += f"\n\n{state_summary}"

        return system_prompt

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