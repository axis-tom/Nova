import feedparser
import asyncio
from typing import Dict, Any, List
from backend.perception.connectors.base import DataConnector  # TODO: update path after full migration

class RSSConnector(DataConnector):
    """RSS 订阅源采集"""
    name = "rss_connector"

    async def fetch(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """获取 RSS 源条目"""
        url = input_data.get('url')
        if not url:
            return {'data': [], 'status': 'error', 'error': 'Missing url'}

        # feedparser 是同步的，用 run_in_executor 执行
        loop = asyncio.get_event_loop()
        try:
            feed = await loop.run_in_executor(None, feedparser.parse, url)
            entries = []
            for entry in feed.entries[:10]:
                entries.append({
                    'title': entry.get('title', ''),
                    'link': entry.get('link', ''),
                    'published': entry.get('published', ''),
                    'summary': entry.get('summary', '')
                })
            return {'data': entries, 'status': 'success'}
        except Exception as e:
            return {'data': [], 'status': 'error', 'error': str(e)}

    async def push(self, output_data: Dict[str, Any], config: Dict[str, Any]) -> bool:
        raise NotImplementedError