"""
联网搜索工具 — 可插拔 Retriever 模式
提供 DuckDuckGo / Google / Bing 三种搜索后端，通过配置切换
零配置默认使用 DuckDuckGo（免费，国内可用）

架构参考 GPT Researcher 的 get_retrievers() 模式：
- BaseSearchBackend: 抽象接口
- DuckDuckGoBackend: 默认实现
- GoogleBackend / BingBackend: 可选实现
- get_searcher(): 工厂函数，根据配置返回对应后端
"""

import asyncio
from typing import List, Dict, Optional, Protocol, TypedDict
import os
import httpx
from bs4 import BeautifulSoup
from duckduckgo_search import DDGS


# ── 抽象接口 ──

import logging

_ws_logger = logging.getLogger(__name__)

class SearchResult(TypedDict):
    title: str
    content: str
    url: str


class BaseSearchBackend(Protocol):
    """搜索后端协议，所有后端必须实现此接口"""
    async def search(self, query: str, max_results: int = 5) -> List[Dict[str, str]]:
        ...


# ── DuckDuckGo 后端（默认，零配置） ──

class DuckDuckGoBackend:
    """DuckDuckGo 搜索后端，无需 API Key，国内可用"""

    async def search(self, query: str, max_results: int = 5) -> List[Dict[str, str]]:
        _ws_logger.info(f"[DuckDuckGoBackend] search: {query[:80]}")
        try:
            loop = asyncio.get_event_loop()
            results = await loop.run_in_executor(
                None, self._sync_search, query, max_results
            )
            _ws_logger.info(f"[DuckDuckGoBackend] 返回 {len(results)} 条结果")
            return results
        except Exception as e:
            _ws_logger.warning(f"[DuckDuckGoBackend] 搜索失败: {e}")
            return [{"title": f"DuckDuckGo 搜索失败: {e}", "content": "", "url": ""}]

    def _sync_search(self, query: str, max_results: int) -> List[Dict[str, str]]:
        """同步版搜索，在 run_in_executor 线程池中运行"""
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


# ── Google 后端（需 API Key） ──

class GoogleBackend:
    """Google Custom Search JSON API 后端
    需要设置环境变量:
    - GOOGLE_API_KEY
    - GOOGLE_CSE_ID (Custom Search Engine ID)
    """

    def __init__(self):
        self.api_key = os.getenv("GOOGLE_API_KEY")
        self.cse_id = os.getenv("GOOGLE_CSE_ID")

    async def search(self, query: str, max_results: int = 5) -> List[Dict[str, str]]:
        if not self.api_key or not self.cse_id:
            _ws_logger.warning("[GoogleBackend] 未配置 GOOGLE_API_KEY 或 GOOGLE_CSE_ID")
            return [{"title": "Google 搜索未配置: 需要设置 GOOGLE_API_KEY 和 GOOGLE_CSE_ID", "content": "", "url": ""}]

        _ws_logger.info(f"[GoogleBackend] search: {query[:80]}")
        try:
            url = "https://www.googleapis.com/customsearch/v1"
            params = {
                "key": self.api_key,
                "cx": self.cse_id,
                "q": query,
                "num": min(max_results, 10),
            }
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(url, params=params)
                resp.raise_for_status()
                data = resp.json()

            results = []
            for item in data.get("items", []):
                results.append({
                    "title": item.get("title", ""),
                    "content": item.get("snippet", ""),
                    "url": item.get("link", ""),
                })
            _ws_logger.info(f"[GoogleBackend] 返回 {len(results)} 条结果")
            return results
        except Exception as e:
            _ws_logger.warning(f"[GoogleBackend] 搜索失败: {e}")
            return [{"title": f"Google 搜索失败: {e}", "content": "", "url": ""}]


# ── Bing 后端（需 API Key） ──

class BingBackend:
    """Bing Search API 后端
    需要设置环境变量:
    - BING_API_KEY
    """

    def __init__(self):
        self.api_key = os.getenv("BING_API_KEY")

    async def search(self, query: str, max_results: int = 5) -> List[Dict[str, str]]:
        if not self.api_key:
            _ws_logger.warning("[BingBackend] 未配置 BING_API_KEY")
            return [{"title": "Bing 搜索未配置: 需要设置 BING_API_KEY", "content": "", "url": ""}]

        _ws_logger.info(f"[BingBackend] search: {query[:80]}")
        try:
            url = "https://api.bing.microsoft.com/v7.0/search"
            headers = {"Ocp-Apim-Subscription-Key": self.api_key}
            params = {"q": query, "count": max_results}
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(url, headers=headers, params=params)
                resp.raise_for_status()
                data = resp.json()

            results = []
            for item in data.get("webPages", {}).get("value", []):
                results.append({
                    "title": item.get("name", ""),
                    "content": item.get("snippet", ""),
                    "url": item.get("url", ""),
                })
            _ws_logger.info(f"[BingBackend] 返回 {len(results)} 条结果")
            return results
        except Exception as e:
            _ws_logger.warning(f"[BingBackend] 搜索失败: {e}")
            return [{"title": f"Bing 搜索失败: {e}", "content": "", "url": ""}]


# ── 工厂函数 ──

_backend_cache: Dict[str, BaseSearchBackend] = {}

def get_searcher(backend_name: Optional[str] = None) -> BaseSearchBackend:
    """
    获取搜索后端实例（工厂模式）
    
    Args:
        backend_name: 后端名称，可选值: duckduckgo / google / bing
                      不传则从环境变量 SEARCH_BACKEND 读取，默认 duckduckgo
    
    Returns:
        搜索后端实例
    """
    if backend_name is None:
        backend_name = os.getenv("SEARCH_BACKEND", "duckduckgo").lower()
    
    if backend_name in _backend_cache:
        return _backend_cache[backend_name]
    
    backends = {
        "duckduckgo": DuckDuckGoBackend,
        "google": GoogleBackend,
        "bing": BingBackend,
    }
    
    backend_class = backends.get(backend_name)
    if backend_class is None:
        # 未知后端，回退到 DuckDuckGo
        backend_class = DuckDuckGoBackend
    
    instance = backend_class()
    _backend_cache[backend_name] = instance
    return instance


# ── 对外接口（保持向后兼容） ──

async def web_search(query: str, max_results: int = 5) -> List[Dict[str, str]]:
    """
    通过配置的搜索引擎搜索外部信息

    Args:
        query: 搜索关键词
        max_results: 最大结果数

    Returns:
        [{title, content, url}]
    """
    _ws_logger.info(f"[web_search] query={query[:120]}, max_results={max_results}")
    searcher = get_searcher()
    return await searcher.search(query, max_results=max_results)


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