from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
import asyncio

router = APIRouter(prefix="/briefings", tags=["简报"])

class BriefingBase(BaseModel):
    title: str
    content: str
    source_data: Optional[dict] = None  # 原始数据摘要

class BriefingCreate(BriefingBase):
    pass

class BriefingOut(BriefingBase):
    id: int
    user_id: int
    created_at: datetime

# 模拟存储
fake_briefings = []
next_id = 1

async def generate_briefing_task(user_id: int, briefing_data: dict):
    """后台生成简报任务（模拟）"""
    await asyncio.sleep(2)  # 模拟耗时
    # 实际应调用智能体群生成内容
    print(f"Generated briefing for user {user_id}: {briefing_data}")

@router.post("/", response_model=BriefingOut, status_code=201)
async def create_briefing(
    briefing: BriefingCreate,
    background_tasks: BackgroundTasks,
    user_id: int = 1
):
    global next_id
    now = datetime.utcnow()
    new_brief = BriefingOut(
        id=next_id,
        user_id=user_id,
        **briefing.dict(),
        created_at=now
    )
    fake_briefings.append(new_brief)
    next_id += 1

    # 触发后台生成任务（实际可能由调度引擎执行）
    background_tasks.add_task(generate_briefing_task, user_id, new_brief.dict())
    return new_brief

@router.get("/", response_model=List[BriefingOut])
async def list_briefings(user_id: int = 1, skip: int = 0, limit: int = 20):
    user_briefs = [b for b in fake_briefings if b.user_id == user_id]
    return user_briefs[skip: skip+limit]

@router.get("/{brief_id}", response_model=BriefingOut)
async def get_briefing(brief_id: int, user_id: int = 1):
    for b in fake_briefings:
        if b.id == brief_id and b.user_id == user_id:
            return b
    raise HTTPException(status_code=404, detail="Briefing not found")

@router.post("/generate", response_model=BriefingOut)
async def generate_now(user_id: int = 1):
    """立即生成简报（同步，模拟）"""
    # 实际会调用 SOP 执行器
    now = datetime.utcnow()
    global next_id
    new_brief = BriefingOut(
        id=next_id,
        user_id=user_id,
        title="今日简报",
        content="这是模拟生成的简报内容。实际应由智能体群生成。",
        source_data={},
        created_at=now
    )
    fake_briefings.append(new_brief)
    next_id += 1
    return new_brief