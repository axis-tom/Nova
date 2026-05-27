from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException, Depends, status
from pydantic import BaseModel
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.routes.auth import get_current_user
from backend.data.database import get_db
from backend.data.models.conversation import (
    ConversationCreate,
    ConversationUpdate,
    ConversationOut,
    ConversationResponse,
    MessageOut,
)
from backend.data.models.project import TreeNode
from backend.data.repositories.postgreSQL.conversation_repo import ConversationRepository
from backend.data.repositories.postgreSQL.message_repo import MessageRepository
from backend.data.repositories.postgreSQL.project_repo import ProjectRepository
from backend.core.orchestrator import run_orchestrator

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
    """发送消息并获取回复"""
    conv_repo = ConversationRepository(db)
    msg_repo = MessageRepository(db)

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

    # 调用 LangGraph Agent 生成回复
    conv_id_str = str(req.conversation_id)
    try:
        reply = await run_orchestrator(req.content, conversation_id=conv_id_str)
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
    return msgs

# ========== WebSocket ==========
@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            data = await websocket.receive_text()
            await websocket.send_text(f"Echo: {data}")
    except WebSocketDisconnect:
        print("Client disconnected")