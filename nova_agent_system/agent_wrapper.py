"""
Agent 包装器
将 Nova 的现有 Agent 包装成 LLM 可调用的 Tool 接口
不改任何现有 Agent 代码，只做适配
"""

from typing import Dict, Any, List
from backend.common.core.state import State

# ── 已注册的 Agent 清单 ──
# 维护一份 Agent 列表，LLM 看到 description 后决定调哪个

AGENT_REGISTRY = [
    {
        "name": "product_collector",
        "description": "Amazon 商品采集：用关键词搜索 Amazon 商品，返回价格、评分、BSR、评论数等。适合回答「蓝牙耳机 top50」「某品类商品列表」类问题",
        "input_example": '{"keywords": ["bluetooth earbuds"], "max_results": 10}',
    },
    {
        "name": "opportunity_judge",
        "description": "Amazon 市场机会评估：综合商品数据、评论分析、竞品对比，计算机会评分（0-100），生成选品建议和市场报告。适合回答「哪个产品值得做」「市场机会分析」类问题",
        "input_example": "收集到的商品数据，此 Agent 会自动从 state 读取 collected_products 等上游数据",
    },
    {
        "name": "review_analyzer",
        "description": "Amazon 评论分析：分析商品评论，提取情感倾向、常见好评/差评关键词、客户需求。适合回答「这个产品有什么问题」「用户吐槽什么」类问题",
        "input_example": "收集到的商品数据，此 Agent 会自动从 state 读取 collected_products",
    },
    {
        "name": "traffic_analyzer",
        "description": "Amazon 流量分析：分析关键词搜索量、流量趋势、市场竞争程度。适合回答「这个品类流量怎么样」「关键词竞争度」类问题",
        "input_example": "收集到的商品数据，此 Agent 会自动从 state 读取 collected_products",
    },
    {
        "name": "keyword_expander",
        "description": "Amazon 关键词拓词：基于种子关键词扩展相关搜索词，适合回答「帮我找更多相关关键词」类问题",
        "input_example": '{"seed_keywords": ["bluetooth earbuds"]}',
    },
    {
        "name": "market_analyst",
        "description": "Amazon 市场分析（product_selection）：分析市场趋势、需求变化、新品机会。适合回答「这个市场趋势怎么样」类问题",
        "input_example": "关键词或商品列表",
    },
    {
        "name": "competitor_analyst",
        "description": "Amazon 竞品分析：对比多个商品/品牌的竞争力、优劣势。适合回答「对比这几个产品」「竞品分析」类问题",
        "input_example": "商品列表或 ASIN 列表",
    },
    {
        "name": "briefing_generator",
        "description": "Amazon 简报生成：基于分析数据生成结构化的选品简报。适合回答「帮我生成报告」类问题",
        "input_example": "上游分析数据",
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
            ReviewAnalyzerAgent,
        )
        return ReviewAnalyzerAgent()
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


async def call_agent(name: str, params: Dict[str, Any]) -> Dict[str, Any]:
    """
    调用指定 Nova Agent

    1. 创建 State，填入输入参数
    2. 调用 Agent.run(state)
    3. 从 state 中提取结果

    Args:
        name: Agent 名称（对应 AGENT_REGISTRY 中的 name）
        params: 输入参数 dict

    Returns:
        Agent 的输出结果 dict，包含:
        - result: 主要结果（文本或结构化数据）
        - data: state 中所有输出数据
        - events: 执行事件日志
    """
    agent = _load_agent(name)

    # 创建 State
    state = State()
    for key, value in params.items():
        state.set(key, value)

    # 执行 Agent
    result_state = agent.run(state)

    # 提取结果
    data = dict(result_state.data)
    events = result_state.events

    # 提取主要结果
    result = data.get("result") or data.get("market_report") or data.get("collected_products") or data

    return {
        "agent": name,
        "result": result,
        "data": data,
        "events": events,
    }


def list_agents() -> List[Dict[str, str]]:
    """列出所有可用的 Agent"""
    return AGENT_REGISTRY