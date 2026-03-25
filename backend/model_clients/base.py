from abc import ABC, abstractmethod
from typing import Optional, List, Dict, Any

class ModelClient(ABC):
    """模型客户端抽象基类"""
    name: str = "base_model"

    @abstractmethod
    async def generate(self, prompt: str, **kwargs) -> str:
        """生成文本响应"""
        pass

    @abstractmethod
    async def chat(self, messages: List[Dict[str, str]], **kwargs) -> str:
        """多轮对话"""
        pass