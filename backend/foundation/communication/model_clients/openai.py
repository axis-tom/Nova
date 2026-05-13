import httpx
from typing import List, Dict, Any, Optional
from backend.foundation.communication.model_clients.base import ModelClient
from backend.config.config import settings

class OpenAIClient(ModelClient):
    """OpenAI API 客户端（云端增强）"""
    name = "openai"

    def __init__(self, api_key: str = None, model: str = "gpt-3.5-turbo"):
        self.api_key = api_key or settings.OPENAI_API_KEY
        self.model = model
        self.base_url = "https://api.openai.com/v1"

    async def generate(self, prompt: str, **kwargs) -> str:
        """使用 completions 接口（旧版）"""
        # 推荐使用 chat 接口，但为兼容保留
        messages = [{"role": "user", "content": prompt}]
        return await self.chat(messages, **kwargs)

    async def chat(self, messages: List[Dict[str, str]], **kwargs) -> str:
        """使用 chat completions 接口"""
        url = f"{self.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": self.model,
            "messages": messages,
            **kwargs
        }
        async with httpx.AsyncClient() as client:
            response = await client.post(url, json=payload, headers=headers, timeout=30.0)
            response.raise_for_status()
            data = response.json()
            return data["choices"][0]["message"]["content"]

# 全局实例（仅当 API_KEY 存在时可用）
openai_client = OpenAIClient() if settings.OPENAI_API_KEY else None
