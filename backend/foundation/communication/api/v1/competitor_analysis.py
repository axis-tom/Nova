"""
竞品分析 API — 对标卖家精灵竞品类 API
直接从 amazon_products 表查询，返回结构化数据

路由前缀: /api/v1/amazon/competitor
"""
import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from backend.data.database import get_db
from backend.business.ecommerce.amazon_monitor.competitor_analysis import CompetitorAnalysisService

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/amazon/competitor",
    tags=["Amazon 竞品分析"],
)


def get_service(db: AsyncSession = Depends(get_db)) -> CompetitorAnalysisService:
    return CompetitorAnalysisService(db)


# ════════════════════════════════════════
# C1: 查竞品 Profile
# ════════════════════════════════════════


@router.get("/profile")
async def competitor_profile(
    asin: str = Query(..., description="ASIN"),
    domain: str = Query("US", description="市场 US/DE/JP"),
    service: CompetitorAnalysisService = Depends(get_service),
):
    """
    查竞品 Profile

    单个竞品详细 Profile 卡片：价格、BSR、评分、卖家、Listing 质量。
    """
    result = await service.get_competitor_profile(asin, domain)
    if result is None:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail=f"ASIN {asin} 未找到")
    return result


# ════════════════════════════════════════
# C2: Head-to-Head 对比
# ════════════════════════════════════════


@router.get("/compare")
async def compare_products(
    asins: str = Query(..., description="逗号分隔的 ASIN 列表"),
    domain: str = Query("US"),
    service: CompetitorAnalysisService = Depends(get_service),
):
    """
    Head-to-Head 对比

    多个 ASIN 并排对比：价格、BSR、评分、Listing 质量、定价策略等。
    """
    asin_list = [a.strip() for a in asins.split(",") if a.strip()]
    return await service.compare_products(asin_list, domain)


# ════════════════════════════════════════
# C3: 定价策略分类
# ════════════════════════════════════════


@router.get("/price-strategy")
async def price_strategy(
    asin: str = Query(..., description="ASIN"),
    domain: str = Query("US"),
    service: CompetitorAnalysisService = Depends(get_service),
):
    """
    定价策略分类

    基于 price_history 识别定价模式：稳定/持续降价/持续涨价/频繁波动/小幅调整。
    """
    return await service.classify_price_strategy(asin, domain)


# ════════════════════════════════════════
# C4: Listing 质量评分
# ════════════════════════════════════════


@router.get("/listing-quality")
async def listing_quality(
    asin: str = Query(..., description="ASIN"),
    domain: str = Query("US"),
    service: CompetitorAnalysisService = Depends(get_service),
):
    """
    Listing 质量评分

    10 分制评分基于：五点描述、图片数量、A+ Content、描述、视频。
    """
    return await service.score_listing_quality(asin, domain)


# ════════════════════════════════════════
# C5: 差异化机会识别
# ════════════════════════════════════════


@router.get("/opportunities")
async def identify_opportunities(
    category: str = Query(..., description="类目名称"),
    domain: str = Query("US"),
    service: CompetitorAnalysisService = Depends(get_service),
):
    """
    差异化机会识别

    分析品类内机会点：价格带空白、上升品牌、评分低洼竞品、Listing 质量洼地、高需求低竞争。
    """
    return await service.identify_opportunities(category, domain)


# ════════════════════════════════════════
# C6: 卖家报价详情
# ════════════════════════════════════════


@router.get("/seller-details")
async def seller_details(
    asin: str = Query(..., description="ASIN"),
    domain: str = Query("US"),
    service: CompetitorAnalysisService = Depends(get_service),
):
    """
    卖家报价详情

    展示 ASIN 的卖家数量、FBA/FBM、Buybox 竞争风险等。
    """
    return await service.get_seller_details(asin, domain)