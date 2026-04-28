import httpx
from typing import Dict, Any
from backend.perception.connectors.base import DataConnector
import json

class FeishuConnector(DataConnector):
    """飞书机器人消息推送"""
    name = "feishu_connector"

    def __init__(self, app_id: str = None, app_secret: str = None):
        self.app_id = app_id
        self.app_secret = app_secret
        self.tenant_access_token = None

    async def _get_tenant_token(self) -> str:
        """获取 tenant access token"""
        url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
        payload = {
            "app_id": self.app_id,
            "app_secret": self.app_secret
        }
        async with httpx.AsyncClient() as client:
            resp = await client.post(url, json=payload)
            data = resp.json()
            if data.get('code') == 0:
                return data['tenant_access_token']
            else:
                raise Exception(f"Failed to get token: {data}")

    async def send_message(self, receive_id: str, content: str, msg_type: str = 'text') -> bool:
        """发送消息到飞书"""
        if not self.tenant_access_token:
            self.tenant_access_token = await self._get_tenant_token()
        url = "https://open.feishu.cn/open-apis/im/v1/messages"
        headers = {
            "Authorization": f"Bearer {self.tenant_access_token}",
            "Content-Type": "application/json"
        }
        payload = {
            "receive_id": receive_id,
            "msg_type": msg_type,
            "content": json.dumps({"text": content}) if msg_type == 'text' else content
        }
        async with httpx.AsyncClient() as client:
            resp = await client.post(url, json=payload, headers=headers)
            data = resp.json()
            return data.get('code') == 0

    async def fetch(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        raise NotImplementedError

    async def push(self, output_data: Dict[str, Any], config: Dict[str, Any]) -> bool:
        """推送消息到飞书"""
        receive_id = config.get('receive_id')
        if not receive_id:
            return False
        content = output_data.get('text', '')
        return await self.send_message(receive_id, content)