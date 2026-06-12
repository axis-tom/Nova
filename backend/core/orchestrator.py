"""
Orchestrator — 核心调度引擎

三层架构：
  Level 1: Intent Router（代码路由） → 判断走哪条 Pipeline
  Level 2: Deterministic Pipeline（固定流水线） → 确定性数据获取+分析，不走 LLM
  Level 3: LLM Analysis（只写注释） → 基于结构化数据写解读

不再使用 ReAct 循环。LLM 不参与工具决策，只基于已有数据写分析注释。
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
from backend.core.data_tools import get_data_tools
from backend.core.data_tools.engine import get_query_engine
from backend.core.data_tools import (  # 5 个新数据工具（用于 execute_tools 路由）
    get_entity_details,
    compare_entities,
    search_entities,
    get_trends,
    analyze_custom,
)
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
async def get_product_data(asins: str) -> str:
    """
    从本地数据库查询 Amazon 商品完整数据。

    优先查本地库，如本地不存在则自动通过 API 采集后返回。
    可查询 180+ 字段：价格、BSR、销量、评论、Listing、卖家、配送、FBA、库存、促销等。

    Args:
        asins: ASIN 列表，逗号或空格分隔，如 "B0F9FS7WQQ" 或 "B0F9FS7WQQ,B0XXXXXX"
    """
    return await _query_product_data(asins)


# ── 非 tool 版本：供系统层直接调用（绕过 LLM tool_call 机制） ──

async def _query_product_data(asins: str) -> str:
    """从本地 PostgreSQL 查询 Amazon 商品数据。
    如本地不存在，自动通过 API（Keepa/Rainforest/Canopy）采集后返回。
    此函数不经过 LangChain @tool 装饰，供系统层在 Phase 0 直接调用。"""
    asin_list = [a.strip() for a in re.split(r'[,，\s]+', asins) if a.strip()]
    if not asin_list:
        return "请提供至少一个 ASIN"
    asin_list = asin_list[:20]
    from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
    from sqlalchemy import select
    from backend.data.models.amazon_product import AmazonProduct
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        return "数据库 URL 未配置"
    engine = create_async_engine(database_url, echo=False, pool_pre_ping=True, pool_recycle=3600)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    try:
        async with factory() as session:
            stmt = select(AmazonProduct).where(
                AmazonProduct.asin.in_(asin_list), AmazonProduct.domain == "US",
            )
            result = await session.execute(stmt)
            products = result.scalars().all()

            # ── 收集缺失 ASIN，走 DataProvider 冷启动 ──
            found_asins = {p.asin for p in products}
            missing_asins = [a for a in asin_list if a not in found_asins]
            if missing_asins:
                from backend.aqueduct.data_provider import DataProvider
                provider = DataProvider()
                for ma in missing_asins:
                    raw = await provider.get_product_blocking(ma)
                    if raw:
                        pass  # 已写入 DB，下一行代码会重新查

                # 冷启动完成后重新查（含新采集的）
                if missing_asins:
                    stmt2 = select(AmazonProduct).where(
                        AmazonProduct.asin.in_(missing_asins), AmazonProduct.domain == "US",
                    )
                    result2 = await session.execute(stmt2)
                    extra = result2.scalars().all()
                    products = list(products) + list(extra)
            lines = []
            found = set()
            for p in products:
                found.add(p.asin)
                title = (p.title or "?")[:80]
                lines.append(f"**{p.asin}**")
                lines.append(f"  标题: {title}")
                lines.append(f"  品牌: {p.brand or '?'} | 价格: ${p.current_price or '?'} | 评分: {p.rating or '?'}⭐ ({p.review_count or 0}评)")
                lines.append(f"  BSR: #{p.current_bsr or '?'} | 月销: {p.monthly_sold or '?'} | 年销: {p.annual_sold or '?'}")
                lines.append(f"  卖家数: {p.seller_count or '?'} | FBA: {'✅' if p.is_fba else '❌'} | Prime: {'✅' if p.is_prime else '❌'}")
                if p.category_name:
                    lines.append(f"  分类: {p.category_name} | 类型: {p.product_type or '?'}")
                if p.has_coupon:
                    lines.append(f"  🎟️ 有 Coupon")
                if p.feature_bullets and isinstance(p.feature_bullets, list):
                    for b in p.feature_bullets[:3]:
                        lines.append(f"  卖点: {b[:100]}")
                lines.append("")
            missing = [a for a in asin_list if a not in found]
            if missing:
                lines.append(f"⚠️ 以下 ASIN 不在本地库中: {', '.join(missing)}")
            return "\n".join(lines)
    finally:
        await engine.dispose()


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

    # ── DecisionTrace：Agent 加载信息（每秒 Agent 从 DB 加载了哪些数据） ──
    try:
        tracer = tracer_var.get()
        agent_load_info = result.get("agent_load_info", {})
        if tracer and agent_load_info:
            tracer.capture_agent_load_db(
                agent_name=agent_name,
                asins_queried=agent_load_info.get("asins_queried", []),
                category_queried=agent_load_info.get("category_queried", ""),
                products_loaded=agent_load_info.get("products_loaded", 0),
                fields_available=agent_load_info.get("fields_available", 0),
            )
    except Exception:
        pass

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


@tool
async def query_analysis() -> str:
    """
    获取当前会话最近一次完整分析的完整证据链和原始数据快照。

    任何时候用户追问上一个分析的细节（价格带、评论、竞品、评分、市场），
    或者你拿到的数据看起来需要核实时，**优先调这个工具**，不要反问用户要数据。

    返回 JSON 格式的原始证据，包含：
    - data_snapshot: ⭐ 原始 ASIN 数据快照（冻住的真相源），每个 ASIN 的 current_price、monthly_sold、rating、review_count、current_bsr、brand 等
    - price_bands: 各价格带的商品数、平均 BSR、平均评分、平均月销（直接回答价格类问题）
    - brand_concentration: 品牌数、Top3 份额、集中度、进入壁垒、具体品牌列表
    - market_volume: 月销总量、月营收、均价、BSR 范围
    - review_barrier: 评论壁垒等级、评论数分布、中位数/平均数/最值
    - rating_health: 评分分布、健康分、各档占比
    - seller_composition: FBA/FBM/Prime 占比
    - opportunities: 市场机会列表
    - risks: 风险列表
    - trends: BSR/价格趋势数据

    拿到 JSON 后直接引用具体数值回答。如果 JSON 里找不到用户问的数据，
    再用其他工具去查。**不要反问用户**——你手里已经有分析过的完整数据快照和证据链了。
    """
    return await _query_analysis()


async def _query_analysis() -> str:
    """从 Session State 中读取最近一次 Pipeline 的结构化分析结果（含原始证据）"""
    import json as _json
    conv_id = conv_id_var.get()
    if not conv_id:
        return "当前没有活跃的会话"
    state = session_store.get_or_create(conv_id)
    pipeline = state.data.get("_last_pipeline")
    if not pipeline:
        return "尚未进行过产品分析。请先提供 ASIN 做选品分析。"

    structured = pipeline.get("structured", {})
    decision = structured.get("decision_support", {})
    asins = structured.get("asins_analyzed", [])
    deterministic = structured.get("deterministic", {})

    # ── 原始证据数据（JSON 格式，LLM 可直接引用具体数值） ──
    if deterministic:
        evidence = {}
        mv = deterministic.get("market_volume", {})
        if mv:
            evidence["market_volume"] = {
                "total_monthly_units": mv.get("total_monthly_units"),
                "estimated_monthly_revenue": mv.get("estimated_monthly_revenue"),
                "product_count": mv.get("product_count"),
                "avg_price": mv.get("avg_price"),
                "bsr_range": mv.get("bsr_range"),
            }

        pb = deterministic.get("price_bands", {})
        if pb:
            evidence["price_bands"] = pb

        bc = deterministic.get("brand_concentration", {})
        if bc:
            evidence["brand_concentration"] = {
                "total_brands": bc.get("total_brands"),
                "total_products": bc.get("total_products"),
                "top_3_market_share_pct": bc.get("top_3_market_share_pct"),
                "concentration": bc.get("concentration"),
                "entry_barrier": bc.get("entry_barrier"),
                "brands": bc.get("brands"),
            }

        rb = deterministic.get("review_barrier", {})
        if rb:
            evidence["review_barrier"] = {
                "review_barrier": rb.get("review_barrier"),
                "avg_review_count": rb.get("avg_review_count"),
                "median_review_count": rb.get("median_review_count"),
                "min_reviews": rb.get("min_reviews"),
                "max_reviews": rb.get("max_reviews"),
                "distribution": rb.get("distribution"),
            }

        rh = deterministic.get("rating_health", {})
        if rh:
            evidence["rating_health"] = {
                "avg_rating": rh.get("avg_rating"),
                "median_rating": rh.get("median_rating"),
                "rating_health_score": rh.get("rating_health_score"),
                "rating_health_label": rh.get("rating_health_label"),
                "distribution_detail": rh.get("distribution_detail"),
            }

        se = deterministic.get("seller_composition", {})
        if se:
            evidence["seller_composition"] = {
                "fba_pct": se.get("fba_pct"),
                "fbm_pct": se.get("fbm_pct"),
                "prime_pct": se.get("prime_pct"),
            }

        opps = deterministic.get("opportunities", [])
        if opps:
            evidence["opportunities"] = [{"opportunity": o.get("opportunity"), "evidence": o.get("evidence"), "strength": o.get("strength"), "asins": o.get("asins")} for o in opps[:5]]

        risks = deterministic.get("risks", [])
        if risks:
            evidence["risks"] = [{"risk_type": r.get("risk_type"), "detail": r.get("detail"), "severity": r.get("severity")} for r in risks[:5]]

        tr = deterministic.get("trends", {})
        if tr:
            evidence["trends"] = tr

        # ★ 数据快照：原始 ASIN 数据（冻住的真相源）
        snapshot = structured.get("data_snapshot", {})
        if snapshot and snapshot.get("products_raw"):
            evidence["data_snapshot"] = {
                "asins": snapshot.get("asins", []),
                "products_count": snapshot.get("products_count", 0),
                "products_raw": snapshot.get("products_raw", []),
            }

        evidence_json = _json.dumps(evidence, ensure_ascii=False, indent=2)
    else:
        evidence_json = "{}"

    # ── 决策结论（浓缩一行） ──
    decision_line = ""
    if decision:
        score = decision.get("market_entry_score", "?")
        label = decision.get("label", "?")
        positives = "; ".join(decision.get("positives", [])[:3])
        negatives = "; ".join(decision.get("negatives", [])[:3])
        decision_line = f"结论: {label} (评分: {score}/100)\n有利: {positives}\n风险: {negatives}"

    asin_line = f"分析 ASIN: {', '.join(asins[:8]) if asins else '无'}" if asins else ""

    return f"""## 分析概览
{asin_line}
{decision_line}

## 原始证据（JSON — 直接引用里面的具体数值回答用户）
```json
{evidence_json}
```"""


# ── 构建工具列表 ──

def get_tools(include_search_web: bool = True):
    """
    构建工具列表。

    search_web 默认可用——LLM 自己决定要不要搜。
    Phase 0 情报报告已注入 system prompt，LLM 有足够上下文判断"该用数据库还是该搜索"。

    数据工具已切换为 5 个全局抽象工具（data_tools），
    覆盖：单实体详情、多实体对比、条件搜索、趋势分析、自定义聚合。
    """
    # ★ 旧数据工具迁移：query_db → search_entities/analyze_custom
    #   get_product_data → get_entity_details/compare_entities
    #   discover_data → search_entities
    # ── data_tools 5 个全局工具 ──
    data_tools = get_data_tools()
    tools = [search_memory, call_nova_agent, query_analysis] + data_tools
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
    # ★ 排除被撤销的 invocation 产出的 keys
    retracted_keys: set = set()
    try:
        retracted_ids = analysis_tree_manager.get_retracted_invocation_ids(conv_id)
        for rid in retracted_ids:
            inv = analysis_tree_manager.get_tree(conv_id)
            if inv:
                found = inv.find_invocation(rid)
                if found:
                    retracted_keys.update(found.retracted_keys)
    except Exception:
        pass

    for key, value in state.data.items():
        if key.startswith("_"):
            continue
        if key in retracted_keys:
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

    # ── 数据就绪提示 — 提示 LLM 调工具 ──
    intel_report = state.data.get("_intel_report")
    if intel_report:
        found = intel_report.get("found_asins", [])
        if found:
            asin_str = ", ".join(found[:8])
            lines.append(f"- **可用 ASIN**: {asin_str}（调 get_entity_details / search_entities 获取数据）")

    if not lines:
        return ""

    # ── Pipeline 已完成的分析结果 ──
    last_pipeline = state.data.get("_last_pipeline")
    if last_pipeline:
        structured = last_pipeline.get("structured", {})
        decision = structured.get("decision_support", {})
        asins = structured.get("asins_analyzed", [])
        score = decision.get("market_entry_score", "?")
        label = decision.get("label", "?")
        lines.append(f"- **已完成分析**: Pipeline [{last_pipeline.get('pipeline_name', '?')}]")
        lines.append(f"- **分析 ASIN**: {', '.join(asins[:5]) if asins else '?'}")
        lines.append(f"- **市场进入评分**: {score}/100 — {label}")
        lines.append(f"- **可用工具**: 调 query_analysis() 获取完整结构化分析数据，回答用户追问")

    return "\n## 当前数据状态\n" + "\n".join(lines)


# ── 产品数据渲染（绕过 LLM 直接返回） ──

def _render_product_data(product_preview: dict) -> str:
    """将 product_preview 渲染为结构化中文文本，不走 LLM"""
    lines = []
    for asin, data in product_preview.items():
        title = (data.get("title") or "无标题")[:100]
        price = data.get("current_price", "N/A")
        rating = data.get("rating", "N/A")
        review_cnt = data.get("review_count", 0)
        bsr = data.get("current_bsr", "N/A")
        monthly = data.get("monthly_sold", "N/A")
        brand = data.get("brand", "N/A")
        seller_ct = data.get("seller_count", "N/A")
        is_fba = "✅ FBA" if data.get("is_fba") else ""
        is_prime = "✅ Prime" if data.get("is_prime") else ""
        coupon = "🎟️ 有Coupon" if data.get("has_coupon") else ""
        stock = data.get("stock_level", "")
        stock_str = f"📦 库存{stock}" if stock else ""

        lines.append(f"## {asin}")
        lines.append(f"**{title}**")
        lines.append("")
        lines.append(f"- **品牌**: {brand}")
        lines.append(f"- **价格**: ${price}" + (f" (原价 ${data.get('list_price', 'N/A')})" if data.get('list_price') else ""))
        lines.append(f"- **评分**: {rating}⭐ ({review_cnt} 条评价)")
        lines.append(f"- **BSR**: #{bsr}")
        lines.append(f"- **月销量**: {monthly}")
        badges = " | ".join(filter(None, [is_fba, is_prime, coupon, stock_str]))
        if badges:
            lines.append(f"- **标识**: {badges}")
        if data.get("seller_count") is not None:
            lines.append(f"- **卖家数**: {seller_ct}")
        if data.get("feature_bullets"):
            bullets = data["feature_bullets"]
            if isinstance(bullets, list) and bullets:
                lines.append(f"- **卖点**:")
                for b in bullets[:5]:
                    lines.append(f"  - {b[:120]}")
        lines.append("")
    return "\n".join(lines)


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

    system_prompt = pe.build_orchestrator_prompt(
        spec=intent_spec,
        agents_info=agents_info,
        memory_context=memory_context,
        state_summary=state_summary,
    )

    # ★ 注入历史纠正前缀（过滤 dead-end 后，防止历史污染）
    correction_prefix = state.get("correction_prefix", "")
    if correction_prefix:
        system_prompt += correction_prefix

    # ★★ Stage 2a: 否定检测 — 用户指出之前回答有误时注入纠正指令
    # 检测用户最后一条消息是否包含否定模式，且紧跟在 assistant 消息之后
    try:
        _NEGATION_PATTERNS = re.compile(
            r'(不对|不是|错了|之前说的不对|刚才不对|重新回答|正确的答案|'
            r'你说错了|你之前说错了|你刚才说错了|我纠正一下|修正一下|'
            r'重新说|重来|上面的不对)'
        )
        messages = state.get("messages", [])
        if len(messages) >= 2:
            last_msg = messages[-1]
            prev_msg = messages[-2]
            if (last_msg.get("role") == "user"
                    and prev_msg.get("role") == "assistant"
                    and _NEGATION_PATTERNS.search(last_msg.get("content", ""))
                    and len(last_msg.get("content", "")) < 100):
                # 获取上一个 assistant 消息内容用于引用
                prev_content = (prev_msg.get("content", "") or "")[:200]
                correction_block = (
                    f"\n\n### 纠正指令\n"
                    f"用户指出你的上一轮回答有误。\n"
                    f"上一轮你说（节选）: \"{prev_content}\"\n\n"
                    f"请按以下步骤修正：\n"
                    f"1. 回顾上方「当前数据状态」— 数据已就绪，是真实有效的\n"
                    f"2. 如果之前基于'数据未就绪'或'数据不足'做出了否定结论，请忽略该前提\n"
                    f"3. 重新分析并输出修正后的回答\n"
                    f"4. 在自检段说明：修正了哪个具体结论、修正依据是什么\n"
                    f"5. **不要延续之前的错误方向**— 基于当前看到的数据重新判断\n\n"
                    f"多轮对话中修正之前结论是完全正常的。直接给正确回答即可。"
                )
                system_prompt += correction_block
                logger = __import__("logging").getLogger(__name__)
                logger.info(f"[NegationDetect] 检测到否定，注入纠正指令")
    except Exception:
        pass

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

            # ── 旧数据工具（向后兼容，已从默认工具列表移除） ──
            elif tool_name == "query_db":
                result = await asyncio.wait_for(db_query.ainvoke(tool_args), timeout=30)
            elif tool_name == "get_product_data":
                result = await asyncio.wait_for(get_product_data.ainvoke(tool_args), timeout=30)
            elif tool_name == "discover_data":
                result = await asyncio.wait_for(discover_data.ainvoke(tool_args), timeout=30)

            # ── 新 5 个全局数据工具 ──
            elif tool_name == "get_entity_details":
                result = await asyncio.wait_for(
                    get_entity_details.ainvoke(tool_args), timeout=30)
            elif tool_name == "compare_entities":
                result = await asyncio.wait_for(
                    compare_entities.ainvoke(tool_args), timeout=30)
            elif tool_name == "search_entities":
                result = await asyncio.wait_for(
                    search_entities.ainvoke(tool_args), timeout=30)
            elif tool_name == "get_trends":
                result = await asyncio.wait_for(
                    get_trends.ainvoke(tool_args), timeout=30)
            elif tool_name == "analyze_custom":
                result = await asyncio.wait_for(
                    analyze_custom.ainvoke(tool_args), timeout=30)

            elif tool_name == "query_analysis":
                result = await _query_analysis()

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
                        # 从 result 提取 agent_load_info（_extract_agent_load_info 的输出）
                        agent_load_info = {}
                        agent_data = result.get("data", {}) if isinstance(result, dict) else {}
                        if isinstance(result, dict):
                            agent_load_info = result.get("agent_load_info", {})
                        tracer.end_agent_call(
                            agent_name=agent_name,
                            result=str(result.get("result", ""))[:500]
                                if isinstance(result, dict) else str(result)[:500],
                            params=tool_args,
                            sub_task=sub_task,
                            products_loaded=agent_load_info.get("products_loaded", 0),
                            asins_loaded=agent_load_info.get("asins_queried", []),
                            evidence_used=agent_load_info.get("evidence_fields", []),
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


def _build_reanalysis_pipeline_context(
    state, user_input: str, conv_id: str,
    decision, last_commentary: str
):
    """构建重分析的 PipelineContext（复用 _generate_llm_commentary 用）"""
    from backend.core.pipeline.base import PipelineContext

    last_ctx_data = state.data.get("_last_pipeline_context", {})
    intent_spec_data = state.data.get("_intent_spec_data", {})

    reanalysis_prompt = (
        f"【上次分析结论】\n{last_commentary[:2000]}\n\n"
        f"【用户指出问题】\n{user_input}\n"
    )

    return PipelineContext(
        intent_type=last_ctx_data.get("intent_type", intent_spec_data.get("intent_type", "")),
        entities=last_ctx_data.get("entities", intent_spec_data.get("entities", [])),
        category_hint=last_ctx_data.get("category_hint", intent_spec_data.get("category_hint", "")),
        found_asins=last_ctx_data.get("found_asins", []),
        missing_asins=last_ctx_data.get("missing_asins", []),
        raw_query=user_input,
        conversation_id=conv_id,
        reanalysis_prompt=reanalysis_prompt,
    )


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

    # ── 后续对话：Pipeline 已完成 → 判断是"继续追问"还是"重分析" ──
    if state.data.get("_pipeline_completed"):
        # ── 使用 ReanalysisClassifier 做意图分流（4 类） ──
        from backend.core.pipeline.reanalysis import classify_reanalysis, extract_filter_constraints
        from backend.core.pipeline.reanalysis import (
            REANALYSIS_FULL, REANALYSIS_PARTIAL, REANALYSIS_EXPLAIN, REANALYSIS_NEW,
        )

        last_pipeline = state.data.get("_last_pipeline", {})
        last_structured = last_pipeline.get("structured", {})
        last_commentary = last_pipeline.get("llm_commentary", "")
        last_deterministic = last_structured.get("deterministic", {})

        # 构建上次分析完成指标列表（给分类器判断局部重算用）
        last_metrics = [k for k, v in last_deterministic.items() if v] if last_deterministic else None

        decision = classify_reanalysis(user_input, last_commentary, last_metrics)
        filter_constraints = extract_filter_constraints(user_input)

        yield {"type": "status", "data": f"🔄 分析意图识别: {decision.scope}"}

        # ── 场景 C: 重新解释（数据没错，结论重新生成注释） ──
        if decision.scope == REANALYSIS_EXPLAIN:
            # 重新走 Level 3（LLM commentary）即可，不用重跑数据
            yield {"type": "status", "data": "📝 重新生成分析注释..."}

            from backend.core.pipeline.base import BasePipeline

            ctx = _build_reanalysis_pipeline_context(
                state, user_input, conv_id, decision, last_commentary
            )

            # 复用上次的结构化数据，只重新生成注释
            temp_pipeline = BasePipeline()
            new_commentary = await temp_pipeline._generate_llm_commentary(ctx, last_structured)

            # ★ 构建 DecisionCard（复用上次的 structured，只换 commentary）
            from backend.core.pipeline.guard import DecisionCard as _ReCard
            re_card = _ReCard.from_pipeline_result(last_structured, new_commentary)

            # 推送结构化数据（与上次相同）+ 新注释
            yield {
                "type": "structured_data",
                "data": {
                    "pipeline": last_pipeline.get("pipeline_name", "re_explain"),
                    "structured": last_structured,
                    "llm_commentary": new_commentary,
                    "decision_card": re_card.to_dict(),
                },
            }

            yield {"type": "start_response", "data": ""}
            if new_commentary:
                for chunk in new_commentary.split("\n"):
                    if chunk.strip():
                        yield {"type": "response_chunk", "data": chunk + "\n"}
                        await asyncio.sleep(0.01)

            yield {"type": "done", "data": ""}
            await durable.append_message(conv_id, "user", user_input)
            await durable.append_message(conv_id, "assistant", new_commentary)
            memory.save_chat(user_input, new_commentary, metadata={
                "importance": 6, "tags": "pipeline_re_explain", "conversation_id": conv_id,
            })

            state.data["_last_pipeline"] = {
                "pipeline_name": last_pipeline.get("pipeline_name", "re_explain"),
                "structured": last_structured,
                "llm_commentary": new_commentary,
            }
            asyncio.create_task(_try_summarize(conv_id))
            return

        # ── 场景 A+B: 全量重跑 / 局部重算 ──
        if decision.scope in (REANALYSIS_FULL, REANALYSIS_PARTIAL):
            yield {"type": "status", "data": "🔄 重新运行 Pipeline 分析..."}

            # 构建重分析上下文：上次的 LLM 结论 + 用户指出的问题
            reanalysis_prompt = (
                f"【上次分析结论】\n{last_commentary[:2000]}\n\n"
                f"【用户指出问题】\n{user_input}\n"
            )

            # 从上次 Pipeline 的 context 恢复参数
            last_ctx_data = state.data.get("_last_pipeline_context", {})
            found_asins = last_ctx_data.get("found_asins", [])
            missing_asins = last_ctx_data.get("missing_asins", [])
            category_hint = last_ctx_data.get("category_hint", "")
            intent_type = last_ctx_data.get("intent_type", "")
            entities = last_ctx_data.get("entities", [])

            # 如果上次没有存 context，从 state 的 _intel_report 恢复
            if not found_asins:
                intel_report = state.data.get("_intel_report", {})
                found_asins = intel_report.get("found_asins", [])
                missing_asins = intel_report.get("missing_asins", [])
                intent_spec_data = state.data.get("_intent_spec_data", {})
                intent_type = intent_spec_data.get("intent_type", "")
                entities = intent_spec_data.get("entities", [])

            from backend.core.pipeline.router import router as pipeline_router
            from backend.core.pipeline.base import PipelineContext

            await durable.append_message(conv_id, "user", user_input)

            pipeline_cls = pipeline_router.resolve(intent_type)

            if pipeline_cls and found_asins:
                yield {"type": "status", "data": f"📊 重新分析 {len(found_asins)} 个 ASIN..."}

                # ★ B 类局部重算：在 reanalysis_prompt 中注入"只关注哪些指标"
                if decision.scope == REANALYSIS_PARTIAL and decision.metrics_to_recompute:
                    reanalysis_prompt += (
                        f"\n【聚焦范围】\n"
                        f"用户只关心以下维度: {', '.join(decision.metrics_to_recompute)}\n"
                        f"其他维度保持上次分析结论即可。\n"
                    )

                # ★ 过滤约束注入（如"只看低价产品"）
                if filter_constraints:
                    reanalysis_prompt += (
                        f"\n【过滤约束】\n"
                        f"用户指定了数据过滤条件: {filter_constraints}\n"
                        f"请基于此约束条件做针对性分析。\n"
                    )

                ctx = PipelineContext(
                    intent_type=intent_type,
                    entities=entities,
                    category_hint=category_hint,
                    found_asins=found_asins,
                    missing_asins=missing_asins,
                    raw_query=user_input,
                    conversation_id=conv_id,
                    reanalysis_prompt=reanalysis_prompt,
                )

                pipeline = pipeline_cls()
                result = await pipeline.run(ctx, tracer=tracer_var.get())

                # ★ PipelineGuard: 校验重分析 Pipeline 输出
                from backend.core.pipeline.guard import PipelineGuard as _Guard, DecisionCard as _Card
                guard_check = _Guard(intent_type).check(pipeline_result=result, found_asins=found_asins)
                if not guard_check.is_valid:
                    error_msg = _Guard.format_guard_error(guard_check)
                    yield {"type": "status", "data": error_msg}
                    yield {"type": "start_response", "data": ""}
                    for chunk in error_msg.split("\n"):
                        if chunk.strip():
                            yield {"type": "response_chunk", "data": chunk + "\n"}
                            await asyncio.sleep(0.01)
                    yield {"type": "done", "data": ""}
                    await durable.append_message(conv_id, "assistant", error_msg)
                    return

                decision_card = _Card.from_pipeline_result(result.structured, result.llm_commentary)

                yield {
                    "type": "structured_data",
                    "data": {
                        "pipeline": result.pipeline_name,
                        "structured": result.structured,
                        "llm_commentary": result.llm_commentary,
                        "decision_card": decision_card.to_dict(),
                    },
                }

                yield {"type": "start_response", "data": ""}
                if result.llm_commentary:
                    for chunk in result.llm_commentary.split("\n"):
                        if chunk.strip():
                            yield {"type": "response_chunk", "data": chunk + "\n"}
                            await asyncio.sleep(0.01)

                yield {"type": "done", "data": ""}
                await durable.append_message(conv_id, "assistant", result.llm_commentary)
                memory.save_chat(user_input, result.llm_commentary, metadata={
                    "importance": 6, "tags": "pipeline_reanalysis", "conversation_id": conv_id,
                })

                state.data["_last_pipeline"] = {
                    "pipeline_name": result.pipeline_name,
                    "structured": result.structured,
                    "llm_commentary": result.llm_commentary,
                }

                asyncio.create_task(_try_summarize(conv_id))
                return
            else:
                yield {"type": "status", "data": "注意：无法重新跑 Pipeline，改为正常对话分析。"}

        # ── 场景 D 或降级: 新问题 → 走 ReAct 循环 ──
        # （REANALYSIS_NEW 或无法走 Pipeline 的降级）

        # 持久化用户消息
        await durable.append_message(conv_id, "user", user_input)

        # 加载历史 + 构建纠正前缀
        history, correction_prefix = await _build_history_messages(conv_id, user_input)

        # 构建并运行 LangGraph ReAct 循环
        graph = build_graph()
        initial_state: AgentState = {
            "messages": history + [{"role": "user", "content": user_input}],
            "user_input": user_input,
            "final_response": None,
            "tool_results": [],
            "intel_collected": True,
            "intent_spec_data": None,
            "intel_report": None,
            "correction_prefix": correction_prefix,
        }

        final_state = await graph.ainvoke(initial_state)

        # 持久化所有 tool 和 assistant 消息
        final_response = "处理完成，但未能生成回答。"
        for msg in final_state["messages"]:
            if msg["role"] == "tool":
                await durable.append_message(
                    conv_id, "tool", str(msg.get("content", ""))[:3000], tool_name=msg.get("name")
                )
            elif msg["role"] == "assistant" and msg.get("content") and not msg.get("tool_calls"):
                final_response = msg["content"]

        await durable.append_message(conv_id, "assistant", final_response)
        memory.save_chat(user_input, final_response, metadata={
            "importance": 6, "tags": "follow_up", "conversation_id": conv_id,
        })

        # 流式输出
        yield {"type": "start_response", "data": ""}
        if final_response:
            for chunk in final_response.split("\n"):
                if chunk.strip():
                    yield {"type": "response_chunk", "data": chunk + "\n"}
                    await asyncio.sleep(0.01)
        yield {"type": "done", "data": ""}
        asyncio.create_task(_try_summarize(conv_id))
        return

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

        # 将情报写入 state
        state.data["_intel_report"] = {
            "found_asins": intel.found_asins,
            "missing_asins": intel.missing_asins,
            "matched_category_names": intel.matched_category_names,
            "exploration": intel.exploration,
            "catalog": intel.catalog,
            "can_collect_asins": intel.can_collect_asins,
        }
        state.data["_intel_report_obj"] = intel  # 保留对象引用，用于 to_llm_context()

        # yield 情报摘要
        total = intel.total_products_available
        if total > 0:
            yield {"type": "status", "data": f"📊 DB 探索到 {total} 个相关商品（品类: {intel.matched_category_names[:3] or '?'}）"}
        else:
            yield {"type": "status", "data": f"ℹ️ DB 未找到匹配用户输入的商品"}
    except Exception as e:
        logger = __import__("logging").getLogger(__name__)
        logger.warning(f"[Phase 0] 情报收集失败: {e}", exc_info=True)
        pass

    # ── Level 1: Intent Router — 确定走哪条 Pipeline ──
    # 不走 LLM 决策，纯代码路由
    intent_spec_data = state.data.get("_intent_spec_data", {})
    intent_type = intent_spec_data.get("intent_type", "")
    found_asins = intel.found_asins if intel else []
    category_hint = intent_spec_data.get("category_hint", "")

    # ★ 日志：打印意图分类结果 & ASIN 命中数
    __import__("logging").getLogger(__name__).info(
        f"[Router] intent_type={intent_type}, found_asins={len(found_asins)}个, "
        f"entities={intent_spec_data.get('entities', [])[:5]}, "
        f"paraphrased={intent_spec_data.get('paraphrased_intent', '')[:60]}"
    )

    # ★ 兜底：用户提供了 ASIN 但意图被识别为 general_query → 强制走 product_research Pipeline
    # 用户给 33 个 ASIN 显然不是"通用对话"——他们需要分析
    if found_asins and intent_type == "general_query":
        __import__("logging").getLogger(__name__).info(
            f"[Router] 强制升级: general_query({len(found_asins)}个ASIN) → product_research"
        )
        intent_type = "product_research"
        intent_spec_data["intent_type"] = intent_type

    # ════════════════════════════════════════════════════════
    # PipelineGuard — 强制执行路径校验
    # ════════════════════════════════════════════════════════
    # 铁律：对于 analysis 类 intent，Pipeline 是唯一执行路径。
    #   不允许 Pipeline 被绕过 → 裸数据输出
    #   不允许 Pipeline 失败 → 优雅降级到 ReAct
    #   Router 未匹配 → 硬错误，不 fallback
    from backend.core.pipeline.guard import PipelineGuard, DecisionCard
    guard = PipelineGuard(intent_type)

    if guard.must_run_pipeline and not found_asins:
        # analysis intent 但无数据 → 硬错误，不降级
        error_msg = (
            f"🚨 系统无法执行分析：意图识别为「{intent_type}」需要走分析管线，"
            f"但本地数据库未找到相关 ASIN 数据。"
        )
        yield {"type": "status", "data": error_msg}
        yield {"type": "start_response", "data": ""}
        for chunk in error_msg.split("\n"):
            if chunk.strip():
                yield {"type": "response_chunk", "data": chunk + "\n"}
                await asyncio.sleep(0.01)
        yield {"type": "done", "data": ""}
        await durable.append_message(conv_id, "assistant", error_msg)
        return

    # ── DecisionTrace：初始化追踪器 ──
    from backend.core.decision_trace import DecisionTracer
    tracer = DecisionTracer(conv_id, user_input)
    tracer_var.set(tracer)
    tracer.capture_intent(intent_spec_data)
    if intel:
        tracer.capture_data_liaison({
            "found_asins": intel.found_asins,
            "missing_asins": intel.missing_asins,
            "matched_category_names": intel.matched_category_names,
            "exploration": intel.exploration,
            "catalog": intel.catalog,
            "can_collect_asins": intel.can_collect_asins,
            "category_hint": intel.category_hint,
        }, to_llm_context_text=intel.to_llm_context())

    from backend.core.pipeline.router import router as pipeline_router
    from backend.core.pipeline.base import PipelineContext

    pipeline_cls = pipeline_router.resolve(intent_type)

    if pipeline_cls and found_asins:
        # ── Level 2: 确定性 Pipeline 执行 ──
        yield {"type": "status", "data": f"📊 开始分析 {len(found_asins)} 个 ASIN..."}
        __import__("logging").getLogger(__name__).info(
            f"[Orchestrator] Pipeline 入口: intent_type={intent_type}, "
            f"found_asins={len(found_asins)}个, "
            f"missing_asins={len(intel.missing_asins if intel else [])}个"
        )

        ctx = PipelineContext(
            intent_type=intent_type,
            entities=intent_spec_data.get("entities", []),
            category_hint=category_hint,
            found_asins=found_asins,
            missing_asins=intel.missing_asins if intel else [],
            raw_query=intent_spec_data.get("raw_query", ""),
            conversation_id=conv_id,
        )

        pipeline = pipeline_cls()
        result = await pipeline.run(ctx, tracer=tracer)

        # ════════════════════════════════════════════════════════
        # PipelineGuard — 校验 Pipeline 输出是否有效
        # ════════════════════════════════════════════════════════
        # 如果 Pipeline 执行后输出无效（缺少 decision_support、deterministic 等关键字段），
        # 直接返回错误，不允许降级到裸数据输出。
        guard_check = guard.check(pipeline_result=result, found_asins=found_asins)
        if not guard_check.is_valid:
            error_msg = PipelineGuard.format_guard_error(guard_check)
            yield {"type": "status", "data": error_msg}
            yield {"type": "start_response", "data": ""}
            for chunk in error_msg.split("\n"):
                if chunk.strip():
                    yield {"type": "response_chunk", "data": chunk + "\n"}
                    await asyncio.sleep(0.01)
            yield {"type": "done", "data": ""}
            await durable.append_message(conv_id, "assistant", error_msg)
            logger.error(f"[PipelineGuard] {guard_check.validation_errors}")
            return

        # ── 构建 DecisionCard（统一输出格式） ──
        decision_card = DecisionCard.from_pipeline_result(result.structured, result.llm_commentary)

        # ── 持久化用户消息 ──
        await durable.append_message(conv_id, "user", user_input)

        # ── DecisionTrace：最终汇总 + 写文件 ──
        try:
            tracer.finalize(final_answer=result.llm_commentary)
        except Exception:
            pass

        # ── 推送 DecisionCard 到前端（SSE）—— 只推前端需要的数据，不推 raw data ──
        # ★ 去除 data_snapshot.products_raw（全量原始 ASIN 数据），保留 deterministic + decision_support
        lean_structured = dict(result.structured)
        if "data_snapshot" in lean_structured:
            lean_structured["data_snapshot"] = {
                "asins": result.structured["data_snapshot"].get("asins", []),
                "products_count": result.structured["data_snapshot"].get("products_count", 0),
                # ★ products_raw 不推给前端，避免几十个 ASIN 的完整数据通过 SSE 传输
            }

        yield {
            "type": "structured_data",
            "data": {
                "pipeline": result.pipeline_name,
                "structured": lean_structured,
                "llm_commentary": result.llm_commentary,
                "decision_card": decision_card.to_dict(),
            },
        }

        # ── 流式输出 LLM 注释 ──
        yield {"type": "start_response", "data": ""}
        if result.llm_commentary:
            for chunk in result.llm_commentary.split("\n"):
                if chunk.strip():
                    yield {"type": "response_chunk", "data": chunk + "\n"}
                    await asyncio.sleep(0.01)

        yield {"type": "done", "data": ""}
        await durable.append_message(conv_id, "assistant", result.llm_commentary)
        memory.save_chat(user_input, result.llm_commentary, metadata={"importance": 6, "tags": "pipeline_analysis", "conversation_id": conv_id})
        asyncio.create_task(_try_summarize(conv_id))

        # ── Pipeline 完成，标记 state，供后续对话使用 ──
        state.data["_pipeline_completed"] = True
        state.data["_last_pipeline"] = {
            "pipeline_name": result.pipeline_name,
            "structured": result.structured,
            "llm_commentary": result.llm_commentary,
        }
        state.data["_last_pipeline_context"] = {
            "intent_type": intent_type,
            "entities": intent_spec_data.get("entities", []),
            "found_asins": found_asins,
            "missing_asins": intel.missing_asins if intel else [],
            "category_hint": category_hint,
        }

        # ★ 结束本轮流式输出，不继续到后面的 fallback 块
        return

    # ── 没有匹配的 Pipeline ──
    # ★ PipelineGuard: analysis 类 intent 不允许 fallback 到裸数据输出
    if guard.must_run_pipeline:
        error_msg = (
            f"🚨 系统执行路径异常：意图识别为「{intent_type}」需要走分析管线，"
            f"但 Pipeline Router 未匹配到具体管线。\n"
            f"这通常是因为 intent_type 不在 router 注册表中。\n"
            f"当前 intent_type: {intent_type}\n"
            f"已注册: {sorted(PipelineGuard.ANALYSIS_INTENTS)}"
        )
        yield {"type": "status", "data": error_msg}
        yield {"type": "start_response", "data": ""}
        for chunk in error_msg.split("\n"):
            if chunk.strip():
                yield {"type": "response_chunk", "data": chunk + "\n"}
                await asyncio.sleep(0.01)
        yield {"type": "done", "data": ""}
        await durable.append_message(conv_id, "assistant", error_msg)
        logger.error(f"[PipelineGuard] Router miss for analysis intent: {intent_type}")
        return

    # ── 非 analysis 类 → 退化到简单数据查询（直接显示数据，不走 LLM） ──
    if found_asins:
        yield {"type": "status", "data": f"🔍 显示 {len(found_asins)} 个 ASIN 的数据..."}
        engine = get_query_engine()
        lines = []
        for asin in found_asins[:5]:
            data = await engine.fetch_details("product", asin, domain="US")
            if data:
                lines.append(f"## {asin}")
                for key, value in data.items():
                    if key in ("id",) or value is None or isinstance(value, (dict, list)):
                        continue
                    lines.append(f"- **{key}**: {value}")
                lines.append("")

        text = "\n".join(lines) if lines else "未找到数据"
        yield {"type": "start_response", "data": ""}
        for chunk in text.split("\n"):
            if chunk.strip():
                yield {"type": "response_chunk", "data": chunk + "\n"}
                await asyncio.sleep(0.01)
        yield {"type": "done", "data": ""}
        await durable.append_message(conv_id, "assistant", text)
        memory.save_chat(user_input, text, metadata={"importance": 4, "tags": "direct_query", "conversation_id": conv_id})
        asyncio.create_task(_try_summarize(conv_id))
        return

    # ── 没有任何数据 → 最后的兜底 ──
    text = "未找到相关 ASIN 数据，请提供具体的 ASIN 或品类名。"
    yield {"type": "start_response", "data": ""}
    yield {"type": "response_chunk", "data": text}
    yield {"type": "done", "data": ""}
    await durable.append_message(conv_id, "assistant", text)
    return
