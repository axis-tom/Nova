"""
Token-Budget-Aware 调度器

核心策略：
  - 每 15 分钟检查一次 Keepa 桶水位
  - 按 Freshess Score 排序，优先更新数据最旧的 ASIN
  - ASIN Tier 加权调整
  - 桶满时批量消费，桶低时只做 Rainforest/Canopy
"""

import asyncio
import logging
from datetime import datetime, timezone, timedelta
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
        self._daily_keepa_usage = 0
        self._keepa_last_run = self._now()

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
        """调度主循环"""
        try:
            logger.info("[BudgetAwareScheduler] 开始调度检查...")

            async with AsyncSessionLocal() as db:
                repo = AmazonProductRepository(db)
                keepa = KeepaConnector()

                # 1. 检查 Keepa 桶水位
                bucket_status = self._check_bucket(keepa)
                if bucket_status["error"]:
                    logger.warning(f"Keepa bucket check failed: {bucket_status['error']}")
                    bucket_level = _BUCKET_THRESHOLDS["normal_mode"] + 1
                else:
                    bucket_level = bucket_status["tokens_left"]

                # 2. 收集需要刷新的 ASIN
                sheduled = await self._collect_stale_asins(repo, bucket_level)

                # 3. 在预算内执行 ETL
                await self._execute_etl(db, sheduled, bucket_level)

                # 4. 重置日用量（跨天时）
                today = self._now().date()
                if self._keepa_last_run.date() < today:
                    self._daily_keepa_usage = 0
                self._daily_keepa_usage += sheduled.get("keepa_count", 0)
                self._keepa_last_run = self._now()

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

        返回：
        {
            "keepa": [(score, asin), ...],    # Keepa 需要
            "rainforest": [asin, ...],
            "canopy": [asin, ...],
            "keepa_count": int,
        }
        """
        # 判断 Keepa 是否可用
        keepa_available = bucket_level > _BUCKET_THRESHOLDS["protect_mode"]

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

    async def _execute_etl(
        self, db, sheduled: Dict, bucket_level: int,
    ):
        """在预算内执行 ETL"""
        # 按桶水位决定 Keepa 批量大小
        if bucket_level > _BUCKET_THRESHOLDS["burst_mode"]:
            # 桶接近满 — 消费模式
            keepa_batch = min(bucket_level - _BUCKET_THRESHOLDS["normal_mode"], len(sheduled["keepa"]))
        elif bucket_level > _BUCKET_THRESHOLDS["protect_mode"]:
            keepa_batch = min(10, len(sheduled["keepa"]))
        else:
            keepa_batch = 0

        # 提取需要执行的 ASIN
        keepa_asins = [a for _, a in sheduled["keepa"][:keepa_batch]]
        rf_asins = sheduled["rainforest"][:_MAX_PER_CYCLE["rainforest"]]
        cn_asins = sheduled["canopy"][:_MAX_PER_CYCLE["canopy"]]

        if not (keepa_asins or rf_asins or cn_asins):
            logger.info("[BudgetAwareScheduler] 本次无过期 ASIN")
            return

        # 确定本次涉及的数据源
        sources = []
        if keepa_asins:
            sources.append("keepa")
        if rf_asins:
            sources.append("rainforest")
        if cn_asins:
            sources.append("canopy")

        # 合并所有 ASIN（去重）
        all_asins = list(set(keepa_asins + rf_asins + cn_asins))

        logger.info(
            f"[BudgetAwareScheduler] 执行 ETL: "
            f"Keepa={len(keepa_asins)}, RF={len(rf_asins)}, CN={len(cn_asins)}, "
            f"桶水位={bucket_level}"
        )

        # 运行 ETL Pipeline
        pipeline = ETLPipeline(db)
        result = await pipeline.run(all_asins, sources=sources, calc_importance=True)

        logger.info(
            f"[BudgetAwareScheduler] ETL 完成: "
            f"status={result['status']}, "
            f"success={result['asins_success']}/{result['asins_total']}"
        )


# 全局单例
budget_scheduler = BudgetAwareScheduler()