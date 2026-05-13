import asyncio
from typing import Dict, Any, List
from backend.common.core import Agent, AgentInput, AgentOutput
from backend.foundation.perception.connectors.rss import RSSConnector

class NewsAgent(Agent):
    """行业新闻采集智能体：根据订阅的RSS源拉取最新新闻"""
    name = "news_agent"
    description = "采集行业新闻RSS，返回新闻列表"

    async def execute(self, input_data: AgentInput) -> AgentOutput:
        feeds = input_data.config.get("rss_feeds", [])
        if not feeds:
            feeds = await self._get_user_feeds(input_data.user_id)

        if not feeds:
            return AgentOutput(
                result=[],
                metadata={"error": "No RSS feeds configured"},
                error="No feeds"
            )

        tasks = [self._fetch_feed(feed_url) for feed_url in feeds]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        all_news = []
        for r in results:
            if isinstance(r, list):
                all_news.extend(r)

        return AgentOutput(
            result=all_news,
            metadata={"source": "rss", "count": len(all_news)}
        )

    async def _fetch_feed(self, feed_url: str) -> List[Dict]:
        connector = RSSConnector()
        input_data = {"url": feed_url}
        output = await connector.fetch(input_data)
        return output.get("data", [])

    async def _get_user_feeds(self, user_id: int) -> List[str]:
        """模拟从数据库获取用户的RSS订阅列表"""
        return []