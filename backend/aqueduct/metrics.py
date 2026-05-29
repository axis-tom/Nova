"""
可观测性 — Aqueduct 内置 Prometheus 指标

跟踪：
  - API 调用计数/延迟/成功率
  - 队列深度
  - Token 消耗
  - 数据覆盖度
  - ETL 耗时
"""
import logging
from functools import wraps
from typing import Callable, Optional

from prometheus_client import Counter, Histogram, Gauge, generate_latest, REGISTRY

logger = logging.getLogger(__name__)

# ── Prometheus 指标 ────────────────────────────────────────────────

api_calls_total = Counter(
    "aqueduct_api_calls_total",
    "Total API calls by source and endpoint",
    ["source", "endpoint", "status"],
)

api_call_duration = Histogram(
    "aqueduct_api_call_seconds",
    "API call latency by source",
    ["source"],
    buckets=(0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0),
)

token_remaining = Gauge(
    "aqueduct_keepa_tokens_remaining",
    "Keepa tokens left in bucket",
)

coverage_ratio = Gauge(
    "aqueduct_coverage_ratio",
    "Data coverage ratio by dimension",
    ["dimension"],
)

acquisition_queue_depth = Gauge(
    "aqueduct_queue_depth",
    "Number of ASINs waiting in acquisition queue",
)

etl_run_duration = Histogram(
    "aqueduct_etl_run_seconds",
    "ETL pipeline run duration",
    buckets=(1, 5, 15, 30, 60, 120, 300),
)

etl_asins_processed = Counter(
    "aqueduct_etl_asins_processed_total",
    "Total ASINs processed by ETL",
    ["status"],
)

# ── 结构化日志 ──────────────────────────────────────────────────────

_STRUCTURED_LOGGER = logging.getLogger("aqueduct.structured")


def structured_log(event: str, **kwargs):
    """输出结构化日志"""
    parts = [f"[{event}]"]
    for k, v in kwargs.items():
        parts.append(f"{k}={v}")
    _STRUCTURED_LOGGER.info(" ".join(parts))


# ── 指标装饰器 ──────────────────────────────────────────────────────

def monitor_api_call(source: str, endpoint: str):
    """装饰器：自动记录 API 调用计数和延迟"""
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            with api_call_duration.labels(source=source).time():
                try:
                    result = await func(*args, **kwargs)
                    api_calls_total.labels(source=source, endpoint=endpoint, status="success").inc()
                    return result
                except Exception as e:
                    api_calls_total.labels(source=source, endpoint=endpoint, status="error").inc()
                    raise
        return wrapper
    return decorator


# ── 指标暴露 ────────────────────────────────────────────────────────

def get_metrics() -> bytes:
    """获取 Prometheus 格式的指标文本"""
    return generate_latest(REGISTRY)