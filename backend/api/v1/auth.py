from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi import APIRouter, HTTPException, Depends, status
from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import datetime, timedelta
import jwt
import os

router = APIRouter(prefix="/auth", tags=["认证"])

# 模拟用户存储（实际应使用数据库）
fake_users_db = {}

# 添加测试账号（在数据库初始化后立即添加）
fake_users_db["test@example.com"] = {
    "id": 999,
    "email": "test@example.com",
    "password": "test123",
    "name": "Test User",
    "created_at": datetime.utcnow()
}

# JWT 配置
SECRET_KEY = os.getenv("JWT_SECRET_KEY", "your-secret-key")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

class UserCreate(BaseModel):
    email: EmailStr
    password: str
    name: str

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class Token(BaseModel):
    access_token: str
    token_type: str

class UserOut(BaseModel):
    id: int
    email: EmailStr
    name: str
    created_at: datetime


security = HTTPBearer()

def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    token = credentials.credentials
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            raise HTTPException(status_code=401, detail="Invalid token")
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Invalid token")
    user = fake_users_db.get(email)
    if user is None:
        raise HTTPException(status_code=401, detail="User not found")
    return user

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=15))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

@router.post("/register", response_model=Token)
async def register(user: UserCreate):
    if user.email in fake_users_db:
        raise HTTPException(status_code=400, detail="Email already registered")
    user_id = len(fake_users_db) + 1
    fake_users_db[user.email] = {
        "id": user_id,
        "email": user.email,
        "password": user.password,  # 实际应哈希存储
        "name": user.name,
        "created_at": datetime.utcnow()
    }

    access_token = create_access_token(data={"sub": user.email})
    return {"access_token": access_token, "token_type": "bearer"}

@router.post("/login", response_model=Token)
async def login(user: UserLogin):
    db_user = fake_users_db.get(user.email)
    if not db_user or db_user["password"] != user.password:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    access_token = create_access_token(data={"sub": user.email})
    return {"access_token": access_token, "token_type": "bearer"}

@router.get("/me", response_model=UserOut)
async def get_current_user_route(current_user: dict = Depends(get_current_user)):
    return UserOut(
        id=current_user["id"],
        email=current_user["email"],
        name=current_user["name"],
        created_at=current_user["created_at"]
    )