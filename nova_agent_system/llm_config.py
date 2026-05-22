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
        "model": "gpt-5.2",
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

# ── 成本监控 ──

_usage_counter: Dict[str, int] = {}
_token_usage: Dict[str, Dict[str, int]] = {}

# 粗略定价（$/1K tokens），按模型估算
_PRICE_PER_1K: Dict[str, Dict[str, float]] = {
    "claude-opus-4-6": {"input": 0.015, "output": 0.075},
    "claude-sonnet-4-6": {"input": 0.003, "output": 0.015},
    "gpt-5.2": {"input": 0.005, "output": 0.015},
}


def record_token_usage(agent_name: str, input_tokens: int, output_tokens: int):
    """记录单次调用的 token 用量"""
    if agent_name not in _token_usage:
        _token_usage[agent_name] = {"input_tokens": 0, "output_tokens": 0, "calls": 0}
    _token_usage[agent_name]["input_tokens"] += input_tokens
    _token_usage[agent_name]["output_tokens"] += output_tokens
    _token_usage[agent_name]["calls"] += 1


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


def get_cost_report() -> Dict[str, Any]:
    """返回各 Agent 的 token 用量和估算成本"""
    report: Dict[str, Any] = {}
    total_cost = 0.0
    for agent_name, usage in _token_usage.items():
        config = AGENT_LLM_CONFIG.get(agent_name)
        model = config["model"] if config else "unknown"
        pricing = _PRICE_PER_1K.get(model, {"input": 0.005, "output": 0.015})
        input_cost = usage["input_tokens"] / 1000 * pricing["input"]
        output_cost = usage["output_tokens"] / 1000 * pricing["output"]
        cost = input_cost + output_cost
        total_cost += cost
        report[agent_name] = {
            "model": model,
            "calls": usage["calls"],
            "input_tokens": usage["input_tokens"],
            "output_tokens": usage["output_tokens"],
            "estimated_cost_usd": round(cost, 4),
        }
    report["_total_estimated_cost_usd"] = round(total_cost, 4)
    return report


def reset_usage():
    """重置所有计数器（测试用）"""
    _usage_counter.clear()
    _token_usage.clear()
