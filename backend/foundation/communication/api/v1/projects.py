from fastapi import APIRouter, Depends, HTTPException, status
from typing import List
from backend.models.project import ProjectCreate, ProjectUpdate, ProjectOut, TreeNode
from backend.foundation.memory.short_term.conversation_store import ConversationOut
from backend.foundation.communication.api.v1.auth import get_current_user          # 统一使用backend.communication.api.v1.auth中的依赖
from backend.models.user import UserOut                  # 依赖返回 UserOut 对象
from backend.repositories.nocodb.project_repo import ProjectRepository
from backend.repositories.nocodb.conversation_repo import ConversationRepository

router = APIRouter(prefix="/projects", tags=["项目管理"])

@router.get("/", response_model=List[ProjectOut])
async def get_projects(
    current_user = Depends(get_current_user),
    project_repo: ProjectRepository = Depends(),
):
    """获取当前用户的所有项目（含对话列表）"""
    projects = await project_repo.get_by_user(current_user.id)
    # 为每个项目加载对话列表
    for proj in projects:
        proj.children = await ConversationRepository().get_by_project(proj.id)
    return projects

@router.post("/", response_model=ProjectOut, status_code=status.HTTP_201_CREATED)
async def create_project(
    data: ProjectCreate,
    current_user = Depends(get_current_user),
    repo: ProjectRepository = Depends(),
):
    """创建新项目"""
    return await repo.create(user_id=current_user.id, name=data.name)

@router.put("/{project_id}", response_model=ProjectOut)
async def update_project(
    project_id: int,
    data: ProjectUpdate,
    current_user = Depends(get_current_user),
    repo: ProjectRepository = Depends(),
):
    """更新项目（如重命名）"""
    project = await repo.get_by_id(project_id)
    if not project or project.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="项目不存在")
    return await repo.update(project_id, data.dict(exclude_unset=True))

@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project(
    project_id: int,
    current_user = Depends(get_current_user),
    repo: ProjectRepository = Depends(),
    conv_repo: ConversationRepository = Depends(),
):
    """删除项目（级联删除其下所有对话）"""
    project = await repo.get_by_id(project_id)
    if not project or project.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="项目不存在")
    # 先删除项目下所有对话（消息级联删除由数据库外键或手动处理）
    await conv_repo.delete_by_project(project_id)
    await repo.delete(project_id)

@router.get("/tree", response_model=List[TreeNode])
async def get_tree(
    current_user = Depends(get_current_user),
    project_repo: ProjectRepository = Depends(),
    conv_repo: ConversationRepository = Depends(),
):
    """返回项目-对话树形结构（供前端直接使用）"""
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
