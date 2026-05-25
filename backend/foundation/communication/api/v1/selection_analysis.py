"""
选品分析 API — 对标卖家精灵选品类 API
直接从 amazon_products 表查询，返回结构化数据

路由前缀: /api/v1/amazon/selection
"""
import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from backend.data.database import get_db
from backend.business.ecommerce.amazon_monitor.product_selection_service import ProductSelectionService

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/amazon/selection",
    tags=["Amazon 选品分析"],
)


def get_service(db: AsyncSession = Depends(get_db)) -> ProductSelectionService:
    return ProductSelectionService(db)


# ════════════════════════════════════════
# S1: 8 维度机会评分
# ════════════════════════════════════════


@router.get("/score-opportunities")
async def score_opportunities(
    category: Optional[str] = Query(None, description="类目名称"),
    asins: Optional[str] = Query(None, description="逗号分隔的 ASIN 列表（与 category 二选一）"),
    domain: str = Query("US"),
    min_score: int = Query(60, description="最低机会评分"),
    top_n: int = Query(20, description="返回 Top N"),
    service: ProductSelectionService = Depends(get_service),
):
    """
    8 维度机会评分

    对指定类目或 ASIN 列表做 8 维加权评分（BSR/趋势/评分/评论/销量/
    价格稳定/竞争/情感），返回 A-D 分级和评分详情。
    """
    asin_list = [a.strip() for a in asins.split(",") if a.strip()] if asins else None
    return await service.score_opportunities(category, asin_list, domain, min_score, top_n)


# ════════════════════════════════════════
# S2: 关键词扩展+搜索选品
# ════════════════════════════════════════


@router.get("/keyword-search")
async def keyword_search(
    keyword: str = Query(..., description="关键词/类目名"),
    domain: str = Query("US"),
    top_n: int = Query(20, description="返回 Top N"),
    service: ProductSelectionService = Depends(get_service),
):
    """
    关键词搜索选品

    按类目名查 amazon_products 表，返回销量排序的商品列表。
    """
    return await service.keyword_search_selection(keyword, domain, top_n=top_n)


# ════════════════════════════════════════
# S3: 多维筛选选品
# ════════════════════════════════════════


@router.get("/filter")
async def filter_products(
    domain: str = Query("US"),
    category: Optional[str] = Query(None, description="类目"),
    tier: Optional[str] = Query(None, description="Importance Tier (hot/active/passive)"),
    min_rating: Optional[float] = Query(None, ge=1, le=5),
    min_review_count: Optional[int] = Query(None, ge=0),
    min_monthly_sold: Optional[int] = Query(None, ge=0),
    min_price: Optional[float] = Query(None, ge=0),
    max_price: Optional[float] = Query(None, ge=0),
    max_bsr: Optional[int] = Query(None, ge=0),
    has_aplus: Optional[bool] = Query(None),
    is_fba: Optional[bool] = Query(None),
    sort_by: str = Query("importance_score", description="排序字段"),
    sort_desc: bool = Query(True),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    service: ProductSelectionService = Depends(get_service),
):
    """
    多维筛选选品

    按销量/BSR/评分/价格/A+/FBA 等多维度筛选商品，支持分页排序。
    """
    return await service.filter_products(
        domain=domain, category=category, tier=tier,
        min_rating=min_rating, min_review_count=min_review_count,
        min_monthly_sold=min_monthly_sold,
        min_price=min_price, max_price=max_price,
        max_bsr=max_bsr, has_aplus=has_aplus, is_fba=is_fba,
        sort_by=sort_by, sort_desc=sort_desc,
        limit=limit, offset=offset,
    )


# ════════════════════════════════════════
# S4: 关键词选品趋势
# ════════════════════════════════════════


@router.get("/keyword-trends")
async def keyword_trends(
    keyword: str = Query(..., description="关键词/类目名"),
    domain: str = Query("US"),
    top_n: int = Query(10),
    days: int = Query(90, description="历史天数"),
    service: ProductSelectionService = Depends(get_service),
):
    """
    关键词选品趋势

    类目下商品带 price_history / bsr_history 趋势数据返回。
    """
    return await service.keyword_product_trends(keyword, domain, top_n, days)


# ════════════════════════════════════════
# S5: ASIN 详情及趋势
# ════════════════════════════════════════


@router.get("/asin-detail")
async def asin_detail(
    asin: str = Query(..., description="ASIN"),
    domain: str = Query("US"),
    days: int = Query(90, description="趋势天数"),
    service: ProductSelectionService = Depends(get_service),
):
    """
    ASIN 详情及趋势

    完整详情：商品信息 + 价格/BSR 历史趋势 + 评分/评论/销量数据。
    """
    result = await service.asin_detail_with_trends(asin, domain, days)
    if result is None:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail=f"ASIN {asin} 未找到")
    return result


# ════════════════════════════════════════
# S6: ASIN 优惠趋势
# ════════════════════════════════════════


@router.get("/asin-deals")
async def asin_deals(
    asin: str = Query(..., description="ASIN"),
    domain: str = Query("US"),
    days: int = Query(90, description="分析天数"),
    service: ProductSelectionService = Depends(get_service),
):
    """
    ASIN 优惠趋势

    基于 price_history 分析：优惠频次、平均折扣、限时优惠检测。
    """
    return await service.asin_deal_trends(asin, domain, days)