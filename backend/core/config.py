import os
from typing import Optional
from pydantic import Field
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # 应用基础
    APP_NAME: str = "Nova"
    DEBUG: bool = False
    API_V1_PREFIX: str = "/api/v1"

    # 安全
    JWT_SECRET_KEY: str = Field(..., env="cvQLm1IE/CxFken7AgI8qTMpUBSgEaP2FFepJzRpK0U=")  # 必须
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    # 数据库
    DATABASE_URL: str = "http://localhost:8080"

    # Redis
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0
    REDIS_PASSWORD: Optional[str] = None

    # Neo4j
    NEO4J_URI: str = "bolt://localhost:7687"
    NEO4J_USER: str = "neo4j"
    NEO4J_PASSWORD: str = "Nova@2026"

    # Chroma
    CHROMA_HOST: str = "localhost"
    CHROMA_PORT: int = 8001

    # 模型服务
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "qwen2.5:3b-instruct-q4_K_M"
    OPENAI_API_KEY: Optional[str] = None
    OPENAI_MODEL: Optional[str] = "gpt-4o-mini"

    # 日志
    LOG_LEVEL: str = "INFO"
    LOG_FILE: Optional[str] = None

    # 智能体配置
    AGENT_TIMEOUT_SECONDS: int = 30
    AGENT_RETRY_LIMIT: int = 2

    # 外部集成
    QQ_EMAIL: Optional[str] = None
    QQ_AUTH_CODE: Optional[str] = None
    FEISHU_WEBHOOK: Optional[str] = None

    class Config:
        env_file = ".env"                # 因为从 ~/nova 启动，根目录的 .env
        env_file_encoding = "utf-8"
        extra = "ignore"                 # 忽略额外的环境变量，不报错

settings = Settings()