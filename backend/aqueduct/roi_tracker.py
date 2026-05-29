"""
获取成本 ROI 追踪

追踪每条数据的投入产出：
  投入 = 采集花费的 token/credit
  产出 = 被 Agent 查询的次数

ROI 数据用于：
  - LifecycleManager 的降级决策
  - Dashboard 展示 Top 10 高/低 ROI ASIN
"""
import logging
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class ROITracker:
    """
    ROI 追踪器（内存 + 惰性写 DB 模式）。

    查询和采集计数在内存中累积，周期性（可选）写持久化。
    现阶段提供内存查询接口，后续可扩展写 DB。
    """

    def __init__(self):
        # asin → {"query_count": int, "acq_cost": int, "last_query": ...}
        self._stats: Dict[str, Dict] = defaultdict(lambda: {"query_count": 0, "acq_cost": 0, "last_query": None})

    async def record_query(self, asin: str, source: str = ""):
        """Agent 查询数据时调用"""
        self._stats[asin]["query_count"] += 1
        self._stats[asin]["last_query"] = datetime.now(timezone.utc).isoformat()

    async def record_acquisition(self, asin: str, source: str, cost: int):
        """采集发生时调用（cost 按 asin 汇总，不按 source 分）"""
        self._stats[asin]["acq_cost"] += cost

    async def get_roi(self, asin: str) -> Dict:
        """计算某个 ASIN 的 ROI"""
        queries = self._stats[asin].get("query_count", 0)
        cost = self._stats[asin].get("acq_cost", 0)
        return {
            "asin": asin,
            "total_queries": queries,
            "total_acq_cost": cost,
            "cost_per_query": round(cost / queries, 2) if queries else None,
            "roi_score": round(queries / max(cost, 1) * 100, 1),
        }

    async def should_demote(self, asin: str, threshold: float = 10.0) -> bool:
        """判断是否该降级：每次查询成本 > threshold → 降级"""
        roi = await self.get_roi(asin)
        cpq = roi.get("cost_per_query")
        return cpq is not None and cpq > threshold

    def get_top_roi(self, n: int = 10) -> List[Dict]:
        """获取 ROI 最高的 N 个 ASIN"""
        scored = []
        for key, stats in self._stats.items():
            if stats["query_count"] > 0 and stats["acq_cost"] > 0:
                scored.append({
                    "asin": key,
                    **stats,
                    "roi_score": round(stats["query_count"] / stats["acq_cost"] * 100, 1),
                })
        scored.sort(key=lambda x: -x["roi_score"])
        return scored[:n]

    def get_lowest_roi(self, n: int = 10) -> List[Dict]:
        """获取 ROI 最低的 N 个 ASIN"""
        scored = []
        for key, stats in self._stats.items():
            if stats["query_count"] > 0 and stats["acq_cost"] > 0:
                scored.append({
                    "asin": key,
                    **stats,
                    "roi_score": round(stats["query_count"] / stats["acq_cost"] * 100, 1),
                })
        scored.sort(key=lambda x: x["roi_score"])
        return scored[:n]

    def reset(self):
        """重置所有统计"""
        self._stats.clear()


# 全局单例
roi_tracker = ROITracker()