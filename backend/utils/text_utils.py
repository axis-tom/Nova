import re
from typing import List, Optional

def truncate(text: str, max_length: int = 200, suffix: str = "...") -> str:
    """截断文本到指定长度"""
    if len(text) <= max_length:
        return text
    return text[:max_length - len(suffix)] + suffix

def extract_keywords(text: str, max_keywords: int = 10) -> List[str]:
    """简单提取关键词（基于词频）"""
    # 移除标点，分词
    words = re.findall(r'\b\w+\b', text.lower())
    # 停用词示例（可扩展）
    stopwords = {'的', '了', '是', '在', '我', '有', '和', '就', '不', '人', '都', '一', '一个', '上', '也', '很', '到', '说', '要', '去', '你', '会', '着', '没有', '看', '好', '自己', '这'}
    words = [w for w in words if w not in stopwords and len(w) > 1]
    # 统计词频
    from collections import Counter
    counter = Counter(words)
    # 返回最常见的词
    return [word for word, _ in counter.most_common(max_keywords)]

def remove_html_tags(text: str) -> str:
    """移除 HTML 标签"""
    return re.sub(r'<[^>]+>', '', text)

def normalize_whitespace(text: str) -> str:
    """规范化空白字符"""
    return ' '.join(text.split())