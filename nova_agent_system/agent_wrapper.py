"""
Agent 包装器
将 Nova 的现有 Agent 包装成 LLM 可调用的 Tool 接口
不改任何现有 Agent 代码，只做适配
"""

import inspect
from typing import Dict, Any, List, Optional
from backend.common.core.state import State
from nova_agent_system.memory_store import MemoryStore
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
        "description": "Amazon 关键词拓词：基于种子关键词扩展相关搜索词。适合回答「帮我找更多相关关键词」类问题；也是 product_collector 的常见前置步骤",
        "input_example": '{"seed_keywords": ["bluetooth earbuds"], "expand_count": 20, "include_long_tail": true}',
        "requires_upstream": [],
    },
    {
        "name": "product_collector",
        "description": (
            "Amazon 商品采集（基于 Keepa）：拉取价格、BSR、评论、销量等历史数据。"
            "**推荐用法**：传入 watchlist_asins=[\"B0XXX\",...] 直接查指定商品（每 ASIN 1 token，快且省）。"
            "用户问「分析 B0XXX 这个商品」「对比这几个 ASIN」类问题时**首选**此入口。"
            "兼容旧入口：可显式 allow_keyword_search=True + expanded_keywords 走关键词搜索"
            "（但 Pro 套餐 /search 每次烧 10 token 且常返空，不推荐）。"
        ),
        "input_example": (
            '{"watchlist_asins": ["B0BDHWDR12", "B0F9FP4MC4"], "domain": "US"}  '
            '# 推荐：直接传 ASIN；或者 {"expanded_keywords":["bluetooth earbuds"], "allow_keyword_search": true}'
        ),
        "requires_upstream": [],
    },
    {
        "name": "review_analyzer",
        "description": "Amazon 评论分析：分析商品评论，提取情感倾向、好评/差评关键词、客户需求。适合回答「这个产品有什么问题」「用户吐槽什么」类问题。**必须先调用 product_collector**，读取 state.collected_products",
        "input_example": '{"max_products_to_analyze": 20}  # 必须先有 product_collector 的 collected_products',
        "requires_upstream": ["product_collector"],
    },
    {
        "name": "traffic_analyzer",
        "description": "Amazon 流量分析：分析关键词搜索量、流量趋势、竞争程度。适合回答「这个品类流量怎么样」「关键词竞争度」类问题。**必须先调用 product_collector**，读取 state.collected_products",
        "input_example": '{}  # 必须先有 product_collector 的 collected_products',
        "requires_upstream": ["product_collector"],
    },
    {
        "name": "opportunity_judge",
        "description": "Amazon 市场机会评估：综合商品 / 评论 / 流量 / 竞品数据，计算机会评分（0-100），输出选品建议和市场报告。适合「哪个产品值得做」「市场机会分析」类问题。**必须先调用 product_collector + review_analyzer + traffic_analyzer**，读取 state.collected_products / review_insights / sentiment_summary / customer_needs / traffic_insights / competitor_comparison",
        "input_example": '{"min_opportunity_score": 60, "output_top_n": 10}  # 上游数据从 state 自动读取',
        "requires_upstream": ["product_collector", "review_analyzer", "traffic_analyzer"],
    },
    {
        "name": "market_analyst",
        "description": (
            "Amazon 市场分析：基于 Keepa 真实数据分析市场趋势、品牌分布、价格带、机会/风险。"
            "支持 analysis_type='market_trends'（默认）或 'roi_analysis'（盈利评估）。"
            "**必须先调用 product_collector**，读取 state.collected_products"
        ),
        "input_example": '{"analysis_type": "market_trends"}  # 必须先有 product_collector 的 collected_products',
        "requires_upstream": ["product_collector"],
    },
    {
        "name": "competitor_analyst",
        "description": (
            "Amazon 竞品分析：基于 Keepa 真实数据，按品牌聚合做市场份额、价格区间、"
            "评分对比、竞争格局分层和差异化机会识别。"
            "**必须先调用 product_collector**，读取 state.collected_products"
        ),
        "input_example": '{}  # 必须先有 product_collector 的 collected_products',
        "requires_upstream": ["product_collector"],
    },
    {
        "name": "briefing_generator",
        "description": "Amazon 简报生成：基于已有分析数据生成结构化选品简报。适合回答「帮我生成报告」类问题。**建议先跑 opportunity_judge**，读取 state 中所有分析产出",
        "input_example": '{}  # 从 state 读取所有上游产出',
        "requires_upstream": ["opportunity_judge"],
    },
]

# ── Agent 懒加载 ──


def _load_agent(name: str):
    """延迟导入 Agent 类，避免启动时加载所有依赖"""
    if name == "product_collector":
        from backend.business.ecommerce.amazon_monitor.agents.product_collector import (
            ProductCollectorAgent,
        )
        return ProductCollectorAgent()
    elif name == "opportunity_judge":
        from backend.business.ecommerce.amazon_monitor.agents.opportunity_judge import (
            OpportunityJudgeAgent,
        )
        return OpportunityJudgeAgent()
    elif name == "review_analyzer":
        from backend.business.ecommerce.amazon_monitor.agents.review_analyzer import (
            AmazonReviewAnalyzerAgent,
        )
        return AmazonReviewAnalyzerAgent()
    elif name == "traffic_analyzer":
        from backend.business.ecommerce.amazon_monitor.agents.traffic_analyzer import (
            TrafficAnalyzerAgent,
        )
        return TrafficAnalyzerAgent()
    elif name == "keyword_expander":
        from backend.business.ecommerce.amazon_monitor.agents.keyword_expander import (
            KeywordExpanderAgent,
        )
        return KeywordExpanderAgent()
    elif name == "market_analyst":
        from backend.business.ecommerce.product_selection.agents.market_analyst import (
            MarketAnalystAgent,
        )
        return MarketAnalystAgent()
    elif name == "competitor_analyst":
        from backend.business.ecommerce.product_selection.agents.competitor_analyst import (
            CompetitorAnalystAgent,
        )
        return CompetitorAnalystAgent()
    elif name == "briefing_generator":
        from backend.business.ecommerce.product_selection.agents.briefing_generator import (
            BriefingGeneratorAgent,
        )
        return BriefingGeneratorAgent()
    else:
        raise ValueError(f"未知 Agent: {name}")


async def call_agent(
    name: str,
    params: Dict[str, Any],
    state: Optional[State] = None,
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

    Returns:
        Agent 的输出结果 dict，包含:
        - result: 主要结果（文本或结构化数据）
        - data: state 中所有输出数据
        - events: 执行事件日志
    """
    agent = _load_agent(name)

    if state is None:
        state = State()

    # Shallow merge：params 覆盖同名 key，保留上游字段
    for key, value in params.items():
        state.set(key, value)

    state.add_event(f"call_agent:{name}:start")

    # 执行 Agent — Nova 部分 Agent 是 sync 的（keyword_expander/traffic_analyzer/opportunity_judge），
    # 部分是 async 的（product_collector/review_analyzer），统一兼容
    maybe_result = agent.run(state)
    if inspect.isawaitable(maybe_result):
        result_state = await maybe_result
    else:
        result_state = maybe_result

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

    return {
        "agent": name,
        "status": "ok",
        "result": result,
        "data": data,
        "events": events,
        "result_state": result_state,  # 供 orchestrator 写回 SessionStore
    }


def list_agents() -> List[Dict[str, Any]]:
    """列出所有可用的 Agent（含 requires_upstream 字段）"""
    return AGENT_REGISTRY