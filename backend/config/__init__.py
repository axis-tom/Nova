"""
Nova 配置模块 - 统一导出
提供配置、模型、仓储等核心模块的统一访问入口
"""

from backend.config.config import settings
from backend.config.settings import BASE_DIR, TEMPLATES_DIR, IS_DEV

# 统一导出 models 模块
from backend.data import models as models_module

# 统一导出 repositories 模块
from backend.data import repositories as repositories_module

__all__ = [
    "settings",
    "BASE_DIR",
    "TEMPLATES_DIR",
    "IS_DEV",
    "models_module",
    "repositories_module",
]
