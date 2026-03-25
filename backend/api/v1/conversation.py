from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
import json

router = APIRouter(prefix="/conversation", tags=["对话"])

class Message(BaseModel):
    id: int
    user_id: int
    role: str          # user, assistant
    content: str
    timestamp: datetime

class ConversationCreate(BaseModel):
    message: str

class ConversationResponse(BaseModel):
    reply: str
    conversation_id: str

# 模拟对话存储
fake_messages = []
next_msg_id = 1

@router.post("/send", response_model=ConversationResponse)
async def send_message(conv: ConversationCreate, user_id: int = 1):
    """发送消息并获取回复（同步）"""
    # 存储用户消息
    global next_msg_id
    now = datetime.utcnow()
    user_msg = Message(
        id=next_msg_id,
        user_id=user_id,
        role="user",
        content=conv.message,
        timestamp=now
    )
    fake_messages.append(user_msg)
    next_msg_id += 1

    # 模拟智能体回复（实际应调用对话经理）
    reply_content = f"这是对「{conv.message}」的模拟回复。实际将由 AI 生成。"
    assistant_msg = Message(
        id=next_msg_id,
        user_id=user_id,
        role="assistant",
        content=reply_content,
        timestamp=datetime.utcnow()
    )
    fake_messages.append(assistant_msg)
    next_msg_id += 1

    return ConversationResponse(reply=reply_content, conversation_id=f"conv_{user_id}")

@router.get("/history", response_model=List[Message])
async def get_history(user_id: int = 1, limit: int = 50):
    user_msgs = [msg for msg in fake_messages if msg.user_id == user_id]
    return user_msgs[-limit:]

@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            data = await websocket.receive_text()
            # 解析消息，调用对话经理，回复
            # 这里简单 echo
            await websocket.send_text(f"Echo: {data}")
    except WebSocketDisconnect:
        print("Client disconnected")