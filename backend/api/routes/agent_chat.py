"""
Agent Chat API — SSE 流式对话接口 + 会话管理
将 orchestrator 以 SSE 流式方式暴露给前端，
同时持久化对话历史到 agent_conversations / agent_messages 表。
"""

import json
import uuid
import logging
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete, func

from backend.core.orchestrator import run_orchestrator_stream, run_orchestrator
from backend.data.database import get_db
from backend.data.models.db import AgentConversation, AgentMessage
from backend.api.routes.auth import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/agent", tags=["Agent 对话"])


# ── 请求/响应模型 ──

class ChatRequest(BaseModel):
    content: str
    conversation_id: str | None = None


class ChatResponse(BaseModel):
    reply: str
    conversation_id: str


class ConversationItem(BaseModel):
    id: str
    title: str
    message_count: int
    created_at: str
    updated_at: str

    class Config:
        from_attributes = True


class ConversationDetail(BaseModel):
    id: str
    title: str
    messages: List[dict]


class RenameRequest(BaseModel):
    title: str


# ── 会话管理 ──

@router.get("/conversations", response_model=List[ConversationItem])
async def list_conversations(
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取当前用户的 Agent 对话列表"""
    result = await db.execute(
        select(AgentConversation)
        .where(AgentConversation.user_id == current_user.id)
        .order_by(AgentConversation.updated_at.desc())
        .limit(50)
    )
    convs = result.scalars().all()
    return [
        ConversationItem(
            id=c.id,
            title=c.title,
            message_count=c.message_count,
            created_at=c.created_at.isoformat() if c.created_at else "",
            updated_at=(c.updated_at or c.created_at).isoformat() if c.created_at else "",
        )
        for c in convs
    ]


@router.get("/conversations/{conv_id}/messages")
async def get_conversation_messages(
    conv_id: str,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取某个对话的消息历史"""
    conv = await db.get(AgentConversation, conv_id)
    if not conv or conv.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="对话不存在")

    result = await db.execute(
        select(AgentMessage)
        .where(AgentMessage.conversation_id == conv_id)
        .order_by(AgentMessage.created_at.asc())
    )
    msgs = result.scalars().all()
    return {
        "conversation_id": conv_id,
        "title": conv.title,
        "messages": [
            {
                "id": m.id,
                "role": m.role,
                "content": m.content,
                "metadata": m.metadata_,
                "created_at": m.created_at.isoformat() if m.created_at else "",
            }
            for m in msgs
        ],
    }


@router.put("/conversations/{conv_id}")
async def rename_conversation(
    conv_id: str,
    req: RenameRequest,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """重命名对话"""
    conv = await db.get(AgentConversation, conv_id)
    if not conv or conv.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="对话不存在")
    conv.title = req.title
    await db.commit()
    return {"ok": True}


@router.delete("/conversations/{conv_id}", status_code=204)
async def delete_conversation(
    conv_id: str,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """删除对话及其所有消息"""
    conv = await db.get(AgentConversation, conv_id)
    if not conv or conv.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="对话不存在")
    await db.execute(delete(AgentMessage).where(AgentMessage.conversation_id == conv_id))
    await db.execute(delete(AgentConversation).where(AgentConversation.id == conv_id))
    await db.commit()


# ── 成本监控 ──

@router.get("/cost-report")
async def get_cost_report_endpoint(
    current_user=Depends(get_current_user),
):
    """获取 Agent LLM 调用成本报告"""
    from backend.core.llm.config import get_cost_report, get_usage_stats
    return {
        "cost_report": get_cost_report(),
        "instance_stats": get_usage_stats(),
    }


@router.post("/cost-report/reset")
async def reset_cost_report_endpoint(
    current_user=Depends(get_current_user),
):
    """重置成本计数器"""
    from backend.core.llm.config import reset_usage
    reset_usage()
    return {"ok": True}


# ── 内部辅助 ──

async def _ensure_conversation(db: AsyncSession, conv_id: str, user_id: int, first_message: str) -> str:
    """确保对话存在，不存在则创建"""
    conv = await db.get(AgentConversation, conv_id)
    if not conv:
        title = first_message[:30].strip() or "新对话"
        conv = AgentConversation(id=conv_id, user_id=user_id, title=title, message_count=0)
        db.add(conv)
        await db.commit()
    return conv_id


async def _save_message(db: AsyncSession, conv_id: str, role: str, content: str, metadata: dict = None):
    """保存消息并更新对话计数"""
    msg = AgentMessage(conversation_id=conv_id, role=role, content=content, metadata_=metadata)
    db.add(msg)
    await db.execute(
        update(AgentConversation)
        .where(AgentConversation.id == conv_id)
        .values(message_count=AgentConversation.message_count + 1)
    )
    await db.commit()


# ── SSE 流式对话 ──

@router.post("/chat/stream")
async def agent_chat_stream(
    req: ChatRequest,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    SSE 流式对话接口

    事件类型:
    - status: 状态消息
    - tool_call: LLM 决定调用的工具
    - tool_result: 工具执行结果
    - start_response: 开始输出最终回答
    - response_chunk: 回答文本片段
    - done: 完成
    - error: 错误
    """
    conv_id = req.conversation_id or str(uuid.uuid4())

    await _ensure_conversation(db, conv_id, current_user.id, req.content)
    await _save_message(db, conv_id, "user", req.content)

    async def event_generator():
        full_response = []
        try:
            async for event in run_orchestrator_stream(req.content, conversation_id=conv_id):
                event_type = event["type"]
                event_data = event["data"]

                if event_type == "response_chunk":
                    full_response.append(event_data)

                sse_data = json.dumps({
                    "type": event_type,
                    "data": event_data,
                    "conversation_id": conv_id,
                }, ensure_ascii=False)
                yield f"data: {sse_data}\n\n"

            # 保存 assistant 回复
            assistant_content = "".join(full_response)
            if assistant_content:
                async with db.begin():
                    msg = AgentMessage(conversation_id=conv_id, role="assistant", content=assistant_content)
                    db.add(msg)
                    await db.execute(
                        update(AgentConversation)
                        .where(AgentConversation.id == conv_id)
                        .values(message_count=AgentConversation.message_count + 1)
                    )

            yield f"data: {json.dumps({'type': 'done', 'data': '', 'conversation_id': conv_id})}\n\n"

        except Exception as e:
            logger.exception(f"Agent chat stream error: {e}")
            error_data = json.dumps({
                "type": "error",
                "data": f"处理出错: {str(e)}",
                "conversation_id": conv_id,
            }, ensure_ascii=False)
            yield f"data: {error_data}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# ── 普通 JSON 对话（非流式） ──

@router.post("/chat", response_model=ChatResponse)
async def agent_chat(
    req: ChatRequest,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """普通 JSON 对话接口（非流式）"""
    conv_id = req.conversation_id or str(uuid.uuid4())

    await _ensure_conversation(db, conv_id, current_user.id, req.content)
    await _save_message(db, conv_id, "user", req.content)

    try:
        reply = await run_orchestrator(req.content, conversation_id=conv_id)
        await _save_message(db, conv_id, "assistant", reply)
        return ChatResponse(reply=reply, conversation_id=conv_id)
    except Exception as e:
        logger.exception(f"Agent chat error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
