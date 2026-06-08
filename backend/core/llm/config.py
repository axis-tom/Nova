"""
模型路由配置 — Phase 4 Agent 智能化

所有模型通过 poloai.top 中转站的 OpenAI 兼容格式调用。

模型分配策略：
- orchestrator: claude-opus-4-8（最强推理 + 工具调用），备用 gpt-5.4-xhigh-openai-compact
- 分析推理/判断类: claude-sonnet-4-6，备用 gpt-5.4-high-openai-compact
- 创意/数据类: gpt-5.4-openai-compact（性价比最高，GPT 线路稳定无需备用）
- 报告生成: gpt-5.4-mini（模板化组织，够用且最便宜，GPT 线路稳定无需备用）
- product_collector: 无需 LLM
"""

import asyncio
import logging
import os
from typing import Any, Dict, Optional

from langchain_openai import ChatOpenAI

logger = logging.getLogger(__name__)

# LLM 实例缓存 key=(api_key, base_url, model, temperature) → ChatOpenAI
_llm_cache: Dict[tuple, ChatOpenAI] = {}

# ── Agent → 模型映射：每个 Agent 配 primary + fallback ──
# fallback: 502 等临时故障时自动降级到备用模型（GPT-5.4 系列走 OpenAI 上游，比 Claude 线路稳定）

AGENT_LLM_CONFIG: Dict[str, Optional[Dict[str, Any]]] = {
    # ── 核心推理（Claude 主推，GPT fallout） ──
    "orchestrator": {
        "primary": {"model": "claude-opus-4-8",     "temperature": 0.3, "max_tokens": 4000},
        "fallback": {"model": "gpt-5.4-xhigh-openai-compact", "temperature": 0.3, "max_tokens": 4000},
    },
    # ── 分析推理/判断类（Sonnet 主推，high compact 兜底） ──
    "review_analyzer": {
        "primary": {"model": "claude-sonnet-4-6", "temperature": 0.2, "max_tokens": 3000},
        "fallback": {"model": "gpt-5.4-high-openai-compact", "temperature": 0.2, "max_tokens": 3000},
    },
    "market_analyst": {
        "primary": {"model": "claude-sonnet-4-6", "temperature": 0.2, "max_tokens": 3000},
        "fallback": {"model": "gpt-5.4-high-openai-compact", "temperature": 0.2, "max_tokens": 3000},
    },
    "competitor_analyst": {
        "primary": {"model": "claude-sonnet-4-6", "temperature": 0.3, "max_tokens": 3000},
        "fallback": {"model": "gpt-5.4-high-openai-compact", "temperature": 0.3, "max_tokens": 3000},
    },
    "opportunity_judge": {
        "primary": {"model": "claude-sonnet-4-6", "temperature": 0.2, "max_tokens": 2000},
        "fallback": {"model": "gpt-5.4-openai-compact", "temperature": 0.2, "max_tokens": 2000},
    },
    # ── 创意/数据类（GPT 线路，稳定无需备用） ──
    "keyword_expander": {
        "primary": {"model": "gpt-5.4-openai-compact", "temperature": 0.7, "max_tokens": 2000},
    },
    "traffic_analyzer": {
        "primary": {"model": "gpt-5.4-openai-compact", "temperature": 0.3, "max_tokens": 2000},
    },
    # ── 报告生成（最便宜，GPT 线路） ──
    "briefing_generator": {
        "primary": {"model": "gpt-5.4-mini", "temperature": 0.4, "max_tokens": 4000},
    },
    # ── 无 LLM ──
    "product_collector": None,
}

# ── 成本监控 ──

_usage_counter: Dict[str, int] = {}
_token_usage: Dict[str, Dict[str, int]] = {}

_PRICE_PER_1K: Dict[str, Dict[str, float]] = {
    "claude-opus-4-8":       {"input": 0.015, "output": 0.075},
    "claude-sonnet-4-6":     {"input": 0.003, "output": 0.015},
    "gpt-5.4-xhigh-openai-compact": {"input": 0.002, "output": 0.01},
    "gpt-5.4-high-openai-compact":  {"input": 0.0006, "output": 0.003},
    "gpt-5.4-openai-compact":       {"input": 0.000342, "output": 0.002055},
    "gpt-5.4-mini":                 {"input": 0.000103, "output": 0.000616},
}


def record_token_usage(agent_name: str, input_tokens: int, output_tokens: int):
    """记录单次调用的 token 用量"""
    if agent_name not in _token_usage:
        _token_usage[agent_name] = {"input_tokens": 0, "output_tokens": 0, "calls": 0}
    _token_usage[agent_name]["input_tokens"] += input_tokens
    _token_usage[agent_name]["output_tokens"] += output_tokens
    _token_usage[agent_name]["calls"] += 1


def _build_llm(model: str, temperature: float, max_tokens: int, cache_key: tuple) -> ChatOpenAI:
    """构建带缓存的 ChatOpenAI 实例"""
    cached = _llm_cache.get(cache_key)
    if cached is not None:
        return cached
    api_key = os.getenv("OPENAI_API_KEY")
    base_url = os.getenv("OPENAI_API_BASE") or os.getenv("OPENAI_BASE_URL", "")
    if base_url and not base_url.rstrip("/").endswith("/v1"):
        base_url = base_url.rstrip("/") + "/v1"
    llm = ChatOpenAI(
        model=model,
        api_key=api_key,
        base_url=base_url,
        temperature=temperature,
        max_tokens=max_tokens,
        use_responses_api=False,
    )
    _llm_cache[cache_key] = llm
    return llm


def get_llm_for_agent(agent_name: str) -> Optional[ChatOpenAI]:
    """按 Agent 角色返回主推 LLM 实例。

    优先级：环境变量 override > 配置表 primary > default。
    product_collector 等无需 LLM 的 Agent 返回 None。
    备用模型通过 get_fallback_llm_for_agent() 获取。
    """
    config = AGENT_LLM_CONFIG.get(agent_name, AGENT_LLM_CONFIG.get("default"))
    if config is None:
        return None

    primary = config.get("primary") or config  # 兼容无 fallback 的旧格式
    env_key = f"AGENT_{agent_name.upper()}_MODEL"
    model = os.getenv(env_key) or primary["model"]

    _usage_counter[agent_name] = _usage_counter.get(agent_name, 0) + 1

    cache_key = (os.getenv("OPENAI_API_KEY"), os.getenv("OPENAI_API_BASE"), model, primary["temperature"])
    return _build_llm(model, primary["temperature"], primary["max_tokens"], cache_key)


def get_fallback_llm_for_agent(agent_name: str) -> Optional[ChatOpenAI]:
    """按 Agent 角色返回备用 LLM 实例（502 降级用）。

    无 fallback 配置的 Agent（GPT 线路）返回 None。
    """
    config = AGENT_LLM_CONFIG.get(agent_name)
    if config is None:
        return None
    fallback = config.get("fallback")
    if fallback is None:
        return None

    model = fallback["model"]
    cache_key = (os.getenv("OPENAI_API_KEY"), os.getenv("OPENAI_API_BASE"), model, fallback["temperature"])
    return _build_llm(model, fallback["temperature"], fallback["max_tokens"], cache_key)


# ── LLM 调用重试 + 自动降级 ──

def _is_retryable_error(err: Exception) -> bool:
    """判断异常是否可重试（临时故障）"""
    err_str = str(err)
    return any(kw in err_str for kw in [
        "502", "503", "504",
        "timeout", "Timeout",
        "temporarily unavailable",
        "temporary unavailable",
        "retry later",
        "internal server error",
        "Internal Server Error",
        "Bad Gateway",
        "Service Unavailable",
        "rate limit",
        "RateLimit",
        "429",
        "ConnectionError",
        "connection",
        "Connection reset",
        "Remote end closed",
    ])


async def llm_invoke_with_fallback(
    llm,
    messages,
    fallback_llm=None,
    primary_retries: int = 3,
    fallback_retries: int = 2,
    base_delay: float = 2.0,
    max_delay: float = 32.0,
) -> Any:
    """调用 LLM，自动重试 + 502 降级到备用模型。

    Args:
        llm: 主 LLM 实例（或绑了 tools 的 LLM）
        messages: 消息列表
        fallback_llm: 备用 LLM 实例（None 时不降级，所有重试用主 LLM）
        primary_retries: 主模型重试次数（含首次）
        fallback_retries: 降级后备用模型重试次数
        base_delay: 首次重试间隔（秒）
        max_delay: 最大重试间隔

    Returns:
        LLM 响应

    Raises:
        最后一次异常（所有重试 + 降级耗尽后）
    """
    import random as _random

    def _retry_delay(attempt: int) -> float:
        delay = min(base_delay * (2 ** attempt), max_delay)
        jitter = _random.uniform(-0.3, 0.3) * delay
        return max(0.5, delay + jitter)

    # ── Phase 1：主模型 ──
    last_exception = None
    for attempt in range(primary_retries):
        try:
            return await llm.ainvoke(messages)
        except AttributeError as e:
            if "'str' object has no attribute 'model_dump'" in str(e):
                if attempt < primary_retries - 1:
                    delay = _retry_delay(attempt)
                    logger.warning(
                        f"[LLM] 异常响应 (attempt {attempt+1}/{primary_retries}), "
                        f"{delay:.1f}s 后重试: {e}"
                    )
                    await asyncio.sleep(delay)
                    last_exception = e
                    continue
            raise
        except Exception as e:
            if _is_retryable_error(e) and attempt < primary_retries - 1:
                delay = _retry_delay(attempt)
                logger.warning(
                    f"[LLM] 主模型重试 (attempt {attempt+1}/{primary_retries}), "
                    f"{delay:.1f}s 后重试: {str(e)[:100]}"
                )
                await asyncio.sleep(delay)
                last_exception = e
                continue
            raise

    # ── Phase 2：降级到备用模型 ──
    if fallback_llm is not None:
        logger.warning(
            f"[LLM] 主模型重试 {primary_retries} 次均失败，降级到备用模型"
        )
        for attempt in range(fallback_retries):
            try:
                return await fallback_llm.ainvoke(messages)
            except Exception as e:
                if _is_retryable_error(e) and attempt < fallback_retries - 1:
                    delay = _retry_delay(attempt)
                    logger.warning(
                        f"[LLM] 备用模型重试 (attempt {attempt+1}/{fallback_retries}), "
                        f"{delay:.1f}s 后重试: {str(e)[:100]}"
                    )
                    await asyncio.sleep(delay)
                    last_exception = e
                    continue
                raise

    raise last_exception or RuntimeError("LLM 调用重试耗尽")


# ── 用量查询 ──


def get_usage_stats() -> Dict[str, int]:
    """返回各 Agent 的 LLM 实例创建次数"""
    return dict(_usage_counter)


def get_cost_report() -> Dict[str, Any]:
    """返回各 Agent 的 token 用量和估算成本"""
    report: Dict[str, Any] = {}
    total_cost = 0.0
    for agent_name, usage in _token_usage.items():
        config = AGENT_LLM_CONFIG.get(agent_name)
        # 优先用 primary 模型名（降级场景下可能不准确，但成本估算本就粗糙）
        model = ""
        if config:
            primary = config.get("primary") or config
            model = primary.get("model", "")
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


# ── Prompt Engine 专用模型（翻译/生成/分类） ──

PROMPT_ENGINE_MODEL_CONFIG = {
    "model": "gpt-5.4-mini-high",
    "temperature": 0.2,
    "max_tokens": 2000,
}


def get_prompt_engine_llm() -> Optional[ChatOpenAI]:
    """获取 Prompt Engine 专用的小模型（翻译/生成/分类用）

    走 .env 中同一套 OPENAI_API_KEY + OPENAI_API_BASE 中转站配置。
    Prompt Engine 用便宜小模型做辅助工作，不占用 Agent 分析层的模型配额。
    """
    api_key = os.getenv("OPENAI_API_KEY")
    base_url = os.getenv("OPENAI_API_BASE") or os.getenv("OPENAI_BASE_URL", "")
    if not api_key:
        return None
    if base_url and not base_url.rstrip("/").endswith("/v1"):
        base_url = base_url.rstrip("/") + "/v1"

    return ChatOpenAI(
        model=PROMPT_ENGINE_MODEL_CONFIG["model"],
        api_key=api_key,
        base_url=base_url,
        temperature=PROMPT_ENGINE_MODEL_CONFIG["temperature"],
        max_tokens=PROMPT_ENGINE_MODEL_CONFIG["max_tokens"],
    )