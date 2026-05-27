"""
Amazon API 工具封装
为 amazon_monitor 场景提供统一的 Amazon PAAPI 访问接口
从 .env 读取凭证，创建并缓存客户端实例
"""
import os
from typing import Optional
from functools import lru_cache

from backend.connectors.amazon.client import AmazonPAAPIClient
from backend.connectors.amazon.product_search import AmazonProductSearch
from backend.connectors.amazon.product_detail import AmazonProductDetail
from backend.connectors.amazon.review_analyzer import AmazonReviewAnalyzer
from backend.connectors.amazon.price_tracker import AmazonPriceTracker
from backend.utils.logger import logger


def _get_env(key: str, default: str = "") -> str:
    """从环境变量或 .env 文件读取配置"""
    val = os.environ.get(key, default)
    if not val:
        # 尝试从 backend/config/.env 读取
        try:
            from backend.config.config import settings
            val = getattr(settings, key, default) or default
        except Exception:
            pass
    return val


def create_amazon_client(
    access_key: Optional[str] = None,
    secret_key: Optional[str] = None,
    associate_tag: Optional[str] = None,
    partner_type: Optional[str] = None,
    marketplace: Optional[str] = None,
    max_retry: Optional[int] = None,
    cache_ttl_hours: Optional[int] = None,
) -> AmazonPAAPIClient:
    """
    创建 Amazon PAAPI 客户端
    优先使用传入参数，否则从环境变量读取
    """
    _access_key = access_key or _get_env("AMAZON_ACCESS_KEY")
    _secret_key = secret_key or _get_env("AMAZON_SECRET_KEY")
    _associate_tag = associate_tag or _get_env("AMAZON_ASSOCIATE_TAG")
    _partner_type = partner_type or _get_env("AMAZON_PARTNER_TYPE", "Associates")
    _marketplace = marketplace or _get_env("AMAZON_MARKETPLACE", "www.amazon.com")
    _max_retry = max_retry or int(_get_env("AMAZON_MAX_RETRY", "3"))
    _cache_ttl = cache_ttl_hours or int(_get_env("AMAZON_CACHE_TTL_HOURS", "24"))

    if not _access_key or not _secret_key or not _associate_tag:
        logger.warning(
            "[AmazonAPI] Missing credentials! "
            "Please set AMAZON_ACCESS_KEY, AMAZON_SECRET_KEY, AMAZON_ASSOCIATE_TAG in .env"
        )

    client = AmazonPAAPIClient(
        access_key=_access_key,
        secret_key=_secret_key,
        associate_tag=_associate_tag,
        partner_type=_partner_type,
        marketplace=_marketplace,
        max_retry=_max_retry,
        cache_ttl_hours=_cache_ttl,
    )

    logger.info(
        f"[AmazonAPI] Client created: marketplace={_marketplace}, "
        f"associate_tag={_associate_tag[:8]}..."
    )
    return client


# 模块级单例客户端（懒加载）
_default_client: Optional[AmazonPAAPIClient] = None
_default_searcher: Optional[AmazonProductSearch] = None
_default_detail: Optional[AmazonProductDetail] = None
_default_review_analyzer: Optional[AmazonReviewAnalyzer] = None
_default_price_tracker: Optional[AmazonPriceTracker] = None


def get_default_client() -> AmazonPAAPIClient:
    """获取默认客户端（单例）"""
    global _default_client
    if _default_client is None:
        _default_client = create_amazon_client()
    return _default_client


def get_product_search(client: Optional[AmazonPAAPIClient] = None) -> AmazonProductSearch:
    """获取商品搜索器"""
    global _default_searcher
    if client is not None:
        return AmazonProductSearch(client)
    if _default_searcher is None:
        _default_searcher = AmazonProductSearch(get_default_client())
    return _default_searcher


def get_product_detail(client: Optional[AmazonPAAPIClient] = None) -> AmazonProductDetail:
    """获取商品详情查询器"""
    global _default_detail
    if client is not None:
        return AmazonProductDetail(client)
    if _default_detail is None:
        _default_detail = AmazonProductDetail(get_default_client())
    return _default_detail


def get_review_analyzer(client: Optional[AmazonPAAPIClient] = None) -> AmazonReviewAnalyzer:
    """获取评论分析器"""
    global _default_review_analyzer
    if client is not None:
        return AmazonReviewAnalyzer(client)
    if _default_review_analyzer is None:
        _default_review_analyzer = AmazonReviewAnalyzer(get_default_client())
    return _default_review_analyzer


def get_price_tracker(client: Optional[AmazonPAAPIClient] = None) -> AmazonPriceTracker:
    """获取价格追踪器"""
    global _default_price_tracker
    if client is not None:
        return AmazonPriceTracker(client)
    if _default_price_tracker is None:
        _default_price_tracker = AmazonPriceTracker(get_default_client())
    return _default_price_tracker


def reset_clients():
    """重置所有单例客户端（用于测试或重新配置）"""
    global _default_client, _default_searcher, _default_detail
    global _default_review_analyzer, _default_price_tracker
    _default_client = None
    _default_searcher = None
    _default_detail = None
    _default_review_analyzer = None
    _default_price_tracker = None
    logger.info("[AmazonAPI] All clients reset")
