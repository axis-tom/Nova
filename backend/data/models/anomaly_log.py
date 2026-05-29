"""
异常检测模型 — 追踪数据剧烈变化事件

ETL 时对比新旧值 → 超阈值 → 写入异常事件。
"""
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import Column, Integer, String, Float, DateTime, JSON, Text
from backend.data.database import Base


# 各字段的异常阈值
ANOMALY_THRESHOLDS = {
    "current_price": {"delta_pct": 30},       # 价格变化 >30%
    "buybox_price": {"delta_pct": 30},
    "list_price": {"delta_pct": 30},
    "current_bsr": {"delta_pct": 200},        # BSR 翻 3 倍
    "avg_bsr_30d": {"delta_pct": 200},
    "avg_bsr_90d": {"delta_pct": 200},
    "review_count": {"delta_pct": 50},        # 评论数变化 >50%
    "rating": {"delta_abs": 0.5},             # 评分变化 >0.5
    "monthly_sold": {"delta_pct": 50},        # 销量变化 >50%
    "weekly_sold": {"delta_pct": 50},
    "annual_sold": {"delta_pct": 50},
    "offer_count": {"delta_pct": 50},         # Offer 数变化 >50%
    "seller_count": {"delta_pct": 50},
    "fba_fee": {"delta_pct": 30},             # FBA 费用变化 >30%
}


class AmazonAnomalyLog(Base):
    """数据异常事件表"""
    __tablename__ = "amazon_anomaly_logs"

    id = Column(Integer, primary_key=True)
    asin = Column(String(10), index=True, nullable=False)
    domain = Column(String(10), default="US", index=True)
    field = Column(String(50), nullable=False)
    old_value = Column(JSON, nullable=True)
    new_value = Column(JSON, nullable=True)
    delta_pct = Column(Float, nullable=True)
    alert_type = Column(String(50), nullable=False, default="threshold_breach")
    severity = Column(String(20), nullable=False, default="info")  # info / warning / critical
    description = Column(Text, nullable=True)
    detected_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


def detect_anomalies(changes: Dict[str, Dict],
                     thresholds: Optional[Dict] = None) -> List[Dict]:
    """
    从变更集中检测异常事件。

    Args:
        changes: detect_changes() 的返回值 {field: {old, new, delta_pct, ...}}
        thresholds: 阈值配置，默认 ANOMALY_THRESHOLDS

    Returns:
        [{field, old_value, new_value, delta_pct, alert_type, severity, description}, ...]
    """
    if thresholds is None:
        thresholds = ANOMALY_THRESHOLDS

    alerts = []
    for field, change in changes.items():
        threshold = thresholds.get(field, {})
        delta_pct = change.get("delta_pct", 0) or 0
        delta_abs = abs(
            (change.get("new", 0) or 0) - (change.get("old", 0) or 0)
        )
        old_val = change.get("old")
        new_val = change.get("new")
        description = ""

        # 阈值判断
        triggered = False

        # delta_pct 超过阈值
        if delta_pct and abs(delta_pct) >= threshold.get("delta_pct", 9999):
            triggered = True
            if delta_pct > 0:
                description = f"{field} 上涨 {delta_pct}% (旧={old_val}, 新={new_val})"
            else:
                description = f"{field} 下跌 {abs(delta_pct)}% (旧={old_val}, 新={new_val})"

        # delta_abs 超过阈值（用于 rating 等）
        if delta_abs >= threshold.get("delta_abs", 9999):
            triggered = True
            description = f"{field} 变化 {delta_abs} (旧={old_val}, 新={new_val})"

        if triggered:
            # 严重程度分级
            severity = "info"
            if abs(delta_pct or 0) >= (threshold.get("delta_pct", 100) * 2) \
               or delta_abs >= (threshold.get("delta_abs", 100) * 2):
                severity = "critical"
            elif abs(delta_pct or 0) >= threshold.get("delta_pct", 100) \
                 or delta_abs >= threshold.get("delta_abs", 100):
                severity = "warning"

            alerts.append({
                "field": field,
                "old_value": old_val,
                "new_value": new_val,
                "delta_pct": delta_pct,
                "alert_type": "threshold_breach",
                "severity": severity,
                "description": description,
            })

    return alerts