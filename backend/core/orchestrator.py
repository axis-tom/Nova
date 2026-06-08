"""
Orchestrator — 核心调度引擎
基于 LangGraph 的 ReAct 循环：
1. LLM 理解用户意图
2. LLM 决定调哪些工具（搜索 / Agent / 查记忆）
3. 循环：调工具 → 看结果 → 再调工具 → 直到完成
4. LLM 汇总结果 → 返回
"""

import operator
from typing import Dict, Any, List, Optional, TypedDict, Annotated, Sequence
from contextvars import ContextVar
import os
import re
import uuid
import asyncio
import time
import json
from pathlib import Path

from dotenv import load_dotenv
from langgraph.graph import StateGraph, END
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage, ToolMessage
from langchain_core.tools import tool

# 加载 .env 文件
env_path = Path(__file__).resolve().parent.parent.parent / "backend" / "config" / ".env"
if env_path.exists():
    load_dotenv(dotenv_path=env_path)

# ⚠️ WSL 环境修复：清除系统级 https_proxy，防止干扰 poloai.top 中转站直连
# httpx/urllib3 会读取这些环境变量自动加代理，但 WSL 的 http_proxy 指向宿主机，
# 而 poloai.top 是外网直连 API，不经过代理。代理通道不稳定会导致 502/ConnectionError。
_UNSET_PROXY_KEYS = ("HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy", "ALL_PROXY", "all_proxy")
_saved_proxy = {}
for _k in _UNSET_PROXY_KEYS:
    _v = os.environ.pop(_k, None)
    if _v:
        _saved_proxy[_k] = _v

from backend.core.tools.web_search import web_search, scrape_url
from backend.core.memory.vector_store import MemoryStore
from backend.core.agent_wrapper import call_agent, list_agents
from backend.core.tools.db_query import query_database as db_query
from backend.core.memory.state_store import session_store
from backend.core.memory.durable import get_durable_session
from backend.core.memory.summarizer import summarize_conversation
from backend.core.llm.config import get_llm_for_agent
from backend.core.tracking.analysis_tree import analysis_tree_manager
from backend.core.cockpit_extractor import extract_cockpit_data, AGENT_CATEGORY_LABELS

# ── Prompt Engine ──
from backend.core.prompt_engine import PromptEngine
from backend.core.prompt_engine.engines.intent_classifier import (
    IntentAnalysisSpec, IntentType, AnalysisDepth,
)

# ── DataLiaison ──
from backend.aqueduct.data_liaison import DataLiaison, DataIntelligenceReport

# ── Decision Trace ──
from backend.core.decision_trace import DecisionTracer

# ── Prompt Engine 单例 ──
_prompt_engine: Optional["PromptEngine"] = None


def get_prompt_engine() -> "PromptEngine":
    global _prompt_engine
    if _prompt_engine is None:
        from backend.core.prompt_engine import PromptEngine
        _prompt_engine = PromptEngine()
    return _prompt_engine


# ── 驾驶舱数据追踪：tool_call_id → 真实 Agent 名 ──
_agent_name_by_call_id: Dict[str, str] = {}

# ── 全局记忆实例 ──
memory = MemoryStore()

# ── ASIN 正则 ──
# ★ P8 修复：不用 \b 边界（Python3 中 CJK ≒ \w 导致中文+ASIN 不匹配）
_ASIN_PATTERN = re.compile(r'(?<![A-Za-z0-9])B[A-Z0-9]{9}[A-Z0-9]?(?![A-Za-z0-9])')

# Step 5: 启动时执行一次全量清理（TTL + 整合 + SQLite 过期）
try:
    _cleanup_stats = memory.cleanup_all()
except Exception:
    pass

# ── 会话上下文（同一 ReAct 循环内的 tool 通过此读取当前 conversation_id） ──
conv_id_var: ContextVar[Optional[str]] = ContextVar("conv_id_var", default=None)

# ── DecisionTrace 上下文 ──
tracer_var: ContextVar[Optional["DecisionTracer"]] = ContextVar("tracer_var", default=None)

# ── 多轮上下文配置 ──
HISTORY_FULL_ROUNDS = 5     # 最近 N 轮保留完整内容（user + assistant + tool）
HISTORY_BRIEF_ROUNDS = 10   # 更早的只保留 user + assistant（省 token）
HISTORY_MAX_MESSAGES = 50   # 从 SQLite 拉取的最大消息数

# ── 状态定义 ──


class AgentState(TypedDict):
    messages: Annotated[List[Dict[str, Any]], operator.add]
    user_input: str
    final_response: Optional[str]
    tool_results: List[Dict[str, Any]]
    intel_collected: bool  # Phase 0 已完成情报收集
    # ★ Phase 0 产出直通（序列化为 dict，经 LangGraph AgentState 传至 call_model）
    intent_spec_data: Optional[Dict[str, Any]]  # IntentAnalysisSpec → dict 序列化结果
    intel_report: Optional[Dict[str, Any]]       # DataLiaison 情报报告
    correction_prefix: str  # 历史纠正提示（过滤 dead-end 后注入 system prompt）


# ── LLM 初始化 ──

def _get_llm():
    """获取 orchestrator 的 LLM 实例（通过模型路由配置）"""
    return get_llm_for_agent("orchestrator")

def _get_fallback_llm():
    """获取 orchestrator 的备用 LLM 实例（502 降级用）"""
    from backend.core.llm.config import get_fallback_llm_for_agent
    return get_fallback_llm_for_agent("orchestrator")


# ── LLM 调用重试 ──

from backend.core.llm.config import llm_invoke_with_fallback as _llm_invoke_with_fallback


# ── 工具定义 ──

@tool
async def search_web(query: str) -> str:
    """搜索互联网获取最新行业报告、新闻事件、市场趋势、消费者趋势。只用于搜索市场大盘数据（品类规模、增长率、消费者趋势等宏观信息），绝不要用来搜索单个 ASIN、单个品牌、或单个商品的产品详情——数据库中的 180+ 字段比网页更全更准。"""
    results = await web_search(query, max_results=5)
    if not results or not results[0].get("content"):
        return "未找到相关结果"
    lines = []
    for i, r in enumerate(results, 1):
        lines.append(f"{i}. {r['title']}\n   {r['content'][:300]}\n   来源: {r['url']}")
    return "\n\n".join(lines)


@tool
async def search_memory(query: str) -> str:
    """搜索历史记忆。当你需要回忆之前的对话内容、Agent 分析结果或之前搜索过的知识时使用。"""
    # 跨 collection 统一搜索
    results = memory.search_all(query, k=5)
    if not results:
        return "未找到相关历史记录"
    lines = []
    for r in results:
        meta = r['metadata']
        source_type = meta.get('type', meta.get('source', 'unknown'))
        lines.append(f"[{meta.get('timestamp', '')}] ({source_type}) {r['content'][:500]}")
    return "\n\n".join(lines)


@tool
async def query_db(natural_query: str) -> str:
    """
    查询 Nova 数据库中的结构化数据。当你需要查看数据库中的表结构、用户数据、项目数据、对话记录等内部信息时使用。
    
    Args:
        natural_query: 自然语言查询描述，例如 "列出所有表"、"查看 users 表的结构"、"查询 projects 表的前 10 条数据"
    """
    return await db_query(natural_query)


@tool
async def discover_data(hint: str, limit: int = 50) -> str:
    """
    Data discovery — check what Amazon product data is available in the database.

    Only reads DB, never triggers API calls.

    Args:
        hint: data description, e.g. ASIN list, category name, brand name. "B0F9FS7WQQ" or "bluetooth earphones"
        limit: max sample count (max 50)
    """
    liaison = DataLiaison()
    return await liaison.discover(hint, limit=limit)


@tool
async def call_nova_agent(agent_name: str, params_json: str) -> str:
    """
    调用 Nova 的 Amazon 业务 Agent 执行特定分析任务。

    Args:
        agent_name: Agent 名称，可选值: keyword_expander, review_analyzer,
                   traffic_analyzer, opportunity_judge, market_analyst, competitor_analyst, briefing_generator
        params_json: JSON 格式的参数。所有分析 Agent 均可使用 sub_task 字段指定分析方向。

                    ★ sub_task 支持：传入 {"sub_task": "分析各品牌定价差异"}，
                    该子任务描述会注入到 Agent 的 system prompt 中，指导 Agent 的分析方向。
    """
    try:
        params = json.loads(params_json) if params_json.strip() else {}
    except json.JSONDecodeError:
        return f"参数格式错误，需要 JSON 格式: {params_json}"

    # 从 ContextVar 获取会话 id；没有就开一个 ephemeral session
    conv_id = conv_id_var.get() or f"ephemeral-{uuid.uuid4()}"
    state = session_store.get_or_create(conv_id)

    # ── 提取 orchestrator 分配的 sub_task（新路径） ──
    sub_task = params.pop("sub_task", "")

    # ── DecisionTrace：记录原始 params（intel 注入前） ──
    _raw_params = dict(params)

    # ── 从 _intel_report 注入 found_asins + matched category ──
    intel = state.data.get("_intel_report", {})
    if intel.get("found_asins"):
        params.setdefault("asins", intel["found_asins"])
    # 品类：优先 matched_category_names，再 exploration 的 category_name
    matched_cats = intel.get("matched_category_names", [])
    if matched_cats:
        cat = matched_cats[0]
        params.setdefault("category_name", cat)
        params.setdefault("category", cat)
    else:
        # 从 exploration 中取第一个商品的 category_name
        exploration = intel.get("exploration", {}) or {}
        products = exploration.get("products", []) or []
        if products and products[0].get("category_name"):
            cat = products[0]["category_name"]
            params.setdefault("category_name", cat)
            params.setdefault("category", cat)

    # 如果没有 asins 也没有 category，尝试从 exploration 中提取前 20 个 ASIN
    if not params.get("asins") and not params.get("category") and not params.get("category_name"):
        exploration = intel.get("exploration", {}) or {}
        products = exploration.get("products", []) or []
        if products:
            asins = [p.get("asin") for p in products[:20] if p.get("asin")]
            if asins:
                params["asins"] = asins

    # ── Prompt Engine：注入定制 system prompt ──
    try:
        pe = get_prompt_engine()
        intent_spec: Optional[IntentAnalysisSpec] = state.data.get("_intent_spec")
        if sub_task:
            # ★ 新路径：orchestrator 通过 sub_task 传自然语言子任务
            custom_prompt = pe.customize(agent_name, sub_task=sub_task, session_id=conv_id)
        elif intent_spec:
            # 旧路径（向后兼容）：从 IntentAnalysisSpec 读（已废弃）
            custom_prompt = pe.customize(agent_name, intent_spec, session_id=conv_id)
        else:
            # 兜底：无指令时的默认模板
            custom_prompt = pe.customize(agent_name, session_id=conv_id)
        # 写入 state，agent_wrapper 会读取并注入到 Agent._custom_system_prompt
        state.data["_custom_system_prompt"] = custom_prompt
    except Exception:
        pass  # Prompt Engine 失败不影响主流程

    # ── DecisionTrace：call_nova_agent intel 注入交接 ──
    try:
        tracer = tracer_var.get()
        if tracer:
            tracer.capture_call_nova_agent_handoff(
                agent_name=agent_name,
                raw_params=_raw_params,
                final_params=dict(params),
                intel_report_used=bool(intel),
            )
    except Exception:
        pass

    result = await call_agent(agent_name, params, state=state, conv_id=conv_id)

    # ── DecisionTrace：call_agent 交接 ──
    try:
        tracer = tracer_var.get()
        if tracer:
            tracer.capture_call_agent_handoff(
                agent_name=agent_name,
                params=params,
                custom_prompt=custom_prompt if 'custom_prompt' in dir() and custom_prompt else "",
                state_keys=list(state.data.keys()),
            )
    except Exception:
        pass

    # 持久化 State 到 SQLite（Phase 3）
    _clean_state_for_save(state)
    session_store.save(conv_id)

    output = result.get("result", "")
    if isinstance(output, list):
        # 结构化数据转文本，截断防止 LLM 上下文爆炸
        if len(output) > 5:
            output = output[:5]
        output = json.dumps(output, ensure_ascii=False, indent=2)
    elif isinstance(output, dict):
        output = json.dumps(output, ensure_ascii=False, indent=2)

    # 给 LLM 附加一段 session_state 摘要，便于它判断是否还需继续调用上游 Agent
    state_keys = session_store.snapshot_keys(conv_id) or []
    interesting_keys = [
        k for k in state_keys
        if k in ("expanded_keywords", "collected_products", "review_insights",
                 "sentiment_summary", "customer_needs", "traffic_insights",
                 "competitor_comparison", "keyword_groups", "market_report",
                 "pending_data_requests")
    ]
    state_hint = f"\n\n[会话 state 已有字段: {', '.join(interesting_keys) or '(空)'}]"

    return f"Agent [{agent_name}] 执行结果:\n{output}{state_hint}"


# ── 构建工具列表 ──

def get_tools(include_search_web: bool = True):
    """
    构建工具列表。

    search_web 默认可用——LLM 自己决定要不要搜。
    Phase 0 情报报告已注入 system prompt，LLM 有足够上下文判断"该用数据库还是该搜索"。
    """
    tools = [search_memory, query_db, discover_data, call_nova_agent]
    if include_search_web:
        tools.insert(0, search_web)
    return tools


def _clean_state_for_save(state) -> None:
    """清理 state.data 中不可 JSON 序列化的对象，确保持久化成功"""
    state.data.pop("_intent_spec", None)
    state.data.pop("_intel_report_obj", None)


# ── Phase 0→AgentState 直通 ──


def _dict_to_intent_spec(d: Optional[Dict[str, Any]]) -> Optional[IntentAnalysisSpec]:
    """反序列化 dict → IntentAnalysisSpec（AgentState → call_model）"""
    if not d or not d.get("intent_type"):
        return None
    try:
        intent_type = IntentType(d["intent_type"])
    except ValueError:
        intent_type = IntentType.GENERAL_QUERY
    try:
        depth = AnalysisDepth(d.get("depth", "moderate"))
    except ValueError:
        depth = AnalysisDepth.MODERATE
    return IntentAnalysisSpec(
        intent_type=intent_type,
        depth=depth,
        entities=d.get("entities", []),
        paraphrased_intent=d.get("paraphrased_intent", ""),
        category_hint=d.get("category_hint", ""),
        raw_query=d.get("raw_query", ""),
    )


# ── 图节点 ──

async def _build_history_messages(conv_id: str, current_input: str) -> tuple:
    """从 SQLite 加载历史消息，构建多轮上下文（不含当前 user_input）

    策略：
    - 最近 HISTORY_FULL_ROUNDS 轮：完整保留 user + assistant + tool
    - 更早的轮次：只保留 user + assistant（省 token）
    - 当前 user_input 已在历史最末（刚 append 的），需排除
    - ★ 过滤 dead-end assistant 消息（"没有...信息"类），防止历史污染
    - ★ 返回 (history, correction_prefix)：correction_prefix 用于注入 system prompt

    Returns:
        tuple: (history_list, correction_prefix_str)
    """
    durable = get_durable_session()
    messages = await durable.get_messages(conv_id, limit=HISTORY_MAX_MESSAGES)

    if not messages:
        return [], ""

    # 排除最后一条（就是刚 append 的当前 user_input）
    if messages and messages[-1]["role"] == "user" and messages[-1]["content"] == current_input:
        messages = messages[:-1]

    if not messages:
        return [], ""

    # ★ 替换 dead-end assistant 内容（保留对话结构，清除毒性）
    _DEAD_END_CORRECTION = "[系统修正：之前的回答因数据状态未刷新而不准确，现在数据已在本地库就绪]"
    _DEAD_END_PATTERNS = (
        "没有", "无法", "无相关", "找不到", "不存在",
        "do not have", "don't have", "no information",
        "not available", "cannot find", "could not find",
    )

    # 按轮次分组：一轮 = user + (tool*) + assistant
    rounds = []
    current_round = []
    for msg in messages:
        current_round.append(msg)
        if msg["role"] == "assistant":
            rounds.append(current_round)
            current_round = []
    if current_round:
        rounds.append(current_round)

    # ★ 统计 dead-end 轮次 + 收集主题（用于 correction_prefix）
    dead_end_rounds = 0
    dead_end_topics = set()
    for round_msgs in rounds:
        for msg in round_msgs:
            if msg["role"] == "assistant":
                content = (msg.get("content") or "").lower()
                if any(pattern in content for pattern in _DEAD_END_PATTERNS):
                    dead_end_rounds += 1
                    for m in round_msgs:
                        if m["role"] == "user":
                            user_text = m.get("content", "")
                            asins = _ASIN_PATTERN.findall(user_text)
                            if asins:
                                dead_end_topics.update(asins)
                            else:
                                dead_end_topics.add(user_text[:40])

    # 构建历史：所有轮次都保留结构，但替换 dead-end 内容
    history = []
    total_rounds = len(rounds)
    for i, round_msgs in enumerate(rounds):
        is_recent = (total_rounds - i) <= HISTORY_FULL_ROUNDS
        for msg in round_msgs:
            if msg["role"] == "tool":
                continue
            if msg["role"] == "assistant":
                content = msg.get("content", "") or ""
                if not content:
                    continue
                # ★ 所有 dead-end assistant 内容替换为纠正标记（不分近期/非近期）
                if any(pattern in content.lower() for pattern in _DEAD_END_PATTERNS):
                    content = _DEAD_END_CORRECTION
                elif not is_recent and len(content) > 500:
                    content = content[:500] + "..."
                history.append({"role": "assistant", "content": content})
            elif msg["role"] == "user":
                content = msg["content"]
                if not is_recent and len(content) > 500:
                    content = content[:500] + "..."
                history.append({"role": "user", "content": content})

    # ★ 构建纠正前缀
    correction_prefix = ""
    if dead_end_rounds > 0:
        topic_str = ", ".join(sorted(dead_end_topics)[:3])
        correction_prefix = (
            f"\n[历史纠正] 之前的 {dead_end_rounds} 次查询（涉及 {topic_str} 等）因系统故障未能正确返回数据。"
            f"现在数据已在本地库中就绪，请按系统提示正常调用 Agent 获取。\n"
        )

    return history, correction_prefix


def _build_state_summary(conv_id: str) -> str:
    """生成当前会话 State 的纯数据摘要（不含行动指令），注入 system_prompt 供 LLM 了解已有数据"""
    state = session_store.get_or_create(conv_id)
    if not state.data:
        return ""

    lines = []

    # ── Phase 0 情报报告 —— 只报告事实，不指挥 LLM ──
    intel_report = state.data.get("_intel_report")
    if intel_report:
        found = intel_report.get("found_asins", [])
        missing = intel_report.get("missing_asins", [])
        exploration = intel_report.get("exploration", {}) or {}
        explored_asins = exploration.get("total_distinct_asins", 0) if exploration else 0
        categories = exploration.get("categories_found", {}) or {}
        brands = exploration.get("brands_found", {}) or {}
        products = exploration.get("products", []) or []

        # ── 情况 A: 有明确 ASIN 命中 ──
        if found:
            lines.append(f"- **匹配 ASIN** ({len(found)} 个): {', '.join(found[:10])}")
            lines.append(f"- **数据覆盖**: 180+ 字段完整（价格/BSR/评论/销量/卖家/Listing/变体/配送/FBA/库存/促销/属性/品牌/类目）")

        # ── 情况 B: 品类探索出商品（无 ASIN 命中） ──
        elif explored_asins > 0:
            cat_str = ", ".join(list(categories.keys())[:5]) if categories else "?"
            brand_str = ", ".join(list(brands.keys())[:8]) if brands else "?"
            lines.append(f"- **跨列探索**: {explored_asins} 个相关商品（品类: {cat_str}, 品牌: {brand_str}）")

        # ── 情况 C: 无 ASIN 也无品类命中 ──
        else:
            catalog = intel_report.get("catalog")
            if catalog and catalog.get("total_products", 0) > 0:
                cats = catalog.get("categories", [])
                lines.append(f"- **数据库概况**: {catalog['total_products']} 个商品（品类: {', '.join(c['name'] for c in cats[:8])}）")
            else:
                lines.append(f"- **数据库状态**: 本地库中未找到匹配用户输入的商品数据")

        # ── 缺失 ASIN 提示（纯数据） ──
        if missing:
            lines.append(f"- **缺失 ASIN** ({len(missing)} 个): {', '.join(missing[:5])}（不在本地库中）")

    # ── collected_products 高亮提示（纯数据） ──
    collected = state.data.get("collected_products") or []
    if collected:
        asin_list = []
        for p in collected:
            if isinstance(p, dict):
                asin_list.append(p.get("asin", "?"))
            elif isinstance(p, str):
                asin_list.append(p)
        lines.append(f"- **已采集商品**: {len(collected)} 个（ASIN: {', '.join(asin_list[:8])}）")

    # ── 其他 State key 摘要 ──
    for key, value in state.data.items():
        if key.startswith("_"):
            continue
        if isinstance(value, list):
            lines.append(f"- **{key}**: {len(value)} 条记录")
        elif isinstance(value, dict):
            summary_keys = list(value.keys())[:5]
            lines.append(f"- **{key}**: dict({', '.join(summary_keys)})")
        elif isinstance(value, str) and len(value) > 100:
            lines.append(f"- **{key}**: {value[:100]}...")
        else:
            lines.append(f"- **{key}**: {value}")

    # ── 产品预取数据：让 LLM 直接看到真实数值（解决"抽象承诺"问题） ──
    intel_report = state.data.get("_intel_report")
    if intel_report:
        preview = intel_report.get("product_preview", {})
        if preview:
            lines.append("")
            lines.append("### 商品预取数据（以下为 DB 中的真实数值）")
            for asin, data in preview.items():
                title = (data.get("title") or "?")[:60]
                price = data.get("current_price", "?")
                rating = data.get("rating", "?")
                bsr = data.get("current_bsr", "?")
                reviews = data.get("review_count", "?")
                monthly = data.get("monthly_sold", "?")
                brand = data.get("brand", "?")
                seller_count = data.get("seller_count", "?")
                is_fba = "✅FBA" if data.get("is_fba") else ""
                is_prime = "✅Prime" if data.get("is_prime") else ""
                coupon = "🎟️有Coupon" if data.get("has_coupon") else ""
                stock = data.get("stock_level", "")
                stock_str = f"库存{stock}" if stock else ""
                badges = " ".join(filter(None, [is_fba, is_prime, coupon, stock_str]))
                lines.append(
                    f"\n  **{asin}**\n"
                    f"  - 标题: {title}\n"
                    f"  - 品牌: {brand} | 价格: ${price} | 评分: {rating}⭐ ({reviews}评) | "
                    f"BSR: #{bsr} | 月销: {monthly}\n"
                    f"  - 卖家数: {seller_count} | {badges}".rstrip()
                )

    if not lines:
        return ""

    return "\n## 当前数据状态\n" + "\n".join(lines)


def should_continue(state: AgentState) -> str:
    """判断是否继续循环"""
    messages = state["messages"]
    last_message = messages[-1]
    # 如果最后一条消息是 AI 且没有 tool_calls，说明 LLM 决定直接回答
    if isinstance(last_message, dict):
        if last_message.get("role") == "assistant" and not last_message.get("tool_calls"):
            return "end"
    return "continue"


async def call_model(state: AgentState) -> Dict[str, Any]:
    """调用 LLM 决定下一步"""
    llm = _get_llm()
    llm_with_tools = llm.bind_tools(get_tools(include_search_web=True))

    # ── 注入相关历史记忆 ──
    memory_context = ""
    try:
        user_msg = ""
        for msg in reversed(state["messages"]):
            if msg.get("role") == "user":
                user_msg = msg["content"]
                break
        if user_msg:
            relevant = memory.search_all(user_msg, k=3)
            if relevant:
                mem_lines = []
                for r in relevant:
                    meta = r['metadata']
                    mem_lines.append(f"- [{meta.get('timestamp', '')}] {r['content'][:200]}")
                memory_context = "\n相关历史记忆:\n" + "\n".join(mem_lines)
    except Exception:
        pass  # 记忆注入失败不影响主流程

    # ── 注入 State 摘要 ──
    conv_id = conv_id_var.get()
    state_summary = _build_state_summary(conv_id) if conv_id else ""

    # ── Prompt Engine：获取/构造 intent_spec（不 gate prompt 路径） ──
    # ★ Phase 0 直通：优先从 AgentState 读取（LangGraph 保证可达，无侧通道）
    intent_spec: IntentAnalysisSpec
    try:
        spec_from_state = _dict_to_intent_spec(state.get("intent_spec_data"))
        if spec_from_state is not None:
            intent_spec = spec_from_state
        else:
            # 兜底：从 session_store 读（Phase 0 缓存）
            session_data = None
            if conv_id:
                s = session_store.get_or_create(conv_id)
                session_data = s.data if s else None
            cached = session_data.get("_intent_spec") if session_data else None
            if cached is not None:
                intent_spec = cached
            elif conv_id:
                pe = get_prompt_engine()
                user_msg = ""
                for msg in reversed(state["messages"]):
                    if msg.get("role") == "user":
                        user_msg = msg["content"]
                        break
                if user_msg:
                    intent_spec = pe.translate(user_msg, session_id=conv_id)
                    if session_data:
                        session_data["_intent_spec"] = intent_spec
                else:
                    intent_spec = IntentAnalysisSpec(
                        intent_type=IntentType.GENERAL_QUERY,
                        raw_query=user_msg or "对话查询",
                        paraphrased_intent="用户查询",
                    )
            else:
                intent_spec = IntentAnalysisSpec(
                    intent_type=IntentType.GENERAL_QUERY,
                    raw_query="对话查询",
                    paraphrased_intent="用户查询",
                )
    except Exception:
        intent_spec = IntentAnalysisSpec(
            intent_type=IntentType.GENERAL_QUERY,
            raw_query="对话查询",
            paraphrased_intent="用户查询",
        )

    # ── 使用 PromptEngine 动态生成 orchestrator prompt（按 intent_type 分模板） ──
    pe = get_prompt_engine()
    agents_info = list_agents()

    # ★ 检测 product_preview 是否存在（决定角色模板是否切换为"直接使用数据"模式）
    intel_from_state = state.get("intel_report")
    has_product_preview = False
    if intel_from_state and intel_from_state.get("product_preview"):
        has_product_preview = True

    system_prompt = pe.build_orchestrator_prompt(
        spec=intent_spec,
        agents_info=agents_info,
        memory_context=memory_context,
        state_summary=state_summary,
        has_product_preview=has_product_preview,
    )

    # ★ 注入历史纠正前缀（过滤 dead-end 后，防止历史污染）
    correction_prefix = state.get("correction_prefix", "")
    if correction_prefix:
        system_prompt += correction_prefix

    # ── DecisionTrace：记录 LLM 接收到的上下文 ──
    try:
        tracer = tracer_var.get()
        if tracer:
            intel_report = None
            intel_summary = ""
            try:
                from backend.core.memory.state_store import session_store
                s = session_store.get_or_create(conv_id)
                intel_report = s.data.get("_intel_report") if s else None
                if intel_report:
                    found = intel_report.get("found_asins", [])
                    missing = intel_report.get("missing_asins", [])
                    exploration = intel_report.get("exploration", {}) or {}
                    total = exploration.get("total_distinct_asins", 0) or intel_report.get("asin_product_count", 0)
                    intel_summary = f"DB {len(found)}个ASIN命中, {len(missing)}个缺失, {total}个品类商品"
            except Exception:
                pass
            mem_count = 0
            if 'relevant' in dir() and relevant:
                mem_count = len(relevant)
            tracer.capture_loaded_context(
                system_prompt=system_prompt,
                had_intel=bool(intel_report),
                intel_summary=intel_summary,
                had_memories=bool(memory_context),
                memory_count=mem_count,
                memory_text=memory_context,
                had_state_summary=bool(state_summary),
                state_summary=state_summary,
            )
            # ── state → system_prompt 交接 ──
            tracer.capture_state_to_system_prompt(state_summary)
    except Exception:
        pass

    # 转换消息格式
    langchain_messages = [SystemMessage(content=system_prompt)]
    for msg in state["messages"]:
        if msg["role"] == "user":
            langchain_messages.append(HumanMessage(content=msg["content"]))
        elif msg["role"] == "assistant":
            tool_calls = msg.get("tool_calls")
            if tool_calls:
                langchain_messages.append(AIMessage(
                    content=msg.get("content", "") or "",
                    tool_calls=[{"id": tc["id"], "name": tc["name"], "args": tc["args"], "type": "tool_call"} for tc in tool_calls],
                ))
            else:
                content = msg.get("content", "") or ""
                if content:
                    langchain_messages.append(AIMessage(content=content))
        elif msg["role"] == "tool":
            langchain_messages.append(ToolMessage(content=msg["content"], tool_call_id=msg.get("tool_call_id", "")))

    try:
        fallback_llm = _get_fallback_llm()
        response = await _llm_invoke_with_fallback(
            llm_with_tools,
            langchain_messages,
            fallback_llm=fallback_llm,
        )
    except AttributeError as e:
        if "'str' object has no attribute 'model_dump'" in str(e):
            return {"messages": [{
                "role": "assistant",
                "content": "⚠️ LLM 服务返回异常响应，请稍后重试。如果问题持续，请检查 API 服务状态。",
            }]}
        raise
    except Exception as e:
        return {"messages": [{
            "role": "assistant",
            "content": f"⚠️ LLM 调用失败（多次重试后仍失败）: {e}",
        }]}

    # 转换回我们的消息格式
    new_message = {
        "role": "assistant",
        "content": response.content or "",
    }
    if response.tool_calls:
        new_message["tool_calls"] = [
            {
                "id": tc["id"],
                "name": tc["name"],
                "args": tc["args"],
            }
            for tc in response.tool_calls
        ]

    return {"messages": [new_message]}


async def execute_tools(state: AgentState) -> Dict[str, Any]:
    """执行 LLM 选择的工具"""
    last_message = state["messages"][-1]
    tool_calls = last_message.get("tool_calls", [])
    
    results = []
    for tc in tool_calls:
        tool_name = tc["name"]
        tool_args = tc["args"]
        tool_id = tc["id"]

        # ── DecisionTrace：工具开始 ──
        try:
            tracer = tracer_var.get()
            if tracer:
                tracer.start_tool_call(tool_name, tool_args)
        except Exception:
            pass

        try:
            # 每个工具调用加 60 秒超时，防止同步阻塞卡死事件循环
            if tool_name == "search_web":
                result = await asyncio.wait_for(search_web.ainvoke(tool_args), timeout=60)
            elif tool_name == "search_memory":
                result = await asyncio.wait_for(search_memory.ainvoke(tool_args), timeout=30)
            elif tool_name == "query_db":
                result = await asyncio.wait_for(query_db.ainvoke(tool_args), timeout=30)
            elif tool_name == "discover_data":
                result = await asyncio.wait_for(discover_data.ainvoke(tool_args), timeout=30)
            elif tool_name == "call_nova_agent":
                # ── DecisionTrace：Agent 调用开始 ──
                agent_name = tool_args.get("agent_name", "unknown")
                try:
                    tracer = tracer_var.get()
                    if tracer:
                        tracer.start_agent_call(agent_name, tool_args)
                except Exception:
                    pass

                result = await asyncio.wait_for(call_nova_agent.ainvoke(tool_args), timeout=120)

                # ── DecisionTrace：Agent 调用结束 ──
                try:
                    tracer = tracer_var.get()
                    if tracer:
                        sub_task = tool_args.get("sub_task", "")
                        tracer.end_agent_call(
                            agent_name=agent_name,
                            result=str(result)[:500],
                            params=tool_args,
                            sub_task=sub_task,
                        )
                except Exception:
                    pass

                # Agent 输出自动保存到记忆
                try:
                    memory.save_memory(
                        content=f"Agent [{agent_name}] 分析结果:\n{result[:1000]}",
                        importance=7,
                        tags=f"agent_output,{agent_name}",
                        source=agent_name,
                    )
                except Exception:
                    pass
            else:
                result = f"未知工具: {tool_name}"

            # ── DecisionTrace：工具结束（成功） ──
            try:
                tracer = tracer_var.get()
                if tracer and tool_name != "call_nova_agent":
                    tracer.end_tool_call(tool_name, str(result)[:500], status="ok")
            except Exception:
                pass

        except Exception as e:
            result = f"工具 [{tool_name}] 执行失败: {e}"
            # ── DecisionTrace：工具结束（失败） ──
            try:
                tracer = tracer_var.get()
                if tracer:
                    tracer.end_tool_call(tool_name, str(e), status="error")
            except Exception:
                pass
        
        results.append({
            "role": "tool",
            "content": str(result)[:3000],
            "tool_call_id": tool_id,
            "name": tool_name,
        })

    return {"messages": results, "tool_results": results}


# ── 构建图 ──

def build_graph():
    """构建 LangGraph 执行图"""
    workflow = StateGraph(AgentState)

    workflow.add_node("agent", call_model)
    workflow.add_node("action", execute_tools)

    workflow.set_entry_point("agent")

    # 条件边：LLM 决定继续还是结束
    workflow.add_conditional_edges(
        "agent",
        should_continue,
        {
            "continue": "action",
            "end": END,
        },
    )

    # action 执行完后回到 agent
    workflow.add_edge("action", "agent")

    return workflow.compile()


# ── 知识摘要（Step 4） ──

async def _try_summarize(conv_id: str) -> None:
    """尝试对会话生成摘要，失败静默"""
    try:
        await summarize_conversation(conv_id, memory=memory)
    except Exception as e:
        logger = __import__("logging").getLogger(__name__)
        logger.debug(f"[Summarizer] Skipped for {conv_id}: {e}")


# ── 主入口（普通模式） ──

async def run_orchestrator(user_input: str, conversation_id: Optional[str] = None) -> str:
    """
    运行 orchestrator，处理用户输入

    Args:
        user_input: 用户输入文本
        conversation_id: 会话 id；同一 conv_id 的多次调用共享 SessionStore 中的 State，
                         使 Nova 流水线 Agent 能正常串起来。未传则生成临时 uuid。

    Returns:
        最终回答
    """
    conv_id = conversation_id or f"ephemeral-{uuid.uuid4()}"
    token = conv_id_var.set(conv_id)
    durable = get_durable_session()
    try:
        # Step 2: 持久化用户消息
        await durable.append_message(conv_id, "user", user_input)

        # Step 3: 加载历史消息构建多轮上下文
        history, correction_prefix = await _build_history_messages(conv_id, user_input)

        graph = build_graph()

        initial_state: AgentState = {
            "messages": history + [{"role": "user", "content": user_input}],
            "user_input": user_input,
            "final_response": None,
            "tool_results": [],
            "intel_collected": True,
            # ★ 非流式模式没有 Phase 0，保持 None
            "intent_spec_data": None,
            "intel_report": None,
            "correction_prefix": correction_prefix,
        }

        final_state = await graph.ainvoke(initial_state)

        # 持久化最终 State 到 SQLite
        non_stream_state = session_store.get_or_create(conv_id)
        _clean_state_for_save(non_stream_state)
        session_store.save(conv_id)

        # Step 2: 持久化所有 tool 和 assistant 消息
        final_response = "处理完成，但未能生成回答。"
        for msg in final_state["messages"]:
            if msg["role"] == "tool":
                await durable.append_message(
                    conv_id, "tool", msg["content"][:3000], tool_name=msg.get("name")
                )
            elif msg["role"] == "assistant" and msg.get("content") and not msg.get("tool_calls"):
                final_response = msg["content"]

        await durable.append_message(conv_id, "assistant", final_response)

        # 保存到记忆（带重要性评分）
        memory.save_chat(user_input, final_response, metadata={"importance": 6, "tags": "user_query", "conversation_id": conv_id})

        # Step 4: 异步触发知识摘要（不阻塞返回）
        asyncio.create_task(_try_summarize(conv_id))

        return final_response
    finally:
        conv_id_var.reset(token)


# ── ASIN 自动采集辅助函数 ──


# ── 主入口（流式模式，支持 SSE） ──


async def run_orchestrator_stream(user_input: str, conversation_id: Optional[str] = None):
    """
    流式运行 orchestrator，逐事件 yield 供 SSE 推送

    Args:
        user_input: 用户输入
        conversation_id: 会话 id；同一会话内多次调用共享 SessionStore State

    Yields:
        dict: 事件对象，包含 type 和 data
    """
    conv_id = conversation_id or f"ephemeral-{uuid.uuid4()}"
    token = conv_id_var.set(conv_id)
    durable = get_durable_session()

    # ── Phase 0 数据情报收集 ──
    state = session_store.get_or_create(conv_id)

    # ── Step 1: Phase 0 — 数据情报收集（不再做二元"就绪"判断） ──
    # 用 PromptEngine 理解意图 → DataLiaison 跨列探索 → 报告给 LLM 自己决策
    intel: Optional[DataIntelligenceReport] = None
    try:
        pe = get_prompt_engine()
        intent_spec = pe.translate(user_input, session_id=conv_id)
        state.data["_intent_spec"] = intent_spec  # 缓存给后续 ReAct 使用
        state.data["_intent_spec_data"] = {
            "intent_type": intent_spec.intent_type.value if intent_spec.intent_type else "",
            "depth": intent_spec.depth.value if intent_spec.depth else "",
            "entities": intent_spec.entities,
            "paraphrased_intent": intent_spec.paraphrased_intent,
            "category_hint": intent_spec.category_hint,
            "raw_query": intent_spec.raw_query,
        }

        # DataLiaison 收集数据情报
        liaison = DataLiaison()
        intel = await liaison.collect_intel(intent_spec)

        # 如果有缺失 ASIN 且数量不大，冷启动采集
        if intel.can_collect_asins:
            yield {"type": "status", "data": f"🔍 发现 {len(intel.can_collect_asins)} 个 ASIN 不在本地数据库，正在采集..."}
            results = await liaison.collect_missing(intel.can_collect_asins)
            success = sum(1 for v in results.values() if v)
            yield {"type": "status", "data": f"✅ 已采集 {success}/{len(intel.can_collect_asins)} 个 ASIN 数据"}
            # 采集完成后再查一次
            intel = await liaison.collect_intel(intent_spec)

        # 将情报写入 state——不做"够不够"的判断，原样给 LLM
        state.data["_intel_report"] = {
            "found_asins": intel.found_asins,
            "missing_asins": intel.missing_asins,
            "matched_category_names": intel.matched_category_names,
            "matched_product_types": intel.matched_product_types,
            "exploration": intel.exploration,
            "catalog": intel.catalog,
            "can_collect_asins": intel.can_collect_asins,
            "asin_fields_coverage": intel.asin_fields_coverage,
            "asin_product_count": intel.asin_product_count,
            "product_preview": intel.product_preview,
        }
        state.data["_intel_report_obj"] = intel  # 保留对象引用，用于 to_llm_context()

        # yield 情报摘要
        total = intel.total_products_available
        if total > 0:
            yield {"type": "status", "data": f"📊 DB 探索到 {total} 个相关商品（品类: {intel.matched_category_names[:3] or '?'}），情报已就绪，LLM 将自行决策"}
        else:
            yield {"type": "status", "data": f"ℹ️ DB 未找到匹配用户输入的商品，原始情报已注入 system prompt，LLM 将自行决策"}
    except Exception as e:
        logger = __import__("logging").getLogger(__name__)
        logger.warning(f"[Phase 0] 情报收集失败: {e}", exc_info=True)
        pass  # Phase 0 失败不影响主流程

    # ── DecisionTrace：初始化追踪器 ──
    tracer = DecisionTracer(conv_id, user_input)
    tracer_var.set(tracer)
    tracer.capture_intent(state.data.get("_intent_spec_data", {}))
    if intel:
        to_llm_text = intel.to_llm_context() if hasattr(intel, 'to_llm_context') else ""
        tracer.capture_data_liaison({
            "found_asins": intel.found_asins,
            "missing_asins": intel.missing_asins,
            "matched_category_names": intel.matched_category_names,
            "matched_product_types": intel.matched_product_types,
            "exploration": intel.exploration,
            "catalog": intel.catalog,
            "asin_product_count": intel.asin_product_count,
            "can_collect_asins": intel.can_collect_asins,
            "asin_fields_coverage": intel.asin_fields_coverage,
            "category_hint": intel.category_hint,
        }, to_llm_context_text=to_llm_text)

    # 注册分析树 SSE 事件队列
    tree_queue: asyncio.Queue = asyncio.Queue(maxsize=200)
    analysis_tree_manager.register_queue(conv_id, tree_queue)

    try:
        # Step 2: 持久化用户消息
        await durable.append_message(conv_id, "user", user_input)

        # Step 3: 加载历史消息构建多轮上下文
        history, correction_prefix = await _build_history_messages(conv_id, user_input)

        graph = build_graph()

        initial_state: AgentState = {
            "messages": history + [{"role": "user", "content": user_input}],
            "user_input": user_input,
            "final_response": None,
            "tool_results": [],
            "intel_collected": True,
            # ★ Phase 0 产出直通 AgentState——不走 session_store 侧通道
            "intent_spec_data": state.data.get("_intent_spec_data"),
            "intel_report": state.data.get("_intel_report"),
            "correction_prefix": correction_prefix,
        }

        yield {"type": "status", "data": "🤖 开始分析..."}

        final_response = ""
        _agent_timers: dict = {}
        async for event in graph.astream(initial_state):
            # 穿插分析树事件（不阻塞）
            while not tree_queue.empty():
                try:
                    tree_event = tree_queue.get_nowait()
                    yield tree_event
                except asyncio.QueueEmpty:
                    break
            node_name = list(event.keys())[0]
            state_data = event[node_name]

            if node_name == "action":
                for msg in state_data.get("messages", []):
                    if isinstance(msg, dict) and msg.get("role") == "tool":
                        tool_name = msg.get("name", "unknown")
                        # 计算耗时
                        elapsed = None
                        if tool_name in _agent_timers:
                            elapsed = round(time.time() - _agent_timers.pop(tool_name), 2)
                        yield {"type": "agent_end", "data": {"name": tool_name, "elapsed_s": elapsed}}
                        yield {"type": "tool_result", "data": f"🔧 {tool_name} 执行完成"}
                        # 从 SessionStore 提取驾驶舱数据
                        # tool_name 是 "call_nova_agent"，需通过 tool_call_id 映射回真实 Agent 名
                        real_agent = _agent_name_by_call_id.pop(msg.get("tool_call_id", ""), "")
                        cockpit_target = real_agent if real_agent else tool_name
                        if cockpit_target in AGENT_CATEGORY_LABELS:   # 只对业务 Agent
                            try:
                                state = session_store.get_or_create(conv_id)
                                cockpit = extract_cockpit_data(cockpit_target, state.data)
                                if cockpit:
                                    yield {"type": "cockpit_update", "data": cockpit}
                            except Exception:
                                pass
                        # Step 2: 持久化工具结果
                        await durable.append_message(
                            conv_id, "tool", msg["content"][:3000], tool_name=tool_name
                        )
            elif node_name == "agent":
                for msg in state_data.get("messages", []):
                    if not isinstance(msg, dict):
                        continue
                    if msg.get("tool_calls"):
                        for tc in msg["tool_calls"]:
                            _agent_timers[tc["name"]] = time.time()
                            # ── 记录 tool_call_id → 真实 Agent 名（驾驶舱使用） ──
                            if tc["name"] == "call_nova_agent":
                                real_agent_name = tc.get("args", {}).get("agent_name", "")
                                if real_agent_name:
                                    _agent_name_by_call_id[tc.get("id", "")] = real_agent_name
                            yield {"type": "agent_start", "data": {"name": tc["name"], "args": tc["args"]}}
                            yield {
                                "type": "tool_call",
                                "data": {
                                    "name": tc["name"],
                                    "args": tc["args"],
                                    "id": tc.get("id", str(uuid.uuid4())),
                                },
                            }
                    elif msg.get("role") == "assistant" and msg.get("content"):
                        final_response = msg["content"]

        if not final_response:
            final_response = "处理完成，但未能生成回答。"

        # 排空剩余的树事件
        while not tree_queue.empty():
            try:
                tree_event = tree_queue.get_nowait()
                yield tree_event
            except asyncio.QueueEmpty:
                break

        # 推送完整树结构（供前端初始化渲染）
        tree_dict = analysis_tree_manager.to_dict(conv_id)
        if tree_dict and tree_dict.get("branches"):
            yield {"type": "tree_full", "data": tree_dict}

        # 流式输出最终回答（按句/段分块）
        yield {"type": "start_response", "data": ""}
        import re
        chunks = re.split(r'(?<=[。！？\n])', final_response)
        for chunk in chunks:
            if chunk.strip():
                yield {"type": "response_chunk", "data": chunk}
                await asyncio.sleep(0.02)

        # ── DecisionTrace：最终汇总 → 终端打印 + 写文件 ──
        try:
            tracer = tracer_var.get()
            if tracer:
                tracer.capture_state_keys(dict(state.data))
                tracer.finalize(final_answer=final_response)
        except Exception:
            pass

        yield {"type": "done", "data": ""}

        # Step 2: 持久化 assistant 回答
        await durable.append_message(conv_id, "assistant", final_response)

        # 持久化最终 State 到 SQLite
        _clean_state_for_save(state)
        session_store.save(conv_id)

        # 保存到记忆
        memory.save_chat(
            user_input,
            final_response,
            metadata={"importance": 6, "tags": "user_query", "conversation_id": conv_id},
        )

        # Step 4: 异步触发知识摘要（不阻塞返回）
        asyncio.create_task(_try_summarize(conv_id))
    finally:
        conv_id_var.reset(token)
        analysis_tree_manager.unregister_queue(conv_id)
