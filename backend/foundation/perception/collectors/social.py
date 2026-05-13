import asyncio
from typing import Dict, Any, List
from backend.common.core import Agent, AgentInput, AgentOutput
from backend.foundation.perception.connectors.social.weibo import WeiboConnector
from backend.foundation.perception.connectors.social.xiaohongshu import XiaohongshuConnector

class SocialAgent(Agent):
    """社交媒体采集智能体：采集指定社交账号的公开内容"""
    name = "social_agent"
    description = "采集社交媒体（微博、小红书等）的公开内容"

    async def execute(self, input_data: AgentInput) -> AgentOutput:
        platforms = input_data.config.get("platforms", [])
        if not platforms:
            platforms = await self._get_user_platforms(input_data.user_id)

        if not platforms:
            return AgentOutput(
                result=[],
                metadata={"error": "No social platforms configured"},
                error="No platforms"
            )

        tasks = []
        for plat in platforms:
            if plat["type"] == "weibo":
                tasks.append(self._fetch_weibo(plat))
            elif plat["type"] == "xiaohongshu":
                tasks.append(self._fetch_xiaohongshu(plat))

        results = await asyncio.gather(*tasks, return_exceptions=True)
        all_posts = []
        for r in results:
            if isinstance(r, list):
                all_posts.extend(r)

        return AgentOutput(
            result=all_posts,
            metadata={"source": "social", "count": len(all_posts)}
        )

    async def _fetch_weibo(self, plat: Dict) -> List[Dict]:
        connector = WeiboConnector()
        input_data = {"uid": plat["uid"]}
        output = await connector.fetch(input_data)
        return output.get("data", [])

    async def _fetch_xiaohongshu(self, plat: Dict) -> List[Dict]:
        connector = XiaohongshuConnector()
        input_data = {"user_id": plat["user_id"]}
        output = await connector.fetch(input_data)
        return output.get("data", [])

    async def _get_user_platforms(self, user_id: int) -> List[Dict]:
        """模拟从数据库获取用户社交平台配置"""
        return []