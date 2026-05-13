"""
Amazon 监控定时调度器
基于 APScheduler 实现三种定时任务：
  - 每小时：价格监控
  - 每天凌晨2点：评论分析
  - 每周一凌晨3点：完整市场报告

使用方式：
  from backend.business.ecommerce.amazon_monitor.monitor_scheduler import AmazonMonitorScheduler
  scheduler = AmazonMonitorScheduler()
  scheduler.start()
"""

import asyncio
from typing import Any, Dict, List, Optional
from datetime import datetime

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from backend.common.core.state import State
from backend.business.ecommerce.amazon_monitor.agents import (
    KeywordExpanderAgent,
    ProductCollectorAgent,
    AmazonReviewAnalyzerAgent,
    TrafficAnalyzerAgent,
    OpportunityJudgeAgent,
)
from backend.utils.logger import logger


class AmazonMonitorScheduler:
    """
    Amazon 市场监控定时调度器
    管理三种定时监控任务
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        初始化调度器

        Args:
            config: 可选配置，覆盖 sop.yaml 中的默认值
                - seed_keywords: List[str] 种子关键词
                - watchlist_asins: List[str] 监控 ASIN 列表
                - price_drop_threshold: float 价格下降预警阈值（%）
                - marketplace: str 目标站点
        """
        self.config = config or {}
        self.scheduler = AsyncIOScheduler(timezone="Asia/Shanghai")
        self._is_running = False

        # 初始化 Agent
        self.keyword_expander = KeywordExpanderAgent()
        self.product_collector = ProductCollectorAgent()
        self.review_analyzer = AmazonReviewAnalyzerAgent()
        self.traffic_analyzer = TrafficAnalyzerAgent()
        self.opportunity_judge = OpportunityJudgeAgent()

        logger.info("[AmazonMonitorScheduler] Initialized")

    def start(self):
        """启动调度器，注册所有定时任务"""
        if self._is_running:
            logger.warning("[AmazonMonitorScheduler] Already running")
            return

        # 每小时价格监控（整点执行）
        self.scheduler.add_job(
            func=self._run_price_monitor,
            trigger=CronTrigger(minute=0),
            id="amazon_price_monitor",
            name="Amazon 价格监控（每小时）",
            replace_existing=True,
            max_instances=1,
            coalesce=True,
            misfire_grace_time=300,
        )

        # 每天凌晨2点：评论分析
        self.scheduler.add_job(
            func=self._run_review_analysis,
            trigger=CronTrigger(hour=2, minute=0),
            id="amazon_review_analysis",
            name="Amazon 评论分析（每日）",
            replace_existing=True,
            max_instances=1,
            coalesce=True,
            misfire_grace_time=600,
        )

        # 每周一凌晨3点：完整市场报告
        self.scheduler.add_job(
            func=self._run_full_market_report,
            trigger=CronTrigger(day_of_week="mon", hour=3, minute=0),
            id="amazon_market_report",
            name="Amazon 市场报告（每周）",
            replace_existing=True,
            max_instances=1,
            coalesce=True,
            misfire_grace_time=1800,
        )

        self.scheduler.start()
        self._is_running = True

        jobs = self.scheduler.get_jobs()
        logger.info(f"[AmazonMonitorScheduler] Started with {len(jobs)} jobs:")
        for job in jobs:
            logger.info(f"  - {job.name}: next run at {job.next_run_time}")

    def stop(self):
        """停止调度器"""
        if self._is_running and self.scheduler.running:
            self.scheduler.shutdown(wait=False)
            self._is_running = False
            logger.info("[AmazonMonitorScheduler] Stopped")

    def trigger_now(self, task: str = "full") -> Dict[str, Any]:
        """
        手动立即触发任务（用于测试或手动刷新）

        Args:
            task: "price" | "review" | "full"

        Returns:
            执行结果
        """
        logger.info(f"[AmazonMonitorScheduler] Manual trigger: {task}")

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            if task == "price":
                return loop.run_until_complete(self._run_price_monitor())
            elif task == "review":
                return loop.run_until_complete(self._run_review_analysis())
            else:
                return loop.run_until_complete(self._run_full_market_report())
        finally:
            loop.close()

    def _build_initial_state(self, task_type: str) -> State:
        """构建初始 State"""
        seed_keywords = self.config.get("seed_keywords", [
            "wireless earbuds",
            "bluetooth speaker",
            "phone stand",
            "laptop stand",
            "usb hub",
        ])
        state = State({
            "task_type": task_type,
            "seed_keywords": seed_keywords,
            "marketplace": self.config.get("marketplace", "www.amazon.com"),
            "started_at": datetime.now().isoformat(),
        })
        return state

    async def _run_price_monitor(self) -> Dict[str, Any]:
        """
        每小时价格监控任务
        流程：关键词扩展 → 商品采集 → 流量分析（含价格预警）
        """
        logger.info("[AmazonMonitorScheduler] === Price Monitor Start ===")
        start_time = datetime.now()

        state = self._build_initial_state("price_monitor")
        state.set("max_results_per_keyword", 5)  # 价格监控只需少量数据

        try:
            # Step 1: 关键词扩展
            state = self.keyword_expander.run(state)

            # Step 2: 商品采集
            state = self.product_collector.run(state)

            # Step 3: 流量与价格分析
            state = self.traffic_analyzer.run(state)

            # 提取价格预警
            price_alerts = state.get("price_alerts", [])
            elapsed = (datetime.now() - start_time).total_seconds()

            logger.info(
                f"[AmazonMonitorScheduler] Price monitor done: "
                f"{len(price_alerts)} alerts in {elapsed:.1f}s"
            )

            return {
                "task": "price_monitor",
                "success": True,
                "price_alerts": price_alerts,
                "products_checked": len(state.get("collected_products", [])),
                "elapsed_seconds": elapsed,
                "completed_at": datetime.now().isoformat(),
            }

        except Exception as e:
            logger.error(f"[AmazonMonitorScheduler] Price monitor failed: {e}")
            return {"task": "price_monitor", "success": False, "error": str(e)}

    async def _run_review_analysis(self) -> Dict[str, Any]:
        """
        每日评论分析任务
        流程：关键词扩展 → 商品采集 → 评论分析
        """
        logger.info("[AmazonMonitorScheduler] === Review Analysis Start ===")
        start_time = datetime.now()

        state = self._build_initial_state("review_analysis")
        state.set("max_results_per_keyword", 10)
        state.set("max_products_to_analyze", 20)

        try:
            state = self.keyword_expander.run(state)
            state = self.product_collector.run(state)
            state = self.review_analyzer.run(state)

            review_insights = state.get("review_insights", [])
            sentiment_summary = state.get("sentiment_summary", {})
            elapsed = (datetime.now() - start_time).total_seconds()

            logger.info(
                f"[AmazonMonitorScheduler] Review analysis done: "
                f"{len(review_insights)} products analyzed in {elapsed:.1f}s"
            )

            return {
                "task": "review_analysis",
                "success": True,
                "products_analyzed": len(review_insights),
                "market_sentiment": sentiment_summary.get("market_sentiment"),
                "avg_rating": sentiment_summary.get("avg_rating"),
                "elapsed_seconds": elapsed,
                "completed_at": datetime.now().isoformat(),
            }

        except Exception as e:
            logger.error(f"[AmazonMonitorScheduler] Review analysis failed: {e}")
            return {"task": "review_analysis", "success": False, "error": str(e)}

    async def _run_full_market_report(self) -> Dict[str, Any]:
        """
        每周完整市场报告任务
        流程：关键词扩展 → 商品采集 → 评论分析 → 流量分析 → 机会评估
        """
        logger.info("[AmazonMonitorScheduler] === Full Market Report Start ===")
        start_time = datetime.now()

        state = self._build_initial_state("full_market_report")
        state.set("max_results_per_keyword", 10)
        state.set("max_products_to_analyze", 20)
        state.set("min_opportunity_score", 60)
        state.set("output_top_n", 10)

        try:
            # 完整 5 步流程
            state = self.keyword_expander.run(state)
            state = self.product_collector.run(state)
            state = self.review_analyzer.run(state)
            state = self.traffic_analyzer.run(state)
            state = self.opportunity_judge.run(state)

            market_report = state.get("market_report", "")
            opportunities = state.get("opportunities", [])
            alerts = state.get("alerts", [])
            elapsed = (datetime.now() - start_time).total_seconds()

            logger.info(
                f"[AmazonMonitorScheduler] Full report done: "
                f"{len(opportunities)} opportunities, {len(alerts)} alerts in {elapsed:.1f}s"
            )

            return {
                "task": "full_market_report",
                "success": True,
                "opportunities_found": len(opportunities),
                "alerts_generated": len(alerts),
                "report_length": len(market_report),
                "elapsed_seconds": elapsed,
                "completed_at": datetime.now().isoformat(),
            }

        except Exception as e:
            logger.error(f"[AmazonMonitorScheduler] Full report failed: {e}")
            return {"task": "full_market_report", "success": False, "error": str(e)}

    def get_status(self) -> Dict[str, Any]:
        """获取调度器状态"""
        jobs = []
        if self._is_running:
            for job in self.scheduler.get_jobs():
                jobs.append({
                    "id": job.id,
                    "name": job.name,
                    "next_run_time": str(job.next_run_time),
                    "trigger": str(job.trigger),
                })

        return {
            "is_running": self._is_running,
            "jobs": jobs,
            "job_count": len(jobs),
        }


# 全局单例（可选）
_default_scheduler: Optional[AmazonMonitorScheduler] = None


def get_monitor_scheduler(config: Optional[Dict] = None) -> AmazonMonitorScheduler:
    """获取全局监控调度器单例"""
    global _default_scheduler
    if _default_scheduler is None:
        _default_scheduler = AmazonMonitorScheduler(config)
    return _default_scheduler
