"""
Amazon 产品数据模型 — 12 语义组全覆盖版

设计原则：
  - 所有表使用 (asin, domain) 复合键，支持多站点
  - 每个语义组标注支持的分析方向编号（#xx）
  - domain 解决多域问题：US 行有 US 专有字段，DE 行对应 NULL
"""
from sqlalchemy import Column, Integer, String, Boolean, DateTime, JSON, Text, Float, BigInteger, Index, UniqueConstraint
from sqlalchemy.sql import func
from backend.data.database import Base


class AmazonProduct(Base):
    """亚马逊商品统一数据表 — 12 语义组全覆盖"""
    __tablename__ = "amazon_products"

    id = Column(Integer, primary_key=True, index=True)

    # ═══════════════════════════════════════════════════════════════
    # Group 1: 基础标识 (8列)  #01 #02 #18 #19 #33
    # ═══════════════════════════════════════════════════════════════
    asin = Column(String(10), nullable=False, index=True)
    domain = Column(String(10), nullable=False, default="US", index=True)
    parent_asin = Column(String(10), nullable=True, index=True)
    child_asins = Column(JSON, nullable=True)  # 子 ASIN 列表
    product_type = Column(String(50), nullable=True)  # STANDARD/VARIATION_PARENT/VARIATION_CHILD
    product_type_name = Column(String(50), nullable=True)  # Keepa type 的文本描述
    link = Column(String(500), nullable=True)  # 商品页面链接

    # ═══════════════════════════════════════════════════════════════
    # Group 2: Listing 内容 (36列)
    # #02 #06 #11 #18 #22 #26 #27 #32
    # ═══════════════════════════════════════════════════════════════
    title = Column(String(500), nullable=True)
    brand = Column(String(200), nullable=True)
    brand_store = Column(JSON, nullable=True)  # {name, url, url_name}
    brand_store_name = Column(String(200), nullable=True)
    brand_store_url = Column(String(500), nullable=True)
    sub_title = Column(JSON, nullable=True)  # {text, link}
    feature_bullets = Column(JSON, nullable=True)
    feature_bullets_count = Column(Integer, nullable=True)
    description = Column(Text, nullable=True)
    specifications = Column(JSON, nullable=True)  # [{name, value}, ...]
    specifications_flat = Column(Text, nullable=True)
    aplus_content = Column(JSON, nullable=True)
    whats_in_the_box = Column(JSON, nullable=True)
    main_image = Column(String(500), nullable=True)
    images = Column(JSON, nullable=True)
    images_count = Column(Integer, nullable=True)
    videos_count = Column(Integer, nullable=True)
    videos = Column(JSON, nullable=True)
    dimensions = Column(String(200), nullable=True)
    shipping_weight = Column(String(100), nullable=True)
    color = Column(String(100), nullable=True)
    size = Column(String(100), nullable=True)
    style = Column(String(100), nullable=True)
    material = Column(String(200), nullable=True)
    weight = Column(String(100), nullable=True)
    item_weight_g = Column(Integer, nullable=True)  # Keepa 克数
    item_height_mm = Column(Integer, nullable=True)
    item_length_mm = Column(Integer, nullable=True)
    item_width_mm = Column(Integer, nullable=True)
    package_weight_g = Column(Integer, nullable=True)
    package_dimensions_mm = Column(JSON, nullable=True)  # [L, W, H]
    package_quantity = Column(Integer, nullable=True)
    rich_product_description = Column(JSON, nullable=True)
    keywords_list = Column(JSON, nullable=True)
    url_slug = Column(String(500), nullable=True)
    search_alias = Column(String(200), nullable=True)
    unit_count = Column(JSON, nullable=True)  # {unitType, unitValue}
    unit_count_type = Column(String(50), nullable=True)
    unit_count_value = Column(Integer, nullable=True)
    number_of_items = Column(Integer, nullable=True)
    has_size_guide = Column(Boolean, nullable=True, default=False)
    has_360_view = Column(Boolean, nullable=True, default=False)

    # ═══════════════════════════════════════════════════════════════
    # Group 3: 商业-价格 (19列)
    # #01 #05 #08 #09 #10 #12 #19 #29 #33
    # ═══════════════════════════════════════════════════════════════
    current_price = Column(Float, nullable=True)
    currency = Column(String(10), nullable=True, default="USD")
    list_price = Column(Float, nullable=True)
    buybox_price = Column(Float, nullable=True)
    avg_price_30d = Column(Float, nullable=True)
    avg_price_90d = Column(Float, nullable=True)
    avg_price_180d = Column(Float, nullable=True)
    avg_price_365d = Column(Float, nullable=True)
    min_price_30d = Column(Float, nullable=True)
    min_price_90d = Column(Float, nullable=True)
    min_price_180d = Column(Float, nullable=True)
    max_price_90d = Column(Float, nullable=True)
    max_price_180d = Column(Float, nullable=True)
    is_lowest_price = Column(Boolean, nullable=True)
    buybox_is_amazon = Column(Boolean, nullable=True)
    buybox_is_prime_eligible = Column(Boolean, nullable=True)
    buybox_shipping = Column(Float, nullable=True)
    has_coupon = Column(Boolean, nullable=True, default=False)
    unit_price = Column(String(100), nullable=True)  # e.g. "$10.99/kg"

    # ═══════════════════════════════════════════════════════════════
    # Group 4: 商业-BSR (18列)
    # #01 #02 #09 #14 #19 #20 #33
    # ═══════════════════════════════════════════════════════════════
    current_bsr = Column(Integer, nullable=True)
    bsr_category = Column(String(200), nullable=True)
    bsr_category_id = Column(Integer, nullable=True)
    avg_bsr_30d = Column(Float, nullable=True)
    avg_bsr_90d = Column(Float, nullable=True)
    avg_bsr_180d = Column(Float, nullable=True)
    avg_bsr_365d = Column(Float, nullable=True)
    bsr_trend = Column(String(20), nullable=True)
    sales_rank_drops_30d = Column(Integer, nullable=True)
    sales_rank_drops_90d = Column(Integer, nullable=True)
    sales_rank_drops_180d = Column(Integer, nullable=True)
    sales_rank_drops_365d = Column(Integer, nullable=True)
    sales_rank_reference_id = Column(Integer, nullable=True)
    root_category_id = Column(Integer, nullable=True)
    sales_rank_reference_history = Column(JSON, nullable=True)
    bestsellers_rank_flat = Column(String(500), nullable=True)
    variant_asins_flat = Column(Text, nullable=True)

    # ═══════════════════════════════════════════════════════════════
    # Group 5: 商业-销量 (8列)
    # #01 #02 #08 #10 #14 #22 #28 #33
    # ═══════════════════════════════════════════════════════════════
    weekly_sold = Column(Integer, nullable=True)  # Canopy
    monthly_sold = Column(Integer, nullable=True)
    annual_sold = Column(Integer, nullable=True)  # Canopy
    recent_sales = Column(String(100), nullable=True)
    sales_rank_history = Column(JSON, nullable=True)
    frequently_bought_together = Column(JSON, nullable=True)
    sponsored_products = Column(JSON, nullable=True)
    also_bought = Column(JSON, nullable=True)  # 经常一起购买（RF）
    also_viewed = Column(JSON, nullable=True)  # 经常一起浏览

    # ═══════════════════════════════════════════════════════════════
    # Group 6: 评论/评分 (14列)
    # #02 #06 #08 #09 #17 #29 #30 #33
    # ═══════════════════════════════════════════════════════════════
    rating = Column(Float, nullable=True)
    review_count = Column(Integer, nullable=True)
    rating_history = Column(JSON, nullable=True)
    review_count_history = Column(JSON, nullable=True)
    rating_breakdown = Column(JSON, nullable=True)
    top_reviews = Column(JSON, nullable=True)
    reviews = Column(JSON, nullable=True)  # Canopy 全文评论
    review_velocity_30d = Column(Integer, nullable=True, default=0)
    coupon_text = Column(String(500), nullable=True)
    promotions_json = Column(JSON, nullable=True)
    lightning_deal_info = Column(JSON, nullable=True)
    summarization_attributes = Column(JSON, nullable=True)
    customers_say = Column(JSON, nullable=True)
    has_reviews = Column(Boolean, nullable=True, default=False)
    gift_guide_badge = Column(JSON, nullable=True)
    amazons_choice = Column(JSON, nullable=True)
    subscribe_and_save = Column(JSON, nullable=True)
    trade_in_and_save = Column(Boolean, nullable=True, default=False)
    deal_badge = Column(String(200), nullable=True)
    big_spring_deal_percentage = Column(Float, nullable=True)

    # ═══════════════════════════════════════════════════════════════
    # Group 7: 竞争/Offer (22列)
    # #03 #05 #12 #13 #21 #24
    # ═══════════════════════════════════════════════════════════════
    seller_count = Column(Integer, nullable=True)
    offer_count = Column(Integer, nullable=True)
    offer_count_fba = Column(Integer, nullable=True)
    offer_count_fbm = Column(Integer, nullable=True)
    buybox_seller_id = Column(String(50), nullable=True)
    buybox_seller_name = Column(String(200), nullable=True)
    buybox_availability = Column(String(100), nullable=True)
    buybox_condition = Column(String(50), nullable=True)
    buybox_is_amazon = Column(Boolean, nullable=True)
    is_fba = Column(Boolean, nullable=True)
    is_prime = Column(Boolean, nullable=True)
    fulfillment = Column(JSON, nullable=True)
    return_policy = Column(JSON, nullable=True)
    protection_plans = Column(JSON, nullable=True)
    offer_history = Column(JSON, nullable=True)
    seller_ids_lowest_fba = Column(JSON, nullable=True)
    seller_ids_lowest_fbm = Column(JSON, nullable=True)
    buybox_eligible_offer_counts = Column(JSON, nullable=True)
    used_offers_count = Column(Integer, nullable=True)
    new_offers_from = Column(Float, nullable=True)
    used_offers_from = Column(Float, nullable=True)

    # ═══════════════════════════════════════════════════════════════
    # Group 8: 卖家生态 (17列)
    # #01 #03 #13 #24 #26
    # ═══════════════════════════════════════════════════════════════
    top_seller_id = Column(String(50), nullable=True)
    top_seller_name = Column(String(200), nullable=True)
    has_amazon_selling = Column(Boolean, nullable=True, default=False)
    has_china_sellers = Column(Boolean, nullable=True, default=False)
    is_warehouse_deal = Column(Boolean, nullable=True, default=False)
    is_preorder = Column(Boolean, nullable=True, default=False)
    is_map_restricted = Column(Boolean, nullable=True, default=False)
    seller_profile = Column(JSON, nullable=True)
    max_order_quantity = Column(Integer, nullable=True)
    is_amazon_brand = Column(Boolean, nullable=True, default=False)
    is_exclusive_to_amazon = Column(Boolean, nullable=True, default=False)
    is_small_business = Column(Boolean, nullable=True, default=False)
    climate_pledge_friendly = Column(Boolean, nullable=True, default=False)
    add_on_item = Column(Boolean, nullable=True, default=False)
    proposition_65_warning = Column(Boolean, nullable=True, default=False)
    sell_on_amazon = Column(Boolean, nullable=True, default=False)

    # ═══════════════════════════════════════════════════════════════
    # Group 9: 履约/库存 (17列)
    # #04 #10 #16 #25 #28 #32
    # ═══════════════════════════════════════════════════════════════
    fba_fee = Column(Float, nullable=True)
    referral_fee_percent = Column(Float, nullable=True)
    stock_level = Column(Integer, nullable=True)
    is_in_stock = Column(Boolean, nullable=True)
    availability_text = Column(String(100), nullable=True)
    out_of_stock_pct_30d = Column(Float, nullable=True)
    out_of_stock_pct_90d = Column(Float, nullable=True)
    out_of_stock_pct_180d = Column(Float, nullable=True)
    out_of_stock_count_amazon = Column(Integer, nullable=True)
    available_prime_exclusive = Column(Boolean, nullable=True)
    shipping_origin = Column(String(100), nullable=True)
    is_eligible_for_free_shipping = Column(Boolean, nullable=True)
    is_heat_sensitive = Column(Boolean, nullable=True)
    hazardous_materials = Column(JSON, nullable=True)
    is_fulfilled_by_amazon_international = Column(Boolean, nullable=True, default=False)
    isEligibleForSuperSaverShipping = Column(Boolean, nullable=True, default=False)
    free_shipping_minimum_spend = Column(Float, nullable=True)

    # ═══════════════════════════════════════════════════════════════
    # Group 10: Listing 安全 (8列)
    # #07 #15 #21 #23 #25 #30 #31
    # ═══════════════════════════════════════════════════════════════
    is_redirect_asin = Column(Boolean, nullable=True, default=False)
    parent_asin_history = Column(JSON, nullable=True)
    is_adult_product = Column(Boolean, nullable=True, default=False)
    is_sns = Column(Boolean, nullable=True, default=False)
    is_eligible_for_trade_in = Column(Boolean, nullable=True, default=False)
    launchpad = Column(Boolean, nullable=True, default=False)
    batteries_included = Column(Boolean, nullable=True, default=False)
    batteries_required = Column(Boolean, nullable=True, default=False)

    # ═══════════════════════════════════════════════════════════════
    # Group 11: 历史序列 (6列)
    # #09 #14
    # ═══════════════════════════════════════════════════════════════
    price_history = Column(JSON, nullable=True)
    bsr_history = Column(JSON, nullable=True)
    rating_history = Column(JSON, nullable=True)
    review_count_history = Column(JSON, nullable=True)
    sales_rank_history = Column(JSON, nullable=True)
    raw_payload = Column(JSON, nullable=True)  # 三源原始数据快照

    # ═══════════════════════════════════════════════════════════════
    # Group 12: 元信息 (16列)
    # #07 #15 #19 #31 #33
    # ═══════════════════════════════════════════════════════════════
    coverage_map = Column(JSON, nullable=True)
    freshness_map = Column(JSON, nullable=True)
    lifecycle_status = Column(String(10), nullable=True, default="active")
    last_accessed_at = Column(DateTime(timezone=True), nullable=True)
    importance_score = Column(Float, nullable=True)
    importance_tier = Column(String(10), nullable=True)
    importance_details = Column(JSON, nullable=True)
    data_source = Column(JSON, nullable=True)
    keepa_updated_at = Column(DateTime(timezone=True), nullable=True)
    rainforest_updated_at = Column(DateTime(timezone=True), nullable=True)
    canopy_updated_at = Column(DateTime(timezone=True), nullable=True)
    importance_updated_at = Column(DateTime(timezone=True), nullable=True)
    listed_since = Column(DateTime(timezone=True), nullable=True)
    tracking_since = Column(DateTime(timezone=True), nullable=True)
    first_available = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # ═══════════════════════════════════════════════════════════════
    # 复合键 + 索引
    # ═══════════════════════════════════════════════════════════════
    __table_args__ = (
        UniqueConstraint("asin", "domain", name="uq_asin_domain"),
        Index("idx_asin_domain", "asin", "domain"),
    )


class AmazonETLLog(Base):
    """ETL 执行日志表"""
    __tablename__ = "amazon_etl_logs"

    id = Column(Integer, primary_key=True, index=True)
    run_id = Column(String(36), nullable=False, index=True)

    started_at = Column(DateTime(timezone=True), nullable=False)
    finished_at = Column(DateTime(timezone=True), nullable=True)
    duration_seconds = Column(Float, nullable=True)
    status = Column(String(20), nullable=False, default="running")

    source = Column(String(20), nullable=False)
    asins_queried = Column(Integer, nullable=True, default=0)
    asins_success = Column(Integer, nullable=True, default=0)
    asins_failed = Column(JSON, nullable=True)

    tokens_or_credits = Column(Integer, nullable=True)
    tier = Column(String(10), nullable=True)

    error_message = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())