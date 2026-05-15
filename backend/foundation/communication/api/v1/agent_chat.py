"""
Agent Chat API — SSE 流式对话接口
将 nova_agent_system 的 orchestrator 以 SSE 流式方式暴露给前端
"""

import json
import asyncio
import uuid
import logging
from typing import AsyncGenerator

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from nova_agent_system.orchestrator import run_orchestrator_stream, run_orchestrator

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/agent", tags=["Agent 对话"])


# ── 请求/响应模型 ──

class ChatRequest(BaseModel):
    content: str
    conversation_id: str | None = None


class ChatResponse(BaseModel):
    reply: str
    conversation_id: str


# ── SSE 流式对话 ──

@router.post("/chat/stream")
async def agent_chat_stream(
    req: ChatRequest,
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

    async def event_generator():
        try:
            async for event in run_orchestrator_stream(req.content, conversation_id=conv_id):
                event_type = event["type"]
                event_data = event["data"]

                # 构造 SSE 事件
                sse_data = json.dumps({
                    "type": event_type,
                    "data": event_data,
                    "conversation_id": conv_id,
                }, ensure_ascii=False)
                yield f"data: {sse_data}\n\n"

            # 发送完成事件
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


# ── 普通 JSON 对话（非流式，兼容旧客户端） ──

@router.post("/chat", response_model=ChatResponse)
async def agent_chat(
    req: ChatRequest,
):
    """普通 JSON 对话接口（非流式）"""
    conv_id = req.conversation_id or str(uuid.uuid4())
    try:
        reply = await run_orchestrator(req.content, conversation_id=conv_id)
        return ChatResponse(reply=reply, conversation_id=conv_id)
    except Exception as e:
        logger.exception(f"Agent chat error: {e}")
        raise HTTPException(status_code=500, detail=str(e))