"""
Amazon PAAPI 5.0 数据模型定义
"""
from typing import Optional, List, Dict, Any
from pydantic import BaseModel
from datetime import datetime


class AmazonPrice(BaseModel):
    """亚马逊商品价格信息"""
    amount: float
    currency: str = "USD"
    display_amount: str = ""
    savings: Optional[float] = None
    savings_percent: Optional[int] = None
    is_prime: bool = False


class AmazonRating(BaseModel):
    """亚马逊商品评分信息"""
    overall_rating: float = 0.0
    total_reviews: int = 0
    five_star: int = 0
    four_star: int = 0
    three_star: int = 0
    two_star: int = 0
    one_star: int = 0


class AmazonBSR(BaseModel):
    """Best Sellers Rank 信息"""
    rank: int = 0
    category: str = ""
    category_id: str = ""


class AmazonProduct(BaseModel):
    """亚马逊商品完整信息"""
    asin: str
    title: str = ""
    url: str = ""
    image_url: str = ""
    image_url_large: str = ""
    feature_bullets: List[str] = []
    description: str = ""
    price: Optional[AmazonPrice] = None
    rating: Optional[AmazonRating] = None
    bsr: Optional[AmazonBSR] = None
    brand: str = ""
    manufacturer: str = ""
    category: str = ""
    category_tree: List[Dict[str, Any]] = []
    dimensions: str = ""
    weight: str = ""
    availability: str = ""
    sales_volume: Optional[int] = None
    also_bought: List[str] = []
    also_viewed: List[str] = []
    variations: List[Dict[str, Any]] = []
    fetched_at: datetime = datetime.now()


class AmazonSearchResult(BaseModel):
    """亚马逊搜索结果"""
    total_results: int = 0
    total_pages: int = 0
    current_page: int = 1
    products: List[AmazonProduct] = []
    search_url: str = ""


class AmazonReview(BaseModel):
    """亚马逊评论摘要"""
    asin: str
    rating: AmazonRating
    review_summary: str = ""
    top_positive_review: str = ""
    top_critical_review: str = ""
    sentiment_positive_pct: float = 0.0
    sentiment_negative_pct: float = 0.0
    sentiment_neutral_pct: float = 0.0
    common_praise: List[str] = []
    common_complaints: List[str] = []
    customer_needs: List[str] = []


class AmazonPriceHistory(BaseModel):
    """亚马逊价格历史"""
    asin: str
    title: str = ""
    current_price: Optional[AmazonPrice] = None
    lowest_price_30d: Optional[float] = None
    highest_price_30d: Optional[float] = None
    average_price_30d: Optional[float] = None
    price_trend: str = ""  # "up", "down", "stable"
    price_changes: List[Dict[str, Any]] = []


class AmazonCompetitor(BaseModel):
    """竞品信息"""
    asin: str
    title: str = ""
    price: Optional[AmazonPrice] = None
    rating: Optional[AmazonRating] = None
    bsr: Optional[AmazonBSR] = None
    brand: str = ""
    estimated_monthly_sales: Optional[int] = None
    estimated_revenue: Optional[float] = None
    market_share_pct: Optional[float] = None