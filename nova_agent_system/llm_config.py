"""
模型路由配置 — Phase 4 Agent 智能化

按 Agent 角色分配最合适的 LLM 模型：
- orchestrator: claude-opus-4-6（最强推理 + 工具调用）
- 分析推理类: claude-sonnet-4-6
- 创意/数据/报告类: gpt-5.2
- product_collector: 无需 LLM

所有模型通过 poloapi.top 中转站的 OpenAI 兼容格式调用。
"""

import os
from typing import Any, Dict, Optional

from langchain_openai import ChatOpenAI

AGENT_LLM_CONFIG: Dict[str, Optional[Dict[str, Any]]] = {
    "orchestrator": {
        "model": "claude-opus-4-6",
        "temperature": 0.3,
        "max_tokens": 4000,
    },
    "keyword_expander": {
        "model": "gpt-5.2",
        "temperature": 0.7,
        "max_tokens": 2000,
    },
    "product_collector": None,
    "review_analyzer": {
        "model": "claude-sonnet-4-6",
        "temperature": 0.2,
        "max_tokens": 3000,
    },
    "traffic_analyzer": {
        "model": "gpt-5.2",
        "temperature": 0.3,
        "max_tokens": 2000,
    },
    "market_analyst": {
        "model": "claude-sonnet-4-6",
        "temperature": 0.2,
        "max_tokens": 3000,
    },
    "competitor_analyst": {
        "model": "gpt-5.2",
        "temperature": 0.3,
        "max_tokens": 3000,
    },
    "opportunity_judge": {
        "model": "claude-sonnet-4-6",
        "temperature": 0.2,
        "max_tokens": 2000,
    },
    "briefing_generator": {
        "model": "gpt-5.2",
        "temperature": 0.4,
        "max_tokens": 4000,
    },
}

# 调用计数（Step 5 成本监控用）
_usage_counter: Dict[str, int] = {}


def get_llm_for_agent(agent_name: str) -> Optional[ChatOpenAI]:
    """按 Agent 角色返回配置好的 LLM 实例。

    优先级：环境变量 override > 配置表 > default。
    product_collector 等无需 LLM 的 Agent 返回 None。
    """
    config = AGENT_LLM_CONFIG.get(agent_name, AGENT_LLM_CONFIG.get("default"))
    if config is None:
        return None

    api_key = os.getenv("OPENAI_API_KEY")
    base_url = os.getenv("OPENAI_API_BASE") or os.getenv("OPENAI_BASE_URL", "")

    # 支持环境变量 override: AGENT_KEYWORD_EXPANDER_MODEL=xxx
    env_key = f"AGENT_{agent_name.upper()}_MODEL"
    model = os.getenv(env_key) or config["model"]

    _usage_counter[agent_name] = _usage_counter.get(agent_name, 0) + 1

    return ChatOpenAI(
        model=model,
        api_key=api_key,
        base_url=base_url,
        temperature=config["temperature"],
        max_tokens=config["max_tokens"],
    )


def get_usage_stats() -> Dict[str, int]:
    """返回各 Agent 的 LLM 实例创建次数"""
    return dict(_usage_counter)
