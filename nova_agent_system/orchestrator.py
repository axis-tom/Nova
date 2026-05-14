"""
Orchestrator — 核心调度引擎
基于 LangGraph 的 ReAct 循环：
1. LLM 理解用户意图
2. LLM 决定调哪些工具（搜索 / Agent / 查记忆）
3. 循环：调工具 → 看结果 → 再调工具 → 直到完成
4. LLM 汇总结果 → 返回
"""

from typing import Dict, Any, List, Optional, TypedDict, Annotated, Sequence
import json
import os

from langgraph.graph import StateGraph, END
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage, ToolMessage
from langchain_core.tools import tool

from nova_agent_system.web_tools import web_search, scrape_url
from nova_agent_system.memory_store import MemoryStore
from nova_agent_system.agent_wrapper import call_agent, list_agents

# ── 全局记忆实例 ──
memory = MemoryStore()

# ── 状态定义 ──


class AgentState(TypedDict):
    messages: Annotated[Sequence[Dict[str, Any]], "对话消息列表"]
    user_input: str
    final_response: Optional[str]
    tool_results: List[Dict[str, Any]]


# ── LLM 初始化 ──

def _get_llm():
    """获取 LLM 实例，优先用环境变量配置"""
    api_key = os.getenv("OPENAI_API_KEY") or os.getenv("ZHIPU_API_KEY")
    base_url = os.getenv("OPENAI_BASE_URL", "")
    model = os.getenv("LLM_MODEL", "gpt-4o-mini")

    if os.getenv("ZHIPU_API_KEY"):
        # 智谱
        return ChatOpenAI(
            model=model or "glm-4-flash",
            api_key=api_key,
            base_url=base_url or "https://open.bigmodel.cn/api/paas/v4/",
            temperature=0.3,
        )
    else:
        return ChatOpenAI(
            model=model,
            api_key=api_key,
            base_url=base_url or "",
            temperature=0.3,
        )


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
    """搜索历史记忆。当你需要回忆之前的对话内容或之前搜索过的知识时使用。"""
    results = memory.search_knowledge(query, k=3)
    if not results:
        return "未找到相关历史记录"
    lines = []
    for r in results:
        lines.append(f"[{r['metadata'].get('timestamp', '')}] {r['content'][:500]}")
    return "\n\n".join(lines)


@tool
async def call_nova_agent(agent_name: str, params_json: str) -> str:
    """
    调用 Nova 的 Amazon 业务 Agent 执行特定分析任务。
    
    Args:
        agent_name: Agent 名称，可选值: product_collector, opportunity_judge, review_analyzer, 
                   traffic_analyzer, keyword_expander, market_analyst, competitor_analyst, briefing_generator
        params_json: JSON 格式的参数，例如 {"keywords": ["bluetooth earbuds"], "max_results": 10}
    """
    try:
        params = json.loads(params_json)
    except json.JSONDecodeError:
        return f"参数格式错误，需要 JSON 格式: {params_json}"
    
    result = await call_agent(agent_name, params)
    output = result.get("result", "")
    if isinstance(output, list):
        # 结构化数据转文本
        if len(output) > 5:
            output = output[:5]
        output = json.dumps(output, ensure_ascii=False, indent=2)
    elif isinstance(output, dict):
        output = json.dumps(output, ensure_ascii=False, indent=2)
    
    return f"Agent [{agent_name}] 执行结果:\n{output}"


# ── 构建工具列表 ──

def get_tools():
    return [search_web, search_memory, call_nova_agent]


# ── 图节点 ──

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
    agents_desc = "\n".join(
        f"  - {a['name']}: {a['description']}" for a in agents_info
    )

    system_prompt = f"""你是一个 Amazon 电商智能助手，负责帮助用户分析市场、选品、监控竞品。

你可以使用以下工具：

1. search_web(query) — 搜索互联网获取最新行业信息、新闻、趋势
2. search_memory(query) — 搜索历史记忆，回顾之前的分析结果
3. call_nova_agent(agent_name, params_json) — 调用 Nova 的 Amazon 业务 Agent

可调用的 Agent：
{agents_desc}

工作流程：
1. 先理解用户意图
2. 如果需要最新信息，先 search_web
3. 如果需要分析 Amazon 商品数据，调 call_nova_agent
4. 如果需要回顾历史，调 search_memory
5. 汇总所有结果，给用户完整的回答

注意：
- 搜索时用英文关键词效果更好
- 调 Agent 时 params_json 必须是合法 JSON
- 最终回答要结构化、清晰，用中文"""

    # 转换消息格式
    langchain_messages = [SystemMessage(content=system_prompt)]
    for msg in state["messages"]:
        if msg["role"] == "user":
            langchain_messages.append(HumanMessage(content=msg["content"]))
        elif msg["role"] == "assistant":
            langchain_messages.append(AIMessage(content=msg.get("content", "")))
        elif msg["role"] == "tool":
            langchain_messages.append(ToolMessage(content=msg["content"], tool_call_id=msg.get("tool_call_id", "")))

    response = await llm_with_tools.ainvoke(langchain_messages)

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
            elif tool_name == "call_nova_agent":
                result = await call_nova_agent.ainvoke(tool_args)
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


# ── 主入口 ──

async def run_orchestrator(user_input: str) -> str:
    """
    运行 orchestrator，处理用户输入

    Args:
        user_input: 用户输入文本

    Returns:
        最终回答
    """
    graph = build_graph()

    initial_state: AgentState = {
        "messages": [{"role": "user", "content": user_input}],
        "user_input": user_input,
        "final_response": None,
        "tool_results": [],
    }

    # 执行图
    final_state = await graph.ainvoke(initial_state)

    # 提取最终回答
    for msg in reversed(final_state["messages"]):
        if msg["role"] == "assistant" and msg.get("content"):
            final_response = msg["content"]
            break
    else:
        final_response = "处理完成，但未能生成回答。"

    # 保存到记忆
    memory.save_chat(user_input, final_response)

    return final_response