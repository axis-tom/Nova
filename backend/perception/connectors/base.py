from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

class DataConnector(ABC):
    """外部数据源连接器抽象基类"""
    name: str = "base_connector"

    @abstractmethod
    async def fetch(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """从外部源获取数据，返回统一格式字典"""
        raise NotImplementedError

    @abstractmethod
    async def push(self, output_data: Dict[str, Any], config: Dict[str, Any]) -> bool:
        """向外部源推送数据（如创建任务、发送消息），返回成功与否"""
        raise NotImplementedError