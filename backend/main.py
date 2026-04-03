from fastapi import FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import uvicorn
from contextlib import asynccontextmanager
import logging

from backend.api.v1 import auth, data_sources, briefings, logs, conversation, settings, market
from backend.api.v1 import models, tree
from backend.api.v1 import router as api_router
from backend.core.config import settings
from backend.core.message_bus import message_bus
from backend.core.audit import audit_logger
from backend.cloud.crawler_pool import crawler_pool
from backend.utils.logger import logger

# 新增导入，用于建表
from backend.core.database import engine, Base
import backend.models.db  # 确保所有模型被加载

# 生命周期管理
@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    应用启动和关闭时的操作
    """
    
    # 启动时
    logger.info("Starting Nova backend...")
    
    # 创建数据库表（如果不存在）
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("Database tables created (if not exist)")
    except Exception as e:
        logger.error(f"Database initialization skipped: {e}")

    # 初始化消息总线连接
    try:
        await message_bus.connect()
        logger.info("Message bus connected")
    except Exception as e:
        logger.error(f"Failed to connect message bus: {e}")
    
    # 启动审计日志后台任务
    try:
        await audit_logger.start()
        logger.info("Audit logger started")
    except Exception as e:
        logger.error(f"Failed to start audit logger: {e}")
    
    # 可选：启动爬虫池工作进程（如需要）
    # await crawler_pool.start_workers(worker_count=2)
    
    yield  # 应用运行期间
    
    # 关闭时
    logger.info("Shutting down Nova backend...")
    
    # 关闭消息总线
    try:
        await message_bus.close()
        logger.info("Message bus closed")
    except Exception as e:
        logger.error(f"Error closing message bus: {e}")
    
    # 停止审计日志
    try:
        await audit_logger.stop()
        logger.info("Audit logger stopped")
    except Exception as e:
        logger.error(f"Error stopping audit logger: {e}")

    
    

# 创建 FastAPI 应用
app = FastAPI(
    title=settings.APP_NAME,
    version="1.0.0",
    description="Nova 智能体运营系统后端 API",
    lifespan=lifespan,
    debug=settings.DEBUG
)

# 配置 CORS
app.add_middleware(
    CORSMiddleware,
    # allow_origins=["*"],  # 生产环境应限制具体域名
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(auth.router, prefix=settings.API_V1_PREFIX)
# print("Before data_sources router include")
app.include_router(data_sources.router, prefix=settings.API_V1_PREFIX)
# print("After data_sources router include")
app.include_router(briefings.router, prefix=settings.API_V1_PREFIX)
app.include_router(logs.router, prefix=settings.API_V1_PREFIX)
app.include_router(conversation.router, prefix=settings.API_V1_PREFIX)
# app.include_router(settings.router, prefix=settings.API_V1_PREFIX)
# app.include_router(api_router, prefix=settings.API_V1_PREFIX)
app.include_router(market.router, prefix=settings.API_V1_PREFIX)
# app.include_router(models.router, prefix=settings.API_V1_PREFIX)
# app.include_router(tree.router, prefix=settings.API_V1_PREFIX)


# # 创建数据库表（如果未创建）
# models.Base.metadata.create_all(bind=engine)

# @app.on_event("startup")
# def create_test_user():
#     db = SessionLocal()
#     # 检查是否已存在测试账号
#     existing_user = db.query(models.User).filter(models.User.email == "test@example.com").first()
#     if not existing_user:
#         # 创建测试用户
#         hashed_password = auth.get_password_hash("test123")
#         test_user = models.User(
#             email="test@example.com",
#             name="Test User",
#             hashed_password=hashed_password,
#             is_active=True
#         )
#         db.add(test_user)
#         db.commit()
#         print("✅ 测试账号已创建: test@example.com / test123")
#     else:
#         print("ℹ️ 测试账号已存在")
#     db.close()


# 健康检查端点
@app.get("/health", tags=["系统"])
async def health_check():
    """健康检查"""
    return {"status": "ok"}

@app.get("/", tags=["系统"])
async def root():
    """根路径，返回基本信息"""
    return {
        "app": settings.APP_NAME,
        "version": "1.0.0",
        "docs": "/docs"
    }

# 全局异常处理
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """HTTP 异常处理"""
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail},
    )

@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    """通用异常处理，记录错误并返回 500"""
    logger.exception(f"Unhandled exception: {exc}")
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Internal server error"},
    )

# 可选：启动独立服务器（用于直接运行）
if __name__ == "__main__":
    uvicorn.run(
        "backend.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.DEBUG,
        log_level=settings.LOG_LEVEL.lower()
    )