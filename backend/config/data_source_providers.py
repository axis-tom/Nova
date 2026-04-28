# backend/config/data_source_providers.py
from typing import Dict, Any, Optional, Callable
from pydantic import BaseModel
import httpx
from backend.foundation.perception.connectors.email.imap_client import IMAPClient
# from backend.foundation.perception.connectors.rss import RSSClient
# 其他 connector 按需导入

class ConfigField(BaseModel):
    name: str
    label: str
    type: str  # text, password, number, textarea, select, checkbox
    required: bool = True
    placeholder: str = ""
    hint: str = ""
    options: Optional[list] = None

class DataSourceTypeDef(BaseModel):
    type: str
    name: str
    fields: list[ConfigField]
    test_connection: Optional[Callable] = None

# 邮箱服务商预设
PROVIDERS_MAP = {
    "qq": {"imap_server": "imap.qq.com", "imap_port": 993, "use_ssl": True},
    "163": {"imap_server": "imap.163.com", "imap_port": 993, "use_ssl": True},
    "gmail": {"imap_server": "imap.gmail.com", "imap_port": 993, "use_ssl": True},
    "outlook": {"imap_server": "outlook.office365.com", "imap_port": 993, "use_ssl": True},
}

# 测试函数
async def test_email_connection(config: dict) -> bool:
    try:
        provider = config.get("provider")
        if provider == "custom":
            host = config["imap_server"]
            port = config.get("imap_port", 993)
            use_ssl = config.get("use_ssl", True)
        else:
            info = PROVIDERS_MAP.get(provider, {})
            host = info.get("imap_server")
            port = info.get("imap_port", 993)
            use_ssl = info.get("use_ssl", True)
        password = config.get("password")
        if not password:
            password = config.get("encrypted_password")
        client = IMAPClient(
            host=host,
            port=port,
            username=config["email"],
            password=password,
            use_ssl=use_ssl
        )
        await client.connect()
        # 连接成功即返回 True，断开失败不影响结果
        try:
            await client.disconnect()
        except Exception:
            pass
        return True
    except Exception as e:
        import traceback
        print(f"Test connection error: {e}")
        traceback.print_exc()
        return False

async def test_rss_connection(config: dict) -> bool:
    try:
        client = RSSClient(config["url"])
        await client.fetch()
        return True
    except:
        return False

# 数据源类型注册表
DATA_SOURCE_TYPES: Dict[str, DataSourceTypeDef] = {}

DATA_SOURCE_TYPES["email"] = DataSourceTypeDef(
    type="email",
    name="邮件 (IMAP)",
    fields=[
        ConfigField(name="provider", label="服务商", type="select", required=True,
                    options=[{"value": "qq", "label": "QQ邮箱"},
                             {"value": "163", "label": "163邮箱"},
                             {"value": "gmail", "label": "Gmail"},
                             {"value": "outlook", "label": "Outlook/Hotmail"},
                             {"value": "custom", "label": "自定义"}]),
        ConfigField(name="email", label="邮箱地址", type="text", required=True),
        ConfigField(name="password", label="密码/授权码", type="password", required=True,
                    hint="QQ邮箱需授权码，Gmail需应用专用密码"),
        ConfigField(name="imap_server", label="IMAP服务器", type="text", required=False,
                    hint="仅自定义服务商需要填写"),
        ConfigField(name="imap_port", label="端口", type="number", required=False, placeholder="993"),
        ConfigField(name="use_ssl", label="使用SSL", type="checkbox", required=False),
    ],
    test_connection=test_email_connection
)

DATA_SOURCE_TYPES["rss"] = DataSourceTypeDef(
    type="rss",
    name="RSS 订阅",
    fields=[
        ConfigField(name="url", label="RSS地址", type="text", required=True,
                    placeholder="https://example.com/feed.xml"),
        ConfigField(name="title", label="订阅名称", type="text", required=False),
    ],
    test_connection=test_rss_connection
)

DATA_SOURCE_TYPES["weibo"] = DataSourceTypeDef(
    type="weibo",
    name="微博",
    fields=[
        ConfigField(name="username", label="用户名/UID", type="text", required=True),
        ConfigField(name="cookie", label="Cookie（可选）", type="password", required=False,
                    hint="用于访问需登录的内容"),
        ConfigField(name="max_items", label="最大抓取条数", type="number", required=False, placeholder="10"),
    ],
    test_connection=None
)

DATA_SOURCE_TYPES["xiaohongshu"] = DataSourceTypeDef(
    type="xiaohongshu",
    name="小红书",
    fields=[
        ConfigField(name="user_id", label="用户ID", type="text", required=True),
        ConfigField(name="cookie", label="Cookie", type="password", required=False),
        ConfigField(name="max_items", label="最大抓取条数", type="number", required=False),
    ],
)

DATA_SOURCE_TYPES["financial"] = DataSourceTypeDef(
    type="financial",
    name="财务数据 (CSV)",
    fields=[
        ConfigField(name="file_url", label="文件URL", type="text", required=False,
                    placeholder="https://.../data.csv"),
        ConfigField(name="local_path", label="本地路径", type="text", required=False,
                    placeholder="/data/finance.csv"),
        ConfigField(name="format", label="格式", type="select", required=True,
                    options=[{"value": "csv", "label": "CSV"}, {"value": "excel", "label": "Excel"}]),
    ],
)

DATA_SOURCE_TYPES["competitor"] = DataSourceTypeDef(
    type="competitor",
    name="竞品监控",
    fields=[
        ConfigField(name="url", label="监控地址", type="text", required=True),
        ConfigField(name="name", label="竞品名称", type="text", required=True),
        ConfigField(name="type", label="类型", type="select", required=True,
                    options=[{"value": "rss", "label": "RSS"},
                             {"value": "website", "label": "网页"},
                             {"value": "api", "label": "API"}]),
        ConfigField(name="api_key", label="API密钥", type="password", required=False),
    ],
)