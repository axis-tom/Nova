import httpx
from typing import List, Dict, Any, Optional
from backend.core.llm.clients.base import ModelClient
from backend.config.config import settings

class OllamaClient(ModelClient):
    """Ollama 本地模型客户端"""
    name = "ollama"

    def __init__(self, base_url: str = None, model: str = None):
        self.base_url = base_url or settings.OLLAMA_BASE_URL
        self.model = model or settings.OLLAMA_MODEL

    async def generate(self, prompt: str, **kwargs) -> str:
        """使用 generate 接口"""
        url = f"{self.base_url}/api/generate"
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            **kwargs
        }
        async with httpx.AsyncClient() as client:
            response = await client.post(url, json=payload, timeout=60.0)
            response.raise_for_status()
            data = response.json()
            return data.get("response", "")

    async def chat(self, messages: List[Dict[str, str]], **kwargs) -> str:
        """使用 chat 接口"""
        url = f"{self.base_url}/api/chat"
        payload = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            **kwargs
        }
        async with httpx.AsyncClient() as client:
            response = await client.post(url, json=payload, timeout=60.0)
            response.raise_for_status()
            data = response.json()
            # Ollama chat 返回格式: {"message": {"content": ...}}
            return data.get("message", {}).get("content", "")

# 全局单例
ollama_client = OllamaClient()
