"""
联网搜索工具
提供 DuckDuckGo 搜索 + 网页爬虫能力
零配置，免费，国内可用
"""

from typing import List, Dict, Optional
import httpx
from bs4 import BeautifulSoup
from duckduckgo_search import DDGS


async def web_search(query: str, max_results: int = 5) -> List[Dict[str, str]]:
    """
    通过 DuckDuckGo 搜索外部信息

    Args:
        query: 搜索关键词
        max_results: 最大结果数

    Returns:
        [{title, content, url}]
    """
    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=max_results))
        return [
            {
                "title": r.get("title", ""),
                "content": r.get("body", ""),
                "url": r.get("href", ""),
            }
            for r in results
        ]
    except Exception as e:
        return [{"title": f"搜索失败: {e}", "content": "", "url": ""}]


async def scrape_url(url: str, timeout: int = 10) -> Optional[str]:
    """
    抓取网页正文内容

    Args:
        url: 网页 URL
        timeout: 超时秒数

    Returns:
        网页纯文本内容，失败返回 None
    """
    try:
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
            resp = await client.get(url, headers={"User-Agent": "Mozilla/5.0"})
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "html.parser")
            # 移除 script/style 标签
            for tag in soup(["script", "style", "nav", "footer", "header"]):
                tag.decompose()
            text = soup.get_text(separator="\n", strip=True)
            # 限制长度
            return text[:5000]
    except Exception as e:
        return None


async def search_and_scrape(query: str, max_results: int = 3) -> List[Dict[str, str]]:
    """
    搜索并抓取前 N 个结果的正文

    Args:
        query: 搜索关键词
        max_results: 抓取前几个结果

    Returns:
        [{title, content, url, full_text}]
    """
    results = await web_search(query, max_results=max_results)
    for r in results:
        if r["url"]:
            full_text = await scrape_url(r["url"])
            r["full_text"] = full_text or r["content"]
        else:
            r["full_text"] = r["content"]
    return results