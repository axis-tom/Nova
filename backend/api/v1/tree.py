# backend/api/v1/tree.py
from fastapi import APIRouter, Depends, HTTPException, status
from typing import List
from backend.models.project import ProjectCreate, ProjectUpdate, ProjectOut
from backend.models.conversation import ConversationCreate, ConversationUpdate, ConversationOut
from backend.repositories.postgres.project_repo import ProjectRepository
from backend.repositories.postgres.conversation_repo import ConversationRepository

router = APIRouter(prefix="/tree", tags=["项目与对话"])


# ==================== 树形结构 ====================
@router.get("/", response_model=List[dict])
async def get_tree(user_id: int = 1):
    """获取项目-对话树形结构"""
    project_repo = ProjectRepository()
    conversation_repo = ConversationRepository()
    
    projects = await project_repo.list(user_id)
    result = []
    for proj in projects:
        convos = await conversation_repo.list_by_project(proj.id, user_id)
        result.append({
            "id": proj.id,
            "name": proj.name,
            "type": "project",
            "children": [
                {"id": c.id, "name": c.name, "type": "conversation"}
                for c in convos
            ]
        })
    return result


# ==================== 项目操作 ====================
@router.post("/projects", response_model=ProjectOut, status_code=status.HTTP_201_CREATED)
async def create_project(data: ProjectCreate, user_id: int = 1):
    repo = ProjectRepository()
    return await repo.create(user_id, data)

@router.put("/projects/{project_id}", response_model=ProjectOut)
async def update_project(project_id: int, data: ProjectUpdate, user_id: int = 1):
    repo = ProjectRepository()
    result = await repo.update(project_id, user_id, data)
    if not result:
        raise HTTPException(status_code=404, detail="Project not found")
    return result

@router.delete("/projects/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project(project_id: int, user_id: int = 1):
    """删除项目（级联删除所有对话）"""
    repo = ProjectRepository()
    if not await repo.delete(project_id, user_id):
        raise HTTPException(status_code=404, detail="Project not found")


# ==================== 对话操作 ====================
@router.post("/conversations", response_model=ConversationOut, status_code=status.HTTP_201_CREATED)
async def create_conversation(data: ConversationCreate, user_id: int = 1):
    repo = ConversationRepository()
    return await repo.create(user_id, data)

@router.put("/conversations/{conv_id}", response_model=ConversationOut)
async def update_conversation(conv_id: int, data: ConversationUpdate, user_id: int = 1):
    repo = ConversationRepository()
    result = await repo.update(conv_id, user_id, data)
    if not result:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return result

@router.delete("/conversations/{conv_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_conversation(conv_id: int, user_id: int = 1):
    repo = ConversationRepository()
    if not await repo.delete(conv_id, user_id):
        raise HTTPException(status_code=404, detail="Conversation not found")