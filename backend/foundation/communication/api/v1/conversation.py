from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException, Depends, status
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
import json
import uuid
from sqlalchemy.ext.asyncio import AsyncSession

from backend.foundation.communication.api.v1.auth import get_current_user
from backend.data.database import get_db
from backend.foundation.cognition.orchestrator.brain import orchestrator
from backend.foundation.memory.short_term.conversation_store import (
    ConversationCreate,
    ConversationUpdate,
    ConversationOut,
    ConversationResponse,
    MessageOut
)
from backend.models.project import TreeNode
from backend.repositories.postgres.conversation_repo import ConversationRepository
from backend.repositories.postgres.message_repo import MessageRepository
from backend.repositories.postgres.project_repo import ProjectRepository

router = APIRouter(prefix="/conversation", tags=["对话"])

# ========== 树形结构接口 ==========
@router.get("/tree", response_model=List[TreeNode])
async def get_conversation_tree(
    current_user = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取项目-对话树形结构（供前端侧边栏使用）"""
    project_repo = ProjectRepository(db)
    conv_repo = ConversationRepository(db)

    projects = await project_repo.get_by_user(current_user.id)
    tree = []
    for proj in projects:
        convs = await conv_repo.get_by_project(proj.id)
        children = [
            TreeNode(
                id=conv.id,
                name=conv.name,
                type="conversation",
                children=[]
            )
            for conv in convs
        ]
        tree.append(TreeNode(
            id=proj.id,
            name=proj.name,
            type="project",
            children=children
        ))
    return tree

# ========== 对话管理 ==========
@router.get("/conversations", response_model=List[ConversationOut])
async def get_conversations(
    project_id: int,
    current_user = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取指定项目下的对话列表"""
    repo = ConversationRepository(db)
    convs = await repo.get_by_project(project_id)
    # 确保对话属于当前用户（repository层已过滤）
    return convs

@router.post("/conversations", response_model=ConversationOut, status_code=status.HTTP_201_CREATED)
async def create_conversation(
    data: ConversationCreate,
    current_user = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """在指定项目下创建新对话"""
    project_repo = ProjectRepository(db)
    repo = ConversationRepository(db)

    # 验证项目存在且属于当前用户
    project = await project_repo.get_by_id(data.project_id)
    if not project or project.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="项目不存在")
    return await repo.create(
        user_id=current_user.id,
        project_id=data.project_id,
        name=data.name,
        scene_id=data.scene_id,
        model_id=data.model_id
    )

@router.put("/conversations/{conv_id}", response_model=ConversationOut)
async def update_conversation(
    conv_id: int,
    data: ConversationUpdate,
    current_user = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """更新对话（重命名或修改默认场景/模型）"""
    repo = ConversationRepository(db)
    conv = await repo.get_by_id(conv_id)
    if not conv or conv.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="对话不存在")
    return await repo.update(conv_id, data.dict(exclude_unset=True))

@router.delete("/conversations/{conv_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_conversation(
    conv_id: int,
    current_user = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """删除对话（同时删除其下所有消息）"""
    conv_repo = ConversationRepository(db)
    msg_repo = MessageRepository(db)

    conv = await conv_repo.get_by_id(conv_id)
    if not conv or conv.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="对话不存在")
    await msg_repo.delete_by_conversation(conv_id)
    await conv_repo.delete(conv_id)

# ========== 消息接口 ==========
class SendMessageRequest(BaseModel):
    conversation_id: int
    content: str
    scene_id: Optional[str] = None
    function: Optional[str] = None
    model_id: Optional[str] = None

@router.post("/send", response_model=ConversationResponse)
async def send_message(
    req: SendMessageRequest,
    current_user = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """发送消息并获取回复（保存消息元数据）"""
    conv_repo = ConversationRepository(db)
    msg_repo = MessageRepository(db)

    # 验证对话归属
    conv = await conv_repo.get_by_id(req.conversation_id)
    if not conv or conv.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="对话不存在")

    # 保存用户消息
    user_msg = await msg_repo.create(
        conversation_id=req.conversation_id,
        user_id=current_user.id,
        role="user",
        content=req.content,
        scene_id=req.scene_id,
        function=req.function,
        model_id=req.model_id
    )

    # 调用智能体生成回复（使用 orchestrator）
    context = {
        "user_message": req.content,
        "scene_id": req.scene_id,
        "function": req.function,
        "model_id": req.model_id,
        "conversation_id": req.conversation_id
    }
    try:
        result = await orchestrator.run_sop(
            sop_name="conversation",
            context=context,
            user_id=current_user.id,
            trace_id=str(uuid.uuid4())
        )
        reply = result.get("reply", "抱歉，我暂时无法回答。")
    except Exception as e:
        reply = f"处理出错：{str(e)}"

    # 保存助手消息
    assistant_msg = await msg_repo.create(
        conversation_id=req.conversation_id,
        user_id=current_user.id,
        role="assistant",
        content=reply,
        scene_id=req.scene_id,
        function=req.function,
        model_id=req.model_id
    )

    return ConversationResponse(reply=reply, conversation_id=str(req.conversation_id))

# ========== 历史消息 ==========
@router.get("/history/{conversation_id}", response_model=List[MessageOut])
async def get_history(
    conversation_id: int,
    current_user = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取指定对话的历史消息"""
    msg_repo = MessageRepository(db)
    msgs = await msg_repo.get_by_conversation(conversation_id)
    # 确保消息属于当前用户（repository层已过滤）
    return msgs

# ========== WebSocket（保留原有，可增强） ==========
@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            data = await websocket.receive_text()
            # 这里可扩展为传递 scene_id/model_id 等
            await websocket.send_text(f"Echo: {data}")
    except WebSocketDisconnect:
        print("Client disconnected")
