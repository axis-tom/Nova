"""
Amazon 监控定时调度器
基于 APScheduler 实现三种定时任务：
  - 每小时：价格监控（Keepa Deal API + BSR 异动检测）
  - 每天凌晨2点：评论分析
  - 每周一凌晨3点：完整市场报告

Keepa 集成后新增能力：
  - 每小时：通过 Keepa Deal API 捕获价格异动商品
  - 每小时：检测已追踪 ASIN 的 BSR 趋势变化
  - 每日：更新已追踪 ASIN 的历史数据快照

使用方式：
  from backend.aqueduct.monitor_scheduler import AmazonMonitorScheduler
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
from backend.aqueduct.connectors.keepa_connector import (
    KeepaError,
    KeepaConfigError,
    KeepaQuotaError,
    KeepaRejectedError,
    KeepaNetworkError,
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
                - domain: str Keepa 市场（US/DE/JP 等）
        """
        from backend.config.config import settings as _settings
        self.config = config or {}
        self.scheduler = AsyncIOScheduler(timezone="Asia/Shanghai")
        self._is_running = False

        # 从 settings 读取 Keepa Token 控制参数（可被 config 覆盖）
        self._keepa_price_interval = self.config.get(
            "keepa_price_interval_hours",
            _settings.KEEPA_PRICE_MONITOR_INTERVAL_HOURS,
        )
        self._keepa_bsr_interval = self.config.get(
            "keepa_bsr_interval_hours",
            _settings.KEEPA_BSR_MONITOR_INTERVAL_HOURS,
        )
        self._keepa_max_keywords = self.config.get(
            "keepa_max_keywords",
            _settings.KEEPA_MAX_KEYWORDS_PER_RUN,
        )
        self._keepa_max_asins = self.config.get(
            "keepa_max_asins",
            _settings.KEEPA_MAX_ASINS_PER_QUERY,
        )
        self._keepa_deal_max = self.config.get(
            "keepa_deal_max_results",
            _settings.KEEPA_DEAL_MAX_RESULTS,
        )

        # 初始化 Agent
        self.keyword_expander = KeywordExpanderAgent()
        self.product_collector = ProductCollectorAgent()
        self.review_analyzer = AmazonReviewAnalyzerAgent()
        self.traffic_analyzer = TrafficAnalyzerAgent()
        self.opportunity_judge = OpportunityJudgeAgent()

        logger.info(
            f"[AmazonMonitorScheduler] Initialized | "
            f"Keepa 价格监控间隔={self._keepa_price_interval}h, "
            f"BSR监控间隔={self._keepa_bsr_interval}h, "
            f"最大关键词={self._keepa_max_keywords}, "
            f"最大ASIN={self._keepa_max_asins}"
        )

    def start(self):
        """
        启动调度器，注册所有定时任务
        
        调度频率由 .env 控制（Keepa Token 节省）：
          - 价格监控：每 KEEPA_PRICE_MONITOR_INTERVAL_HOURS 小时（默认6小时）
          - BSR 监控：每 KEEPA_BSR_MONITOR_INTERVAL_HOURS 小时（默认24小时，即每天）
          - 评论分析：每天凌晨2点（固定）
          - 完整报告：每周一凌晨3点（固定）
        """
        if self._is_running:
            logger.warning("[AmazonMonitorScheduler] Already running")
            return

        # 价格监控：按配置间隔执行（默认每6小时，节省 Keepa Token）
        price_interval = self._keepa_price_interval
        self.scheduler.add_job(
            func=self._run_price_monitor,
            trigger=CronTrigger(hour=f"*/{price_interval}"),
            id="amazon_price_monitor",
            name=f"Amazon 价格监控（每{price_interval}小时）",
            replace_existing=True,
            max_instances=1,
            coalesce=True,
            misfire_grace_time=300,
        )

        # BSR 趋势监控：按配置间隔执行（默认每24小时，即每天凌晨1点）
        bsr_interval = self._keepa_bsr_interval
        self.scheduler.add_job(
            func=self._run_bsr_monitor_only,
            trigger=CronTrigger(hour=1, minute=0) if bsr_interval >= 24
                    else CronTrigger(hour=f"*/{bsr_interval}"),
            id="amazon_bsr_monitor",
            name=f"Amazon BSR 趋势监控（每{bsr_interval}小时）",
            replace_existing=True,
            max_instances=1,
            coalesce=True,
            misfire_grace_time=600,
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

    async def async_trigger(self, task: str = "full") -> Dict[str, Any]:
        """
        异步手动触发任务（供 FastAPI 路由调用，避免事件循环冲突）

        Args:
            task: "price" | "review" | "full" | "bsr"

        Returns:
            执行结果
        """
        logger.info(f"[AmazonMonitorScheduler] Async trigger: {task}")
        if task == "price":
            return await self._run_price_monitor()
        elif task == "review":
            return await self._run_review_analysis()
        elif task == "bsr":
            return await self._run_bsr_monitor_only()
        else:
            return await self._run_full_market_report()

    def trigger_now(self, task: str = "full") -> Dict[str, Any]:
        """
        同步手动触发任务（供命令行/脚本调用）
        注意：在 FastAPI 环境中请使用 async_trigger()，避免事件循环冲突

        Args:
            task: "price" | "review" | "full" | "bsr"

        Returns:
            执行结果
        """
        logger.info(f"[AmazonMonitorScheduler] Sync trigger: {task}")

        try:
            # 尝试在已有事件循环中运行（Jupyter/某些环境）
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # 如果已有运行中的循环，使用 run_coroutine_threadsafe
                import concurrent.futures
                future = asyncio.run_coroutine_threadsafe(
                    self.async_trigger(task), loop
                )
                return future.result(timeout=300)
        except RuntimeError:
            pass

        # 标准同步调用：创建新事件循环
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(self.async_trigger(task))
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
        
        流程：
          1. Keepa Deal API → 捕获市场价格异动商品（降价 ≥10%）
          2. 已追踪 ASIN 的 BSR 趋势检测（Keepa Product API）
          3. 传统流量分析（PAAPI 兜底）
          
        告警类型：
          - price_drop: 价格大幅下降（竞品降价）
          - bsr_spike: BSR 突然恶化（销量下滑）
          - bsr_improve: BSR 持续改善（新机会）
        """
        logger.info("[AmazonMonitorScheduler] === Price Monitor Start ===")
        start_time = datetime.now()

        state = self._build_initial_state("price_monitor")
        state.set("max_results_per_keyword", 5)
        domain = self.config.get("domain", "US")

        all_alerts: List[Dict] = []

        try:
            # ── Step 1: Keepa Deal API 捕获价格异动 ──
            keepa_deal_alerts = await self._run_keepa_deal_monitor(domain)
            all_alerts.extend(keepa_deal_alerts)

        # ── Step 2: 已追踪 ASIN 的 BSR 趋势检测（价格监控时跳过，由独立 BSR 任务处理）──
            # 注意：BSR 监控已独立为每日任务，此处不重复调用，节省 Token
            bsr_alerts = []

            # ── Step 3: 传统流量分析（PAAPI 兜底） ──
            state = self.keyword_expander.run(state)
            state = await self.product_collector.run(state)
            state = self.traffic_analyzer.run(state)

            paapi_price_alerts = state.get("price_alerts", [])
            all_alerts.extend(paapi_price_alerts)

            elapsed = (datetime.now() - start_time).total_seconds()

            # 按严重程度分类
            high_alerts = [a for a in all_alerts if a.get("severity") == "high"]
            medium_alerts = [a for a in all_alerts if a.get("severity") == "medium"]

            logger.info(
                f"[AmazonMonitorScheduler] Price monitor done: "
                f"{len(all_alerts)} alerts (high={len(high_alerts)}, medium={len(medium_alerts)}) "
                f"in {elapsed:.1f}s"
            )

            return {
                "task": "price_monitor",
                "success": True,
                "price_alerts": all_alerts,
                "high_alerts": len(high_alerts),
                "medium_alerts": len(medium_alerts),
                "products_checked": len(state.get("collected_products", [])),
                "keepa_deal_alerts": len(keepa_deal_alerts),
                "bsr_alerts": 0,  # BSR 监控已独立为每日任务
                "elapsed_seconds": elapsed,
                "completed_at": datetime.now().isoformat(),
            }

        except Exception as e:
            logger.error(f"[AmazonMonitorScheduler] Price monitor failed: {e}")
            return {"task": "price_monitor", "success": False, "error": str(e)}

    async def _run_bsr_monitor_only(self) -> Dict[str, Any]:
        """
        独立 BSR 趋势监控任务（每天凌晨1点执行）
        仅对 watchlist_asins 做 Keepa 查询，Token 消耗最小
        """
        logger.info("[AmazonMonitorScheduler] === BSR Monitor Start ===")
        start_time = datetime.now()
        domain = self.config.get("domain", "US")
        watchlist_asins = self.config.get("watchlist_asins", [])

        if not watchlist_asins:
            logger.info("[AmazonMonitorScheduler] No watchlist_asins configured, skipping BSR monitor")
            return {"task": "bsr_monitor", "success": True, "alerts": [], "skipped": True}

        try:
            # 限制 ASIN 数量（节省 Token）
            asins_to_check = watchlist_asins[:self._keepa_max_asins]
            bsr_alerts = await self._run_keepa_bsr_monitor(asins_to_check, domain)
            elapsed = (datetime.now() - start_time).total_seconds()

            logger.info(
                f"[AmazonMonitorScheduler] BSR monitor done: "
                f"{len(bsr_alerts)} alerts for {len(asins_to_check)} ASINs in {elapsed:.1f}s"
            )
            return {
                "task": "bsr_monitor",
                "success": True,
                "alerts": bsr_alerts,
                "asins_checked": len(asins_to_check),
                "elapsed_seconds": elapsed,
                "completed_at": datetime.now().isoformat(),
            }
        except Exception as e:
            logger.error(f"[AmazonMonitorScheduler] BSR monitor failed: {e}")
            return {"task": "bsr_monitor", "success": False, "error": str(e)}

    async def _run_keepa_deal_monitor(self, domain: str = "US") -> List[Dict]:
        """
        通过 Keepa Deal API 捕获价格异动商品（1 token/次）
        返回标准化告警列表
        """
        alerts = []
        try:
            from backend.aqueduct.connectors.keepa_connector import KeepaConnector
            keepa = KeepaConnector()
            
            min_reviews = self.config.get("deal_min_reviews", 50)
            deals = await keepa.async_get_deals(
                domain=domain,
                min_rating=30,
                min_reviews=min_reviews,
                max_results=self._keepa_deal_max,  # 受 KEEPA_DEAL_MAX_RESULTS 控制
            )
            
            price_drop_threshold = self.config.get("price_drop_threshold", 15)
            
            for deal in deals:
                delta = abs(deal.get("delta_percent", 0))
                if delta >= price_drop_threshold:
                    severity = "high" if delta >= 30 else "medium"
                    alerts.append({
                        "type": "price_drop",
                        "severity": severity,
                        "source": "keepa_deal",
                        "asin": deal.get("asin"),
                        "title": deal.get("title", "")[:60],
                        "message": (
                            f"价格下降 {delta:.0f}%：${deal.get('avg_price', 0):.2f} → "
                            f"${deal.get('current_price', 0):.2f}"
                        ),
                        "data": {
                            "current_price": deal.get("current_price"),
                            "avg_price": deal.get("avg_price"),
                            "delta_percent": delta,
                            "rating": deal.get("rating"),
                            "review_count": deal.get("review_count"),
                        },
                        "created_at": datetime.now().isoformat(),
                    })
            
            logger.info(f"[AmazonMonitorScheduler] Keepa Deal: {len(alerts)} price alerts")

        except KeepaConfigError:
            logger.info("[AmazonMonitorScheduler] Keepa not configured, skipping Deal API")
        except KeepaQuotaError as e:
            logger.warning(f"[AmazonMonitorScheduler] Keepa Deal API quota exhausted: {e}")
        except KeepaRejectedError as e:
            logger.warning(f"[AmazonMonitorScheduler] Keepa Deal API rejected: {e}")
        except KeepaNetworkError as e:
            logger.warning(f"[AmazonMonitorScheduler] Keepa Deal API network error: {e}")
        except KeepaError as e:
            logger.warning(f"[AmazonMonitorScheduler] Keepa Deal API failed: {e}")
        except Exception as e:
            logger.warning(f"[AmazonMonitorScheduler] Keepa Deal API unexpected: {e}")
        
        return alerts

    async def _run_keepa_bsr_monitor(
        self,
        asins: List[str],
        domain: str = "US",
    ) -> List[Dict]:
        """
        检测已追踪 ASIN 的 BSR 趋势变化
        - BSR 趋势恶化（declining）→ 告警
        - BSR 趋势改善（improving）→ 机会通知
        """
        alerts = []
        try:
            from backend.aqueduct.connectors.keepa_connector import KeepaConnector
            keepa = KeepaConnector()
            
            products = await keepa.async_query_products(
                asins[:50],  # 最多50个
                domain=domain,
                history=True,
                stats=30,    # 最近30天统计
            )
            
            for p in products:
                asin = p.get("asin", "")
                bsr_trend = p.get("bsr_trend", "unknown")
                current_bsr = p.get("current_bsr")
                monthly_sold = p.get("monthly_sold", 0)
                
                if bsr_trend == "declining":
                    alerts.append({
                        "type": "bsr_spike",
                        "severity": "high",
                        "source": "keepa_bsr",
                        "asin": asin,
                        "title": p.get("title", "")[:60],
                        "message": (
                            f"BSR 持续恶化（当前 #{current_bsr}），"
                            f"月销量约 {monthly_sold} 件，销量下滑风险"
                        ),
                        "data": {
                            "current_bsr": current_bsr,
                            "avg_bsr_30d": p.get("avg_bsr_30d"),
                            "bsr_trend": bsr_trend,
                            "monthly_sold": monthly_sold,
                        },
                        "created_at": datetime.now().isoformat(),
                    })
                elif bsr_trend == "improving":
                    alerts.append({
                        "type": "bsr_improve",
                        "severity": "info",
                        "source": "keepa_bsr",
                        "asin": asin,
                        "title": p.get("title", "")[:60],
                        "message": (
                            f"BSR 持续改善（当前 #{current_bsr}），"
                            f"月销量约 {monthly_sold} 件，销量增长趋势"
                        ),
                        "data": {
                            "current_bsr": current_bsr,
                            "avg_bsr_30d": p.get("avg_bsr_30d"),
                            "bsr_trend": bsr_trend,
                            "monthly_sold": monthly_sold,
                        },
                        "created_at": datetime.now().isoformat(),
                    })
            
            logger.info(f"[AmazonMonitorScheduler] Keepa BSR: {len(alerts)} trend alerts for {len(asins)} ASINs")

        except KeepaConfigError:
            logger.info("[AmazonMonitorScheduler] Keepa not configured, skipping BSR monitor")
        except KeepaQuotaError as e:
            logger.warning(f"[AmazonMonitorScheduler] Keepa BSR monitor quota exhausted: {e}")
        except KeepaRejectedError as e:
            logger.warning(f"[AmazonMonitorScheduler] Keepa BSR monitor rejected: {e}")
        except KeepaNetworkError as e:
            logger.warning(f"[AmazonMonitorScheduler] Keepa BSR monitor network error: {e}")
        except KeepaError as e:
            logger.warning(f"[AmazonMonitorScheduler] Keepa BSR monitor failed: {e}")
        except Exception as e:
            logger.warning(f"[AmazonMonitorScheduler] Keepa BSR monitor unexpected: {e}")
        
        return alerts

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
            state = await self.product_collector.run(state)
            state = await self.review_analyzer.run(state)

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
            # 注意：product_collector.run() 是 async，其余 agent 是同步
            state = self.keyword_expander.run(state)
            state = await self.product_collector.run(state)
            state = await self.review_analyzer.run(state)
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
