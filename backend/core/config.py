from pathlib import Path
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
    JWT_SECRET_KEY: str = "IfvAeR0DgGsG7a+x6auBKG4tnyg57PtmJ1KZkmTJ1wMkQtuYzzyf+BX+zyizdxX9"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    # 数据库（硬编码，确保启动）
    # DATABASE_URL: str = "postgresql+asyncpg://nova:Nova@2026@localhost:5432/nova_dev"
    DATABASE_URL: str = "postgresql+asyncpg://nova:Nova@2026@172.25.48.1:5432/nova_dev"

    # NocoDB（可保留）
    NOCODB_URL: str = "http://localhost:8081"
    NOCODB_API_KEY: str = ""

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

    # 加密
    ENCRYPTION_KEY: str = "u7f5ZaldUvoH4QKomSipfk7hBRlq3LZl1/y9KUYHwFk="

    # AI 相关
    GROQ_API_KEY: Optional[str] = "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"
    GEMINI_API_KEY: Optional[str] = "AIzaSyCicIEXYhxHb8qqsZge-Kp07a5iSH47FJM"
    ZHIPU_API_KEY: Optional[str] = "a5d63731a2dc4ef68d3dea49c3240eff.n9gDmEANrgAHwDDr"
    HTTP_PROXY: Optional[str] = "http://127.0.0.1:7897"
    HTTPS_PROXY: Optional[str] = "http://127.0.0.1:7897"

    class Config:
        # 如果未来想用 .env 文件，可取消注释并指向正确路径
        # env_file = "/home/nova/nova/.env"
        env_file_encoding = "utf-8"
        extra = "ignore"

settings = Settings()