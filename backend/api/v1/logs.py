from fastapi import APIRouter, Query, HTTPException
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

router = APIRouter(prefix="/logs", tags=["审计日志"])

class LogEntry(BaseModel):
    id: int
    user_id: int
    action: str          # 操作类型，如 "data_source.create", "briefing.generate"
    details: dict        # 详细参数
    status: str          # success, failure
    error_msg: Optional[str] = None
    timestamp: datetime

# 模拟日志数据
fake_logs = []

@router.get("/", response_model=List[LogEntry])
async def list_logs(
    user_id: int = 1,
    start_time: Optional[datetime] = Query(None),
    end_time: Optional[datetime] = Query(None),
    action: Optional[str] = None,
    skip: int = 0,
    limit: int = 50
):
    filtered = [log for log in fake_logs if log.user_id == user_id]
    if start_time:
        filtered = [log for log in filtered if log.timestamp >= start_time]
    if end_time:
        filtered = [log for log in filtered if log.timestamp <= end_time]
    if action:
        filtered = [log for log in filtered if log.action == action]
    return filtered[skip: skip+limit]

@router.get("/{log_id}", response_model=LogEntry)
async def get_log(log_id: int, user_id: int = 1):
    for log in fake_logs:
        if log.id == log_id and log.user_id == user_id:
            return log
    raise HTTPException(status_code=404, detail="Log not found")