from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional

router = APIRouter(prefix="/settings", tags=["设置"])

class UserSettings(BaseModel):
    language: str = "zh-CN"
    theme: str = "light"
    notification_enabled: bool = True
    briefing_time: str = "08:00"  # 每日简报生成时间
    risk_threshold: int = 70      # 风险预警阈值 0-100
    MODEL_STORAGE_PATH: str = "./models"

class UserSettingsUpdate(BaseModel):
    language: Optional[str] = None
    theme: Optional[str] = None
    notification_enabled: Optional[bool] = None
    briefing_time: Optional[str] = None
    risk_threshold: Optional[int] = None

# class Settings(BaseSettings):
#     language: Optional[str] = None
#     theme: Optional[str] = None
#     notification_enabled: Optional[bool] = None
#     briefing_time: Optional[str] = None
#     risk_threshold: Optional[int] = None
    

# 模拟存储
fake_settings = {
    1: UserSettings()
}

@router.get("/", response_model=UserSettings)
async def get_settings(user_id: int = 1):
    return fake_settings.get(user_id, UserSettings())

@router.put("/", response_model=UserSettings)
async def update_settings(update: UserSettingsUpdate, user_id: int = 1):
    current = fake_settings.get(user_id, UserSettings())
    updated_data = current.dict()
    for key, value in update.dict(exclude_unset=True).items():
        updated_data[key] = value
    new_settings = UserSettings(**updated_data)
    fake_settings[user_id] = new_settings
    return new_settings
