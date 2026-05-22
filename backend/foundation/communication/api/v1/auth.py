from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, EmailStr, field_validator
from datetime import datetime, timedelta
from typing import Optional
import jwt
import bcrypt
import re

from backend.config.config import settings
from backend.data.database import get_db
from backend.data.repositories.postgreSQL.user_repo import UserRepository
from backend.data.models.user import UserCreate, UserOut

router = APIRouter(prefix="/auth", tags=["认证"])
security = HTTPBearer()

# ---------- 辅助函数 ----------
def hash_password(password: str) -> str:
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')

def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode('utf-8'), hashed.encode('utf-8'))

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)

# ---------- 请求/响应模型 ----------
class UserLogin(BaseModel):
    email: EmailStr
    password: str

class UserRegister(UserCreate):
    """注册请求模型，继承自UserCreate"""
    pass

class Token(BaseModel):
    access_token: str
    token_type: str
    user: Optional[UserOut] = None

# ---------- 依赖注入：获取当前用户 ----------
security_optional = HTTPBearer(auto_error=False)

async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(security_optional),
    db: AsyncSession = Depends(get_db)
) -> UserOut:
    if settings.DEBUG and (credentials is None or credentials.credentials == "dev-token"):
        return UserOut(id=1, email="dev@example.com", name="开发者")

    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = credentials.credentials
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
        user_id: str = payload.get("sub")
        if user_id is None:
            raise credentials_exception
    except jwt.PyJWTError:
        raise credentials_exception

    repo = UserRepository(db)
    user = await repo.get(int(user_id))
    if user is None:
        raise credentials_exception

    return UserOut(
        id=user.id,
        email=user.email,
        name=user.name,
        company=user.company,
        phone=user.phone,
        created_at=user.created_at,
        updated_at=user.updated_at
    )

# ---------- 路由 ----------
@router.post("/register", response_model=Token)
async def register(user: UserRegister, db: AsyncSession = Depends(get_db)):
    """
    用户注册
    - 验证邮箱是否已注册
    - 密码哈希存储
    - 创建用户并返回JWT token
    """
    repo = UserRepository(db)
    
    # 检查邮箱是否已注册
    existing = await repo.get_by_email(user.email)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="该邮箱已被注册"
        )
    
    # 哈希密码
    hashed_password = hash_password(user.password)
    
    # 创建用户数据字典
    user_data = user.model_dump(exclude={'password'})
    user_data['password'] = hashed_password
    
    # 创建用户
    new_user = await repo.create(UserCreate(**user_data))
    
    # 创建访问令牌
    access_token = create_access_token(data={"sub": str(new_user.id)})
    
    # 返回用户信息
    user_out = UserOut(
        id=new_user.id,
        email=new_user.email,
        name=new_user.name,
        company=new_user.company,
        phone=new_user.phone,
        created_at=new_user.created_at,
        updated_at=new_user.updated_at
    )
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": user_out
    }

@router.post("/login", response_model=Token)
async def login(user: UserLogin, db: AsyncSession = Depends(get_db)):
    """
    用户登录
    - 验证邮箱和密码
    - 返回JWT token和用户信息
    """
    repo = UserRepository(db)
    db_user = await repo.get_by_email(user.email)
    
    if not db_user or not verify_password(user.password, db_user.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="邮箱或密码错误"
        )
    
    # 创建访问令牌
    access_token = create_access_token(data={"sub": str(db_user.id)})
    
    # 返回用户信息
    user_out = UserOut(
        id=db_user.id,
        email=db_user.email,
        name=db_user.name,
        # company=db_user.company,
        # phone=db_user.phone,
        created_at=db_user.created_at,
        updated_at=db_user.updated_at
    )
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": user_out
    }

@router.get("/me", response_model=UserOut)
async def get_current_user_route(current_user: UserOut = Depends(get_current_user)):
    """
    获取当前用户信息
    """
    return current_user

@router.post("/check-email")
async def check_email(email: str, db: AsyncSession = Depends(get_db)):
    """
    检查邮箱是否已注册
    """
    repo = UserRepository(db)
    existing = await repo.get_by_email(email)
    
    return {
        "email": email,
        "available": existing is None
    }
