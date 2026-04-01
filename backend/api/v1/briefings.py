from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
from datetime import datetime

from backend.core.database import AsyncSessionLocal, get_db
from backend.api.v1.auth import get_current_user
from backend.models.user import UserOut
from backend.models.briefing import BriefingCreate, BriefingOut, BriefingUpdate
from backend.repositories.postgres.briefing_repo import BriefingRepository
from backend.agents.collector.email_agent import EmailAgent

router = APIRouter(prefix="/briefings", tags=["简报"])

# ---------- 后台任务 ----------
async def generate_briefing_task(user_id: int, briefing_data: dict):
    """后台生成简报任务，使用独立的数据库会话"""
    async with AsyncSessionLocal() as db:
        try:
            # 1. 获取用户的数据源（通过 EmailAgent）
            agent = EmailAgent(db)
            from backend.agents.base import AgentInput
            input_data = AgentInput(user_id=user_id, parameters=briefing_data)
            output = await agent.execute(input_data)

            # 2. 生成简报内容（模拟，实际可调用 LLM）
            content = f"今日简报：共采集到 {len(output.result)} 条新邮件。\n"
            for email in output.result[:5]:
                content += f"- {email.get('subject', '无主题')}\n"

            # 更新简报内容
            repo = BriefingRepository(db)
            # 关键修复：将字典转换为 BriefingUpdate 对象
            await repo.update(briefing_data.get("id"), user_id, BriefingUpdate(content=content))
        except Exception as e:
            print(f"生成简报失败: {e}")

# ---------- 路由 ----------
@router.post("/", response_model=BriefingOut, status_code=201)
async def create_briefing(
    briefing: BriefingCreate,
    background_tasks: BackgroundTasks,
    current_user: UserOut = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    repo = BriefingRepository(db)
    new_brief = await repo.create(current_user.id, briefing)
    background_tasks.add_task(generate_briefing_task, current_user.id, new_brief.dict())
    return new_brief

@router.get("/", response_model=List[BriefingOut])
async def list_briefings(
    skip: int = 0,
    limit: int = 20,
    current_user: UserOut = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    repo = BriefingRepository(db)
    briefings = await repo.list(current_user.id, skip, limit)
    return briefings

@router.get("/{brief_id}", response_model=BriefingOut)
async def get_briefing(
    brief_id: int,
    current_user: UserOut = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    repo = BriefingRepository(db)
    briefing = await repo.get(brief_id, current_user.id)
    if not briefing:
        raise HTTPException(status_code=404, detail="Briefing not found")
    return briefing

@router.post("/generate", response_model=BriefingOut)
async def generate_now(
    current_user: UserOut = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """立即生成简报（同步调用，等待完成）"""
    repo = BriefingRepository(db)
    new_brief = await repo.create(
        current_user.id,
        BriefingCreate(title="今日简报", content="生成中...", source_data={})
    )
    await generate_briefing_task(current_user.id, new_brief.dict())
    updated = await repo.get(new_brief.id, current_user.id)
    return updated


# ---------- 新增删除路由 ----------
@router.delete("/{brief_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_briefing(
    brief_id: int,
    current_user: UserOut = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    repo = BriefingRepository(db)
    success = await repo.delete(brief_id, current_user.id)
    if not success:
        raise HTTPException(status_code=404, detail="Briefing not found")