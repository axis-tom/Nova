"""
Amazon 产品数据模型 — 三源 ETL 合并后的统一存储

设计原则：
1. 字段整合 Keepa / Rainforest / Canopy 三源数据
2. 每个字段携带 source 标记（哪个源最后更新）
3. Importance Score 存储在 ASIN 级别
4. 使用 JSON 字段存储结构化和历史数据（避免过多关联表）
"""
from sqlalchemy import Column, Integer, String, Boolean, DateTime, JSON, Text, Float, BigInteger
from sqlalchemy.sql import func
from backend.data.database import Base


class AmazonProduct(Base):
    """
    亚马逊商品统一数据表。

    三源 ETL Pipeline 的目标表，所有 Agent 查商品时查此表而非直接调 API。
    字段分 5 组：标识信息 / 基础信息 / 商业数据 / 卖家数据 / 元数据
    """
    __tablename__ = "amazon_products"

    id = Column(Integer, primary_key=True, index=True)

    # ── 标识信息 ──
    asin = Column(String(10), unique=True, nullable=False, index=True)
    domain = Column(String(10), nullable=False, default="US", index=True)  # US/DE/JP 等
    parent_asin = Column(String(10), nullable=True, index=True)
    child_asins = Column(JSON, nullable=True)  # 子 ASIN 列表，Rainforest 提供

    # ── 基础信息 ──
    title = Column(String(500), nullable=True)
    brand = Column(String(200), nullable=True)
    category_id = Column(Integer, nullable=True)
    category_name = Column(String(200), nullable=True)
    category_tree = Column(JSON, nullable=True)  # [{id, name, link}]
    feature_bullets = Column(JSON, nullable=True)  # 五点描述列表
    description = Column(Text, nullable=True)
    main_image = Column(String(500), nullable=True)
    images = Column(JSON, nullable=True)  # 图片 URL 列表
    videos_count = Column(Integer, nullable=True)

    # ── 规格/制造 ──
    manufacturer = Column(String(200), nullable=True)
    model_number = Column(String(200), nullable=True)
    part_number = Column(String(200), nullable=True)
    upc = Column(String(50), nullable=True)
    ean = Column(String(50), nullable=True)
    color = Column(String(100), nullable=True)
    size = Column(String(100), nullable=True)
    weight = Column(String(100), nullable=True)
    dimensions = Column(String(200), nullable=True)
    binding = Column(String(100), nullable=True)
    product_group = Column(String(100), nullable=True)
    country_of_origin = Column(String(100), nullable=True)

    # ── Listing 内容 ──
    aplus_content = Column(JSON, nullable=True)
    specifications = Column(JSON, nullable=True)

    # ── 商业数据 ──
    current_price = Column(Float, nullable=True)
    currency = Column(String(10), nullable=True, default="USD")
    list_price = Column(Float, nullable=True)
    current_bsr = Column(Integer, nullable=True)
    bsr_category = Column(String(200), nullable=True)
    avg_price_30d = Column(Float, nullable=True)
    avg_price_90d = Column(Float, nullable=True)
    min_price_90d = Column(Float, nullable=True)
    max_price_90d = Column(Float, nullable=True)
    avg_bsr_30d = Column(Float, nullable=True)
    avg_bsr_90d = Column(Float, nullable=True)
    bsr_trend = Column(String(20), nullable=True)  # improving / declining / stable / unknown
    price_history = Column(JSON, nullable=True)  # [{timestamp, value}] — Keepa 独家
    bsr_history = Column(JSON, nullable=True)  # [{timestamp, value}] — Keepa 独家

    # ── 销量/评论 ──
    monthly_sold = Column(Integer, nullable=True)
    recent_sales = Column(String(100), nullable=True)
    rating = Column(Float, nullable=True)
    review_count = Column(Integer, nullable=True)
    rating_breakdown = Column(JSON, nullable=True)  # {5: N, 4: N, 3: N, 2: N, 1: N}
    top_reviews = Column(JSON, nullable=True)  # 评论预览列表

    # ── 评论增速（ETL 管道自动计算） ──
    review_velocity_30d = Column(Integer, nullable=True, default=0)
    review_count_history = Column(JSON, nullable=True)  # [{timestamp, value}] — Keepa 提供

    # ── 卖家数据 ──
    seller_count = Column(Integer, nullable=True)
    seller_name = Column(String(200), nullable=True)
    is_fba = Column(Boolean, nullable=True)
    is_prime = Column(Boolean, nullable=True)
    fulfillment = Column(String(50), nullable=True)
    availability = Column(String(100), nullable=True)

    # ── 广告数据（Rainforest 提供） ──
    sponsored_products = Column(JSON, nullable=True)

    # ── Importance Score ──
    importance_score = Column(Float, nullable=True)
    importance_tier = Column(String(10), nullable=True)  # hot / active / passive
    importance_details = Column(JSON, nullable=True)  # 各分量分值和输入参数快照

    # ── 数据源元信息 ──
    data_source = Column(JSON, nullable=True)  # {"keepa": true, "rainforest": true, "canopy": true}
    keepa_updated_at = Column(DateTime(timezone=True), nullable=True)
    rainforest_updated_at = Column(DateTime(timezone=True), nullable=True)
    canopy_updated_at = Column(DateTime(timezone=True), nullable=True)
    importance_updated_at = Column(DateTime(timezone=True), nullable=True)

    # ── 通用时间戳 ──
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class AmazonETLLog(Base):
    """
    ETL 执行日志表 — 记录每次三源调用的执行情况。

    用于 Token 预算审计、调度器监控、异常诊断。
    """
    __tablename__ = "amazon_etl_logs"

    id = Column(Integer, primary_key=True, index=True)
    run_id = Column(String(36), nullable=False, index=True)  # 同批 ETL 共享一个 run_id

    # 批次信息
    started_at = Column(DateTime(timezone=True), nullable=False)
    finished_at = Column(DateTime(timezone=True), nullable=True)
    duration_seconds = Column(Float, nullable=True)
    status = Column(String(20), nullable=False, default="running")  # running/success/failed/partial

    # 数据源调用统计
    source = Column(String(20), nullable=False)  # keepa / rainforest / canopy
    asins_queried = Column(Integer, nullable=True, default=0)
    asins_success = Column(Integer, nullable=True, default=0)
    asins_failed = Column(JSON, nullable=True)  # 失败 ASIN 列表

    # Token/Credit 消耗
    tokens_or_credits = Column(Integer, nullable=True)  # Keepa tokens 或 API credits
    tier = Column(String(10), nullable=True)  # hot/active/passive — 本次执行针对的 tier

    # 错误信息
    error_message = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())