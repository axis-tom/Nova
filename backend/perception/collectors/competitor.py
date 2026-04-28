import asyncio
from typing import Dict, Any, List
from backend.common.core import Agent, AgentInput, AgentOutput
from backend.perception.connectors.rss import RSSConnector
from backend.perception.connectors.weibo import WeiboConnector

class CompetitorAgent(Agent):
    """竞品监控智能体：采集指定竞品的最新动态（RSS/社交媒体）"""
    name = "competitor_agent"
    description = "监控竞品在公开渠道的更新，返回动态列表"

    async def execute(self, input_data: AgentInput) -> AgentOutput:
        competitors = input_data.config.get("competitors", [])
        if not competitors:
            # 从用户配置获取
            competitors = await self._get_user_competitors(input_data.user_id)

        if not competitors:
            return AgentOutput(
                result=[],
                metadata={"error": "No competitors configured"},
                error="No competitors"
            )

        tasks = []
        for comp in competitors:
            # 假设每个竞品配置了类型和源
            if comp.get("type") == "rss":
                tasks.append(self._fetch_rss(comp))
            elif comp.get("type") == "weibo":
                tasks.append(self._fetch_weibo(comp))

        results = await asyncio.gather(*tasks, return_exceptions=True)
        all_updates = []
        for r in results:
            if isinstance(r, list):
                all_updates.extend(r)

        return AgentOutput(
            result=all_updates,
            metadata={"source": "competitor", "count": len(all_updates)}
        )

    async def _fetch_rss(self, comp: Dict) -> List[Dict]:
        connector = RSSConnector()
        input_data = {"url": comp["url"]}
        output = await connector.fetch(input_data)
        return output.get("data", [])

    async def _fetch_weibo(self, comp: Dict) -> List[Dict]:
        connector = WeiboConnector()
        input_data = {"uid": comp["uid"]}
        output = await connector.fetch(input_data)
        return output.get("data", [])

    async def _get_user_competitors(self, user_id: int) -> List[Dict]:
        """模拟从数据库获取用户竞品配置"""
        return []