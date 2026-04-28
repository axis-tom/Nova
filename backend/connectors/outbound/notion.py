import httpx
from typing import Dict, Any
from backend.perception.connectors.base import DataConnector

class NotionConnector(DataConnector):
    """Notion API 客户端"""
    name = "notion_connector"

    def __init__(self, api_key: str = None):
        self.api_key = api_key
        self.base_url = "https://api.notion.com/v1"
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Notion-Version": "2022-06-28"
        }

    async def create_page(self, database_id: str, content: Dict[str, Any]) -> bool:
        """在数据库中创建页面"""
        url = f"{self.base_url}/pages"
        payload = {
            "parent": {"database_id": database_id},
            "properties": self._build_properties(content)
        }
        async with httpx.AsyncClient() as client:
            resp = await client.post(url, json=payload, headers=self.headers)
            return resp.status_code == 200

    def _build_properties(self, content: Dict) -> Dict:
        """将内容转换为 Notion 属性格式"""
        # 简化示例，实际需要根据数据库字段映射
        properties = {}
        for key, value in content.items():
            properties[key] = {
                "title": [{"text": {"content": value}}]
            } if key == "title" else {
                "rich_text": [{"text": {"content": value}}]
            }
        return properties

    async def fetch(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """获取数据库数据（可选）"""
        raise NotImplementedError

    async def push(self, output_data: Dict[str, Any], config: Dict[str, Any]) -> bool:
        """实现 DataConnector.push，创建页面"""
        database_id = config.get('database_id')
        if not database_id:
            return False
        return await self.create_page(database_id, output_data)