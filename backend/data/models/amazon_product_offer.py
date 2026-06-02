"""
Amazon 产品 Offer 子表模型

每个 ASIN+domain 对应 N 条 offer（Keepa offers=20 参数触发）。
支撑 #03 #13 #21 #24 #28 #30 等分析方向。
"""
from sqlalchemy import Column, Integer, String, Boolean, DateTime, JSON, Float, Index, Text
from backend.data.database import Base


class AmazonProductOffer(Base):
    """亚马逊商品 Offer 子表 — 每个 seller 一条记录"""
    __tablename__ = "amazon_product_offers"

    id = Column(Integer, primary_key=True)
    asin = Column(String(10), nullable=False, index=True)
    domain = Column(String(10), default="US", index=True)

    # offer 基本信息
    seller_id = Column(String(50), nullable=False)
    seller_name = Column(String(200), nullable=True)
    seller_link = Column(String(500), nullable=True)
    seller_rating = Column(Float, nullable=True)
    seller_ratings_total = Column(Integer, nullable=True)
    seller_ratings_total_percentage = Column(Float, nullable=True)
    price = Column(Float, nullable=True)
    shipping = Column(Float, nullable=True)
    condition = Column(String(50), nullable=True)       # 1=new, 2=used-like-new, etc.
    is_amazon = Column(Boolean, default=False)
    is_fba = Column(Boolean, default=False)
    is_prime = Column(Boolean, default=False)
    is_prime_exclusive = Column(Boolean, default=False)
    is_preorder = Column(Boolean, default=False)
    is_warehouse_deal = Column(Boolean, default=False)
    is_shippable = Column(Boolean, default=True)
    is_map = Column(Boolean, default=False)
    min_order_qty = Column(Integer, default=1)
    max_order_qty = Column(Integer, nullable=True)
    ships_from_china = Column(Boolean, default=False)
    buybox_winner = Column(Boolean, default=False)
    availability = Column(String(100), nullable=True)
    rating = Column(Float, nullable=True)
    review_count = Column(Integer, nullable=True)
    promotion = Column(JSON, nullable=True)
    import_fee = Column(Float, nullable=True)
    offer_asin = Column(String(10), nullable=True)
    position = Column(Integer, nullable=True)
    undeliverable = Column(Boolean, default=False)
    undeliverable_message = Column(String(500), nullable=True)

    # 时间信息
    last_seen = Column(DateTime(timezone=True), nullable=True)
    last_stock_update = Column(DateTime(timezone=True), nullable=True)

    # 历史
    offer_csv = Column(JSON, nullable=True)  # 价格库存时间序列（Keepa offers 原始）

    __table_args__ = (
        Index("idx_offer_asin_domain", "asin", "domain"),
        Index("idx_offer_seller", "seller_id"),
    )