from pathlib import Path
from typing import Optional
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    APP_NAME: str = "Nova"
    DEBUG: bool = False
    API_V1_PREFIX: str = "/api/v1"
    LOG_LEVEL: str = "INFO"
    LOG_FILE: Optional[str] = None

    # 安全
    JWT_SECRET_KEY: str
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    # 数据库
    DATABASE_URL: str

    # 加密
    ENCRYPTION_KEY: str

    # Redis
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0
    REDIS_PASSWORD: Optional[str] = None

    # 模型与外部服务
    OPENAI_API_KEY: Optional[str] = None
    OPENAI_API_BASE: Optional[str] = None
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "qwen2.5:3b-instruct-q4_K_M"
    GROQ_API_KEY: Optional[str] = None
    GEMINI_API_KEY: Optional[str] = None
    ZHIPU_API_KEY: Optional[str] = None
    HTTP_PROXY: Optional[str] = None
    HTTPS_PROXY: Optional[str] = None

    # 智能体
    AGENT_TIMEOUT_SECONDS: int = 30
    AGENT_RETRY_LIMIT: int = 2

    # 本地模型缓存路径
    MODEL_STORAGE_PATH: str = "data/models"

    # Amazon Product Advertising API 5.0
    AMAZON_ACCESS_KEY: Optional[str] = None
    AMAZON_SECRET_KEY: Optional[str] = None
    AMAZON_ASSOCIATE_TAG: Optional[str] = None
    AMAZON_PARTNER_TYPE: str = "Associates"
    AMAZON_MARKETPLACE: str = "www.amazon.com"
    AMAZON_MAX_RETRY: int = 3
    AMAZON_CACHE_TTL_HOURS: int = 24

    # Keepa API
    KEEPA_API_KEY: Optional[str] = None

    # Keepa Token 消耗控制
    KEEPA_PRICE_MONITOR_INTERVAL_HOURS: int = 6    # 价格监控间隔（小时）
    KEEPA_BSR_MONITOR_INTERVAL_HOURS: int = 24     # BSR 监控间隔（小时）
    KEEPA_MAX_KEYWORDS_PER_RUN: int = 5            # 每次最多搜索关键词数
    KEEPA_MAX_ASINS_PER_QUERY: int = 20            # 每次最多查询 ASIN 数
    KEEPA_DEAL_MAX_RESULTS: int = 30               # Deal API 每次最多返回数量
    KEEPA_CACHE_TTL_HOURS: int = 6                 # ASIN 缓存 TTL（小时），0 = 禁用缓存

    # Rainforest API 配置
    # 注册地址: https://app.rainforestapi.com/
    # 文档: https://docs.rainforestapi.com/
    # 计费: 不同端点独立计费（product/reviews/search 各消耗不同 credit）
    RAINFOREST_API_KEY: Optional[str] = None

    # Rainforest 采集控制
    RAINFOREST_DEFAULT_DOMAIN: str = "amazon.com"     # 默认市场域名
    RAINFOREST_MAX_RETRY: int = 3                     # 失败重试次数
    RAINFOREST_REQUEST_TIMEOUT: int = 30              # 请求超时（秒）
    RAINFOREST_REVIEWS_FIRST_PAGE_SIZE: int = 10      # L1 评论首页条数
    RAINFOREST_REVIEWS_EXTRA_PAGE_SIZE: int = 50      # L2 补单时每页条数
    RAINFOREST_MAX_REVIEW_PAGES: int = 3              # 补单最多拉取页数
    RAINFOREST_SEARCH_MAX_RESULTS: int = 20           # 搜索每关键词最大结果数
    RAINFOREST_SEARCH_MAX_KEYWORDS: int = 5           # 每次最多搜索关键词数

    # Canopy API 配置
    # 注册地址: https://app.canopyapi.com/
    # 文档: https://docs.canopyapi.com/
    CANOPY_API_KEY: Optional[str] = None

    # Canopy 采集控制
    CANOPY_DEFAULT_DOMAIN: str = "amazon.com"
    CANOPY_REQUEST_TIMEOUT: int = 60
    CANOPY_REVIEWS_FIRST_PAGE_SIZE: int = 10
    CANOPY_REVIEWS_EXTRA_PAGE_SIZE: int = 50
    CANOPY_MAX_REVIEW_PAGES: int = 3
    CANOPY_SEARCH_MAX_RESULTS: int = 20
    CANOPY_SEARCH_MAX_KEYWORDS: int = 5

    # Amazon 监控调度器开关
    # 默认关闭：避免每 6 小时自动跑 product_collector 偷烧 Keepa token
    # 显式设为 1/true/yes 才会在启动时拉起后台定时任务
    ENABLE_AMAZON_SCHEDULER: bool = False

    # 运行时数据目录（SQLite / 缓存等）
    DATA_DIR: str = str(Path(__file__).resolve().parent.parent / "infrastructure" / "data")

    class Config:
        env_file = Path(__file__).resolve().parent / ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"

settings = Settings()
