# backend/core/auth.py
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from datetime import datetime
from typing import Optional
from backend.core.config import settings
from backend.models.user import UserOut
from backend.repositories.sqlite.user_repo import UserRepository  # 根据实际路径调整

security = HTTPBearer()

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> UserOut:
    """从 JWT token 中获取当前用户"""
    token = credentials.credentials
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[settings.JWT_ALGORITHM]
        )
        user_id: str = payload.get("sub")
        if user_id is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    user_repo = UserRepository()
    user = await user_repo.get_by_id(int(user_id))
    if user is None:
        raise credentials_exception
    return UserOut(**user)  # 返回 UserOut 对象