"""
变更检测模型 — 追踪每个 ASIN 字段级变化

每次 ETL 写入前对比新旧值，有变化才写，同时记录 changelog。
"""
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import Column, Integer, String, Float, DateTime, JSON
from backend.data.database import Base

# 纳入变更追踪的字段列表
TRACKED_FIELDS = [
    "current_price", "buybox_price", "list_price",
    "avg_price_30d", "avg_price_90d",
    "current_bsr", "avg_bsr_30d", "avg_bsr_90d", "bsr_trend",
    "sales_rank_drops_30d",
    "rating", "review_count",
    "monthly_sold",
    "offer_count", "offer_count_fba", "seller_count",
    "buybox_seller_id",
    "is_in_stock",
    "fba_fee", "referral_fee_percent",
    "weekly_sold", "annual_sold",
]


class AmazonChangeLog(Base):
    """字段级变更日志表"""
    __tablename__ = "amazon_change_logs"

    id = Column(Integer, primary_key=True)
    asin = Column(String(10), index=True, nullable=False)
    domain = Column(String(10), default="US", index=True)
    field = Column(String(50), nullable=False)
    old_value = Column(JSON, nullable=True)
    new_value = Column(JSON, nullable=True)
    delta_pct = Column(Float, nullable=True)
    detected_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


def detect_changes(old: Dict[str, Any], new: Dict[str, Any],
                   tracked: Optional[List[str]] = None) -> Dict[str, Dict]:
    """
    对比新旧数据，返回变化集。

    Args:
        old: 数据库中的旧数据（ORM 转 dict）
        new: 本次 ETL 的新合并数据
        tracked: 要追踪的字段列表，默认 TRACKED_FIELDS

    Returns:
        {field: {"old": val, "new": val, "delta_pct": x, "detected_at": "..."}}
    """
    if tracked is None:
        tracked = TRACKED_FIELDS

    now = datetime.now(timezone.utc)
    changes = {}

    for field in tracked:
        old_val = old.get(field)
        new_val = new.get(field)

        # 两者都是 None → 无变化
        if old_val is None and new_val is None:
            continue

        # 其中一个为 None → 有变化
        if old_val is None or new_val is None:
            entry = {"old": old_val, "new": new_val, "detected_at": now.isoformat()}
            if old_val is not None and isinstance(old_val, (int, float)) and old_val != 0:
                entry["delta_pct"] = -100.0
            changes[field] = entry
            continue

        # 值不同 → 变化
        if old_val != new_val:
            entry = {"old": old_val, "new": new_val, "detected_at": now.isoformat()}
            if isinstance(old_val, (int, float)) and isinstance(new_val, (int, float)) and old_val != 0:
                entry["delta_pct"] = round((new_val - old_val) / abs(old_val) * 100, 1)
            changes[field] = entry

    return changes


def changes_to_log_entries(asin: str, domain: str, changes: Dict[str, Dict]) -> List[Dict]:
    """将 detect_changes 的输出转为 DB 写入条目"""
    entries = []
    for field, change in changes.items():
        entries.append({
            "asin": asin,
            "domain": domain,
            "field": field,
            "old_value": change.get("old"),
            "new_value": change.get("new"),
            "delta_pct": change.get("delta_pct"),
            "detected_at": change.get("detected_at", datetime.now(timezone.utc).isoformat()),
        })
    return entries