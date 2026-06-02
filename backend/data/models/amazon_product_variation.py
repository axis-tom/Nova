"""
Amazon 产品 Variation 子表模型

每个 ASIN+domain 对应 N 条变体记录。
支撑 #02 #18 #26 等分析方向。
"""
from sqlalchemy import Column, Integer, String, Boolean, JSON, Index, Float
from backend.data.database import Base


class AmazonProductVariation(Base):
    """亚马逊商品变体子表 — 每个变体一条记录"""
    __tablename__ = "amazon_product_variations"

    id = Column(Integer, primary_key=True)
    asin = Column(String(10), nullable=False, index=True)          # 父体/主体
    domain = Column(String(10), default="US", index=True)
    variant_asin = Column(String(10), nullable=False)

    # 变体信息
    title = Column(String(500), nullable=True)
    is_current = Column(Boolean, default=False)  # 是否当前产品
    attributes = Column(JSON, nullable=True)      # [{dimension, value}, ...]
    image = Column(String(500), nullable=True)
    price = Column(Float, nullable=True)
    rating = Column(Float, nullable=True)
    review_count = Column(Integer, nullable=True)
    is_prime = Column(Boolean, default=False)
    is_fba = Column(Boolean, default=False)
    is_in_stock = Column(Boolean, default=True)
    availability = Column(String(100), nullable=True)
    format_ = Column(String(50), nullable=True)  # 变体格式（如 Audio CD）
    price_only_in_cart = Column(Boolean, default=False)  # 价格是否仅购物车显示

    __table_args__ = (
        Index("idx_var_asin_domain", "asin", "domain"),
        Index("idx_var_variant", "variant_asin"),
    )