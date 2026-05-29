"""
Token-Budget-Aware 调度器

核心策略：
  - 每 15 分钟检查一次 Keepa 桶水位
  - 消费 AcquisitionQueue（DataProvider 异步刷新请求优先级最高）
  - 主动扫描过期 ASIN 并入队（背景新鲜度维护）
  - ASIN Tier 加权排序
  - 桶满时批量消费，桶低时只做 Rainforest/Canopy
"""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from backend.data.database import AsyncSessionLocal
from backend.data.repositories.postgreSQL.amazon_product_repo import AmazonProductRepository
from backend.aqueduct.connectors.keepa_connector import (
    KeepaConnector,
    KeepaQuotaError,
)
from backend.aqueduct.acquisition_queue import acquisition_queue, QueueItem
from backend.aqueduct.cost_controller import cost_controller
from backend.aqueduct.etl_pipeline import ETLPipeline

logger = logging.getLogger(__name__)

# 各源 TTL（小时）
_TTL = {
    "hot": {
        "keepa": 6,       # Hot 价格趋势每 6h
        "rainforest": 12,  # Hot 基础信息每 12h
        "canopy": 12,      # Hot 评论/评分每 12h
    },
    "active": {
        "keepa": 24,
        "rainforest": 72,
        "canopy": 48,
    },
    "passive": {
        "keepa": 72,
        "rainforest": 240,  # 10 天
        "canopy": 168,       # 7 天
    },
}

# Keepa 桶水位阈值
_BUCKET_THRESHOLDS = {
    "burst_mode": 50,    # >50 → 批量消费
    "normal_mode": 10,   # >10 → 正常更新
    "protect_mode": 10,  # ≤10 → 暂停 Keepa
}

# 各调度周期的最大处理量
_MAX_PER_CYCLE = {
    "keepa": 30,        # 每周期最多 30 个 Keepa ETL
    "rainforest": 20,
    "canopy": 30,
}

# 数据维度 → 所需 API 源映射（用于队列项 → 确定调哪些源）
_DIM_TO_SOURCES = {
    "has_price": ["keepa", "rainforest"],
    "has_buybox": ["keepa", "rainforest"],
    "has_price_stats": ["keepa"],
    "has_bsr": ["keepa"],
    "has_bsr_stats": ["keepa"],
    "has_rating_history": ["keepa"],
    "has_listing": ["rainforest"],
    "has_aplus": ["rainforest"],
    "has_videos": ["rainforest"],
    "has_reviews_body": ["rainforest", "canopy"],
    "has_rating_breakdown": ["rainforest"],
    "has_sales_estimate": ["canopy"],
    "has_stock_level": ["canopy"],
    "has_offer_counts": ["keepa", "rainforest"],
    "has_fba_fee": ["keepa"],
    "has_referral_fee": ["keepa"],
}


class BudgetAwareScheduler:
    """
    Token 预算感知型调度器

    定时运行：
      - 查 Keepa 桶水位
      - 查 amazon_products 中各 ASIN 的新鲜度
      - 按优先级排序，在预算内执行 ETL
    """

    def __init__(self):
        self.scheduler = AsyncIOScheduler()
        self._running = False

    def _now(self):
        return datetime.now(timezone.utc)

    def start(self):
        """启动调度器"""
        if self._running:
            return
        self._running = True

        # 每 15 分钟执行一次调度检查
        self.scheduler.add_job(
            self._tick,
            IntervalTrigger(minutes=15),
            id="budget_aware_tick",
            name="Token-Budget-Aware ETL 调度",
            coalesce=True,
            max_instances=1,
        )
        self.scheduler.start()
        logger.info("[BudgetAwareScheduler] 已启动，每 15 分钟执行一次调度检查")

    def stop(self):
        """停止调度器"""
        if self._running:
            self.scheduler.shutdown(wait=False)
            self._running = False
            logger.info("[BudgetAwareScheduler] 已停止")

    async def _tick(self):
        """调度主循环：消费 AcquisitionQueue + 主动发现过期 ASIN"""
        try:
            logger.info("[BudgetAwareScheduler] 开始调度检查...")

            async with AsyncSessionLocal() as db:
                repo = AmazonProductRepository(db)
                keepa = KeepaConnector()

                # 1. 检查 Keepa 桶水位 + CostController
                bucket_status = self._check_bucket(keepa)
                if bucket_status["error"]:
                    logger.warning(f"Keepa bucket check failed: {bucket_status['error']}")
                    bucket_level = _BUCKET_THRESHOLDS["normal_mode"] + 1
                else:
                    bucket_level = bucket_status["tokens_left"]

                # CostController 熔断检查
                keepa_available = (
                    bucket_level > _BUCKET_THRESHOLDS["protect_mode"]
                    and not cost_controller.should_circuit_break("keepa")
                    and await cost_controller.check_and_throttle("keepa", 1)
                )
                rf_available = (
                    not cost_controller.should_circuit_break("rainforest")
                    and await cost_controller.check_and_throttle("rainforest", 1)
                )
                cn_available = (
                    not cost_controller.should_circuit_break("canopy")
                    and await cost_controller.check_and_throttle("canopy", 1)
                )

                # 2a. 消费 AcquisitionQueue（DataProvider 异步刷新请求）
                batch_size = acquisition_queue.batch_size_by_budget(bucket_level)
                queue_items = await acquisition_queue.dequeue_batch(batch_size)

                # 2b. 主动发现过期 ASIN（背景新鲜度维护）
                stale_asins = await self._collect_stale_asins(repo, bucket_level)

                # 2c. 合并：队列项优先，去重
                queued_keys = {(i.asin, i.domain) for i in queue_items}
                for source, items in stale_asins.items():
                    if source == "keepa_count":
                        continue
                    if source == "keepa":
                        for score, asin in items:
                            if (asin, "US") not in queued_keys:
                                await acquisition_queue.enqueue(
                                    asin, priority=(-score), domain="US",
                                    dimensions=self._staleness_dims(asin, repo),
                                )
                    else:
                        for asin in items:
                            if (asin, "US") not in queued_keys:
                                await acquisition_queue.enqueue(
                                    asin, priority=2, domain="US",
                                )
                queue_items = await acquisition_queue.dequeue_batch(batch_size)

                # 3. 执行 ETL
                await self._execute_etl_from_queue(db, queue_items, bucket_level)

        except Exception as e:
            logger.error(f"[BudgetAwareScheduler] 调度异常: {e}", exc_info=True)

    def _check_bucket(self, keepa: KeepaConnector) -> Dict:
        """检查 Keepa 桶水位"""
        try:
            status = keepa.get_token_status()
            return {
                "tokens_left": status["tokens_left"],
                "refill_rate": status["refill_rate"],
                "max_tokens": status["max_tokens"],
                "error": None,
            }
        except Exception as e:
            return {"tokens_left": 0, "error": str(e)}

    async def _collect_stale_asins(
        self, repo: AmazonProductRepository, bucket_level: int,
    ) -> Dict[str, any]:
        """
        收集需要刷新的 ASIN，按优先级排列。

        通过 CostController 检查各源是否可用，已熔断/超配额的源跳过。

        返回：
        {
            "keepa": [(score, asin), ...],    # Keepa 需要
            "rainforest": [asin, ...],
            "canopy": [asin, ...],
            "keepa_count": int,
        }
        """
        keepa_available = (
            bucket_level > _BUCKET_THRESHOLDS["protect_mode"]
            and not cost_controller.should_circuit_break("keepa")
        )
        rf_available = not cost_controller.should_circuit_break("rainforest")
        cn_available = not cost_controller.should_circuit_break("canopy")

        result = {"keepa": [], "rainforest": [], "canopy": [], "keepa_count": 0}

        for tier, ttl in _TTL.items():
            for source, hours in ttl.items():
                if source == "keepa" and not keepa_available:
                    continue

                max_cycle = _MAX_PER_CYCLE.get(source, 20)
                stale = await repo.get_stale_asins(
                    source=source, max_age_hours=hours, tier=tier, limit=max_cycle,
                )

                for p in stale:
                    if source == "keepa":
                        score = p.importance_score or 50
                        if p.importance_tier == "hot":
                            score *= 3
                        elif p.importance_tier == "active":
                            score *= 1
                        else:
                            score *= 0.3
                        result["keepa"].append((score, p.asin))
                    else:
                        result[source].append(p.asin)

        # Keepa 按优先级降序排列
        result["keepa"].sort(key=lambda x: -x[0])
        result["keepa_count"] = len(result["keepa"])

        # 移除重复，优先留在 Keepa 列表
        keepa_asins = {a for _, a in result["keepa"]}
        for source in ["rainforest", "canopy"]:
            result[source] = [a for a in result[source] if a not in keepa_asins]

        return result

    def _staleness_dims(self, asin: str, repo: AmazonProductRepository) -> List[str]:
        """推断过期 ASIN 可能需要刷新的维度（基于默认 TTL）"""
        # 简化实现：返回所有需要 keepa 的维度
        # 后续 P2 cost_catalog 接入后可做精确推断
        return []

    async def _execute_etl_from_queue(
        self, db, queue_items: List[QueueItem], bucket_level: int,
    ):
        """从 AcquisitionQueue 出队执行 ETL"""
        if not queue_items:
            logger.info("[BudgetAwareScheduler] 队列为空，本次无执行项")
            return

        # 按来源分组并收集 ASIN
        keepa_asins = []
        rf_asins = []
        cn_asins = []

        for item in queue_items:
            dims = item.dimensions or []
            # 根据维度推断需要哪些源
            if not dims:
                # 无指定维度 → 全量刷新
                keepa_asins.append(item.asin)
                rf_asins.append(item.asin)
                cn_asins.append(item.asin)
            else:
                for dim in dims:
                    sources = _DIM_TO_SOURCES.get(dim, ["keepa"])
                    for s in sources:
                        if s == "keepa" and item.asin not in keepa_asins:
                            keepa_asins.append(item.asin)
                        elif s == "rainforest" and item.asin not in rf_asins:
                            rf_asins.append(item.asin)
                        elif s == "canopy" and item.asin not in cn_asins:
                            cn_asins.append(item.asin)

        # Keepa 按桶水位限速
        if bucket_level > _BUCKET_THRESHOLDS["burst_mode"]:
            keepa_batch_size = min(bucket_level - _BUCKET_THRESHOLDS["normal_mode"], len(keepa_asins))
        elif bucket_level > _BUCKET_THRESHOLDS["protect_mode"]:
            keepa_batch_size = min(10, len(keepa_asins))
        else:
            keepa_batch_size = 0

        keepa_asins = keepa_asins[:keepa_batch_size]
        rf_asins = rf_asins[:_MAX_PER_CYCLE["rainforest"]]
        cn_asins = cn_asins[:_MAX_PER_CYCLE["canopy"]]

        if not (keepa_asins or rf_asins or cn_asins):
            logger.info("[BudgetAwareScheduler] 预算内无可用 ASIN 执行")
            # 队列项放回（优先级降低）
            for item in queue_items:
                await acquisition_queue.enqueue(
                    item.asin, priority=item.priority + 1,
                    domain=item.domain, dimensions=item.dimensions,
                )
            return

        # 确定本次涉及的数据源
        sources = []
        if keepa_asins and not cost_controller.should_circuit_break("keepa"):
            sources.append("keepa")
        if rf_asins and not cost_controller.should_circuit_break("rainforest"):
            sources.append("rainforest")
        if cn_asins and not cost_controller.should_circuit_break("canopy"):
            sources.append("canopy")

        # 合并所有 ASIN（去重）
        all_asins = list(set(keepa_asins + rf_asins + cn_asins))

        logger.info(
            f"[BudgetAwareScheduler] 执行 ETL（队列模式）: "
            f"Keepa={len(keepa_asins)}, RF={len(rf_asins)}, CN={len(cn_asins)}, "
            f"桶水位={bucket_level}"
        )

        pipeline = ETLPipeline(db)
        result = await pipeline.run(all_asins, sources=sources, calc_importance=True)

        # 记录成本消耗到 CostController
        keepa_cost = result.get("keepa_consumed", 0)
        rf_cost = result.get("rainforest_consumed", 0)
        cn_cost = result.get("canopy_consumed", 0)
        if keepa_cost:
            await cost_controller.record_usage("keepa", keepa_cost)
        if rf_cost:
            await cost_controller.record_usage("rainforest", rf_cost)
        if cn_cost:
            await cost_controller.record_usage("canopy", cn_cost)

        # 成功/失败 → 通知 CostController（用于熔断判断）
        for source in sources:
            await cost_controller.record_success(source)

        # 未成功处理的 ASIN 重新入队
        failed = result.get("asins_failed", [])
        if failed:
            for asin in failed:
                await acquisition_queue.enqueue(asin, priority=3, domain="US")
                logger.info(f"[BudgetAwareScheduler] {asin} 失败，重入队列")

        logger.info(
            f"[BudgetAwareScheduler] ETL 完成: "
            f"status={result['status']}, "
            f"success={result['asins_success']}/{result['asins_total']}, "
            f"queued_items={len(queue_items)}"
        )


# 全局单例
budget_scheduler = BudgetAwareScheduler()