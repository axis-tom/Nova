"""
数据质量/可信度评分

为每个字段提供 0.0~1.0 的可信度分数，Agent 据此判断数据的可靠程度。
"""
from datetime import datetime, timezone
from typing import Any, Dict, Optional

_QUALITY_SCORES = {
    # (source, hours_bucket, was_degraded) → score
    ("keepa", 0, False): 1.0,
    ("keepa", 6, False): 0.95,
    ("keepa", 24, False): 0.9,
    ("keepa", 72, False): 0.8,
    ("keepa", 168, False): 0.7,
    ("keepa", 720, False): 0.5,
    ("rainforest", 0, False): 0.95,
    ("rainforest", 6, False): 0.9,
    ("rainforest", 24, False): 0.85,
    ("rainforest", 72, False): 0.75,
    ("rainforest", 168, False): 0.65,
    ("rainforest", 720, False): 0.45,
    ("canopy", 0, False): 0.9,
    ("canopy", 6, False): 0.85,
    ("canopy", 24, False): 0.8,
    ("canopy", 72, False): 0.7,
    ("canopy", 168, False): 0.6,
    ("canopy", 720, False): 0.4,
    ("rainforest", 0, True): 0.7,     # 降级源
    ("keepa", 0, True): 0.75,         # 降级源
    ("canopy", 0, True): 0.7,         # 降级源
    ("unknown", 0, False): 0.5,
}

_CONFIDENCE_LABELS = {
    (1.0, 0.9): "high",
    (0.9, 0.7): "medium",
    (0.7, 0.4): "low",
    (0.4, 0.0): "unknown",
}


def _hours_bucket(hours: float) -> int:
    """将小时数映射到预定义桶"""
    if hours < 1:
        return 0
    if hours < 6:
        return 6
    if hours < 24:
        return 24
    if hours < 72:
        return 72
    if hours < 168:
        return 168
    return 720


def _confidence_label(score: float) -> str:
    """分数转文字标签"""
    for (hi, lo), label in _CONFIDENCE_LABELS.items():
        if hi >= score > lo:
            return label
    return "unknown"


def field_trust_score(
    field: str,
    freshness_map: Dict,
    freshness_ttl: Dict[str, int] = None,
) -> Dict[str, Any]:
    """
    计算某个字段的可信度。

    Returns:
        {"score": 0.95, "confidence": "high", "source": "keepa",
         "updated_at": "...", "freshness_hours": 2, "note": ""}
    """
    fm = freshness_map.get(field, {})
    if not isinstance(fm, dict):
        return {"score": 0.5, "confidence": "unknown", "note": "freshness_map 格式异常"}

    source = fm.get("source", "unknown")
    degraded = fm.get("degraded", False)
    updated_str = fm.get("updated_at")

    if not updated_str:
        return {"score": 0.4, "confidence": "unknown", "source": source, "note": "无时间戳"}

    try:
        updated = datetime.fromisoformat(updated_str.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return {"score": 0.4, "confidence": "unknown", "source": source, "note": "时间戳格式异常"}

    hours = (datetime.now(timezone.utc) - updated).total_seconds() / 3600
    bucket = _hours_bucket(hours)

    score = _QUALITY_SCORES.get((source, bucket, degraded), 0.5)
    confidence = _confidence_label(score)

    note = ""
    if degraded:
        note = f"降级来源"
    if hours > 168:
        note = f"{note}; 数据已超过 {(hours/24):.0f} 天".strip("; ")

    return {
        "score": score,
        "confidence": confidence,
        "source": source,
        "updated_at": updated_str,
        "freshness_hours": round(hours, 1),
        "note": note,
    }


def enrich_with_trust(
    product: Dict,
    freshness_map: Dict,
    freshness_ttl: Dict[str, int] = None,
) -> Dict:
    """
    将 product dict 的每个字段附上可信度信息。
    Agent 通过 DataProvider 获取时直接拿到可信度。
    """
    enriched = {}
    for key, value in product.items():
        if key in ("coverage_map", "freshness_map", "raw_payload", "data_source"):
            enriched[key] = value
            continue
        if key.startswith("_") or value is None:
            enriched[key] = value
            continue

        trust = field_trust_score(key, freshness_map, freshness_ttl)
        enriched[key] = {
            "value": value,
            "confidence": trust["confidence"],
            "source": trust["source"],
            "updated_at": trust["updated_at"],
            "freshness_hours": trust["freshness_hours"],
            "note": trust["note"],
        }

    # 附上整体可信度摘要
    confidences = [v.get("confidence", "unknown") for v in enriched.values() if isinstance(v, dict)]
    if confidences:
        high_ratio = confidences.count("high") / len(confidences)
        low_ratio = confidences.count("low") / len(confidences)
        if high_ratio > 0.8:
            enriched["_trust_summary"] = {"overall": "high", "high_ratio": round(high_ratio, 2)}
        elif low_ratio > 0.5:
            enriched["_trust_summary"] = {"overall": "low", "low_ratio": round(low_ratio, 2)}
        else:
            enriched["_trust_summary"] = {"overall": "medium", "high_ratio": round(high_ratio, 2)}

    return enriched