from backend.core.config import settings as core_settings
from pathlib import Path

# 重新导出核心设置
settings = core_settings

# 补充项目根目录相关路径
BASE_DIR = Path(__file__).resolve().parent.parent.parent
TEMPLATES_DIR = BASE_DIR / "backend" / "config" / "templates"

# 可在此添加其他运行时配置，如环境判断
IS_DEV = settings.DEBUG