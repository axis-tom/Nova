"""
Agent 包装器
将 Nova 的现有 Agent 包装成 LLM 可调用的 Tool 接口
不改任何现有 Agent 代码，只做适配
"""

import inspect
from typing import Dict, Any, List, Optional
from backend.common.core.state import State
from backend.core.memory.vector_store import MemoryStore
from backend.core.llm.config import get_llm_for_agent, get_fallback_llm_for_agent
import json

# ── 全局记忆实例 ──
_memory = MemoryStore()

# ── 已注册的 Agent 清单 ──
# 维护一份 Agent 列表，LLM 看到 description 后决定调哪个
# input_example 使用 Agent 真实读取的 state 字段名
# requires_upstream 列出该 Agent 依赖的上游 Agent（必须先在同一会话内运行过）

AGENT_REGISTRY = [
    {
        "name": "keyword_expander",
        "description": (
            "Amazon 关键词拓词：基于种子关键词扩展相关搜索词。"
            "如果数据库中有商品数据，会从竞品标题提取真实市场关键词（更精准）。"
            "适合回答「帮我找更多相关关键词」类问题"
        ),
        "input_example": '{"seed_keywords": ["portable fan"], "expand_count": 20, "include_long_tail": true}',
        "requires_upstream": [],
    },
    {
        "name": "review_analyzer",
        "description": (
            "Amazon 评分/评论洞察：基于商品数据做评分定位、评论壁垒评估、情感倾向、"
            "好评/差评推断、客户需求分析。适合回答「这个产品口碑怎么样」「评论壁垒高不高」类问题。"
            "传 category 或 asins 从 amazon_products 本地表查询（秒级响应）"
        ),
        "input_example": '{"category": "Headphones", "domain": "US", "max_products_to_analyze": 20}  # 传 category 走本地表',
        "requires_upstream": [],
    },
    {
        "name": "traffic_analyzer",
        "description": (
            "Amazon 流量与竞品分析：分析 BSR 排名分布、价格竞争格局、价格异常检测、"
            "品类竞争度评估。适合回答「这个品类流量怎么样」「价格竞争格局」类问题。"
            "传 category 或 asins 从 amazon_products 本地表查询（秒级响应）"
        ),
        "input_example": '{"category": "Wireless Earbuds", "domain": "US"}  # 传 category 走本地表',
        "requires_upstream": [],
    },
    {
        "name": "opportunity_judge",
        "description": (
            "Amazon 市场机会评估：综合商品/评论/流量/竞品数据，计算机会评分（0-100），"
            "输出选品建议和市场报告。适合「哪个产品值得做」「市场机会分析」类问题。"
            "传 category 或 asins 从 amazon_products 本地表加载商品数据后评分"
        ),
        "input_example": '{"category": "Headphones", "domain": "US", "min_opportunity_score": 60, "output_top_n": 10}',
        "requires_upstream": [],
    },
    {
        "name": "market_analyst",
        "description": (
            "Amazon 市场分析：分析市场体量（月销/营收）、市场趋势（BSR/价格 time-series 变化率）、"
            "淡旺季（月度 BSR/价格分布）、品牌分布、价格带、机会/风险。"
            "传 category + domain 从 amazon_products 本地表查询（数据由 ETL 定时刷新，毫秒级响应）"
        ),
        "input_example": '{"category": "Headphones", "domain": "US", "analysis_type": "market_trends"}  # 推荐：传 category 走本地表',
        "requires_upstream": [],
    },
    {
        "name": "competitor_analyst",
        "description": (
            "Amazon 竞品分析：品牌聚合 + 产品级 head-to-head 对比。"
            "分析市场份额、竞争格局分层、头部竞品定价策略（基于 price_history 识别的涨价/降价/稳定模式）、"
            "listing 质量对比（五点/图片/描述/A+）、差异化机会。"
            "传 category 或 asins 从 amazon_products 本地表查询（秒级响应）"
        ),
        "input_example": '{"category": "Bluetooth Speaker", "domain": "US"}  # 传 category 走本地表',
        "requires_upstream": [],
    },
    {
        "name": "briefing_generator",
        "description": "Amazon 简报生成：基于已有分析数据生成结构化选品简报（Markdown）。适合回答「帮我生成报告」类问题。建议先跑 opportunity_judge 以获得最完整的报告内容。",
        "input_example": '{}  # 自动读取 state 中所有上游产出',
        "requires_upstream": [],
    },
]

# ── Agent 懒加载 ──


def _load_agent(name: str):
    """延迟导入 Agent 类，避免启动时加载所有依赖；自动注入模型路由的 LLM"""
    if name == "opportunity_judge":
        from backend.business.ecommerce.amazon_monitor.agents.opportunity_judge import (
            OpportunityJudgeAgent,
        )
        agent = OpportunityJudgeAgent()
    elif name == "review_analyzer":
        from backend.business.ecommerce.amazon_monitor.agents.review_analyzer import (
            AmazonReviewAnalyzerAgent,
        )
        agent = AmazonReviewAnalyzerAgent()
    elif name == "traffic_analyzer":
        from backend.business.ecommerce.amazon_monitor.agents.traffic_analyzer import (
            TrafficAnalyzerAgent,
        )
        agent = TrafficAnalyzerAgent()
    elif name == "keyword_expander":
        from backend.business.ecommerce.amazon_monitor.agents.keyword_expander import (
            KeywordExpanderAgent,
        )
        agent = KeywordExpanderAgent()
    elif name == "market_analyst":
        from backend.business.ecommerce.product_selection.agents.market_analyst import (
            MarketAnalystAgent,
        )
        agent = MarketAnalystAgent()
    elif name == "competitor_analyst":
        from backend.business.ecommerce.product_selection.agents.competitor_analyst import (
            CompetitorAnalystAgent,
        )
        agent = CompetitorAnalystAgent()
    elif name == "briefing_generator":
        from backend.business.ecommerce.product_selection.agents.briefing_generator import (
            BriefingGeneratorAgent,
        )
        agent = BriefingGeneratorAgent()
    else:
        raise ValueError(f"未知 Agent: {name}")

    llm = get_llm_for_agent(name)
    if llm is not None:
        agent.llm = llm

    # 备用模型（502 降级用）
    fallback_llm = get_fallback_llm_for_agent(name)
    if fallback_llm is not None:
        agent.fallback_llm = fallback_llm

    return agent


async def call_agent(
    name: str,
    params: Dict[str, Any],
    state: Optional[State] = None,
    conv_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    调用指定 Nova Agent

    1. 如传入 state（来自 SessionStore），shallow merge params 进 state.data（params 覆盖同名 key，保留上游字段）
    2. 否则新建空 State，仅填入 params
    3. 调用 Agent.run(state)
    4. 从 state 中提取结果

    Args:
        name: Agent 名称（对应 AGENT_REGISTRY 中的 name）
        params: 输入参数 dict
        state: 可选的会话 State；若传入，本次调用会读取/写入该 State（流水线模式）
        conv_id: 可选会话 ID；传入则自动追踪到分析树

    Returns:
        Agent 的输出结果 dict，包含:
        - result: 主要结果（文本或结构化数据）
        - data: state 中所有输出数据
        - events: 执行事件日志
    """
    from backend.core.tracking.analysis_tree import analysis_tree_manager

    agent = _load_agent(name)

    if state is None:
        state = State()

    # 清除上一次 agent 调用残留的 error（防止 pipeline 状态污染）
    state.data.pop("error", None)
    state.data.pop("error_type", None)
    state.data.pop("error_details", None)

    # Shallow merge：params 覆盖同名 key，保留上游字段
    for key, value in params.items():
        state.set(key, value)

    state.add_event(f"call_agent:{name}:start")

    # ── Prompt Engine 注入：如果 state 中有定制 system_prompt，注入到 Agent ──
    custom_prompt = state.data.pop("_custom_system_prompt", None)
    if custom_prompt:
        agent._custom_system_prompt = custom_prompt

    # ── 分析树追踪：开始 ──
    invocation = None
    if conv_id:
        try:
            round_num = state.get_meta("conversation_round", 0)
            invocation = analysis_tree_manager.on_agent_start(
                conv_id, name, params, conversation_round=round_num
            )
        except Exception:
            pass  # 树追踪失败不影响主流程

    # 执行 Agent — Nova 部分 Agent 是 sync 的（keyword_expander/traffic_analyzer/opportunity_judge），
    # 部分是 async 的（product_collector/review_analyzer），统一兼容
    error_message = None
    try:
        maybe_result = agent.run(state)
        if inspect.isawaitable(maybe_result):
            result_state = await maybe_result
        else:
            result_state = maybe_result
    except Exception as e:
        error_message = str(e)
        result_state = state
        result_state.data["error"] = error_message
        result_state.data["error_type"] = "agent_exception"

    # 注意：result_state 与 state 通常是同一对象（agent 就地改），但 review_analyzer 等
    # 部分 agent 可能返回 new State。这里以 result_state 为准做后续提取，但若 state
    # 来自 SessionStore，调用方应保证 result_state 的写入也已反映到 session 中（见 orchestrator）。

    # 提取结果
    data = dict(result_state.data)
    events = list(result_state.events)

    # 错误优先：如果 state 含 error，整个工具结果以错误对象返回，
    # 让 LLM 第一时间看到 status=error 而不是空 collected_products
    if data.get("error"):
        error_payload = {
            "status": "error",
            "error_type": data.get("error_type", "unknown"),
            "error_message": data["error"],
            "error_details": data.get("error_details") or {},
        }
        # 分析树追踪：错误结束
        if conv_id and invocation:
            try:
                analysis_tree_manager.on_agent_end(
                    conv_id=conv_id,
                    invocation_id=invocation.invocation_id,
                    result_summary=data["error"][:300],
                    state_dict=result_state.to_dict() if result_state else None,
                    error_message=data["error"],
                )
            except Exception:
                pass
        return {
            "agent": name,
            "status": "error",
            "result": error_payload,
            "data": data,
            "events": events,
            "result_state": result_state,
        }

    # 提取主要结果（成功路径）
    result = data.get("result") or data.get("market_report") or data.get("collected_products") or data

    # ── Agent 加载信息提取（供 DecisionTrace + 驾驶舱使用） ──
    # 从 state.data 提取 Agent 实际加载了哪些数据，不改 Agent 的 run() 方法
    agent_load_info = _extract_agent_load_info(name, data)

    # 自动保存到记忆系统
    try:
        result_summary = ""
        if isinstance(result, str):
            result_summary = result[:500]
        elif isinstance(result, list):
            result_summary = f"共 {len(result)} 条记录"
            if result:
                result_summary += f"，首条: {json.dumps(result[0], ensure_ascii=False)[:200]}"
        elif isinstance(result, dict):
            result_summary = json.dumps(result, ensure_ascii=False)[:500]
        else:
            result_summary = str(result)[:500]

        _memory.save_memory(
            content=f"Agent [{name}] 分析结果:\n{result_summary}",
            importance=7,  # Agent 输出通常高重要性
            tags=f"agent_output,{name}",
            source=name,
            metadata={
                "agent_name": name,
                "params": json.dumps(params, ensure_ascii=False)[:200],
            },
        )
    except Exception:
        pass  # 记忆保存失败不影响主流程

    # ── 分析树追踪：结束 ──
    if conv_id and invocation:
        try:
            analysis_tree_manager.on_agent_end(
                conv_id=conv_id,
                invocation_id=invocation.invocation_id,
                result_summary=result_summary,
                state_dict=result_state.to_dict() if result_state else None,
                error_message=error_message,
            )
        except Exception:
            pass  # 树追踪失败不影响主流程

    return {
        "agent": name,
        "status": "ok",
        "result": result,
        "data": data,
        "events": events,
        "result_state": result_state,  # 供 orchestrator 写回 SessionStore
        "agent_load_info": agent_load_info,  # 加载信息（供 DecisionTrace + 驾驶舱）
    }


def _extract_agent_load_info(agent_name: str, state_data: dict) -> dict:
    """
    从 Agent 执行后的 state.data 中提取数据加载信息。
    不依赖 Agent run() 内部的具体实现，只从结果中推测。

    Args:
        agent_name: Agent 名称
        state_data: Agent 执行后的 state.data

    Returns:
        加载信息 dict，包含：
        - asins_queried: 查询的 ASIN 列表
        - category_queried: 查询的品类名
        - products_loaded: 加载的商品数量
        - fields_available: 可用字段数（从首个商品推断）
        - output_keys_produced: Agent 输出的 state key 列表
        - evidence_fields: Agent 用了哪些字段作为分析依据
    """
    # ── ASIN 查询 ──
    asins: list = state_data.get("asins", []) or []
    if isinstance(asins, str):
        asins = [a.strip() for a in asins.replace(",", " ").split() if a.strip()]
    asins = list(asins) if isinstance(asins, (list, tuple)) else []

    # ── 品类查询 ──
    category_queried = (
        state_data.get("category")
        or state_data.get("category_name")
        or ""
    )
    if isinstance(category_queried, str):
        category_queried = category_queried.strip()

    # ── 加载的商品数 ──
    products_loaded = 0
    fields_available = 0
    sample_product = None

    # 检查各种可能的商品列表存放位置
    for key in ("collected_products", "products", "product_map", "results"):
        val = state_data.get(key)
        if isinstance(val, list) and len(val) > 0:
            products_loaded = len(val)
            sample_product = val[0] if val else None
            break
        elif isinstance(val, dict) and len(val) > 0:
            # product_map: {asin: product}
            products_loaded = len(val)
            sample_product = next(iter(val.values())) if val else None
            break

    # 如果没找到 products，从 asins 数推断
    if products_loaded == 0 and asins:
        products_loaded = len(asins)

    # 字段数（从首个商品推断）
    if sample_product and isinstance(sample_product, dict):
        fields_available = len(sample_product)

    # ── Agent 输出的 state key（排除 params 注入的） ──
    output_keys = [k for k in state_data.keys()
                   if not k.startswith("_")
                   and k not in ("asins", "category", "category_name", "domain",
                                 "max_products_to_analyze", "seed_keywords",
                                 "expand_count", "analysis_type", "sub_task",
                                 "min_opportunity_score", "output_top_n",
                                 "include_long_tail", "error", "error_type", "error_details")]

    # ── 证据字段（Agent 分析中用到的字段） ──
    # 从 Agent 产出结果中反推（eg. 结果的 key 名）
    evidence_fields = _infer_evidence_fields(agent_name, state_data)

    return {
        "asins_queried": asins[:20],
        "category_queried": category_queried,
        "products_loaded": products_loaded,
        "fields_available": fields_available,
        "output_keys_produced": output_keys[:15],
        "evidence_fields": evidence_fields[:15],
        "sample_product_title": (sample_product.get("title") or "?")[:60]
            if isinstance(sample_product, dict) else "",
    }


def _infer_evidence_fields(agent_name: str, state_data: dict) -> List[str]:
    """
    从 Agent 的分析结果中推断用到了哪些数据字段作为分析依据。
    这是启发式推断——不完美但比完全黑盒好。
    """
    # 每个 Agent 可能使用的标准字段
    agent_evidence_patterns = {
        "market_analyst": [
            "current_price", "rating", "review_count", "current_bsr",
            "monthly_sold", "brand", "is_fba", "is_prime",
            "price_history", "bsr_history", "category_name", "feature_bullets",
            "aplus_content", "seller_count",
        ],
        "review_analyzer": [
            "rating", "review_count", "rating_breakdown", "review_velocity_30d",
            "top_reviews", "customers_say", "rating_history",
            "review_count_history", "has_reviews",
        ],
        "traffic_analyzer": [
            "current_bsr", "avg_bsr_30d", "avg_bsr_90d", "monthly_sold",
            "current_price", "is_fba", "is_prime", "seller_count",
            "price_history", "bsr_history", "avg_price_30d",
        ],
        "competitor_analyst": [
            "title", "brand", "current_price", "rating", "review_count",
            "current_bsr", "monthly_sold", "feature_bullets", "main_image",
            "images_count", "aplus_content", "description", "is_fba", "is_prime",
        ],
        "opportunity_judge": [
            "current_price", "rating", "review_count", "current_bsr",
            "monthly_sold", "seller_count", "is_fba", "is_prime",
            "fba_fee", "stock_level", "brand", "category_name",
            "price_history", "bsr_history", "has_coupon",
        ],
        "keyword_expander": [
            "title", "brand", "keywords_list", "feature_bullets",
            "description", "search_alias",
        ],
    }

    patterns = agent_evidence_patterns.get(agent_name, [])
    if not patterns:
        return []

    # 从 state_data 中检查哪些字段有值，与 patterns 取交集
    available_fields = set()
    for key in patterns:
        if state_data.get(key) is not None:
            available_fields.add(key)
        # 也检查 collected_products 中的字段
        products = state_data.get("collected_products")
        if isinstance(products, list) and products:
            sample = products[0]
            if isinstance(sample, dict) and sample.get(key) is not None:
                available_fields.add(key)

    return sorted(available_fields) or patterns[:5]


def list_agents() -> List[Dict[str, Any]]:
    """列出所有可用的 Agent（含 requires_upstream 字段）"""
    return AGENT_REGISTRY