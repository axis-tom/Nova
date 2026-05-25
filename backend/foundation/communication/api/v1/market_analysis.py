"""
市场分析 API — 对标卖家精灵市场类 API
直接从 amazon_products 表查询，返回结构化数据

路由前缀: /api/v1/amazon/market
"""
import logging
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from backend.data.database import get_db
from backend.business.ecommerce.amazon_monitor.market_analysis import MarketAnalysisService

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/amazon/market",
    tags=["Amazon 市场分析"],
)


def get_service(db: AsyncSession = Depends(get_db)) -> MarketAnalysisService:
    return MarketAnalysisService(db)


# ════════════════════════════════════════
# M1: 选市场-统计
# ════════════════════════════════════════


@router.get("/summary")
async def market_summary(
    category: Optional[str] = Query(None, description="类目名称，不传则全品类"),
    domain: str = Query("US", description="市场 US/DE/JP"),
    tier: Optional[str] = Query(None, description="Importance Tier 筛选 (hot/active/passive)"),
    brand: Optional[str] = Query(None, description="品牌名筛选"),
    service: MarketAnalysisService = Depends(get_service),
):
    """
    选市场-统计

    类目聚合统计：ASIN 数、平均 BSR/价格/评分、品牌数、卖家数、
    月销总量、营收估算、价格带分布、Tier 分布。
    """
    return await service.get_market_summary(category, domain, tier, brand)


# ════════════════════════════════════════
# M2: 商品需求趋势
# ════════════════════════════════════════


@router.get("/trend")
async def market_trend(
    category: Optional[str] = Query(None, description="类目名称"),
    domain: str = Query("US"),
    days: int = Query(90, description="分析天数"),
    service: MarketAnalysisService = Depends(get_service),
):
    """
    商品需求趋势

    基于 Keepa 时间序列的 BSR 趋势、价格趋势、市场方向、季节性分析。
    """
    return await service.get_market_trend(category, domain, days)


# ════════════════════════════════════════
# M3: 价格分布
# ════════════════════════════════════════


@router.get("/price-distribution")
async def price_distribution(
    category: Optional[str] = Query(None),
    domain: str = Query("US"),
    service: MarketAnalysisService = Depends(get_service),
):
    """
    价格分布

    价格区间分布（<$20 / $20-50 / $50-100 / $100-200 / $200+）、
    平均/中位数/最小/最大价格、Prime 比例、推荐定价区间。
    """
    return await service.get_price_distribution(category, domain)


# ════════════════════════════════════════
# M4: 品牌集中度
# ════════════════════════════════════════


@router.get("/brand-concentration")
async def brand_concentration(
    category: Optional[str] = Query(None),
    domain: str = Query("US"),
    service: MarketAnalysisService = Depends(get_service),
):
    """
    品牌集中度

    品牌市场份额排名、集中度判断（寡占/分散/竞争）、进入壁垒评估。
    """
    return await service.get_brand_concentration(category, domain)


# ════════════════════════════════════════
# M5: 评分数分布
# ════════════════════════════════════════


@router.get("/review-distribution")
async def review_distribution(
    category: Optional[str] = Query(None),
    domain: str = Query("US"),
    service: MarketAnalysisService = Depends(get_service),
):
    """
    评分数分布

    评论数区间分布、平均/中位数评论数、评论壁垒评估（极高/高/中/低）。
    """
    return await service.get_review_count_distribution(category, domain)


# ════════════════════════════════════════
# M6: 评分值分布
# ════════════════════════════════════════


@router.get("/rating-distribution")
async def rating_distribution(
    category: Optional[str] = Query(None),
    domain: str = Query("US"),
    service: MarketAnalysisService = Depends(get_service),
):
    """
    评分值分布

    评分区间分布（4-5 / 3-4 / 2-3 / 1-2）、评分健康度评分。
    """
    return await service.get_rating_distribution(category, domain)


# ════════════════════════════════════════
# M7: 商品集中度
# ════════════════════════════════════════


@router.get("/seller-distribution")
async def seller_distribution(
    category: Optional[str] = Query(None),
    domain: str = Query("US"),
    service: MarketAnalysisService = Depends(get_service),
):
    """
    商品集中度（卖家分布）

    卖家数区间分布、去重卖家数、平均卖家数。
    """
    return await service.get_product_concentration(category, domain)


# ════════════════════════════════════════
# M8: 卖家类型分布
# ════════════════════════════════════════


@router.get("/seller-type")
async def seller_type_distribution(
    category: Optional[str] = Query(None),
    domain: str = Query("US"),
    service: MarketAnalysisService = Depends(get_service),
):
    """
    卖家类型分布

    FBA / FBM / 未标记 分布比例、Prime 覆盖率。
    """
    return await service.get_seller_type_distribution(category, domain)


# ════════════════════════════════════════
# M9: A+ 视频分布
# ════════════════════════════════════════


@router.get("/aplus-video")
async def aplus_video_distribution(
    category: Optional[str] = Query(None),
    domain: str = Query("US"),
    service: MarketAnalysisService = Depends(get_service),
):
    """
    A+ 视频分布

    A+ Content 覆盖率、视频数分布（Rainforest 独家数据）。
    """
    return await service.get_aplus_video_distribution(category, domain)


# ════════════════════════════════════════
# M10: 市场报告（组合 9 个维度）
# ════════════════════════════════════════


@router.get("/report")
async def market_report(
    category: Optional[str] = Query(None, description="类目名称，不传则全品类"),
    domain: str = Query("US"),
    service: MarketAnalysisService = Depends(get_service),
):
    """
    市场报告（组合 9 个维度）

    一次性返回所有市场分析数据：统计/趋势/价格分布/品牌集中度/
    评分分布/卖家分布/卖家类型/A+视频。
    """
    return await service.get_market_report(category, domain)