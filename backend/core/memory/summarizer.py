"""Summarizer — LLM 对话摘要生成（Phase 3 · Step 4）

职责：
- 将多轮对话历史压缩为结构化摘要
- 摘要存入 ChromaDB knowledge_cache，供跨会话检索
- 同时更新 conversations.title
"""

import logging
from typing import Optional

from backend.core.memory.durable import get_durable_session
from backend.core.memory.vector_store import MemoryStore

logger = logging.getLogger(__name__)

SUMMARIZE_PROMPT = """请将以下对话历史压缩为一段结构化摘要（200字以内），包含：
1. 用户目标（在研究什么）
2. 分析的商品/品类/关键词
3. 关键发现（数据、趋势、洞察）
4. 结论和建议

只输出摘要内容，不要前缀或解释。

对话历史：
{conversation}"""

MIN_MESSAGES_FOR_SUMMARY = 6


async def summarize_conversation(
    conv_id: str,
    memory: Optional[MemoryStore] = None,
    force: bool = False,
) -> Optional[str]:
    """对指定会话生成 LLM 摘要并存入 knowledge_cache

    Args:
        conv_id: 会话 ID
        memory: MemoryStore 实例（为 None 则新建）
        force: 强制生成（忽略消息数阈值）

    Returns:
        摘要文本，未触发则返回 None
    """
    durable = get_durable_session()
    messages = await durable.get_messages(conv_id, limit=50)

    if not messages:
        return None

    if not force and len(messages) < MIN_MESSAGES_FOR_SUMMARY:
        return None

    # 构建对话文本
    conversation_text = _format_messages_for_summary(messages)

    # 调用 LLM 生成摘要
    try:
        summary = await _call_llm_for_summary(conversation_text)
    except Exception as e:
        logger.error(f"[Summarizer] LLM call failed for {conv_id}: {e}")
        return None

    if not summary or len(summary.strip()) < 10:
        logger.warning(f"[Summarizer] Empty summary for {conv_id}")
        return None

    summary = summary.strip()

    # 存入 knowledge_cache
    if memory is None:
        memory = MemoryStore()

    memory.save_knowledge(
        key=f"conversation_summary_{conv_id}",
        content=summary,
        source="summarizer",
        importance=7,
        tags="conversation_summary,auto_generated",
        metadata={"conversation_id": conv_id},
    )

    # 更新 conversations 的 title（取摘要前 50 字）
    title = summary[:50].replace("\n", " ")
    _update_conversation_title(conv_id, title)

    logger.info(f"[Summarizer] Generated summary for {conv_id}: {title}")
    return summary


def _format_messages_for_summary(messages: list) -> str:
    """将消息列表格式化为对话文本"""
    lines = []
    for msg in messages:
        role = msg["role"]
        content = msg["content"]
        if role == "user":
            lines.append(f"用户: {content}")
        elif role == "assistant":
            lines.append(f"助手: {content[:500]}")
        elif role == "tool":
            tool_name = msg.get("tool_name") or "tool"
            lines.append(f"[{tool_name}]: {content[:200]}")
    return "\n".join(lines)


def _update_conversation_title(conv_id: str, title: str) -> None:
    """更新 SQLite 中 conversations 的 title 字段"""
    import sqlite3
    import time

    durable = get_durable_session()
    try:
        conn = sqlite3.connect(durable.db_path)
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE conversations SET title = ?, updated_at = ? WHERE conv_id = ?",
            (title, time.time(), conv_id)
        )
        conn.commit()
        conn.close()
    except Exception as e:
        logger.warning(f"[Summarizer] Failed to update title for {conv_id}: {e}")


async def _call_llm_for_summary(conversation_text: str) -> str:
    """调用 LLM 生成摘要（复用 orchestrator 的 LLM 配置）"""
    from backend.core.llm.config import get_llm_for_agent

    llm = get_llm_for_agent("orchestrator")
    if llm is None:
        logger.error("[Summarizer] Failed to get orchestrator LLM, cannot generate summary")
        return ""

    prompt = SUMMARIZE_PROMPT.format(conversation=conversation_text[:3000])
    response = await llm.ainvoke(prompt)
    return response.content
