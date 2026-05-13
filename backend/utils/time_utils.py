from datetime import datetime, timedelta
from typing import Optional, Union
import re

def parse_date(date_str: str) -> Optional[datetime]:
    """尝试解析多种日期格式"""
    patterns = [
        r'(\d{4}-\d{2}-\d{2})',           # YYYY-MM-DD
        r'(\d{2}/\d{2}/\d{4})',           # MM/DD/YYYY
        r'(\d{4}年\d{1,2}月\d{1,2}日)',   # 中文日期
    ]
    for pattern in patterns:
        match = re.search(pattern, date_str)
        if match:
            try:
                return datetime.strptime(match.group(1), '%Y-%m-%d')
            except:
                pass
    return None

def format_datetime(dt: datetime, fmt: str = "%Y-%m-%d %H:%M:%S") -> str:
    """格式化 datetime"""
    return dt.strftime(fmt)

def now() -> datetime:
    """返回当前 UTC 时间"""
    return datetime.utcnow()

def days_ago(days: int) -> datetime:
    """返回 N 天前的 UTC 时间"""
    return datetime.utcnow() - timedelta(days=days)

def to_iso8601(dt: datetime) -> str:
    """转换为 ISO 8601 格式"""
    return dt.isoformat()