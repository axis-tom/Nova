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
import json
import os
import uuid
import asyncio
import time
from pathlib import Path

from dotenv import load_dotenv
from langgraph.graph import StateGraph, END
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage, ToolMessage
from langchain_core.tools import tool

# 加载 .env 文件
env_path = Path(__file__).resolve().parent.parent / "backend" / "config" / ".env"
if env_path.exists():
    load_dotenv(dotenv_path=env_path)

from nova_agent_system.web_tools import web_search, scrape_url
from nova_agent_system.memory_store import MemoryStore
from nova_agent_system.agent_wrapper import call_agent, list_agents
from nova_agent_system.db_retriever import query_database as db_query
from nova_agent_system.session_store import session_store
from nova_agent_system.durable_session import get_durable_session
from nova_agent_system.summarizer import summarize_conversation
from nova_agent_system.llm_config import get_llm_for_agent
from nova_agent_system.analysis_tree import analysis_tree_manager

# ── 全局记忆实例 ──
memory = MemoryStore()

# Step 5: 启动时执行一次全量清理（TTL + 整合 + SQLite 过期）
try:
    _cleanup_stats = memory.cleanup_all()
except Exception:
    pass

# ── 会话上下文（同一 ReAct 循环内的 tool 通过此读取当前 conversation_id） ──
conv_id_var: ContextVar[Optional[str]] = ContextVar("conv_id_var", default=None)

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


# ── LLM 初始化 ──

def _get_llm():
    """获取 orchestrator 的 LLM 实例（通过模型路由配置）"""
    return get_llm_for_agent("orchestrator")


# ── 工具定义 ──

@tool
async def search_web(query: str) -> str:
    """搜索互联网获取最新信息。当你需要了解行业新闻、市场趋势、竞品动态等外部信息时使用。"""
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
async def call_nova_agent(agent_name: str, params_json: str) -> str:
    """
    调用 Nova 的 Amazon 业务 Agent 执行特定分析任务。

    Args:
        agent_name: Agent 名称，可选值: keyword_expander, product_collector, review_analyzer,
                   traffic_analyzer, opportunity_judge, market_analyst, competitor_analyst, briefing_generator
        params_json: JSON 格式的参数，例如 {"expanded_keywords": ["bluetooth earbuds"], "max_results_per_keyword": 10}
                    下游 Agent（review_analyzer/traffic_analyzer/opportunity_judge）可传 {}，
                    它们会从同一会话的 session state 中读取上游 Agent 产出的字段
    """
    try:
        params = json.loads(params_json) if params_json.strip() else {}
    except json.JSONDecodeError:
        return f"参数格式错误，需要 JSON 格式: {params_json}"

    # 从 ContextVar 获取会话 id；没有就开一个 ephemeral session
    conv_id = conv_id_var.get() or f"ephemeral-{uuid.uuid4()}"
    state = session_store.get_or_create(conv_id)

    result = await call_agent(agent_name, params, state=state, conv_id=conv_id)

    # 持久化 State 到 SQLite（Phase 3）
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

    # 如果有 pending_data_requests，额外提示 LLM 需要再次调 product_collector
    deferred_count = len(state.get("pending_data_requests") or [])
    if deferred_count > 0:
        state_hint += (
            f"\n⚠️ 有 {deferred_count} 个 ASIN 因 Keepa token 不足被推迟采集 "
            f"(pending_data_requests)。请再次调用 product_collector 完成补采。"
        )

    return f"Agent [{agent_name}] 执行结果:\n{output}{state_hint}"


# ── 构建工具列表 ──

def get_tools():
    return [search_web, search_memory, query_db, call_nova_agent]


# ── 图节点 ──

async def _build_history_messages(conv_id: str, current_input: str) -> List[Dict[str, Any]]:
    """从 SQLite 加载历史消息，构建多轮上下文（不含当前 user_input）

    策略：
    - 最近 HISTORY_FULL_ROUNDS 轮：完整保留 user + assistant + tool
    - 更早的轮次：只保留 user + assistant（省 token）
    - 当前 user_input 已在历史最末（刚 append 的），需排除
    """
    durable = get_durable_session()
    messages = await durable.get_messages(conv_id, limit=HISTORY_MAX_MESSAGES)

    if not messages:
        return []

    # 排除最后一条（就是刚 append 的当前 user_input）
    if messages and messages[-1]["role"] == "user" and messages[-1]["content"] == current_input:
        messages = messages[:-1]

    if not messages:
        return []

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

    # 分层：最近 N 轮完整，更早的只保留 user + assistant
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
                if not is_recent and len(content) > 500:
                    content = content[:500] + "..."
                history.append({"role": "assistant", "content": content})
            elif msg["role"] == "user":
                content = msg["content"]
                if not is_recent and len(content) > 500:
                    content = content[:500] + "..."
                history.append({"role": "user", "content": content})

    return history


def _build_state_summary(conv_id: str) -> str:
    """生成当前会话 State 的摘要，注入 system_prompt 帮助 LLM 感知已有数据"""
    state = session_store.get_or_create(conv_id)
    if not state.data:
        return ""

    lines = []
    for key, value in state.data.items():
        if key.startswith("_"):
            continue
        if isinstance(value, list):
            lines.append(f"- {key}: {len(value)} 条记录")
        elif isinstance(value, dict):
            summary_keys = list(value.keys())[:5]
            lines.append(f"- {key}: dict({', '.join(summary_keys)})")
        elif isinstance(value, str) and len(value) > 100:
            lines.append(f"- {key}: {value[:100]}...")
        else:
            lines.append(f"- {key}: {value}")

    # ── pending_data_requests 高亮提示 ──
    pending = state.data.get("pending_data_requests") or []
    if pending:
        pending_asins = {r.get("asin", "?") for r in pending if isinstance(r, dict)}
        lines.insert(
            0,
            f"⚠️ **pending_data_requests**: {len(pending)} 项待补单 "
            f"(ASINs: {', '.join(sorted(pending_asins)[:5])}) —— "
            f"请调用 product_collector 补充数据",
        )

    if not lines:
        return ""

    return "\n\n当前会话已有数据（来自之前的 Agent 调用，可直接引用）:\n" + "\n".join(lines)


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
    llm_with_tools = llm.bind_tools(get_tools())

    # 构建系统提示
    agents_info = list_agents()
    agents_desc_lines = []
    pipeline_lines = []
    for a in agents_info:
        ups = a.get("requires_upstream", [])
        ups_str = f"  ← 依赖: {', '.join(ups)}" if ups else ""
        agents_desc_lines.append(
            f"  - {a['name']}: {a['description']}\n      input_example: {a['input_example']}{ups_str}"
        )
        if ups:
            pipeline_lines.append(f"  - {a['name']} 之前必须先调: {' → '.join(ups)}")
    agents_desc = "\n".join(agents_desc_lines)
    pipeline_desc = "\n".join(pipeline_lines) if pipeline_lines else "  (无)"

    # 注入相关历史记忆
    memory_context = ""
    try:
        # 取最后一条 user 消息作为检索 query
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

    # Step 3: 注入 State 摘要
    conv_id = conv_id_var.get()
    state_summary = _build_state_summary(conv_id) if conv_id else ""

    system_prompt = f"""你是一个 Amazon 电商智能助手，负责帮助用户分析市场、选品、监控竞品。

你可以使用以下工具：

1. search_web(query) — 搜索互联网获取最新行业信息、新闻、趋势
2. search_memory(query) — 搜索历史记忆，回顾之前的分析结果
3. query_db(natural_query) — 查询 Nova 数据库中的结构化数据（表结构、用户数据等）
4. call_nova_agent(agent_name, params_json) — 调用 Nova 的 Amazon 业务 Agent

可调用的 Agent（input_example 字段是真实需要传的 JSON 字段名，必须严格遵守）：
{agents_desc}

**关键：Agent 流水线依赖**（必须按顺序调用，下游 Agent 会从同一会话 state 自动读取上游产出）：
{pipeline_desc}

例：用户问"分析蓝牙耳机市场机会"，正确的调用顺序：
  1. call_nova_agent("product_collector", '{{"expanded_keywords":["bluetooth earbuds"], "max_results_per_keyword":10}}')
  2. call_nova_agent("review_analyzer", '{{}}')       # 从 state 自动拿 collected_products
  3. call_nova_agent("traffic_analyzer", '{{}}')      # 同上
  4. call_nova_agent("opportunity_judge", '{{}}')     # 从 state 自动拿全部上游产出
错误示例：直接调 opportunity_judge 会拿不到数据。

工作流程：
1. 先理解用户意图
2. 如果需要最新行业信息，先 search_web
3. 如果需要查看数据库已有数据，调 query_db
4. 如果需要分析 Amazon 商品数据，按上面的流水线依赖**依次**调 call_nova_agent
5. 如果需要回顾历史，调 search_memory
6. 汇总所有结果，给用户结构化的中文回答

注意：
- 搜索时用英文关键词效果更好
- 调 Agent 时 params_json 必须是合法 JSON，字段名严格按 input_example
- 调用 Agent 返回结果末尾的 `[会话 state 已有字段: ...]` 提示了当前会话累积了哪些上游产出，据此判断下一步
- 如果当前会话已有数据（下方列出），说明用户之前已执行过 Agent，优先利用现有数据，不要重复调用
- 最终回答要结构化、清晰，用中文，列出关键数据和建议
	- 如果会话 state 中有 pending_data_requests，表示有 ASIN 因 API token 不足被推迟采集，需要再次调用 product_collector 来补采
{memory_context}{state_summary}"""

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
        response = await llm_with_tools.ainvoke(langchain_messages)
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
            "content": f"⚠️ LLM 调用失败: {e}",
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
        
        try:
            if tool_name == "search_web":
                result = await search_web.ainvoke(tool_args)
            elif tool_name == "search_memory":
                result = await search_memory.ainvoke(tool_args)
            elif tool_name == "query_db":
                result = await query_db.ainvoke(tool_args)
            elif tool_name == "call_nova_agent":
                result = await call_nova_agent.ainvoke(tool_args)
                # Agent 输出自动保存到记忆
                try:
                    agent_name = tool_args.get("agent_name", "unknown")
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
        except Exception as e:
            result = f"工具 [{tool_name}] 执行失败: {e}"
        
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
        history = await _build_history_messages(conv_id, user_input)

        graph = build_graph()

        initial_state: AgentState = {
            "messages": history + [{"role": "user", "content": user_input}],
            "user_input": user_input,
            "final_response": None,
            "tool_results": [],
        }

        final_state = await graph.ainvoke(initial_state)

        # 持久化最终 State 到 SQLite
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

    # 注册分析树 SSE 事件队列
    tree_queue: asyncio.Queue = asyncio.Queue(maxsize=200)
    analysis_tree_manager.register_queue(conv_id, tree_queue)

    try:
        # Step 2: 持久化用户消息
        await durable.append_message(conv_id, "user", user_input)

        # Step 3: 加载历史消息构建多轮上下文
        history = await _build_history_messages(conv_id, user_input)

        graph = build_graph()

        initial_state: AgentState = {
            "messages": history + [{"role": "user", "content": user_input}],
            "user_input": user_input,
            "final_response": None,
            "tool_results": [],
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
                        # 如果是 briefing_generator，额外发送结构化数据供前端图表渲染
                        if tool_name == "briefing_generator":
                            try:
                                tool_content = json.loads(msg.get("content", "{}"))
                                briefing_data = tool_content.get("data", {})
                                if briefing_data:
                                    yield {"type": "briefing_data", "data": briefing_data}
                            except (json.JSONDecodeError, TypeError):
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

        yield {"type": "done", "data": ""}

        # Step 2: 持久化 assistant 回答
        await durable.append_message(conv_id, "assistant", final_response)

        # 持久化最终 State 到 SQLite
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
