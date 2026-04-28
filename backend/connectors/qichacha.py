import httpx
from typing import Dict, Any
from backend.perception.connectors.base import DataConnector

class QichachaConnector(DataConnector):
    """企查查 API 客户端（需申请 API Key）"""
    name = "qichacha_connector"

    def __init__(self, api_key: str = None):
        self.api_key = api_key
        self.base_url = "https://api.qichacha.com"

    async def fetch(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """查询企业信息"""
        company_name = input_data.get('company_name')
        if not company_name:
            return {'data': None, 'status': 'error', 'error': 'Missing company_name'}

        # 实际接口：/Search/GetSearchList?key=...&keyword=...
        params = {
            'key': self.api_key,
            'keyword': company_name
        }
        async with httpx.AsyncClient() as client:
            try:
                resp = await client.get(f"{self.base_url}/Search/GetSearchList", params=params)
                resp.raise_for_status()
                data = resp.json()
                if data.get('Status') == '200':
                    result = data.get('Result', {})
                    companies = result.get('List', [])
                    return {'data': companies, 'status': 'success'}
                else:
                    return {'data': None, 'status': 'error', 'error': data.get('Message', 'Unknown error')}
            except Exception as e:
                return {'data': None, 'status': 'error', 'error': str(e)}

    async def push(self, output_data: Dict[str, Any], config: Dict[str, Any]) -> bool:
        raise NotImplementedError