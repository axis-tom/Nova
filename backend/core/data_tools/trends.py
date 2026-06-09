"""
趋势解析器 — JSON 历史字段 → 时序数据

amazon_products 中的历史字段存储为 JSON 数组：
  price_history: [[timestamp_epoch, price], [ts, price], ...]
  bsr_history:   [[timestamp_epoch, bsr], ...]
  rating_history/review_count_history: 同上

本模块将这些 JSON 原始数据解析为 LLM 可读的时序文本。
"""

import json
from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime, timezone


# ── 历史字段名 → 友好标签 ──
HISTORY_FIELDS = {
    "price_history": "价格",
    "bsr_history": "BSR",
    "rating_history": "评分",
    "review_count_history": "评论数",
}


def is_history_field(metric_name: str) -> bool:
    """判断是否历史序列字段"""
    return metric_name.lower().strip() in HISTORY_FIELDS


def parse_timestamp_series(
    raw: Any,
    field_name: str,
    max_points: int = 90,
) -> List[Dict[str, Any]]:
    """
    解析 JSON 历史时间序列

    Args:
        raw: 数据库中的 JSON 值（list of [ts, value] 或 None）
        field_name: 字段名（用于格式化）
        max_points: 最大返回数据点数

    Returns:
        时序数据列表：[{"timestamp": "2026-05-01", "value": 25.99}, ...]
        数据点按时间升序排列
    """
    if not raw:
        return []

    # 解析 JSON（可能已是 Python list，可能是 str）
    if isinstance(raw, str):
        try:
            data = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return []
    elif isinstance(raw, list):
        data = raw
    else:
        return []

    if not isinstance(data, list) or not data:
        return []

    points = []
    for item in data:
        if not isinstance(item, (list, tuple)) or len(item) < 2:
            continue

        ts, value = item[0], item[1]

        if value is None:
            continue

        # 时间戳：优先用 unix epoch 秒，否则尝试 ISO 字符串
        if isinstance(ts, (int, float)):
            try:
                dt = datetime.fromtimestamp(ts / 1000 if ts > 1e12 else ts, tz=timezone.utc)
                ts_str = dt.strftime("%Y-%m-%d")
            except (OSError, ValueError, OverflowError):
                ts_str = str(ts)
        else:
            ts_str = str(ts)

        # 数值格式化
        if isinstance(value, float):
            if field_name in ("price_history",):
                val_str = f"${value:.2f}"
            elif field_name in ("rating_history",):
                val_str = f"{value:.2f}"
            else:
                val_str = f"{value:.1f}"
        else:
            val_str = str(value)

        points.append({
            "timestamp": ts_str,
            "value": value,
            "value_display": val_str,
            "date": dt.strftime("%Y-%m-%d") if isinstance(ts, (int, float)) else str(ts),
        })

    # 按时间排序（去重，按 val 降序）
    points.sort(key=lambda p: p["timestamp"])

    # 去重（相同 timestamp 保留最新的）
    seen_ts = set()
    deduped = []
    for p in points:
        if p["timestamp"] not in seen_ts:
            seen_ts.add(p["timestamp"])
            deduped.append(p)

    # 截断
    if len(deduped) > max_points:
        # 均匀采样：保留首尾 + 中间等距
        step = len(deduped) / max_points
        sampled = [deduped[0]]
        for i in range(1, max_points - 1):
            idx = int(i * step)
            if idx < len(deduped):
                sampled.append(deduped[idx])
        sampled.append(deduped[-1])
        deduped = sampled

    return deduped


def format_trend_text(
    field_name: str,
    points: List[Dict[str, Any]],
    entity_id: str,
) -> str:
    """
    将时序数据格式化为 LLM 可读文本

    Args:
        field_name: 原始字段名
        points: parse_timestamp_series 的输出
        entity_id: ASIN 等实体标识

    Returns:
        格式化的趋势文本
    """
    label = HISTORY_FIELDS.get(field_name, field_name)
    if not points:
        return f"[{entity_id}] {label}: 无历史数据"

    # 计算趋势摘要
    values = [p["value"] for p in points if p["value"] is not None]
    if len(values) >= 2:
        first_val, last_val = values[0], values[-1]
        direction = ""
        if isinstance(first_val, (int, float)) and isinstance(last_val, (int, float)):
            if field_name in ("bsr_history",):
                # BSR 越小越好
                if last_val < first_val:
                    direction = "📈 改善（BSR 下降）"
                elif last_val > first_val:
                    direction = "📉 恶化（BSR 上升）"
                else:
                    direction = "➡️ 持平"
            elif field_name in ("price_history",):
                if last_val < first_val:
                    direction = "📉 下降"
                elif last_val > first_val:
                    direction = "📈 上涨"
                else:
                    direction = "➡️ 持平"
            else:
                if last_val > first_val:
                    direction = "📈 上升"
                elif last_val < first_val:
                    direction = "📉 下降"
                else:
                    direction = "➡️ 持平"
    else:
        direction = ""

    lines = [f"[{entity_id}] {label} 趋势 {direction}"]
    lines.append(f"  {len(points)} 个数据点 | 范围: {points[0]['timestamp']} ~ {points[-1]['timestamp']}")

    # 展示关键转折点（只显示部分点防止 token 爆炸）
    display_count = min(len(points), 20)
    shown_points = points
    if len(points) > display_count:
        # 保留首尾 + 等距采样中间
        step = (len(points) - 2) / (display_count - 2) if display_count > 2 else 1
        idxs = {0, len(points) - 1}
        for i in range(1, display_count - 1):
            idxs.add(int(i * step))
        shown_points = [points[i] for i in sorted(idxs)]

    for p in shown_points:
        lines.append(f"  {p['date']}: {p['value_display']}")

    return "\n".join(lines)


def batch_format_trends(
    field_name: str,
    points_by_entity: Dict[str, List[Dict[str, Any]]],
) -> str:
    """
    批量格式化多个实体的趋势

    Args:
        field_name: 字段名
        points_by_entity: {entity_id: [points, ...]}

    Returns:
        完整趋势文本
    """
    parts = []
    for entity_id, points in points_by_entity.items():
        text = format_trend_text(field_name, points, entity_id)
        parts.append(text)
    return "\n\n".join(parts)