from fastapi import APIRouter, Query, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
from datetime import datetime

from backend.data.database import get_db
from backend.foundation.communication.api.v1.auth import get_current_user
from backend.data.models.user import UserOut
from backend.data.repositories.postgreSQL.log_repo import LogRepository
from backend.data.models.log import LogEntryOut

router = APIRouter(prefix="/logs", tags=["审计日志"])

@router.get("/", response_model=List[LogEntryOut])
async def list_logs(
    start_time: Optional[datetime] = Query(None),
    end_time: Optional[datetime] = Query(None),
    action: Optional[str] = None,
    skip: int = 0,
    limit: int = 50,
    current_user: UserOut = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    repo = LogRepository(db)
    logs = await repo.list(
        user_id=current_user.id,
        start_time=start_time,
        end_time=end_time,
        action=action,
        skip=skip,
        limit=limit
    )
    return logs

@router.get("/{log_id}", response_model=LogEntryOut)
async def get_log(
    log_id: int,
    current_user: UserOut = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    repo = LogRepository(db)
    log = await repo.get(log_id, current_user.id)
    if not log:
        raise HTTPException(status_code=404, detail="Log not found")
    return log
