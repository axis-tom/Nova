"""
Amazon 产品数据模型 — 三源 ETL 合并后的统一存储

分组说明（7 组 + 2 组元数据）：
  1. 基础标识  — ASIN、domain、parent
  2. Listing   — 标题/品牌/图片/A+/视频/规格
  3. 商业数据   — 价格 / BSR / 销量 / 评论 / 评分
  4. 竞争数据   — Buy Box / Offer / FBA / 推荐费
  5. 历史序列   — Keepa 独占的时间序列
  6. 制造/规格  — 制造商/型号/条形码/颜色/尺寸
  7. 配送/库存  — FBA/FBM/库存量/配送方式
  8. 覆盖与新鲜度 — ★ 新增：数据质量追踪
  9. 元信息     — 时间戳、数据源
"""
from sqlalchemy import Column, Integer, String, Boolean, DateTime, JSON, Text, Float, BigInteger
from sqlalchemy.sql import func
from backend.data.database import Base


class AmazonProduct(Base):
    """
    亚马逊商品统一数据表。
    三源 ETL Pipeline 的目标表，所有 Agent 查商品时查此表而非直接调 API。
    """
    __tablename__ = "amazon_products"

    id = Column(Integer, primary_key=True, index=True)

    # ── 1. 基础标识 ───────────────────────────────────────────────
    asin = Column(String(10), unique=True, nullable=False, index=True)
    domain = Column(String(10), nullable=False, default="US", index=True)  # US/DE/JP
    parent_asin = Column(String(10), nullable=True, index=True)
    child_asins = Column(JSON, nullable=True)  # 子 ASIN 列表（Rainforest/Keepa）
    product_type = Column(String(50), nullable=True)  # 标准/变体父/子（Keepa productType）

    # ── 2. Listing 内容 ──────────────────────────────────────────
    title = Column(String(500), nullable=True)
    brand = Column(String(200), nullable=True)
    brand_store = Column(JSON, nullable=True)  # {name, url, url_name}
    sub_title = Column(JSON, nullable=True)  # {text, link} 店铺链接
    feature_bullets = Column(JSON, nullable=True)  # 五点描述列表
    description = Column(Text, nullable=True)
    specifications = Column(JSON, nullable=True)  # [{name, value}, ...] 规格参数
    aplus_content = Column(JSON, nullable=True)  # A+ 品牌故事内容
    whats_in_the_box = Column(JSON, nullable=True)  # 包装内容列表
    main_image = Column(String(500), nullable=True)
    images = Column(JSON, nullable=True)  # 图片 URL 列表
    images_count = Column(Integer, nullable=True)
    videos_count = Column(Integer, nullable=True)
    videos = Column(JSON, nullable=True)  # 视频信息列表
    color = Column(String(100), nullable=True)
    size = Column(String(100), nullable=True)
    style = Column(String(100), nullable=True)
    material = Column(String(200), nullable=True)
    weight = Column(String(100), nullable=True)
    item_weight_g = Column(Integer, nullable=True)  # Keepa 克数
    package_weight_g = Column(Integer, nullable=True)  # Keepa 包装克数
    package_dimensions_mm = Column(JSON, nullable=True)  # [L, W, H] 毫米
    package_quantity = Column(Integer, nullable=True)
    unit_count = Column(JSON, nullable=True)  # {unitType, unitValue}

    # ── 3. 商业数据 ──────────────────────────────────────────────
    # 价格
    current_price = Column(Float, nullable=True)
    currency = Column(String(10), nullable=True, default="USD")
    list_price = Column(Float, nullable=True)  # 厂商建议零售价
    buybox_price = Column(Float, nullable=True)  # Buy Box 当前价
    avg_price_30d = Column(Float, nullable=True)
    avg_price_90d = Column(Float, nullable=True)
    min_price_90d = Column(Float, nullable=True)
    max_price_90d = Column(Float, nullable=True)

    # BSR
    current_bsr = Column(Integer, nullable=True)
    bsr_category = Column(String(200), nullable=True)  # BSR 所在类目名
    bsr_category_id = Column(Integer, nullable=True)  # BSR 类目 ID（Keepa）
    avg_bsr_30d = Column(Float, nullable=True)
    avg_bsr_90d = Column(Float, nullable=True)
    bsr_trend = Column(String(20), nullable=True)  # improving/declining/stable/unknown
    sales_rank_drops_30d = Column(Integer, nullable=True)
    sales_rank_drops_90d = Column(Integer, nullable=True)

    # 销量
    weekly_sold = Column(Integer, nullable=True)  # Canopy 周销量
    monthly_sold = Column(Integer, nullable=True)
    annual_sold = Column(Integer, nullable=True)  # Canopy 年销量
    recent_sales = Column(String(100), nullable=True)  # "400+ bought in past month"

    # 评论 & 评分
    rating = Column(Float, nullable=True)
    review_count = Column(Integer, nullable=True)
    rating_breakdown = Column(JSON, nullable=True)  # {5: {count, percentage}, 4: ...}
    top_reviews = Column(JSON, nullable=True)  # 评论预览列表
    review_velocity_30d = Column(Integer, nullable=True, default=0)

    # 库存
    stock_level = Column(Integer, nullable=True)  # Canopy product/stock
    is_in_stock = Column(Boolean, nullable=True)
    availability_text = Column(String(100), nullable=True)  # "In Stock"
    out_of_stock_pct_30d = Column(Float, nullable=True)  # Keepa 30天缺货%

    # ── 4. 竞争数据 ──────────────────────────────────────────────
    seller_count = Column(Integer, nullable=True)  # 总 offer 数
    offer_count = Column(Integer, nullable=True)  # 新品 offer 数
    offer_count_fba = Column(Integer, nullable=True)
    offer_count_fbm = Column(Integer, nullable=True)
    buybox_seller_id = Column(String(50), nullable=True)
    buybox_seller_name = Column(String(200), nullable=True)
    is_fba = Column(Boolean, nullable=True)
    is_prime = Column(Boolean, nullable=True)
    fulfillment = Column(JSON, nullable=True)  # {type, is_FBA, is_Amazon, seller, delivery_dates}
    return_policy = Column(JSON, nullable=True)  # {duration_days, type}
    fba_fee = Column(Float, nullable=True)  # Keepa FBA pick&pack fee
    referral_fee_percent = Column(Float, nullable=True)  # Keepa referral fee %
    protection_plans = Column(JSON, nullable=True)  # 延长保修
    is_bundle = Column(Boolean, nullable=True)

    # ── 5. 历史序列（Keepa 独占） ──────────────────────────────
    price_history = Column(JSON, nullable=True)  # [{timestamp, value}]
    bsr_history = Column(JSON, nullable=True)  # [{timestamp, value}]
    rating_history = Column(JSON, nullable=True)  # 评分历史时间序列
    review_count_history = Column(JSON, nullable=True)  # [{timestamp, value}]
    sales_rank_history = Column(JSON, nullable=True)  # 多类目 BSR {catId: [{ts, val}]}

    # ── 6. 制造/规格 ─────────────────────────────────────────────
    manufacturer = Column(String(200), nullable=True)
    model_number = Column(String(200), nullable=True)
    part_number = Column(String(200), nullable=True)
    upc = Column(String(50), nullable=True)
    ean = Column(String(50), nullable=True)
    isbn = Column(String(50), nullable=True)
    product_group = Column(String(100), nullable=True)
    binding = Column(String(100), nullable=True)
    country_of_origin = Column(String(100), nullable=True)
    item_type_keyword = Column(String(100), nullable=True)  # Keepa itemTypeKeyword

    # ── 7. 配送/物流 ─────────────────────────────────────────────
    available_prime_exclusive = Column(Boolean, nullable=True)  # Prime 专享价
    shipping_origin = Column(String(100), nullable=True)  # 发货国家
    is_eligible_for_free_shipping = Column(Boolean, nullable=True)
    is_adult_product = Column(Boolean, nullable=True)

    # ── 8. 覆盖度与新鲜度 ★ ─────────────────────────────────────
    freshness_map = Column(JSON, nullable=True)
    # 每个源各类数据的最后成功采集时间
    # {"keepa_product": "2026-05-28T12:00:00Z",
    #  "rainforest_product": "2026-05-28T12:01:00Z",
    #  "canopy_reviews": "2026-05-28T12:02:00Z",
    #  "canopy_sales": "2026-05-28T12:03:00Z",
    #  "canopy_stock": "2026-05-28T12:04:00Z"}

    coverage_map = Column(JSON, nullable=True)
    # 这个 ASIN 在各源上实际获取到了什么数据
    # {"has_reviews_body": true, "has_aplus": false,
    #  "has_price_history": true, "has_stock_level": true,
    #  "has_sales_estimate": true, "has_buybox_info": true,
    #  "has_seller_profile": false}

    raw_payload = Column(JSON, nullable=True)
    # 三源各端点的原始数据快照，用于回填历史字段 + 数据血缘
    # {"keepa_product": {...}, "rainforest_product": {...},
    #  "canopy_product": {...}, "canopy_reviews": {...},
    #  "canopy_sales": {...}, "canopy_stock": {...}}

    # ── Importance Score ──────────────────────────────────────────
    importance_score = Column(Float, nullable=True)
    importance_tier = Column(String(10), nullable=True)  # hot / active / passive
    importance_details = Column(JSON, nullable=True)

    # ── 9. 数据源元信息 ─────────────────────────────────────────
    data_source = Column(JSON, nullable=True)  # {"keepa": true, "rainforest": true, "canopy": true}
    keepa_updated_at = Column(DateTime(timezone=True), nullable=True)
    rainforest_updated_at = Column(DateTime(timezone=True), nullable=True)
    canopy_updated_at = Column(DateTime(timezone=True), nullable=True)
    importance_updated_at = Column(DateTime(timezone=True), nullable=True)

    # ── 通用时间戳 ────────────────────────────────────────────────
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class AmazonETLLog(Base):
    """
    ETL 执行日志表 — 记录每次三源调用的执行情况。
    用于 Token 预算审计、调度器监控、异常诊断。
    """
    __tablename__ = "amazon_etl_logs"

    id = Column(Integer, primary_key=True, index=True)
    run_id = Column(String(36), nullable=False, index=True)

    started_at = Column(DateTime(timezone=True), nullable=False)
    finished_at = Column(DateTime(timezone=True), nullable=True)
    duration_seconds = Column(Float, nullable=True)
    status = Column(String(20), nullable=False, default="running")  # running/success/failed/partial

    source = Column(String(20), nullable=False)  # keepa/rainforest/canopy
    asins_queried = Column(Integer, nullable=True, default=0)
    asins_success = Column(Integer, nullable=True, default=0)
    asins_failed = Column(JSON, nullable=True)

    tokens_or_credits = Column(Integer, nullable=True)
    tier = Column(String(10), nullable=True)  # hot/active/passive

    error_message = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())