from fastapi import APIRouter

# 导入各个子路由模块
from .auth import router as auth_router
from .data_sources import router as data_sources_router
from .briefings import router as briefings_router
from .logs import router as logs_router
from .conversation import router as conversation_router
from .settings import router as settings_router
from .market import router as market_router
from .models import router as models_router

# 创建主路由
router = APIRouter()

# 将子路由挂载到主路由
router.include_router(auth_router, prefix="/auth", tags=["认证"])
router.include_router(data_sources_router, prefix="/data-sources", tags=["数据源"])
router.include_router(briefings_router, prefix="/briefings", tags=["简报"])
router.include_router(logs_router, prefix="/logs", tags=["审计日志"])
router.include_router(conversation_router, prefix="/conversation", tags=["对话"])
router.include_router(settings_router, prefix="/settings", tags=["设置"])
router.include_router(market_router, prefix="/market", tags=["场景商店"])
router.include_router(models_router, prefix="/AI model", tags=["AI模型"])