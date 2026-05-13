"""
Amazon 市场监控 API
提供亚马逊监控任务的触发、状态查询、报告获取等接口

路由前缀: /amazon
"""

from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from pydantic import BaseModel, Field
from typing import Any, Dict, List, Optional
from datetime import datetime

from backend.utils.logger import logger

router = APIRouter(prefix="/amazon", tags=["Amazon 市场监控"])

# ---- 请求/响应模型 ----

class MonitorConfig(BaseModel):
    """监控配置"""
    seed_keywords: List[str] = Field(
        default=["wireless earbuds", "bluetooth speaker", "phone stand"],
        description="种子关键词列表"
    )
    marketplace: str = Field(default="www.amazon.com", description="目标站点")
    price_drop_threshold: float = Field(default=10.0, description="价格下降预警阈值（%）")
    watchlist_asins: List[str] = Field(default=[], description="监控的ASIN列表")


class TriggerRequest(BaseModel):
    """手动触发监控任务请求"""
    task: str = Field(
        default="full",
        description="任务类型: price（价格监控）| review（评论分析）| full（完整报告）"
    )
    config: Optional[MonitorConfig] = None


class TriggerResponse(BaseModel):
    """触发任务响应"""
    success: bool
    task: str
    message: str
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    triggered_at: str = Field(default_factory=lambda: datetime.now().isoformat())


class SchedulerStatusResponse(BaseModel):
    """调度器状态响应"""
    is_running: bool
    job_count: int
    jobs: List[Dict[str, Any]]


class KeywordExpandRequest(BaseModel):
    """关键词扩展请求"""
    seed_keywords: List[str] = Field(..., description="种子关键词")
    expand_count: int = Field(default=20, description="每个种子词扩展数量")
    include_long_tail: bool = Field(default=True, description="是否包含长尾词")


# ---- 全局状态（内存缓存最近一次执行结果）----
_last_results: Dict[str, Any] = {}
_last_alerts: List[Dict[str, Any]] = []
_last_report: str = ""


# ---- 路由 ----

@router.post("/monitor/trigger", response_model=TriggerResponse)
async def trigger_monitor(
    request: TriggerRequest,
    background_tasks: BackgroundTasks,
):
    """
    手动触发 Amazon 监控任务

    - task=price: 价格监控（关键词扩展 → 商品采集 → 流量分析）
    - task=review: 评论分析（关键词扩展 → 商品采集 → 评论分析）
    - task=full: 完整市场报告（全5步流程）
    """
    valid_tasks = ["price", "review", "full"]
    if request.task not in valid_tasks:
        raise HTTPException(
            status_code=400,
            detail=f"无效的任务类型: {request.task}，支持: {valid_tasks}"
        )

    logger.info(f"[AmazonMonitorAPI] Manual trigger: task={request.task}")

    try:
        from backend.business.ecommerce.amazon_monitor.monitor_scheduler import AmazonMonitorScheduler

        config = {}
        if request.config:
            config = {
                "seed_keywords": request.config.seed_keywords,
                "marketplace": request.config.marketplace,
                "price_drop_threshold": request.config.price_drop_threshold,
                "watchlist_asins": request.config.watchlist_asins,
            }

        scheduler = AmazonMonitorScheduler(config=config)
        result = scheduler.trigger_now(task=request.task)

        # 缓存结果
        global _last_results, _last_alerts, _last_report
        _last_results[request.task] = result
        if "price_alerts" in result:
            _last_alerts = result.get("price_alerts", [])
        if "market_report" in result:
            _last_report = result.get("market_report", "")

        return TriggerResponse(
            success=result.get("success", False),
            task=request.task,
            message=f"任务 '{request.task}' 执行完成",
            result=result,
        )

    except Exception as e:
        logger.error(f"[AmazonMonitorAPI] Trigger failed: {e}")
        return TriggerResponse(
            success=False,
            task=request.task,
            message=f"任务执行失败",
            error=str(e),
        )


@router.get("/monitor/status", response_model=SchedulerStatusResponse)
async def get_monitor_status():
    """
    获取 Amazon 监控调度器状态
    返回所有定时任务的运行状态和下次执行时间
    """
    try:
        from backend.business.ecommerce.amazon_monitor.monitor_scheduler import get_monitor_scheduler
        scheduler = get_monitor_scheduler()
        status = scheduler.get_status()
        return SchedulerStatusResponse(**status)
    except Exception as e:
        logger.error(f"[AmazonMonitorAPI] Get status failed: {e}")
        raise HTTPException(status_code=500, detail=f"获取调度器状态失败: {str(e)}")


@router.get("/monitor/report")
async def get_latest_report():
    """
    获取最新的市场报告（Markdown 格式）
    """
    if not _last_report:
        return {
            "has_report": False,
            "message": "暂无报告，请先触发完整市场报告任务（task=full）",
            "report": None,
        }

    return {
        "has_report": True,
        "report": _last_report,
        "generated_at": _last_results.get("full", {}).get("completed_at"),
    }


@router.get("/monitor/alerts")
async def get_latest_alerts():
    """
    获取最新的预警列表
    """
    return {
        "total": len(_last_alerts),
        "alerts": _last_alerts,
        "fetched_at": datetime.now().isoformat(),
    }


@router.get("/monitor/last-results")
async def get_last_results():
    """
    获取最近一次各类任务的执行结果摘要
    """
    return {
        "results": _last_results,
        "fetched_at": datetime.now().isoformat(),
    }


@router.post("/keywords/expand")
async def expand_keywords(request: KeywordExpandRequest):
    """
    关键词扩展接口
    基于种子关键词生成长尾词和相关词
    """
    try:
        from backend.common.core.state import State
        from backend.business.ecommerce.amazon_monitor.agents.keyword_expander import KeywordExpanderAgent

        state = State({
            "seed_keywords": request.seed_keywords,
            "expand_count": request.expand_count,
            "include_long_tail": request.include_long_tail,
        })

        agent = KeywordExpanderAgent()
        result_state = agent.run(state)

        return {
            "success": True,
            "seed_keywords": request.seed_keywords,
            "expanded_keywords": result_state.get("expanded_keywords", []),
            "keyword_groups": result_state.get("keyword_groups", {}),
            "total_count": len(result_state.get("expanded_keywords", [])),
        }

    except Exception as e:
        logger.error(f"[AmazonMonitorAPI] Keyword expand failed: {e}")
        raise HTTPException(status_code=500, detail=f"关键词扩展失败: {str(e)}")


@router.get("/health")
async def amazon_health():
    """Amazon 监控 API 健康检查"""
    return {
        "status": "healthy",
        "api": "amazon_monitor",
        "version": "1.0",
        "endpoints": [
            "POST /amazon/monitor/trigger",
            "GET  /amazon/monitor/status",
            "GET  /amazon/monitor/report",
            "GET  /amazon/monitor/alerts",
            "GET  /amazon/monitor/last-results",
            "POST /amazon/keywords/expand",
        ],
        "checked_at": datetime.now().isoformat(),
    }
