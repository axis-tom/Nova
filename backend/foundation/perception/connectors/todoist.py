import httpx
from typing import Dict, Any, List
from backend.foundation.perception.connectors.base import DataConnector  # TODO: update path after full migration

class TodoistConnector(DataConnector):
    """Todoist API 客户端"""
    name = "todoist_connector"

    def __init__(self, api_key: str = None):
        self.api_key = api_key
        self.base_url = "https://api.todoist.com/rest/v2"

    async def add_task(self, content: str, due_string: str = None, project_id: str = None) -> bool:
        """添加任务到 Todoist"""
        url = f"{self.base_url}/tasks"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "content": content,
        }
        if due_string:
            payload["due_string"] = due_string
        if project_id:
            payload["project_id"] = project_id
        async with httpx.AsyncClient() as client:
            resp = await client.post(url, json=payload, headers=headers)
            return resp.status_code == 200

    async def fetch(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        raise NotImplementedError

    async def push(self, output_data: Dict[str, Any], config: Dict[str, Any]) -> bool:
        """推送任务到 Todoist"""
        tasks = output_data.get('tasks', [])
        if not tasks:
            return False
        for task in tasks:
            content = task.get('title', '')
            due = task.get('due')
            project_id = config.get('project_id')
            success = await self.add_task(content, due, project_id)
            if not success:
                return False
        return True