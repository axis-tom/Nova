from fastapi import FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import uvicorn
from contextlib import asynccontextmanager
import logging

from backend.api.routes import auth, data_sources, briefings, logs, conversation, settings, market, scheduler
from backend.api.routes import models, amazon_monitor, agent_chat, analysis_tree_api
from backend.api.routes import router as api_router
from backend.config.config import settings
from backend.infrastructure.message_bus import message_bus
from backend.infrastructure.audit_logger import audit_logger
from backend.connectors.crawler_pool import crawler_pool
from backend.utils.logger import logger                                   # ✅ 保留原位

# 新增导入，用于建表
from backend.data.database import engine, Base                            # ✅ 已迁移
import backend.data.models.db  # 确保所有模型被加载
import backend.data.models.amazon_product  # Amazon 产品 ETL 模型

# 新增导入，用于 ToolRegistry
from backend.core.tools.registry import ToolRegistry
from backend.core.tools.mock_tool import MockTool

# 新增导入，用于调度管理器
from backend.infrastructure.scheduler_manager import scheduler_manager      # ✅ 已迁移

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

    # 注册 Mock Tool
    try:
        ToolRegistry.register("mock", MockTool())
        logger.info("Mock tool registered successfully")
    except Exception as e:
        logger.error(f"Failed to register mock tool: {e}")

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
    
    # 启动数据采集调度器
    try:
        await scheduler_manager.start()
        logger.info("Data collection scheduler started")
    except Exception as e:
        logger.error(f"Failed to start data collection scheduler: {e}")
    
    # 启动 Amazon 市场监控调度器
    # 同时启动 Token-Budget-Aware ETL 调度器（负责三源 ETL 定时刷新）
    # 默认关闭：通过 ENABLE_AMAZON_SCHEDULER=1 显式开启
    if settings.ENABLE_AMAZON_SCHEDULER:
        try:
            from backend.business.ecommerce.amazon_monitor.budget_scheduler import budget_scheduler
            budget_scheduler.start()
            logger.info("Token-Budget-Aware ETL scheduler started")
        except Exception as e:
            logger.error(f"Failed to start BudgetAwareScheduler: {e}")

        try:
            from backend.business.ecommerce.amazon_monitor.monitor_scheduler import get_monitor_scheduler
            amazon_scheduler = get_monitor_scheduler()
            amazon_scheduler.start()
            logger.info("Amazon market monitor scheduler started")
        except Exception as e:
            logger.error(f"Failed to start Amazon monitor scheduler: {e}")
    else:
        logger.info("Amazon market monitor scheduler disabled (set ENABLE_AMAZON_SCHEDULER=1 to enable)")
    
    yield  # 应用运行期间
    
    # 关闭时
    logger.info("Shutting down Nova backend...")
    
    # 停止 Amazon 市场监控调度器
    if settings.ENABLE_AMAZON_SCHEDULER:
        try:
            from backend.business.ecommerce.amazon_monitor.budget_scheduler import budget_scheduler
            budget_scheduler.stop()
            logger.info("Token-Budget-Aware ETL scheduler stopped")
        except Exception as e:
            logger.error(f"Error stopping BudgetAwareScheduler: {e}")

        try:
            from backend.business.ecommerce.amazon_monitor.monitor_scheduler import get_monitor_scheduler
            amazon_scheduler = get_monitor_scheduler()
            amazon_scheduler.stop()
            logger.info("Amazon market monitor scheduler stopped")
        except Exception as e:
            logger.error(f"Error stopping Amazon monitor scheduler: {e}")
    
    # 停止数据采集调度器
    try:
        await scheduler_manager.stop()
        logger.info("Data collection scheduler stopped")
    except Exception as e:
        logger.error(f"Error stopping data collection scheduler: {e}")
    
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
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(auth.router, prefix=settings.API_V1_PREFIX)
app.include_router(data_sources.router, prefix=settings.API_V1_PREFIX)
app.include_router(briefings.router, prefix=settings.API_V1_PREFIX)
app.include_router(logs.router, prefix=settings.API_V1_PREFIX)
app.include_router(conversation.router, prefix=settings.API_V1_PREFIX)
app.include_router(market.router, prefix=settings.API_V1_PREFIX)
app.include_router(scheduler.router, prefix=settings.API_V1_PREFIX)

# 注册分析树 API 路由 - 选品分析树查询/回溯/追加维度
app.include_router(analysis_tree_api.router, prefix=settings.API_V1_PREFIX, tags=["分析树"])


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

# 启动独立服务器
if __name__ == "__main__":
    uvicorn.run(
        "backend.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.DEBUG,
        reload_dirs=["/home/nova/projects/Nova/backend"],
        reload_excludes=[settings.DATA_DIR],
        log_level=settings.LOG_LEVEL.lower()
    )