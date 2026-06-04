"""
Nova 配置模块 - 统一导出
提供配置、模型、仓储等核心模块的统一访问入口

注意：models_module / repositories_module 使用 __getattr__ 延迟加载，
避免 data.database → config.config → config.__init__ → data.models → data.database 的循环依赖。
"""
from backend.config.config import settings
from backend.config.settings import BASE_DIR, TEMPLATES_DIR, IS_DEV


def __getattr__(name):
    """延迟导入，避免启动时的 circular import"""
    if name == "models_module":
        from backend.data import models as m
        return m
    if name == "repositories_module":
        from backend.data import repositories as r
        return r
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "settings",
    "BASE_DIR",
    "TEMPLATES_DIR",
    "IS_DEV",
    "models_module",
    "repositories_module",
]