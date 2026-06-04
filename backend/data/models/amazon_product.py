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
    search_alias = Column(JSON, nullable=True)
    unit_count = Column(JSON, nullable=True)  # {unitType, unitValue}
    unit_count_type = Column(String(50), nullable=True)
    unit_count_value = Column(Integer, nullable=True)
    number_of_items = Column(Integer, nullable=True)
    has_size_guide = Column(Boolean, nullable=True, default=False)
    has_360_view = Column(Boolean, nullable=True, default=False)
    # ETL Rainforest/Canopy 字段补全
    category_name = Column(String(500), nullable=True)
    category_tree = Column(JSON, nullable=True)
    manufacturer = Column(String(200), nullable=True)
    model_number = Column(String(100), nullable=True)
    part_number = Column(String(100), nullable=True)
    upc = Column(String(50), nullable=True)
    ean = Column(String(50), nullable=True)
    isbn = Column(String(50), nullable=True)
    binding = Column(String(100), nullable=True)
    product_group = Column(String(100), nullable=True)
    country_of_origin = Column(String(100), nullable=True)
    is_bundle = Column(Boolean, nullable=True, default=False)
    availability = Column(String(200), nullable=True)
    seller_id = Column(String(50), nullable=True)
    seller_name = Column(String(200), nullable=True)
    variations = Column(JSON, nullable=True)
    # Keepa 字段补全
    images_csv = Column(Text, nullable=True)
    item_type_keyword = Column(String(200), nullable=True)
    model = Column(String(100), nullable=True)
    root_category = Column(String(20), nullable=True)
    variation_csv = Column(Text, nullable=True)

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
    bsr_category_id = Column(String(20), nullable=True)
    avg_bsr_30d = Column(Float, nullable=True)
    avg_bsr_90d = Column(Float, nullable=True)
    avg_bsr_180d = Column(Float, nullable=True)
    avg_bsr_365d = Column(Float, nullable=True)
    bsr_trend = Column(String(20), nullable=True)
    sales_rank_drops_30d = Column(Integer, nullable=True)
    sales_rank_drops_90d = Column(Integer, nullable=True)
    sales_rank_drops_180d = Column(Integer, nullable=True)
    sales_rank_drops_365d = Column(Integer, nullable=True)
    sales_rank_reference_id = Column(String(20), nullable=True)
    root_category_id = Column(String(20), nullable=True)
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
    max_order_quantity = Column(JSON, nullable=True)
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
    first_available = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # ═══════════════════════════════════════════════════════════════
    # Group 13: 补充字段（基于多源API字段总表补全）
    # ═══════════════════════════════════════════════════════════════

    # 基础标识补充
    title_excluding_variant_name = Column(String(200), nullable=True)
    parent_title = Column(String(200), nullable=True)
    marketplace_id = Column(String(200), nullable=True)
    keywords = Column(String(200), nullable=True)
    type = Column(String(200), nullable=True)
    format = Column(String(200), nullable=True)
    edition = Column(String(200), nullable=True)
    runtime = Column(String(200), nullable=True)
    website_display_group = Column(String(200), nullable=True)
    website_display_group_name = Column(String(200), nullable=True)
    is_collection = Column(Boolean, nullable=True, default=False)
    collection_size = Column(Float, nullable=True)
    publication_date = Column(String(200), nullable=True)
    release_date = Column(Integer, nullable=True)
    publisher = Column(String(200), nullable=True)
    isbn_10 = Column(String(200), nullable=True)
    isbn_13 = Column(String(200), nullable=True)
    language = Column(String(200), nullable=True)
    reading_age = Column(String(200), nullable=True)
    kindle_unlimited = Column(Boolean, nullable=True, default=False)
    audible_sample = Column(String(500), nullable=True)
    book_description = Column(Text, nullable=True)
    domain_id = Column(Integer, nullable=True)
    g = Column(Integer, nullable=True)

    # 商品属性补充
    package_height_mm = Column(Integer, nullable=True)
    package_length_mm = Column(Integer, nullable=True)
    package_width_mm = Column(Integer, nullable=True)
    size_guide_html = Column(Text, nullable=True)
    recommended_uses_for_product = Column(String(200), nullable=True)

    # Listing 补充
    feature_bullets_flat = Column(Text, nullable=True)
    information = Column(String(500), nullable=True)
    promotions_feature = Column(String(500), nullable=True)

    # 图片视频补充
    images_flat = Column(Text, nullable=True)
    image_overlay_badge = Column(JSON, nullable=True)
    videos_flat = Column(Text, nullable=True)
    videos_additional = Column(JSON, nullable=True)

    # 品牌补充
    brand_store_url_name = Column(String(500), nullable=True)
    store_name = Column(String(200), nullable=True)
    store_id = Column(String(50), nullable=True)

    # 类目补充
    categories = Column(JSON, nullable=True)
    category_tree = Column(JSON, nullable=True)
    categories_flat = Column(Text, nullable=True)
    sales_rank_display_group = Column(String(200), nullable=True)
    category_information = Column(JSON, nullable=True)

    # 价格补充
    buybox_winner = Column(JSON, nullable=True)
    price = Column(JSON, nullable=True)
    prices = Column(JSON, nullable=True)
    rrp = Column(JSON, nullable=True)
    shipping = Column(JSON, nullable=True)
    condition = Column(JSON, nullable=True)
    save = Column(JSON, nullable=True)
    one_time_price = Column(JSON, nullable=True)
    mixed_offers_count = Column(Integer, nullable=True)
    mixed_offers_from = Column(JSON, nullable=True)
    is_big_spring_deal = Column(Boolean, nullable=True, default=False)
    amazon_discount = Column(JSON, nullable=True)
    unqualified_buy_box = Column(Boolean, nullable=True, default=False)
    deal = Column(JSON, nullable=True)
    vat = Column(JSON, nullable=True)
    eligible_free_international_delivery = Column(Boolean, nullable=True, default=False)

    # 评论评分补充
    ratings_total = Column(Integer, nullable=True)
    safety_product_resources = Column(JSON, nullable=True)

    # Offer/卖家补充
    offer_asin = Column(String(10), nullable=True)
    position = Column(Integer, nullable=True)
    is_sold_by_amazon = Column(Boolean, nullable=True, default=False)
    is_prime_excl = Column(Boolean, nullable=True, default=False)
    is_shippable = Column(Boolean, nullable=True, default=False)
    is_map = Column(Boolean, nullable=True, default=False)
    ships_from_china = Column(Boolean, nullable=True, default=False)
    minimum_order_quantity = Column(JSON, nullable=True)
    last_seen = Column(Integer, nullable=True)
    last_stock_update = Column(Integer, nullable=True)
    offer_csv = Column(JSON, nullable=True)
    prime_excl_csv = Column(JSON, nullable=True)
    offers_successful = Column(Boolean, nullable=True, default=False)
    buybox_is_fba = Column(Boolean, nullable=True, default=False)
    buybox_shipping_country = Column(String(50), nullable=True)
    promotion = Column(JSON, nullable=True)
    import_fee = Column(JSON, nullable=True)
    undeliverable = Column(Boolean, nullable=True, default=False)
    undeliverable_message = Column(String(500), nullable=True)
    product = Column(JSON, nullable=True)
    offers = Column(JSON, nullable=True)
    available_filters = Column(JSON, nullable=True)
    pagination = Column(JSON, nullable=True)

    # BSR 补充
    sales_ranks = Column(JSON, nullable=True)
    bestsellers_rank = Column(JSON, nullable=True)
    bestseller = Column(JSON, nullable=True)

    # 变体补充
    variation_csv = Column(Text, nullable=True)

    # 促销补充
    coupon = Column(JSON, nullable=True)
    gift_guide = Column(JSON, nullable=True)
    featured_from_our_brands = Column(Boolean, nullable=True, default=False)
    is_amazon_fresh = Column(Boolean, nullable=True, default=False)
    is_whole_foods_market = Column(Boolean, nullable=True, default=False)
    prime_video = Column(Boolean, nullable=True, default=False)

    # 配送物流补充
    delivery = Column(JSON, nullable=True)

    # 时间戳补充
    last_update = Column(Integer, nullable=True)
    last_price_change = Column(Integer, nullable=True)
    last_rating_update = Column(Integer, nullable=True)
    last_ebay_update = Column(Integer, nullable=True)

    # FBA 费用补充
    referral_fee_percentage = Column(Float, nullable=True)

    # 搜索专用
    search_results = Column(JSON, nullable=True)
    search_information = Column(JSON, nullable=True)
    ad_blocks = Column(JSON, nullable=True)
    video_blocks = Column(JSON, nullable=True)
    related_searches = Column(JSON, nullable=True)
    related_brands = Column(JSON, nullable=True)
    refinements = Column(JSON, nullable=True)
    shopping_advisors = Column(JSON, nullable=True)
    sponsored = Column(Boolean, nullable=True, default=False)
    is_carousel = Column(Boolean, nullable=True, default=False)
    carousel = Column(JSON, nullable=True)
    recent_views = Column(String(500), nullable=True)
    other_formats = Column(JSON, nullable=True)
    narrated_by = Column(JSON, nullable=True)
    image = Column(String(500), nullable=True)

    # 请求元数据补充
    request_info = Column(JSON, nullable=True)
    request_parameters = Column(JSON, nullable=True)
    request_metadata = Column(JSON, nullable=True)

    # JSON 对象补充（有子字段的独立字段）
    authors = Column(JSON, nullable=True)
    series = Column(JSON, nullable=True)
    read_sample = Column(JSON, nullable=True)
    collection_children = Column(JSON, nullable=True)
    ingredients = Column(JSON, nullable=True)
    diet_type = Column(JSON, nullable=True)
    attributes = Column(JSON, nullable=True)
    specific_uses_for_product = Column(JSON, nullable=True)
    special_features = Column(JSON, nullable=True)
    languages = Column(JSON, nullable=True)
    materials = Column(JSON, nullable=True)
    energy_efficiency = Column(JSON, nullable=True)
    services = Column(JSON, nullable=True)
    documents = Column(JSON, nullable=True)
    editorial_reviews = Column(JSON, nullable=True)
    important_information = Column(JSON, nullable=True)
    additional_details = Column(JSON, nullable=True)
    bestseller_badge = Column(JSON, nullable=True)
    product_deal = Column(JSON, nullable=True)

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