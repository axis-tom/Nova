"""
数据采集调度器 API

提供手动触发数据采集、查看任务状态等功能
"""

from fastapi import APIRouter, Depends, HTTPException, status
from typing import Dict, Any, Optional
from pydantic import BaseModel

from backend.foundation.communication.scheduler_manager import scheduler_manager
from backend.foundation.communication.api.v1.auth import get_current_user
from backend.models.user import UserOut

router = APIRouter(prefix="/scheduler", tags=["数据采集调度"])

class ManualCollectionRequest(BaseModel):
    """手动触发数据采集请求"""
    user_id: Optional[int] = None  # 如果为None，则采集所有用户的数据

class JobInfo(BaseModel):
    """任务信息"""
    id: str
    name: str
    next_run_time: Optional[str]
    trigger: Dict[str, Any]

class CollectionResult(BaseModel):
    """采集结果"""
    success: bool
    message: str
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None

@router.get("/jobs", response_model=list[JobInfo])
async def get_scheduled_jobs(current_user: UserOut = Depends(get_current_user)):
    """获取所有定时任务"""
    jobs = scheduler_manager.get_jobs()
    
    job_infos = []
    for job in jobs:
        job_infos.append(JobInfo(
            id=job.id,
            name=job.name,
            next_run_time=str(job.next_run_time) if job.next_run_time else None,
            trigger={
                "type": str(job.trigger),
                "expression": str(job.trigger) if hasattr(job.trigger, '__str__') else None
            }
        ))
    
    return job_infos

@router.post("/trigger-collection", response_model=CollectionResult)
async def trigger_manual_collection(
    request: ManualCollectionRequest,
    current_user: UserOut = Depends(get_current_user)
):
    """手动触发数据采集"""
    try:
        result = await scheduler_manager.trigger_manual_collection(request.user_id)
        return CollectionResult(**result)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to trigger collection: {str(e)}"
        )

@router.get("/status")
async def get_scheduler_status(current_user: UserOut = Depends(get_current_user)):
    """获取调度器状态"""
    jobs = scheduler_manager.get_jobs()
    
    return {
        "running": scheduler_manager.scheduler.running,
        "job_count": len(jobs),
        "jobs": [
            {
                "id": job.id,
                "name": job.name,
                "next_run": str(job.next_run_time) if job.next_run_time else None,
                "pending": job.pending
            }
            for job in jobs
        ]
    }

@router.post("/test-collection")
async def test_collection(current_user: UserOut = Depends(get_current_user)):
    """测试数据采集（仅采集当前用户的数据）"""
    try:
        result = await scheduler_manager.trigger_manual_collection(current_user.id)
        return result
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Test collection failed: {str(e)}"
        )
